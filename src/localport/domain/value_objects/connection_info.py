"""Connection info value object for representing connection details."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..enums import ForwardingTechnology
from ..exceptions import SSHKeyNotFoundError, ConfigurationValidationError


@dataclass(frozen=True)
class ConnectionInfo:
    """Value object representing connection information for port forwarding."""

    technology: ForwardingTechnology
    config: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate connection info after creation."""
        if not isinstance(self.config, dict):
            raise ValueError("Config must be a dictionary")

        # Validate based on technology
        if self.technology == ForwardingTechnology.KUBECTL:
            self._validate_kubectl_config()
        elif self.technology == ForwardingTechnology.SSH:
            self._validate_ssh_config()

    def _validate_kubectl_config(self) -> None:
        """Validate kubectl-specific configuration."""
        required_fields = ["resource_name"]
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"kubectl connection missing required field '{field}'. Example: resource_name: 'my-service'")

        # Validate resource_name is not empty
        if not self.config["resource_name"].strip():
            raise ValueError("kubectl resource_name cannot be empty. Provide a valid Kubernetes resource name like 'my-service' or 'my-pod'")

        # Validate optional fields
        if "namespace" in self.config and not self.config["namespace"].strip():
            raise ValueError("kubectl namespace cannot be empty if provided. Use a valid namespace like 'default' or 'production', or remove the field")

        if "resource_type" in self.config:
            valid_types = ["service", "pod", "deployment"]
            if self.config["resource_type"] not in valid_types:
                raise ValueError(f"kubectl resource_type '{self.config['resource_type']}' is invalid. Valid options: {', '.join(valid_types)}")

    def _validate_ssh_config(self) -> None:
        """Validate SSH-specific configuration."""
        required_fields = ["host"]
        for field in required_fields:
            if field not in self.config:
                raise ValueError(f"SSH connection missing required field '{field}'. Example: host: 'example.com' or host: '192.168.1.100'")

        # Validate host is not empty
        if not self.config["host"].strip():
            raise ValueError("SSH host cannot be empty. Provide a hostname like 'example.com' or IP address like '192.168.1.100'")

        # Validate port if provided
        if "port" in self.config:
            try:
                port = int(self.config["port"])
                if not 1 <= port <= 65535:
                    raise ValueError(f"SSH port {port} is invalid. Use a port between 1 and 65535 (default SSH port is 22)")
            except (ValueError, TypeError):
                raise ValueError(f"SSH port '{self.config['port']}' must be a valid integer. Example: port: 22 or port: 2222")

        # Validate key_file path if provided
        if "key_file" in self.config and self.config["key_file"]:
            key_path = Path(self.config["key_file"]).expanduser()
            if not key_path.exists():
                raise SSHKeyNotFoundError(
                    key_path=str(key_path),
                    service_name=None,  # Will be populated by higher layers
                    config_source=None  # Will be populated by higher layers
                )

        # Validate remote_host if provided
        if "remote_host" in self.config and self.config["remote_host"]:
            if not self.config["remote_host"].strip():
                raise ValueError("SSH remote_host cannot be empty if provided. Use a hostname like 'example.com' or remove the field")

    @classmethod
    def kubectl(
        cls,
        resource_name: str,
        namespace: str = "default",
        resource_type: str = "service",
        context: str | None = None
    ) -> "ConnectionInfo":
        """Create kubectl connection info.

        Args:
            resource_name: Name of the Kubernetes resource
            namespace: Kubernetes namespace
            resource_type: Type of resource (service, pod, deployment)
            context: Kubernetes context to use

        Returns:
            ConnectionInfo instance for kubectl
        """
        config = {
            "resource_name": resource_name,
            "namespace": namespace,
            "resource_type": resource_type,
        }

        if context:
            config["context"] = context

        return cls(ForwardingTechnology.KUBECTL, config)

    @classmethod
    def ssh(
        cls,
        host: str,
        user: str | None = None,
        port: int = 22,
        key_file: str | Path | None = None,
        password: str | None = None,
        **kwargs: Any
    ) -> "ConnectionInfo":
        """Create SSH connection info.

        Args:
            host: SSH host to connect to
            user: SSH username
            port: SSH port (default 22)
            key_file: Path to SSH private key file
            password: SSH password (not recommended)
            **kwargs: Additional SSH options

        Returns:
            ConnectionInfo instance for SSH
        """
        config = {
            "host": host,
            "port": port,
        }

        if user:
            config["user"] = user

        if key_file:
            config["key_file"] = str(Path(key_file).expanduser())

        if password:
            config["password"] = password

        # Add any additional SSH options
        config.update(kwargs)

        return cls(ForwardingTechnology.SSH, config)

    def get_kubectl_resource_name(self) -> str:
        """Get the Kubernetes resource name.

        Returns:
            Resource name for kubectl connections

        Raises:
            ValueError: If not a kubectl connection
        """
        if self.technology != ForwardingTechnology.KUBECTL:
            raise ValueError("Not a kubectl connection")
        return self.config["resource_name"]

    def get_kubectl_namespace(self) -> str:
        """Get the Kubernetes namespace.

        Returns:
            Namespace for kubectl connections

        Raises:
            ValueError: If not a kubectl connection
        """
        if self.technology != ForwardingTechnology.KUBECTL:
            raise ValueError("Not a kubectl connection")
        return self.config.get("namespace", "default")

    def get_kubectl_resource_type(self) -> str:
        """Get the Kubernetes resource type.

        Returns:
            Resource type for kubectl connections

        Raises:
            ValueError: If not a kubectl connection
        """
        if self.technology != ForwardingTechnology.KUBECTL:
            raise ValueError("Not a kubectl connection")
        return self.config.get("resource_type", "service")

    def get_kubectl_context(self) -> str | None:
        """Get the Kubernetes context.

        Returns:
            Context for kubectl connections, None if not specified

        Raises:
            ValueError: If not a kubectl connection
        """
        if self.technology != ForwardingTechnology.KUBECTL:
            raise ValueError("Not a kubectl connection")
        return self.config.get("context")

    def get_ssh_host(self) -> str:
        """Get the SSH host.

        Returns:
            Host for SSH connections

        Raises:
            ValueError: If not an SSH connection
        """
        if self.technology != ForwardingTechnology.SSH:
            raise ValueError("Not an SSH connection")
        return self.config["host"]

    def get_ssh_user(self) -> str | None:
        """Get the SSH user.

        Returns:
            User for SSH connections, None if not specified

        Raises:
            ValueError: If not an SSH connection
        """
        if self.technology != ForwardingTechnology.SSH:
            raise ValueError("Not an SSH connection")
        return self.config.get("user")

    def get_ssh_port(self) -> int:
        """Get the SSH port.

        Returns:
            Port for SSH connections

        Raises:
            ValueError: If not an SSH connection
        """
        if self.technology != ForwardingTechnology.SSH:
            raise ValueError("Not an SSH connection")
        return self.config.get("port", 22)

    def get_ssh_key_file(self) -> str | None:
        """Get the SSH key file path.

        Returns:
            Key file path for SSH connections, None if not specified

        Raises:
            ValueError: If not an SSH connection
        """
        if self.technology != ForwardingTechnology.SSH:
            raise ValueError("Not an SSH connection")
        return self.config.get("key_file")

    def has_ssh_password(self) -> bool:
        """Check if SSH connection has a password.

        Returns:
            True if password is configured

        Raises:
            ValueError: If not an SSH connection
        """
        if self.technology != ForwardingTechnology.SSH:
            raise ValueError("Not an SSH connection")
        return "password" in self.config and self.config["password"] is not None

    def get_ssh_remote_host(self) -> str:
        """Get the SSH remote host for tunneling.
        
        Returns:
            Remote host for SSH tunnel destination, defaults to 'localhost'
            
        Raises:
            ValueError: If not an SSH connection
        """
        if self.technology != ForwardingTechnology.SSH:
            raise ValueError("Not an SSH connection")
        return self.config.get("remote_host", "localhost")

    def validate_against_discovered_resource(self, discovered_resource) -> list[str]:
        """Validate connection info against a discovered Kubernetes resource.
        
        Args:
            discovered_resource: KubernetesResource instance from discovery
            
        Returns:
            List of validation warnings/errors (empty if valid)
            
        Raises:
            ValueError: If not a kubectl connection or resource is incompatible
        """
        if self.technology != ForwardingTechnology.KUBECTL:
            raise ValueError("Can only validate kubectl connections against discovered resources")
        
        from .discovery import KubernetesResource  # Import here to avoid circular imports
        if not isinstance(discovered_resource, KubernetesResource):
            raise ValueError("discovered_resource must be a KubernetesResource instance")
        
        warnings = []
        
        # Validate resource name matches
        if self.get_kubectl_resource_name() != discovered_resource.name:
            warnings.append(f"Resource name mismatch: expected '{discovered_resource.name}', got '{self.get_kubectl_resource_name()}'")
        
        # Validate namespace matches
        if self.get_kubectl_namespace() != discovered_resource.namespace:
            warnings.append(f"Namespace mismatch: expected '{discovered_resource.namespace}', got '{self.get_kubectl_namespace()}'")
        
        # Validate resource type matches
        if self.get_kubectl_resource_type() != discovered_resource.resource_type:
            warnings.append(f"Resource type mismatch: expected '{discovered_resource.resource_type}', got '{self.get_kubectl_resource_type()}'")
        
        # Check if resource has any ports
        if not discovered_resource.has_ports:
            warnings.append(f"Resource '{discovered_resource.name}' has no exposed ports")
        
        return warnings

    def set_discovered_namespace(self, namespace: str) -> "ConnectionInfo":
        """Create a new ConnectionInfo with the discovered namespace set.
        
        Args:
            namespace: Namespace discovered from Kubernetes resource
            
        Returns:
            New ConnectionInfo instance with updated namespace
            
        Raises:
            ValueError: If not a kubectl connection
        """
        if self.technology != ForwardingTechnology.KUBECTL:
            raise ValueError("Can only set namespace for kubectl connections")
        
        # Create new config dictionary with updated namespace
        new_config = dict(self.config)
        new_config["namespace"] = namespace
        
        # Return new instance (since this is a frozen dataclass)
        return ConnectionInfo(self.technology, new_config)

    def update_from_discovered_resource(self, discovered_resource) -> "ConnectionInfo":
        """Create a new ConnectionInfo updated with information from discovered resource.
        
        Args:
            discovered_resource: KubernetesResource instance from discovery
            
        Returns:
            New ConnectionInfo instance with updated information
            
        Raises:
            ValueError: If not a kubectl connection or resource is incompatible
        """
        if self.technology != ForwardingTechnology.KUBECTL:
            raise ValueError("Can only update kubectl connections from discovered resources")
        
        from .discovery import KubernetesResource  # Import here to avoid circular imports
        if not isinstance(discovered_resource, KubernetesResource):
            raise ValueError("discovered_resource must be a KubernetesResource instance")
        
        # Create new config dictionary with discovered information
        new_config = dict(self.config)
        new_config["namespace"] = discovered_resource.namespace
        new_config["resource_type"] = discovered_resource.resource_type
        
        # Ensure resource name matches what was discovered
        new_config["resource_name"] = discovered_resource.name
        
        # Return new instance (since this is a frozen dataclass)
        return ConnectionInfo(self.technology, new_config)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary representation of connection info
        """
        return {
            "technology": self.technology.value,
            "config": dict(self.config)
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConnectionInfo":
        """Create ConnectionInfo from dictionary.

        Args:
            data: Dictionary containing technology and config

        Returns:
            ConnectionInfo instance

        Raises:
            ValueError: If data is invalid
        """
        if "technology" not in data:
            raise ValueError("Missing 'technology' field")

        if "config" not in data:
            raise ValueError("Missing 'config' field")

        try:
            technology = ForwardingTechnology(data["technology"])
        except ValueError:
            raise ValueError(f"Invalid technology: {data['technology']}")

        return cls(technology, data["config"])
