"""Kubectl adapter for port forwarding operations."""

import asyncio
from typing import Any, Optional

import psutil
import structlog

from .base_adapter import PortForwardingAdapter
from ...domain.value_objects.connection_info import ConnectionInfo
from ..logging.service_log_manager import get_service_log_manager

logger = structlog.get_logger()


class KubectlAdapter(PortForwardingAdapter):
    """Adapter for kubectl port-forward operations."""

    def __init__(self) -> None:
        """Initialize the kubectl adapter."""
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
        """Start a kubectl port-forward process with service logging.

        Args:
            service_name: Name of the service for logging
            local_port: Local port to bind to
            remote_port: Remote port to forward to
            connection_info: Kubectl-specific connection details

        Returns:
            Tuple of (process_id, service_id)

        Raises:
            RuntimeError: If kubectl port-forward fails to start
            ValueError: If connection_info is invalid
        """
        # Extract connection details using ConnectionInfo methods
        namespace = connection_info.get_kubectl_namespace()
        resource_type = connection_info.get_kubectl_resource_type()
        resource_name = connection_info.get_kubectl_resource_name()
        context = connection_info.get_kubectl_context()

        # Create service configuration for logging
        service_config = {
            'local_port': local_port,
            'host': resource_name,
            'port': remote_port,
            'type': 'kubectl',
            'namespace': namespace,
            'resource': f"{resource_type}/{resource_name}",
            'context': context
        }

        # Create service log
        try:
            service_id, log_file = self._service_log_manager.create_service_log(
                service_name, service_config
            )
            
            logger.info("service_log_created_for_kubectl",
                       service_name=service_name,
                       service_id=service_id,
                       log_file=str(log_file))
        except Exception as e:
            logger.error("failed_to_create_service_log",
                        service_name=service_name,
                        error=str(e))
            # Fall back to original behavior if logging fails
            return await self.start_port_forward(local_port, remote_port, connection_info), None

        # Build kubectl command
        cmd = [
            'kubectl', 'port-forward',
            f'{resource_type}/{resource_name}',
            f'{local_port}:{remote_port}',
            '--namespace', namespace
        ]

        if context:
            cmd.extend(['--context', context])

        logger.info("Starting kubectl port-forward with logging",
                   command=' '.join(cmd),
                   local_port=local_port,
                   remote_port=remote_port,
                   resource=f"{resource_type}/{resource_name}",
                   namespace=namespace,
                   service_id=service_id,
                   log_file=str(log_file))

        try:
            import subprocess
            import os
            
            # Open log file for writing
            log_file_handle = open(log_file, 'a', encoding='utf-8', buffering=1)  # Line buffered
            
            # Use subprocess.Popen with log file output
            process = subprocess.Popen(
                cmd,
                stdout=log_file_handle,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                stdin=subprocess.DEVNULL,
                start_new_session=True  # Create new session
            )

            logger.info("kubectl subprocess created with logging", 
                       pid=process.pid,
                       service_id=service_id)

            # Wait a moment to ensure it starts successfully
            await asyncio.sleep(2)

            # Check if process is still running using psutil
            try:
                psutil_process = psutil.Process(process.pid)
                if not psutil_process.is_running():
                    log_file_handle.close()
                    logger.error("kubectl process terminated early", 
                               pid=process.pid,
                               service_id=service_id)
                    raise RuntimeError("kubectl port-forward failed to start")
                
                logger.info("kubectl process confirmed running with logging", 
                           pid=process.pid,
                           service_id=service_id,
                           status=psutil_process.status())
                
            except psutil.NoSuchProcess:
                log_file_handle.close()
                logger.error("kubectl process not found after creation", 
                           pid=process.pid,
                           service_id=service_id)
                raise RuntimeError("kubectl port-forward failed to start")

            # Store process and service log mapping
            if process.pid:
                self._active_processes[process.pid] = None  # Store PID but not process object
                self._service_logs[process.pid] = service_id

            # Note: We don't close log_file_handle here as the process needs to write to it
            # It will be closed when the process terminates

            logger.info("kubectl port-forward started successfully with logging",
                       pid=process.pid,
                       service_id=service_id,
                       local_port=local_port,
                       remote_port=remote_port,
                       resource=f"{resource_type}/{resource_name}")

            return process.pid, service_id

        except FileNotFoundError:
            if 'log_file_handle' in locals():
                log_file_handle.close()
            raise RuntimeError("kubectl command not found. Please ensure kubectl is installed and in PATH")
        except Exception as e:
            if 'log_file_handle' in locals():
                log_file_handle.close()
            logger.error("Failed to start kubectl port-forward with logging",
                        error=str(e),
                        service_id=service_id,
                        local_port=local_port,
                        remote_port=remote_port)
            raise RuntimeError(f"Failed to start kubectl port-forward: {e}")

    async def start_port_forward(
        self,
        local_port: int,
        remote_port: int,
        connection_info: ConnectionInfo
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
        # Extract connection details using ConnectionInfo methods
        namespace = connection_info.get_kubectl_namespace()
        resource_type = connection_info.get_kubectl_resource_type()
        resource_name = connection_info.get_kubectl_resource_name()
        context = connection_info.get_kubectl_context()

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
            # Start the process completely detached using subprocess.Popen
            import subprocess
            import os
            
            logger.info("Starting kubectl subprocess", command=cmd)
            
            # Use subprocess.Popen for better control over detachment
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,  # Don't capture output to avoid keeping references
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True  # Create new session
            )

            logger.info("kubectl subprocess created", pid=process.pid)

            # Wait a moment to ensure it starts successfully
            await asyncio.sleep(2)

            # Check if process is still running using psutil
            try:
                import psutil
                psutil_process = psutil.Process(process.pid)
                if not psutil_process.is_running():
                    logger.error("kubectl process terminated early", pid=process.pid)
                    raise RuntimeError("kubectl port-forward failed to start")
                
                logger.info("kubectl process confirmed running", 
                           pid=process.pid,
                           status=psutil_process.status())
                
            except psutil.NoSuchProcess:
                logger.error("kubectl process not found after creation", pid=process.pid)
                raise RuntimeError("kubectl port-forward failed to start")

            # Don't store the subprocess.Popen object as it keeps references
            # Just store the PID for tracking
            if process.pid:
                self._active_processes[process.pid] = None  # Store PID but not process object

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

                except psutil.NoSuchProcess:
                    logger.warning("Process not found", pid=process_id)
                    # Still need to clean up service log tracking
                    if service_id:
                        self._service_logs.pop(process_id, None)
                        self._service_log_manager.remove_service_log(service_id)
                    return

            # Clean up service log tracking
            if service_id:
                self._service_logs.pop(process_id, None)
                self._service_log_manager.remove_service_log(service_id)
                logger.info("service_log_cleaned_up", 
                           pid=process_id,
                           service_id=service_id)

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

    async def validate_kubectl_connectivity(self, connection_info: ConnectionInfo) -> tuple[bool, str]:
        """Pre-flight kubectl connectivity check.

        Args:
            connection_info: Kubectl connection information

        Returns:
            Tuple of (success, message)
        """
        namespace = connection_info.get_kubectl_namespace()
        context = connection_info.get_kubectl_context()
        
        # Build test command
        cmd = ['kubectl', 'get', 'pods', '--namespace', namespace, '--limit=1']
        if context:
            cmd.extend(['--context', context])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await asyncio.wait_for(process.wait(), timeout=10.0)
            
            if process.returncode == 0:
                return True, "kubectl connectivity verified"
            else:
                stderr = await process.stderr.read()
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                return False, f"kubectl connection failed: {error_msg}"
                
        except asyncio.TimeoutError:
            return False, "kubectl connectivity check timed out"
        except Exception as e:
            return False, f"kubectl connectivity check failed: {str(e)}"

    async def validate_resource_exists(self, connection_info: ConnectionInfo) -> tuple[bool, str]:
        """Check if specified resource exists before starting port-forward.

        Args:
            connection_info: Kubectl connection information

        Returns:
            Tuple of (success, message)
        """
        namespace = connection_info.get_kubectl_namespace()
        resource_type = connection_info.get_kubectl_resource_type()
        resource_name = connection_info.get_kubectl_resource_name()
        context = connection_info.get_kubectl_context()
        
        if not resource_name:
            return False, "Resource name is required"
        
        cmd = ['kubectl', 'get', f'{resource_type}/{resource_name}', '--namespace', namespace]
        if context:
            cmd.extend(['--context', context])
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await asyncio.wait_for(process.wait(), timeout=10.0)
            
            if process.returncode == 0:
                return True, f"Resource {resource_type}/{resource_name} found"
            else:
                return False, f"Resource {resource_type}/{resource_name} not found in namespace {namespace}"
        except Exception as e:
            return False, f"Resource validation failed: {str(e)}"

    async def validate_dependencies(self) -> tuple[bool, list[str]]:
        """Validate that required dependencies are available.

        Returns:
            Tuple of (all_available, missing_tools)
        """
        missing_tools = []
        
        # Check kubectl availability
        if not await self.validate_kubectl_available():
            missing_tools.append("kubectl - Install kubectl and ensure it's in PATH")
        
        return len(missing_tools) == 0, missing_tools

    async def check_prerequisites(self) -> bool:
        """Check if all prerequisites for kubectl adapter are met.

        Returns:
            True if all prerequisites are available, False otherwise
        """
        try:
            all_available, missing_tools = await self.validate_dependencies()
            
            if not all_available:
                logger.warning("kubectl adapter prerequisites not met",
                             missing_tools=missing_tools)
                return False
            
            logger.debug("kubectl adapter prerequisites check passed")
            return True
            
        except Exception as e:
            logger.error("Error checking kubectl adapter prerequisites",
                        error=str(e))
            return False

    # Required abstract methods from PortForwardingAdapter

    async def validate_connection_info(self, connection_info: ConnectionInfo) -> list[str]:
        """Validate kubectl connection configuration.

        Args:
            connection_info: Kubectl connection information object to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate that this is a kubectl connection
        from ...domain.enums import ForwardingTechnology
        if connection_info.technology != ForwardingTechnology.KUBECTL:
            errors.append("Connection info is not for kubectl technology")
            return errors

        try:
            # Required fields validation - use object methods
            resource_name = connection_info.get_kubectl_resource_name()
            if not resource_name or not resource_name.strip():
                errors.append("kubectl resource_name cannot be empty. Provide a valid Kubernetes resource name like 'my-service' or 'my-pod'")
        except ValueError:
            errors.append("kubectl connection requires 'resource_name' field. Example: resource_name: 'my-service'")

        # Namespace validation
        try:
            namespace = connection_info.get_kubectl_namespace()
            if not namespace or not namespace.strip():
                errors.append("kubectl namespace cannot be empty if provided. Use a valid namespace like 'default' or 'production'")
        except ValueError:
            # Namespace is optional, so this is fine
            pass

        # Resource type validation
        try:
            resource_type = connection_info.get_kubectl_resource_type()
            valid_types = ["service", "pod", "deployment", "statefulset"]
            if resource_type not in valid_types:
                errors.append(f"kubectl resource_type '{resource_type}' is invalid. Valid options: {', '.join(valid_types)}")
        except ValueError:
            # Resource type has a default, so this shouldn't happen
            pass

        # Context validation (if kubectl is available)
        context = connection_info.get_kubectl_context()
        if context:
            try:
                available_contexts = await self.list_contexts()
                if context not in available_contexts:
                    if available_contexts:
                        errors.append(f"kubectl context '{context}' not found. Available contexts: {', '.join(available_contexts[:5])}")
                    else:
                        errors.append(f"kubectl context '{context}' not found. No contexts available or kubectl not accessible")
            except Exception:
                # If we can't list contexts, just warn
                errors.append(f"Cannot verify kubectl context '{context}' - kubectl may not be available")

        return errors

    def get_adapter_name(self) -> str:
        """Get the name of this adapter.

        Returns:
            Human-readable adapter name
        """
        return "Kubectl Port Forward"

    def get_required_tools(self) -> list[str]:
        """Get list of required external tools for this adapter.

        Returns:
            List of required tool names
        """
        return ["kubectl"]

    async def is_port_forward_running(self, process_id: int) -> bool:
        """Check if a port forward process is still running.

        Args:
            process_id: Process ID to check

        Returns:
            True if process is running, False otherwise
        """
        # Delegate to existing method (renamed for interface compliance)
        return await self.is_process_running(process_id)
