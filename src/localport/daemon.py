"""LocalPort daemon entry point for background operation."""

import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path

import structlog

from .application.services.daemon_manager import DaemonManager
from .application.services.health_monitor_scheduler import HealthMonitorScheduler
from .application.services.restart_manager import RestartManager
from .application.services.service_manager import ServiceManager
from .infrastructure.adapters.adapter_factory import AdapterFactory
from .infrastructure.health_checks.health_check_factory import HealthCheckFactory
from .infrastructure.repositories.memory_service_repository import (
    MemoryServiceRepository,
)
from .infrastructure.repositories.yaml_config_repository import YamlConfigRepository
from .infrastructure.shutdown import (
    AsyncSignalHandler,
    ShutdownCoordinator,
    TaskManager,
)

logger = structlog.get_logger()


class LocalPortDaemon:
    """Main daemon process for LocalPort background operation."""

    def __init__(self, config_file: str | None = None, auto_start: bool = True):
        """Initialize the daemon.

        Args:
            config_file: Optional configuration file path
            auto_start: Whether to auto-start configured services
        """
        self.config_file = config_file
        self.auto_start = auto_start
        self.daemon_manager: DaemonManager | None = None
        
        # New shutdown infrastructure
        self._task_manager = TaskManager()
        self._signal_handler: AsyncSignalHandler | None = None
        self._shutdown_coordinator: ShutdownCoordinator | None = None

    async def start(self) -> None:
        """Start the daemon process with graceful shutdown infrastructure."""
        logger.info("Starting LocalPort daemon with graceful shutdown",
                   config_file=self.config_file,
                   auto_start=self.auto_start)

        try:
            # Initialize shutdown infrastructure first
            self._signal_handler = AsyncSignalHandler()
            self._shutdown_coordinator = ShutdownCoordinator(
                self._task_manager,
                self._signal_handler
            )

            # Setup signal handlers
            self._signal_handler.setup_signal_handlers()

            # Initialize repositories and services
            service_repo = MemoryServiceRepository()
            config_repo = YamlConfigRepository(config_path=self.config_file)
            AdapterFactory()
            health_check_factory = HealthCheckFactory()

            # Initialize core services
            service_manager = ServiceManager()
            restart_manager = RestartManager(service_manager)
            health_monitor = HealthMonitorScheduler(
                health_check_factory, 
                restart_manager,
                task_manager=self._task_manager
            )

            # Initialize daemon manager with new health monitoring system
            self.daemon_manager = DaemonManager(
                service_repository=service_repo,
                config_repository=config_repo,
                service_manager=service_manager,
                health_monitor=health_monitor
            )

            # Register daemon manager tasks with task manager
            await self._register_daemon_tasks()

            # Start daemon manager
            await self.daemon_manager.start_daemon(auto_start_services=self.auto_start)

            logger.info("LocalPort daemon started successfully")

            # Run until shutdown signal
            await self._shutdown_coordinator.wait_for_shutdown_signal()
            
            logger.info("Shutdown signal received, initiating graceful shutdown")
            
            # Perform graceful shutdown
            success = await self._shutdown_coordinator.initiate_shutdown()
            
            if success:
                logger.info("Graceful shutdown completed successfully")
            else:
                logger.warning("Graceful shutdown completed with issues")

        except Exception as e:
            logger.exception("Failed to start daemon", error=str(e))
            # Attempt emergency shutdown
            if self._shutdown_coordinator:
                await self._shutdown_coordinator.emergency_shutdown()
            raise
        finally:
            # Cleanup signal handlers
            if self._signal_handler:
                self._signal_handler.cleanup_signal_handlers()

    async def _register_daemon_tasks(self) -> None:
        """Register daemon manager tasks with the task manager."""
        logger.debug("Registering daemon tasks with task manager")
        
        # Register daemon manager shutdown callback
        if self._shutdown_coordinator and self.daemon_manager:
            from .infrastructure.shutdown.shutdown_coordinator import ShutdownPhase
            
            # Register daemon manager stop in the CANCEL_TASKS phase
            self._shutdown_coordinator.register_phase_callback(
                ShutdownPhase.CANCEL_TASKS,
                self._stop_daemon_manager
            )
            
            # Register configuration reload handler
            if self._signal_handler:
                # Handle reload signals
                async def handle_reload():
                    if self.daemon_manager:
                        await self.daemon_manager.reload_configuration()
                
                # Check for reload signals periodically
                reload_task = self._task_manager.register_task(
                    "reload_signal_monitor",
                    self._monitor_reload_signals(),
                    group="daemon_management",
                    priority=10
                )

    async def _stop_daemon_manager(self) -> None:
        """Stop the daemon manager during shutdown."""
        if self.daemon_manager:
            logger.info("Stopping daemon manager")
            await self.daemon_manager.stop_daemon()

    async def _monitor_reload_signals(self) -> None:
        """Monitor for reload signals."""
        if not self._signal_handler:
            return
            
        while True:
            try:
                # Wait for reload signal with timeout
                await asyncio.wait_for(
                    self._signal_handler.wait_for_reload(),
                    timeout=5.0
                )
                
                logger.info("Reload signal received")
                if self.daemon_manager:
                    await self.daemon_manager.reload_configuration()
                    
                # Reset the reload event for next signal
                self._signal_handler.reload_event.clear()
                
            except asyncio.TimeoutError:
                # Normal timeout, continue monitoring
                continue
            except asyncio.CancelledError:
                logger.debug("Reload signal monitoring cancelled")
                break
            except Exception as e:
                logger.exception("Error monitoring reload signals", error=str(e))
                await asyncio.sleep(1.0)  # Brief pause before retry


def daemonize() -> None:
    """Daemonize the current process using the Unix double-fork technique."""
    if sys.platform == "win32":
        # Windows doesn't support fork, skip daemonization
        return

    try:
        # First fork
        pid = os.fork()
        if pid > 0:
            # Parent process, exit
            sys.exit(0)
    except OSError as e:
        logger.error("First fork failed", error=str(e))
        sys.exit(1)

    # Decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    try:
        # Second fork
        pid = os.fork()
        if pid > 0:
            # Parent process, exit
            sys.exit(0)
    except OSError as e:
        logger.error("Second fork failed", error=str(e))
        sys.exit(1)

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    # Redirect stdin, stdout, stderr to /dev/null
    with open(os.devnull) as dev_null_r:
        os.dup2(dev_null_r.fileno(), sys.stdin.fileno())

    with open(os.devnull, 'w') as dev_null_w:
        os.dup2(dev_null_w.fileno(), sys.stdout.fileno())
        os.dup2(dev_null_w.fileno(), sys.stderr.fileno())


def setup_daemon_logging(log_file: str | None = None) -> None:
    """Setup logging for daemon operation.

    Args:
        log_file: Optional log file path
    """
    import structlog

    # Default log file location
    if not log_file:
        log_dir = Path.home() / ".local" / "share" / "localport" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / "daemon.log")

    # Configure structlog for daemon operation
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Setup file logging
    import logging
    import logging.handlers

    # Create file handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)


def main() -> None:
    """Main entry point for the daemon."""
    parser = argparse.ArgumentParser(description="LocalPort daemon")
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Configuration file path"
    )
    parser.add_argument(
        "--no-auto-start",
        action="store_true",
        help="Don't auto-start configured services"
    )
    parser.add_argument(
        "--foreground", "-f",
        action="store_true",
        help="Run in foreground (don't daemonize)"
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="Log file path"
    )
    parser.add_argument(
        "--pid-file",
        type=str,
        default="/tmp/localport.pid",
        help="PID file path"
    )

    args = parser.parse_args()

    # Setup logging
    setup_daemon_logging(args.log_file)

    # Daemonize if not running in foreground
    if not args.foreground:
        daemonize()

    # Write PID file
    try:
        with open(args.pid_file, 'w') as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.error("Failed to write PID file", pid_file=args.pid_file, error=str(e))
        sys.exit(1)

    # Create and start daemon
    daemon = LocalPortDaemon(
        config_file=args.config,
        auto_start=not args.no_auto_start
    )

    try:
        # Run daemon
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
    except Exception as e:
        logger.exception("Daemon failed", error=str(e))
        sys.exit(1)
    finally:
        # Clean up PID file
        try:
            os.remove(args.pid_file)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
