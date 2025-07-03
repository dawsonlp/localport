"""Health check entity representing health monitoring configuration and state."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID


class HealthCheckType(Enum):
    """Type of health check to perform."""

    TCP = "tcp"
    HTTP = "http"
    KAFKA = "kafka"
    POSTGRES = "postgres"


class HealthCheckStatus(Enum):
    """Status of a health check."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    ERROR = "error"


@dataclass
class HealthCheckResult:
    """Result of a health check execution."""

    status: HealthCheckStatus
    timestamp: datetime
    message: str | None = None
    error: str | None = None
    response_time_ms: float | None = None

    @classmethod
    def healthy(
        cls,
        message: str | None = None,
        response_time_ms: float | None = None
    ) -> "HealthCheckResult":
        """Create a healthy result."""
        return cls(
            status=HealthCheckStatus.HEALTHY,
            timestamp=datetime.now(),
            message=message,
            response_time_ms=response_time_ms
        )

    @classmethod
    def unhealthy(
        cls,
        message: str | None = None,
        error: str | None = None
    ) -> "HealthCheckResult":
        """Create an unhealthy result."""
        return cls(
            status=HealthCheckStatus.UNHEALTHY,
            timestamp=datetime.now(),
            message=message,
            error=error
        )

    @classmethod
    def error(cls, error: str) -> "HealthCheckResult":
        """Create an error result."""
        return cls(
            status=HealthCheckStatus.ERROR,
            timestamp=datetime.now(),
            error=error
        )


@dataclass
class HealthCheck:
    """Health check configuration and state for a service."""

    service_id: UUID
    check_type: HealthCheckType
    config: dict[str, Any]
    interval_seconds: int = 30
    timeout_seconds: float = 5.0
    failure_threshold: int = 3
    consecutive_failures: int = 0
    last_check: HealthCheckResult | None = None
    last_success: datetime | None = None

    def is_healthy(self) -> bool:
        """Check if the service is currently healthy."""
        if not self.last_check:
            return False
        return self.last_check.status == HealthCheckStatus.HEALTHY

    def should_trigger_restart(self) -> bool:
        """Check if consecutive failures exceed threshold."""
        return self.consecutive_failures >= self.failure_threshold

    def record_success(self, result: HealthCheckResult) -> None:
        """Record a successful health check."""
        self.last_check = result
        self.last_success = result.timestamp
        self.consecutive_failures = 0

    def record_failure(self, result: HealthCheckResult) -> None:
        """Record a failed health check."""
        self.last_check = result
        self.consecutive_failures += 1

    def reset_failure_count(self) -> None:
        """Reset the consecutive failure count."""
        self.consecutive_failures = 0

    def get_failure_rate(self) -> float:
        """Get the current failure rate as a percentage."""
        if self.failure_threshold == 0:
            return 0.0
        return (self.consecutive_failures / self.failure_threshold) * 100
