"""HTTP health check implementation."""

from typing import Any

import aiohttp
import structlog

logger = structlog.get_logger()


class HTTPHealthCheck:
    """HTTP-based health check implementation."""

    def __init__(self, config: dict[str, Any]):
        """Initialize HTTP health checker.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.expected_status_codes = config.get('expected_status_codes', [200, 201, 202, 204])
        self.expected_content = config.get('expected_content')
        self.headers = config.get('headers', {})
        self.method = config.get('method', 'GET').upper()
        self.verify_ssl = config.get('verify_ssl', True)

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
