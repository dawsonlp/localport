"""
Resource status domain entity for cluster resources.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class ResourcePhase(Enum):
    """Kubernetes resource phases."""
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ResourceType(Enum):
    """Types of Kubernetes resources we monitor."""
    POD = "Pod"
    SERVICE = "Service"
    DEPLOYMENT = "Deployment"
    NODE = "Node"


@dataclass(frozen=True)
class ResourceCondition:
    """Represents a condition on a Kubernetes resource."""
    
    type: str
    status: str  # True, False, Unknown
    reason: Optional[str] = None
    message: Optional[str] = None
    last_transition_time: Optional[datetime] = None


@dataclass(frozen=True)
class ResourceStatus:
    """
    Represents the status of a Kubernetes resource (pod, service, etc.).
    
    This entity contains resource status information collected from
    kubectl commands for monitoring cluster health.
    """
    
    name: str
    namespace: str
    resource_type: ResourceType
    phase: ResourcePhase
    context: str
    
    # Timestamps
    creation_time: Optional[datetime] = None
    last_check_time: Optional[datetime] = None
    
    # Status details
    ready: bool = False
    restart_count: int = 0
    conditions: List[ResourceCondition] = None
    
    # Resource-specific information
    node_name: Optional[str] = None  # For pods
    pod_ip: Optional[str] = None     # For pods
    host_ip: Optional[str] = None    # For pods
    
    # Error information
    error_message: Optional[str] = None
    
    # Raw data for debugging
    raw_status: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize default values for mutable fields."""
        if self.conditions is None:
            object.__setattr__(self, 'conditions', [])
    
    @property
    def is_healthy(self) -> bool:
        """
        Determine if the resource is considered healthy.
        
        Returns:
            bool: True if resource is in a healthy state
        """
        if self.phase == ResourcePhase.FAILED:
            return False
        
        if self.resource_type == ResourceType.POD:
            return (
                self.phase == ResourcePhase.RUNNING and 
                self.ready and 
                self.restart_count < 5  # Arbitrary threshold
            )
        elif self.resource_type == ResourceType.NODE:
            # Check for Ready condition
            ready_condition = next(
                (c for c in self.conditions if c.type == "Ready"), 
                None
            )
            return ready_condition is not None and ready_condition.status == "True"
        
        # Default for other resource types
        return self.phase in [ResourcePhase.RUNNING, ResourcePhase.SUCCEEDED]
    
    @property
    def status_summary(self) -> str:
        """
        Get a human-readable status summary.
        
        Returns:
            str: Brief status description
        """
        if self.error_message:
            return f"{self.phase.value}: {self.error_message}"
        
        if self.resource_type == ResourceType.POD:
            ready_status = "Ready" if self.ready else "Not Ready"
            if self.restart_count > 0:
                return f"{self.phase.value}, {ready_status} (Restarts: {self.restart_count})"
            return f"{self.phase.value}, {ready_status}"
        
        return self.phase.value
    
    @property
    def qualified_name(self) -> str:
        """
        Get the fully qualified resource name.
        
        Returns:
            str: namespace/name format
        """
        return f"{self.namespace}/{self.name}"
    
    def has_condition(self, condition_type: str, status: str = "True") -> bool:
        """
        Check if the resource has a specific condition.
        
        Args:
            condition_type: The type of condition to check for
            status: The expected status (default: "True")
            
        Returns:
            bool: True if the condition exists with the expected status
        """
        return any(
            c.type == condition_type and c.status == status 
            for c in self.conditions
        )
    
    def get_condition(self, condition_type: str) -> Optional[ResourceCondition]:
        """
        Get a specific condition by type.
        
        Args:
            condition_type: The type of condition to retrieve
            
        Returns:
            ResourceCondition or None: The condition if found
        """
        return next(
            (c for c in self.conditions if c.type == condition_type), 
            None
        )
    
    def with_update(self, **kwargs) -> "ResourceStatus":
        """
        Create a new ResourceStatus instance with updated fields.
        
        Args:
            **kwargs: Fields to update
            
        Returns:
            ResourceStatus: New instance with updated fields
        """
        current_data = {
            'name': self.name,
            'namespace': self.namespace,
            'resource_type': self.resource_type,
            'phase': self.phase,
            'context': self.context,
            'creation_time': self.creation_time,
            'last_check_time': self.last_check_time,
            'ready': self.ready,
            'restart_count': self.restart_count,
            'conditions': self.conditions,
            'node_name': self.node_name,
            'pod_ip': self.pod_ip,
            'host_ip': self.host_ip,
            'error_message': self.error_message,
            'raw_status': self.raw_status,
        }
        current_data.update(kwargs)
        return ResourceStatus(**current_data)
