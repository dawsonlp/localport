"""SSH adapter for port forwarding operations."""

import asyncio
from pathlib import Path
from typing import Any, Optional

import psutil
import structlog

from .base_adapter import PortForwardingAdapter
from ..logging.service_log_manager import get_service_log_manager
from ...domain.value_objects.connection_info import ConnectionInfo

logger = structlog.get_logger()


class SSHAdapter(PortForwardingAdapter):
    """Adapter for SSH tunnel port forwarding operations."""

    def __init__(self) -> None:
        """Initialize the SSH adapter."""
        self._active_processes: dict[int, asyncio.subprocess.Process] = {}
        self._service_log_manager = get_service_log_manager()
        self._service_logs: dict[int, str] = {}  # Maps PID to service_id

    async def start_port_forward_with_logging(
        self,
        service_name: str,
        local_port: int,
        remote_port: int,
        connection_info: ConnectionInfo
    ) -> tuple[int, str]:
        """Start an SSH tunnel port-forward process with service logging.

        Args:
            service_name: Name of the service for logging
            local_port: Local port to bind to
            remote_port: Remote port to forward to
            connection_info: SSH connection information object

        Returns:
            Tuple of (process_id, service_id)

        Raises:
            RuntimeError: If SSH tunnel fails to start
            ValueError: If connection_info is invalid
        """
        # Extract connection details using object methods
        host = connection_info.get_ssh_host()
        user = connection_info.get_ssh_user()
        ssh_port = connection_info.get_ssh_port()
        key_file = connection_info.get_ssh_key_file()
        password = connection_info.config.get('password')  # Direct access for password since no method exists

        # Create service configuration for logging
        service_config = {
            'local_port': local_port,
            'host': host,
            'port': remote_port,
            'type': 'ssh',
            'ssh_port': ssh_port,
            'user': user,
            'key_file': key_file,
            'has_password': bool(password)  # Don't log actual password
        }

        # Create service log
        try:
            service_id, log_file = self._service_log_manager.create_service_log(
                service_name, service_config
            )
            
            logger.info("service_log_created_for_ssh",
                       service_name=service_name,
                       service_id=service_id,
                       log_file=str(log_file))
        except Exception as e:
            logger.error("failed_to_create_service_log",
                        service_name=service_name,
                        error=str(e))
            # Fall back to original behavior if logging fails
            return await self.start_port_forward(local_port, remote_port, connection_info), None

        # Get remote host for tunnel destination (supports bastion host scenarios)
        remote_host = connection_info.get_ssh_remote_host()
        
        # Build SSH command
        cmd = [
            'ssh',
            '-N',  # Don't execute remote command
            '-L', f'{local_port}:{remote_host}:{remote_port}',  # Local port forwarding
            '-o', 'StrictHostKeyChecking=no',  # Don't prompt for host key verification
            '-o', 'UserKnownHostsFile=/dev/null',  # Don't save host keys
            '-o', 'LogLevel=INFO',  # More verbose for logging (changed from ERROR)
            '-o', 'ServerAliveInterval=30',  # Keep connection alive
            '-o', 'ServerAliveCountMax=3',  # Max missed keepalives
            '-p', str(ssh_port),  # SSH port
        ]

        # Add key file if specified
        if key_file:
            key_path = Path(key_file).expanduser()
            if not key_path.exists():
                from ...domain.exceptions import SSHKeyNotFoundError
                raise SSHKeyNotFoundError(
                    key_path=str(key_path),
                    service_name=service_name
                )
            cmd.extend(['-i', str(key_path)])

        # Add user and host
        if user:
            cmd.append(f'{user}@{host}')
        else:
            cmd.append(host)


        logger.info("Starting SSH tunnel with logging",
                   command=' '.join(cmd[:-1] + ['***@***']),  # Hide credentials
                   local_port=local_port,
                   remote_port=remote_port,
                   host=host,
                   remote_host=remote_host,
                   ssh_port=ssh_port,
                   service_id=service_id,
                   log_file=str(log_file))

        try:
            # Handle password authentication if needed
            if password and not key_file:
                # Use sshpass for password authentication
                cmd = ['sshpass', '-p', password] + cmd

            # Open log file for writing
            log_file_handle = open(log_file, 'a', encoding='utf-8', buffering=1)  # Line buffered

            # Start the process with log file output
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=log_file_handle,
                stderr=asyncio.subprocess.STDOUT,  # Combine stderr with stdout
                stdin=asyncio.subprocess.DEVNULL
            )

            logger.info("SSH subprocess created with logging", 
                       pid=process.pid,
                       service_id=service_id)

            # Wait a moment to ensure it starts successfully
            await asyncio.sleep(2)

            if process.returncode is not None:
                # Process has already terminated
                log_file_handle.close()
                logger.error("SSH process terminated early", 
                           pid=process.pid,
                           service_id=service_id)
                raise RuntimeError("SSH tunnel failed to start")

            # Store the process and service log mapping
            if process.pid:
                self._active_processes[process.pid] = process
                self._service_logs[process.pid] = service_id

            # Note: We don't close log_file_handle here as the process needs to write to it
            # It will be closed when the process terminates

            logger.info("SSH tunnel started successfully with logging",
                       pid=process.pid,
                       service_id=service_id,
                       local_port=local_port,
                       remote_port=remote_port,
                       host=host)

            return process.pid, service_id

        except FileNotFoundError as e:
            if 'log_file_handle' in locals():
                log_file_handle.close()
            if 'sshpass' in str(e):
                raise RuntimeError("sshpass command not found. Please install sshpass for password authentication")
            else:
                raise RuntimeError("ssh command not found. Please ensure OpenSSH client is installed")
        except Exception as e:
            if 'log_file_handle' in locals():
                log_file_handle.close()
            logger.error("Failed to start SSH tunnel with logging",
                        error=str(e),
                        service_id=service_id,
                        local_port=local_port,
                        remote_port=remote_port,
                        host=host)
            raise RuntimeError(f"Failed to start SSH tunnel: {e}")

    async def start_port_forward(
        self,
        local_port: int,
        remote_port: int,
        connection_info: "ConnectionInfo"
    ) -> int:
        """Start an SSH tunnel port-forward process.

        Args:
            local_port: Local port to bind to
            remote_port: Remote port to forward to
            connection_info: SSH connection information object

        Returns:
            Process ID of the started SSH process

        Raises:
            RuntimeError: If SSH tunnel fails to start
            ValueError: If connection_info is invalid
        """
        # Extract connection details using object methods
        host = connection_info.get_ssh_host()
        user = connection_info.get_ssh_user()
        ssh_port = connection_info.get_ssh_port()
        key_file = connection_info.get_ssh_key_file()
        password = connection_info.config.get('password')  # Direct access for password since no method exists

        # Get remote host for tunnel destination (supports bastion host scenarios)
        remote_host = connection_info.get_ssh_remote_host()

        # Build SSH command
        cmd = [
            'ssh',
            '-N',  # Don't execute remote command
            '-L', f'{local_port}:{remote_host}:{remote_port}',  # Local port forwarding
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
                from ...domain.exceptions import SSHKeyNotFoundError
                raise SSHKeyNotFoundError(
                    key_path=str(key_path)
                )
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
                   remote_host=remote_host,
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

        # Get service_id for cleanup if this process has logging
        service_id = self._service_logs.get(process_id)

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

                except (psutil.NoSuchProcess, Exception) as e:
                    if "NoSuchProcess" in str(e) or isinstance(e, psutil.NoSuchProcess):
                        logger.warning("Process not found", pid=process_id)
                        # Still need to clean up service log tracking
                        if service_id:
                            self._service_logs.pop(process_id, None)
                            self._service_log_manager.remove_service_log(service_id)
                        return
                    else:
                        # Re-raise other exceptions
                        raise

            # Clean up service log tracking
            if service_id:
                self._service_logs.pop(process_id, None)
                self._service_log_manager.remove_service_log(service_id)
                logger.info("service_log_cleaned_up", 
                           pid=process_id,
                           service_id=service_id)

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

    async def validate_ssh_connectivity(self, connection_info: dict[str, Any]) -> tuple[bool, str]:
        """Pre-flight SSH connectivity check.

        Args:
            connection_info: SSH connection configuration

        Returns:
            Tuple of (success, message)
        """
        host = connection_info['host']
        port = connection_info.get('port', 22)
        user = connection_info.get('user')
        key_file = connection_info.get('key_file')
        
        # Build test command
        cmd = [
            'ssh',
            '-o', 'ConnectTimeout=5',
            '-o', 'BatchMode=yes',  # Don't prompt for passwords
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'LogLevel=ERROR',
            '-p', str(port)
        ]
        
        # Add key file if specified
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
            
            await asyncio.wait_for(process.wait(), timeout=10.0)
            
            if process.returncode == 0:
                return True, "SSH connectivity verified"
            else:
                stderr = await process.stderr.read()
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                return False, f"SSH connection failed: {error_msg}"
                
        except asyncio.TimeoutError:
            return False, "SSH connectivity check timed out"
        except Exception as e:
            return False, f"SSH connectivity check failed: {str(e)}"

    async def validate_dependencies(self) -> tuple[bool, list[str]]:
        """Validate that required dependencies are available.

        Returns:
            Tuple of (all_available, missing_tools)
        """
        missing_tools = []
        
        # Check SSH availability
        if not await self.validate_ssh_available():
            missing_tools.append("ssh - Install OpenSSH client")
        
        return len(missing_tools) == 0, missing_tools

    async def check_prerequisites(self) -> bool:
        """Check if all prerequisites for SSH adapter are met.

        Returns:
            True if all prerequisites are available, False otherwise
        """
        try:
            all_available, missing_tools = await self.validate_dependencies()
            
            if not all_available:
                logger.warning("SSH adapter prerequisites not met",
                             missing_tools=missing_tools)
                return False
            
            logger.debug("SSH adapter prerequisites check passed")
            return True
            
        except Exception as e:
            logger.error("Error checking SSH adapter prerequisites",
                        error=str(e))
            return False

    # Required abstract methods from PortForwardingAdapter

    async def validate_connection_info(self, connection_info: "ConnectionInfo") -> list[str]:
        """Validate SSH connection configuration.

        Args:
            connection_info: SSH connection information object to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate that this is an SSH connection
        from ...domain.enums import ForwardingTechnology
        if connection_info.technology != ForwardingTechnology.SSH:
            errors.append("Connection info is not for SSH technology")
            return errors

        try:
            # Required fields validation - use object methods
            host = connection_info.get_ssh_host()
            if not host or not host.strip():
                errors.append("SSH host cannot be empty. Provide a hostname like 'example.com' or IP address like '192.168.1.100'")
        except ValueError:
            errors.append("SSH connection requires 'host' field. Example: host: 'example.com' or host: '192.168.1.100'")

        # Port validation
        try:
            port = connection_info.get_ssh_port()
            if not 1 <= port <= 65535:
                errors.append(f"SSH port {port} must be between 1 and 65535 (default SSH port is 22)")
        except (ValueError, TypeError):
            errors.append("SSH port must be a valid integer. Example: port: 22 or port: 2222")

        # Key file validation - Use concise error message
        key_file = connection_info.get_ssh_key_file()
        if key_file:
            key_path = Path(key_file).expanduser()
            if not key_path.exists():
                # Create safe path for display
                from ...domain.exceptions import SSHKeyNotFoundError
                safe_path = SSHKeyNotFoundError._make_safe_path(str(key_path))
                errors.append(f"SSH key file not found: {safe_path}. Check path or generate key: ssh-keygen -t rsa")
            elif not key_path.is_file():
                errors.append(f"SSH key path is not a file: {key_path}")
            else:
                # Check key file permissions (should be 600 or 400)
                try:
                    stat_info = key_path.stat()
                    if stat_info.st_mode & 0o077:
                        errors.append(f"SSH key file has overly permissive permissions. Run: chmod 600 {key_path}")
                except Exception as e:
                    errors.append(f"Cannot check SSH key file permissions: {str(e)}")

        # Authentication validation
        has_key = key_file is not None
        has_password = connection_info.has_ssh_password()
        
        if not has_key and not has_password:
            errors.append("SSH connection requires either 'key_file' or 'password' for authentication")

        # Password authentication warning
        if has_password and not has_key:
            # Check if sshpass is available
            try:
                import shutil
                if not shutil.which('sshpass'):
                    errors.append("Password authentication requires 'sshpass' to be installed. Install with: brew install sshpass (macOS) or apt-get install sshpass (Ubuntu)")
            except Exception:
                pass

        return errors

    def get_adapter_name(self) -> str:
        """Get the name of this adapter.

        Returns:
            Human-readable adapter name
        """
        return "SSH Tunnel"

    def get_required_tools(self) -> list[str]:
        """Get list of required external tools for this adapter.

        Returns:
            List of required tool names
        """
        return ["ssh"]

    async def is_port_forward_running(self, process_id: int) -> bool:
        """Check if a port forward process is still running.

        Args:
            process_id: Process ID to check

        Returns:
            True if process is running, False otherwise
        """
        # Delegate to existing method (renamed for interface compliance)
        return await self.is_process_running(process_id)
