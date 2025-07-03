"""Service entity representing a port forwarding service."""

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class ServiceStatus(Enum):
    """Status of a port forwarding service."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"
    RESTARTING = "restarting"


class ForwardingTechnology(Enum):
    """Technology used for port forwarding."""

    KUBECTL = "kubectl"
    SSH = "ssh"


@dataclass
class Service:
    """Core service entity representing a port forwarding service."""

    id: UUID
    name: str
    technology: ForwardingTechnology
    local_port: int
    remote_port: int
    connection_info: dict[str, Any]
    status: ServiceStatus = ServiceStatus.STOPPED
    health_check_config: dict[str, Any] | None = None
    restart_policy: dict[str, Any] | None = None
    tags: list[str] = None
    description: str | None = None

    def __post_init__(self) -> None:
        """Initialize default values after dataclass creation."""
        if self.tags is None:
            self.tags = []

    @classmethod
    def create(
        cls,
        name: str,
        technology: ForwardingTechnology,
        local_port: int,
        remote_port: int,
        connection_info: dict[str, Any],
        **kwargs: Any,
    ) -> "Service":
        """Factory method to create a new service."""
        return cls(
            id=uuid4(),
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
