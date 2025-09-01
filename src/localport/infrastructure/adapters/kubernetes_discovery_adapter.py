"""Kubernetes discovery adapter for finding resources and ports."""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional, Tuple

import structlog

from ...domain.repositories.discovery_repository import KubernetesDiscoveryRepository
from ...domain.value_objects.discovery import KubernetesResource, DiscoveredPort
from ...domain.exceptions import (
    KubernetesResourceNotFoundError,
    MultipleNamespacesFoundError,
    NoPortsAvailableError
)
from ..cluster_monitoring.kubectl_client import KubectlClient, KubectlError

logger = structlog.get_logger()


class KubernetesDiscoveryAdapter(KubernetesDiscoveryRepository):
    """Adapter for discovering Kubernetes resources using kubectl."""
    
    def __init__(self, kubectl_client: Optional[KubectlClient] = None, context: Optional[str] = None):
        """Initialize the Kubernetes discovery adapter.
        
        Args:
            kubectl_client: Optional kubectl client (creates default if None)
            context: Kubernetes context to use (uses current context if None)
        """
        self.kubectl_client = kubectl_client or KubectlClient()
        self.context = context
        
    async def find_resource(self, name: str, namespace: Optional[str] = None) -> Optional[KubernetesResource]:
        """Find a Kubernetes resource by name and optional namespace.
        
        Args:
            name: Resource name to find
            namespace: Optional namespace to search in
            
        Returns:
            KubernetesResource if found, None otherwise
        """
        logger.debug("Finding Kubernetes resource", name=name, namespace=namespace)
        
        # Resource types to search for (in order of preference for port forwarding)
        resource_types = ["service", "pod", "deployment"]
        
        for resource_type in resource_types:
            try:
                resource = await self._find_resource_by_type(name, resource_type, namespace)
                if resource:
                    logger.debug("Found resource", resource_type=resource_type, name=name, namespace=resource.namespace)
                    return resource
                    
            except Exception as e:
                logger.warning("Error searching for resource", resource_type=resource_type, name=name, error=str(e))
                continue
        
        logger.debug("Resource not found", name=name, namespace=namespace)
        return None

    async def get_available_ports(self, resource_name: str, namespace: str) -> List[DiscoveredPort]:
        """Get available ports for a specific resource.
        
        Args:
            resource_name: Name of the resource
            namespace: Namespace of the resource
            
        Returns:
            List of discovered ports
        """
        logger.debug("Getting available ports", resource_name=resource_name, namespace=namespace)
        
        # Try to find the resource first to determine its type
        resource = await self.find_resource(resource_name, namespace)
        if not resource:
            raise KubernetesResourceNotFoundError(f"Resource '{resource_name}' not found in namespace '{namespace}'")
        
        # Get ports based on resource type
        if resource.resource_type == "service":
            return await self._get_service_ports(resource_name, namespace)
        elif resource.resource_type == "pod":
            return await self._get_pod_ports(resource_name, namespace)
        elif resource.resource_type == "deployment":
            return await self._get_deployment_ports(resource_name, namespace)
        else:
            logger.warning("Unknown resource type for port discovery", resource_type=resource.resource_type)
            return []

    async def get_current_namespace(self) -> str:
        """Get the current Kubernetes namespace from context.
        
        Returns:
            Current namespace name
        """
        try:
            context_args = ["--context", self.context] if self.context else []
            cmd = ["kubectl", "config", "view", "--minify", "--output=json"] + context_args
            
            stdout, stderr, returncode = await self.kubectl_client._execute_command(cmd)
            
            if returncode != 0:
                logger.warning("Failed to get current namespace, using default", error=stderr)
                return "default"
            
            # Parse the kubectl config output
            config_data = json.loads(stdout)
            current_context = config_data.get("current-context")
            
            if not current_context:
                return "default"
            
            # Find the context and get its namespace
            for context_info in config_data.get("contexts", []):
                if context_info.get("name") == current_context:
                    context_config = context_info.get("context", {})
                    namespace = context_config.get("namespace", "default")
                    logger.debug("Found current namespace", namespace=namespace)
                    return namespace
            
            return "default"
            
        except Exception as e:
            logger.warning("Error getting current namespace", error=str(e))
            return "default"

    async def search_all_namespaces(self, resource_name: str) -> List[Tuple[str, KubernetesResource]]:
        """Search for a resource across all namespaces.
        
        Args:
            resource_name: Name of the resource to search for
            
        Returns:
            List of tuples containing (namespace, resource) for each match
        """
        logger.debug("Searching all namespaces", resource_name=resource_name)
        
        matches = []
        resource_types = ["service", "pod", "deployment"]
        
        for resource_type in resource_types:
            try:
                namespace_matches = await self._search_resource_all_namespaces(resource_name, resource_type)
                matches.extend(namespace_matches)
                
            except Exception as e:
                logger.warning("Error searching all namespaces", resource_type=resource_type, error=str(e))
                continue
        
        logger.debug("Search completed", resource_name=resource_name, matches_found=len(matches))
        return matches

    async def _find_resource_by_type(
        self, 
        name: str, 
        resource_type: str, 
        namespace: Optional[str] = None
    ) -> Optional[KubernetesResource]:
        """Find a specific resource by type."""
        try:
            context_args = ["--context", self.context] if self.context else []
            namespace_args = ["-n", namespace] if namespace else []
            
            cmd = ["kubectl", "get", resource_type, name, "--output=json"] + namespace_args + context_args
            
            stdout, stderr, returncode = await self.kubectl_client._execute_command(cmd)
            
            if returncode != 0:
                if "not found" in stderr.lower() or "no resources found" in stderr.lower():
                    return None
                else:
                    logger.warning("kubectl command failed", cmd=" ".join(cmd), error=stderr)
                    return None
            
            # Parse JSON response
            resource_data = json.loads(stdout)
            return await self._parse_resource_data(resource_data, resource_type)
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse kubectl JSON output", error=str(e))
            return None
        except Exception as e:
            logger.warning("Error finding resource", name=name, resource_type=resource_type, error=str(e))
            return None

    async def _search_resource_all_namespaces(
        self, 
        resource_name: str, 
        resource_type: str
    ) -> List[Tuple[str, KubernetesResource]]:
        """Search for a resource across all namespaces for a specific resource type."""
        try:
            context_args = ["--context", self.context] if self.context else []
            
            cmd = [
                "kubectl", "get", resource_type, 
                "--all-namespaces", 
                "--output=json",
                "--field-selector", f"metadata.name={resource_name}"
            ] + context_args
            
            stdout, stderr, returncode = await self.kubectl_client._execute_command(cmd)
            
            if returncode != 0:
                logger.warning("Failed to search all namespaces", resource_type=resource_type, error=stderr)
                return []
            
            # Parse JSON response
            data = json.loads(stdout)
            matches = []
            
            for item in data.get("items", []):
                resource = await self._parse_resource_data(item, resource_type)
                if resource and resource.name == resource_name:
                    matches.append((resource.namespace, resource))
            
            return matches
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse kubectl JSON output", error=str(e))
            return []
        except Exception as e:
            logger.warning("Error searching all namespaces", resource_name=resource_name, error=str(e))
            return []

    async def _parse_resource_data(self, resource_data: Dict[str, Any], resource_type: str) -> Optional[KubernetesResource]:
        """Parse kubectl JSON output into a KubernetesResource."""
        try:
            metadata = resource_data.get("metadata", {})
            name = metadata.get("name")
            namespace = metadata.get("namespace", "default")
            
            if not name:
                logger.warning("Resource missing name in metadata")
                return None
            
            # Extract available ports based on resource type
            available_ports = await self._extract_ports_from_resource_data(resource_data, resource_type)
            
            return KubernetesResource(
                name=name,
                namespace=namespace,
                resource_type=resource_type,
                available_ports=available_ports
            )
            
        except Exception as e:
            logger.warning("Error parsing resource data", error=str(e))
            return None

    async def _extract_ports_from_resource_data(
        self, 
        resource_data: Dict[str, Any], 
        resource_type: str
    ) -> List[DiscoveredPort]:
        """Extract ports from resource data based on resource type."""
        ports = []
        
        try:
            if resource_type == "service":
                spec = resource_data.get("spec", {})
                for port_spec in spec.get("ports", []):
                    port_number = port_spec.get("port")
                    protocol = port_spec.get("protocol", "TCP").upper()
                    name = port_spec.get("name", f"port-{port_number}")
                    target_port = port_spec.get("targetPort", port_number)
                    
                    if port_number:
                        ports.append(DiscoveredPort(
                            port=int(port_number),
                            protocol=protocol,
                            name=name,
                            description=f"Service port {port_number} -> {target_port}"
                        ))
                        
            elif resource_type == "pod":
                spec = resource_data.get("spec", {})
                for container in spec.get("containers", []):
                    for port_spec in container.get("ports", []):
                        port_number = port_spec.get("containerPort")
                        protocol = port_spec.get("protocol", "TCP").upper()
                        name = port_spec.get("name", f"port-{port_number}")
                        
                        if port_number:
                            ports.append(DiscoveredPort(
                                port=int(port_number),
                                protocol=protocol,
                                name=name,
                                description=f"Container port {port_number} in {container.get('name', 'container')}"
                            ))
                            
            elif resource_type == "deployment":
                spec = resource_data.get("spec", {})
                template = spec.get("template", {})
                pod_spec = template.get("spec", {})
                
                for container in pod_spec.get("containers", []):
                    for port_spec in container.get("ports", []):
                        port_number = port_spec.get("containerPort")
                        protocol = port_spec.get("protocol", "TCP").upper()
                        name = port_spec.get("name", f"port-{port_number}")
                        
                        if port_number:
                            ports.append(DiscoveredPort(
                                port=int(port_number),
                                protocol=protocol,
                                name=name,
                                description=f"Deployment port {port_number} in {container.get('name', 'container')}"
                            ))
                            
        except Exception as e:
            logger.warning("Error extracting ports from resource data", resource_type=resource_type, error=str(e))
        
        return ports

    async def _get_service_ports(self, service_name: str, namespace: str) -> List[DiscoveredPort]:
        """Get ports for a service."""
        try:
            context_args = ["--context", self.context] if self.context else []
            
            cmd = [
                "kubectl", "get", "service", service_name,
                "-n", namespace,
                "--output=json"
            ] + context_args
            
            stdout, stderr, returncode = await self.kubectl_client._execute_command(cmd)
            
            if returncode != 0:
                raise KubernetesResourceNotFoundError(f"Service '{service_name}' not found in namespace '{namespace}': {stderr}")
            
            service_data = json.loads(stdout)
            return await self._extract_ports_from_resource_data(service_data, "service")
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse service JSON", error=str(e))
            return []

    async def _get_pod_ports(self, pod_name: str, namespace: str) -> List[DiscoveredPort]:
        """Get ports for a pod."""
        try:
            context_args = ["--context", self.context] if self.context else []
            
            cmd = [
                "kubectl", "get", "pod", pod_name,
                "-n", namespace,
                "--output=json"
            ] + context_args
            
            stdout, stderr, returncode = await self.kubectl_client._execute_command(cmd)
            
            if returncode != 0:
                raise KubernetesResourceNotFoundError(f"Pod '{pod_name}' not found in namespace '{namespace}': {stderr}")
            
            pod_data = json.loads(stdout)
            return await self._extract_ports_from_resource_data(pod_data, "pod")
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse pod JSON", error=str(e))
            return []

    async def _get_deployment_ports(self, deployment_name: str, namespace: str) -> List[DiscoveredPort]:
        """Get ports for a deployment."""
        try:
            context_args = ["--context", self.context] if self.context else []
            
            cmd = [
                "kubectl", "get", "deployment", deployment_name,
                "-n", namespace,
                "--output=json"
            ] + context_args
            
            stdout, stderr, returncode = await self.kubectl_client._execute_command(cmd)
            
            if returncode != 0:
                raise KubernetesResourceNotFoundError(f"Deployment '{deployment_name}' not found in namespace '{namespace}': {stderr}")
            
            deployment_data = json.loads(stdout)
            return await self._extract_ports_from_resource_data(deployment_data, "deployment")
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse deployment JSON", error=str(e))
            return []
