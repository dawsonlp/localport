"""JSON formatters for CLI output."""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

logger = structlog.get_logger()


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for LocalPort objects."""

    def default(self, obj: Any) -> Any:
        """Convert objects to JSON-serializable format.

        Args:
            obj: Object to serialize

        Returns:
            JSON-serializable representation
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, UUID):
            return str(obj)
        elif hasattr(obj, '__dict__'):
            # Handle dataclasses and other objects with __dict__
            return obj.__dict__
        elif hasattr(obj, 'value'):
            # Handle enums
            return obj.value
        else:
            return super().default(obj)


class BaseJSONFormatter(ABC):
    """Base class for JSON formatters."""

    def __init__(self):
        self.encoder = JSONEncoder()

    def format(self, data: Any, **kwargs) -> str:
        """Format data as JSON string.

        Args:
            data: Data to format
            **kwargs: Additional formatting options

        Returns:
            JSON-formatted string
        """
        try:
            json_data = self._prepare_data(data, **kwargs)
            return json.dumps(json_data, cls=JSONEncoder, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to format JSON output", error=str(e))
            return self._format_error("JSON formatting failed", str(e))

    @abstractmethod
    def _prepare_data(self, data: Any, **kwargs) -> dict[str, Any]:
        """Prepare data for JSON serialization.

        Args:
            data: Raw data to prepare
            **kwargs: Additional preparation options

        Returns:
            Dictionary ready for JSON serialization
        """
        pass

    def _format_error(self, error_type: str, message: str, details: dict[str, Any] | None = None) -> str:
        """Format an error as JSON.

        Args:
            error_type: Type of error
            message: Error message
            details: Optional error details

        Returns:
            JSON-formatted error string
        """
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "error": {
                "type": error_type,
                "message": message,
                "details": details
            }
        }

        try:
            return json.dumps(error_data, cls=JSONEncoder, indent=2, ensure_ascii=False)
        except Exception:
            # Fallback to minimal JSON if even error formatting fails
            return '{"success": false, "error": {"type": "formatting_error", "message": "Failed to format error as JSON"}}'

    def _add_metadata(self, data: dict[str, Any], command: str) -> dict[str, Any]:
        """Add common metadata to JSON output.

        Args:
            data: Data dictionary to enhance
            command: Command name that generated this output

        Returns:
            Enhanced data dictionary with metadata
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            **data
        }


class ServiceStatusJSONFormatter(BaseJSONFormatter):
    """JSON formatter for service status output."""

    def _prepare_data(self, data: Any, **kwargs) -> dict[str, Any]:
        """Prepare service status data for JSON serialization.

        Args:
            data: ServiceSummary object
            **kwargs: Additional options

        Returns:
            Dictionary ready for JSON serialization
        """
        # Extract summary information
        summary = {
            "total_services": data.total_services,
            "running_services": data.running_services,
            "stopped_services": data.stopped_services,
            "failed_services": data.failed_services,
            "healthy_services": data.healthy_services,
            "unhealthy_services": data.unhealthy_services,
            "success_rate": round(data.success_rate, 2) if hasattr(data, 'success_rate') else 0.0,
            "health_rate": round(data.health_rate, 2) if hasattr(data, 'health_rate') else 0.0
        }

        # Extract service details
        services = []
        for service_info in data.services:
            service_data = {
                "name": service_info.name,
                "status": str(service_info.status).lower(),
                "technology": getattr(service_info, 'technology', 'unknown'),
                "local_port": service_info.local_port,
                "remote_port": service_info.remote_port,
                "target": f"remote:{service_info.remote_port}",  # Simplified for now
                "is_healthy": service_info.is_healthy,
                "uptime_seconds": service_info.uptime_seconds or 0,
                "last_health_check": service_info.last_health_check.isoformat() if service_info.last_health_check else None,
                "failure_count": getattr(service_info, 'failure_count', 0),
                "restart_count": getattr(service_info, 'restart_count', 0),
                "tags": getattr(service_info, 'tags', []),
                "description": getattr(service_info, 'description', None)
            }
            services.append(service_data)

        return self._add_metadata({
            "summary": summary,
            "services": services
        }, "status")


class ServiceOperationJSONFormatter(BaseJSONFormatter):
    """JSON formatter for service start/stop operations."""

    def _prepare_data(self, data: Any, **kwargs) -> dict[str, Any]:
        """Prepare service operation data for JSON serialization.

        Args:
            data: Service operation result
            **kwargs: Additional options (command_name required)

        Returns:
            Dictionary ready for JSON serialization
        """
        command_name = kwargs.get('command_name', 'operation')

        # Handle different result types
        if hasattr(data, 'success'):
            # Single operation result
            results = [data]
            overall_success = data.success
        elif isinstance(data, list):
            # Multiple operation results
            results = data
            overall_success = all(getattr(r, 'success', False) for r in results)
        else:
            # Fallback for unknown data types
            results = []
            overall_success = False

        # Calculate summary
        successful_operations = sum(1 for r in results if getattr(r, 'success', False))
        failed_operations = len(results) - successful_operations

        summary = {
            "requested_services": len(results),
            "successful_operations": successful_operations,
            "failed_operations": failed_operations
        }

        # Format individual results
        formatted_results = []
        for result in results:
            result_data = {
                "service_name": getattr(result, 'service_name', 'unknown'),
                "success": getattr(result, 'success', False),
                "message": getattr(result, 'message', ''),
                "error": getattr(result, 'error', None),
                "process_id": getattr(result, 'process_id', None),
                "duration_ms": getattr(result, 'duration_ms', None)
            }
            formatted_results.append(result_data)

        return self._add_metadata({
            "success": overall_success,
            "summary": summary,
            "results": formatted_results
        }, command_name)


class DaemonStatusJSONFormatter(BaseJSONFormatter):
    """JSON formatter for daemon status output."""

    def _prepare_data(self, data: Any, **kwargs) -> dict[str, Any]:
        """Prepare daemon status data for JSON serialization.

        Args:
            data: Daemon status result
            **kwargs: Additional options

        Returns:
            Dictionary ready for JSON serialization
        """
        # Extract daemon information
        daemon_info = {
            "running": getattr(data, 'success', False),
            "pid": getattr(data, 'pid', None),
            "uptime_seconds": None,  # Would need to be calculated
            "config_file": getattr(data, 'config_file', None),
            "active_services": getattr(data, 'active_services', 0),
            "health_monitor_active": getattr(data, 'health_monitor_active', False),
            "last_reload": None  # Would need to be tracked
        }

        # Add status information if available
        if hasattr(data, 'status') and data.status:
            status_info = data.status
            daemon_info.update({
                "running": getattr(status_info, 'running', False),
                "pid": getattr(status_info, 'pid', None),
                "uptime_seconds": getattr(status_info, 'uptime_seconds', None),
                "active_services": getattr(status_info, 'active_services', 0)
            })

        return self._add_metadata({
            "daemon": daemon_info
        }, "daemon status")


class DaemonOperationJSONFormatter(BaseJSONFormatter):
    """JSON formatter for daemon management operations."""

    def _prepare_data(self, data: Any, **kwargs) -> dict[str, Any]:
        """Prepare daemon operation data for JSON serialization.

        Args:
            data: Daemon operation result
            **kwargs: Additional options (command_name required)

        Returns:
            Dictionary ready for JSON serialization
        """
        command_name = kwargs.get('command_name', 'daemon operation')

        daemon_info = {
            "pid": getattr(data, 'pid', None),
            "config_file": getattr(data, 'config_file', None),
            "auto_start_enabled": getattr(data, 'auto_start_enabled', False)
        }

        return self._add_metadata({
            "success": getattr(data, 'success', False),
            "message": getattr(data, 'message', ''),
            "daemon": daemon_info,
            "error": getattr(data, 'error', None)
        }, command_name)
