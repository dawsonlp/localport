"""
Cluster configuration manager for converting YAML config to cluster monitoring config.
"""

import logging
from typing import Dict, Set, Optional, Any

from ...infrastructure.cluster_monitoring import ClusterMonitorConfig
from ...domain.enums import ForwardingTechnology
from ...domain.entities.service import Service


logger = logging.getLogger(__name__)


class ClusterConfigManager:
    """
    Manages cluster health monitoring configuration.
    
    This service converts YAML configuration to ClusterMonitorConfig objects
    and determines which cluster contexts should be monitored based on active services.
    """
    
    def __init__(self):
        """Initialize the cluster configuration manager."""
        self._default_config: Optional[ClusterMonitorConfig] = None
        self._context_configs: Dict[str, ClusterMonitorConfig] = {}
    
    def load_from_yaml_config(self, yaml_config: Dict[str, Any]) -> None:
        """
        Load cluster health configuration from YAML configuration.
        
        Args:
            yaml_config: The loaded YAML configuration dictionary
        """
        defaults = yaml_config.get('defaults', {})
        cluster_health_config = defaults.get('cluster_health', {})
        
        # Create default cluster monitor configuration
        self._default_config = self._create_cluster_monitor_config(cluster_health_config)
        
        # Load per-cluster context overrides if they exist
        cluster_contexts = yaml_config.get('cluster_contexts', {})
        for context, context_config in cluster_contexts.items():
            context_cluster_health = context_config.get('cluster_health', {})
            if context_cluster_health:
                # Merge with defaults
                merged_config = self._merge_cluster_configs(cluster_health_config, context_cluster_health)
                self._context_configs[context] = self._create_cluster_monitor_config(merged_config)
        
        logger.info("Loaded cluster health configuration",
                   extra={
                       "default_enabled": self._default_config.enable_cluster_info if self._default_config else False,
                       "context_overrides": len(self._context_configs)
                   })
    
    def get_cluster_monitor_config(self, context: str) -> ClusterMonitorConfig:
        """
        Get cluster monitor configuration for a specific context.
        
        Args:
            context: Cluster context name
            
        Returns:
            ClusterMonitorConfig: Configuration for the context
        """
        # Return context-specific config if available, otherwise default
        if context in self._context_configs:
            return self._context_configs[context]
        
        if self._default_config:
            return self._default_config
        
        # Fallback to built-in defaults
        return ClusterMonitorConfig()
    
    def get_default_config(self) -> ClusterMonitorConfig:
        """
        Get the default cluster monitor configuration.
        
        Returns:
            ClusterMonitorConfig: Default configuration
        """
        return self._default_config or ClusterMonitorConfig()
    
    def is_cluster_health_enabled(self) -> bool:
        """
        Check if cluster health monitoring is enabled globally.
        
        Returns:
            bool: True if cluster health monitoring is enabled
        """
        if not self._default_config:
            return True  # Default to enabled
        
        return self._default_config.enable_cluster_info
    
    def extract_cluster_contexts_from_services(self, services: list[Service]) -> Set[str]:
        """
        Extract unique cluster contexts from a list of services.
        
        Args:
            services: List of service configurations
            
        Returns:
            Set[str]: Set of unique cluster context names
        """
        contexts = set()
        
        for service in services:
            # Only consider kubectl services for cluster monitoring
            if service.technology == ForwardingTechnology.KUBECTL:
                try:
                    # Use the proper method to get kubectl context
                    context = service.connection_info.get_kubectl_context()
                    if context:
                        contexts.add(context)
                except Exception as e:
                    logger.warning("Failed to extract context from service",
                                 service_name=service.name,
                                 error=str(e))
        
        logger.info("Extracted cluster contexts from services",
                   extra={
                       "contexts": list(contexts),
                       "total_services": len(services),
                       "kubectl_services": len([s for s in services if s.technology == ForwardingTechnology.KUBECTL])
                   })
        
        return contexts
    
    def _create_cluster_monitor_config(self, config_dict: Dict[str, Any]) -> ClusterMonitorConfig:
        """
        Create a ClusterMonitorConfig from a configuration dictionary.
        
        Args:
            config_dict: Configuration dictionary from YAML
            
        Returns:
            ClusterMonitorConfig: Cluster monitor configuration
        """
        # Extract basic configuration
        enabled = config_dict.get('enabled', True)
        interval = config_dict.get('interval', 240)  # 4 minutes default
        timeout = config_dict.get('timeout', 30)
        retry_attempts = config_dict.get('retry_attempts', 2)
        failure_threshold = config_dict.get('failure_threshold', 3)
        
        # Extract command configuration
        commands = config_dict.get('commands', {})
        enable_cluster_info = self._get_command_enabled(commands, 'cluster_info', True)
        enable_pod_status = self._get_command_enabled(commands, 'pod_status', True)
        enable_node_status = self._get_command_enabled(commands, 'node_status', True)
        enable_events_on_failure = self._get_command_enabled(commands, 'events_on_failure', True)
        
        # If cluster health is disabled globally, disable all commands
        if not enabled:
            enable_cluster_info = False
            enable_pod_status = False
            enable_node_status = False
            enable_events_on_failure = False
        
        return ClusterMonitorConfig(
            interval=interval,
            timeout=timeout,
            retry_attempts=retry_attempts,
            failure_threshold=failure_threshold,
            enable_cluster_info=enable_cluster_info,
            enable_pod_status=enable_pod_status,
            enable_node_status=enable_node_status,
            enable_events_on_failure=enable_events_on_failure
        )
    
    def _get_command_enabled(self, commands_config: Dict[str, Any], command_name: str, default: bool) -> bool:
        """
        Get whether a specific command is enabled.
        
        Args:
            commands_config: Commands configuration dictionary
            command_name: Name of the command
            default: Default value if not specified
            
        Returns:
            bool: True if command is enabled
        """
        command_config = commands_config.get(command_name, default)
        
        if isinstance(command_config, bool):
            return command_config
        elif isinstance(command_config, dict):
            return command_config.get('enabled', default)
        else:
            return default
    
    def _merge_cluster_configs(self, base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge cluster configuration with overrides.
        
        Args:
            base_config: Base configuration (defaults)
            override_config: Override configuration (context-specific)
            
        Returns:
            Dict[str, Any]: Merged configuration
        """
        merged = base_config.copy()
        
        # Merge top-level settings
        for key, value in override_config.items():
            if key == 'commands' and isinstance(value, dict):
                # Merge commands configuration
                base_commands = merged.get('commands', {})
                merged_commands = base_commands.copy()
                merged_commands.update(value)
                merged['commands'] = merged_commands
            else:
                merged[key] = value
        
        return merged
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current cluster health configuration.
        
        Returns:
            Dict[str, Any]: Configuration summary
        """
        default_config = self.get_default_config()
        
        return {
            'enabled': self.is_cluster_health_enabled(),
            'default_config': {
                'interval': default_config.interval,
                'timeout': default_config.timeout,
                'retry_attempts': default_config.retry_attempts,
                'failure_threshold': default_config.failure_threshold,
                'commands': {
                    'cluster_info': default_config.enable_cluster_info,
                    'pod_status': default_config.enable_pod_status,
                    'node_status': default_config.enable_node_status,
                    'events_on_failure': default_config.enable_events_on_failure,
                }
            },
            'context_overrides': list(self._context_configs.keys()),
            'context_count': len(self._context_configs)
        }
    
    def validate_configuration(self) -> list[str]:
        """
        Validate the current cluster health configuration.
        
        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []
        
        if not self._default_config:
            errors.append("No default cluster health configuration loaded")
            return errors
        
        # Validate default configuration
        default_errors = self._validate_cluster_monitor_config(self._default_config, "default")
        errors.extend(default_errors)
        
        # Validate context-specific configurations
        for context, config in self._context_configs.items():
            context_errors = self._validate_cluster_monitor_config(config, f"context '{context}'")
            errors.extend(context_errors)
        
        return errors
    
    def _validate_cluster_monitor_config(self, config: ClusterMonitorConfig, prefix: str) -> list[str]:
        """
        Validate a cluster monitor configuration.
        
        Args:
            config: Configuration to validate
            prefix: Prefix for error messages
            
        Returns:
            List[str]: Validation errors
        """
        errors = []
        
        # Validate intervals and timeouts
        if config.interval < 60:
            errors.append(f"{prefix}: interval must be at least 60 seconds")
        if config.interval > 3600:
            errors.append(f"{prefix}: interval must be at most 3600 seconds (1 hour)")
        
        if config.timeout < 5:
            errors.append(f"{prefix}: timeout must be at least 5 seconds")
        if config.timeout > 300:
            errors.append(f"{prefix}: timeout must be at most 300 seconds (5 minutes)")
        
        if config.timeout >= config.interval:
            errors.append(f"{prefix}: timeout must be less than interval")
        
        # Validate retry attempts
        if config.retry_attempts < 0:
            errors.append(f"{prefix}: retry_attempts must be non-negative")
        if config.retry_attempts > 10:
            errors.append(f"{prefix}: retry_attempts must be at most 10")
        
        # Validate failure threshold
        if config.failure_threshold < 1:
            errors.append(f"{prefix}: failure_threshold must be at least 1")
        if config.failure_threshold > 100:
            errors.append(f"{prefix}: failure_threshold must be at most 100")
        
        # Warn if no commands are enabled
        if not any([
            config.enable_cluster_info,
            config.enable_pod_status,
            config.enable_node_status,
            config.enable_events_on_failure
        ]):
            errors.append(f"{prefix}: at least one command should be enabled for effective monitoring")
        
        return errors
