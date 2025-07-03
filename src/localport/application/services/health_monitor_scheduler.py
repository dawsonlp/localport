"""Health monitoring scheduler for continuous service health checking."""

import asyncio
from datetime import datetime
from uuid import UUID

import structlog

from ...domain.entities.service import Service, ServiceStatus
from ...infrastructure.health_checks.health_check_factory import HealthCheckFactory
from ..dto.health_dto import HealthCheckResult
from .restart_manager import RestartManager

logger = structlog.get_logger()


class HealthMonitorScheduler:
    """Schedules and coordinates health checks for all services."""

    def __init__(self, health_check_factory: HealthCheckFactory, restart_manager: RestartManager):
        self._health_check_factory = health_check_factory
        self._restart_manager = restart_manager
        self._running = False
        self._tasks: dict[UUID, asyncio.Task] = {}
        self._service_health: dict[UUID, HealthCheckResult] = {}
        self._failure_counts: dict[UUID, int] = {}
        self._last_check_times: dict[UUID, datetime] = {}

    async def start_monitoring(self, services: list[Service]) -> None:
        """Start health monitoring for the given services."""
        logger.info("Starting health monitoring", service_count=len(services))

        self._running = True

        # Start monitoring task for each service
        for service in services:
            if service.health_check_config and service.status == ServiceStatus.RUNNING:
                task = asyncio.create_task(
                    self._monitor_service_health(service),
                    name=f"health_monitor_{service.name}"
                )
                self._tasks[service.id] = task
                self._failure_counts[service.id] = 0

                logger.info("Started health monitoring for service",
                           service_name=service.name,
                           check_interval=service.health_check_config.get('interval', 30))

    async def stop_monitoring(self, service_ids: set[UUID] | None = None) -> None:
        """Stop health monitoring for specified services or all services."""
        if service_ids is None:
            # Stop all monitoring
            service_ids = set(self._tasks.keys())
            self._running = False
            logger.info("Stopping all health monitoring")
        else:
            logger.info("Stopping health monitoring for services",
                       service_count=len(service_ids))

        # Cancel monitoring tasks
        for service_id in service_ids:
            if service_id in self._tasks:
                task = self._tasks[service_id]
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                del self._tasks[service_id]

                # Clean up tracking data
                self._failure_counts.pop(service_id, None)
                self._last_check_times.pop(service_id, None)
                self._service_health.pop(service_id, None)

    async def add_service(self, service: Service) -> None:
        """Add a new service to health monitoring."""
        if (service.health_check_config and
            service.status == ServiceStatus.RUNNING and
            self._running):

            # Stop existing monitoring if any
            if service.id in self._tasks:
                await self.stop_monitoring({service.id})

            # Start new monitoring
            task = asyncio.create_task(
                self._monitor_service_health(service),
                name=f"health_monitor_{service.name}"
            )
            self._tasks[service.id] = task
            self._failure_counts[service.id] = 0

            logger.info("Added service to health monitoring",
                       service_name=service.name)

    async def remove_service(self, service_id: UUID) -> None:
        """Remove a service from health monitoring."""
        await self.stop_monitoring({service_id})
        logger.info("Removed service from health monitoring", service_id=str(service_id))

    def get_health_status(self, service_id: UUID) -> HealthCheckResult | None:
        """Get the latest health check result for a service."""
        return self._service_health.get(service_id)

    def get_all_health_status(self) -> dict[UUID, HealthCheckResult]:
        """Get health status for all monitored services."""
        return self._service_health.copy()

    def get_failure_count(self, service_id: UUID) -> int:
        """Get the current failure count for a service."""
        return self._failure_counts.get(service_id, 0)

    async def _monitor_service_health(self, service: Service) -> None:
        """Monitor health for a single service."""
        logger.info("Starting health monitoring loop", service_name=service.name)

        health_config = service.health_check_config
        check_interval = health_config.get('interval', 30)
        failure_threshold = health_config.get('failure_threshold', 3)

        while self._running and service.id in self._tasks:
            try:
                # Perform health check
                health_result = await self._perform_health_check(service)

                # Update tracking data
                self._service_health[service.id] = health_result
                self._last_check_times[service.id] = datetime.now()

                if health_result.is_healthy:
                    # Reset failure count on successful check
                    if self._failure_counts.get(service.id, 0) > 0:
                        logger.info("Service health recovered",
                                   service_name=service.name,
                                   previous_failures=self._failure_counts[service.id])
                    self._failure_counts[service.id] = 0
                else:
                    # Increment failure count
                    self._failure_counts[service.id] += 1
                    failure_count = self._failure_counts[service.id]

                    logger.warning("Service health check failed",
                                 service_name=service.name,
                                 failure_count=failure_count,
                                 failure_threshold=failure_threshold,
                                 error=health_result.error)

                    # Check if we've reached the failure threshold
                    if failure_count >= failure_threshold:
                        logger.error("Service health failure threshold reached",
                                   service_name=service.name,
                                   failure_count=failure_count,
                                   threshold=failure_threshold)

                        # Trigger restart logic (will be implemented in restart manager)
                        await self._trigger_service_restart(service, health_result)

                # Wait for next check interval
                await asyncio.sleep(check_interval)

            except asyncio.CancelledError:
                logger.info("Health monitoring cancelled", service_name=service.name)
                break
            except Exception as e:
                logger.exception("Error in health monitoring loop",
                               service_name=service.name,
                               error=str(e))
                # Continue monitoring despite errors
                await asyncio.sleep(check_interval)

    async def _perform_health_check(self, service: Service) -> HealthCheckResult:
        """Perform a health check for a service."""
        try:
            health_config = service.health_check_config
            check_type = health_config.get('type', 'tcp')
            timeout = health_config.get('timeout', 5.0)

            # Get appropriate health checker
            health_checker = self._health_check_factory.create_health_checker(
                check_type,
                health_config.get('config', {})
            )

            # Perform the check
            start_time = datetime.now()

            if check_type == 'tcp':
                is_healthy = await health_checker.check(
                    host='localhost',
                    port=service.local_port,
                    timeout=timeout
                )
            elif check_type == 'http':
                url = health_config.get('config', {}).get('url', f'http://localhost:{service.local_port}/health')
                is_healthy = await health_checker.check(url=url, timeout=timeout)
            elif check_type == 'kafka':
                bootstrap_servers = health_config.get('config', {}).get('bootstrap_servers', f'localhost:{service.local_port}')
                is_healthy = await health_checker.check(bootstrap_servers=bootstrap_servers, timeout=timeout)
            elif check_type == 'postgres':
                connection_config = health_config.get('config', {})
                connection_config.setdefault('host', 'localhost')
                connection_config.setdefault('port', service.local_port)
                is_healthy = await health_checker.check(**connection_config, timeout=timeout)
            else:
                # Default to TCP check
                is_healthy = await health_checker.check(
                    host='localhost',
                    port=service.local_port,
                    timeout=timeout
                )

            check_duration = (datetime.now() - start_time).total_seconds()

            return HealthCheckResult(
                service_id=service.id,
                service_name=service.name,
                check_type=check_type,
                is_healthy=is_healthy,
                checked_at=start_time,
                response_time=check_duration,
                error=None if is_healthy else f"{check_type.upper()} health check failed"
            )

        except Exception as e:
            logger.exception("Health check failed with exception",
                           service_name=service.name,
                           error=str(e))

            return HealthCheckResult(
                service_id=service.id,
                service_name=service.name,
                check_type=health_config.get('type', 'tcp'),
                is_healthy=False,
                checked_at=datetime.now(),
                response_time=0.0,
                error=f"Health check exception: {str(e)}"
            )

    async def _trigger_service_restart(self, service: Service, health_result: HealthCheckResult) -> None:
        """Trigger service restart due to health check failures."""
        logger.critical("Service restart triggered by health check failures",
                       service_name=service.name,
                       failure_count=self._failure_counts.get(service.id, 0),
                       last_error=health_result.error)

        # Use restart manager to schedule restart with exponential backoff
        restart_scheduled = await self._restart_manager.schedule_restart(
            service=service,
            trigger_reason=f"health_check_failure: {health_result.error}",
            restart_policy=service.restart_policy
        )

        if restart_scheduled:
            logger.info("Service restart scheduled",
                       service_name=service.name,
                       restart_attempts=self._restart_manager.get_restart_count(service.id))
        else:
            logger.error("Failed to schedule service restart",
                        service_name=service.name,
                        reason="max_attempts_reached_or_disabled")

            # Update service status to failed if restart can't be scheduled
            service.status = ServiceStatus.FAILED
