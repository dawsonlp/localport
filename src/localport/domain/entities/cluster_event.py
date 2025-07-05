"""
Cluster event domain entity.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any


class EventType(Enum):
    """Types of Kubernetes events."""
    NORMAL = "Normal"
    WARNING = "Warning"


@dataclass(frozen=True)
class ClusterEvent:
    """
    Represents a Kubernetes cluster event.
    
    This entity contains event information collected from kubectl get events
    for monitoring cluster activity and diagnosing issues.
    """
    
    name: str
    namespace: str
    context: str
    event_type: EventType
    reason: str
    message: str
    
    # Timestamps
    first_timestamp: Optional[datetime] = None
    last_timestamp: Optional[datetime] = None
    event_time: Optional[datetime] = None
    
    # Source information
    source_component: Optional[str] = None
    source_host: Optional[str] = None
    
    # Involved object
    involved_object_kind: Optional[str] = None
    involved_object_name: Optional[str] = None
    involved_object_namespace: Optional[str] = None
    involved_object_uid: Optional[str] = None
    
    # Event metadata
    count: int = 1
    reporting_controller: Optional[str] = None
    reporting_instance: Optional[str] = None
    
    # Raw data for debugging
    raw_event: Optional[Dict[str, Any]] = None
    
    @property
    def is_warning(self) -> bool:
        """
        Check if this is a warning event.
        
        Returns:
            bool: True if this is a warning event
        """
        return self.event_type == EventType.WARNING
    
    @property
    def is_recent(self, threshold_minutes: int = 30) -> bool:
        """
        Check if this event is recent.
        
        Args:
            threshold_minutes: Minutes to consider as recent (default: 30)
            
        Returns:
            bool: True if the event occurred within the threshold
        """
        if not self.last_timestamp:
            return False
        
        now = datetime.utcnow()
        threshold = now.timestamp() - (threshold_minutes * 60)
        return self.last_timestamp.timestamp() >= threshold
    
    @property
    def qualified_object_name(self) -> str:
        """
        Get the fully qualified name of the involved object.
        
        Returns:
            str: kind/namespace/name format, or just name if no namespace
        """
        parts = []
        if self.involved_object_kind:
            parts.append(self.involved_object_kind)
        if self.involved_object_namespace:
            parts.append(self.involved_object_namespace)
        if self.involved_object_name:
            parts.append(self.involved_object_name)
        return "/".join(parts) if parts else "unknown"
    
    @property
    def summary(self) -> str:
        """
        Get a brief summary of the event.
        
        Returns:
            str: Brief event description
        """
        obj_name = self.qualified_object_name
        if self.count > 1:
            return f"{self.reason} ({self.count}x): {obj_name} - {self.message}"
        return f"{self.reason}: {obj_name} - {self.message}"
    
    def is_related_to_object(self, kind: str, name: str, namespace: Optional[str] = None) -> bool:
        """
        Check if this event is related to a specific object.
        
        Args:
            kind: The kind of object (e.g., "Pod", "Service")
            name: The name of the object
            namespace: The namespace of the object (optional)
            
        Returns:
            bool: True if the event is related to the specified object
        """
        if self.involved_object_kind != kind or self.involved_object_name != name:
            return False
        
        if namespace is not None:
            return self.involved_object_namespace == namespace
        
        return True
    
    def matches_pattern(self, reason_pattern: Optional[str] = None, 
                       message_pattern: Optional[str] = None) -> bool:
        """
        Check if the event matches specific patterns.
        
        Args:
            reason_pattern: Pattern to match in the reason (case-insensitive)
            message_pattern: Pattern to match in the message (case-insensitive)
            
        Returns:
            bool: True if the event matches the patterns
        """
        if reason_pattern and reason_pattern.lower() not in self.reason.lower():
            return False
        
        if message_pattern and message_pattern.lower() not in self.message.lower():
            return False
        
        return True
    
    def with_update(self, **kwargs) -> "ClusterEvent":
        """
        Create a new ClusterEvent instance with updated fields.
        
        Args:
            **kwargs: Fields to update
            
        Returns:
            ClusterEvent: New instance with updated fields
        """
        current_data = {
            'name': self.name,
            'namespace': self.namespace,
            'context': self.context,
            'event_type': self.event_type,
            'reason': self.reason,
            'message': self.message,
            'first_timestamp': self.first_timestamp,
            'last_timestamp': self.last_timestamp,
            'event_time': self.event_time,
            'source_component': self.source_component,
            'source_host': self.source_host,
            'involved_object_kind': self.involved_object_kind,
            'involved_object_name': self.involved_object_name,
            'involved_object_namespace': self.involved_object_namespace,
            'involved_object_uid': self.involved_object_uid,
            'count': self.count,
            'reporting_controller': self.reporting_controller,
            'reporting_instance': self.reporting_instance,
            'raw_event': self.raw_event,
        }
        current_data.update(kwargs)
        return ClusterEvent(**current_data)
