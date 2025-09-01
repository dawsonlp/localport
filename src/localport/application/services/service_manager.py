"""Service manager for managing the lifecycle of port forwarding services."""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import UUID

import psutil
import structlog

from ...domain.entities.port_forward import PortForward
from ...domain.entities.service import ForwardingTechnology, Service, ServiceStatus
from ...infrastructure.adapters.kubectl_adapter import KubectlAdapter
from ...infrastructure.adapters.ssh_adapter import SSHAdapter
from ...infrastructure.health_checks.tcp_health_check import TCPHealthCheck
from ...infrastructure.logging.service_log_manager import get_service_log_manager
from ...config.settings import get_settings
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
        self._state_file = self._get_state_file_path()
        self._load_persisted_state()

    async def start_service(self, service: Service) -> ServiceStartResult:
        """Start a port forwarding service.

        Args:
            service: The service to start

        Returns:
            ServiceStartResult with the outcome
        """
        logger.info("Starting service", service_name=service.name)

        try:
            # Check if service is already running by service ID
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
            conflict_info = await self._get_port_conflict_info(service.local_port)
            if conflict_info:
                if conflict_info['is_managed']:
                    error_msg = f"Port {service.local_port} is already in use by another LocalPort service (PID: {conflict_info['pid']})"
                else:
                    error_msg = (f"Port {service.local_port} is already in use by external process\n"
                               f"Process: {conflict_info['name']} (PID: {conflict_info['pid']})\n"
                               f"Command: {conflict_info['cmdline']}\n\n"
                               f"Resolution:\n"
                               f"- Use a different local port in your configuration, or\n"
                               f"- Stop the conflicting process manually if you own it")
                
                logger.error("Port unavailable",
                           service_name=service.name,
                           port=service.local_port,
                           conflict_pid=conflict_info['pid'],
                           is_managed=conflict_info['is_managed'])
                service.update_status(ServiceStatus.FAILED)
                return ServiceStartResult.failure_result(service.name, error_msg)

            # Update service status
            service.update_status(ServiceStatus.STARTING)

            # Get appropriate adapter
            adapter = self._adapters[service.technology]

            # Start the port forward with service logging
            settings = get_settings()
            
            try:
                # Try to start with service logging first (if enabled)
                if (settings.is_service_logging_enabled() and 
                    hasattr(adapter, 'start_port_forward_with_logging')):
                    process_id, service_log_id = await adapter.start_port_forward_with_logging(
                        service.name,
                        service.local_port,
                        service.remote_port,
                        service.connection_info
                    )
                    
                    logger.info("Service started with logging",
                               service_name=service.name,
                               process_id=process_id,
                               service_log_id=service_log_id)
                else:
                    # Fallback to regular port forwarding
                    process_id = await adapter.start_port_forward(
                        service.local_port,
                        service.remote_port,
                        service.connection_info
                    )
                    
                    logger.info("Service started without logging (adapter doesn't support it)",
                               service_name=service.name,
                               process_id=process_id)
                    
            except Exception as logging_error:
                # If service logging fails, fall back to regular port forwarding
                logger.warning("Service logging failed, falling back to regular port forwarding",
                              service_name=service.name,
                              error=str(logging_error))
                
                process_id = await adapter.start_port_forward(
                    service.local_port,
                    service.remote_port,
                    service.connection_info
                )
                
                logger.info("Service started with fallback method",
                           service_name=service.name,
                           process_id=process_id)

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

            # Persist state to disk
            self._persist_state()

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
            process_id = None
            
            if port_forward:
                process_id = port_forward.process_id
                logger.info("Found active forward in memory", 
                           service_name=service.name, 
                           process_id=process_id)
            else:
                # No active forward in memory, but there might be a running process
                # Try to find kubectl processes that match this service
                logger.info("No active forward in memory, searching for running processes", 
                           service_name=service.name)
                
                # Look for kubectl processes using this local port
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        # Check if this is a kubectl process (handle different paths like /snap/kubectl/xxx/kubectl)
                        if (proc.info['cmdline'] and 
                            len(proc.info['cmdline']) > 0 and
                            'kubectl' in proc.info['cmdline'][0] and 
                            'port-forward' in proc.info['cmdline']):
                            
                            # Check if this kubectl process is forwarding our exact port mapping
                            cmdline = ' '.join(proc.info['cmdline'])
                            if self._validate_port_mapping(cmdline, service.local_port, service.remote_port):
                                process_id = proc.info['pid']
                                logger.info("Found running kubectl process for service",
                                           service_name=service.name,
                                           process_id=process_id,
                                           cmdline=cmdline)
                                break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue

            if not process_id:
                logger.info("No running process found for service", service_name=service.name)
                service.update_status(ServiceStatus.STOPPED)
                return ServiceStopResult.success_result(service.name)

            # Get appropriate adapter
            adapter = self._adapters[service.technology]

            # Stop the port forward
            await adapter.stop_port_forward(process_id)

            # Remove from active forwards if it was there
            if service.id in self._active_forwards:
                del self._active_forwards[service.id]
                # Persist state after removing the forward
                self._persist_state()

            # Update service status
            service.update_status(ServiceStatus.STOPPED)

            logger.info("Service stopped successfully",
                       service_name=service.name,
                       process_id=process_id)

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
        
        # Check in-memory state first (fast path)
        if port_forward:
            if port_forward.is_process_alive():
                return True
            else:
                # Process is dead, clean up
                del self._active_forwards[service.id]
                self._persist_state()
        
        # No active forward in memory, search for running processes (slow path)
        logger.debug("Checking for running processes", service_name=service.name)
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                
                # Check if this is a kubectl process (handle different paths like /snap/kubectl/xxx/kubectl)
                if (proc.info['cmdline'] and 
                    len(proc.info['cmdline']) > 0 and
                    'kubectl' in proc.info['cmdline'][0] and 
                    'port-forward' in proc.info['cmdline']):
                    
                    # Check if this kubectl process is forwarding our exact port mapping
                    if self._validate_port_mapping(cmdline, service.local_port, service.remote_port):
                        logger.debug("Found running kubectl process for service",
                                   service_name=service.name,
                                   process_id=proc.info['pid'],
                                   cmdline=cmdline)
                        return True
                
                # Check if this is an SSH process
                elif (service.technology == ForwardingTechnology.SSH and
                      proc.info['cmdline'] and 
                      len(proc.info['cmdline']) > 0 and
                      'ssh' in proc.info['cmdline'][0] and 
                      '-L' in proc.info['cmdline']):
                    
                    # Check if this SSH process is forwarding our exact port mapping
                    if self._validate_ssh_port_mapping(cmdline, service.local_port, service.remote_port):
                        logger.debug("Found running SSH process for service",
                                   service_name=service.name,
                                   process_id=proc.info['pid'],
                                   cmdline=cmdline)
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        return False

    async def get_service_status(self, service: Service) -> ServiceStatusInfo:
        """Get detailed status information for a service.

        Args:
            service: The service to get status for

        Returns:
            ServiceStatusInfo with detailed status
        """
        logger.debug("Getting service status",
                    service_name=service.name,
                    service_id=str(service.id),
                    current_status=service.status.value)
        
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

        # Check if service is actually running using improved detection
        is_running = await self.is_service_running(service)
        
        # Add port forward specific info if available
        if port_forward:
            status_info.process_id = port_forward.process_id
            status_info.started_at = port_forward.started_at
            status_info.last_health_check = port_forward.last_health_check
            status_info.restart_count = port_forward.restart_count
            status_info.uptime_seconds = port_forward.get_uptime_seconds()

            # Check if process is actually alive using improved detection
            if is_running:
                status_info.is_healthy = True
                service.update_status(ServiceStatus.RUNNING)
                status_info.status = ServiceStatus.RUNNING
            else:
                # Process is dead but we still have a record
                status_info.is_healthy = False
                service.update_status(ServiceStatus.FAILED)
                status_info.status = ServiceStatus.FAILED
        else:
            # No active forward in memory - check if process is running externally
            if is_running:
                # Found running process that matches our service but not tracked
                status_info.is_healthy = True
                service.update_status(ServiceStatus.RUNNING)
                status_info.status = ServiceStatus.RUNNING
                logger.info("Found untracked running process for service", 
                           service_name=service.name)
            else:
                # No process found
                status_info.is_healthy = False
                service.update_status(ServiceStatus.STOPPED)
                status_info.status = ServiceStatus.STOPPED

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

    async def detect_orphaned_processes(self, declared_services: list[Service]) -> list[dict]:
        """Detect LocalPort processes that are no longer in the configuration.

        Args:
            declared_services: List of services currently declared in configuration

        Returns:
            List of orphaned process information dictionaries
        """
        logger.info("Detecting orphaned LocalPort processes")
        
        # Get service IDs from declared services
        declared_service_ids = {service.id for service in declared_services}
        
        orphaned_processes = []
        
        # Check state file for processes not in current config
        for service_id, port_forward in self._active_forwards.items():
            if service_id not in declared_service_ids:
                # This process is in our state but not in current config
                if port_forward.is_process_alive():
                    try:
                        proc = psutil.Process(port_forward.process_id)
                        cmdline = ' '.join(proc.cmdline()) if proc.cmdline() else proc.name()
                        
                        orphaned_processes.append({
                            'service_id': str(service_id),
                            'process_id': port_forward.process_id,
                            'local_port': port_forward.local_port,
                            'remote_port': port_forward.remote_port,
                            'started_at': port_forward.started_at,
                            'cmdline': cmdline,
                            'status': 'orphaned'
                        })
                        
                        logger.info("Found orphaned LocalPort process",
                                   service_id=service_id,
                                   process_id=port_forward.process_id,
                                   local_port=port_forward.local_port)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        # Process is dead, will be cleaned up by cleanup_dead_processes
                        pass
                else:
                    # Process is dead, will be cleaned up by cleanup_dead_processes
                    logger.debug("Found dead orphaned process",
                               service_id=service_id,
                               process_id=port_forward.process_id)
        
        logger.info("Orphaned process detection completed", count=len(orphaned_processes))
        return orphaned_processes

    async def cleanup_orphaned_processes(self, declared_services: list[Service]) -> list[dict]:
        """Clean up LocalPort processes that are no longer in the configuration.

        Args:
            declared_services: List of services currently declared in configuration

        Returns:
            List of cleaned up process information dictionaries
        """
        logger.info("Cleaning up orphaned LocalPort processes")
        
        orphaned_processes = await self.detect_orphaned_processes(declared_services)
        cleaned_up = []
        
        for orphan_info in orphaned_processes:
            try:
                service_id = UUID(orphan_info['service_id'])
                process_id = orphan_info['process_id']
                
                # Stop the process using the appropriate adapter
                # For now, assume kubectl (could be enhanced to detect technology)
                adapter = self._adapters[ForwardingTechnology.KUBECTL]
                await adapter.stop_port_forward(process_id)
                
                # Remove from active forwards
                if service_id in self._active_forwards:
                    del self._active_forwards[service_id]
                
                cleaned_up.append(orphan_info)
                logger.info("Cleaned up orphaned process",
                           service_id=service_id,
                           process_id=process_id,
                           local_port=orphan_info['local_port'])
                
            except Exception as e:
                logger.error("Error cleaning up orphaned process",
                           service_id=orphan_info['service_id'],
                           process_id=orphan_info['process_id'],
                           error=str(e))
        
        # Persist the updated state
        if cleaned_up:
            self._persist_state()
        
        logger.info("Orphaned process cleanup completed", count=len(cleaned_up))
        return cleaned_up

    async def _is_port_available(self, port: int) -> bool:
        """Check if a local port is available.

        Args:
            port: Port number to check

        Returns:
            True if port is available, False if in use
        """
        return await self._tcp_health_check.check_port_available(port)

    async def _get_port_conflict_info(self, port: int) -> dict | None:
        """Get detailed information about what's using a port.

        Args:
            port: Port number to check

        Returns:
            Dictionary with conflict details or None if port is available
        """
        if await self._tcp_health_check.check_port_available(port):
            return None

        # Port is in use, find what's using it
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # Check if this process has connections on the port
                connections = proc.connections()
                for conn in connections:
                    if (conn.laddr and conn.laddr.port == port and 
                        conn.status == psutil.CONN_LISTEN):
                        
                        cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else proc.info['name']
                        
                        # Check if this is a LocalPort-managed process
                        is_managed = False
                        for service_id, port_forward in self._active_forwards.items():
                            if (port_forward.process_id == proc.info['pid'] and 
                                port_forward.local_port == port):
                                is_managed = True
                                break
                        
                        return {
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'cmdline': cmdline,
                            'is_managed': is_managed,
                            'port': port
                        }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Port is in use but we couldn't identify the process
        return {
            'pid': None,
            'name': 'Unknown',
            'cmdline': 'Unable to identify process',
            'is_managed': False,
            'port': port
        }

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

    def _get_state_file_path(self) -> Path:
        """Get platform-appropriate state file location.
        
        Returns:
            Path to the state file
        """
        if os.name == 'nt':  # Windows
            state_dir = Path.home() / "AppData/Local/localport"
        else:  # Linux/macOS
            state_dir = Path.home() / ".local/share/localport"
        
        # Ensure directory exists
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / "state.json"

    def _load_persisted_state(self) -> None:
        """Load persisted state from disk and validate processes."""
        if not self._state_file.exists():
            logger.debug("No state file found, starting with empty state")
            return

        try:
            with open(self._state_file, 'r') as f:
                data = json.load(f)

            active_forwards_data = data.get('active_forwards', {})
            logger.info("Loading persisted state", count=len(active_forwards_data))

            # Reconstruct PortForward objects and validate processes
            validated_forwards = {}
            for service_id_str, forward_data in active_forwards_data.items():
                try:
                    service_id = UUID(service_id_str)
                    process_id = forward_data['process_id']
                    
                    # Validate process still exists and matches expected command
                    if self._validate_process(process_id, forward_data.get('local_port'), forward_data.get('remote_port')):
                        port_forward = PortForward(
                            service_id=service_id,
                            process_id=process_id,
                            local_port=forward_data['local_port'],
                            remote_port=forward_data['remote_port'],
                            started_at=datetime.fromisoformat(forward_data['started_at'])
                        )
                        port_forward.restart_count = forward_data.get('restart_count', 0)
                        validated_forwards[service_id] = port_forward
                        logger.info("Restored active forward", 
                                   service_id=service_id,
                                   process_id=process_id,
                                   local_port=forward_data['local_port'])
                    else:
                        logger.info("Process no longer valid, skipping", 
                                   service_id=service_id,
                                   process_id=process_id)
                        
                except Exception as e:
                    logger.warning("Error loading forward state", 
                                  service_id=service_id_str,
                                  error=str(e))

            self._active_forwards = validated_forwards
            logger.info("State loaded successfully", 
                       total_loaded=len(active_forwards_data),
                       validated=len(validated_forwards))

            # Persist the cleaned state
            if len(validated_forwards) != len(active_forwards_data):
                self._persist_state()

        except Exception as e:
            logger.error("Error loading persisted state", error=str(e))
            self._active_forwards = {}

    def migrate_state_to_deterministic_ids(self, services: list[Service]) -> int:
        """Migrate state from random UUIDs to deterministic UUIDs.
        
        This method matches running processes to current service configuration
        based on port mappings and updates the state file with deterministic IDs.
        
        Args:
            services: List of current services with deterministic IDs
            
        Returns:
            Number of processes migrated
        """
        logger.info("Starting state migration to deterministic IDs")
        
        # Create mapping of (local_port, remote_port) -> service
        port_to_service = {}
        for service in services:
            key = (service.local_port, service.remote_port)
            port_to_service[key] = service
        
        migrated_forwards = {}
        migration_count = 0
        
        # Check each active forward for migration
        for old_service_id, port_forward in self._active_forwards.items():
            key = (port_forward.local_port, port_forward.remote_port)
            
            if key in port_to_service:
                # Found a matching service in current config
                new_service = port_to_service[key]
                
                # Check if this is actually a migration (different IDs)
                if old_service_id != new_service.id:
                    logger.info("Migrating process to deterministic ID",
                               old_service_id=old_service_id,
                               new_service_id=new_service.id,
                               service_name=new_service.name,
                               process_id=port_forward.process_id,
                               local_port=port_forward.local_port,
                               remote_port=port_forward.remote_port)
                    
                    # Create new PortForward with updated service ID
                    migrated_forward = PortForward(
                        service_id=new_service.id,
                        process_id=port_forward.process_id,
                        local_port=port_forward.local_port,
                        remote_port=port_forward.remote_port,
                        started_at=port_forward.started_at
                    )
                    migrated_forward.restart_count = port_forward.restart_count
                    migrated_forward.last_health_check = port_forward.last_health_check
                    
                    migrated_forwards[new_service.id] = migrated_forward
                    migration_count += 1
                else:
                    # ID is already deterministic, keep as-is
                    migrated_forwards[old_service_id] = port_forward
            else:
                # No matching service in current config - this is an orphaned process
                logger.info("Found orphaned process during migration",
                           old_service_id=old_service_id,
                           process_id=port_forward.process_id,
                           local_port=port_forward.local_port,
                           remote_port=port_forward.remote_port)
                # Keep the orphaned process for now - it will be handled by orphaned process cleanup
                migrated_forwards[old_service_id] = port_forward
        
        # Update active forwards with migrated state
        self._active_forwards = migrated_forwards
        
        # Persist the migrated state
        if migration_count > 0:
            self._persist_state()
            logger.info("State migration completed", migrated_count=migration_count)
        else:
            logger.info("No migration needed - all IDs are already deterministic")
        
        return migration_count

    def _validate_port_mapping(self, cmdline: str, local_port: int, remote_port: int) -> bool:
        """Validate that a command line contains the expected port mapping.
        
        Args:
            cmdline: Command line string to check
            local_port: Expected local port
            remote_port: Expected remote port
            
        Returns:
            True if the exact port mapping is found, False otherwise
        """
        port_pattern = f'{local_port}:{remote_port}'
        
        # Check for exact port mapping pattern
        if port_pattern in cmdline:
            logger.debug("Port mapping validation successful",
                        local_port=local_port,
                        remote_port=remote_port,
                        pattern=port_pattern)
            return True
        
        logger.debug("Port mapping validation failed",
                    local_port=local_port,
                    remote_port=remote_port,
                    pattern=port_pattern,
                    cmdline=cmdline)
        return False

    def _validate_ssh_port_mapping(self, cmdline: str, local_port: int, remote_port: int) -> bool:
        """Validate that an SSH command line contains the expected port mapping.
        
        Args:
            cmdline: SSH command line string to check
            local_port: Expected local port
            remote_port: Expected remote port
            
        Returns:
            True if the exact SSH port mapping is found, False otherwise
        """
        # SSH tunnel format: -L local_port:remote_host:remote_port
        # We need to check for the local_port and remote_port parts
        import re
        
        # Look for -L port mapping pattern: -L local_port:something:remote_port
        ssh_pattern = rf'-L\s+{local_port}:[^:\s]+:{remote_port}'
        
        if re.search(ssh_pattern, cmdline):
            logger.debug("SSH port mapping validation successful",
                        local_port=local_port,
                        remote_port=remote_port,
                        pattern=ssh_pattern)
            return True
        
        logger.debug("SSH port mapping validation failed",
                    local_port=local_port,
                    remote_port=remote_port,
                    pattern=ssh_pattern,
                    cmdline=cmdline)
        return False

    def _validate_process(self, process_id: int, expected_local_port: int | None = None, expected_remote_port: int | None = None) -> bool:
        """Validate that a process exists and matches expected criteria.
        
        Args:
            process_id: Process ID to validate
            expected_local_port: Expected local port (optional)
            expected_remote_port: Expected remote port (optional)
            
        Returns:
            True if process is valid, False otherwise
        """
        try:
            proc = psutil.Process(process_id)
            cmdline_list = proc.cmdline()
            cmdline = ' '.join(cmdline_list)
            
            logger.debug("Validating process", 
                        process_id=process_id,
                        cmdline=cmdline,
                        expected_local_port=expected_local_port,
                        expected_remote_port=expected_remote_port)
            
            # Check if it's a kubectl port-forward process
            has_kubectl = any('kubectl' in arg for arg in cmdline_list)
            has_port_forward = 'port-forward' in cmdline
            
            if has_kubectl and has_port_forward:
                # Validate kubectl process
                if expected_local_port is not None and expected_remote_port is not None:
                    if not self._validate_port_mapping(cmdline, expected_local_port, expected_remote_port):
                        logger.debug("Kubectl port mapping validation failed",
                                   process_id=process_id,
                                   expected_local_port=expected_local_port,
                                   expected_remote_port=expected_remote_port,
                                   cmdline=cmdline)
                        return False
                elif expected_local_port is not None:
                    # Fallback to local port only validation for backward compatibility
                    port_pattern = f'{expected_local_port}:'
                    if port_pattern not in cmdline:
                        logger.debug("Kubectl local port validation failed",
                                   process_id=process_id,
                                   expected_local_port=expected_local_port,
                                   cmdline=cmdline)
                        return False
                
                logger.debug("Kubectl process validation successful",
                           process_id=process_id,
                           expected_local_port=expected_local_port,
                           expected_remote_port=expected_remote_port)
                return True
            
            # Check if it's an SSH tunnel process
            elif (cmdline_list and len(cmdline_list) > 0 and 
                  'ssh' in cmdline_list[0] and '-L' in cmdline):
                # Validate SSH process
                if expected_local_port is not None and expected_remote_port is not None:
                    if not self._validate_ssh_port_mapping(cmdline, expected_local_port, expected_remote_port):
                        logger.debug("SSH port mapping validation failed",
                                   process_id=process_id,
                                   expected_local_port=expected_local_port,
                                   expected_remote_port=expected_remote_port,
                                   cmdline=cmdline)
                        return False
                elif expected_local_port is not None:
                    # Fallback to local port only validation for backward compatibility
                    port_pattern = f'-L {expected_local_port}:'
                    if port_pattern not in cmdline:
                        logger.debug("SSH local port validation failed",
                                   process_id=process_id,
                                   expected_local_port=expected_local_port,
                                   cmdline=cmdline)
                        return False
                
                logger.debug("SSH process validation successful",
                           process_id=process_id,
                           expected_local_port=expected_local_port,
                           expected_remote_port=expected_remote_port)
                return True
            
            else:
                logger.debug("Process validation failed - not kubectl port-forward or SSH tunnel",
                           process_id=process_id,
                           has_kubectl=has_kubectl,
                           has_port_forward=has_port_forward,
                           has_ssh=('ssh' in cmdline_list[0] if cmdline_list else False),
                           has_ssh_tunnel=('-L' in cmdline),
                           cmdline=cmdline)
                return False
                
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.debug("Process validation failed - process error",
                       process_id=process_id,
                       error=str(e))
            return False

    def _persist_state(self) -> None:
        """Persist current state to disk."""
        try:
            # Convert active forwards to serializable format
            active_forwards_data = {}
            for service_id, port_forward in self._active_forwards.items():
                active_forwards_data[str(service_id)] = {
                    'process_id': port_forward.process_id,
                    'local_port': port_forward.local_port,
                    'remote_port': port_forward.remote_port,
                    'started_at': port_forward.started_at.isoformat(),
                    'restart_count': port_forward.restart_count
                }

            data = {
                'active_forwards': active_forwards_data,
                'last_updated': datetime.now().isoformat()
            }

            # Write atomically by writing to temp file then renaming
            temp_file = self._state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            temp_file.replace(self._state_file)
            logger.debug("State persisted successfully", count=len(active_forwards_data))

        except Exception as e:
            logger.error("Error persisting state", error=str(e))
