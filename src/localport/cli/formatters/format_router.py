"""Format routing for CLI output."""

from typing import Any

from rich.console import Console
from rich.table import Table

from ..utils.rich_utils import (
    format_health_status,
    format_port,
    format_service_name,
    format_technology,
    format_uptime,
    get_status_color,
)
from .json_formatter import (
    DaemonOperationJSONFormatter,
    DaemonStatusJSONFormatter,
    ServiceOperationJSONFormatter,
    ServiceStatusJSONFormatter,
)
from .output_format import OutputFormat


class FormatRouter:
    """Routes output formatting based on the requested format."""

    def __init__(self, console: Console):
        self.console = console

        # Initialize JSON formatters
        self.service_status_json = ServiceStatusJSONFormatter()
        self.service_operation_json = ServiceOperationJSONFormatter()
        self.daemon_status_json = DaemonStatusJSONFormatter()
        self.daemon_operation_json = DaemonOperationJSONFormatter()

    def format_service_status(self, data: Any, output_format: OutputFormat) -> str:
        """Format service status output.

        Args:
            data: ServiceSummary object
            output_format: Desired output format

        Returns:
            Formatted output string
        """
        if output_format == OutputFormat.JSON:
            return self.service_status_json.format(data)
        elif output_format == OutputFormat.TABLE:
            return self._format_service_status_table(data)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def format_service_operation(self, data: Any, output_format: OutputFormat, command_name: str) -> str:
        """Format service operation output.

        Args:
            data: Service operation result(s)
            output_format: Desired output format
            command_name: Name of the command that generated this output

        Returns:
            Formatted output string
        """
        if output_format == OutputFormat.JSON:
            return self.service_operation_json.format(data, command_name=command_name)
        elif output_format == OutputFormat.TABLE:
            return self._format_service_operation_table(data, command_name)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def format_daemon_status(self, data: Any, output_format: OutputFormat) -> str:
        """Format daemon status output.

        Args:
            data: Daemon status result
            output_format: Desired output format

        Returns:
            Formatted output string
        """
        if output_format == OutputFormat.JSON:
            return self.daemon_status_json.format(data)
        elif output_format == OutputFormat.TABLE:
            return self._format_daemon_status_table(data)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def format_daemon_operation(self, data: Any, output_format: OutputFormat, command_name: str) -> str:
        """Format daemon operation output.

        Args:
            data: Daemon operation result
            output_format: Desired output format
            command_name: Name of the command that generated this output

        Returns:
            Formatted output string
        """
        if output_format == OutputFormat.JSON:
            return self.daemon_operation_json.format(data, command_name=command_name)
        elif output_format == OutputFormat.TABLE:
            return self._format_daemon_operation_table(data, command_name)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def _format_service_status_table(self, data: Any) -> str:
        """Format service status as Rich table.

        Args:
            data: ServiceSummary object

        Returns:
            Rich table markup string
        """
        # Create status table
        table = Table(title="Service Status")
        table.add_column("Service", style="bold blue")
        table.add_column("Status", style="bold")
        table.add_column("Technology", style="cyan")
        table.add_column("Local Port", style="green")
        table.add_column("Target", style="yellow")
        table.add_column("Health", style="bold")
        table.add_column("Uptime", style="dim")

        # Check if we have services to display
        if data.services:
            for service_info in data.services:
                status_color = get_status_color(
                    service_info.status.value if hasattr(service_info.status, 'value')
                    else str(service_info.status)
                )
                health_status = format_health_status(
                    service_info.is_healthy,
                    getattr(service_info, 'failure_count', 0)
                )

                table.add_row(
                    format_service_name(service_info.name),
                    f"[{status_color}]{str(service_info.status).title()}[/{status_color}]",
                    format_technology(getattr(service_info, 'technology', 'kubectl')),
                    format_port(service_info.local_port),
                    f"remote:{service_info.remote_port}",
                    health_status,
                    format_uptime(service_info.uptime_seconds or 0)
                )
        else:
            table.add_row("No services found", "-", "-", "-", "-", "-", "-")

        # For table format, we should directly print to console, not capture
        # The FormatRouter should return a signal to print directly
        self.console.print(table)

        # Add summary
        summary = f"Total: {data.total_services} | Running: {data.running_services} | Healthy: {data.healthy_services}"
        self.console.print(f"\n[dim]{summary}[/dim]")

        return ""  # Return empty string since we printed directly

    def _format_service_operation_table(self, data: Any, command_name: str) -> str:
        """Format service operation as Rich table.

        Args:
            data: Service operation result(s)
            command_name: Command name

        Returns:
            Rich table markup string
        """
        # For now, return a simple success/failure message
        # This would be enhanced with actual table formatting
        if hasattr(data, 'success'):
            if data.success:
                return f"✓ Service {command_name} operation completed successfully"
            else:
                return f"✗ Service {command_name} operation failed: {getattr(data, 'error', 'Unknown error')}"
        else:
            return f"Service {command_name} operation completed"

    def _format_daemon_status_table(self, data: Any) -> str:
        """Format daemon status as Rich table.

        Args:
            data: Daemon status result

        Returns:
            Rich table markup string
        """
        # Create status table
        table = Table(title="Daemon Status")
        table.add_column("Property", style="bold blue")
        table.add_column("Value", style="white")

        # Check if we have status information
        if hasattr(data, 'status') and data.status:
            status_info = data.status
            is_running = getattr(status_info, 'running', False)

            # Add daemon information
            table.add_row("Status", "[green]Running[/green]" if is_running else "[red]Stopped[/red]")

            if is_running:
                if hasattr(status_info, 'pid') and status_info.pid:
                    table.add_row("PID", str(status_info.pid))
                if hasattr(status_info, 'uptime_seconds') and status_info.uptime_seconds:
                    table.add_row("Uptime", format_uptime(status_info.uptime_seconds))
                if hasattr(status_info, 'active_services'):
                    table.add_row("Active Services", str(status_info.active_services or 0))
        else:
            # Fallback - show basic status based on success
            table.add_row("Status", "[red]Stopped[/red]")
            table.add_row("Message", getattr(data, 'message', 'Daemon is not running'))

        # Capture table output
        with self.console.capture() as capture:
            self.console.print(table)

        return capture.get()

    def _format_daemon_operation_table(self, data: Any, command_name: str) -> str:
        """Format daemon operation as Rich table.

        Args:
            data: Daemon operation result
            command_name: Command name

        Returns:
            Rich table markup string
        """
        # For now, return a simple success/failure message
        if hasattr(data, 'success'):
            if data.success:
                message = getattr(data, 'message', f'Daemon {command_name} completed successfully')
                return f"✓ {message}"
            else:
                error = getattr(data, 'error', 'Unknown error')
                return f"✗ Daemon {command_name} failed: {error}"
        else:
            return f"Daemon {command_name} operation completed"
