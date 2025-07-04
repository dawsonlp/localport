"""Abstract base class for health checkers."""

from abc import ABC, abstractmethod
from typing import Any, Dict

from ...domain.entities.health_check import HealthCheckResult


class HealthChecker(ABC):
    """Abstract base class for all health checkers.
    
    This interface ensures all health checkers have a consistent contract,
    enabling polymorphic usage and eliminating type-specific conditional logic.
    """

    @abstractmethod
    async def check_health(self, config: Dict[str, Any]) -> HealthCheckResult:
        """Perform health check with given configuration.
        
        Args:
            config: Health check configuration including connection details,
                   timeout, and any checker-specific parameters
                   
        Returns:
            HealthCheckResult with status, timing, and error information
        """
        pass

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration for this health checker.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if configuration is valid, False otherwise
        """
        pass

    @abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for this health checker.
        
        Returns:
            Dictionary containing default configuration values
        """
        pass

    def get_config_schema(self) -> Dict[str, Any]:
        """Get JSON schema for configuration validation.
        
        Returns:
            JSON schema dictionary for configuration validation.
            Override in subclasses to provide specific schema.
        """
        return {
            "type": "object",
            "properties": {
                "timeout": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 300,
                    "default": 5.0,
                    "description": "Health check timeout in seconds"
                }
            },
            "additionalProperties": True
        }

    def merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge provided config with defaults.
        
        Args:
            config: User-provided configuration
            
        Returns:
            Configuration merged with defaults
        """
        defaults = self.get_default_config()
        merged = defaults.copy()
        merged.update(config)
        return merged
