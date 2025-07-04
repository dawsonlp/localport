"""TCP health check implementation."""

import asyncio
import socket
from datetime import datetime
from typing import Any, Dict

import structlog

from ...domain.entities.health_check import HealthCheckResult
from .base_health_checker import HealthChecker

logger = structlog.get_logger()


class TCPHealthCheck(HealthChecker):
    """TCP connectivity health check implementation."""

    def __init__(self) -> None:
        """Initialize the TCP health check."""
        pass

    async def check_health(self, config: Dict[str, Any]) -> HealthCheckResult:
        """Perform TCP health check with given configuration.
        
        Args:
            config: Configuration containing host, port, timeout
            
        Returns:
            HealthCheckResult with the check outcome
        """
        # Merge with defaults and validate
        merged_config = self.merge_with_defaults(config)
        
        host = merged_config.get('host', 'localhost')
        port = merged_config.get('port', 80)
        timeout = merged_config.get('timeout', 5.0)
        
        return await self.check(host=host, port=port, timeout=timeout)

    async def check(
        self,
        host: str = "localhost",
        port: int = 80,
        timeout: float = 5.0,
        **kwargs: Any
    ) -> HealthCheckResult:
        """Perform TCP health check.

        Args:
            host: Host to connect to
            port: Port to connect to
            timeout: Connection timeout in seconds
            **kwargs: Additional configuration (ignored)

        Returns:
            HealthCheckResult with the check outcome
        """
        start_time = datetime.now()

        try:
            # Create connection with timeout
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=timeout)

            # Calculate response time
            end_time = datetime.now()
            response_time_ms = (end_time - start_time).total_seconds() * 1000

            # Close connection immediately
            writer.close()
            await writer.wait_closed()

            logger.debug("TCP health check passed",
                        host=host,
                        port=port,
                        response_time_ms=response_time_ms)

            return HealthCheckResult.healthy(
                message=f"TCP connection to {host}:{port} successful",
                response_time_ms=response_time_ms
            )

        except TimeoutError:
            logger.debug("TCP health check timed out",
                        host=host,
                        port=port,
                        timeout=timeout)

            return HealthCheckResult.unhealthy(
                message=f"TCP connection to {host}:{port} timed out after {timeout}s",
                error="Connection timeout"
            )

        except ConnectionRefusedError:
            logger.debug("TCP health check connection refused",
                        host=host,
                        port=port)

            return HealthCheckResult.unhealthy(
                message=f"TCP connection to {host}:{port} refused",
                error="Connection refused"
            )

        except OSError as e:
            logger.debug("TCP health check OS error",
                        host=host,
                        port=port,
                        error=str(e))

            return HealthCheckResult.unhealthy(
                message=f"TCP connection to {host}:{port} failed",
                error=str(e)
            )

        except Exception as e:
            logger.error("TCP health check unexpected error",
                        host=host,
                        port=port,
                        error=str(e))

            return HealthCheckResult.error(
                error=f"Unexpected error during TCP health check: {e}"
            )

    async def check_with_config(self, config: dict[str, Any]) -> HealthCheckResult:
        """Perform TCP health check with configuration dictionary.

        Args:
            config: Configuration dictionary containing host, port, timeout

        Returns:
            HealthCheckResult with the check outcome
        """
        host = config.get('host', 'localhost')
        port = config.get('port', 80)
        timeout = config.get('timeout', 5.0)

        return await self.check(host=host, port=port, timeout=timeout)

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Validate TCP health check configuration.

        Args:
            config: Configuration to validate

        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required fields
            if 'port' not in config:
                logger.error("TCP health check missing required 'port' field")
                return False

            # Validate port
            port = config['port']
            if not isinstance(port, int) or not 1 <= port <= 65535:
                logger.error("TCP health check invalid port", port=port)
                return False

            # Validate optional host
            host = config.get('host', 'localhost')
            if not isinstance(host, str) or not host.strip():
                logger.error("TCP health check invalid host", host=host)
                return False

            # Validate optional timeout
            timeout = config.get('timeout', 5.0)
            if not isinstance(timeout, int | float) or timeout <= 0:
                logger.error("TCP health check invalid timeout", timeout=timeout)
                return False

            return True

        except Exception as e:
            logger.error("Error validating TCP health check config", error=str(e))
            return False

    async def check_port_available(self, port: int, host: str = "localhost") -> bool:
        """Check if a port is available (not in use).

        Args:
            port: Port to check
            host: Host to check on

        Returns:
            True if port is available, False if in use
        """
        try:
            # Try to bind to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            sock.close()
            return True

        except OSError:
            # Port is in use or cannot be bound
            return False
        except Exception as e:
            logger.error("Error checking port availability",
                        port=port,
                        host=host,
                        error=str(e))
            return False

    async def scan_port_range(
        self,
        start_port: int,
        end_port: int,
        host: str = "localhost",
        timeout: float = 1.0
    ) -> dict[int, bool]:
        """Scan a range of ports for connectivity.

        Args:
            start_port: Starting port number
            end_port: Ending port number (inclusive)
            host: Host to scan
            timeout: Timeout per port

        Returns:
            Dictionary mapping port numbers to connectivity status
        """
        results = {}

        # Create tasks for concurrent scanning
        tasks = []
        for port in range(start_port, end_port + 1):
            task = asyncio.create_task(self._check_single_port(host, port, timeout))
            tasks.append((port, task))

        # Wait for all tasks to complete
        for port, task in tasks:
            try:
                is_open = await task
                results[port] = is_open
            except Exception as e:
                logger.debug("Error scanning port",
                           port=port,
                           host=host,
                           error=str(e))
                results[port] = False

        return results

    async def _check_single_port(self, host: str, port: int, timeout: float) -> bool:
        """Check a single port for connectivity.

        Args:
            host: Host to check
            port: Port to check
            timeout: Connection timeout

        Returns:
            True if port is open, False otherwise
        """
        try:
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=timeout)
            writer.close()
            await writer.wait_closed()
            return True

        except (TimeoutError, ConnectionRefusedError, OSError):
            return False
        except Exception:
            return False

    def get_default_config(self) -> dict[str, Any]:
        """Get default configuration for TCP health checks.

        Returns:
            Default configuration dictionary
        """
        return {
            "host": "localhost",
            "port": 80,
            "timeout": 5.0
        }

    def get_config_schema(self) -> dict[str, Any]:
        """Get configuration schema for TCP health checks.

        Returns:
            JSON schema for configuration validation
        """
        return {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "default": "localhost",
                    "description": "Host to connect to"
                },
                "port": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 65535,
                    "description": "Port to connect to"
                },
                "timeout": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 300,
                    "default": 5.0,
                    "description": "Connection timeout in seconds"
                }
            },
            "required": ["port"],
            "additionalProperties": False
        }
