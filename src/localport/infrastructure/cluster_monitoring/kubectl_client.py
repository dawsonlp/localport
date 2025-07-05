"""
Kubectl client wrapper for cluster monitoring.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import subprocess
import shlex

from ...domain.entities.cluster_info import ClusterInfo
from ...domain.entities.cluster_event import ClusterEvent, EventType
from ...domain.entities.resource_status import (
    ResourceStatus, ResourcePhase, ResourceType, ResourceCondition
)


logger = logging.getLogger(__name__)


class KubectlClient:
    """
    Wrapper for kubectl commands with proper error handling and parsing.
    
    This client provides a clean interface for executing kubectl commands
    and parsing their output into domain entities.
    """
    
    def __init__(self, timeout: int = 30, retry_attempts: int = 2):
        """
        Initialize the kubectl client.
        
        Args:
            timeout: Command timeout in seconds (default: 30)
            retry_attempts: Number of retry attempts for failed commands (default: 2)
        """
        self.timeout = timeout
        self.retry_attempts = retry_attempts
    
    async def get_cluster_info(self, context: str) -> ClusterInfo:
        """
        Get basic cluster information using kubectl cluster-info.
        
        Args:
            context: Cluster context name
            
        Returns:
            ClusterInfo: Basic cluster information
            
        Raises:
            KubectlError: If kubectl command fails
        """
        try:
            # Execute kubectl cluster-info
            cmd = ["kubectl", "cluster-info", "--context", context, "--request-timeout=30s"]
            stdout, stderr, returncode = await self._execute_command(cmd)
            
            if returncode != 0:
                error_msg = stderr.strip() if stderr else "Unknown error"
                return ClusterInfo(
                    context=context,
                    is_reachable=False,
                    error_message=error_msg,
                    last_check_time=datetime.utcnow()
                )
            
            # Parse cluster-info output
            api_server_url = None
            cluster_version = None
            core_services_healthy = True
            
            for line in stdout.split('\n'):
                line = line.strip()
                if 'Kubernetes control plane' in line or 'Kubernetes master' in line:
                    # Extract API server URL
                    if 'https://' in line:
                        start = line.find('https://')
                        end = line.find(' ', start) if ' ' in line[start:] else len(line)
                        api_server_url = line[start:end]
                elif 'is running at' not in line and line and not line.startswith('To'):
                    # Check if any core services are not running
                    if 'is not running' in line.lower() or 'error' in line.lower():
                        core_services_healthy = False
            
            # Try to get cluster version (handle kubectl version compatibility)
            try:
                # Try new format first (kubectl v1.28+)
                version_cmd = ["kubectl", "version", "--context", context, "--output=json"]
                version_stdout, _, version_returncode = await self._execute_command(version_cmd)
                
                if version_returncode == 0:
                    try:
                        version_data = json.loads(version_stdout)
                        server_version = version_data.get('serverVersion', {})
                        if server_version:
                            cluster_version = server_version.get('gitVersion', '').replace('v', '')
                    except json.JSONDecodeError:
                        # Fallback to parsing text output
                        for line in version_stdout.split('\n'):
                            if 'Server Version' in line:
                                cluster_version = line.split(':')[-1].strip()
                                break
                else:
                    # Fallback to older format for compatibility
                    version_cmd = ["kubectl", "version", "--context", context]
                    version_stdout, _, version_returncode = await self._execute_command(version_cmd)
                    if version_returncode == 0:
                        for line in version_stdout.split('\n'):
                            if 'Server Version' in line:
                                cluster_version = line.split(':')[-1].strip()
                                break
            except Exception as e:
                logger.debug(f"Failed to get cluster version for {context}: {e}")
            
            return ClusterInfo(
                context=context,
                api_server_url=api_server_url,
                cluster_version=cluster_version,
                is_reachable=True,
                core_services_healthy=core_services_healthy,
                last_check_time=datetime.utcnow(),
                raw_cluster_info={'stdout': stdout, 'stderr': stderr}
            )
            
        except Exception as e:
            logger.error(f"Failed to get cluster info for {context}: {e}")
            return ClusterInfo(
                context=context,
                is_reachable=False,
                error_message=str(e),
                last_check_time=datetime.utcnow()
            )
    
    async def get_pod_statuses(self, context: str) -> List[ResourceStatus]:
        """
        Get status of all active pods in the cluster.
        
        Args:
            context: Cluster context name
            
        Returns:
            List[ResourceStatus]: List of pod statuses
            
        Raises:
            KubectlError: If kubectl command fails
        """
        try:
            cmd = [
                "kubectl", "get", "pods", "-A", 
                "--field-selector=status.phase!=Succeeded",
                "--output=json",
                "--context", context
            ]
            
            stdout, stderr, returncode = await self._execute_command(cmd)
            
            if returncode != 0:
                logger.error(f"Failed to get pod statuses for {context}: {stderr}")
                return []
            
            # Parse JSON output
            data = json.loads(stdout)
            pod_statuses = []
            
            for item in data.get('items', []):
                try:
                    pod_status = self._parse_pod_status(item, context)
                    if pod_status:
                        pod_statuses.append(pod_status)
                except Exception as e:
                    logger.warning(f"Failed to parse pod status: {e}")
                    continue
            
            return pod_statuses
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse pod JSON for {context}: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to get pod statuses for {context}: {e}")
            return []
    
    async def get_node_statuses(self, context: str) -> List[ResourceStatus]:
        """
        Get status of all nodes in the cluster.
        
        Args:
            context: Cluster context name
            
        Returns:
            List[ResourceStatus]: List of node statuses
            
        Raises:
            KubectlError: If kubectl command fails
        """
        try:
            cmd = [
                "kubectl", "get", "nodes",
                "--output=json",
                "--context", context
            ]
            
            stdout, stderr, returncode = await self._execute_command(cmd)
            
            if returncode != 0:
                logger.error(f"Failed to get node statuses for {context}: {stderr}")
                return []
            
            # Parse JSON output
            data = json.loads(stdout)
            node_statuses = []
            
            for item in data.get('items', []):
                try:
                    node_status = self._parse_node_status(item, context)
                    if node_status:
                        node_statuses.append(node_status)
                except Exception as e:
                    logger.warning(f"Failed to parse node status: {e}")
                    continue
            
            return node_statuses
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse node JSON for {context}: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to get node statuses for {context}: {e}")
            return []
    
    async def get_cluster_events(self, context: str, limit: int = 50) -> List[ClusterEvent]:
        """
        Get recent cluster events.
        
        Args:
            context: Cluster context name
            limit: Maximum number of events to return
            
        Returns:
            List[ClusterEvent]: List of cluster events
            
        Raises:
            KubectlError: If kubectl command fails
        """
        try:
            # Build command without --limit flag for kubectl v1.28+ compatibility
            cmd = [
                "kubectl", "get", "events",
                "--sort-by=.lastTimestamp",
                "--output=json",
                "--context", context
            ]
            
            stdout, stderr, returncode = await self._execute_command(cmd)
            
            if returncode != 0:
                logger.error(f"Failed to get cluster events for {context}: {stderr}")
                return []
            
            # Parse JSON output
            data = json.loads(stdout)
            events = []
            
            # Apply limit manually since --limit flag is not available in newer kubectl versions
            items = data.get('items', [])
            limited_items = items[-limit:] if len(items) > limit else items
            
            for item in limited_items:
                try:
                    event = self._parse_cluster_event(item, context)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.warning(f"Failed to parse cluster event: {e}")
                    continue
            
            return events
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse events JSON for {context}: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to get cluster events for {context}: {e}")
            return []
    
    async def _execute_command(self, cmd: List[str]) -> Tuple[str, str, int]:
        """
        Execute a kubectl command with proper error handling and retries.
        
        Args:
            cmd: Command and arguments as a list
            
        Returns:
            Tuple[str, str, int]: (stdout, stderr, returncode)
            
        Raises:
            KubectlError: If command fails after all retries
        """
        last_error = None
        
        for attempt in range(self.retry_attempts + 1):
            try:
                logger.debug(f"Executing kubectl command (attempt {attempt + 1}): {' '.join(cmd)}")
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), 
                        timeout=self.timeout
                    )
                    
                    stdout_str = stdout.decode('utf-8') if stdout else ""
                    stderr_str = stderr.decode('utf-8') if stderr else ""
                    
                    logger.debug(f"Command completed with return code: {process.returncode}")
                    
                    return stdout_str, stderr_str, process.returncode
                    
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    last_error = f"Command timed out after {self.timeout} seconds"
                    logger.warning(f"kubectl command timed out: {' '.join(cmd)}")
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"kubectl command failed (attempt {attempt + 1}): {e}")
            
            # Wait before retry (exponential backoff)
            if attempt < self.retry_attempts:
                wait_time = 2 ** attempt
                logger.debug(f"Waiting {wait_time} seconds before retry...")
                await asyncio.sleep(wait_time)
        
        # All attempts failed
        error_msg = f"kubectl command failed after {self.retry_attempts + 1} attempts: {last_error}"
        logger.error(error_msg)
        raise KubectlError(error_msg)
    
    def _parse_pod_status(self, pod_data: Dict[str, Any], context: str) -> Optional[ResourceStatus]:
        """Parse pod data from kubectl JSON output."""
        try:
            metadata = pod_data.get('metadata', {})
            status = pod_data.get('status', {})
            
            name = metadata.get('name', 'unknown')
            namespace = metadata.get('namespace', 'default')
            
            # Parse phase
            phase_str = status.get('phase', 'Unknown')
            try:
                phase = ResourcePhase(phase_str)
            except ValueError:
                phase = ResourcePhase.UNKNOWN
            
            # Parse conditions
            conditions = []
            for cond_data in status.get('conditions', []):
                condition = ResourceCondition(
                    type=cond_data.get('type', ''),
                    status=cond_data.get('status', ''),
                    reason=cond_data.get('reason'),
                    message=cond_data.get('message'),
                    last_transition_time=self._parse_timestamp(cond_data.get('lastTransitionTime'))
                )
                conditions.append(condition)
            
            # Check if pod is ready
            ready = any(c.type == 'Ready' and c.status == 'True' for c in conditions)
            
            # Count restarts
            restart_count = 0
            for container_status in status.get('containerStatuses', []):
                restart_count += container_status.get('restartCount', 0)
            
            return ResourceStatus(
                name=name,
                namespace=namespace,
                resource_type=ResourceType.POD,
                phase=phase,
                context=context,
                creation_time=self._parse_timestamp(metadata.get('creationTimestamp')),
                last_check_time=datetime.utcnow(),
                ready=ready,
                restart_count=restart_count,
                conditions=conditions,
                node_name=status.get('hostIP'),
                pod_ip=status.get('podIP'),
                host_ip=status.get('hostIP'),
                raw_status=pod_data
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse pod status: {e}")
            return None
    
    def _parse_node_status(self, node_data: Dict[str, Any], context: str) -> Optional[ResourceStatus]:
        """Parse node data from kubectl JSON output."""
        try:
            metadata = node_data.get('metadata', {})
            status = node_data.get('status', {})
            
            name = metadata.get('name', 'unknown')
            
            # Parse conditions
            conditions = []
            for cond_data in status.get('conditions', []):
                condition = ResourceCondition(
                    type=cond_data.get('type', ''),
                    status=cond_data.get('status', ''),
                    reason=cond_data.get('reason'),
                    message=cond_data.get('message'),
                    last_transition_time=self._parse_timestamp(cond_data.get('lastTransitionTime'))
                )
                conditions.append(condition)
            
            # Check if node is ready
            ready = any(c.type == 'Ready' and c.status == 'True' for c in conditions)
            
            # Determine phase based on conditions
            if ready:
                phase = ResourcePhase.RUNNING
            else:
                phase = ResourcePhase.UNKNOWN
            
            return ResourceStatus(
                name=name,
                namespace='',  # Nodes don't have namespaces
                resource_type=ResourceType.NODE,
                phase=phase,
                context=context,
                creation_time=self._parse_timestamp(metadata.get('creationTimestamp')),
                last_check_time=datetime.utcnow(),
                ready=ready,
                conditions=conditions,
                raw_status=node_data
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse node status: {e}")
            return None
    
    def _parse_cluster_event(self, event_data: Dict[str, Any], context: str) -> Optional[ClusterEvent]:
        """Parse cluster event data from kubectl JSON output."""
        try:
            metadata = event_data.get('metadata', {})
            
            name = metadata.get('name', 'unknown')
            namespace = metadata.get('namespace', 'default')
            
            # Parse event type
            event_type_str = event_data.get('type', 'Normal')
            try:
                event_type = EventType(event_type_str)
            except ValueError:
                event_type = EventType.NORMAL
            
            reason = event_data.get('reason', '')
            message = event_data.get('message', '')
            
            # Parse involved object
            involved_object = event_data.get('involvedObject', {})
            
            return ClusterEvent(
                name=name,
                namespace=namespace,
                context=context,
                event_type=event_type,
                reason=reason,
                message=message,
                first_timestamp=self._parse_timestamp(event_data.get('firstTimestamp')),
                last_timestamp=self._parse_timestamp(event_data.get('lastTimestamp')),
                event_time=self._parse_timestamp(event_data.get('eventTime')),
                source_component=event_data.get('source', {}).get('component'),
                source_host=event_data.get('source', {}).get('host'),
                involved_object_kind=involved_object.get('kind'),
                involved_object_name=involved_object.get('name'),
                involved_object_namespace=involved_object.get('namespace'),
                involved_object_uid=involved_object.get('uid'),
                count=event_data.get('count', 1),
                reporting_controller=event_data.get('reportingController'),
                reporting_instance=event_data.get('reportingInstance'),
                raw_event=event_data
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse cluster event: {e}")
            return None
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse Kubernetes timestamp string to datetime."""
        if not timestamp_str:
            return None
        
        try:
            # Kubernetes uses RFC3339 format
            # Handle both with and without microseconds
            if '.' in timestamp_str:
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
            return None


class KubectlError(Exception):
    """Exception raised for kubectl command errors."""
    pass
