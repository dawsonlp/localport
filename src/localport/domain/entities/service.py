"""Service entity representing a port forwarding service."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4, uuid5, NAMESPACE_DNS
import traceback

import structlog

from ..enums import ForwardingTechnology, ServiceStatus
from ..value_objects.connection_info import ConnectionInfo

logger = structlog.get_logger()


@dataclass
class Service:
    """Core service entity representing a port forwarding service."""

    id: UUID
    name: str
    technology: ForwardingTechnology
    local_port: int
    remote_port: int
    connection_info: ConnectionInfo
    status: ServiceStatus = ServiceStatus.STOPPED
    health_check_config: dict[str, Any] | None = None
    restart_policy: dict[str, Any] | None = None
    tags: list[str] = None
    description: str | None = None

    def __post_init__(self) -> None:
        """Initialize default values after dataclass creation."""
        if self.tags is None:
            self.tags = []
        

    @staticmethod
    def generate_deterministic_id(
        name: str,
        technology: ForwardingTechnology,
        local_port: int,
        remote_port: int,
        connection_info: ConnectionInfo,
    ) -> UUID:
        """Generate deterministic service ID based on configuration.
        
        The ID is stable across configuration reloads and LocalPort restarts,
        but changes when the service configuration changes.
        
        Args:
            name: Service name
            technology: Forwarding technology (kubectl/ssh)
            local_port: Local port number
            remote_port: Remote port number
            connection_info: Connection details
            
        Returns:
            Deterministic UUID based on service configuration
        """
        # Build stable config key from essential service properties
        config_key = f"{name}:{technology.value}:{local_port}:{remote_port}"
        
        # Add connection-specific details
        if technology == ForwardingTechnology.KUBECTL:
            namespace = connection_info.get_kubectl_namespace()
            resource_name = connection_info.get_kubectl_resource_name()
            resource_type = connection_info.get_kubectl_resource_type()
            config_key += f":{namespace}:{resource_name}:{resource_type}"
            
            context = connection_info.get_kubectl_context()
            if context:
                config_key += f":{context}"
        elif technology == ForwardingTechnology.SSH:
            host = connection_info.get_ssh_host()
            port = connection_info.get_ssh_port()
            config_key += f":{host}:{port}"
            
            user = connection_info.get_ssh_user()
            if user:
                config_key += f":{user}"
        
        # Generate deterministic UUID using UUID5 with DNS namespace
        return uuid5(NAMESPACE_DNS, config_key)

    @classmethod
    def create(
        cls,
        name: str,
        technology: ForwardingTechnology,
        local_port: int,
        remote_port: int,
        connection_info: ConnectionInfo,
        **kwargs: Any,
    ) -> "Service":
        """Factory method to create a new service with deterministic ID."""
        service_id = cls.generate_deterministic_id(
            name=name,
            technology=technology,
            local_port=local_port,
            remote_port=remote_port,
            connection_info=connection_info,
        )
        
        return cls(
            id=service_id,
            name=name,
            technology=technology,
            local_port=local_port,
            remote_port=remote_port,
            connection_info=connection_info,
            **kwargs
        )

    def is_healthy(self) -> bool:
        """Check if service is in a healthy state."""
        return self.status == ServiceStatus.RUNNING

    def can_restart(self) -> bool:
        """Check if service can be restarted."""
        return self.status in [ServiceStatus.FAILED, ServiceStatus.STOPPED]

    def update_status(self, status: ServiceStatus) -> None:
        """Update the service status."""
        self.status = status

    def has_tag(self, tag: str) -> bool:
        """Check if service has a specific tag."""
        return tag in self.tags

    def add_tag(self, tag: str) -> None:
        """Add a tag to the service."""
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the service."""
        if tag in self.tags:
            self.tags.remove(tag)
