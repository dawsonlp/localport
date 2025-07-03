"""Kafka-specific health check implementation."""

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()


class KafkaHealthCheck:
    """Kafka-specific health check using bootstrap servers."""

    def __init__(self, timeout: float = 10.0):
        """Initialize Kafka health check.

        Args:
            timeout: Connection timeout in seconds
        """
        self.timeout = timeout

    async def check(self, config: dict[str, Any]) -> bool:
        """Check Kafka connectivity via bootstrap servers.

        Args:
            config: Configuration containing bootstrap_servers and other options

        Returns:
            True if Kafka is healthy, False otherwise
        """
        bootstrap_servers = config.get('bootstrap_servers', 'localhost:9092')

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
                None, self._check_kafka_sync, bootstrap_servers
            )

        except Exception as e:
            logger.debug("Kafka health check failed",
                        bootstrap_servers=bootstrap_servers,
                        error=str(e))
            return False

    def _check_kafka_sync(self, bootstrap_servers: str) -> bool:
        """Synchronous Kafka connectivity check.

        Args:
            bootstrap_servers: Comma-separated list of bootstrap servers

        Returns:
            True if connection successful, False otherwise
        """
        try:
            from kafka import KafkaConsumer
            from kafka.errors import KafkaError, NoBrokersAvailable

            # Create a consumer to test connectivity
            consumer = KafkaConsumer(
                bootstrap_servers=bootstrap_servers.split(','),
                consumer_timeout_ms=int(self.timeout * 1000),
                api_version_auto_timeout_ms=int(self.timeout * 1000),
                request_timeout_ms=int(self.timeout * 1000),
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

    def _check_topic_sync(self, bootstrap_servers: str, topic_name: str) -> bool:
        """Synchronous Kafka topic existence check.

        Args:
            bootstrap_servers: Comma-separated list of bootstrap servers
            topic_name: Name of the topic to check

        Returns:
            True if topic exists, False otherwise
        """
        try:
            from kafka import KafkaConsumer

            consumer = KafkaConsumer(
                bootstrap_servers=bootstrap_servers.split(','),
                consumer_timeout_ms=int(self.timeout * 1000),
                api_version_auto_timeout_ms=int(self.timeout * 1000),
                request_timeout_ms=int(self.timeout * 1000),
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

    def _check_producer_sync(self, bootstrap_servers: str) -> bool:
        """Synchronous Kafka producer connectivity check.

        Args:
            bootstrap_servers: Comma-separated list of bootstrap servers

        Returns:
            True if producer can connect, False otherwise
        """
        try:
            from kafka import KafkaProducer

            producer = KafkaProducer(
                bootstrap_servers=bootstrap_servers.split(','),
                request_timeout_ms=int(self.timeout * 1000),
                api_version_auto_timeout_ms=int(self.timeout * 1000),
                # Don't actually send any messages
                max_block_ms=int(self.timeout * 1000)
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
    health_check = KafkaHealthCheck(timeout=timeout)
    config = {'bootstrap_servers': bootstrap_servers}
    return await health_check.check(config)
