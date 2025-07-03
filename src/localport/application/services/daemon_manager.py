"""Daemon manager for background processing capabilities."""

import asyncio
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional, Set
from uuid import UUID
import structlog

from ..dto.service_dto import DaemonStatusInfo
from ...domain.entities.service import Service, ServiceStatus
from ...domain.repositories.service_repository import ServiceRepository
from ...domain.repositories.config_repository import ConfigRepository
from .service_manager import ServiceManager
from .health_monitor import HealthMonitor

logger = structlog.get_logger()


class DaemonManager:
    """Manager for background daemon processing capabilities."""
    
    def __init__(
        self,
        service_repository: ServiceRepository,
        config_repository: ConfigRepository,
        service_manager: ServiceManager,
        health_monitor: HealthMonitor
    ):
        """Initialize the daemon manager.
        
        Args:
            service_repository: Repository for service persistence
            config_repository: Repository for configuration management
            service_manager: Service manager for lifecycle operations
            health_monitor: Health monitor for service monitoring
        """
        self._service_repository = service_repository
        self._config_repository = config_repository
        self._service_manager = service_manager
        self._health_monitor = health_monitor
        
        # Daemon state
        self._is_running = False
        self._started_at: Optional[datetime] = None
        self._background_tasks: Set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()
        
        # Configuration
        self._auto_start_services = True
        self._enable_health_monitoring = True
        self._config_reload_enabled = True
        self._graceful_shutdown_timeout = 30  # seconds
        
        # Signal handlers
        self._original_handlers: Dict[int, any] = {}
    
    async def start_daemon(self, auto_start_services: bool = True) -> None:
        """Start the daemon manager.
        
        Args:
            auto_start_services: Whether to automatically start configured services
        """
        if self._is_running:
            logger.warning("Daemon manager is already running")
            return
        
        logger.info("Starting daemon manager")
        
        self._is_running = True
        self._started_at = datetime.now()
        self._auto_start_services = auto_start_services
        
        try:
            # Setup signal handlers
            self._setup_signal_handlers()
            
            # Load configuration
            await self._load_configuration()
            
            # Start services if requested
            if auto_start_services:
                await self._auto_start_configured_services()
            
            # Start health monitoring
            if self._enable_health_monitoring:
                await self._start_health_monitoring()
            
            # Start background tasks
            await self._start_background_tasks()
            
            logger.info("Daemon manager started successfully")
            
        except Exception as e:
            logger.error("Failed to start daemon manager", error=str(e))
            await self.stop_daemon()
            raise
    
    async def stop_daemon(self, timeout: Optional[float] = None) -> None:
        """Stop the daemon manager.
        
        Args:
            timeout: Timeout for graceful shutdown
        """
        if not self._is_running:
            return
        
        logger.info("Stopping daemon manager")
        
        self._is_running = False
        timeout = timeout or self._graceful_shutdown_timeout
        
        try:
            # Signal shutdown
            self._shutdown_event.set()
            
            # Stop health monitoring
            await self._health_monitor.stop_monitoring()
            
            # Stop all services
            await self._stop_all_services()
            
            # Cancel background tasks
            await self._cancel_background_tasks(timeout)
            
            # Restore signal handlers
            self._restore_signal_handlers()
            
            logger.info("Daemon manager stopped")
            
        except Exception as e:
            logger.error("Error during daemon shutdown", error=str(e))
            raise
    
    async def reload_configuration(self) -> None:
        """Reload configuration and restart services as needed."""
        if not self._is_running:
            logger.warning("Cannot reload configuration: daemon not running")
            return
        
        logger.info("Reloading configuration")
        
        try:
            # Load new configuration
            await self._load_configuration()
            
            # Get current and configured services
            current_services = await self._service_repository.find_all()
            
            # Stop services that are no longer configured
            # Start new services that were added
            # Restart services with changed configuration
            await self._reconcile_services(current_services)
            
            # Restart health monitoring with new configuration
            if self._enable_health_monitoring:
                await self._health_monitor.stop_monitoring()
                await self._start_health_monitoring()
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error("Failed to reload configuration", error=str(e))
            raise
    
    async def get_daemon_status(self) -> DaemonStatusInfo:
        """Get current daemon status.
        
        Returns:
            Daemon status information
        """
        uptime_seconds = None
        if self._started_at:
            uptime_seconds = (datetime.now() - self._started_at).total_seconds()
        
        # Get service counts
        services = await self._service_repository.find_all()
        managed_services = len(services)
        active_forwards = len([s for s in services if s.status == ServiceStatus.RUNNING])
        
        # Get health monitoring status
        health_checks_enabled = self._health_monitor.is_monitoring
        last_health_check = None
        if health_checks_enabled:
            # Get the most recent health check time from any service
            health_statuses = await self._health_monitor.get_all_health_status()
            if health_statuses:
                recent_checks = [info.last_check for info in health_statuses.values() if info.last_check]
                if recent_checks:
                    last_health_check = max(recent_checks)
        
        return DaemonStatusInfo(
            is_running=self._is_running,
            pid=None,  # Will be set by the caller if needed
            started_at=self._started_at,
            uptime_seconds=uptime_seconds,
            managed_services=managed_services,
            active_forwards=active_forwards,
            health_checks_enabled=health_checks_enabled,
            last_health_check=last_health_check
        )
    
    async def run_until_shutdown(self) -> None:
        """Run the daemon until shutdown is requested."""
        if not self._is_running:
            raise RuntimeError("Daemon manager is not running")
        
        logger.info("Daemon manager running, waiting for shutdown signal")
        
        try:
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error("Daemon run error", error=str(e))
            raise
        finally:
            await self.stop_daemon()
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for daemon control."""
        if sys.platform == "win32":
            # Windows doesn't support UNIX signals
            return
        
        def handle_shutdown(signum, frame):
            """Handle shutdown signals."""
            logger.info("Received shutdown signal", signal=signum)
            asyncio.create_task(self.stop_daemon())
        
        def handle_reload(signum, frame):
            """Handle reload signal."""
            logger.info("Received reload signal", signal=signum)
            if self._config_reload_enabled:
                asyncio.create_task(self.reload_configuration())
        
        # Store original handlers
        self._original_handlers[signal.SIGTERM] = signal.signal(signal.SIGTERM, handle_shutdown)
        self._original_handlers[signal.SIGINT] = signal.signal(signal.SIGINT, handle_shutdown)
        self._original_handlers[signal.SIGUSR1] = signal.signal(signal.SIGUSR1, handle_reload)
        
        logger.debug("Signal handlers configured")
    
    def _restore_signal_handlers(self) -> None:
        """Restore original signal handlers."""
        if sys.platform == "win32":
            return
        
        for signum, handler in self._original_handlers.items():
            signal.signal(signum, handler)
        
        self._original_handlers.clear()
        logger.debug("Signal handlers restored")
    
    async def _load_configuration(self) -> None:
        """Load configuration from repository."""
        try:
            # Load services from configuration
            services = await self._config_repository.load_services()
            
            # Update service repository
            for service in services:
                await self._service_repository.save(service)
            
            logger.info("Configuration loaded", service_count=len(services))
            
        except Exception as e:
            logger.error("Failed to load configuration", error=str(e))
            raise
    
    async def _auto_start_configured_services(self) -> None:
        """Automatically start configured services."""
        try:
            services = await self._service_repository.find_all()
            enabled_services = [s for s in services if getattr(s, 'enabled', True)]
            
            if not enabled_services:
                logger.info("No enabled services to start")
                return
            
            logger.info("Auto-starting services", service_count=len(enabled_services))
            
            # Start services in parallel
            start_tasks = []
            for service in enabled_services:
                task = asyncio.create_task(self._start_service_safe(service))
                start_tasks.append(task)
            
            # Wait for all services to start
            results = await asyncio.gather(*start_tasks, return_exceptions=True)
            
            # Log results
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            failure_count = len(results) - success_count
            
            logger.info("Auto-start completed", 
                       success_count=success_count,
                       failure_count=failure_count)
            
        except Exception as e:
            logger.error("Failed to auto-start services", error=str(e))
            raise
    
    async def _start_service_safe(self, service: Service) -> None:
        """Safely start a service with error handling.
        
        Args:
            service: Service to start
        """
        try:
            result = await self._service_manager.start_service(service)
            if result.success:
                logger.info("Service started", service_name=service.name)
            else:
                logger.error("Failed to start service", 
                           service_name=service.name,
                           error=result.error)
        except Exception as e:
            logger.error("Error starting service", 
                        service_name=service.name,
                        error=str(e))
    
    async def _start_health_monitoring(self) -> None:
        """Start health monitoring for services."""
        try:
            services = await self._service_repository.find_all()
            monitored_services = [s for s in services if s.health_check_config]
            
            if monitored_services:
                await self._health_monitor.start_monitoring(monitored_services)
                logger.info("Health monitoring started", 
                           monitored_count=len(monitored_services))
            else:
                logger.info("No services configured for health monitoring")
                
        except Exception as e:
            logger.error("Failed to start health monitoring", error=str(e))
            raise
    
    async def _start_background_tasks(self) -> None:
        """Start background tasks."""
        # Create background task for periodic maintenance
        maintenance_task = asyncio.create_task(self._maintenance_loop())
        self._background_tasks.add(maintenance_task)
        
        # Add task cleanup callback
        maintenance_task.add_done_callback(self._background_tasks.discard)
        
        logger.debug("Background tasks started")
    
    async def _maintenance_loop(self) -> None:
        """Background maintenance loop."""
        logger.debug("Maintenance loop started")
        
        try:
            while self._is_running and not self._shutdown_event.is_set():
                # Perform periodic maintenance
                await self._perform_maintenance()
                
                # Wait before next maintenance cycle (5 minutes)
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=300)
                    break  # Shutdown requested
                except asyncio.TimeoutError:
                    continue  # Continue maintenance loop
                    
        except asyncio.CancelledError:
            logger.debug("Maintenance loop cancelled")
            raise
        except Exception as e:
            logger.error("Maintenance loop error", error=str(e))
            raise
    
    async def _perform_maintenance(self) -> None:
        """Perform periodic maintenance tasks."""
        try:
            # Clean up dead processes
            services = await self._service_repository.find_all()
            for service in services:
                if service.status == ServiceStatus.RUNNING:
                    # Check if process is still alive
                    # This would be implemented based on the service manager's capabilities
                    pass
            
            # Log statistics
            stats = await self._health_monitor.get_monitoring_statistics()
            logger.debug("Maintenance completed", **stats)
            
        except Exception as e:
            logger.error("Maintenance error", error=str(e))
    
    async def _stop_all_services(self) -> None:
        """Stop all running services."""
        try:
            services = await self._service_repository.find_all()
            running_services = [s for s in services if s.status == ServiceStatus.RUNNING]
            
            if not running_services:
                return
            
            logger.info("Stopping all services", service_count=len(running_services))
            
            # Stop services in parallel
            stop_tasks = []
            for service in running_services:
                task = asyncio.create_task(self._stop_service_safe(service))
                stop_tasks.append(task)
            
            # Wait for all services to stop
            await asyncio.gather(*stop_tasks, return_exceptions=True)
            
            logger.info("All services stopped")
            
        except Exception as e:
            logger.error("Failed to stop all services", error=str(e))
    
    async def _stop_service_safe(self, service: Service) -> None:
        """Safely stop a service with error handling.
        
        Args:
            service: Service to stop
        """
        try:
            success = await self._service_manager.stop_service(service)
            if success:
                logger.info("Service stopped", service_name=service.name)
            else:
                logger.error("Failed to stop service", service_name=service.name)
        except Exception as e:
            logger.error("Error stopping service", 
                        service_name=service.name,
                        error=str(e))
    
    async def _cancel_background_tasks(self, timeout: float) -> None:
        """Cancel all background tasks.
        
        Args:
            timeout: Timeout for task cancellation
        """
        if not self._background_tasks:
            return
        
        logger.debug("Cancelling background tasks", task_count=len(self._background_tasks))
        
        # Cancel all tasks
        for task in self._background_tasks:
            task.cancel()
        
        # Wait for tasks to complete with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._background_tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Background tasks did not complete within timeout")
        
        self._background_tasks.clear()
        logger.debug("Background tasks cancelled")
    
    async def _reconcile_services(self, current_services: List[Service]) -> None:
        """Reconcile current services with configuration.
        
        Args:
            current_services: Currently managed services
        """
        # This is a placeholder for service reconciliation logic
        # In a full implementation, this would:
        # 1. Compare current services with newly loaded configuration
        # 2. Stop services that are no longer configured
        # 3. Start new services that were added
        # 4. Restart services with changed configuration
        
        logger.info("Service reconciliation completed", 
                   current_count=len(current_services))
    
    @property
    def is_running(self) -> bool:
        """Check if daemon manager is running."""
        return self._is_running
    
    @property
    def started_at(self) -> Optional[datetime]:
        """Get daemon start time."""
        return self._started_at
    
    @property
    def uptime_seconds(self) -> Optional[float]:
        """Get daemon uptime in seconds."""
        if not self._started_at:
            return None
        return (datetime.now() - self._started_at).total_seconds()
    
    async def set_auto_start_services(self, enabled: bool) -> None:
        """Set auto-start services configuration.
        
        Args:
            enabled: Whether to auto-start services
        """
        self._auto_start_services = enabled
        logger.info("Auto-start services configuration updated", enabled=enabled)
    
    async def set_health_monitoring(self, enabled: bool) -> None:
        """Set health monitoring configuration.
        
        Args:
            enabled: Whether to enable health monitoring
        """
        self._enable_health_monitoring = enabled
        
        if self._is_running:
            if enabled and not self._health_monitor.is_monitoring:
                await self._start_health_monitoring()
            elif not enabled and self._health_monitor.is_monitoring:
                await self._health_monitor.stop_monitoring()
        
        logger.info("Health monitoring configuration updated", enabled=enabled)
    
    async def set_config_reload(self, enabled: bool) -> None:
        """Set configuration reload capability.
        
        Args:
            enabled: Whether to enable config reload
        """
        self._config_reload_enabled = enabled
        logger.info("Configuration reload updated", enabled=enabled)
