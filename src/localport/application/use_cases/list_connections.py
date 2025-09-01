"""Use case for listing configured connections."""

import structlog
from typing import Any

from ...domain.repositories.config_repository import ConfigRepository
from ..dto.connection_dto import (
    ListConnectionsRequest,
    ListConnectionsResponse,
    ServiceSummary
)

logger = structlog.get_logger()


class ListConnectionsUseCase:
    """Use case for listing all configured connections."""
    
    def __init__(self, config_repository: ConfigRepository):
        """Initialize the use case with required repositories.
        
        Args:
            config_repository: Repository for configuration management
        """
        self.config_repository = config_repository
    
    async def execute(self, request: ListConnectionsRequest) -> ListConnectionsResponse:
        """Execute the list connections use case.
        
        Args:
            request: Request containing filtering and sorting options
            
        Returns:
            Response with list of configured connections
        """
        try:
            logger.debug("Listing configured connections", 
                        filter_technology=request.filter_technology,
                        filter_tags=request.filter_tags,
                        include_disabled=request.include_disabled,
                        sort_by=request.sort_by)
            
            # Load configuration
            config = await self.config_repository.load_configuration()
            services_config = config.get('services', [])
            
            # Convert to ServiceSummary objects
            services = []
            for service_config in services_config:
                try:
                    service_summary = self._create_service_summary(service_config)
                    services.append(service_summary)
                except Exception as e:
                    logger.warning("Skipping invalid service configuration", 
                                  service_name=service_config.get('name', 'unknown'),
                                  error=str(e))
                    continue
            
            # Apply filters
            filtered_services = self._apply_filters(services, request)
            
            # Apply sorting
            sorted_services = self._apply_sorting(filtered_services, request.sort_by)
            
            return ListConnectionsResponse.success_response(
                services=sorted_services,
                message=f"Found {len(sorted_services)} configured connection(s)"
            )
            
        except Exception as e:
            logger.exception("Failed to list connections")
            return ListConnectionsResponse.failure_response(
                message=f"Failed to list connections: {str(e)}"
            )
    
    def _create_service_summary(self, service_config: dict[str, Any]) -> ServiceSummary:
        """Create a ServiceSummary from service configuration.
        
        Args:
            service_config: Service configuration dictionary
            
        Returns:
            ServiceSummary object
        """
        name = service_config.get('name', 'unnamed')
        technology = service_config.get('technology', 'unknown')
        local_port = service_config.get('local_port', 0)
        remote_port = service_config.get('remote_port', 0)
        connection_params = service_config.get('connection', {})
        enabled = service_config.get('enabled', True)
        tags = service_config.get('tags', [])
        description = service_config.get('description')
        
        # Create human-readable target description
        target = self._create_target_description(service_config)
        
        return ServiceSummary(
            name=name,
            technology=technology,
            target=target,
            local_port=local_port,
            remote_port=remote_port,
            connection_params=connection_params,
            enabled=enabled,
            tags=tags,
            description=description
        )
    
    def _create_target_description(self, service_config: dict[str, Any]) -> str:
        """Create a human-readable target description.
        
        Args:
            service_config: Service configuration dictionary
            
        Returns:
            Human-readable target description
        """
        technology = service_config.get('technology', 'unknown')
        remote_port = service_config.get('remote_port', 0)
        connection = service_config.get('connection', {})
        
        if technology == 'kubectl':
            resource_name = connection.get('resource_name', 'unknown')
            namespace = connection.get('namespace', 'default')
            resource_type = connection.get('resource_type', 'service')
            
            if namespace == 'default':
                return f"{resource_name}:{remote_port}"
            else:
                return f"{resource_name}:{remote_port} ({namespace})"
        
        elif technology == 'ssh':
            host = connection.get('host', 'unknown')
            remote_host = connection.get('remote_host', 'localhost')
            
            if remote_host == 'localhost':
                return f"{host}:{remote_port}"
            else:
                return f"{host} → {remote_host}:{remote_port}"
        
        else:
            return f"unknown:{remote_port}"
    
    def _apply_filters(
        self, 
        services: list[ServiceSummary], 
        request: ListConnectionsRequest
    ) -> list[ServiceSummary]:
        """Apply filtering to the service list.
        
        Args:
            services: List of services to filter
            request: Request containing filter criteria
            
        Returns:
            Filtered list of services
        """
        filtered = services
        
        # Filter by technology
        if request.filter_technology:
            filtered = [s for s in filtered if s.technology == request.filter_technology]
        
        # Filter by tags
        if request.filter_tags:
            filtered = [s for s in filtered 
                       if any(tag in s.tags for tag in request.filter_tags)]
        
        # Filter by enabled status
        if not request.include_disabled:
            filtered = [s for s in filtered if s.enabled]
        
        return filtered
    
    def _apply_sorting(
        self, 
        services: list[ServiceSummary], 
        sort_by: str
    ) -> list[ServiceSummary]:
        """Apply sorting to the service list.
        
        Args:
            services: List of services to sort
            sort_by: Field to sort by (name, technology, local_port)
            
        Returns:
            Sorted list of services
        """
        if sort_by == "name":
            return sorted(services, key=lambda s: s.name.lower())
        elif sort_by == "technology":
            return sorted(services, key=lambda s: (s.technology, s.name.lower()))
        elif sort_by == "local_port":
            return sorted(services, key=lambda s: (s.local_port, s.name.lower()))
        else:
            logger.warning("Unknown sort field, using default", sort_by=sort_by)
            return sorted(services, key=lambda s: s.name.lower())
