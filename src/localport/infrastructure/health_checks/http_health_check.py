"""HTTP health check implementation."""

import asyncio
from typing import Dict, Any, Optional
import structlog
from datetime import datetime
import aiohttp

from ...domain.entities.health_check import HealthCheckResult, HealthCheckStatus

logger = structlog.get_logger()


class HTTPHealthCheck:
    """HTTP health check implementation."""
    
    def __init__(self) -> None:
        """Initialize the HTTP health check."""
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def check(
        self, 
        url: str,
        method: str = "GET",
        timeout: float = 10.0,
        expected_status: int = 200,
        expected_text: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs: Any
    ) -> HealthCheckResult:
        """Perform HTTP health check.
        
        Args:
            url: URL to check
            method: HTTP method to use
            timeout: Request timeout in seconds
            expected_status: Expected HTTP status code
            expected_text: Expected text in response body
            headers: Additional headers to send
            **kwargs: Additional configuration (ignored)
            
        Returns:
            HealthCheckResult with the check outcome
        """
        start_time = datetime.now()
        
        try:
            # Ensure we have a session
            if not self._session:
                self._session = aiohttp.ClientSession()
            
            # Prepare request parameters
            request_headers = headers or {}
            timeout_config = aiohttp.ClientTimeout(total=timeout)
            
            logger.debug("Starting HTTP health check", 
                        url=url, 
                        method=method,
                        expected_status=expected_status)
            
            # Make the HTTP request
            async with self._session.request(
                method=method,
                url=url,
                headers=request_headers,
                timeout=timeout_config
            ) as response:
                
                # Calculate response time
                end_time = datetime.now()
                response_time_ms = (end_time - start_time).total_seconds() * 1000
                
                # Check status code
                if response.status != expected_status:
                    logger.debug("HTTP health check status mismatch", 
                                url=url,
                                expected_status=expected_status,
                                actual_status=response.status)
                    
                    return HealthCheckResult.unhealthy(
                        message=f"HTTP {method} {url} returned status {response.status}, expected {expected_status}",
                        error=f"Status code mismatch: {response.status} != {expected_status}"
                    )
                
                # Check response text if specified
                if expected_text:
                    try:
                        response_text = await response.text()
                        if expected_text not in response_text:
                            logger.debug("HTTP health check text mismatch", 
                                        url=url,
                                        expected_text=expected_text)
                            
                            return HealthCheckResult.unhealthy(
                                message=f"HTTP {method} {url} response does not contain expected text",
                                error=f"Expected text '{expected_text}' not found in response"
                            )
                    except Exception as e:
                        logger.debug("HTTP health check text read error", 
                                    url=url,
                                    error=str(e))
                        
                        return HealthCheckResult.unhealthy(
                            message=f"HTTP {method} {url} response text could not be read",
                            error=str(e)
                        )
                
                logger.debug("HTTP health check passed", 
                            url=url,
                            status=response.status,
                            response_time_ms=response_time_ms)
                
                return HealthCheckResult.healthy(
                    message=f"HTTP {method} {url} returned status {response.status}",
                    response_time_ms=response_time_ms
                )
                
        except asyncio.TimeoutError:
            logger.debug("HTTP health check timed out", 
                        url=url, 
                        timeout=timeout)
            
            return HealthCheckResult.unhealthy(
                message=f"HTTP {method} {url} timed out after {timeout}s",
                error="Request timeout"
            )
            
        except aiohttp.ClientConnectorError as e:
            logger.debug("HTTP health check connection error", 
                        url=url, 
                        error=str(e))
            
            return HealthCheckResult.unhealthy(
                message=f"HTTP {method} {url} connection failed",
                error=str(e)
            )
            
        except aiohttp.ClientError as e:
            logger.debug("HTTP health check client error", 
                        url=url, 
                        error=str(e))
            
            return HealthCheckResult.unhealthy(
                message=f"HTTP {method} {url} client error",
                error=str(e)
            )
            
        except Exception as e:
            logger.error("HTTP health check unexpected error", 
                        url=url, 
                        error=str(e))
            
            return HealthCheckResult.error(
                error=f"Unexpected error during HTTP health check: {e}"
            )
    
    async def check_with_config(self, config: Dict[str, Any]) -> HealthCheckResult:
        """Perform HTTP health check with configuration dictionary.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            HealthCheckResult with the check outcome
        """
        url = config['url']
        method = config.get('method', 'GET')
        timeout = config.get('timeout', 10.0)
        expected_status = config.get('expected_status', 200)
        expected_text = config.get('expected_text')
        headers = config.get('headers')
        
        return await self.check(
            url=url,
            method=method,
            timeout=timeout,
            expected_status=expected_status,
            expected_text=expected_text,
            headers=headers
        )
    
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
            
            # Basic URL validation
            if not (url.startswith('http://') or url.startswith('https://')):
                logger.error("HTTP health check URL must start with http:// or https://", url=url)
                return False
            
            # Validate optional method
            method = config.get('method', 'GET')
            valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS', 'PATCH']
            if method.upper() not in valid_methods:
                logger.error("HTTP health check invalid method", method=method)
                return False
            
            # Validate optional timeout
            timeout = config.get('timeout', 10.0)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                logger.error("HTTP health check invalid timeout", timeout=timeout)
                return False
            
            # Validate optional expected_status
            expected_status = config.get('expected_status', 200)
            if not isinstance(expected_status, int) or not 100 <= expected_status <= 599:
                logger.error("HTTP health check invalid expected_status", expected_status=expected_status)
                return False
            
            # Validate optional expected_text
            expected_text = config.get('expected_text')
            if expected_text is not None and not isinstance(expected_text, str):
                logger.error("HTTP health check invalid expected_text", expected_text=expected_text)
                return False
            
            # Validate optional headers
            headers = config.get('headers')
            if headers is not None:
                if not isinstance(headers, dict):
                    logger.error("HTTP health check invalid headers", headers=headers)
                    return False
                
                for key, value in headers.items():
                    if not isinstance(key, str) or not isinstance(value, str):
                        logger.error("HTTP health check invalid header", key=key, value=value)
                        return False
            
            return True
            
        except Exception as e:
            logger.error("Error validating HTTP health check config", error=str(e))
            return False
    
    async def check_endpoint_health(
        self, 
        host: str, 
        port: int, 
        path: str = "/health",
        use_https: bool = False,
        timeout: float = 10.0
    ) -> HealthCheckResult:
        """Check a standard health endpoint.
        
        Args:
            host: Host to check
            port: Port to check
            path: Health endpoint path
            use_https: Whether to use HTTPS
            timeout: Request timeout
            
        Returns:
            HealthCheckResult with the check outcome
        """
        scheme = "https" if use_https else "http"
        url = f"{scheme}://{host}:{port}{path}"
        
        return await self.check(url=url, timeout=timeout)
    
    async def check_multiple_endpoints(
        self, 
        endpoints: list[Dict[str, Any]]
    ) -> Dict[str, HealthCheckResult]:
        """Check multiple HTTP endpoints concurrently.
        
        Args:
            endpoints: List of endpoint configurations
            
        Returns:
            Dictionary mapping endpoint names to results
        """
        results = {}
        
        # Create tasks for concurrent checking
        tasks = []
        for endpoint in endpoints:
            name = endpoint.get('name', endpoint['url'])
            task = asyncio.create_task(self.check_with_config(endpoint))
            tasks.append((name, task))
        
        # Wait for all tasks to complete
        for name, task in tasks:
            try:
                result = await task
                results[name] = result
            except Exception as e:
                logger.error("Error checking endpoint", 
                           name=name, 
                           error=str(e))
                results[name] = HealthCheckResult.error(
                    error=f"Error checking endpoint: {e}"
                )
        
        return results
    
    async def cleanup(self) -> None:
        """Clean up HTTP session resources."""
        if self._session:
            await self._session.close()
            self._session = None
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for HTTP health checks.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "url": "http://localhost:8080/health",
            "method": "GET",
            "timeout": 10.0,
            "expected_status": 200
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
                    "pattern": "^https?://",
                    "description": "URL to check"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"],
                    "default": "GET",
                    "description": "HTTP method to use"
                },
                "timeout": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 300,
                    "default": 10.0,
                    "description": "Request timeout in seconds"
                },
                "expected_status": {
                    "type": "integer",
                    "minimum": 100,
                    "maximum": 599,
                    "default": 200,
                    "description": "Expected HTTP status code"
                },
                "expected_text": {
                    "type": "string",
                    "description": "Expected text in response body"
                },
                "headers": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "string"
                    },
                    "description": "Additional headers to send"
                }
            },
            "required": ["url"],
            "additionalProperties": False
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()
