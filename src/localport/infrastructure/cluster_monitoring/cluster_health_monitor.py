"""
Cluster health monitor implementation.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from ...domain.entities.cluster_info import ClusterInfo
from ...domain.entities.cluster_event import ClusterEvent
from ...domain.entities.cluster_health import ClusterHealth, ClusterHealthStatus
from ...domain.entities.resource_status import ResourceStatus
from ...domain.services.cluster_health_provider import (
    ClusterHealthProvider, ClusterNotFoundError, ClusterConnectionError
)
from .kubectl_client import KubectlClient, KubectlError


logger = logging.getLogger(__name__)


@dataclass
class ClusterMonitorConfig:
    """Configuration for cluster health monitoring."""
    
    interval: int = 240  # 4 minutes
    timeout: int = 30    # 30 seconds per command
    retry_attempts: int = 2
    failure_threshold: int = 3  # Consecutive failures before marking unhealthy
    
    # Command configuration
    enable_cluster_info: bool = True
    enable_pod_status: bool = True
    enable_node_status: bool = True
    enable_events_on_failure: bool = True


class ClusterHealthMonitor:
    """
    Monitors health of a single cluster context.
    
    This class implements the core cluster monitoring logic, executing
    periodic health checks and maintaining cluster state information.
    """
    
    def __init__(self, context: str, config: ClusterMonitorConfig):
        """
        Initialize the cluster health monitor.
        
        Args:
            context: Cluster context name to monitor
            config: Monitoring configuration
        """
        self.context = context
        self.config = config
        self.kubectl_client = KubectlClient(
            timeout=config.timeout,
            retry_attempts=config.retry_attempts
        )
        
        # State tracking
        self._current_health: Optional[ClusterHealth] = None
        self._consecutive_failures = 0
        self._last_successful_check: Optional[datetime] = None
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_running = False
        
        # Cache for performance
        self._cached_cluster_info: Optional[ClusterInfo] = None
        self._cache_expiry: Optional[datetime] = None
        self._cache_duration = timedelta(minutes=5)  # Cache cluster info for 5 minutes
    
    async def start_monitoring(self) -> None:
        """
        Start the monitoring loop for this cluster.
        
        Raises:
            RuntimeError: If monitoring is already running
        """
        if self._is_running:
            raise RuntimeError(f"Monitoring already running for context '{self.context}'")
        
        logger.info(f"Starting cluster health monitoring for context: {self.context}")
        self._is_running = True
        
        # Start the monitoring task
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        # Perform initial health check
        try:
            await self._perform_health_check()
        except Exception as e:
            logger.warning(f"Initial health check failed for {self.context}: {e}")
    
    async def stop_monitoring(self) -> None:
        """Stop the monitoring loop for this cluster."""
        if not self._is_running:
            return
        
        logger.info(f"Stopping cluster health monitoring for context: {self.context}")
        self._is_running = False
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
    
    async def get_current_health(self) -> Optional[ClusterHealth]:
        """
        Get the current cluster health state.
        
        Returns:
            ClusterHealth or None: Current health state if available
        """
        return self._current_health
    
    async def refresh_health(self) -> Optional[ClusterHealth]:
        """
        Force a refresh of cluster health information.
        
        Returns:
            ClusterHealth or None: Updated health state
        """
        try:
            await self._perform_health_check()
            return self._current_health
        except Exception as e:
            logger.error(f"Failed to refresh health for {self.context}: {e}")
            return self._current_health
    
    async def get_cluster_info(self) -> Optional[ClusterInfo]:
        """
        Get cached cluster information or fetch if expired.
        
        Returns:
            ClusterInfo or None: Cluster information if available
        """
        # Check cache
        if (self._cached_cluster_info and self._cache_expiry and 
            datetime.utcnow() < self._cache_expiry):
            return self._cached_cluster_info
        
        # Fetch fresh data
        try:
            cluster_info = await self.kubectl_client.get_cluster_info(self.context)
            if cluster_info.is_reachable:
                self._cached_cluster_info = cluster_info
                self._cache_expiry = datetime.utcnow() + self._cache_duration
            return cluster_info
        except Exception as e:
            logger.error(f"Failed to get cluster info for {self.context}: {e}")
            return self._cached_cluster_info
    
    async def get_resource_status(self, namespace: str, resource_name: str, 
                                 resource_type: str) -> Optional[ResourceStatus]:
        """
        Get the status of a specific resource.
        
        Args:
            namespace: Resource namespace
            resource_name: Name of the resource
            resource_type: Type of resource (Pod, Service, etc.)
            
        Returns:
            ResourceStatus or None: Resource status if found
        """
        try:
            if resource_type.lower() == 'pod':
                pods = await self.kubectl_client.get_pod_statuses(self.context)
                for pod in pods:
                    if pod.name == resource_name and pod.namespace == namespace:
                        return pod
            elif resource_type.lower() == 'node':
                nodes = await self.kubectl_client.get_node_statuses(self.context)
                for node in nodes:
                    if node.name == resource_name:
                        return node
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get resource status for {resource_type}/{namespace}/{resource_name}: {e}")
            return None
    
    async def get_cluster_events(self, since: Optional[datetime] = None, 
                                limit: int = 50) -> List[ClusterEvent]:
        """
        Get recent cluster events.
        
        Args:
            since: Only return events after this timestamp (optional)
            limit: Maximum number of events to return
            
        Returns:
            List[ClusterEvent]: List of cluster events
        """
        try:
            events = await self.kubectl_client.get_cluster_events(self.context, limit)
            
            if since:
                # Filter events by timestamp
                filtered_events = []
                for event in events:
                    if event.last_timestamp and event.last_timestamp >= since:
                        filtered_events.append(event)
                return filtered_events
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get cluster events for {self.context}: {e}")
            return []
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop that runs periodically."""
        logger.debug(f"Starting monitoring loop for {self.context} (interval: {self.config.interval}s)")
        
        while self._is_running:
            try:
                # Perform health check
                await self._perform_health_check()
                
                # Wait for next interval
                await asyncio.sleep(self.config.interval)
                
            except asyncio.CancelledError:
                logger.debug(f"Monitoring loop cancelled for {self.context}")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop for {self.context}: {e}")
                # Continue monitoring even if there's an error
                await asyncio.sleep(min(self.config.interval, 60))  # Wait at least 1 minute on error
    
    async def _perform_health_check(self) -> None:
        """Perform a comprehensive health check of the cluster."""
        start_time = datetime.utcnow()
        
        try:
            logger.debug(f"Performing health check for {self.context}")
            
            # Collect cluster information
            cluster_info = None
            nodes = []
            pods = []
            events = []
            
            # 1. Get cluster info (always enabled)
            if self.config.enable_cluster_info:
                cluster_info = await self.kubectl_client.get_cluster_info(self.context)
                
                # If cluster is not reachable, mark as unhealthy and return
                if not cluster_info.is_reachable:
                    self._consecutive_failures += 1
                    self._current_health = ClusterHealth.create_unhealthy(
                        context=self.context,
                        error=cluster_info.error_message or "Cluster not reachable",
                        consecutive_failures=self._consecutive_failures
                    )
                    logger.warning(f"Cluster {self.context} is not reachable: {cluster_info.error_message}")
                    return
            
            # 2. Get node statuses
            if self.config.enable_node_status:
                try:
                    nodes = await self.kubectl_client.get_node_statuses(self.context)
                except Exception as e:
                    logger.warning(f"Failed to get node statuses for {self.context}: {e}")
            
            # 3. Get pod statuses
            if self.config.enable_pod_status:
                try:
                    pods = await self.kubectl_client.get_pod_statuses(self.context)
                except Exception as e:
                    logger.warning(f"Failed to get pod statuses for {self.context}: {e}")
            
            # 4. Get events on failure or if this is the first check
            if (self.config.enable_events_on_failure and 
                (self._consecutive_failures > 0 or self._current_health is None)):
                try:
                    events = await self.kubectl_client.get_cluster_events(self.context, limit=50)
                except Exception as e:
                    logger.warning(f"Failed to get cluster events for {self.context}: {e}")
            
            # Calculate check duration
            check_duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Create healthy cluster health state
            self._current_health = ClusterHealth.create_healthy(
                context=self.context,
                cluster_info=cluster_info,
                nodes=nodes,
                pods=pods,
                events=events,
                check_duration=check_duration
            )
            
            # Reset failure count on successful check
            self._consecutive_failures = 0
            self._last_successful_check = datetime.utcnow()
            
            logger.debug(f"Health check completed for {self.context}: {self._current_health.status_summary}")
            
        except Exception as e:
            # Handle unexpected errors
            self._consecutive_failures += 1
            error_msg = f"Health check failed: {str(e)}"
            
            self._current_health = ClusterHealth.create_unhealthy(
                context=self.context,
                error=error_msg,
                consecutive_failures=self._consecutive_failures
            )
            
            logger.error(f"Health check failed for {self.context}: {e}")
            
            # If we've exceeded the failure threshold, log a warning
            if self._consecutive_failures >= self.config.failure_threshold:
                logger.warning(
                    f"Cluster {self.context} has failed {self._consecutive_failures} "
                    f"consecutive health checks (threshold: {self.config.failure_threshold})"
                )
    
    @property
    def is_monitoring(self) -> bool:
        """Check if monitoring is currently active."""
        return self._is_running
    
    @property
    def consecutive_failures(self) -> int:
        """Get the number of consecutive failures."""
        return self._consecutive_failures
    
    @property
    def last_successful_check(self) -> Optional[datetime]:
        """Get the timestamp of the last successful check."""
        return self._last_successful_check
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """
        Get monitoring statistics for this cluster.
        
        Returns:
            Dict[str, Any]: Monitoring statistics
        """
        return {
            'context': self.context,
            'is_monitoring': self.is_monitoring,
            'consecutive_failures': self.consecutive_failures,
            'last_successful_check': self.last_successful_check.isoformat() if self.last_successful_check else None,
            'current_status': self._current_health.status.value if self._current_health else 'Unknown',
            'config': {
                'interval': self.config.interval,
                'timeout': self.config.timeout,
                'failure_threshold': self.config.failure_threshold,
            }
        }
