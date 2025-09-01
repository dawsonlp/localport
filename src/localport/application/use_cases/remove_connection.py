"""Use case for removing a connection from the configuration."""

import structlog
from typing import Any

from ...domain.repositories.config_repository import ConfigRepository
from ...domain.repositories.service_repository import ServiceRepository
from ...domain.exceptions import ServiceNotFoundError
from ..dto.connection_dto import (
    RemoveConnectionRequest,
    RemoveConnectionResponse
)

logger = structlog.get_logger()


class RemoveConnectionUseCase:
    """Use case for removing a connection from the configuration."""
    
    def __init__(
        self,
        config_repository: ConfigRepository,
        service_repository: ServiceRepository | None = None
    ):
        """Initialize the use case with required repositories.
        
        Args:
            config_repository: Repository for configuration management
            service_repository: Repository for service status (optional, for runtime checks)
        """
        self.config_repository = config_repository
        self.service_repository = service_repository
    
    async def execute(self, request: RemoveConnectionRequest) -> RemoveConnectionResponse:
        """Execute the remove connection use case.
        
        Args:
            request: Request containing service name and options
            
        Returns:
            Response indicating success or failure with details
        """
        try:
            logger.info("Removing connection", service_name=request.service_name)
            
            # Check if service exists in configuration
            if not await self.config_repository.service_exists(request.service_name):
                available_services = await self.config_repository.get_service_names()
                raise ServiceNotFoundError(
                    service_name=request.service_name,
                    available_services=available_services
                )
            
            # Check if service is currently running
            was_running = await self._is_service_running(request.service_name)
            
            # Create backup if requested
            backup_path = None
            if request.backup:
                backup_path = await self.config_repository.backup_configuration()
                logger.info("Created configuration backup", backup_path=backup_path)
            
            # Remove the service from configuration
            removed = await self.config_repository.remove_service_config(request.service_name)
            
            if not removed:
                return RemoveConnectionResponse.failure_response(
                    service_name=request.service_name,
                    message=f"Failed to remove service '{request.service_name}' from configuration"
                )
            
            # Prepare success message
            message = f"Removed service '{request.service_name}' from configuration"
            if was_running:
                message += " (service was running - you may want to stop it manually)"
            
            return RemoveConnectionResponse.success_response(
                service_name=request.service_name,
                was_running=was_running,
                backup_path=backup_path,
                message=message
            )
            
        except ServiceNotFoundError as e:
            logger.error("Service not found", service_name=request.service_name, error=str(e))
            return RemoveConnectionResponse.failure_response(
                service_name=request.service_name,
                message=str(e)
            )
        except Exception as e:
            logger.exception("Failed to remove connection", service_name=request.service_name)
            return RemoveConnectionResponse.failure_response(
                service_name=request.service_name,
                message=f"Failed to remove connection: {str(e)}"
            )
    
    async def _is_service_running(self, service_name: str) -> bool:
        """Check if a service is currently running.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            True if service is running, False otherwise
        """
        if not self.service_repository:
            return False
        
        try:
            # Try to get the service from the repository
            services = await self.service_repository.get_all_services()
            service = next((s for s in services if s.name == service_name), None)
            
            if service:
                return service.is_healthy()  # Check if service is in a running state
            
            return False
        except Exception as e:
            logger.warning("Could not check service running status", 
                          service_name=service_name, error=str(e))
            return False
