"""Data Transfer Objects for health monitoring."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class HealthCheckResult:
    """Result of a health check operation."""
    
    service_id: UUID
    service_name: str
    check_type: str
    is_healthy: bool
    checked_at: datetime
    response_time: float
    error: str | None = None
    cluster_context: str | None = None
    cluster_healthy: bool | None = None
    skip_restart_due_to_cluster: bool = False

    @classmethod
    def cluster_unhealthy_result(
        cls,
        service_id: UUID,
        service_name: str,
        check_type: str,
        cluster_context: str,
        cluster_error: str
    ) -> "HealthCheckResult":
        """Create a health check result indicating cluster is unhealthy.
        
        Args:
            service_id: Service ID
            service_name: Service name
            check_type: Type of health check
            cluster_context: Cluster context name
            cluster_error: Cluster error description
            
        Returns:
            HealthCheckResult indicating cluster issues
        """
        return cls(
            service_id=service_id,
            service_name=service_name,
            check_type=check_type,
            is_healthy=False,
            checked_at=datetime.now(),
            response_time=0.0,
            error=f"Cluster unhealthy: {cluster_error}",
            cluster_context=cluster_context,
            cluster_healthy=False,
            skip_restart_due_to_cluster=True
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'service_id': str(self.service_id),
            'service_name': self.service_name,
            'check_type': self.check_type,
            'is_healthy': self.is_healthy,
            'checked_at': self.checked_at.isoformat(),
            'response_time': self.response_time,
            'error': self.error
        }


@dataclass
class HealthMetrics:
    """Health metrics for a service over time."""

    service_id: UUID
    service_name: str
    total_checks: int
    successful_checks: int
    failed_checks: int
    average_response_time: float
    last_check_time: datetime | None = None
    current_failure_streak: int = 0
    max_failure_streak: int = 0
    uptime_percentage: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_checks == 0:
            return 0.0
        return (self.successful_checks / self.total_checks) * 100.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'service_id': str(self.service_id),
            'service_name': self.service_name,
            'total_checks': self.total_checks,
            'successful_checks': self.successful_checks,
            'failed_checks': self.failed_checks,
            'success_rate': self.success_rate,
            'average_response_time': self.average_response_time,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'current_failure_streak': self.current_failure_streak,
            'max_failure_streak': self.max_failure_streak,
            'uptime_percentage': self.uptime_percentage
        }


@dataclass
class RestartAttempt:
    """Information about a service restart attempt."""

    service_id: UUID
    service_name: str
    attempt_number: int
    triggered_at: datetime
    trigger_reason: str
    success: bool
    error: str | None = None
    delay_before_attempt: float = 0.0  # in seconds

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'service_id': str(self.service_id),
            'service_name': self.service_name,
            'attempt_number': self.attempt_number,
            'triggered_at': self.triggered_at.isoformat(),
            'trigger_reason': self.trigger_reason,
            'success': self.success,
            'error': self.error,
            'delay_before_attempt': self.delay_before_attempt
        }
