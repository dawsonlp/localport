"""
Cluster information domain entity.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class ClusterInfo:
    """
    Represents basic cluster connectivity and version information.
    
    This entity contains essential cluster metadata collected from
    kubectl cluster-info and related commands.
    """
    
    context: str
    api_server_url: Optional[str] = None
    cluster_version: Optional[str] = None
    is_reachable: bool = False
    last_check_time: Optional[datetime] = None
    error_message: Optional[str] = None
    
    # Additional cluster metadata
    node_count: Optional[int] = None
    namespace_count: Optional[int] = None
    core_services_healthy: bool = False
    
    # Raw data for debugging
    raw_cluster_info: Optional[Dict[str, Any]] = None
    
    @property
    def is_healthy(self) -> bool:
        """
        Determine if the cluster is considered healthy.
        
        Returns:
            bool: True if cluster is reachable and core services are healthy
        """
        return self.is_reachable and self.core_services_healthy
    
    @property
    def status_summary(self) -> str:
        """
        Get a human-readable status summary.
        
        Returns:
            str: Brief status description
        """
        if not self.is_reachable:
            return f"Unreachable: {self.error_message or 'Unknown error'}"
        elif not self.core_services_healthy:
            return "Reachable but core services unhealthy"
        else:
            return "Healthy"
    
    def with_update(self, **kwargs) -> "ClusterInfo":
        """
        Create a new ClusterInfo instance with updated fields.
        
        Args:
            **kwargs: Fields to update
            
        Returns:
            ClusterInfo: New instance with updated fields
        """
        current_data = {
            'context': self.context,
            'api_server_url': self.api_server_url,
            'cluster_version': self.cluster_version,
            'is_reachable': self.is_reachable,
            'last_check_time': self.last_check_time,
            'error_message': self.error_message,
            'node_count': self.node_count,
            'namespace_count': self.namespace_count,
            'core_services_healthy': self.core_services_healthy,
            'raw_cluster_info': self.raw_cluster_info,
        }
        current_data.update(kwargs)
        return ClusterInfo(**current_data)
