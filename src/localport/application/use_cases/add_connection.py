"""Use case for adding a new connection to the configuration."""

import structlog
from typing import Any

from ...domain.repositories.config_repository import ConfigRepository
from ...domain.repositories.discovery_repository import KubernetesDiscoveryRepository
from ...domain.enums import ForwardingTechnology
from ...domain.entities.service import Service
from ...domain.exceptions import (
    ServiceAlreadyExistsError,
    KubernetesResourceNotFoundError,
    MultipleNamespacesFoundError,
    NoPortsAvailableError
)
from ..dto.connection_dto import (
    AddConnectionRequest,
    AddConnectionResponse,
    DiscoveryResult
)

logger = structlog.get_logger()


class AddConnectionUseCase:
    """Use case for adding a new connection to the configuration."""
    
    def __init__(
        self,
        config_repository: ConfigRepository,
        discovery_repository: KubernetesDiscoveryRepository | None = None
    ):
        """Initialize the use case with required repositories.
        
        Args:
            config_repository: Repository for configuration management
            discovery_repository: Repository for Kubernetes discovery (optional for SSH)
        """
        self.config_repository = config_repository
        self.discovery_repository = discovery_repository
    
    async def execute(self, request: AddConnectionRequest) -> AddConnectionResponse:
        """Execute the add connection use case.
        
        Args:
            request: Request containing connection details
            
        Returns:
            Response indicating success or failure with details
        """
        try:
            logger.info("Adding new connection", 
                       service_name=request.service_name,
                       technology=request.technology.value)
            
            # Validate that service name doesn't already exist
            await self._validate_service_name(request)
            
            if request.technology == ForwardingTechnology.KUBECTL:
                return await self._handle_kubectl_connection(request)
            elif request.technology == ForwardingTechnology.SSH:
                return await self._handle_ssh_connection(request)
            else:
                return AddConnectionResponse.failure_response(
                    service_name=request.service_name or "unknown",
                    message=f"Unsupported technology: {request.technology.value}"
                )
                
        except ServiceAlreadyExistsError as e:
            logger.error("Service already exists", service_name=request.service_name, error=str(e))
            return AddConnectionResponse.failure_response(
                service_name=request.service_name or "unknown",
                message=str(e)
            )
        except Exception as e:
            logger.exception("Failed to add connection", service_name=request.service_name)
            return AddConnectionResponse.failure_response(
                service_name=request.service_name or "unknown",
                message=f"Failed to add connection: {str(e)}"
            )
    
    async def _validate_service_name(self, request: AddConnectionRequest) -> None:
        """Validate that the service name doesn't already exist.
        
        Args:
            request: Connection request
            
        Raises:
            ServiceAlreadyExistsError: If service already exists
        """
        # For kubectl, default service name to resource name if not provided
        service_name = request.service_name
        if not service_name and request.technology == ForwardingTechnology.KUBECTL:
            service_name = request.connection_params.get("resource_name")
        
        if not service_name:
            raise ValueError("Service name is required for SSH connections")
        
        # Update the request with the resolved service name
        request.service_name = service_name
        
        # Check if service already exists
        if await self.config_repository.service_exists(service_name):
            raise ServiceAlreadyExistsError(service_name)
    
    async def _handle_kubectl_connection(self, request: AddConnectionRequest) -> AddConnectionResponse:
        """Handle adding a kubectl connection with discovery.
        
        Args:
            request: kubectl connection request
            
        Returns:
            Response with connection details
        """
        if not self.discovery_repository:
            return AddConnectionResponse.failure_response(
                service_name=request.service_name,
                message="Kubernetes discovery is not available. Cannot add kubectl connection."
            )
        
        # Perform resource discovery
        discovery_result = await self._discover_kubernetes_resource(request)
        
        if not discovery_result.found:
            return AddConnectionResponse.failure_response(
                service_name=request.service_name,
                message=f"Kubernetes resource '{request.connection_params['resource_name']}' not found"
            )
        
        # Handle namespace ambiguity
        if discovery_result.needs_namespace_selection:
            raise MultipleNamespacesFoundError(
                resource_name=request.connection_params["resource_name"],
                namespaces=discovery_result.multiple_namespaces
            )
        
        # Handle port selection/discovery
        if not discovery_result.selected_port and discovery_result.resource:
            if discovery_result.resource.has_ports:
                # Auto-select port if only one available
                if discovery_result.has_single_port:
                    discovery_result.selected_port = discovery_result.resource.single_port
                else:
                    # Use default port selection logic
                    discovery_result.selected_port = discovery_result.resource.get_default_port()
            else:
                raise NoPortsAvailableError(
                    resource_name=request.connection_params["resource_name"],
                    namespace=discovery_result.resource.namespace,
                    resource_type=request.connection_params.get("resource_type", "service")
                )
        
        # Create service configuration
        service_config = await self._create_kubectl_service_config(request, discovery_result)
        
        # Add to configuration
        await self.config_repository.add_service_config(service_config)
        
        # Prepare response
        discovered_info = {
            "namespace": discovery_result.resource.namespace,
            "resource_type": discovery_result.resource.resource_type,
            "available_ports": [port.to_dict() for port in discovery_result.resource.available_ports],
            "selected_port": discovery_result.selected_port.to_dict() if discovery_result.selected_port else None
        }
        
        return AddConnectionResponse.success_response(
            service_name=request.service_name,
            configuration_added=service_config,
            discovered_info=discovered_info,
            warnings=discovery_result.warnings,
            message=f"Added kubectl connection '{request.service_name}' successfully"
        )
    
    async def _handle_ssh_connection(self, request: AddConnectionRequest) -> AddConnectionResponse:
        """Handle adding an SSH connection.
        
        Args:
            request: SSH connection request
            
        Returns:
            Response with connection details
        """
        # For SSH, we need explicit ports since there's no discovery
        local_port = request.options.get("local_port")
        remote_port = request.options.get("remote_port")
        
        if not local_port:
            raise ValueError("Local port is required for SSH connections")
        if not remote_port:
            raise ValueError("Remote port is required for SSH connections")
        
        # Create service configuration
        service_config = await self._create_ssh_service_config(request, local_port, remote_port)
        
        # Add to configuration
        await self.config_repository.add_service_config(service_config)
        
        return AddConnectionResponse.success_response(
            service_name=request.service_name,
            configuration_added=service_config,
            message=f"Added SSH connection '{request.service_name}' successfully"
        )
    
    async def _discover_kubernetes_resource(self, request: AddConnectionRequest) -> DiscoveryResult:
        """Discover a Kubernetes resource and handle namespace resolution.
        
        Args:
            request: kubectl connection request
            
        Returns:
            Discovery result with resource information
        """
        resource_name = request.connection_params["resource_name"]
        resource_type = request.connection_params.get("resource_type", "service")
        namespace = request.connection_params.get("namespace")
        
        try:
            if namespace:
                # Try specific namespace first
                resource = await self.discovery_repository.find_resource(
                    name=resource_name,
                    namespace=namespace,
                    resource_type=resource_type
                )
                
                if resource:
                    return DiscoveryResult.found_single(resource)
                else:
                    return DiscoveryResult.not_found()
            
            else:
                # Try current namespace first
                current_namespace = await self.discovery_repository.get_current_namespace()
                resource = await self.discovery_repository.find_resource(
                    name=resource_name,
                    namespace=current_namespace,
                    resource_type=resource_type
                )
                
                if resource:
                    return DiscoveryResult.found_single(resource)
                
                # Try default namespace if different
                if current_namespace != "default":
                    resource = await self.discovery_repository.find_resource(
                        name=resource_name,
                        namespace="default",
                        resource_type=resource_type
                    )
                    
                    if resource:
                        return DiscoveryResult.found_single(resource)
                
                # Search all namespaces
                all_matches = await self.discovery_repository.search_all_namespaces(
                    resource_name=resource_name,
                    resource_type=resource_type
                )
                
                if not all_matches:
                    return DiscoveryResult.not_found()
                elif len(all_matches) == 1:
                    namespace, resource = all_matches[0]
                    return DiscoveryResult.found_single(resource)
                else:
                    namespaces = [ns for ns, _ in all_matches]
                    return DiscoveryResult.found_multiple_namespaces(namespaces)
                    
        except Exception as e:
            logger.exception("Error during resource discovery", resource_name=resource_name)
            return DiscoveryResult.not_found(warnings=[f"Discovery failed: {str(e)}"])
    
    async def _create_kubectl_service_config(
        self, 
        request: AddConnectionRequest, 
        discovery: DiscoveryResult
    ) -> dict[str, Any]:
        """Create service configuration for kubectl connection.
        
        Args:
            request: Connection request
            discovery: Discovery result with resource information
            
        Returns:
            Service configuration dictionary
        """
        local_port = request.options.get("local_port")
        if not local_port:
            raise ValueError("Local port is required")
        
        remote_port = discovery.selected_port.port if discovery.selected_port else None
        if not remote_port:
            raise ValueError("Remote port could not be determined from discovery")
        
        return {
            "name": request.service_name,
            "technology": "kubectl",
            "local_port": local_port,
            "remote_port": remote_port,
            "connection": {
                "resource_name": request.connection_params["resource_name"],
                "namespace": discovery.resource.namespace,
                "resource_type": discovery.resource.resource_type,
                **{k: v for k, v in request.connection_params.items() 
                   if k not in ["resource_name", "namespace", "resource_type"] and v is not None}
            },
            **{k: v for k, v in request.options.items() 
               if k not in ["local_port"] and v is not None}
        }
    
    async def _create_ssh_service_config(
        self, 
        request: AddConnectionRequest, 
        local_port: int,
        remote_port: int
    ) -> dict[str, Any]:
        """Create service configuration for SSH connection.
        
        Args:
            request: Connection request
            local_port: Local port to bind
            remote_port: Remote port to forward to
            
        Returns:
            Service configuration dictionary
        """
        return {
            "name": request.service_name,
            "technology": "ssh",
            "local_port": local_port,
            "remote_port": remote_port,
            "connection": {
                **request.connection_params,
                # Ensure remote_host defaults to localhost if not specified
                "remote_host": request.connection_params.get("remote_host", "localhost")
            },
            **{k: v for k, v in request.options.items() 
               if k not in ["local_port", "remote_port"] and v is not None}
        }


def to_dict(obj) -> dict[str, Any]:
    """Convert a discovery object to dictionary (helper function)."""
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    else:
        return {"port": obj.port, "protocol": obj.protocol, "name": obj.name}
