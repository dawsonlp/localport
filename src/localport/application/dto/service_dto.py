"""Data Transfer Objects for service operations."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID

from ...domain.entities.service import ServiceStatus, ForwardingTechnology


@dataclass
class ServiceStartResult:
    """Result of starting a service."""
    
    service_name: str
    success: bool
    process_id: Optional[int] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    
    @classmethod
    def success_result(
        cls, 
        service_name: str, 
        process_id: int,
        started_at: Optional[datetime] = None
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
    error: Optional[str] = None
    stopped_at: Optional[datetime] = None
    
    @classmethod
    def success_result(
        cls, 
        service_name: str,
        stopped_at: Optional[datetime] = None
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
    process_id: Optional[int] = None
    started_at: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    restart_count: int = 0
    tags: List[str] = None
    description: Optional[str] = None
    uptime_seconds: Optional[float] = None
    is_healthy: bool = False
    
    def __post_init__(self) -> None:
        """Initialize default values after dataclass creation."""
        if self.tags is None:
            self.tags = []


@dataclass
class HealthCheckInfo:
    """Health check information."""
    
    service_name: str
    check_type: str
    status: str
    last_check: Optional[datetime] = None
    last_success: Optional[datetime] = None
    consecutive_failures: int = 0
    failure_threshold: int = 3
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    
    @property
    def is_healthy(self) -> bool:
        """Check if the health check is currently healthy."""
        return self.status == "healthy"
    
    @property
    def failure_rate(self) -> float:
        """Get the current failure rate as a percentage."""
        if self.failure_threshold == 0:
            return 0.0
        return (self.consecutive_failures / self.failure_threshold) * 100


@dataclass
class ServiceSummary:
    """Summary of all services."""
    
    total_services: int
    running_services: int
    stopped_services: int
    failed_services: int
    healthy_services: int
    unhealthy_services: int
    services: List[ServiceStatusInfo]
    
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
    pid: Optional[int] = None
    started_at: Optional[datetime] = None
    uptime_seconds: Optional[float] = None
    managed_services: int = 0
    active_forwards: int = 0
    health_checks_enabled: bool = False
    last_health_check: Optional[datetime] = None
    
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
class ServiceMetrics:
    """Service performance metrics."""
    
    service_name: str
    total_starts: int = 0
    total_stops: int = 0
    total_restarts: int = 0
    total_failures: int = 0
    average_startup_time_ms: Optional[float] = None
    average_response_time_ms: Optional[float] = None
    uptime_percentage: float = 0.0
    last_failure: Optional[datetime] = None
    last_restart: Optional[datetime] = None
    
    @property
    def reliability_score(self) -> float:
        """Calculate a reliability score (0-100)."""
        if self.total_starts == 0:
            return 0.0
        
        failure_rate = self.total_failures / self.total_starts
        reliability = max(0.0, 1.0 - failure_rate) * 100
        
        # Factor in uptime percentage
        return (reliability + self.uptime_percentage) / 2


@dataclass
class BulkOperationResult:
    """Result of a bulk operation on multiple services."""
    
    operation: str
    total_services: int
    successful_services: List[str]
    failed_services: List[str]
    errors: Dict[str, str]
    
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
class ConfigValidationResult:
    """Result of configuration validation."""
    
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    services_count: int = 0
    
    @property
    def has_errors(self) -> bool:
        """Check if there are validation errors."""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if there are validation warnings."""
        return len(self.warnings) > 0
    
    def add_error(self, error: str) -> None:
        """Add a validation error."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a validation warning."""
        self.warnings.append(warning)


@dataclass
class ServiceMonitorResult:
    """Result of service monitoring operation."""
    service_name: str
    is_healthy: bool
    last_check: datetime
    failure_count: int
    restart_attempted: bool = False
    restart_success: bool = False
    error: Optional[str] = None


@dataclass
class DaemonStatusResult:
    """Result of daemon status check."""
    running: bool
    pid: Optional[int] = None
    uptime_seconds: Optional[float] = None
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
    pid: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None
    status: Optional[DaemonStatusResult] = None
    
    @classmethod
    def success_result(
        cls, 
        command: str, 
        message: str,
        pid: Optional[int] = None
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
