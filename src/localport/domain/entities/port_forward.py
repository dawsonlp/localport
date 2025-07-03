"""Port forward entity representing an active port forwarding process."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class PortForward:
    """Represents an active port forwarding process."""

    service_id: UUID
    process_id: int | None
    local_port: int
    remote_port: int
    started_at: datetime
    last_health_check: datetime | None = None
    restart_count: int = 0

    def is_process_alive(self) -> bool:
        """Check if the underlying process is still alive."""
        if not self.process_id:
            return False

        try:
            import psutil
            return psutil.pid_exists(self.process_id)
        except Exception:
            return False

    def increment_restart_count(self) -> None:
        """Increment the restart counter."""
        self.restart_count += 1

    def update_health_check_time(self, check_time: datetime | None = None) -> None:
        """Update the last health check time."""
        self.last_health_check = check_time or datetime.now()

    def get_uptime_seconds(self) -> float:
        """Get the uptime of the port forward in seconds."""
        return (datetime.now() - self.started_at).total_seconds()

    def should_restart(self, max_restarts: int = 5) -> bool:
        """Check if the port forward should be restarted based on restart count."""
        return self.restart_count < max_restarts
