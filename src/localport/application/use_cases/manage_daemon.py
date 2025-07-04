"""Use case for managing daemon operations."""

from dataclasses import dataclass
from enum import Enum

import structlog

from ...domain.repositories.service_repository import ServiceRepository
from ..dto.service_dto import DaemonOperationResult, DaemonStatusResult
from ..services.service_manager import ServiceManager

logger = structlog.get_logger()


class DaemonCommand(str, Enum):
    """Available daemon commands."""
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    STATUS = "status"
    RELOAD = "reload"


@dataclass
class ManageDaemonCommand:
    """Command to manage daemon operations."""
    command: DaemonCommand
    config_file: str | None = None
    force: bool = False
    timeout: float = 30.0


class ManageDaemonUseCase:
    """Use case for managing LocalPort daemon operations."""

    def __init__(
        self,
        service_repository: ServiceRepository,
        service_manager: ServiceManager
    ):
        """Initialize the manage daemon use case.

        Args:
            service_repository: Repository for service persistence
            service_manager: Service manager for lifecycle operations
        """
        self._service_repository = service_repository
        self._service_manager = service_manager
        self._daemon_pid_file = "/tmp/localport.pid"  # TODO: Make configurable

    async def execute(self, command: ManageDaemonCommand) -> DaemonOperationResult:
        """Execute the daemon management command.

        Args:
            command: Daemon management command to execute

        Returns:
            Result of the daemon operation
        """
        logger.info("Executing daemon command",
                   command=command.command.value,
                   config_file=command.config_file,
                   force=command.force)

        try:
            if command.command == DaemonCommand.START:
                return await self._start_daemon(command)
            elif command.command == DaemonCommand.STOP:
                return await self._stop_daemon(command)
            elif command.command == DaemonCommand.RESTART:
                return await self._restart_daemon(command)
            elif command.command == DaemonCommand.STATUS:
                return await self._get_daemon_status(command)
            elif command.command == DaemonCommand.RELOAD:
                return await self._reload_daemon(command)
            else:
                raise ValueError(f"Unknown daemon command: {command.command}")

        except Exception as e:
            logger.error("Daemon command failed",
                        command=command.command.value,
                        error=str(e))
            return DaemonOperationResult(
                command=command.command.value,
                success=False,
                error=str(e)
            )

    async def _start_daemon(self, command: ManageDaemonCommand) -> DaemonOperationResult:
        """Start the LocalPort daemon.

        Args:
            command: Start daemon command

        Returns:
            Result of the start operation
        """
        # Check if daemon is already running
        if await self._is_daemon_running():
            if not command.force:
                return DaemonOperationResult(
                    command=command.command.value,
                    success=False,
                    error="Daemon is already running. Use --force to restart."
                )
            else:
                # Force restart
                logger.info("Daemon already running, forcing restart")
                await self._stop_daemon_process()

        try:
            # Start daemon process
            pid = await self._start_daemon_process(command.config_file)

            # Write PID file
            await self._write_pid_file(pid)

            logger.info("Daemon started successfully", pid=pid)

            return DaemonOperationResult(
                command=command.command.value,
                success=True,
                pid=pid,
                message=f"Daemon started with PID {pid}"
            )

        except Exception as e:
            logger.error("Failed to start daemon", error=str(e))
            return DaemonOperationResult(
                command=command.command.value,
                success=False,
                error=f"Failed to start daemon: {str(e)}"
            )

    async def _stop_daemon(self, command: ManageDaemonCommand) -> DaemonOperationResult:
        """Stop the LocalPort daemon.

        Args:
            command: Stop daemon command

        Returns:
            Result of the stop operation
        """
        if not await self._is_daemon_running():
            return DaemonOperationResult(
                command=command.command.value,
                success=False,
                error="Daemon is not running"
            )

        try:
            # Get daemon PID
            pid = await self._get_daemon_pid()

            # Stop daemon process
            await self._stop_daemon_process(command.timeout)

            # Remove PID file
            await self._remove_pid_file()

            logger.info("Daemon stopped successfully", pid=pid)

            return DaemonOperationResult(
                command=command.command.value,
                success=True,
                pid=pid,
                message=f"Daemon stopped (was PID {pid})"
            )

        except Exception as e:
            logger.error("Failed to stop daemon", error=str(e))
            return DaemonOperationResult(
                command=command.command.value,
                success=False,
                error=f"Failed to stop daemon: {str(e)}"
            )

    async def _restart_daemon(self, command: ManageDaemonCommand) -> DaemonOperationResult:
        """Restart the LocalPort daemon.

        Args:
            command: Restart daemon command

        Returns:
            Result of the restart operation
        """
        logger.info("Restarting daemon")

        # Stop daemon if running
        if await self._is_daemon_running():
            stop_result = await self._stop_daemon(
                ManageDaemonCommand(DaemonCommand.STOP, timeout=command.timeout)
            )
            if not stop_result.success:
                return DaemonOperationResult(
                    command=command.command.value,
                    success=False,
                    error=f"Failed to stop daemon during restart: {stop_result.error}"
                )

        # Start daemon
        start_result = await self._start_daemon(
            ManageDaemonCommand(DaemonCommand.START, config_file=command.config_file)
        )

        if start_result.success:
            return DaemonOperationResult(
                command=command.command.value,
                success=True,
                pid=start_result.pid,
                message=f"Daemon restarted with PID {start_result.pid}"
            )
        else:
            return DaemonOperationResult(
                command=command.command.value,
                success=False,
                error=f"Failed to start daemon during restart: {start_result.error}"
            )

    async def _get_daemon_status(self, command: ManageDaemonCommand) -> DaemonOperationResult:
        """Get the status of the LocalPort daemon.

        Args:
            command: Status daemon command

        Returns:
            Result containing daemon status information
        """
        try:
            is_running = await self._is_daemon_running()

            if is_running:
                pid = await self._get_daemon_pid()
                uptime = await self._get_daemon_uptime(pid)
                active_services = await self._get_active_services_count()

                status = DaemonStatusResult(
                    running=True,
                    pid=pid,
                    uptime_seconds=uptime,
                    active_services=active_services
                )

                message = f"Daemon is running (PID {pid}, {active_services} active services)"
            else:
                status = DaemonStatusResult(running=False)
                message = "Daemon is not running"

            return DaemonOperationResult(
                command=command.command.value,
                success=True,
                message=message,
                status=status
            )

        except Exception as e:
            logger.error("Failed to get daemon status", error=str(e))
            return DaemonOperationResult(
                command=command.command.value,
                success=False,
                error=f"Failed to get daemon status: {str(e)}"
            )

    async def _reload_daemon(self, command: ManageDaemonCommand) -> DaemonOperationResult:
        """Reload the daemon configuration.

        Args:
            command: Reload daemon command

        Returns:
            Result of the reload operation
        """
        if not await self._is_daemon_running():
            return DaemonOperationResult(
                command=command.command.value,
                success=False,
                error="Daemon is not running"
            )

        try:
            # Send reload signal to daemon
            pid = await self._get_daemon_pid()
            await self._send_reload_signal(pid)

            logger.info("Daemon configuration reloaded", pid=pid)

            return DaemonOperationResult(
                command=command.command.value,
                success=True,
                pid=pid,
                message=f"Daemon configuration reloaded (PID {pid})"
            )

        except Exception as e:
            logger.error("Failed to reload daemon", error=str(e))
            return DaemonOperationResult(
                command=command.command.value,
                success=False,
                error=f"Failed to reload daemon: {str(e)}"
            )

    async def _is_daemon_running(self) -> bool:
        """Check if the daemon is currently running.

        Returns:
            True if daemon is running, False otherwise
        """
        try:
            import os

            import psutil

            if not os.path.exists(self._daemon_pid_file):
                return False

            with open(self._daemon_pid_file) as f:
                pid = int(f.read().strip())

            return psutil.pid_exists(pid)

        except (FileNotFoundError, ValueError, OSError):
            return False

    async def _get_daemon_pid(self) -> int | None:
        """Get the daemon process ID.

        Returns:
            Daemon PID if running, None otherwise
        """
        try:
            import os

            if not os.path.exists(self._daemon_pid_file):
                return None

            with open(self._daemon_pid_file) as f:
                return int(f.read().strip())

        except (FileNotFoundError, ValueError, OSError):
            return None

    async def _start_daemon_process(self, config_file: str | None = None) -> int:
        """Start the daemon process.

        Args:
            config_file: Optional configuration file path

        Returns:
            Process ID of the started daemon
        """
        import asyncio
        import sys

        # Build daemon command
        cmd = [sys.executable, "-m", "localport.daemon"]

        if config_file:
            cmd.extend(["--config", config_file])

        # Add PID file argument
        cmd.extend(["--pid-file", self._daemon_pid_file])

        # Start daemon process in background
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            stdin=asyncio.subprocess.DEVNULL,
            start_new_session=True  # Detach from parent
        )

        # Wait for daemon to write PID file and become ready
        max_wait_time = 10.0  # Maximum time to wait for daemon startup
        check_interval = 0.5  # Check every 500ms
        elapsed_time = 0.0

        while elapsed_time < max_wait_time:
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval

            # Check if PID file exists and daemon is running
            if await self._is_daemon_running():
                daemon_pid = await self._get_daemon_pid()
                if daemon_pid:
                    logger.info("Daemon startup verified", pid=daemon_pid, startup_time=elapsed_time)
                    return daemon_pid

            # Check if the initial process failed early
            if process.returncode is not None:
                raise RuntimeError(f"Daemon process failed to start (exit code: {process.returncode})")

        # If we get here, daemon didn't start within timeout
        raise RuntimeError(f"Daemon failed to start within {max_wait_time} seconds")

    async def _stop_daemon_process(self, timeout: float = 30.0) -> None:
        """Stop the daemon process.

        Args:
            timeout: Timeout for graceful shutdown
        """

        import psutil

        pid = await self._get_daemon_pid()
        if not pid:
            return

        try:
            process = psutil.Process(pid)

            # Send SIGTERM for graceful shutdown
            process.terminate()

            # Wait for graceful termination
            try:
                process.wait(timeout=timeout)
            except psutil.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                logger.warning("Daemon did not terminate gracefully, forcing kill", pid=pid)
                process.kill()
                process.wait()

        except psutil.NoSuchProcess:
            # Process already terminated
            pass

    async def _write_pid_file(self, pid: int) -> None:
        """Write the daemon PID to file.

        Args:
            pid: Process ID to write
        """
        import os

        # Ensure directory exists
        os.makedirs(os.path.dirname(self._daemon_pid_file), exist_ok=True)

        with open(self._daemon_pid_file, 'w') as f:
            f.write(str(pid))

    async def _remove_pid_file(self) -> None:
        """Remove the daemon PID file."""
        import os

        try:
            os.remove(self._daemon_pid_file)
        except FileNotFoundError:
            pass

    async def _get_daemon_uptime(self, pid: int) -> float:
        """Get daemon uptime in seconds.

        Args:
            pid: Process ID

        Returns:
            Uptime in seconds
        """
        try:
            import time

            import psutil

            process = psutil.Process(pid)
            create_time = process.create_time()
            return time.time() - create_time

        except psutil.NoSuchProcess:
            return 0.0

    async def _get_active_services_count(self) -> int:
        """Get the number of active services.

        Returns:
            Number of active services
        """
        try:
            # Use service manager's active forwards count instead of repository
            # The service manager tracks actually running processes
            return self._service_manager.get_active_forwards_count()
        except Exception:
            return 0

    async def _send_reload_signal(self, pid: int) -> None:
        """Send reload signal to daemon process.

        Args:
            pid: Process ID to signal
        """
        import os
        import signal

        try:
            os.kill(pid, signal.SIGUSR1)  # Use SIGUSR1 for reload
        except OSError as e:
            raise RuntimeError(f"Failed to send reload signal: {e}")
