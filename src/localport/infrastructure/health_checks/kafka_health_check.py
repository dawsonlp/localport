"""Kafka-specific health check implementation."""

import asyncio
from datetime import datetime
from typing import Any, Dict

import structlog

from ...domain.entities.health_check import HealthCheckResult
from .base_health_checker import HealthChecker

logger = structlog.get_logger()


class KafkaHealthCheck(HealthChecker):
    """Kafka-specific health check using bootstrap servers."""

    def __init__(self):
        """Initialize Kafka health check."""
        pass

    async def check_health(self, config: Dict[str, Any]) -> HealthCheckResult:
        """Perform Kafka health check with given configuration.
        
        Args:
            config: Configuration containing bootstrap_servers, timeout, etc.
            
        Returns:
            HealthCheckResult with the check outcome
        """
        # Merge with defaults and validate
        merged_config = self.merge_with_defaults(config)
        
        bootstrap_servers = merged_config.get('bootstrap_servers', 'localhost:9092')
        timeout = merged_config.get('timeout', 10.0)
        
        start_time = datetime.now()
        
        try:
            # Import kafka-python here to make it optional
            try:
                from kafka import KafkaConsumer
                from kafka.errors import KafkaError, NoBrokersAvailable
            except ImportError:
                return HealthCheckResult.error("kafka-python not installed. Install with: pip install kafka-python")

            # Run the blocking Kafka operations in a thread pool
            is_healthy = await asyncio.get_event_loop().run_in_executor(
                None, self._check_kafka_sync, bootstrap_servers, timeout
            )
            
            # Calculate response time
            end_time = datetime.now()
            response_time_ms = (end_time - start_time).total_seconds() * 1000
            
            if is_healthy:
                return HealthCheckResult.healthy(
                    message=f"Kafka connection to {bootstrap_servers} successful",
                    response_time_ms=response_time_ms
                )
            else:
                return HealthCheckResult.unhealthy(
                    message=f"Kafka connection to {bootstrap_servers} failed",
                    error="Connection failed"
                )

        except Exception as e:
            logger.debug("Kafka health check failed",
                        bootstrap_servers=bootstrap_servers,
                        error=str(e))
            return HealthCheckResult.error(f"Kafka health check exception: {str(e)}")

    def _check_kafka_sync(self, bootstrap_servers: str, timeout: float) -> bool:
        """Synchronous Kafka connectivity check.

        Args:
            bootstrap_servers: Comma-separated list of bootstrap servers
            timeout: Connection timeout in seconds

        Returns:
            True if connection successful, False otherwise
        """
        try:
            from kafka import KafkaConsumer
            from kafka.errors import KafkaError, NoBrokersAvailable

            # Create a consumer to test connectivity
            consumer = KafkaConsumer(
                bootstrap_servers=bootstrap_servers.split(','),
                consumer_timeout_ms=int(timeout * 1000),
                api_version_auto_timeout_ms=int(timeout * 1000),
                request_timeout_ms=int(timeout * 1000),
                # Don't actually consume any messages
                enable_auto_commit=False,
                auto_offset_reset='earliest'
            )

            try:
                # Try to get cluster metadata - this will test connectivity
                metadata = consumer.list_consumer_groups()
                logger.debug("Kafka health check passed",
                            bootstrap_servers=bootstrap_servers,
                            consumer_groups_count=len(metadata))
                return True

            finally:
                consumer.close()

        except NoBrokersAvailable:
            logger.debug("Kafka health check failed - no brokers available",
                        bootstrap_servers=bootstrap_servers)
            return False
        except KafkaError as e:
            logger.debug("Kafka health check failed - Kafka error",
                        bootstrap_servers=bootstrap_servers,
                        error=str(e))
            return False
        except Exception as e:
            logger.debug("Kafka health check failed - unexpected error",
                        bootstrap_servers=bootstrap_servers,
                        error=str(e))
            return False

    async def check(self, config: dict[str, Any]) -> bool:
        """Check Kafka connectivity via bootstrap servers.

        Args:
            config: Configuration containing bootstrap_servers and other options

        Returns:
            True if Kafka is healthy, False otherwise
        """
        bootstrap_servers = config.get('bootstrap_servers', 'localhost:9092')
        timeout = config.get('timeout', 10.0)

        try:
            # Import kafka-python here to make it optional
            try:
                from kafka import KafkaConsumer
                from kafka.errors import KafkaError, NoBrokersAvailable
            except ImportError:
                logger.error("kafka-python not installed. Install with: pip install kafka-python")
                return False

            # Run the blocking Kafka operations in a thread pool
            return await asyncio.get_event_loop().run_in_executor(
                None, self._check_kafka_sync, bootstrap_servers, timeout
            )

        except Exception as e:
            logger.debug("Kafka health check failed",
                        bootstrap_servers=bootstrap_servers,
                        error=str(e))
            return False

    async def check_topic_exists(self, config: dict[str, Any], topic_name: str) -> bool:
        """Check if a specific Kafka topic exists.

        Args:
            config: Configuration containing bootstrap_servers
            topic_name: Name of the topic to check

        Returns:
            True if topic exists, False otherwise
        """
        bootstrap_servers = config.get('bootstrap_servers', 'localhost:9092')

        try:

            return await asyncio.get_event_loop().run_in_executor(
                None, self._check_topic_sync, bootstrap_servers, topic_name
            )

        except Exception as e:
            logger.debug("Kafka topic check failed",
                        topic=topic_name,
                        bootstrap_servers=bootstrap_servers,
                        error=str(e))
            return False

    def _check_topic_sync(self, bootstrap_servers: str, topic_name: str, timeout: float = 10.0) -> bool:
        """Synchronous Kafka topic existence check.

        Args:
            bootstrap_servers: Comma-separated list of bootstrap servers
            topic_name: Name of the topic to check
            timeout: Connection timeout in seconds

        Returns:
            True if topic exists, False otherwise
        """
        try:
            from kafka import KafkaConsumer

            consumer = KafkaConsumer(
                bootstrap_servers=bootstrap_servers.split(','),
                consumer_timeout_ms=int(timeout * 1000),
                api_version_auto_timeout_ms=int(timeout * 1000),
                request_timeout_ms=int(timeout * 1000),
                enable_auto_commit=False
            )

            try:
                # Get topic metadata
                topics = consumer.topics()
                exists = topic_name in topics

                logger.debug("Kafka topic check completed",
                            topic=topic_name,
                            exists=exists,
                            available_topics=len(topics))
                return exists

            finally:
                consumer.close()

        except Exception as e:
            logger.debug("Kafka topic check failed",
                        topic=topic_name,
                        error=str(e))
            return False

    async def check_producer_connectivity(self, config: dict[str, Any]) -> bool:
        """Check Kafka producer connectivity.

        Args:
            config: Configuration containing bootstrap_servers

        Returns:
            True if producer can connect, False otherwise
        """
        bootstrap_servers = config.get('bootstrap_servers', 'localhost:9092')

        try:

            return await asyncio.get_event_loop().run_in_executor(
                None, self._check_producer_sync, bootstrap_servers
            )

        except Exception as e:
            logger.debug("Kafka producer check failed",
                        bootstrap_servers=bootstrap_servers,
                        error=str(e))
            return False

    def _check_producer_sync(self, bootstrap_servers: str, timeout: float = 10.0) -> bool:
        """Synchronous Kafka producer connectivity check.

        Args:
            bootstrap_servers: Comma-separated list of bootstrap servers
            timeout: Connection timeout in seconds

        Returns:
            True if producer can connect, False otherwise
        """
        try:
            from kafka import KafkaProducer

            producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers.split(','),
                request_timeout_ms=int(timeout * 1000),
                api_version_auto_timeout_ms=int(timeout * 1000),
                # Don't actually send any messages
                max_block_ms=int(timeout * 1000)
            )

            try:
                # Try to get cluster metadata
                producer.partitions_for('__test_topic__')
                logger.debug("Kafka producer check passed",
                            bootstrap_servers=bootstrap_servers)
                return True

            finally:
                producer.close()

        except Exception as e:
            logger.debug("Kafka producer check failed",
                        bootstrap_servers=bootstrap_servers,
                        error=str(e))
            return False


    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate Kafka health check configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Validate optional bootstrap_servers
            bootstrap_servers = config.get('bootstrap_servers', 'localhost:9092')
            if not isinstance(bootstrap_servers, str) or not bootstrap_servers.strip():
                logger.error("Kafka health check invalid bootstrap_servers", bootstrap_servers=bootstrap_servers)
                return False

            # Validate optional timeout
            timeout = config.get('timeout', 10.0)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                logger.error("Kafka health check invalid timeout", timeout=timeout)
                return False

            return True

        except Exception as e:
            logger.error("Error validating Kafka health check config", error=str(e))
            return False

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for Kafka health checks.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "bootstrap_servers": "localhost:9092",
            "timeout": 10.0
        }

    def get_config_schema(self) -> Dict[str, Any]:
        """Get configuration schema for Kafka health checks.
        
        Returns:
            JSON schema for configuration validation
        """
        return {
            "type": "object",
            "properties": {
                "bootstrap_servers": {
                    "type": "string",
                    "default": "localhost:9092",
                    "description": "Comma-separated list of Kafka bootstrap servers"
                },
                "timeout": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 300,
                    "default": 10.0,
                    "description": "Connection timeout in seconds"
                }
            },
            "additionalProperties": False
        }


# Convenience function for simple health checks
async def check_kafka_health(
    bootstrap_servers: str = 'localhost:9092',
    timeout: float = 10.0
) -> bool:
    """Simple Kafka health check function.

    Args:
        bootstrap_servers: Comma-separated list of bootstrap servers
        timeout: Connection timeout in seconds

    Returns:
        True if Kafka is healthy, False otherwise
    """
    health_check = KafkaHealthCheck()
    config = {'bootstrap_servers': bootstrap_servers, 'timeout': timeout}
    result = await health_check.check_health(config)
    return result.status.value == 'healthy'
