"""Data Transfer Objects for service operations."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ...domain.entities.service import ForwardingTechnology, ServiceStatus


@dataclass
class ServiceStartResult:
    """Result of starting a service."""

    service_name: str
    success: bool
    process_id: int | None = None
    error: str | None = None
    started_at: datetime | None = None

    @classmethod
    def success_result(
        cls,
        service_name: str,
        process_id: int,
        started_at: datetime | None = None
    ) -> "ServiceStartResult":
        """Create a successful start result."""
        return cls(
            service_name=service_name,
            success=True,
            process_id=process_id,
            started_at=started_at or datetime.now()
        )

    @classmethod
    def failure_result(cls, service_name: str, error: str) -> "ServiceStartResult":
        """Create a failed start result."""
        return cls(
            service_name=service_name,
            success=False,
            error=error
        )


@dataclass
class ServiceStopResult:
    """Result of stopping a service."""

    service_name: str
    success: bool
    error: str | None = None
    stopped_at: datetime | None = None

    @classmethod
    def success_result(
        cls,
        service_name: str,
        stopped_at: datetime | None = None
    ) -> "ServiceStopResult":
        """Create a successful stop result."""
        return cls(
            service_name=service_name,
            success=True,
            stopped_at=stopped_at or datetime.now()
        )

    @classmethod
    def failure_result(cls, service_name: str, error: str) -> "ServiceStopResult":
        """Create a failed stop result."""
        return cls(
            service_name=service_name,
            success=False,
            error=error
        )


@dataclass
class ServiceStatusInfo:
    """Service status information."""

    id: UUID
    name: str
    technology: ForwardingTechnology
    local_port: int
    remote_port: int
    status: ServiceStatus
    process_id: int | None = None
    started_at: datetime | None = None
    last_health_check: datetime | None = None
    restart_count: int = 0
    tags: list[str] = None
    description: str | None = None
    uptime_seconds: float | None = None
    is_healthy: bool = False

    def __post_init__(self) -> None:
        """Initialize default values after dataclass creation."""
        if self.tags is None:
            self.tags = []


@dataclass
class ServiceSummary:
    """Summary of all services."""

    total_services: int
    running_services: int
    stopped_services: int
    failed_services: int
    healthy_services: int
    unhealthy_services: int
    services: list[ServiceStatusInfo]

    @property
    def success_rate(self) -> float:
        """Get the success rate of running services."""
        if self.total_services == 0:
            return 0.0
        return (self.running_services / self.total_services) * 100

    @property
    def health_rate(self) -> float:
        """Get the health rate of services."""
        if self.total_services == 0:
            return 0.0
        return (self.healthy_services / self.total_services) * 100


@dataclass
class DaemonStatusInfo:
    """Daemon status information."""

    is_running: bool
    pid: int | None = None
    started_at: datetime | None = None
    uptime_seconds: float | None = None
    managed_services: int = 0
    active_forwards: int = 0
    health_checks_enabled: bool = False
    last_health_check: datetime | None = None

    @property
    def uptime_formatted(self) -> str:
        """Get formatted uptime string."""
        if not self.uptime_seconds:
            return "N/A"

        hours, remainder = divmod(int(self.uptime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"


@dataclass
class BulkOperationResult:
    """Result of a bulk operation on multiple services."""

    operation: str
    total_services: int
    successful_services: list[str]
    failed_services: list[str]
    errors: dict[str, str]

    @property
    def success_count(self) -> int:
        """Number of successful operations."""
        return len(self.successful_services)

    @property
    def failure_count(self) -> int:
        """Number of failed operations."""
        return len(self.failed_services)

    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        if self.total_services == 0:
            return 0.0
        return (self.success_count / self.total_services) * 100

    @property
    def is_complete_success(self) -> bool:
        """Check if all operations succeeded."""
        return self.failure_count == 0

    @property
    def is_complete_failure(self) -> bool:
        """Check if all operations failed."""
        return self.success_count == 0


@dataclass
class DaemonStatusResult:
    """Result of daemon status check."""
    running: bool
    pid: int | None = None
    uptime_seconds: float | None = None
    active_services: int = 0

    @property
    def uptime_formatted(self) -> str:
        """Get formatted uptime string."""
        if not self.uptime_seconds:
            return "N/A"

        hours, remainder = divmod(int(self.uptime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"


@dataclass
class DaemonOperationResult:
    """Result of daemon operation."""
    command: str
    success: bool
    pid: int | None = None
    message: str | None = None
    error: str | None = None
    status: DaemonStatusResult | None = None

    @classmethod
    def success_result(
        cls,
        command: str,
        message: str,
        pid: int | None = None
    ) -> "DaemonOperationResult":
        """Create a successful operation result."""
        return cls(
            command=command,
            success=True,
            message=message,
            pid=pid
        )

    @classmethod
    def failure_result(cls, command: str, error: str) -> "DaemonOperationResult":
        """Create a failed operation result."""
        return cls(
            command=command,
            success=False,
            error=error
        )
