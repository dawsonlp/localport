"""Health monitoring scheduler for continuous service health checking."""

import asyncio
from datetime import datetime
from uuid import UUID

import structlog

from ...domain.entities.service import Service, ServiceStatus
from ...domain.enums import ForwardingTechnology
from ...domain.services.cluster_health_provider import ClusterHealthProvider
from ...infrastructure.health_checks.health_check_factory import HealthCheckFactory
from ...infrastructure.shutdown import CooperativeTask, TaskManager
from ..dto.health_dto import HealthCheckResult
from .restart_manager import RestartManager

logger = structlog.get_logger()


class HealthMonitorScheduler:
    """Schedules and coordinates health checks for all services."""

    def __init__(
        self, 
        health_check_factory: HealthCheckFactory, 
        restart_manager: RestartManager,
        cluster_health_provider: ClusterHealthProvider | None = None,
        task_manager: TaskManager | None = None
    ):
        self._health_check_factory = health_check_factory
        self._restart_manager = restart_manager
        self._cluster_health_provider = cluster_health_provider
        self._task_manager = task_manager or TaskManager()
        self._running = False
        
        # Replace direct task management with cooperative tasks
        self._cooperative_tasks: dict[UUID, CooperativeTask] = {}
        self._service_health: dict[UUID, HealthCheckResult] = {}
        self._failure_counts: dict[UUID, int] = {}
        self._last_check_times: dict[UUID, datetime] = {}

    async def start_monitoring(self, services: list[Service]) -> None:
        """Start health monitoring for the given services using cooperative tasks."""
        logger.info("Health monitor scheduler received services for monitoring",
                   total_services=len(services),
                   service_names=[s.name for s in services])

        self._running = True

        # Analyze and log which services will be monitored
        eligible_services = []
        skipped_services = []
        
        for service in services:
            has_health_check = bool(service.health_check_config)
            is_running = service.status == ServiceStatus.RUNNING
            will_monitor = has_health_check and is_running
            
            service_info = {
                'service_name': service.name,
                'service_id': str(service.id),
                'has_health_check': has_health_check,
                'is_running': is_running,
                'status': service.status.value,
                'will_monitor': will_monitor
            }
            
            if has_health_check:
                service_info['health_check_type'] = service.health_check_config.get('type')
                service_info['health_check_interval'] = service.health_check_config.get('interval', 30)
                service_info['failure_threshold'] = service.health_check_config.get('failure_threshold', 3)
            
            if will_monitor:
                eligible_services.append(service)
                logger.info("Health monitor will monitor service", **service_info)
            else:
                skipped_services.append(service_info)
                if not has_health_check:
                    logger.info("Health monitor skipping service - no health check config", **service_info)
                elif not is_running:
                    logger.info("Health monitor skipping service - not running", **service_info)
                else:
                    logger.warning("Health monitor skipping service - unknown reason", **service_info)

        logger.info("Health monitor service analysis complete",
                   total_services=len(services),
                   eligible_services=len(eligible_services),
                   skipped_services=len(skipped_services))

        # Start cooperative monitoring task for each eligible service
        for service in eligible_services:
            await self._start_service_monitoring(service)
        
        logger.info("Health monitoring startup complete",
                   active_monitors=len(self._cooperative_tasks),
                   monitored_services=[s.name for s in eligible_services])

    async def stop_monitoring(self, service_ids: set[UUID] | None = None) -> None:
        """Stop health monitoring for specified services or all services."""
        if service_ids is None:
            # Stop all monitoring
            service_ids = set(self._cooperative_tasks.keys())
            self._running = False
            logger.info("Stopping all health monitoring")
        else:
            logger.info("Stopping health monitoring for services",
                       service_count=len(service_ids))

        # Stop cooperative tasks gracefully
        for service_id in service_ids:
            if service_id in self._cooperative_tasks:
                cooperative_task = self._cooperative_tasks[service_id]
                await cooperative_task.stop()
                del self._cooperative_tasks[service_id]

                # Clean up tracking data
                self._failure_counts.pop(service_id, None)
                self._last_check_times.pop(service_id, None)
                self._service_health.pop(service_id, None)

    async def _start_service_monitoring(self, service: Service) -> None:
        """Start cooperative monitoring for a single service."""
        health_config = service.health_check_config
        check_interval = health_config.get('interval', 30)
        
        # Create cooperative task for this service
        cooperative_task = ServiceHealthMonitorTask(
            service=service,
            health_scheduler=self,
            check_interval=check_interval
        )
        
        # Register with task manager
        task_name = f"health_monitor_{service.name}"
        self._task_manager.register_task(
            task_name,
            cooperative_task._run_loop(),
            group="health_monitoring",
            priority=5,
            resource_tags={"service_id", "health_monitoring"}
        )
        
        # Store cooperative task
        self._cooperative_tasks[service.id] = cooperative_task
        self._failure_counts[service.id] = 0
        
        # Start the cooperative task
        await cooperative_task.start()

        logger.info("Started cooperative health monitoring for service",
                   service_name=service.name,
                   check_interval=check_interval)

    async def add_service(self, service: Service) -> None:
        """Add a new service to health monitoring using cooperative tasks."""
        if (service.health_check_config and
            service.status == ServiceStatus.RUNNING and
            self._running):

            # Stop existing monitoring if any
            if service.id in self._cooperative_tasks:
                await self.stop_monitoring({service.id})

            # Start new cooperative monitoring
            await self._start_service_monitoring(service)

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


    async def _perform_health_check(self, service: Service) -> HealthCheckResult:
        """Perform a health check for a service."""
        try:
            health_config = service.health_check_config
            check_type = health_config.get('type', 'tcp')
            timeout = health_config.get('timeout', 5.0)
            cluster_aware = health_config.get('cluster_aware', False)

            logger.info("Starting health check",
                       service_name=service.name,
                       service_id=str(service.id),
                       check_type=check_type,
                       timeout=timeout,
                       cluster_aware=cluster_aware,
                       local_port=service.local_port)

            # NEW: Check cluster health first if cluster-aware health checking is enabled
            cluster_context = None
            cluster_healthy = None
            
            if (cluster_aware and 
                self._cluster_health_provider and 
                service.technology == ForwardingTechnology.KUBECTL):
                
                # Extract cluster context from kubectl service
                cluster_context = getattr(service.connection_info, 'context', None)
                
                if cluster_context:
                    try:
                        logger.debug("Checking cluster health before service health check",
                                   service_name=service.name,
                                   cluster_context=cluster_context)
                        
                        cluster_healthy = await self._cluster_health_provider.is_cluster_healthy(cluster_context)
                        
                        if not cluster_healthy:
                            # Get cluster health details for better error reporting
                            cluster_health = await self._cluster_health_provider.get_cluster_health(cluster_context)
                            cluster_error = "Unknown cluster issue"
                            
                            if cluster_health and cluster_health.error_message:
                                cluster_error = cluster_health.error_message
                            elif cluster_health and not cluster_health.is_healthy:
                                cluster_error = f"Cluster unhealthy: {cluster_health.status.value}"
                            
                            logger.warning("Skipping service health check due to cluster issues",
                                         service_name=service.name,
                                         cluster_context=cluster_context,
                                         cluster_error=cluster_error)
                            
                            # Return cluster-unhealthy result
                            return HealthCheckResult.cluster_unhealthy_result(
                                service_id=service.id,
                                service_name=service.name,
                                check_type=check_type,
                                cluster_context=cluster_context,
                                cluster_error=cluster_error
                            )
                        else:
                            logger.debug("Cluster is healthy, proceeding with service health check",
                                       service_name=service.name,
                                       cluster_context=cluster_context)
                            
                    except Exception as cluster_error:
                        logger.warning("Failed to check cluster health, proceeding with service check",
                                     service_name=service.name,
                                     cluster_context=cluster_context,
                                     error=str(cluster_error))
                        # Continue with service health check if cluster check fails

            # Get appropriate health checker
            logger.debug("Creating health checker",
                        service_name=service.name,
                        check_type=check_type)
            
            health_checker = self._health_check_factory.create_health_checker(
                check_type,
                health_config.get('config', {})
            )

            # Perform the check
            start_time = datetime.now()

            # Prepare configuration for the health checker
            check_config = health_config.get('config', {}).copy()
            check_config.setdefault('timeout', timeout)
            
            # Add service-specific defaults based on check type
            if check_type == 'tcp':
                check_config.setdefault('host', 'localhost')
                check_config.setdefault('port', service.local_port)
            elif check_type == 'http':
                if 'url' not in check_config:
                    check_config['url'] = f'http://localhost:{service.local_port}/health'
            elif check_type == 'kafka':
                if 'bootstrap_servers' not in check_config:
                    check_config['bootstrap_servers'] = f'localhost:{service.local_port}'
            elif check_type == 'postgres':
                check_config.setdefault('host', 'localhost')
                check_config.setdefault('port', service.local_port)
            else:
                # Default to TCP-like configuration
                check_config.setdefault('host', 'localhost')
                check_config.setdefault('port', service.local_port)

            logger.info("Executing health check",
                       service_name=service.name,
                       check_type=check_type,
                       check_config=check_config)

            # Use polymorphic interface - all health checkers implement check_health()
            health_result = await health_checker.check_health(check_config)
            
            # Update timing information
            check_duration = (datetime.now() - start_time).total_seconds()
            
            # Log health check completion
            logger.info("Health check completed",
                       service_name=service.name,
                       check_type=check_type,
                       is_healthy=health_result.status.value == 'healthy',
                       response_time=check_duration,
                       status=health_result.status.value,
                       error=health_result.error)
            
            # Create standardized result with service information
            final_result = HealthCheckResult(
                service_id=service.id,
                service_name=service.name,
                check_type=check_type,
                is_healthy=health_result.status.value == 'healthy',
                checked_at=start_time,
                response_time=check_duration,
                error=health_result.error,
                cluster_context=cluster_context,
                cluster_healthy=cluster_healthy
            )
            
            # Log final result creation
            logger.info("Health check result created",
                       service_name=service.name,
                       final_is_healthy=final_result.is_healthy,
                       final_error=final_result.error)
            
            return final_result

        except Exception as e:
            logger.exception("Health check failed with exception",
                           service_name=service.name,
                           check_type=health_config.get('type', 'tcp'),
                           error=str(e),
                           error_type=type(e).__name__)

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
        
        # NEW: Check if restart should be skipped due to cluster issues
        if health_result.skip_restart_due_to_cluster:
            logger.info("Skipping service restart due to cluster health issues",
                       service_name=service.name,
                       cluster_context=health_result.cluster_context,
                       cluster_healthy=health_result.cluster_healthy,
                       failure_count=self._failure_counts.get(service.id, 0),
                       reason="cluster_unhealthy")
            
            # Don't increment restart attempts or change service status
            # The service will be retried when cluster health improves
            return

        logger.critical("Service restart triggered by health check failures",
                       service_name=service.name,
                       failure_count=self._failure_counts.get(service.id, 0),
                       last_error=health_result.error,
                       cluster_context=health_result.cluster_context,
                       cluster_healthy=health_result.cluster_healthy)

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


class ServiceHealthMonitorTask(CooperativeTask):
    """Cooperative task for monitoring a single service's health."""

    def __init__(
        self,
        service: Service,
        health_scheduler: HealthMonitorScheduler,
        check_interval: float = 30.0
    ):
        """Initialize the service health monitor task.
        
        Args:
            service: Service to monitor
            health_scheduler: Parent health scheduler
            check_interval: How often to check health (seconds)
        """
        super().__init__(
            name=f"health_monitor_{service.name}",
            check_interval=check_interval
        )
        self._service = service
        self._health_scheduler = health_scheduler
        self._check_interval = check_interval

    async def _execute_iteration(self) -> None:
        """Execute one health check iteration."""
        # Check if service is still being monitored
        if not self._health_scheduler._running:
            logger.debug("Health monitoring stopped, ending task",
                        service_name=self._service.name)
            await self.request_shutdown()
            return

        if self._service.id not in self._health_scheduler._cooperative_tasks:
            logger.debug("Service no longer monitored, ending task",
                        service_name=self._service.name)
            await self.request_shutdown()
            return

        try:
            # Perform health check
            health_result = await self._health_scheduler._perform_health_check(self._service)

            # Update tracking data
            self._health_scheduler._service_health[self._service.id] = health_result
            self._health_scheduler._last_check_times[self._service.id] = datetime.now()

            # Get health config for failure threshold
            health_config = self._service.health_check_config
            failure_threshold = health_config.get('failure_threshold', 3)

            if health_result.is_healthy:
                # Reset failure count on successful check
                if self._health_scheduler._failure_counts.get(self._service.id, 0) > 0:
                    logger.info("Service health recovered",
                               service_name=self._service.name,
                               previous_failures=self._health_scheduler._failure_counts[self._service.id])
                self._health_scheduler._failure_counts[self._service.id] = 0
            else:
                # Increment failure count
                self._health_scheduler._failure_counts[self._service.id] += 1
                failure_count = self._health_scheduler._failure_counts[self._service.id]

                logger.warning("Service health check failed",
                             service_name=self._service.name,
                             failure_count=failure_count,
                             failure_threshold=failure_threshold,
                             error=health_result.error)

                # Check if we've reached the failure threshold
                if failure_count >= failure_threshold:
                    logger.error("Service health failure threshold reached",
                               service_name=self._service.name,
                               failure_count=failure_count,
                               threshold=failure_threshold)

                    # Trigger restart logic
                    await self._health_scheduler._trigger_service_restart(self._service, health_result)

        except Exception as e:
            logger.exception("Error in health check iteration",
                           service_name=self._service.name,
                           error=str(e))

    async def _handle_iteration_error(self, error: Exception) -> bool:
        """Handle errors during health check iterations."""
        logger.warning("Health check iteration error, continuing",
                      service_name=self._service.name,
                      error=str(error))
        # Continue monitoring despite errors
        return True
