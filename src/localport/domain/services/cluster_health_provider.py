"""
Cluster health provider domain service interface.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, List

from ..entities.cluster_info import ClusterInfo
from ..entities.cluster_event import ClusterEvent
from ..entities.cluster_health import ClusterHealth
from ..entities.resource_status import ResourceStatus


class ClusterHealthProvider(ABC):
    """
    Abstract interface for cluster health monitoring and querying.
    
    This interface defines the contract for cluster health providers,
    allowing different implementations (e.g., kubectl-based, API-based)
    while maintaining a consistent interface for the application layer.
    """
    
    @abstractmethod
    async def is_cluster_healthy(self, context: str) -> bool:
        """
        Check if a cluster is considered healthy.
        
        Args:
            context: The cluster context name
            
        Returns:
            bool: True if the cluster is healthy
            
        Raises:
            ClusterNotFoundError: If the cluster context is not found
            ClusterConnectionError: If unable to connect to the cluster
        """
        pass
    
    @abstractmethod
    async def get_cluster_info(self, context: str) -> Optional[ClusterInfo]:
        """
        Get basic cluster information.
        
        Args:
            context: The cluster context name
            
        Returns:
            ClusterInfo or None: Cluster information if available
            
        Raises:
            ClusterNotFoundError: If the cluster context is not found
        """
        pass
    
    @abstractmethod
    async def get_cluster_health(self, context: str) -> Optional[ClusterHealth]:
        """
        Get comprehensive cluster health information.
        
        Args:
            context: The cluster context name
            
        Returns:
            ClusterHealth or None: Complete cluster health state if available
            
        Raises:
            ClusterNotFoundError: If the cluster context is not found
        """
        pass
    
    @abstractmethod
    async def get_resource_status(self, context: str, namespace: str, 
                                 resource_name: str, resource_type: str) -> Optional[ResourceStatus]:
        """
        Get the status of a specific resource.
        
        Args:
            context: The cluster context name
            namespace: The resource namespace
            resource_name: The name of the resource
            resource_type: The type of resource (Pod, Service, etc.)
            
        Returns:
            ResourceStatus or None: Resource status if found
            
        Raises:
            ClusterNotFoundError: If the cluster context is not found
            ClusterConnectionError: If unable to connect to the cluster
        """
        pass
    
    @abstractmethod
    async def get_cluster_events(self, context: str, since: Optional[datetime] = None,
                                limit: int = 50) -> List[ClusterEvent]:
        """
        Get recent cluster events.
        
        Args:
            context: The cluster context name
            since: Only return events after this timestamp (optional)
            limit: Maximum number of events to return (default: 50)
            
        Returns:
            List[ClusterEvent]: List of cluster events
            
        Raises:
            ClusterNotFoundError: If the cluster context is not found
            ClusterConnectionError: If unable to connect to the cluster
        """
        pass
    
    @abstractmethod
    async def get_last_check_time(self, context: str) -> Optional[datetime]:
        """
        Get the timestamp of the last health check for a cluster.
        
        Args:
            context: The cluster context name
            
        Returns:
            datetime or None: Last check time if available
        """
        pass
    
    @abstractmethod
    async def get_monitored_contexts(self) -> List[str]:
        """
        Get the list of cluster contexts currently being monitored.
        
        Returns:
            List[str]: List of cluster context names
        """
        pass
    
    @abstractmethod
    async def start_monitoring(self, context: str) -> None:
        """
        Start monitoring a cluster context.
        
        Args:
            context: The cluster context name to start monitoring
            
        Raises:
            ClusterNotFoundError: If the cluster context is not found
            ClusterConnectionError: If unable to connect to the cluster
        """
        pass
    
    @abstractmethod
    async def stop_monitoring(self, context: str) -> None:
        """
        Stop monitoring a cluster context.
        
        Args:
            context: The cluster context name to stop monitoring
        """
        pass
    
    @abstractmethod
    async def refresh_cluster_health(self, context: str) -> Optional[ClusterHealth]:
        """
        Force a refresh of cluster health information.
        
        Args:
            context: The cluster context name
            
        Returns:
            ClusterHealth or None: Updated cluster health state
            
        Raises:
            ClusterNotFoundError: If the cluster context is not found
            ClusterConnectionError: If unable to connect to the cluster
        """
        pass


class ClusterNotFoundError(Exception):
    """Raised when a cluster context is not found."""
    
    def __init__(self, context: str):
        self.context = context
        super().__init__(f"Cluster context '{context}' not found")


class ClusterConnectionError(Exception):
    """Raised when unable to connect to a cluster."""
    
    def __init__(self, context: str, reason: str):
        self.context = context
        self.reason = reason
        super().__init__(f"Unable to connect to cluster '{context}': {reason}")


class ClusterHealthProviderError(Exception):
    """Base exception for cluster health provider errors."""
    
    def __init__(self, context: str, message: str):
        self.context = context
        super().__init__(f"Cluster health provider error for '{context}': {message}")
