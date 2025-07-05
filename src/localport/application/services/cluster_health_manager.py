"""
Cluster health manager application service.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from ...domain.entities.cluster_health import ClusterHealth
from ...domain.entities.cluster_info import ClusterInfo
from ...domain.entities.cluster_event import ClusterEvent
from ...domain.entities.resource_status import ResourceStatus
from ...domain.services.cluster_health_provider import (
    ClusterHealthProvider, ClusterNotFoundError, ClusterConnectionError
)
from ...infrastructure.cluster_monitoring import (
    ClusterHealthMonitor, ClusterMonitorConfig
)


logger = logging.getLogger(__name__)


class ClusterHealthManager(ClusterHealthProvider):
    """
    Manages cluster health monitoring across multiple cluster contexts.
    
    This service orchestrates individual ClusterHealthMonitor instances,
    providing a unified interface for cluster health operations while
    managing the lifecycle of monitors based on active services.
    """
    
    def __init__(self, default_config: Optional[ClusterMonitorConfig] = None):
        """
        Initialize the cluster health manager.
        
        Args:
            default_config: Default configuration for cluster monitors
        """
        self.default_config = default_config or ClusterMonitorConfig()
        self._monitors: Dict[str, ClusterHealthMonitor] = {}
        self._active_contexts: Set[str] = set()
        self._is_running = False
    
    async def start(self) -> None:
        """Start the cluster health manager."""
        if self._is_running:
            logger.warning("Cluster health manager is already running")
            return
        
        logger.info("Starting cluster health manager")
        self._is_running = True
    
    async def stop(self) -> None:
        """Stop the cluster health manager and all monitors."""
        if not self._is_running:
            return
        
        logger.info("Stopping cluster health manager")
        self._is_running = False
        
        # Stop all monitors
        stop_tasks = []
        for monitor in self._monitors.values():
            stop_tasks.append(monitor.stop_monitoring())
        
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        self._monitors.clear()
        self._active_contexts.clear()
    
    async def register_context(self, context: str, 
                              config: Optional[ClusterMonitorConfig] = None) -> None:
        """
        Register a cluster context for monitoring.
        
        Args:
            context: Cluster context name
            config: Optional custom configuration for this context
        """
        if context in self._active_contexts:
            logger.debug(f"Context {context} is already registered")
            return
        
        logger.info(f"Registering cluster context for monitoring: {context}")
        self._active_contexts.add(context)
        
        # Create and start monitor if manager is running
        if self._is_running:
            await self._create_monitor(context, config)
    
    async def unregister_context(self, context: str) -> None:
        """
        Unregister a cluster context from monitoring.
        
        Args:
            context: Cluster context name
        """
        if context not in self._active_contexts:
            logger.debug(f"Context {context} is not registered")
            return
        
        logger.info(f"Unregistering cluster context from monitoring: {context}")
        self._active_contexts.discard(context)
        
        # Stop and remove monitor
        if context in self._monitors:
            monitor = self._monitors.pop(context)
            await monitor.stop_monitoring()
    
    async def update_active_contexts(self, contexts: Set[str]) -> None:
        """
        Update the set of active contexts, starting/stopping monitors as needed.
        
        Args:
            contexts: Set of cluster context names that should be monitored
        """
        current_contexts = set(self._active_contexts)
        
        # Start monitoring for new contexts
        new_contexts = contexts - current_contexts
        for context in new_contexts:
            await self.register_context(context)
        
        # Stop monitoring for removed contexts
        removed_contexts = current_contexts - contexts
        for context in removed_contexts:
            await self.unregister_context(context)
    
    # ClusterHealthProvider interface implementation
    
    async def is_cluster_healthy(self, context: str) -> bool:
        """Check if a cluster is considered healthy."""
        if context not in self._monitors:
            raise ClusterNotFoundError(context)
        
        monitor = self._monitors[context]
        health = await monitor.get_current_health()
        
        return health.is_healthy if health else False
    
    async def get_cluster_info(self, context: str) -> Optional[ClusterInfo]:
        """Get basic cluster information."""
        if context not in self._monitors:
            raise ClusterNotFoundError(context)
        
        monitor = self._monitors[context]
        return await monitor.get_cluster_info()
    
    async def get_cluster_health(self, context: str) -> Optional[ClusterHealth]:
        """Get comprehensive cluster health information."""
        if context not in self._monitors:
            raise ClusterNotFoundError(context)
        
        monitor = self._monitors[context]
        return await monitor.get_current_health()
    
    async def get_resource_status(self, context: str, namespace: str, 
                                 resource_name: str, resource_type: str) -> Optional[ResourceStatus]:
        """Get the status of a specific resource."""
        if context not in self._monitors:
            raise ClusterNotFoundError(context)
        
        monitor = self._monitors[context]
        return await monitor.get_resource_status(namespace, resource_name, resource_type)
    
    async def get_cluster_events(self, context: str, since: Optional[datetime] = None,
                                limit: int = 50) -> List[ClusterEvent]:
        """Get recent cluster events."""
        if context not in self._monitors:
            raise ClusterNotFoundError(context)
        
        monitor = self._monitors[context]
        return await monitor.get_cluster_events(since, limit)
    
    async def get_last_check_time(self, context: str) -> Optional[datetime]:
        """Get the timestamp of the last health check for a cluster."""
        if context not in self._monitors:
            raise ClusterNotFoundError(context)
        
        monitor = self._monitors[context]
        return monitor.last_successful_check
    
    async def get_monitored_contexts(self) -> List[str]:
        """Get the list of cluster contexts currently being monitored."""
        return list(self._active_contexts)
    
    async def start_monitoring(self, context: str) -> None:
        """Start monitoring a cluster context."""
        await self.register_context(context)
    
    async def stop_monitoring(self, context: str) -> None:
        """Stop monitoring a cluster context."""
        await self.unregister_context(context)
    
    async def refresh_cluster_health(self, context: str) -> Optional[ClusterHealth]:
        """Force a refresh of cluster health information."""
        if context not in self._monitors:
            raise ClusterNotFoundError(context)
        
        monitor = self._monitors[context]
        return await monitor.refresh_health()
    
    # Additional management methods
    
    async def get_all_cluster_health(self) -> Dict[str, Optional[ClusterHealth]]:
        """
        Get health information for all monitored clusters.
        
        Returns:
            Dict[str, ClusterHealth]: Mapping of context names to health states
        """
        health_states = {}
        
        for context, monitor in self._monitors.items():
            try:
                health = await monitor.get_current_health()
                health_states[context] = health
            except Exception as e:
                logger.error(f"Failed to get health for context {context}: {e}")
                health_states[context] = None
        
        return health_states
    
    async def get_unhealthy_clusters(self) -> List[str]:
        """
        Get a list of cluster contexts that are currently unhealthy.
        
        Returns:
            List[str]: List of unhealthy cluster context names
        """
        unhealthy_contexts = []
        
        for context, monitor in self._monitors.items():
            try:
                health = await monitor.get_current_health()
                if health and not health.is_healthy:
                    unhealthy_contexts.append(context)
            except Exception as e:
                logger.error(f"Failed to check health for context {context}: {e}")
                unhealthy_contexts.append(context)  # Consider failed checks as unhealthy
        
        return unhealthy_contexts
    
    async def get_monitoring_statistics(self) -> Dict[str, Dict]:
        """
        Get monitoring statistics for all clusters.
        
        Returns:
            Dict[str, Dict]: Monitoring statistics per cluster
        """
        stats = {}
        
        for context, monitor in self._monitors.items():
            try:
                stats[context] = monitor.get_monitoring_stats()
            except Exception as e:
                logger.error(f"Failed to get stats for context {context}: {e}")
                stats[context] = {
                    'context': context,
                    'error': str(e),
                    'is_monitoring': False
                }
        
        return stats
    
    def get_manager_status(self) -> Dict[str, any]:
        """
        Get the overall status of the cluster health manager.
        
        Returns:
            Dict[str, any]: Manager status information
        """
        return {
            'is_running': self._is_running,
            'active_contexts': list(self._active_contexts),
            'monitor_count': len(self._monitors),
            'default_config': {
                'interval': self.default_config.interval,
                'timeout': self.default_config.timeout,
                'failure_threshold': self.default_config.failure_threshold,
            }
        }
    
    async def _create_monitor(self, context: str, 
                             config: Optional[ClusterMonitorConfig] = None) -> None:
        """
        Create and start a cluster monitor for the given context.
        
        Args:
            context: Cluster context name
            config: Optional custom configuration
        """
        if context in self._monitors:
            logger.warning(f"Monitor already exists for context {context}")
            return
        
        monitor_config = config or self.default_config
        monitor = ClusterHealthMonitor(context, monitor_config)
        
        try:
            await monitor.start_monitoring()
            self._monitors[context] = monitor
            logger.info(f"Started cluster monitor for context: {context}")
        except Exception as e:
            logger.error(f"Failed to start monitor for context {context}: {e}")
            # Clean up the failed monitor
            try:
                await monitor.stop_monitoring()
            except Exception:
                pass
            raise ClusterConnectionError(context, str(e))
    
    async def refresh_all_clusters(self) -> Dict[str, Optional[ClusterHealth]]:
        """
        Force a refresh of all cluster health information.
        
        Returns:
            Dict[str, ClusterHealth]: Updated health states for all clusters
        """
        refresh_tasks = {}
        
        for context, monitor in self._monitors.items():
            refresh_tasks[context] = monitor.refresh_health()
        
        # Wait for all refreshes to complete
        results = await asyncio.gather(*refresh_tasks.values(), return_exceptions=True)
        
        # Collect results
        health_states = {}
        for context, result in zip(refresh_tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Failed to refresh health for context {context}: {result}")
                health_states[context] = None
            else:
                health_states[context] = result
        
        return health_states
