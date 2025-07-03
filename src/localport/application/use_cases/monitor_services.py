"""Use case for monitoring port forwarding services."""

from dataclasses import dataclass

import structlog

from ...domain.entities.service import Service, ServiceStatus
from ...domain.repositories.service_repository import ServiceRepository
from ..dto.service_dto import ServiceStatusInfo, ServiceSummary
from ..services.service_manager import ServiceManager

logger = structlog.get_logger()


@dataclass
class MonitorServicesCommand:
    """Command to monitor services."""
    service_names: list[str] | None = None
    tags: list[str] | None = None
    all_services: bool = True
    include_health_checks: bool = True
    include_metrics: bool = False


class MonitorServicesUseCase:
    """Use case for monitoring port forwarding services."""

    def __init__(
        self,
        service_repository: ServiceRepository,
        service_manager: ServiceManager
    ):
        self._service_repository = service_repository
        self._service_manager = service_manager

    async def execute(self, command: MonitorServicesCommand) -> ServiceSummary:
        """Execute the monitor services use case.

        Args:
            command: Command containing monitoring criteria

        Returns:
            ServiceSummary with current status of all services
        """
        logger.info("Monitoring services use case", command=command)

        try:
            # Resolve which services to monitor
            services = await self._resolve_services(command)

            if not services:
                logger.warning("No services found to monitor")
                return ServiceSummary(
                    total_services=0,
                    running_services=0,
                    stopped_services=0,
                    failed_services=0,
                    healthy_services=0,
                    unhealthy_services=0,
                    services=[]
                )

            logger.debug("Resolved services to monitor",
                        count=len(services),
                        service_names=[s.name for s in services])

            # Get status for all services
            service_statuses = await self._service_manager.get_all_service_status(services)

            # Calculate summary statistics
            summary = self._calculate_summary(service_statuses)

            logger.info("Monitor services use case completed",
                       total=summary.total_services,
                       running=summary.running_services,
                       stopped=summary.stopped_services,
                       failed=summary.failed_services,
                       healthy=summary.healthy_services,
                       success_rate=summary.success_rate,
                       health_rate=summary.health_rate)

            return summary

        except Exception as e:
            logger.error("Error in monitor services use case", error=str(e))
            raise

    async def _resolve_services(self, command: MonitorServicesCommand) -> list[Service]:
        """Resolve which services to monitor based on command.

        Args:
            command: Command containing service selection criteria

        Returns:
            List of services to monitor
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
                service = await self._service_repository.find_by_name(name)
                if service:
                    services.append(service)
                else:
                    logger.warning("Service not found", service_name=name)

            return services

        else:
            logger.debug("No service selection criteria provided, defaulting to all")
            return await self._service_repository.find_all()

    def _calculate_summary(self, service_statuses: list[ServiceStatusInfo]) -> ServiceSummary:
        """Calculate summary statistics from service statuses.

        Args:
            service_statuses: List of service status information

        Returns:
            ServiceSummary with calculated statistics
        """
        total_services = len(service_statuses)
        running_services = 0
        stopped_services = 0
        failed_services = 0
        healthy_services = 0
        unhealthy_services = 0

        for status in service_statuses:
            # Count by status
            if status.status == ServiceStatus.RUNNING:
                running_services += 1
            elif status.status == ServiceStatus.STOPPED:
                stopped_services += 1
            elif status.status == ServiceStatus.FAILED:
                failed_services += 1

            # Count by health
            if status.is_healthy:
                healthy_services += 1
            else:
                unhealthy_services += 1

        return ServiceSummary(
            total_services=total_services,
            running_services=running_services,
            stopped_services=stopped_services,
            failed_services=failed_services,
            healthy_services=healthy_services,
            unhealthy_services=unhealthy_services,
            services=service_statuses
        )

    async def get_service_status(self, service_name: str) -> ServiceStatusInfo | None:
        """Get status for a single service by name.

        Args:
            service_name: Name of the service to get status for

        Returns:
            ServiceStatusInfo if service found, None otherwise
        """
        try:
            service = await self._service_repository.find_by_name(service_name)
            if not service:
                logger.warning("Service not found", service_name=service_name)
                return None

            return await self._service_manager.get_service_status(service)

        except Exception as e:
            logger.error("Error getting service status",
                        service_name=service_name,
                        error=str(e))
            return None

    async def get_running_services(self) -> list[ServiceStatusInfo]:
        """Get status for all currently running services.

        Returns:
            List of ServiceStatusInfo for running services
        """
        try:
            services = await self._service_repository.find_all()
            all_statuses = await self._service_manager.get_all_service_status(services)

            # Filter for running services
            running_statuses = [
                status for status in all_statuses
                if status.status == ServiceStatus.RUNNING
            ]

            logger.debug("Found running services", count=len(running_statuses))
            return running_statuses

        except Exception as e:
            logger.error("Error getting running services", error=str(e))
            return []

    async def get_failed_services(self) -> list[ServiceStatusInfo]:
        """Get status for all failed services.

        Returns:
            List of ServiceStatusInfo for failed services
        """
        try:
            services = await self._service_repository.find_all()
            all_statuses = await self._service_manager.get_all_service_status(services)

            # Filter for failed services
            failed_statuses = [
                status for status in all_statuses
                if status.status == ServiceStatus.FAILED
            ]

            logger.debug("Found failed services", count=len(failed_statuses))
            return failed_statuses

        except Exception as e:
            logger.error("Error getting failed services", error=str(e))
            return []

    async def get_unhealthy_services(self) -> list[ServiceStatusInfo]:
        """Get status for all unhealthy services.

        Returns:
            List of ServiceStatusInfo for unhealthy services
        """
        try:
            services = await self._service_repository.find_all()
            all_statuses = await self._service_manager.get_all_service_status(services)

            # Filter for unhealthy services
            unhealthy_statuses = [
                status for status in all_statuses
                if not status.is_healthy
            ]

            logger.debug("Found unhealthy services", count=len(unhealthy_statuses))
            return unhealthy_statuses

        except Exception as e:
            logger.error("Error getting unhealthy services", error=str(e))
            return []

    async def cleanup_dead_processes(self) -> int:
        """Clean up dead port forward processes.

        Returns:
            Number of dead processes cleaned up
        """
        try:
            count = await self._service_manager.cleanup_dead_processes()
            logger.info("Cleaned up dead processes", count=count)
            return count

        except Exception as e:
            logger.error("Error cleaning up dead processes", error=str(e))
            return 0

    async def get_services_by_tag(self, tag: str) -> list[ServiceStatusInfo]:
        """Get status for all services with a specific tag.

        Args:
            tag: Tag to filter services by

        Returns:
            List of ServiceStatusInfo for services with the tag
        """
        try:
            services = await self._service_repository.find_by_tags([tag])
            statuses = await self._service_manager.get_all_service_status(services)

            logger.debug("Found services by tag", tag=tag, count=len(statuses))
            return statuses

        except Exception as e:
            logger.error("Error getting services by tag", tag=tag, error=str(e))
            return []

    async def get_port_usage_summary(self) -> dict:
        """Get summary of port usage across all services.

        Returns:
            Dictionary with port usage information
        """
        try:
            services = await self._service_repository.find_all()
            all_statuses = await self._service_manager.get_all_service_status(services)

            port_usage = {
                "total_ports": len(all_statuses),
                "active_ports": [],
                "inactive_ports": [],
                "port_conflicts": [],
                "port_ranges": {
                    "privileged": 0,  # 1-1023
                    "registered": 0,  # 1024-49151
                    "ephemeral": 0    # 49152-65535
                }
            }

            used_ports = set()

            for status in all_statuses:
                port = status.local_port

                # Check for conflicts
                if port in used_ports:
                    port_usage["port_conflicts"].append(port)
                else:
                    used_ports.add(port)

                # Categorize by status
                if status.status == ServiceStatus.RUNNING:
                    port_usage["active_ports"].append(port)
                else:
                    port_usage["inactive_ports"].append(port)

                # Categorize by port range
                if 1 <= port <= 1023:
                    port_usage["port_ranges"]["privileged"] += 1
                elif 1024 <= port <= 49151:
                    port_usage["port_ranges"]["registered"] += 1
                elif 49152 <= port <= 65535:
                    port_usage["port_ranges"]["ephemeral"] += 1

            logger.debug("Generated port usage summary",
                        total_ports=port_usage["total_ports"],
                        active_ports=len(port_usage["active_ports"]),
                        conflicts=len(port_usage["port_conflicts"]))

            return port_usage

        except Exception as e:
            logger.error("Error getting port usage summary", error=str(e))
            return {}

    async def get_quick_status(self) -> dict:
        """Get a quick status overview.

        Returns:
            Dictionary with quick status information
        """
        try:
            summary = await self.execute(MonitorServicesCommand())

            return {
                "total_services": summary.total_services,
                "running": summary.running_services,
                "stopped": summary.stopped_services,
                "failed": summary.failed_services,
                "healthy": summary.healthy_services,
                "success_rate": round(summary.success_rate, 1),
                "health_rate": round(summary.health_rate, 1),
                "active_forwards": self._service_manager.get_active_forwards_count()
            }

        except Exception as e:
            logger.error("Error getting quick status", error=str(e))
            return {
                "error": str(e),
                "total_services": 0,
                "running": 0,
                "stopped": 0,
                "failed": 0,
                "healthy": 0,
                "success_rate": 0.0,
                "health_rate": 0.0,
                "active_forwards": 0
            }
