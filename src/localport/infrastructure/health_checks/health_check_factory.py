"""Factory for creating health check instances based on configuration."""

from typing import Dict, Any, Optional, Type, Protocol
from enum import Enum
import structlog

from .tcp_health_check import TCPHealthCheck
from .http_health_check import HTTPHealthCheck
from .kafka_health_check import KafkaHealthCheck
from .postgres_health_check import PostgreSQLHealthCheck

logger = structlog.get_logger()


class HealthCheckType(str, Enum):
    """Supported health check types."""
    TCP = "tcp"
    HTTP = "http"
    HTTPS = "https"
    KAFKA = "kafka"
    POSTGRES = "postgres"
    POSTGRESQL = "postgresql"  # Alias for postgres


class HealthCheckProtocol(Protocol):
    """Protocol that all health check implementations must follow."""
    
    async def check(self, config: Dict[str, Any]) -> bool:
        """Perform health check.
        
        Args:
            config: Health check configuration
            
        Returns:
            True if healthy, False otherwise
        """
        ...


class HealthCheckFactory:
    """Factory for creating health check instances."""
    
    def __init__(self):
        """Initialize the health check factory."""
        self._health_checks: Dict[str, Type[HealthCheckProtocol]] = {
            HealthCheckType.TCP: TCPHealthCheck,
            HealthCheckType.HTTP: HTTPHealthCheck,
            HealthCheckType.HTTPS: HTTPHealthCheck,  # HTTPS uses HTTPHealthCheck
            HealthCheckType.KAFKA: KafkaHealthCheck,
            HealthCheckType.POSTGRES: PostgreSQLHealthCheck,
            HealthCheckType.POSTGRESQL: PostgreSQLHealthCheck,  # Alias
        }
    
    def create_health_check(
        self, 
        health_check_type: str, 
        timeout: float = 5.0,
        **kwargs
    ) -> Optional[HealthCheckProtocol]:
        """Create a health check instance.
        
        Args:
            health_check_type: Type of health check to create
            timeout: Timeout for health check operations
            **kwargs: Additional arguments for health check initialization
            
        Returns:
            Health check instance or None if type not supported
        """
        health_check_type = health_check_type.lower()
        
        if health_check_type not in self._health_checks:
            logger.error("Unsupported health check type", 
                        type=health_check_type,
                        supported_types=list(self._health_checks.keys()))
            return None
        
        health_check_class = self._health_checks[health_check_type]
        
        try:
            # Create instance with timeout and any additional kwargs
            if health_check_type in [HealthCheckType.TCP, HealthCheckType.HTTP, HealthCheckType.HTTPS]:
                return health_check_class(timeout=timeout, **kwargs)
            elif health_check_type in [HealthCheckType.KAFKA, HealthCheckType.POSTGRES, HealthCheckType.POSTGRESQL]:
                return health_check_class(timeout=timeout, **kwargs)
            else:
                # Fallback for any new health checks
                return health_check_class(timeout=timeout, **kwargs)
                
        except Exception as e:
            logger.error("Failed to create health check instance", 
                        type=health_check_type,
                        error=str(e))
            return None
    
    def register_health_check(self, health_check_type: str, health_check_class: Type[HealthCheckProtocol]) -> None:
        """Register a new health check type.
        
        Args:
            health_check_type: Name of the health check type
            health_check_class: Class implementing the health check
        """
        health_check_type = health_check_type.lower()
        
        logger.info("Registering health check type", 
                   type=health_check_type,
                   class_name=health_check_class.__name__)
        
        self._health_checks[health_check_type] = health_check_class
    
    def get_supported_types(self) -> list[str]:
        """Get list of supported health check types.
        
        Returns:
            List of supported health check type names
        """
        return list(self._health_checks.keys())
    
    def is_supported(self, health_check_type: str) -> bool:
        """Check if a health check type is supported.
        
        Args:
            health_check_type: Type to check
            
        Returns:
            True if supported, False otherwise
        """
        return health_check_type.lower() in self._health_checks


class HealthCheckConfig:
    """Configuration for health checks."""
    
    def __init__(
        self,
        health_check_type: str,
        interval: int = 30,
        timeout: float = 5.0,
        failure_threshold: int = 3,
        success_threshold: int = 1,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize health check configuration.
        
        Args:
            health_check_type: Type of health check
            interval: Check interval in seconds
            timeout: Check timeout in seconds
            failure_threshold: Number of failures before marking unhealthy
            success_threshold: Number of successes before marking healthy
            config: Type-specific configuration
        """
        self.type = health_check_type.lower()
        self.interval = interval
        self.timeout = timeout
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.config = config or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary representation of the configuration
        """
        return {
            'type': self.type,
            'interval': self.interval,
            'timeout': self.timeout,
            'failure_threshold': self.failure_threshold,
            'success_threshold': self.success_threshold,
            'config': self.config
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HealthCheckConfig':
        """Create configuration from dictionary.
        
        Args:
            data: Dictionary containing configuration data
            
        Returns:
            HealthCheckConfig instance
        """
        return cls(
            health_check_type=data['type'],
            interval=data.get('interval', 30),
            timeout=data.get('timeout', 5.0),
            failure_threshold=data.get('failure_threshold', 3),
            success_threshold=data.get('success_threshold', 1),
            config=data.get('config', {})
        )


class HealthCheckRunner:
    """Runs health checks with proper configuration and state tracking."""
    
    def __init__(self, factory: Optional[HealthCheckFactory] = None):
        """Initialize health check runner.
        
        Args:
            factory: Health check factory to use (creates default if None)
        """
        self.factory = factory or HealthCheckFactory()
        self._failure_counts: Dict[str, int] = {}
        self._success_counts: Dict[str, int] = {}
    
    async def run_health_check(
        self, 
        service_name: str, 
        config: HealthCheckConfig
    ) -> bool:
        """Run a health check for a service.
        
        Args:
            service_name: Name of the service being checked
            config: Health check configuration
            
        Returns:
            True if service is healthy, False otherwise
        """
        # Create health check instance
        health_check = self.factory.create_health_check(
            config.type,
            timeout=config.timeout
        )
        
        if not health_check:
            logger.error("Failed to create health check", 
                        service=service_name,
                        type=config.type)
            return False
        
        try:
            # Run the health check
            is_healthy = await health_check.check(config.config)
            
            # Update counters
            if is_healthy:
                self._success_counts[service_name] = self._success_counts.get(service_name, 0) + 1
                self._failure_counts[service_name] = 0  # Reset failure count
                
                # Check if we've reached success threshold
                if self._success_counts[service_name] >= config.success_threshold:
                    logger.debug("Service health check passed", 
                                service=service_name,
                                type=config.type,
                                success_count=self._success_counts[service_name])
                    return True
                else:
                    # Still recovering, not yet healthy
                    logger.debug("Service health check passed but still recovering", 
                                service=service_name,
                                success_count=self._success_counts[service_name],
                                threshold=config.success_threshold)
                    return False
            else:
                self._failure_counts[service_name] = self._failure_counts.get(service_name, 0) + 1
                self._success_counts[service_name] = 0  # Reset success count
                
                # Check if we've reached failure threshold
                if self._failure_counts[service_name] >= config.failure_threshold:
                    logger.warning("Service health check failed", 
                                  service=service_name,
                                  type=config.type,
                                  failure_count=self._failure_counts[service_name])
                    return False
                else:
                    # Still within failure threshold, consider healthy for now
                    logger.debug("Service health check failed but within threshold", 
                                service=service_name,
                                failure_count=self._failure_counts[service_name],
                                threshold=config.failure_threshold)
                    return True
                    
        except Exception as e:
            logger.error("Health check execution failed", 
                        service=service_name,
                        type=config.type,
                        error=str(e))
            
            # Treat exceptions as failures
            self._failure_counts[service_name] = self._failure_counts.get(service_name, 0) + 1
            self._success_counts[service_name] = 0
            
            return self._failure_counts[service_name] < config.failure_threshold
    
    def reset_counters(self, service_name: str) -> None:
        """Reset health check counters for a service.
        
        Args:
            service_name: Name of the service
        """
        self._failure_counts.pop(service_name, None)
        self._success_counts.pop(service_name, None)
        
        logger.debug("Reset health check counters", service=service_name)
    
    def get_failure_count(self, service_name: str) -> int:
        """Get current failure count for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Current failure count
        """
        return self._failure_counts.get(service_name, 0)
    
    def get_success_count(self, service_name: str) -> int:
        """Get current success count for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Current success count
        """
        return self._success_counts.get(service_name, 0)


# Global factory instance
_default_factory = HealthCheckFactory()


def create_health_check(
    health_check_type: str, 
    timeout: float = 5.0,
    **kwargs
) -> Optional[HealthCheckProtocol]:
    """Create a health check using the default factory.
    
    Args:
        health_check_type: Type of health check to create
        timeout: Timeout for health check operations
        **kwargs: Additional arguments for health check initialization
        
    Returns:
        Health check instance or None if type not supported
    """
    return _default_factory.create_health_check(health_check_type, timeout, **kwargs)


def register_health_check(health_check_type: str, health_check_class: Type[HealthCheckProtocol]) -> None:
    """Register a new health check type with the default factory.
    
    Args:
        health_check_type: Name of the health check type
        health_check_class: Class implementing the health check
    """
    _default_factory.register_health_check(health_check_type, health_check_class)


def get_supported_health_check_types() -> list[str]:
    """Get list of supported health check types.
    
    Returns:
        List of supported health check type names
    """
    return _default_factory.get_supported_types()
