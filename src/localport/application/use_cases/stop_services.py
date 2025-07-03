"""Use case for stopping port forwarding services."""

from dataclasses import dataclass

import structlog

from ...domain.entities.service import Service
from ...domain.repositories.service_repository import (
    ServiceNotFoundError,
    ServiceRepository,
)
from ..dto.service_dto import BulkOperationResult, ServiceStopResult
from ..services.service_manager import ServiceManager

logger = structlog.get_logger()


@dataclass
class StopServicesCommand:
    """Command to stop services."""
    service_names: list[str] | None = None
    tags: list[str] | None = None
    all_services: bool = False
    force_stop: bool = False
    graceful_timeout: float = 10.0


class StopServicesUseCase:
    """Use case for stopping port forwarding services."""

    def __init__(
        self,
        service_repository: ServiceRepository,
        service_manager: ServiceManager
    ):
        self._service_repository = service_repository
        self._service_manager = service_manager

    async def execute(self, command: StopServicesCommand) -> BulkOperationResult:
        """Execute the stop services use case.

        Args:
            command: Command containing service selection criteria

        Returns:
            BulkOperationResult with the results of stopping services
        """
        logger.info("Stopping services use case", command=command)

        try:
            # Resolve which services to stop
            services = await self._resolve_services(command)

            if not services:
                logger.warning("No services found to stop")
                return BulkOperationResult(
                    operation="stop",
                    total_services=0,
                    successful_services=[],
                    failed_services=[],
                    errors={}
                )

            logger.info("Resolved services to stop",
                       count=len(services),
                       service_names=[s.name for s in services])

            # Stop each service
            successful_services = []
            failed_services = []
            errors = {}

            for service in services:
                try:
                    result = await self._stop_single_service(service, command)

                    if result.success:
                        successful_services.append(service.name)
                        logger.info("Service stopped successfully",
                                   service_name=service.name)
                    else:
                        failed_services.append(service.name)
                        errors[service.name] = result.error or "Unknown error"
                        logger.error("Service failed to stop",
                                    service_name=service.name,
                                    error=result.error)

                except Exception as e:
                    failed_services.append(service.name)
                    error_msg = str(e)
                    errors[service.name] = error_msg
                    logger.error("Unexpected error stopping service",
                                service_name=service.name,
                                error=error_msg)

            # Create result
            result = BulkOperationResult(
                operation="stop",
                total_services=len(services),
                successful_services=successful_services,
                failed_services=failed_services,
                errors=errors
            )

            logger.info("Stop services use case completed",
                       total=result.total_services,
                       successful=result.success_count,
                       failed=result.failure_count,
                       success_rate=result.success_rate)

            return result

        except Exception as e:
            logger.error("Error in stop services use case", error=str(e))
            raise

    async def _resolve_services(self, command: StopServicesCommand) -> list[Service]:
        """Resolve which services to stop based on command.

        Args:
            command: Command containing service selection criteria

        Returns:
            List of services to stop
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

    async def _stop_single_service(
        self,
        service: Service,
        command: StopServicesCommand
    ) -> ServiceStopResult:
        """Stop a single service.

        Args:
            service: Service to stop
            command: Command with additional options

        Returns:
            ServiceStopResult with the outcome
        """
        logger.debug("Stopping single service", service_name=service.name)

        try:
            # Check if service is already stopped
            if not await self._service_manager.is_service_running(service):
                logger.info("Service already stopped", service_name=service.name)
                return ServiceStopResult.success_result(service.name)

            # Stop the service
            result = await self._service_manager.stop_service(service)

            return result

        except Exception as e:
            logger.error("Error stopping single service",
                        service_name=service.name,
                        error=str(e))
            return ServiceStopResult.failure_result(
                service_name=service.name,
                error=str(e)
            )

    async def stop_service_by_name(self, service_name: str) -> ServiceStopResult:
        """Convenience method to stop a single service by name.

        Args:
            service_name: Name of the service to stop

        Returns:
            ServiceStopResult with the outcome
        """
        command = StopServicesCommand(service_names=[service_name])
        result = await self.execute(command)

        if result.success_count > 0:
            return ServiceStopResult.success_result(service_name)
        else:
            error = result.errors.get(service_name, "Unknown error")
            return ServiceStopResult.failure_result(service_name, error)

    async def stop_all_services(self) -> BulkOperationResult:
        """Convenience method to stop all services.

        Returns:
            BulkOperationResult with the outcome
        """
        command = StopServicesCommand(all_services=True)
        return await self.execute(command)

    async def stop_services_by_tags(self, tags: list[str]) -> BulkOperationResult:
        """Convenience method to stop services by tags.

        Args:
            tags: List of tags to filter services

        Returns:
            BulkOperationResult with the outcome
        """
        command = StopServicesCommand(tags=tags)
        return await self.execute(command)

    async def emergency_stop_all(self) -> BulkOperationResult:
        """Emergency stop all services with force.

        Returns:
            BulkOperationResult with the outcome
        """
        command = StopServicesCommand(
            all_services=True,
            force_stop=True,
            graceful_timeout=5.0
        )
        return await self.execute(command)
