"""Factory for creating health check instances based on configuration."""

from typing import Any, Protocol

import structlog

from .http_health_check import HTTPHealthCheck
from .tcp_health_check import TCPHealthCheck

logger = structlog.get_logger()


class HealthChecker(Protocol):
    """Protocol for health check implementations."""

    async def check(self, **kwargs) -> bool:
        """Perform a health check and return True if healthy."""
        ...


class HealthCheckFactory:
    """Factory for creating health check instances."""

    def __init__(self):
        self._health_checkers: dict[str, type] = {
            'tcp': TCPHealthCheck,
            'http': HTTPHealthCheck,
        }

        # Try to import optional health checkers
        self._register_optional_health_checkers()

    def create_health_checker(self, check_type: str, config: dict[str, Any]) -> HealthChecker:
        """Create a health checker instance.
        
        Args:
            check_type: Type of health check (tcp, http, kafka, postgres)
            config: Configuration for the health checker
            
        Returns:
            Health checker instance
            
        Raises:
            ValueError: If check_type is not supported
        """
        if check_type not in self._health_checkers:
            available_types = list(self._health_checkers.keys())
            raise ValueError(f"Unsupported health check type '{check_type}'. Available types: {available_types}")

        health_checker_class = self._health_checkers[check_type]

        try:
            return health_checker_class(config)
        except Exception as e:
            logger.error("Failed to create health checker",
                        check_type=check_type,
                        config=config,
                        error=str(e))
            raise ValueError(f"Failed to create {check_type} health checker: {e}")

    def register_health_checker(self, check_type: str, health_checker_class: type) -> None:
        """Register a custom health checker.
        
        Args:
            check_type: Type identifier for the health checker
            health_checker_class: Health checker class
        """
        self._health_checkers[check_type] = health_checker_class
        logger.info("Registered health checker", check_type=check_type)

    def get_supported_types(self) -> list[str]:
        """Get list of supported health check types."""
        return list(self._health_checkers.keys())

    def _register_optional_health_checkers(self) -> None:
        """Register optional health checkers if their dependencies are available."""

        # Try to register Kafka health checker
        try:
            from .kafka_health_check import KafkaHealthCheck
            self._health_checkers['kafka'] = KafkaHealthCheck
            logger.debug("Registered Kafka health checker")
        except ImportError:
            logger.debug("Kafka health checker not available (kafka-python not installed)")

        # Try to register PostgreSQL health checker
        try:
            from .postgres_health_check import PostgreSQLHealthCheck
            self._health_checkers['postgres'] = PostgreSQLHealthCheck
            logger.debug("Registered PostgreSQL health checker")
        except ImportError:
            logger.debug("PostgreSQL health checker not available (psycopg not installed)")
