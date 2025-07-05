"""Base adapter interface for port forwarding implementations."""

from abc import ABC, abstractmethod
from typing import Any

import structlog

from ...domain.value_objects.connection_info import ConnectionInfo

logger = structlog.get_logger()


class PortForwardingAdapter(ABC):
    """Abstract base class for port forwarding adapters."""

    @abstractmethod
    async def start_port_forward(
        self,
        local_port: int,
        remote_port: int,
        connection_info: ConnectionInfo
    ) -> int:
        """Start a port forwarding process.

        Args:
            local_port: Local port to bind to
            remote_port: Remote port to forward to
            connection_info: Connection information object

        Returns:
            Process ID of the started port forward

        Raises:
            RuntimeError: If port forward fails to start
        """
        pass

    @abstractmethod
    async def stop_port_forward(self, process_id: int) -> None:
        """Stop a port forwarding process.

        Args:
            process_id: Process ID to stop

        Raises:
            RuntimeError: If process cannot be stopped
        """
        pass

    @abstractmethod
    async def is_port_forward_running(self, process_id: int) -> bool:
        """Check if a port forward process is still running.

        Args:
            process_id: Process ID to check

        Returns:
            True if process is running, False otherwise
        """
        pass

    @abstractmethod
    async def validate_connection_info(self, connection_info: ConnectionInfo) -> list[str]:
        """Validate connection information for this adapter.

        Args:
            connection_info: Connection information object to validate

        Returns:
            List of validation errors (empty if valid)
        """
        pass

    @abstractmethod
    def get_adapter_name(self) -> str:
        """Get the name of this adapter.

        Returns:
            Human-readable adapter name
        """
        pass

    @abstractmethod
    def get_required_tools(self) -> list[str]:
        """Get list of required external tools for this adapter.

        Returns:
            List of required tool names (e.g., ['kubectl', 'ssh'])
        """
        pass

    async def check_prerequisites(self) -> bool:
        """Check if all prerequisites for this adapter are met.

        Returns:
            True if prerequisites are met, False otherwise
        """
        import shutil

        required_tools = self.get_required_tools()
        missing_tools = []

        for tool in required_tools:
            if not shutil.which(tool):
                missing_tools.append(tool)

        if missing_tools:
            logger.warning("Missing required tools for adapter",
                          adapter=self.get_adapter_name(),
                          missing_tools=missing_tools)
            return False

        logger.debug("Prerequisites check passed",
                    adapter=self.get_adapter_name(),
                    required_tools=required_tools)
        return True

    async def get_port_forward_status(self, process_id: int) -> dict[str, Any]:
        """Get detailed status of a port forward process.

        Args:
            process_id: Process ID to check

        Returns:
            Dictionary with status information
        """
        try:
            import psutil

            if not psutil.pid_exists(process_id):
                return {
                    'running': False,
                    'status': 'not_found',
                    'error': 'Process not found'
                }

            process = psutil.Process(process_id)

            return {
                'running': True,
                'status': process.status(),
                'cpu_percent': process.cpu_percent(),
                'memory_info': process.memory_info()._asdict(),
                'create_time': process.create_time(),
                'cmdline': process.cmdline()
            }

        except Exception as e:
            logger.error("Failed to get port forward status",
                        process_id=process_id,
                        error=str(e))
            return {
                'running': False,
                'status': 'error',
                'error': str(e)
            }

    async def cleanup_dead_processes(self) -> int:
        """Clean up any dead port forward processes created by this adapter.

        Returns:
            Number of processes cleaned up
        """
        # Default implementation - subclasses can override for adapter-specific cleanup
        try:
            import psutil

            cleaned_count = 0
            adapter_name = self.get_adapter_name().lower()

            # Look for processes that might be from this adapter
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if not cmdline:
                        continue

                    # Check if this looks like a process from this adapter
                    cmdline_str = ' '.join(cmdline).lower()

                    if adapter_name in cmdline_str and 'port-forward' in cmdline_str:
                        # Check if process is actually dead/zombie
                        if proc.status() in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]:
                            proc.terminate()
                            cleaned_count += 1
                            logger.debug("Cleaned up dead process",
                                        adapter=self.get_adapter_name(),
                                        pid=proc.pid)

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if cleaned_count > 0:
                logger.info("Cleaned up dead processes",
                           adapter=self.get_adapter_name(),
                           count=cleaned_count)

            return cleaned_count

        except Exception as e:
            logger.error("Failed to cleanup dead processes",
                        adapter=self.get_adapter_name(),
                        error=str(e))
            return 0


class AdapterError(Exception):
    """Base exception for adapter-related errors."""
    pass


class AdapterNotAvailableError(AdapterError):
    """Raised when an adapter's prerequisites are not met."""
    pass


class PortForwardStartError(AdapterError):
    """Raised when a port forward fails to start."""
    pass


class PortForwardStopError(AdapterError):
    """Raised when a port forward fails to stop."""
    pass


class InvalidConnectionInfoError(AdapterError):
    """Raised when connection information is invalid."""
    pass
