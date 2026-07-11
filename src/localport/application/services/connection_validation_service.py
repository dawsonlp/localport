"""Connection validation service for validating service configurations."""

import asyncio
import re
import socket
from dataclasses import dataclass, field
from typing import Any

import structlog

from ...domain.repositories.config_repository import ConfigRepository

logger = structlog.get_logger()


@dataclass
class ConnectionValidationResult:
    """Unified result of a full connection validation.
    
    Aggregates SSH connectivity, port availability, and Kubernetes
    resource existence checks into a single result object.
    """
    valid: bool = True
    service_name_errors: list[str] = field(default_factory=list)
    port_errors: list[str] = field(default_factory=list)
    ssh_connectivity_errors: list[str] = field(default_factory=list)
    kubernetes_resource_errors: list[str] = field(default_factory=list)
    configuration_errors: list[str] = field(default_factory=list)

    @property
    def all_errors(self) -> list[str]:
        """Return all errors across all categories."""
        return (
            self.service_name_errors
            + self.port_errors
            + self.ssh_connectivity_errors
            + self.kubernetes_resource_errors
            + self.configuration_errors
        )

    @property
    def error_count(self) -> int:
        return len(self.all_errors)

    @property
    def summary(self) -> str:
        if self.valid:
            return "Connection validation passed"
        parts = []
        if self.service_name_errors:
            parts.append(f"{len(self.service_name_errors)} name error(s)")
        if self.port_errors:
            parts.append(f"{len(self.port_errors)} port error(s)")
        if self.ssh_connectivity_errors:
            parts.append(f"{len(self.ssh_connectivity_errors)} SSH error(s)")
        if self.kubernetes_resource_errors:
            parts.append(f"{len(self.kubernetes_resource_errors)} K8s error(s)")
        if self.configuration_errors:
            parts.append(f"{len(self.configuration_errors)} config error(s)")
        return f"Validation failed: {', '.join(parts)}"


class ConnectionValidationService:
    """Service for validating connection parameters and configuration."""
    
    def __init__(self, config_repository: ConfigRepository):
        """Initialize the validation service.
        
        Args:
            config_repository: Repository for accessing configuration
        """
        self.config_repository = config_repository

    async def validate_service_name(
        self,
        name: str,
        exclude_existing: bool = True
    ) -> list[str]:
        """Validate a service name and check for conflicts.
        
        Args:
            name: Service name to validate
            exclude_existing: Whether to check for existing service conflicts
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Basic name validation
        if not name or not name.strip():
            errors.append("Service name cannot be empty")
            return errors
        
        name = name.strip()
        
        # Length validation
        if len(name) > 100:
            errors.append("Service name cannot exceed 100 characters")
        
        # Character validation - allow alphanumeric, hyphens, underscores, dots
        if not re.match(r'^[a-zA-Z0-9._-]+$', name):
            errors.append("Service name can only contain letters, numbers, dots, hyphens, and underscores")
        
        # Cannot start or end with special characters
        if name.startswith(('.', '-', '_')) or name.endswith(('.', '-', '_')):
            errors.append("Service name cannot start or end with dots, hyphens, or underscores")
        
        # Reserved names
        reserved_names = ['all', 'default', 'system', 'admin', 'root', 'config', 'help']
        if name.lower() in reserved_names:
            errors.append(f"'{name}' is a reserved service name")
        
        # Check for existing service if requested
        if exclude_existing and not errors:  # Only check if name is otherwise valid
            try:
                if await self.config_repository.service_exists(name):
                    # Generate alternative suggestions
                    suggestions = [
                        f"{name}-2",
                        f"{name}-dev",
                        f"{name}-new",
                        f"my-{name}"
                    ]
                    errors.append(f"Service '{name}' already exists. Try: {', '.join(suggestions[:2])}")
            except Exception as e:
                logger.warning("Error checking service existence", name=name, error=str(e))
                # Don't fail validation if we can't check - let it proceed
        
        return errors

    async def validate_port_availability(self, local_port: int) -> list[str]:
        """Validate that a local port is available and valid.
        
        Args:
            local_port: Port number to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Basic port range validation
        if not isinstance(local_port, int) or not (1 <= local_port <= 65535):
            errors.append(f"Port {local_port} must be between 1 and 65535")
            return errors
        
        # Check for well-known ports (warn but don't fail)
        well_known_ports = {
            22: "SSH",
            25: "SMTP", 
            53: "DNS",
            80: "HTTP",
            110: "POP3",
            143: "IMAP",
            443: "HTTPS",
            993: "IMAPS",
            995: "POP3S"
        }
        
        if local_port in well_known_ports:
            service = well_known_ports[local_port]
            errors.append(f"Warning: Port {local_port} is typically used by {service}. Consider using a different port")
        
        # Check if port is already in use by testing binding
        try:
            # Try to bind to the port briefly to check availability
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(('127.0.0.1', local_port))
                logger.debug("Port availability check passed", port=local_port)
            except OSError as e:
                if e.errno == 48:  # Address already in use
                    errors.append(f"Port {local_port} is already in use by another process")
                elif e.errno == 13:  # Permission denied
                    if local_port < 1024:
                        errors.append(f"Port {local_port} requires root privileges. Try a port >= 1024")
                    else:
                        errors.append(f"Permission denied for port {local_port}")
                else:
                    errors.append(f"Cannot bind to port {local_port}: {str(e)}")
            finally:
                sock.close()
                
        except Exception as e:
            logger.warning("Error checking port availability", port=local_port, error=str(e))
            # Don't fail validation if we can't check - just warn
            errors.append(f"Warning: Could not verify port {local_port} availability")
        
        return errors

    async def validate_ssh_host(self, host: str, port: int = 22, timeout: float = 5.0) -> list[str]:
        """Validate SSH host connectivity and format.
        
        Args:
            host: SSH hostname or IP address
            port: SSH port (default 22)
            timeout: Connection timeout in seconds
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Basic host validation
        if not host or not host.strip():
            errors.append("SSH host cannot be empty")
            return errors
        
        host = host.strip()
        
        # Basic format validation
        # Allow hostnames, IP addresses, and special cases like localhost
        if not self._is_valid_hostname_or_ip(host):
            errors.append(f"'{host}' is not a valid hostname or IP address")
            return errors  # Don't proceed with network tests if format is invalid
        
        # Network connectivity test (optional but recommended)
        try:
            # Perform a quick TCP connection test
            logger.debug("Testing SSH host connectivity", host=host, port=port)
            
            # Use asyncio to avoid blocking
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout
                )
                writer.close()
                await writer.wait_closed()
                logger.debug("SSH host connectivity test passed", host=host, port=port)
                
            except asyncio.TimeoutError:
                errors.append(f"Connection to {host}:{port} timed out after {timeout}s")
            except OSError as e:
                if e.errno == 61:  # Connection refused
                    errors.append(f"Connection refused to {host}:{port}. Check if SSH service is running")
                elif e.errno == 8:  # Name resolution failure
                    errors.append(f"Cannot resolve hostname '{host}'. Check if the hostname is correct")
                else:
                    errors.append(f"Cannot connect to {host}:{port}: {str(e)}")
                    
        except Exception as e:
            logger.warning("Error testing SSH host connectivity", host=host, port=port, error=str(e))
            # Don't fail validation for network issues - just warn
            errors.append(f"Warning: Could not verify connectivity to {host}:{port}")
        
        return errors

    async def validate_port_range(self, port: int, port_type: str = "port") -> list[str]:
        """Validate that a port number is in the valid range.
        
        Args:
            port: Port number to validate
            port_type: Type of port for error messages (e.g., "local port", "remote port")
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not isinstance(port, int):
            errors.append(f"{port_type.capitalize()} must be an integer")
            return errors
        
        if not (1 <= port <= 65535):
            errors.append(f"{port_type.capitalize()} {port} must be between 1 and 65535")
        
        return errors

    async def validate_kubernetes_resource_name(self, resource_name: str) -> list[str]:
        """Validate a Kubernetes resource name format.
        
        Args:
            resource_name: Kubernetes resource name to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not resource_name or not resource_name.strip():
            errors.append("Kubernetes resource name cannot be empty")
            return errors
        
        resource_name = resource_name.strip()
        
        # Kubernetes naming rules (simplified)
        if len(resource_name) > 253:
            errors.append("Kubernetes resource name cannot exceed 253 characters")
        
        # Must be lowercase alphanumeric with hyphens and dots
        if not re.match(r'^[a-z0-9.-]+$', resource_name):
            errors.append("Kubernetes resource name must contain only lowercase letters, numbers, hyphens, and dots")
        
        # Cannot start or end with hyphen or dot
        if resource_name.startswith('-') or resource_name.startswith('.') or \
           resource_name.endswith('-') or resource_name.endswith('.'):
            errors.append("Kubernetes resource name cannot start or end with hyphen or dot")
        
        return errors

    async def validate_kubernetes_namespace(self, namespace: str) -> list[str]:
        """Validate a Kubernetes namespace name format.
        
        Args:
            namespace: Kubernetes namespace to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        # Namespaces follow similar rules to resource names
        errors = await self.validate_kubernetes_resource_name(namespace)
        
        # Replace "resource name" with "namespace" in error messages
        errors = [error.replace("resource name", "namespace") for error in errors]
        
        # Additional namespace-specific validation
        if namespace and namespace in ['kube-system', 'kube-public', 'kube-node-lease']:
            errors.append(f"Warning: '{namespace}' is a system namespace. Make sure this is intended")
        
        return errors

    def _is_valid_hostname_or_ip(self, host: str) -> bool:
        """Check if a string is a valid hostname or IP address.
        
        Args:
            host: Host string to validate
            
        Returns:
            True if valid hostname or IP address
        """
        # Try to parse as IP address first
        try:
            socket.inet_pton(socket.AF_INET, host)
            return True
        except socket.error:
            pass
        
        try:
            socket.inet_pton(socket.AF_INET6, host)
            return True
        except socket.error:
            pass
        
        # Validate as hostname
        if len(host) > 253:
            return False
        
        # Remove trailing dot if present
        if host.endswith('.'):
            host = host[:-1]
        
        # Check hostname format
        allowed = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$')
        labels = host.split('.')
        
        if not labels:
            return False
        
        for label in labels:
            if not allowed.match(label):
                return False
        
        return True

    async def validate_connection(
        self,
        service_config: dict[str, Any],
        check_ssh_connectivity: bool = True,
        check_port_availability: bool = True,
        check_k8s_resource: bool = True,
        ssh_adapter: Any = None,
        kubectl_adapter: Any = None,
    ) -> ConnectionValidationResult:
        """Unified connection validation combining all checks.
        
        Provides a single interface to validate SSH connectivity,
        port availability, and Kubernetes resource existence for
        a service configuration.
        
        Args:
            service_config: Service configuration dictionary
            check_ssh_connectivity: Whether to test SSH host reachability
            check_port_availability: Whether to test local port availability
            check_k8s_resource: Whether to verify K8s resource exists
            ssh_adapter: Optional SSHAdapter for SSH connectivity checks
            kubectl_adapter: Optional KubectlAdapter for K8s resource checks
            
        Returns:
            ConnectionValidationResult with categorised errors
        """
        result = ConnectionValidationResult()

        # --- 1. Service name validation ---
        name = service_config.get("name")
        if name:
            name_errors = await self.validate_service_name(name)
            result.service_name_errors.extend(name_errors)
        else:
            result.configuration_errors.append("Service configuration missing 'name' field")

        # --- 2. Required field validation ---
        for required in ("technology", "local_port", "remote_port"):
            if required not in service_config:
                result.configuration_errors.append(
                    f"Service configuration missing '{required}' field"
                )

        technology = service_config.get("technology")
        connection_info = service_config.get("connection", {})

        # --- 3. Port validation + availability ---
        local_port = service_config.get("local_port")
        if local_port is not None:
            port_range_errors = await self.validate_port_range(local_port, "local port")
            result.port_errors.extend(port_range_errors)

            if not port_range_errors and check_port_availability:
                availability_errors = await self.validate_port_availability(local_port)
                result.port_errors.extend(availability_errors)

        remote_port = service_config.get("remote_port")
        if remote_port is not None:
            result.port_errors.extend(
                await self.validate_port_range(remote_port, "remote port")
            )

        # --- 4. SSH connectivity ---
        if technology == "ssh":
            host = connection_info.get("host")
            if not host:
                result.ssh_connectivity_errors.append("SSH connection missing 'host' field")
            else:
                ssh_port = connection_info.get("port", 22)
                if check_ssh_connectivity:
                    # Use the dedicated SSH adapter if available
                    if ssh_adapter is not None:
                        try:
                            adapter_errors = await ssh_adapter.validate_connection_info(connection_info)
                            result.ssh_connectivity_errors.extend(adapter_errors)
                        except Exception as e:
                            result.ssh_connectivity_errors.append(f"SSH validation error: {e}")
                    else:
                        # Fall back to basic TCP connectivity check
                        host_errors = await self.validate_ssh_host(host, ssh_port)
                        result.ssh_connectivity_errors.extend(host_errors)

        # --- 5. Kubernetes resource existence ---
        if technology == "kubectl":
            resource_name = connection_info.get("resource_name")
            if not resource_name:
                result.kubernetes_resource_errors.append(
                    "kubectl connection missing 'resource_name' field"
                )
            else:
                fmt_errors = await self.validate_kubernetes_resource_name(resource_name)
                result.kubernetes_resource_errors.extend(fmt_errors)

                # Verify the resource actually exists in the cluster
                if not fmt_errors and check_k8s_resource and kubectl_adapter is not None:
                    try:
                        namespace = connection_info.get("namespace", "default")
                        exists = await kubectl_adapter.validate_resource_exists(
                            resource_name, namespace
                        )
                        if not exists:
                            result.kubernetes_resource_errors.append(
                                f"Kubernetes resource '{resource_name}' not found "
                                f"in namespace '{namespace}'"
                            )
                    except Exception as e:
                        result.kubernetes_resource_errors.append(
                            f"K8s resource check failed: {e}"
                        )

            namespace = connection_info.get("namespace")
            if namespace:
                ns_errors = await self.validate_kubernetes_namespace(namespace)
                result.kubernetes_resource_errors.extend(ns_errors)

        # --- Determine overall validity ---
        result.valid = result.error_count == 0

        logger.debug(
            "Unified connection validation complete",
            service=name,
            valid=result.valid,
            errors=result.error_count,
        )

        return result

    async def validate_service_configuration(self, service_config: dict[str, Any]) -> list[str]:
        """Validate a complete service configuration.
        
        Args:
            service_config: Service configuration dictionary
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Validate required fields
        if 'name' not in service_config:
            errors.append("Service configuration missing 'name' field")
            return errors  # Can't proceed without name
        
        if 'technology' not in service_config:
            errors.append("Service configuration missing 'technology' field")
        
        if 'local_port' not in service_config:
            errors.append("Service configuration missing 'local_port' field")
        
        if 'remote_port' not in service_config:
            errors.append("Service configuration missing 'remote_port' field")
        
        # Validate service name
        name_errors = await self.validate_service_name(service_config['name'])
        errors.extend(name_errors)
        
        # Validate ports if present
        if 'local_port' in service_config:
            local_port_errors = await self.validate_port_range(
                service_config['local_port'], "local port"
            )
            errors.extend(local_port_errors)
            
            # Also check availability
            if not local_port_errors:  # Only if port format is valid
                availability_errors = await self.validate_port_availability(
                    service_config['local_port']
                )
                errors.extend(availability_errors)
        
        if 'remote_port' in service_config:
            remote_port_errors = await self.validate_port_range(
                service_config['remote_port'], "remote port"
            )
            errors.extend(remote_port_errors)
        
        # Technology-specific validation
        technology = service_config.get('technology')
        connection_info = service_config.get('connection', {})
        
        if technology == 'ssh':
            if 'host' not in connection_info:
                errors.append("SSH connection missing 'host' field")
            else:
                ssh_port = connection_info.get('port', 22)
                ssh_errors = await self.validate_ssh_host(
                    connection_info['host'], ssh_port
                )
                errors.extend(ssh_errors)
        
        elif technology == 'kubectl':
            if 'resource_name' not in connection_info:
                errors.append("kubectl connection missing 'resource_name' field")
            else:
                resource_errors = await self.validate_kubernetes_resource_name(
                    connection_info['resource_name']
                )
                errors.extend(resource_errors)
            
            if 'namespace' in connection_info:
                namespace_errors = await self.validate_kubernetes_namespace(
                    connection_info['namespace']
                )
                errors.extend(namespace_errors)
        
        return errors
