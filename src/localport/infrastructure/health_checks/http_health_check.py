"""HTTP health check implementation."""

from datetime import datetime
from typing import Any, Dict

import aiohttp
import structlog

from ...domain.entities.health_check import HealthCheckResult
from .base_health_checker import HealthChecker

logger = structlog.get_logger()


class HTTPHealthCheck(HealthChecker):
    """HTTP-based health check implementation."""

    def __init__(self):
        """Initialize HTTP health checker."""
        pass

    async def check_health(self, config: Dict[str, Any]) -> HealthCheckResult:
        """Perform HTTP health check with given configuration.
        
        Args:
            config: Configuration containing url, method, expected_status, etc.
            
        Returns:
            HealthCheckResult with the check outcome
        """
        # Merge with defaults and validate
        merged_config = self.merge_with_defaults(config)
        
        url = merged_config.get('url')
        if not url:
            return HealthCheckResult.error("HTTP health check missing required 'url' field")
        
        timeout = merged_config.get('timeout', 5.0)
        method = merged_config.get('method', 'GET').upper()
        expected_status_codes = merged_config.get('expected_status_codes', [200, 201, 202, 204])
        expected_content = merged_config.get('expected_content')
        headers = merged_config.get('headers', {})
        verify_ssl = merged_config.get('verify_ssl', True)
        
        return await self._perform_http_check(
            url=url,
            timeout=timeout,
            method=method,
            expected_status_codes=expected_status_codes,
            expected_content=expected_content,
            headers=headers,
            verify_ssl=verify_ssl
        )

    async def _perform_http_check(
        self,
        url: str,
        timeout: float,
        method: str,
        expected_status_codes: list[int],
        expected_content: str | None,
        headers: dict[str, str],
        verify_ssl: bool
    ) -> HealthCheckResult:
        """Perform the actual HTTP health check.
        
        Args:
            url: URL to check
            timeout: Request timeout
            method: HTTP method
            expected_status_codes: List of acceptable status codes
            expected_content: Expected content in response (optional)
            headers: Request headers
            verify_ssl: Whether to verify SSL certificates
            
        Returns:
            HealthCheckResult with the check outcome
        """
        start_time = datetime.now()
        
        try:
            connector = aiohttp.TCPConnector(
                ssl=verify_ssl,
                limit=1,
                limit_per_host=1
            )

            timeout_config = aiohttp.ClientTimeout(total=timeout)

            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout_config,
                headers=headers
            ) as session:

                async with session.request(method, url) as response:
                    # Calculate response time
                    end_time = datetime.now()
                    response_time_ms = (end_time - start_time).total_seconds() * 1000

                    # Check status code
                    if response.status not in expected_status_codes:
                        logger.debug("HTTP health check failed - unexpected status code",
                                   url=url,
                                   status_code=response.status,
                                   expected_codes=expected_status_codes)
                        return HealthCheckResult.unhealthy(
                            message=f"HTTP {method} {url} returned status {response.status}, expected one of {expected_status_codes}",
                            error=f"Unexpected status code: {response.status}"
                        )

                    # Check content if specified
                    if expected_content:
                        try:
                            content = await response.text()
                            if expected_content not in content:
                                logger.debug("HTTP health check failed - expected content not found",
                                           url=url,
                                           expected_content=expected_content)
                                return HealthCheckResult.unhealthy(
                                    message=f"HTTP {method} {url} response does not contain expected content",
                                    error=f"Expected content '{expected_content}' not found"
                                )
                        except Exception as e:
                            logger.debug("HTTP health check failed - error reading content",
                                       url=url,
                                       error=str(e))
                            return HealthCheckResult.unhealthy(
                                message=f"HTTP {method} {url} failed to read response content",
                                error=f"Content read error: {str(e)}"
                            )

                    logger.debug("HTTP health check passed",
                               url=url,
                               status_code=response.status,
                               response_time_ms=response_time_ms)
                    
                    return HealthCheckResult.healthy(
                        message=f"HTTP {method} {url} successful (status {response.status})",
                        response_time_ms=response_time_ms
                    )

        except TimeoutError:
            logger.debug("HTTP health check failed - timeout",
                       url=url,
                       timeout=timeout)
            return HealthCheckResult.unhealthy(
                message=f"HTTP {method} {url} timed out after {timeout}s",
                error="Request timeout"
            )
        except aiohttp.ClientError as e:
            logger.debug("HTTP health check failed - client error",
                       url=url,
                       error=str(e))
            return HealthCheckResult.unhealthy(
                message=f"HTTP {method} {url} client error",
                error=str(e)
            )
        except Exception as e:
            logger.error("HTTP health check failed - unexpected error",
                       url=url,
                       error=str(e))
            return HealthCheckResult.error(
                error=f"Unexpected error during HTTP health check: {e}"
            )

    async def check(self, url: str, timeout: float = 5.0, **kwargs) -> bool:
        """Perform HTTP health check.

        Args:
            url: URL to check
            timeout: Request timeout in seconds
            **kwargs: Additional arguments (ignored)

        Returns:
            True if the HTTP endpoint is healthy
        """
        try:
            connector = aiohttp.TCPConnector(
                ssl=self.verify_ssl,
                limit=1,
                limit_per_host=1
            )

            timeout_config = aiohttp.ClientTimeout(total=timeout)

            async with aiohttp.ClientSession(
                connector=connector,
                timeout=timeout_config,
                headers=self.headers
            ) as session:

                async with session.request(self.method, url) as response:
                    # Check status code
                    if response.status not in self.expected_status_codes:
                        logger.debug("HTTP health check failed - unexpected status code",
                                   url=url,
                                   status_code=response.status,
                                   expected_codes=self.expected_status_codes)
                        return False

                    # Check content if specified
                    if self.expected_content:
                        try:
                            content = await response.text()
                            if self.expected_content not in content:
                                logger.debug("HTTP health check failed - expected content not found",
                                           url=url,
                                           expected_content=self.expected_content)
                                return False
                        except Exception as e:
                            logger.debug("HTTP health check failed - error reading content",
                                       url=url,
                                       error=str(e))
                            return False

                    logger.debug("HTTP health check passed",
                               url=url,
                               status_code=response.status)
                    return True

        except TimeoutError:
            logger.debug("HTTP health check failed - timeout",
                       url=url,
                       timeout=timeout)
            return False
        except aiohttp.ClientError as e:
            logger.debug("HTTP health check failed - client error",
                       url=url,
                       error=str(e))
            return False
        except Exception as e:
            logger.debug("HTTP health check failed - unexpected error",
                       url=url,
                       error=str(e))
            return False

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate HTTP health check configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if configuration is valid, False otherwise
        """
        try:
            # Check required fields
            if 'url' not in config:
                logger.error("HTTP health check missing required 'url' field")
                return False

            # Validate URL
            url = config['url']
            if not isinstance(url, str) or not url.strip():
                logger.error("HTTP health check invalid URL", url=url)
                return False

            # Validate optional method
            method = config.get('method', 'GET')
            if not isinstance(method, str) or method.upper() not in ['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS']:
                logger.error("HTTP health check invalid method", method=method)
                return False

            # Validate optional timeout
            timeout = config.get('timeout', 5.0)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                logger.error("HTTP health check invalid timeout", timeout=timeout)
                return False

            # Validate optional expected_status_codes
            expected_codes = config.get('expected_status_codes', [200])
            if not isinstance(expected_codes, list) or not all(isinstance(code, int) and 100 <= code <= 599 for code in expected_codes):
                logger.error("HTTP health check invalid expected_status_codes", expected_codes=expected_codes)
                return False

            # Validate optional headers
            headers = config.get('headers', {})
            if not isinstance(headers, dict):
                logger.error("HTTP health check invalid headers", headers=headers)
                return False

            return True

        except Exception as e:
            logger.error("Error validating HTTP health check config", error=str(e))
            return False

    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for HTTP health checks.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "method": "GET",
            "timeout": 5.0,
            "expected_status_codes": [200, 201, 202, 204],
            "headers": {},
            "verify_ssl": True
        }

    def get_config_schema(self) -> Dict[str, Any]:
        """Get configuration schema for HTTP health checks.
        
        Returns:
            JSON schema for configuration validation
        """
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to check"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
                    "default": "GET",
                    "description": "HTTP method to use"
                },
                "timeout": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 300,
                    "default": 5.0,
                    "description": "Request timeout in seconds"
                },
                "expected_status_codes": {
                    "type": "array",
                    "items": {
                        "type": "integer",
                        "minimum": 100,
                        "maximum": 599
                    },
                    "default": [200, 201, 202, 204],
                    "description": "List of acceptable HTTP status codes"
                },
                "expected_content": {
                    "type": "string",
                    "description": "Expected content in response body (optional)"
                },
                "headers": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "string"
                    },
                    "default": {},
                    "description": "HTTP headers to send with request"
                },
                "verify_ssl": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to verify SSL certificates"
                }
            },
            "required": ["url"],
            "additionalProperties": False
        }
