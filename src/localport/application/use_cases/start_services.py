"""Use case for starting port forwarding services."""

from dataclasses import dataclass

import structlog

from ...domain.entities.service import Service
from ...domain.repositories.service_repository import (
    ServiceNotFoundError,
    ServiceRepository,
)
from ..dto.service_dto import BulkOperationResult, ServiceStartResult
from ..services.service_manager import ServiceManager

logger = structlog.get_logger()


@dataclass
class StartServicesCommand:
    """Command to start services."""
    service_names: list[str] | None = None
    tags: list[str] | None = None
    all_services: bool = False
    force_restart: bool = False
    wait_for_health: bool = True
    health_timeout: float = 30.0


class StartServicesUseCase:
    """Use case for starting port forwarding services."""

    def __init__(
        self,
        service_repository: ServiceRepository,
        service_manager: ServiceManager
    ):
        self._service_repository = service_repository
        self._service_manager = service_manager

    async def execute(self, command: StartServicesCommand) -> BulkOperationResult:
        """Execute the start services use case.

        Args:
            command: Command containing service selection criteria

        Returns:
            BulkOperationResult with the results of starting services
        """
        logger.info("Starting services use case", command=command)

        try:
            # Resolve which services to start
            services = await self._resolve_services(command)

            if not services:
                logger.warning("No services found to start")
                return BulkOperationResult(
                    operation="start",
                    total_services=0,
                    successful_services=[],
                    failed_services=[],
                    errors={}
                )

            logger.info("Resolved services to start",
                       count=len(services),
                       service_names=[s.name for s in services])

            # Start each service
            successful_services = []
            failed_services = []
            errors = {}

            for service in services:
                try:
                    result = await self._start_single_service(service, command)

                    if result.success:
                        successful_services.append(service.name)
                        logger.info("Service started successfully",
                                   service_name=service.name,
                                   process_id=result.process_id)
                    else:
                        failed_services.append(service.name)
                        errors[service.name] = result.error or "Unknown error"
                        logger.error("Service failed to start",
                                    service_name=service.name,
                                    error=result.error)

                except Exception as e:
                    failed_services.append(service.name)
                    error_msg = str(e)
                    errors[service.name] = error_msg
                    logger.error("Unexpected error starting service",
                                service_name=service.name,
                                error=error_msg)

            # Create result
            result = BulkOperationResult(
                operation="start",
                total_services=len(services),
                successful_services=successful_services,
                failed_services=failed_services,
                errors=errors
            )

            logger.info("Start services use case completed",
                       total=result.total_services,
                       successful=result.success_count,
                       failed=result.failure_count,
                       success_rate=result.success_rate)

            return result

        except Exception as e:
            logger.error("Error in start services use case", error=str(e))
            raise

    async def _resolve_services(self, command: StartServicesCommand) -> list[Service]:
        """Resolve which services to start based on command.

        Args:
            command: Command containing service selection criteria

        Returns:
            List of services to start
        """
        if command.all_services:
            logger.debug("Resolving all services")
            return await self._service_repository.find_all()

        elif command.tags:
            logger.debug("Resolving services by tags", tags=command.tags)
            return await self._service_repository.find_by_tags(command.tags)

        elif command.service_names:
            logger.debug("Resolving services by names", names=command.service_names)
            services = []

            for name in command.service_names:
                try:
                    service = await self._service_repository.find_by_name(name)
                    if service:
                        services.append(service)
                    else:
                        logger.warning("Service not found", service_name=name)

                except ServiceNotFoundError:
                    logger.warning("Service not found", service_name=name)

            return services

        else:
            logger.debug("No service selection criteria provided")
            return []

    async def _start_single_service(
        self,
        service: Service,
        command: StartServicesCommand
    ) -> ServiceStartResult:
        """Start a single service.

        Args:
            service: Service to start
            command: Command with additional options

        Returns:
            ServiceStartResult with the outcome
        """
        logger.debug("Starting single service", service_name=service.name)

        try:
            # Check if service is already running
            if service.is_healthy() and not command.force_restart:
                logger.info("Service already running", service_name=service.name)
                return ServiceStartResult.success_result(
                    service_name=service.name,
                    process_id=0  # Placeholder for already running
                )

            # Stop service if force restart is requested
            if command.force_restart and service.is_healthy():
                logger.info("Force restarting service", service_name=service.name)
                await self._service_manager.stop_service(service)

            # Start the service
            result = await self._service_manager.start_service(service)

            # Wait for health check if requested
            if command.wait_for_health and result.success:
                health_result = await self._wait_for_health(
                    service,
                    command.health_timeout
                )

                if not health_result:
                    logger.warning("Service started but health check failed",
                                  service_name=service.name)
                    # Don't fail the start operation, just log the warning

            return result

        except Exception as e:
            logger.error("Error starting single service",
                        service_name=service.name,
                        error=str(e))
            return ServiceStartResult.failure_result(
                service_name=service.name,
                error=str(e)
            )

    async def _wait_for_health(self, service: Service, timeout: float) -> bool:
        """Wait for service to become healthy.

        Args:
            service: Service to check
            timeout: Maximum time to wait in seconds

        Returns:
            True if service becomes healthy, False otherwise
        """
        import asyncio

        logger.debug("Waiting for service health",
                    service_name=service.name,
                    timeout=timeout)

        try:
            # Simple implementation - in a real system this would use the health monitor
            await asyncio.sleep(2)  # Give service time to start

            # Check if service is still running
            is_running = await self._service_manager.is_service_running(service)

            if is_running:
                logger.debug("Service health check passed", service_name=service.name)
                return True
            else:
                logger.debug("Service health check failed", service_name=service.name)
                return False

        except TimeoutError:
            logger.warning("Health check timed out",
                          service_name=service.name,
                          timeout=timeout)
            return False
        except Exception as e:
            logger.error("Error during health check",
                        service_name=service.name,
                        error=str(e))
            return False

    async def start_service_by_name(self, service_name: str) -> ServiceStartResult:
        """Convenience method to start a single service by name.

        Args:
            service_name: Name of the service to start

        Returns:
            ServiceStartResult with the outcome
        """
        command = StartServicesCommand(service_names=[service_name])
        result = await self.execute(command)

        if result.success_count > 0:
            return ServiceStartResult.success_result(
                service_name=service_name,
                process_id=0  # Would need to track this properly
            )
        else:
            error = result.errors.get(service_name, "Unknown error")
            return ServiceStartResult.failure_result(
                service_name=service_name,
                error=error
            )

    async def start_all_services(self) -> BulkOperationResult:
        """Convenience method to start all services.

        Returns:
            BulkOperationResult with the outcome
        """
        command = StartServicesCommand(all_services=True)
        return await self.execute(command)

    async def start_services_by_tags(self, tags: list[str]) -> BulkOperationResult:
        """Convenience method to start services by tags.

        Args:
            tags: List of tags to filter services

        Returns:
            BulkOperationResult with the outcome
        """
        command = StartServicesCommand(tags=tags)
        return await self.execute(command)
