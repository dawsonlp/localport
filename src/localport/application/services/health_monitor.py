"""Health monitoring service with automatic restart logic."""

import asyncio
from datetime import datetime
from uuid import UUID

import structlog

from ...domain.entities.service import Service, ServiceStatus
from ...domain.repositories.service_repository import ServiceRepository
from ...infrastructure.health_checks.health_check_factory import HealthCheckFactory
from ..dto.service_dto import HealthCheckInfo, ServiceMonitorResult
from .service_manager import ServiceManager

logger = structlog.get_logger()


class HealthMonitor:
    """Service for monitoring health and managing automatic restarts."""

    def __init__(
        self,
        service_repository: ServiceRepository,
        service_manager: ServiceManager,
        health_check_factory: HealthCheckFactory
    ):
        """Initialize the health monitor.

        Args:
            service_repository: Repository for service persistence
            service_manager: Service manager for lifecycle operations
            health_check_factory: Factory for creating health checks
        """
        self._service_repository = service_repository
        self._service_manager = service_manager
        self._health_check_factory = health_check_factory

        # Health monitoring state
        self._health_states: dict[UUID, HealthCheckInfo] = {}
        self._failure_counts: dict[UUID, int] = {}
        self._last_restart_attempts: dict[UUID, datetime] = {}
        self._monitoring_tasks: dict[UUID, asyncio.Task] = {}
        self._is_monitoring = False
        self._monitor_task: asyncio.Task | None = None

        # Configuration
        self._default_check_interval = 30  # seconds
        self._default_failure_threshold = 3
        self._restart_cooldown = 60  # seconds between restart attempts
        self._max_restart_attempts = 5

    async def start_monitoring(self, services: list[Service] | None = None) -> None:
        """Start health monitoring for services.

        Args:
            services: Optional list of services to monitor. If None, monitors all services.
        """
        if self._is_monitoring:
            logger.warning("Health monitoring is already running")
            return

        logger.info("Starting health monitoring")

        # Get services to monitor
        if services is None:
            services = await self._service_repository.find_all()

        # Initialize health states
        for service in services:
            if service.health_check_config:
                self._initialize_health_state(service)

        # Start monitoring
        self._is_monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())

        logger.info("Health monitoring started",
                   monitored_services=len([s for s in services if s.health_check_config]))

    async def stop_monitoring(self) -> None:
        """Stop health monitoring."""
        if not self._is_monitoring:
            return

        logger.info("Stopping health monitoring")

        self._is_monitoring = False

        # Cancel monitoring task
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Cancel individual monitoring tasks
        for task in self._monitoring_tasks.values():
            task.cancel()

        if self._monitoring_tasks:
            await asyncio.gather(*self._monitoring_tasks.values(), return_exceptions=True)

        self._monitoring_tasks.clear()

        logger.info("Health monitoring stopped")

    async def check_service_health(self, service: Service) -> ServiceMonitorResult:
        """Check health of a single service.

        Args:
            service: Service to check

        Returns:
            Health check result
        """
        logger.debug("Checking service health", service_name=service.name)

        now = datetime.now()
        failure_count = self._failure_counts.get(service.id, 0)
        restart_attempted = False
        restart_success = False

        try:
            # Check if service has health check configuration
            if not service.health_check_config:
                logger.debug("No health check configured", service_name=service.name)
                return ServiceMonitorResult(
                    service_name=service.name,
                    is_healthy=service.status == ServiceStatus.RUNNING,
                    last_check=now,
                    failure_count=failure_count
                )

            # Get health check strategy
            health_check = self._health_check_factory.create_health_check(
                service.health_check_config['type'],
                service.health_check_config.get('config', {})
            )

            # Perform health check
            is_healthy = await health_check.check(
                host='localhost',
                port=service.local_port,
                timeout=service.health_check_config.get('timeout', 5.0)
            )

            # Update health state
            health_info = self._health_states.get(service.id)
            if health_info:
                health_info.last_check = now
                if is_healthy:
                    health_info.last_success = now
                    health_info.consecutive_failures = 0
                    health_info.status = "healthy"
                    # Reset failure count on success
                    self._failure_counts[service.id] = 0
                    failure_count = 0
                else:
                    health_info.consecutive_failures += 1
                    health_info.status = "unhealthy"
                    # Increment failure count
                    failure_count = health_info.consecutive_failures
                    self._failure_counts[service.id] = failure_count

            # Check if restart is needed
            failure_threshold = service.health_check_config.get('failure_threshold', self._default_failure_threshold)

            if not is_healthy and failure_count >= failure_threshold:
                restart_attempted, restart_success = await self._attempt_restart(service)

            logger.debug("Health check completed",
                        service_name=service.name,
                        is_healthy=is_healthy,
                        failure_count=failure_count,
                        restart_attempted=restart_attempted)

            return ServiceMonitorResult(
                service_name=service.name,
                is_healthy=is_healthy,
                last_check=now,
                failure_count=failure_count,
                restart_attempted=restart_attempted,
                restart_success=restart_success
            )

        except Exception as e:
            error_msg = str(e)
            logger.error("Health check failed",
                        service_name=service.name,
                        error=error_msg)

            # Increment failure count on error
            failure_count += 1
            self._failure_counts[service.id] = failure_count

            return ServiceMonitorResult(
                service_name=service.name,
                is_healthy=False,
                last_check=now,
                failure_count=failure_count,
                error=error_msg
            )

    async def get_health_status(self, service_id: UUID) -> HealthCheckInfo | None:
        """Get current health status for a service.

        Args:
            service_id: Service ID

        Returns:
            Health check information or None if not monitored
        """
        return self._health_states.get(service_id)

    async def get_all_health_status(self) -> dict[UUID, HealthCheckInfo]:
        """Get health status for all monitored services.

        Returns:
            Dictionary mapping service IDs to health check information
        """
        return self._health_states.copy()

    def _initialize_health_state(self, service: Service) -> None:
        """Initialize health state for a service.

        Args:
            service: Service to initialize
        """
        if not service.health_check_config:
            return

        health_info = HealthCheckInfo(
            service_name=service.name,
            check_type=service.health_check_config['type'],
            status="unknown",
            failure_threshold=service.health_check_config.get('failure_threshold', self._default_failure_threshold)
        )

        self._health_states[service.id] = health_info
        self._failure_counts[service.id] = 0

        logger.debug("Initialized health state",
                    service_name=service.name,
                    check_type=health_info.check_type)

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Health monitoring loop started")

        try:
            while self._is_monitoring:
                # Get all services that need monitoring
                services = await self._service_repository.find_all()
                monitored_services = [s for s in services if s.health_check_config and s.status == ServiceStatus.RUNNING]

                # Check health for each service
                if monitored_services:
                    tasks = []
                    for service in monitored_services:
                        task = asyncio.create_task(self._monitor_service(service))
                        tasks.append(task)
                        self._monitoring_tasks[service.id] = task

                    # Wait for all health checks to complete
                    await asyncio.gather(*tasks, return_exceptions=True)

                    # Clean up completed tasks
                    for service in monitored_services:
                        self._monitoring_tasks.pop(service.id, None)

                # Wait before next monitoring cycle
                await asyncio.sleep(self._default_check_interval)

        except asyncio.CancelledError:
            logger.info("Health monitoring loop cancelled")
            raise
        except Exception as e:
            logger.error("Health monitoring loop error", error=str(e))
            raise

    async def _monitor_service(self, service: Service) -> None:
        """Monitor a single service.

        Args:
            service: Service to monitor
        """
        try:
            result = await self.check_service_health(service)

            # Update service repository if needed
            if result.restart_attempted:
                await self._service_repository.save(service)

        except Exception as e:
            logger.error("Service monitoring error",
                        service_name=service.name,
                        error=str(e))

    async def _attempt_restart(self, service: Service) -> tuple[bool, bool]:
        """Attempt to restart a failed service.

        Args:
            service: Service to restart

        Returns:
            Tuple of (restart_attempted, restart_success)
        """
        now = datetime.now()

        # Check restart cooldown
        last_restart = self._last_restart_attempts.get(service.id)
        if last_restart and (now - last_restart).total_seconds() < self._restart_cooldown:
            logger.debug("Restart cooldown active",
                        service_name=service.name,
                        cooldown_remaining=(self._restart_cooldown - (now - last_restart).total_seconds()))
            return False, False

        # Check max restart attempts
        restart_count = getattr(service, 'restart_count', 0)
        if restart_count >= self._max_restart_attempts:
            logger.warning("Max restart attempts reached",
                          service_name=service.name,
                          restart_count=restart_count)
            return False, False

        logger.info("Attempting service restart",
                   service_name=service.name,
                   restart_count=restart_count)

        try:
            # Record restart attempt
            self._last_restart_attempts[service.id] = now

            # Stop the service first
            await self._service_manager.stop_service(service)

            # Wait a moment before restarting
            await asyncio.sleep(2)

            # Start the service
            result = await self._service_manager.start_service(service)

            if result.success:
                # Increment restart count
                service.restart_count = restart_count + 1

                # Reset failure count on successful restart
                self._failure_counts[service.id] = 0

                logger.info("Service restart successful",
                           service_name=service.name,
                           new_process_id=result.process_id)

                return True, True
            else:
                logger.error("Service restart failed",
                           service_name=service.name,
                           error=result.error)
                return True, False

        except Exception as e:
            logger.error("Service restart error",
                        service_name=service.name,
                        error=str(e))
            return True, False

    async def reset_failure_count(self, service_id: UUID) -> None:
        """Reset failure count for a service.

        Args:
            service_id: Service ID
        """
        self._failure_counts[service_id] = 0

        health_info = self._health_states.get(service_id)
        if health_info:
            health_info.consecutive_failures = 0
            health_info.status = "healthy"

        logger.info("Reset failure count", service_id=str(service_id))

    async def set_monitoring_interval(self, interval: int) -> None:
        """Set the monitoring interval.

        Args:
            interval: Interval in seconds
        """
        if interval < 5:
            raise ValueError("Monitoring interval must be at least 5 seconds")

        self._default_check_interval = interval
        logger.info("Updated monitoring interval", interval=interval)

    async def set_failure_threshold(self, service_id: UUID, threshold: int) -> None:
        """Set failure threshold for a specific service.

        Args:
            service_id: Service ID
            threshold: Failure threshold
        """
        if threshold < 1:
            raise ValueError("Failure threshold must be at least 1")

        health_info = self._health_states.get(service_id)
        if health_info:
            health_info.failure_threshold = threshold
            logger.info("Updated failure threshold",
                       service_id=str(service_id),
                       threshold=threshold)

    @property
    def is_monitoring(self) -> bool:
        """Check if monitoring is active."""
        return self._is_monitoring

    @property
    def monitored_service_count(self) -> int:
        """Get count of monitored services."""
        return len(self._health_states)

    async def get_monitoring_statistics(self) -> dict[str, any]:
        """Get monitoring statistics.

        Returns:
            Dictionary with monitoring statistics
        """
        healthy_count = sum(1 for info in self._health_states.values() if info.status == "healthy")
        unhealthy_count = len(self._health_states) - healthy_count

        total_failures = sum(self._failure_counts.values())
        total_restarts = sum(getattr(service, 'restart_count', 0)
                           for service in await self._service_repository.find_all())

        return {
            "is_monitoring": self._is_monitoring,
            "monitored_services": len(self._health_states),
            "healthy_services": healthy_count,
            "unhealthy_services": unhealthy_count,
            "total_failures": total_failures,
            "total_restarts": total_restarts,
            "monitoring_interval": self._default_check_interval,
            "restart_cooldown": self._restart_cooldown,
            "max_restart_attempts": self._max_restart_attempts
        }
