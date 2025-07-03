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
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Start the daemon process."""
        logger.info("Starting LocalPort daemon",
                   config_file=self.config_file,
                   auto_start=self.auto_start)

        try:
            # Initialize repositories and services
            service_repo = MemoryServiceRepository()
            config_repo = YamlConfigRepository(config_file=self.config_file)
            adapter_factory = AdapterFactory()
            health_check_factory = HealthCheckFactory()

            # Initialize core services
            service_manager = ServiceManager()
            restart_manager = RestartManager(service_manager)
            health_monitor = HealthMonitorScheduler(health_check_factory, restart_manager)

            # Initialize daemon manager with new health monitoring system
            self.daemon_manager = DaemonManager(
                service_repository=service_repo,
                config_repository=config_repo,
                service_manager=service_manager,
                health_monitor=health_monitor
            )

            # Setup signal handlers
            self._setup_signal_handlers()

            # Start daemon manager
            await self.daemon_manager.start_daemon(auto_start_services=self.auto_start)

            logger.info("LocalPort daemon started successfully")

            # Run until shutdown
            await self.daemon_manager.run_until_shutdown()

        except Exception as e:
            logger.exception("Failed to start daemon", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the daemon process."""
        logger.info("Stopping LocalPort daemon")

        if self.daemon_manager:
            await self.daemon_manager.stop_daemon()

        self._shutdown_event.set()
        logger.info("LocalPort daemon stopped")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for daemon control."""
        if sys.platform == "win32":
            # Windows signal handling
            signal.signal(signal.SIGINT, self._handle_shutdown_signal)
            signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        else:
            # Unix signal handling
            signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
            signal.signal(signal.SIGINT, self._handle_shutdown_signal)
            signal.signal(signal.SIGUSR1, self._handle_reload_signal)
            signal.signal(signal.SIGHUP, self._handle_reload_signal)

        logger.debug("Signal handlers configured")

    def _handle_shutdown_signal(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        logger.info("Received shutdown signal", signal=signum)
        asyncio.create_task(self.stop())

    def _handle_reload_signal(self, signum: int, frame) -> None:
        """Handle reload signals."""
        logger.info("Received reload signal", signal=signum)
        if self.daemon_manager:
            asyncio.create_task(self.daemon_manager.reload_configuration())


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
