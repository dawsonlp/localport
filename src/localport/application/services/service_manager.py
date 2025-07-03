"""Service manager for managing the lifecycle of port forwarding services."""

import asyncio
from datetime import datetime
from uuid import UUID

import structlog

from ...domain.entities.port_forward import PortForward
from ...domain.entities.service import ForwardingTechnology, Service, ServiceStatus
from ...infrastructure.adapters.kubectl_adapter import KubectlAdapter
from ...infrastructure.adapters.ssh_adapter import SSHAdapter
from ...infrastructure.health_checks.tcp_health_check import TCPHealthCheck
from ..dto.service_dto import ServiceStartResult, ServiceStatusInfo, ServiceStopResult

logger = structlog.get_logger()


class ServiceManager:
    """Manages the lifecycle of port forwarding services."""

    def __init__(self):
        """Initialize the service manager."""
        self._active_forwards: dict[UUID, PortForward] = {}
        self._adapters = {
            ForwardingTechnology.KUBECTL: KubectlAdapter(),
            ForwardingTechnology.SSH: SSHAdapter(),
        }
        self._tcp_health_check = TCPHealthCheck()

    async def start_service(self, service: Service) -> ServiceStartResult:
        """Start a port forwarding service.
        
        Args:
            service: The service to start
            
        Returns:
            ServiceStartResult with the outcome
        """
        logger.info("Starting service", service_name=service.name)

        try:
            # Check if service is already running
            if service.id in self._active_forwards:
                existing_forward = self._active_forwards[service.id]
                if existing_forward.is_process_alive():
                    logger.info("Service already running",
                               service_name=service.name,
                               process_id=existing_forward.process_id)
                    return ServiceStartResult.success_result(
                        service_name=service.name,
                        process_id=existing_forward.process_id,
                        started_at=existing_forward.started_at
                    )
                else:
                    # Clean up dead process
                    logger.info("Cleaning up dead process",
                               service_name=service.name,
                               process_id=existing_forward.process_id)
                    del self._active_forwards[service.id]

            # Check if local port is available
            if not await self._is_port_available(service.local_port):
                error_msg = f"Port {service.local_port} is already in use"
                logger.error("Port unavailable",
                           service_name=service.name,
                           port=service.local_port)
                service.update_status(ServiceStatus.FAILED)
                return ServiceStartResult.failure_result(service.name, error_msg)

            # Update service status
            service.update_status(ServiceStatus.STARTING)

            # Get appropriate adapter
            adapter = self._adapters[service.technology]

            # Start the port forward
            process_id = await adapter.start_port_forward(
                service.local_port,
                service.remote_port,
                service.connection_info
            )

            # Create port forward entity
            port_forward = PortForward(
                service_id=service.id,
                process_id=process_id,
                local_port=service.local_port,
                remote_port=service.remote_port,
                started_at=datetime.now()
            )

            # Store active forward
            self._active_forwards[service.id] = port_forward

            # Update service status
            service.update_status(ServiceStatus.RUNNING)

            logger.info("Service started successfully",
                       service_name=service.name,
                       process_id=process_id,
                       local_port=service.local_port,
                       remote_port=service.remote_port)

            return ServiceStartResult.success_result(
                service_name=service.name,
                process_id=process_id,
                started_at=port_forward.started_at
            )

        except Exception as e:
            service.update_status(ServiceStatus.FAILED)
            error_msg = str(e)
            logger.error("Failed to start service",
                        service_name=service.name,
                        error=error_msg)
            return ServiceStartResult.failure_result(service.name, error_msg)

    async def stop_service(self, service: Service) -> ServiceStopResult:
        """Stop a port forwarding service.
        
        Args:
            service: The service to stop
            
        Returns:
            ServiceStopResult with the outcome
        """
        logger.info("Stopping service", service_name=service.name)

        try:
            port_forward = self._active_forwards.get(service.id)
            if not port_forward:
                logger.warning("No active forward found", service_name=service.name)
                service.update_status(ServiceStatus.STOPPED)
                return ServiceStopResult.success_result(service.name)

            # Get appropriate adapter
            adapter = self._adapters[service.technology]

            # Stop the port forward
            if port_forward.process_id:
                await adapter.stop_port_forward(port_forward.process_id)

            # Remove from active forwards
            del self._active_forwards[service.id]

            # Update service status
            service.update_status(ServiceStatus.STOPPED)

            logger.info("Service stopped successfully",
                       service_name=service.name,
                       process_id=port_forward.process_id)

            return ServiceStopResult.success_result(service.name)

        except Exception as e:
            error_msg = str(e)
            logger.error("Failed to stop service",
                        service_name=service.name,
                        error=error_msg)
            return ServiceStopResult.failure_result(service.name, error_msg)

    async def restart_service(self, service: Service) -> ServiceStartResult:
        """Restart a port forwarding service.
        
        Args:
            service: The service to restart
            
        Returns:
            ServiceStartResult with the outcome
        """
        logger.info("Restarting service", service_name=service.name)

        try:
            # Stop the service first
            stop_result = await self.stop_service(service)
            if not stop_result.success:
                logger.error("Failed to stop service for restart",
                           service_name=service.name,
                           error=stop_result.error)
                return ServiceStartResult.failure_result(
                    service.name,
                    f"Failed to stop for restart: {stop_result.error}"
                )

            # Wait a moment before restarting
            await asyncio.sleep(1)

            # Start the service
            start_result = await self.start_service(service)

            # Update restart count if we have an active forward
            if start_result.success and service.id in self._active_forwards:
                self._active_forwards[service.id].increment_restart_count()

            return start_result

        except Exception as e:
            error_msg = str(e)
            logger.error("Failed to restart service",
                        service_name=service.name,
                        error=error_msg)
            return ServiceStartResult.failure_result(service.name, error_msg)

    async def is_service_running(self, service: Service) -> bool:
        """Check if a service is currently running.
        
        Args:
            service: The service to check
            
        Returns:
            True if service is running, False otherwise
        """
        port_forward = self._active_forwards.get(service.id)
        if not port_forward:
            return False

        return port_forward.is_process_alive()

    async def get_service_status(self, service: Service) -> ServiceStatusInfo:
        """Get detailed status information for a service.
        
        Args:
            service: The service to get status for
            
        Returns:
            ServiceStatusInfo with detailed status
        """
        port_forward = self._active_forwards.get(service.id)

        # Basic status info
        status_info = ServiceStatusInfo(
            id=service.id,
            name=service.name,
            technology=service.technology,
            local_port=service.local_port,
            remote_port=service.remote_port,
            status=service.status,
            tags=service.tags.copy(),
            description=service.description
        )

        # Add port forward specific info if available
        if port_forward:
            status_info.process_id = port_forward.process_id
            status_info.started_at = port_forward.started_at
            status_info.last_health_check = port_forward.last_health_check
            status_info.restart_count = port_forward.restart_count
            status_info.uptime_seconds = port_forward.get_uptime_seconds()

            # Check if process is actually alive
            if port_forward.is_process_alive():
                status_info.is_healthy = True
            else:
                # Process is dead but we still have a record
                status_info.is_healthy = False
                service.update_status(ServiceStatus.FAILED)
                status_info.status = ServiceStatus.FAILED

        return status_info

    async def get_all_service_status(self, services: list[Service]) -> list[ServiceStatusInfo]:
        """Get status information for multiple services.
        
        Args:
            services: List of services to get status for
            
        Returns:
            List of ServiceStatusInfo objects
        """
        status_list = []

        for service in services:
            try:
                status = await self.get_service_status(service)
                status_list.append(status)
            except Exception as e:
                logger.error("Error getting service status",
                           service_name=service.name,
                           error=str(e))
                # Create a basic status with error state
                status_list.append(ServiceStatusInfo(
                    id=service.id,
                    name=service.name,
                    technology=service.technology,
                    local_port=service.local_port,
                    remote_port=service.remote_port,
                    status=ServiceStatus.FAILED,
                    tags=service.tags.copy(),
                    description=service.description,
                    is_healthy=False
                ))

        return status_list

    async def cleanup_dead_processes(self) -> int:
        """Clean up dead port forward processes.
        
        Returns:
            Number of dead processes cleaned up
        """
        logger.info("Cleaning up dead processes")

        dead_services = []

        for service_id, port_forward in self._active_forwards.items():
            if not port_forward.is_process_alive():
                dead_services.append(service_id)
                logger.info("Found dead process",
                           service_id=service_id,
                           process_id=port_forward.process_id)

        # Remove dead processes
        for service_id in dead_services:
            del self._active_forwards[service_id]

        logger.info("Cleaned up dead processes", count=len(dead_services))
        return len(dead_services)

    async def stop_all_services(self, services: list[Service]) -> list[ServiceStopResult]:
        """Stop all provided services.
        
        Args:
            services: List of services to stop
            
        Returns:
            List of ServiceStopResult objects
        """
        logger.info("Stopping all services", count=len(services))

        results = []

        for service in services:
            try:
                result = await self.stop_service(service)
                results.append(result)
            except Exception as e:
                logger.error("Error stopping service",
                           service_name=service.name,
                           error=str(e))
                results.append(ServiceStopResult.failure_result(
                    service.name,
                    str(e)
                ))

        return results

    async def cleanup_all_processes(self) -> None:
        """Clean up all active port forward processes."""
        logger.info("Cleaning up all processes", count=len(self._active_forwards))

        for technology, adapter in self._adapters.items():
            try:
                await adapter.cleanup_all_processes()
            except Exception as e:
                logger.error("Error cleaning up adapter processes",
                           technology=technology.value,
                           error=str(e))

        self._active_forwards.clear()
        logger.info("All processes cleaned up")

    async def _is_port_available(self, port: int) -> bool:
        """Check if a local port is available.
        
        Args:
            port: Port number to check
            
        Returns:
            True if port is available, False if in use
        """
        return await self._tcp_health_check.check_port_available(port)

    def get_active_forwards_count(self) -> int:
        """Get the number of active port forwards.
        
        Returns:
            Number of active port forwards
        """
        return len(self._active_forwards)

    def get_active_forwards(self) -> dict[UUID, PortForward]:
        """Get all active port forwards.
        
        Returns:
            Dictionary of active port forwards by service ID
        """
        return self._active_forwards.copy()
