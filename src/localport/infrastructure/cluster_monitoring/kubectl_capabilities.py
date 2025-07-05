"""
kubectl capability detection for version-resilient Kubernetes operations.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Set, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class KubectlCapability:
    """Represents a specific kubectl capability."""
    name: str
    supported: bool
    tested_at: datetime
    alternative: Optional[str] = None
    error_message: Optional[str] = None


class KubectlCapabilities:
    """
    Runtime detection and caching of kubectl capabilities.
    
    This class implements capability-based command construction instead of
    version-based branching, making LocalPort resilient to kubectl changes.
    """
    
    def __init__(self, timeout: int = 10, cache_duration_minutes: int = 60):
        """
        Initialize capability detector.
        
        Args:
            timeout: Command timeout in seconds
            cache_duration_minutes: How long to cache capability results
        """
        self.timeout = timeout
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self._capabilities_cache: Dict[str, Dict[str, KubectlCapability]] = {}
        
    async def detect_capabilities(self, context: str) -> Dict[str, KubectlCapability]:
        """
        Detect kubectl capabilities for a specific context.
        
        Args:
            context: Kubernetes context name
            
        Returns:
            Dict[str, KubectlCapability]: Mapping of capability names to results
        """
        # Check cache first
        if self._is_cache_valid(context):
            logger.debug(f"Using cached capabilities for context: {context}")
            return self._capabilities_cache[context]
        
        logger.info(f"Detecting kubectl capabilities for context: {context}")
        
        # Run capability tests in parallel for efficiency
        capability_tests = {
            'events_limit_flag': self._test_events_limit_flag(context),
            'version_json_output': self._test_version_json_output(context),
            'version_short_flag': self._test_version_short_flag(context),
            'api_resources_verbs': self._test_api_resources_verbs(context),
            'cluster_info_command': self._test_cluster_info_command(context),
            'get_events_sort': self._test_get_events_sort(context),
        }
        
        # Execute all tests concurrently
        results = await asyncio.gather(
            *capability_tests.values(),
            return_exceptions=True
        )
        
        # Build capability map
        capabilities = {}
        for (name, _), result in zip(capability_tests.items(), results):
            if isinstance(result, Exception):
                capabilities[name] = KubectlCapability(
                    name=name,
                    supported=False,
                    tested_at=datetime.utcnow(),
                    error_message=str(result)
                )
            else:
                capabilities[name] = result
        
        # Cache results
        self._capabilities_cache[context] = capabilities
        
        logger.info(f"Capability detection complete for {context}",
                   extra={
                       "supported_capabilities": [name for name, cap in capabilities.items() if cap.supported],
                       "unsupported_capabilities": [name for name, cap in capabilities.items() if not cap.supported]
                   })
        
        return capabilities
    
    def get_capability(self, context: str, capability_name: str) -> Optional[KubectlCapability]:
        """
        Get a specific capability for a context.
        
        Args:
            context: Kubernetes context name
            capability_name: Name of the capability to check
            
        Returns:
            KubectlCapability or None if not found
        """
        context_capabilities = self._capabilities_cache.get(context, {})
        return context_capabilities.get(capability_name)
    
    def supports_capability(self, context: str, capability_name: str) -> bool:
        """
        Check if a capability is supported for a context.
        
        Args:
            context: Kubernetes context name
            capability_name: Name of the capability to check
            
        Returns:
            bool: True if capability is supported
        """
        capability = self.get_capability(context, capability_name)
        return capability.supported if capability else False
    
    async def _test_events_limit_flag(self, context: str) -> KubectlCapability:
        """Test if --limit flag is supported for kubectl get events."""
        try:
            cmd = [
                "kubectl", "get", "events",
                "--context", context,
                "--limit=1",
                "--dry-run=client",
                "--output=json"
            ]
            
            stdout, stderr, returncode = await self._execute_test_command(cmd)
            
            supported = returncode == 0 and "unknown flag" not in stderr.lower()
            
            return KubectlCapability(
                name="events_limit_flag",
                supported=supported,
                tested_at=datetime.utcnow(),
                alternative="manual_limiting" if not supported else None,
                error_message=stderr if not supported else None
            )
            
        except Exception as e:
            return KubectlCapability(
                name="events_limit_flag",
                supported=False,
                tested_at=datetime.utcnow(),
                alternative="manual_limiting",
                error_message=str(e)
            )
    
    async def _test_version_json_output(self, context: str) -> KubectlCapability:
        """Test if kubectl version supports --output=json."""
        try:
            cmd = [
                "kubectl", "version",
                "--context", context,
                "--output=json",
                "--client"
            ]
            
            stdout, stderr, returncode = await self._execute_test_command(cmd)
            
            supported = returncode == 0
            if supported:
                try:
                    json.loads(stdout)
                except json.JSONDecodeError:
                    supported = False
            
            return KubectlCapability(
                name="version_json_output",
                supported=supported,
                tested_at=datetime.utcnow(),
                alternative="text_parsing" if not supported else None,
                error_message=stderr if not supported else None
            )
            
        except Exception as e:
            return KubectlCapability(
                name="version_json_output",
                supported=False,
                tested_at=datetime.utcnow(),
                alternative="text_parsing",
                error_message=str(e)
            )
    
    async def _test_version_short_flag(self, context: str) -> KubectlCapability:
        """Test if kubectl version supports --short flag."""
        try:
            cmd = [
                "kubectl", "version",
                "--context", context,
                "--short",
                "--client"
            ]
            
            stdout, stderr, returncode = await self._execute_test_command(cmd)
            
            supported = returncode == 0 and "unknown flag" not in stderr.lower()
            
            return KubectlCapability(
                name="version_short_flag",
                supported=supported,
                tested_at=datetime.utcnow(),
                alternative="json_output" if not supported else None,
                error_message=stderr if not supported else None
            )
            
        except Exception as e:
            return KubectlCapability(
                name="version_short_flag",
                supported=False,
                tested_at=datetime.utcnow(),
                alternative="json_output",
                error_message=str(e)
            )
    
    async def _test_api_resources_verbs(self, context: str) -> KubectlCapability:
        """Test if kubectl api-resources supports --verbs flag."""
        try:
            cmd = [
                "kubectl", "api-resources",
                "--context", context,
                "--verbs=get",
                "--output=json"
            ]
            
            stdout, stderr, returncode = await self._execute_test_command(cmd)
            
            supported = returncode == 0 and "unknown flag" not in stderr.lower()
            
            return KubectlCapability(
                name="api_resources_verbs",
                supported=supported,
                tested_at=datetime.utcnow(),
                alternative="basic_api_resources" if not supported else None,
                error_message=stderr if not supported else None
            )
            
        except Exception as e:
            return KubectlCapability(
                name="api_resources_verbs",
                supported=False,
                tested_at=datetime.utcnow(),
                alternative="basic_api_resources",
                error_message=str(e)
            )
    
    async def _test_cluster_info_command(self, context: str) -> KubectlCapability:
        """Test if kubectl cluster-info works for the context."""
        try:
            cmd = [
                "kubectl", "cluster-info",
                "--context", context,
                "--request-timeout=10s"
            ]
            
            stdout, stderr, returncode = await self._execute_test_command(cmd)
            
            # cluster-info should work even if cluster is unreachable
            # We're testing command availability, not cluster connectivity
            supported = "unknown command" not in stderr.lower()
            
            return KubectlCapability(
                name="cluster_info_command",
                supported=supported,
                tested_at=datetime.utcnow(),
                alternative="version_only" if not supported else None,
                error_message=stderr if not supported else None
            )
            
        except Exception as e:
            return KubectlCapability(
                name="cluster_info_command",
                supported=False,
                tested_at=datetime.utcnow(),
                alternative="version_only",
                error_message=str(e)
            )
    
    async def _test_get_events_sort(self, context: str) -> KubectlCapability:
        """Test if kubectl get events supports --sort-by flag."""
        try:
            cmd = [
                "kubectl", "get", "events",
                "--context", context,
                "--sort-by=.lastTimestamp",
                "--dry-run=client",
                "--output=json"
            ]
            
            stdout, stderr, returncode = await self._execute_test_command(cmd)
            
            supported = returncode == 0 and "unknown flag" not in stderr.lower()
            
            return KubectlCapability(
                name="get_events_sort",
                supported=supported,
                tested_at=datetime.utcnow(),
                alternative="client_side_sorting" if not supported else None,
                error_message=stderr if not supported else None
            )
            
        except Exception as e:
            return KubectlCapability(
                name="get_events_sort",
                supported=False,
                tested_at=datetime.utcnow(),
                alternative="client_side_sorting",
                error_message=str(e)
            )
    
    async def _execute_test_command(self, cmd: list[str]) -> Tuple[str, str, int]:
        """
        Execute a test command with timeout.
        
        Args:
            cmd: Command and arguments as a list
            
        Returns:
            Tuple[str, str, int]: (stdout, stderr, returncode)
        """
        try:
            logger.debug(f"Testing kubectl capability: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout
            )
            
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""
            
            return stdout_str, stderr_str, process.returncode
            
        except asyncio.TimeoutError:
            if process:
                process.kill()
                await process.wait()
            raise Exception(f"Command timed out after {self.timeout} seconds")
        except Exception as e:
            raise Exception(f"Failed to execute test command: {e}")
    
    def _is_cache_valid(self, context: str) -> bool:
        """Check if cached capabilities are still valid."""
        if context not in self._capabilities_cache:
            return False
        
        # Check if any capability is expired
        for capability in self._capabilities_cache[context].values():
            if datetime.utcnow() - capability.tested_at > self.cache_duration:
                return False
        
        return True
    
    def clear_cache(self, context: Optional[str] = None):
        """
        Clear capability cache.
        
        Args:
            context: Specific context to clear, or None to clear all
        """
        if context:
            self._capabilities_cache.pop(context, None)
            logger.debug(f"Cleared capability cache for context: {context}")
        else:
            self._capabilities_cache.clear()
            logger.debug("Cleared all capability caches")
    
    def get_capability_summary(self, context: str) -> Dict[str, any]:
        """
        Get a summary of capabilities for a context.
        
        Args:
            context: Kubernetes context name
            
        Returns:
            Dict containing capability summary
        """
        capabilities = self._capabilities_cache.get(context, {})
        
        if not capabilities:
            return {"status": "not_detected", "capabilities": {}}
        
        supported = [name for name, cap in capabilities.items() if cap.supported]
        unsupported = [name for name, cap in capabilities.items() if not cap.supported]
        
        return {
            "status": "detected",
            "total_capabilities": len(capabilities),
            "supported_count": len(supported),
            "unsupported_count": len(unsupported),
            "supported_capabilities": supported,
            "unsupported_capabilities": unsupported,
            "last_detection": min(cap.tested_at for cap in capabilities.values()).isoformat(),
            "cache_valid_until": (min(cap.tested_at for cap in capabilities.values()) + self.cache_duration).isoformat()
        }


class KubectlCommandBuilder:
    """
    Build kubectl commands based on detected capabilities.
    
    This class uses capability detection to construct commands that work
    across different kubectl versions.
    """
    
    def __init__(self, capabilities: KubectlCapabilities):
        """
        Initialize command builder.
        
        Args:
            capabilities: Capability detector instance
        """
        self.capabilities = capabilities
    
    async def build_events_command(self, context: str, limit: int = 50) -> Tuple[list[str], Optional[int]]:
        """
        Build events command based on detected capabilities.
        
        Args:
            context: Kubernetes context name
            limit: Maximum number of events to return
            
        Returns:
            Tuple[list[str], Optional[int]]: (command, manual_limit)
            manual_limit is set if --limit flag is not supported
        """
        base_cmd = ["kubectl", "get", "events", "--context", context]
        manual_limit = None
        
        # Add sorting if supported
        if self.capabilities.supports_capability(context, "get_events_sort"):
            base_cmd.extend(["--sort-by=.lastTimestamp"])
        
        # Add limit if supported
        if self.capabilities.supports_capability(context, "events_limit_flag"):
            base_cmd.extend([f"--limit={limit}"])
        else:
            manual_limit = limit
        
        # Always add JSON output
        base_cmd.extend(["--output=json"])
        
        return base_cmd, manual_limit
    
    async def build_version_command(self, context: str) -> list[str]:
        """
        Build version command based on detected capabilities.
        
        Args:
            context: Kubernetes context name
            
        Returns:
            list[str]: kubectl version command
        """
        base_cmd = ["kubectl", "version", "--context", context]
        
        # Prefer JSON output if supported
        if self.capabilities.supports_capability(context, "version_json_output"):
            base_cmd.extend(["--output=json"])
        elif self.capabilities.supports_capability(context, "version_short_flag"):
            base_cmd.extend(["--short"])
        
        return base_cmd
    
    async def build_cluster_info_command(self, context: str) -> list[str]:
        """
        Build cluster-info command based on detected capabilities.
        
        Args:
            context: Kubernetes context name
            
        Returns:
            list[str]: kubectl cluster-info command
        """
        if self.capabilities.supports_capability(context, "cluster_info_command"):
            return [
                "kubectl", "cluster-info",
                "--context", context,
                "--request-timeout=30s"
            ]
        else:
            # Fallback to version command
            return await self.build_version_command(context)
