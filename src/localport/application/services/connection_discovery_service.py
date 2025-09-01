"""Service for discovering Kubernetes resources and managing namespace resolution."""

import structlog
from typing import Any

from ...domain.repositories.discovery_repository import (
    KubernetesDiscoveryRepository,
    ResourceNotFoundError,
    MultipleResourcesFoundError
)
from ...domain.value_objects.discovery import KubernetesResource, DiscoveredPort
from ...domain.exceptions import (
    KubernetesResourceNotFoundError,
    MultipleNamespacesFoundError,
    NoPortsAvailableError
)
from ..dto.connection_dto import DiscoveryResult

logger = structlog.get_logger()


class ConnectionDiscoveryService:
    """Service for discovering Kubernetes connections and resolving ambiguity."""
    
    def __init__(self, discovery_repository: KubernetesDiscoveryRepository):
        """Initialize the service with a discovery repository.
        
        Args:
            discovery_repository: Repository for Kubernetes discovery operations
        """
        self.discovery_repository = discovery_repository
    
    async def discover_kubectl_connection(
        self,
        resource_name: str,
        namespace: str | None = None,
        resource_type: str = "service"
    ) -> DiscoveryResult:
        """Discover a Kubernetes resource with intelligent namespace resolution.
        
        Args:
            resource_name: Name of the resource to discover
            namespace: Optional namespace (if not provided, will search intelligently)
            resource_type: Type of resource (service, pod, deployment)
            
        Returns:
            DiscoveryResult with found resource or multiple namespace options
        """
        logger.debug("Discovering Kubernetes resource", 
                    resource_name=resource_name,
                    namespace=namespace,
                    resource_type=resource_type)
        
        try:
            if namespace:
                # Explicit namespace provided - search only there
                return await self._find_in_specific_namespace(
                    resource_name, namespace, resource_type
                )
            else:
                # No namespace provided - use intelligent discovery
                return await self._intelligent_namespace_discovery(
                    resource_name, resource_type
                )
                
        except Exception as e:
            logger.exception("Discovery failed", 
                           resource_name=resource_name, 
                           namespace=namespace,
                           resource_type=resource_type)
            return DiscoveryResult.not_found(
                warnings=[f"Discovery failed: {str(e)}"]
            )
    
    async def resolve_namespace_ambiguity(
        self,
        resource_name: str,
        namespaces: list[str],
        resource_type: str = "service"
    ) -> dict[str, KubernetesResource]:
        """Resolve namespace ambiguity by getting resource details from all namespaces.
        
        Args:
            resource_name: Name of the resource
            namespaces: List of namespaces where resource was found
            resource_type: Type of resource
            
        Returns:
            Dictionary mapping namespace to KubernetesResource
        """
        logger.debug("Resolving namespace ambiguity",
                    resource_name=resource_name,
                    namespaces=namespaces,
                    resource_type=resource_type)
        
        namespace_resources = {}
        
        for namespace in namespaces:
            try:
                resource = await self.discovery_repository.find_resource(
                    name=resource_name,
                    namespace=namespace,
                    resource_type=resource_type
                )
                
                if resource:
                    namespace_resources[namespace] = resource
                    
            except Exception as e:
                logger.warning("Failed to get resource details",
                             resource_name=resource_name,
                             namespace=namespace,
                             error=str(e))
                continue
        
        return namespace_resources
    
    async def validate_connection_availability(self) -> bool:
        """Validate that kubectl is available and can connect to a cluster.
        
        Returns:
            True if kubectl connection is available, False otherwise
        """
        try:
            return await self.discovery_repository.validate_connection()
        except Exception as e:
            logger.warning("Kubectl connection validation failed", error=str(e))
            return False
    
    async def get_cluster_context(self) -> dict[str, Any]:
        """Get current cluster context information.
        
        Returns:
            Dictionary with cluster context information
        """
        try:
            cluster_info = await self.discovery_repository.get_cluster_info()
            current_namespace = await self.discovery_repository.get_current_namespace()
            
            return {
                "cluster_info": cluster_info,
                "current_namespace": current_namespace,
                "available": True
            }
        except Exception as e:
            logger.warning("Failed to get cluster context", error=str(e))
            return {
                "cluster_info": {},
                "current_namespace": "unknown",
                "available": False,
                "error": str(e)
            }
    
    async def _find_in_specific_namespace(
        self,
        resource_name: str,
        namespace: str,
        resource_type: str
    ) -> DiscoveryResult:
        """Find resource in a specific namespace.
        
        Args:
            resource_name: Name of the resource
            namespace: Specific namespace to search
            resource_type: Type of resource
            
        Returns:
            DiscoveryResult with resource or not found
        """
        try:
            resource = await self.discovery_repository.find_resource(
                name=resource_name,
                namespace=namespace,
                resource_type=resource_type
            )
            
            if resource:
                return DiscoveryResult.found_single(resource)
            else:
                return DiscoveryResult.not_found(
                    warnings=[f"Resource '{resource_name}' not found in namespace '{namespace}'"]
                )
                
        except Exception as e:
            logger.exception("Failed to find resource in specific namespace")
            return DiscoveryResult.not_found(
                warnings=[f"Search failed in namespace '{namespace}': {str(e)}"]
            )
    
    async def _intelligent_namespace_discovery(
        self,
        resource_name: str,
        resource_type: str
    ) -> DiscoveryResult:
        """Perform intelligent namespace discovery with fallback strategy.
        
        Discovery strategy:
        1. Try current namespace
        2. Try default namespace (if different)
        3. Search all namespaces
        
        Args:
            resource_name: Name of the resource
            resource_type: Type of resource
            
        Returns:
            DiscoveryResult with discovered resource or multiple options
        """
        warnings = []
        
        try:
            # Step 1: Try current namespace
            current_namespace = await self.discovery_repository.get_current_namespace()
            logger.debug("Trying current namespace", namespace=current_namespace)
            
            resource = await self.discovery_repository.find_resource(
                name=resource_name,
                namespace=current_namespace,
                resource_type=resource_type
            )
            
            if resource:
                logger.debug("Found resource in current namespace", namespace=current_namespace)
                return DiscoveryResult.found_single(
                    resource,
                    warnings=[f"Found in current namespace: {current_namespace}"]
                )
            
            warnings.append(f"Not found in current namespace: {current_namespace}")
            
        except Exception as e:
            logger.warning("Failed to check current namespace", error=str(e))
            warnings.append(f"Failed to check current namespace: {str(e)}")
        
        try:
            # Step 2: Try default namespace if different
            current_namespace = await self.discovery_repository.get_current_namespace()
            if current_namespace != "default":
                logger.debug("Trying default namespace")
                
                resource = await self.discovery_repository.find_resource(
                    name=resource_name,
                    namespace="default",
                    resource_type=resource_type
                )
                
                if resource:
                    logger.debug("Found resource in default namespace")
                    return DiscoveryResult.found_single(
                        resource,
                        warnings=warnings + ["Found in default namespace"]
                    )
                
                warnings.append("Not found in default namespace")
            
        except Exception as e:
            logger.warning("Failed to check default namespace", error=str(e))
            warnings.append(f"Failed to check default namespace: {str(e)}")
        
        try:
            # Step 3: Search all namespaces
            logger.debug("Searching all namespaces")
            
            all_matches = await self.discovery_repository.search_all_namespaces(
                resource_name=resource_name,
                resource_type=resource_type
            )
            
            if not all_matches:
                logger.debug("Resource not found in any namespace")
                return DiscoveryResult.not_found(
                    warnings=warnings + ["Resource not found in any namespace"]
                )
            
            elif len(all_matches) == 1:
                # Found in exactly one namespace
                namespace, resource = all_matches[0]
                logger.debug("Found resource in single namespace", namespace=namespace)
                return DiscoveryResult.found_single(
                    resource,
                    warnings=warnings + [f"Found in namespace: {namespace}"]
                )
            
            else:
                # Found in multiple namespaces - need user selection
                namespaces = [ns for ns, _ in all_matches]
                logger.debug("Found resource in multiple namespaces", namespaces=namespaces)
                return DiscoveryResult.found_multiple_namespaces(
                    namespaces,
                    warnings=warnings + [f"Found in {len(namespaces)} namespaces"]
                )
                
        except Exception as e:
            logger.exception("Failed to search all namespaces")
            return DiscoveryResult.not_found(
                warnings=warnings + [f"Failed to search all namespaces: {str(e)}"]
            )
    
    async def get_resource_suggestions(
        self,
        partial_name: str,
        namespace: str | None = None,
        resource_type: str = "service",
        limit: int = 5
    ) -> list[str]:
        """Get suggestions for similar resource names (for error messages).
        
        Args:
            partial_name: Partial or incorrect resource name
            namespace: Optional namespace to search in
            resource_type: Type of resource
            limit: Maximum number of suggestions
            
        Returns:
            List of suggested resource names
        """
        try:
            # This is a simplified implementation
            # In a real implementation, you might use kubectl to list resources
            # and find similar names
            
            if namespace:
                # Search in specific namespace
                # For now, return empty list - would need kubectl list implementation
                return []
            else:
                # Search across namespaces
                # For now, return empty list - would need kubectl list implementation
                return []
                
        except Exception as e:
            logger.warning("Failed to get resource suggestions", 
                          partial_name=partial_name, error=str(e))
            return []
