"""SSH adapter for port forwarding operations."""

import asyncio
from pathlib import Path
from typing import Any

import psutil
import structlog

logger = structlog.get_logger()


class SSHAdapter:
    """Adapter for SSH tunnel port forwarding operations."""

    def __init__(self) -> None:
        """Initialize the SSH adapter."""
        self._active_processes: dict[int, asyncio.subprocess.Process] = {}

    async def start_port_forward(
        self,
        local_port: int,
        remote_port: int,
        connection_info: dict[str, Any]
    ) -> int:
        """Start an SSH tunnel port-forward process.
        
        Args:
            local_port: Local port to bind to
            remote_port: Remote port to forward to
            connection_info: SSH-specific connection details
            
        Returns:
            Process ID of the started SSH process
            
        Raises:
            RuntimeError: If SSH tunnel fails to start
            ValueError: If connection_info is invalid
        """
        # Extract connection details
        host = connection_info['host']
        user = connection_info.get('user')
        ssh_port = connection_info.get('port', 22)
        key_file = connection_info.get('key_file')
        password = connection_info.get('password')

        # Build SSH command
        cmd = [
            'ssh',
            '-N',  # Don't execute remote command
            '-L', f'{local_port}:localhost:{remote_port}',  # Local port forwarding
            '-o', 'StrictHostKeyChecking=no',  # Don't prompt for host key verification
            '-o', 'UserKnownHostsFile=/dev/null',  # Don't save host keys
            '-o', 'LogLevel=ERROR',  # Reduce SSH output
            '-o', 'ServerAliveInterval=30',  # Keep connection alive
            '-o', 'ServerAliveCountMax=3',  # Max missed keepalives
            '-p', str(ssh_port),  # SSH port
        ]

        # Add key file if specified
        if key_file:
            key_path = Path(key_file).expanduser()
            if not key_path.exists():
                raise ValueError(f"SSH key file not found: {key_path}")
            cmd.extend(['-i', str(key_path)])

        # Add user and host
        if user:
            cmd.append(f'{user}@{host}')
        else:
            cmd.append(host)

        logger.info("Starting SSH tunnel",
                   command=' '.join(cmd[:-1] + ['***@***']),  # Hide credentials
                   local_port=local_port,
                   remote_port=remote_port,
                   host=host,
                   ssh_port=ssh_port)

        try:
            # Handle password authentication if needed
            if password and not key_file:
                # Use sshpass for password authentication
                cmd = ['sshpass', '-p', password] + cmd

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
                raise RuntimeError(f"SSH tunnel failed: {error_msg}")

            # Store the process for later management
            if process.pid:
                self._active_processes[process.pid] = process

            logger.info("SSH tunnel started successfully",
                       pid=process.pid,
                       local_port=local_port,
                       remote_port=remote_port,
                       host=host)

            return process.pid

        except FileNotFoundError as e:
            if 'sshpass' in str(e):
                raise RuntimeError("sshpass command not found. Please install sshpass for password authentication")
            else:
                raise RuntimeError("ssh command not found. Please ensure OpenSSH client is installed")
        except Exception as e:
            logger.error("Failed to start SSH tunnel",
                        error=str(e),
                        local_port=local_port,
                        remote_port=remote_port,
                        host=host)
            raise RuntimeError(f"Failed to start SSH tunnel: {e}")

    async def stop_port_forward(self, process_id: int) -> None:
        """Stop an SSH tunnel process.
        
        Args:
            process_id: Process ID to stop
            
        Raises:
            RuntimeError: If process cannot be stopped
        """
        logger.info("Stopping SSH tunnel", pid=process_id)

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

            logger.info("SSH tunnel stopped successfully", pid=process_id)

        except Exception as e:
            logger.error("Failed to stop SSH tunnel",
                        pid=process_id,
                        error=str(e))
            raise RuntimeError(f"Failed to stop SSH tunnel: {e}")

    async def is_process_running(self, process_id: int) -> bool:
        """Check if an SSH tunnel process is still running.
        
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
        """Get information about an SSH tunnel process.
        
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
        """Clean up all active SSH tunnel processes."""
        logger.info("Cleaning up all SSH tunnel processes",
                   count=len(self._active_processes))

        for process_id in list(self._active_processes.keys()):
            try:
                await self.stop_port_forward(process_id)
            except Exception as e:
                logger.error("Error cleaning up process",
                           pid=process_id,
                           error=str(e))

        self._active_processes.clear()

    async def validate_ssh_available(self) -> bool:
        """Validate that SSH client is available and working.
        
        Returns:
            True if SSH is available, False otherwise
        """
        try:
            process = await asyncio.create_subprocess_exec(
                'ssh', '-V',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            # SSH version info goes to stderr typically
            if process.returncode == 0 or stderr:
                logger.debug("SSH validation successful")
                return True
            else:
                logger.warning("SSH validation failed")
                return False

        except FileNotFoundError:
            logger.warning("SSH command not found")
            return False
        except Exception as e:
            logger.error("Error validating SSH", error=str(e))
            return False

    async def test_ssh_connection(
        self,
        host: str,
        user: str | None = None,
        port: int = 22,
        key_file: str | None = None,
        timeout: float = 10.0
    ) -> bool:
        """Test SSH connection to a host.
        
        Args:
            host: SSH host to test
            user: SSH username
            port: SSH port
            key_file: Path to SSH key file
            timeout: Connection timeout in seconds
            
        Returns:
            True if connection successful, False otherwise
        """
        cmd = [
            'ssh',
            '-o', 'ConnectTimeout=5',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'LogLevel=ERROR',
            '-o', 'BatchMode=yes',  # Don't prompt for passwords
            '-p', str(port),
        ]

        if key_file:
            key_path = Path(key_file).expanduser()
            if key_path.exists():
                cmd.extend(['-i', str(key_path)])

        # Add user and host
        if user:
            cmd.extend([f'{user}@{host}', 'exit'])
        else:
            cmd.extend([host, 'exit'])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                await asyncio.wait_for(process.wait(), timeout=timeout)
                success = process.returncode == 0

                if success:
                    logger.debug("SSH connection test successful", host=host, port=port)
                else:
                    logger.debug("SSH connection test failed", host=host, port=port)

                return success

            except TimeoutError:
                logger.debug("SSH connection test timed out", host=host, port=port)
                process.kill()
                await process.wait()
                return False

        except Exception as e:
            logger.error("Error testing SSH connection",
                        host=host,
                        port=port,
                        error=str(e))
            return False

    async def check_sshpass_available(self) -> bool:
        """Check if sshpass is available for password authentication.
        
        Returns:
            True if sshpass is available, False otherwise
        """
        try:
            process = await asyncio.create_subprocess_exec(
                'sshpass', '-V',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            await process.communicate()
            return process.returncode == 0

        except FileNotFoundError:
            return False
        except Exception:
            return False
