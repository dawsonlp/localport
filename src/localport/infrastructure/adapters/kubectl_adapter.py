"""Kubectl adapter for port forwarding operations."""

import asyncio
from typing import Any

import psutil
import structlog

logger = structlog.get_logger()


class KubectlAdapter:
    """Adapter for kubectl port-forward operations."""

    def __init__(self) -> None:
        """Initialize the kubectl adapter."""
        self._active_processes: dict[int, asyncio.subprocess.Process] = {}

    async def start_port_forward(
        self,
        local_port: int,
        remote_port: int,
        connection_info: dict[str, Any]
    ) -> int:
        """Start a kubectl port-forward process.

        Args:
            local_port: Local port to bind to
            remote_port: Remote port to forward to
            connection_info: Kubectl-specific connection details

        Returns:
            Process ID of the started kubectl process

        Raises:
            RuntimeError: If kubectl port-forward fails to start
            ValueError: If connection_info is invalid
        """
        # Extract connection details
        namespace = connection_info.get('namespace', 'default')
        resource_type = connection_info.get('resource_type', 'service')
        resource_name = connection_info['resource_name']
        context = connection_info.get('context')

        # Build kubectl command
        cmd = [
            'kubectl', 'port-forward',
            f'{resource_type}/{resource_name}',
            f'{local_port}:{remote_port}',
            '--namespace', namespace
        ]

        if context:
            cmd.extend(['--context', context])

        logger.info("Starting kubectl port-forward",
                   command=' '.join(cmd),
                   local_port=local_port,
                   remote_port=remote_port,
                   resource=f"{resource_type}/{resource_name}",
                   namespace=namespace)

        try:
            # Start the process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL
            )

            # Wait a moment to ensure it starts successfully
            await asyncio.sleep(2)

            if process.returncode is not None:
                # Process has already terminated
                stdout, stderr = await process.communicate()
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                raise RuntimeError(f"kubectl port-forward failed: {error_msg}")

            # Store the process for later management
            if process.pid:
                self._active_processes[process.pid] = process

            logger.info("kubectl port-forward started successfully",
                       pid=process.pid,
                       local_port=local_port,
                       remote_port=remote_port,
                       resource=f"{resource_type}/{resource_name}")

            return process.pid

        except FileNotFoundError:
            raise RuntimeError("kubectl command not found. Please ensure kubectl is installed and in PATH")
        except Exception as e:
            logger.error("Failed to start kubectl port-forward",
                        error=str(e),
                        local_port=local_port,
                        remote_port=remote_port)
            raise RuntimeError(f"Failed to start kubectl port-forward: {e}")

    async def stop_port_forward(self, process_id: int) -> None:
        """Stop a kubectl port-forward process.

        Args:
            process_id: Process ID to stop

        Raises:
            RuntimeError: If process cannot be stopped
        """
        logger.info("Stopping kubectl port-forward", pid=process_id)

        try:
            # Try to get the process from our active processes first
            process = self._active_processes.get(process_id)

            if process:
                # Terminate the asyncio process
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except TimeoutError:
                    # Force kill if it doesn't terminate gracefully
                    process.kill()
                    await process.wait()

                # Remove from active processes
                self._active_processes.pop(process_id, None)

            else:
                # Fall back to psutil for processes we don't track
                try:
                    psutil_process = psutil.Process(process_id)
                    psutil_process.terminate()

                    # Wait for graceful termination
                    try:
                        psutil_process.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        # Force kill if it doesn't terminate gracefully
                        psutil_process.kill()
                        psutil_process.wait()

                except psutil.NoSuchProcess:
                    logger.warning("Process not found", pid=process_id)
                    return

            logger.info("kubectl port-forward stopped successfully", pid=process_id)

        except Exception as e:
            logger.error("Failed to stop kubectl port-forward",
                        pid=process_id,
                        error=str(e))
            raise RuntimeError(f"Failed to stop kubectl port-forward: {e}")

    async def is_process_running(self, process_id: int) -> bool:
        """Check if a kubectl port-forward process is still running.

        Args:
            process_id: Process ID to check

        Returns:
            True if process is running, False otherwise
        """
        try:
            # Check our tracked processes first
            process = self._active_processes.get(process_id)
            if process:
                return process.returncode is None

            # Fall back to psutil
            return psutil.pid_exists(process_id)

        except Exception as e:
            logger.debug("Error checking process status",
                        pid=process_id,
                        error=str(e))
            return False

    async def get_process_info(self, process_id: int) -> dict[str, Any] | None:
        """Get information about a kubectl port-forward process.

        Args:
            process_id: Process ID to get info for

        Returns:
            Dictionary with process information, None if process not found
        """
        try:
            psutil_process = psutil.Process(process_id)

            return {
                "pid": process_id,
                "status": psutil_process.status(),
                "create_time": psutil_process.create_time(),
                "cpu_percent": psutil_process.cpu_percent(),
                "memory_info": psutil_process.memory_info()._asdict(),
                "cmdline": psutil_process.cmdline()
            }

        except psutil.NoSuchProcess:
            return None
        except Exception as e:
            logger.error("Error getting process info",
                        pid=process_id,
                        error=str(e))
            return None

    async def cleanup_all_processes(self) -> None:
        """Clean up all active kubectl port-forward processes."""
        logger.info("Cleaning up all kubectl port-forward processes",
                   count=len(self._active_processes))

        for process_id in list(self._active_processes.keys()):
            try:
                await self.stop_port_forward(process_id)
            except Exception as e:
                logger.error("Error cleaning up process",
                           pid=process_id,
                           error=str(e))

        self._active_processes.clear()

    async def validate_kubectl_available(self) -> bool:
        """Validate that kubectl is available and working.

        Returns:
            True if kubectl is available, False otherwise
        """
        try:
            process = await asyncio.create_subprocess_exec(
                'kubectl', 'version', '--client', '--output=json',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.debug("kubectl validation successful")
                return True
            else:
                logger.warning("kubectl validation failed",
                             stderr=stderr.decode().strip())
                return False

        except FileNotFoundError:
            logger.warning("kubectl command not found")
            return False
        except Exception as e:
            logger.error("Error validating kubectl", error=str(e))
            return False

    async def list_contexts(self) -> list[str]:
        """List available kubectl contexts.

        Returns:
            List of available context names
        """
        try:
            process = await asyncio.create_subprocess_exec(
                'kubectl', 'config', 'get-contexts', '-o', 'name',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                contexts = stdout.decode().strip().split('\n')
                return [ctx.strip() for ctx in contexts if ctx.strip()]
            else:
                logger.warning("Failed to list kubectl contexts",
                             stderr=stderr.decode().strip())
                return []

        except Exception as e:
            logger.error("Error listing kubectl contexts", error=str(e))
            return []
