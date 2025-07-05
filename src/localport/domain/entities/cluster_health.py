"""
Cluster health domain entity that aggregates cluster state.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict

from .cluster_info import ClusterInfo
from .cluster_event import ClusterEvent
from .resource_status import ResourceStatus


class ClusterHealthStatus(Enum):
    """Overall cluster health status."""
    HEALTHY = "Healthy"
    WARNING = "Warning"
    UNHEALTHY = "Unhealthy"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class ClusterHealth:
    """
    Represents the overall health state of a cluster.
    
    This entity aggregates cluster information, resource status,
    and recent events to provide a comprehensive health assessment.
    """
    
    context: str
    status: ClusterHealthStatus
    last_check_time: datetime
    
    # Core cluster information
    cluster_info: Optional[ClusterInfo] = None
    
    # Resource status summaries
    total_nodes: int = 0
    healthy_nodes: int = 0
    total_pods: int = 0
    healthy_pods: int = 0
    
    # Recent events
    recent_events: List[ClusterEvent] = None
    warning_events_count: int = 0
    
    # Failure information
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    
    # Performance metrics
    check_duration_seconds: Optional[float] = None
    
    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.recent_events is None:
            object.__setattr__(self, 'recent_events', [])
    
    @property
    def is_healthy(self) -> bool:
        """
        Check if the cluster is considered healthy.
        
        Returns:
            bool: True if cluster status is healthy
        """
        return self.status == ClusterHealthStatus.HEALTHY
    
    @property
    def node_health_percentage(self) -> float:
        """
        Calculate the percentage of healthy nodes.
        
        Returns:
            float: Percentage of healthy nodes (0.0 to 100.0)
        """
        if self.total_nodes == 0:
            return 0.0
        return (self.healthy_nodes / self.total_nodes) * 100.0
    
    @property
    def pod_health_percentage(self) -> float:
        """
        Calculate the percentage of healthy pods.
        
        Returns:
            float: Percentage of healthy pods (0.0 to 100.0)
        """
        if self.total_pods == 0:
            return 0.0
        return (self.healthy_pods / self.total_pods) * 100.0
    
    @property
    def has_recent_warnings(self) -> bool:
        """
        Check if there are recent warning events.
        
        Returns:
            bool: True if there are recent warning events
        """
        return self.warning_events_count > 0
    
    @property
    def status_summary(self) -> str:
        """
        Get a human-readable status summary.
        
        Returns:
            str: Brief status description
        """
        if self.status == ClusterHealthStatus.HEALTHY:
            return f"Healthy ({self.healthy_nodes}/{self.total_nodes} nodes, {self.healthy_pods}/{self.total_pods} pods)"
        elif self.status == ClusterHealthStatus.WARNING:
            warnings = f", {self.warning_events_count} warnings" if self.warning_events_count > 0 else ""
            return f"Warning ({self.healthy_nodes}/{self.total_nodes} nodes{warnings})"
        elif self.status == ClusterHealthStatus.UNHEALTHY:
            error_info = f": {self.last_error}" if self.last_error else ""
            return f"Unhealthy{error_info}"
        else:
            return "Unknown"
    
    @property
    def time_since_check(self) -> str:
        """
        Get a human-readable time since last check.
        
        Returns:
            str: Time since last check (e.g., "2 minutes ago")
        """
        now = datetime.utcnow()
        delta = now - self.last_check_time
        
        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())} seconds ago"
        elif delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() / 60)} minutes ago"
        else:
            return f"{int(delta.total_seconds() / 3600)} hours ago"
    
    def get_warning_events(self) -> List[ClusterEvent]:
        """
        Get only the warning events from recent events.
        
        Returns:
            List[ClusterEvent]: List of warning events
        """
        return [event for event in self.recent_events if event.is_warning]
    
    def get_events_for_object(self, kind: str, name: str, namespace: Optional[str] = None) -> List[ClusterEvent]:
        """
        Get events related to a specific object.
        
        Args:
            kind: The kind of object (e.g., "Pod", "Service")
            name: The name of the object
            namespace: The namespace of the object (optional)
            
        Returns:
            List[ClusterEvent]: Events related to the object
        """
        return [
            event for event in self.recent_events 
            if event.is_related_to_object(kind, name, namespace)
        ]
    
    def has_connectivity_issues(self) -> bool:
        """
        Check if there are connectivity issues with the cluster.
        
        Returns:
            bool: True if there are connectivity issues
        """
        if not self.cluster_info:
            return True
        
        return not self.cluster_info.is_reachable or self.consecutive_failures > 0
    
    def should_trigger_service_restart(self, failure_threshold: int = 3) -> bool:
        """
        Determine if cluster health should trigger service restarts.
        
        Args:
            failure_threshold: Number of consecutive failures before triggering restarts
            
        Returns:
            bool: True if service restarts should be triggered
        """
        # Don't restart services if cluster is having issues
        if self.status == ClusterHealthStatus.UNHEALTHY:
            return False
        
        # Don't restart if we have connectivity issues
        if self.has_connectivity_issues():
            return False
        
        # Don't restart if there are too many consecutive failures
        if self.consecutive_failures >= failure_threshold:
            return False
        
        return True
    
    @classmethod
    def create_healthy(cls, context: str, cluster_info: ClusterInfo, 
                      nodes: List[ResourceStatus], pods: List[ResourceStatus],
                      events: List[ClusterEvent], check_duration: Optional[float] = None) -> "ClusterHealth":
        """
        Create a healthy cluster health instance.
        
        Args:
            context: Cluster context name
            cluster_info: Basic cluster information
            nodes: List of node statuses
            pods: List of pod statuses
            events: List of recent events
            check_duration: Time taken for health check
            
        Returns:
            ClusterHealth: New healthy cluster health instance
        """
        healthy_nodes = sum(1 for node in nodes if node.is_healthy)
        healthy_pods = sum(1 for pod in pods if pod.is_healthy)
        warning_events = [event for event in events if event.is_warning]
        
        # Determine status based on health metrics
        if healthy_nodes == len(nodes) and len(warning_events) == 0:
            status = ClusterHealthStatus.HEALTHY
        elif healthy_nodes >= len(nodes) * 0.8:  # 80% of nodes healthy
            status = ClusterHealthStatus.WARNING
        else:
            status = ClusterHealthStatus.UNHEALTHY
        
        return cls(
            context=context,
            status=status,
            last_check_time=datetime.utcnow(),
            cluster_info=cluster_info,
            total_nodes=len(nodes),
            healthy_nodes=healthy_nodes,
            total_pods=len(pods),
            healthy_pods=healthy_pods,
            recent_events=events,
            warning_events_count=len(warning_events),
            consecutive_failures=0,
            check_duration_seconds=check_duration,
        )
    
    @classmethod
    def create_unhealthy(cls, context: str, error: str, 
                        consecutive_failures: int = 1) -> "ClusterHealth":
        """
        Create an unhealthy cluster health instance.
        
        Args:
            context: Cluster context name
            error: Error message describing the issue
            consecutive_failures: Number of consecutive failures
            
        Returns:
            ClusterHealth: New unhealthy cluster health instance
        """
        return cls(
            context=context,
            status=ClusterHealthStatus.UNHEALTHY,
            last_check_time=datetime.utcnow(),
            consecutive_failures=consecutive_failures,
            last_error=error,
        )
    
    def with_update(self, **kwargs) -> "ClusterHealth":
        """
        Create a new ClusterHealth instance with updated fields.
        
        Args:
            **kwargs: Fields to update
            
        Returns:
            ClusterHealth: New instance with updated fields
        """
        current_data = {
            'context': self.context,
            'status': self.status,
            'last_check_time': self.last_check_time,
            'cluster_info': self.cluster_info,
            'total_nodes': self.total_nodes,
            'healthy_nodes': self.healthy_nodes,
            'total_pods': self.total_pods,
            'healthy_pods': self.healthy_pods,
            'recent_events': self.recent_events,
            'warning_events_count': self.warning_events_count,
            'consecutive_failures': self.consecutive_failures,
            'last_error': self.last_error,
            'check_duration_seconds': self.check_duration_seconds,
        }
        current_data.update(kwargs)
        return ClusterHealth(**current_data)
