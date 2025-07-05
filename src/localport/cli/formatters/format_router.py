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
        # Create enhanced status table with better styling
        table = Table(
            title="🚀 LocalPort Service Status",
            title_style="bold blue",
            show_header=True,
            header_style="bold white on blue",
            border_style="blue",
            expand=False
        )
        
        # Add columns with improved styling and spacing
        table.add_column("Service", style="bold cyan", min_width=12)
        table.add_column("Status", style="bold", justify="center", min_width=10)
        table.add_column("Tech", style="dim cyan", justify="center", min_width=8)
        table.add_column("Local", style="bold green", justify="center", min_width=8)
        table.add_column("→ Target", style="yellow", min_width=15)
        table.add_column("Health", style="bold", justify="center", min_width=10)
        table.add_column("Uptime", style="dim white", justify="right", min_width=10)

        # Check if we have services to display
        if data.services:
            for service_info in data.services:
                # Get status string properly
                if hasattr(service_info.status, 'value'):
                    status_str = service_info.status.value
                else:
                    status_str = str(service_info.status)
                
                status_color = get_status_color(status_str)
                health_status = format_health_status(
                    service_info.is_healthy,
                    getattr(service_info, 'failure_count', 0)
                )

                # Enhanced target formatting
                target_port = service_info.remote_port
                technology = getattr(service_info, 'technology', 'kubectl')
                if technology == 'kubectl':
                    target = f"pod:{target_port}"
                elif technology == 'ssh':
                    target = f"ssh:{target_port}"
                else:
                    target = f"remote:{target_port}"

                # Add status icons for better visual clarity
                status_icon = "🟢" if status_str.lower() == "running" else "🔴" if status_str.lower() == "failed" else "🟡"
                
                table.add_row(
                    format_service_name(service_info.name),
                    f"{status_icon} [{status_color}]{status_str.title()}[/{status_color}]",
                    format_technology(technology),
                    f":{service_info.local_port}",
                    target,
                    health_status,
                    format_uptime(service_info.uptime_seconds or 0)
                )
        else:
            # Enhanced empty state message
            table.add_row(
                "[dim]No services configured[/dim]", 
                "[dim]—[/dim]", 
                "[dim]—[/dim]", 
                "[dim]—[/dim]", 
                "[dim]—[/dim]", 
                "[dim]—[/dim]", 
                "[dim]—[/dim]"
            )

        # Print the enhanced table
        self.console.print(table)

        # Enhanced summary with better formatting and helpful info
        if data.services:
            # Create summary with status indicators
            running_indicator = "🟢" if data.running_services > 0 else "🔴"
            healthy_indicator = "💚" if data.healthy_services == data.total_services else "💛" if data.healthy_services > 0 else "❤️"
            
            summary_parts = [
                f"📊 Total: [bold]{data.total_services}[/bold]",
                f"{running_indicator} Running: [bold green]{data.running_services}[/bold green]",
                f"{healthy_indicator} Healthy: [bold]{data.healthy_services}[/bold]"
            ]
            
            summary = " | ".join(summary_parts)
            self.console.print(f"\n{summary}")
            
            # Add helpful tips if there are issues
            if data.running_services == 0 and data.total_services > 0:
                self.console.print("\n[dim]💡 Tip: Start services with 'localport start --all' or 'localport daemon start'[/dim]")
            elif data.healthy_services < data.running_services:
                unhealthy_count = data.running_services - data.healthy_services
                self.console.print(f"\n[dim]⚠️  {unhealthy_count} service(s) may have health issues. Check logs with 'localport logs --list'[/dim]")
            else:
                # All services healthy - show log access tip
                self.console.print("\n[dim]📋 View service logs: 'localport logs --list' | Get log details: 'localport logs --service <name>'[/dim]")
        else:
            self.console.print("\n[dim]💡 Get started: Create a config with 'localport config init' or see 'localport --help'[/dim]")

        return ""  # Return empty string since we printed directly

    def _get_service_log_status(self, service_name: str, is_running: bool) -> str:
        """Get service log status for display.

        Args:
            service_name: Name of the service
            is_running: Whether the service is currently running

        Returns:
            Formatted log status string
        """
        try:
            from pathlib import Path
            import os
            
            # Get log directory path
            log_dir = Path.home() / ".local" / "share" / "localport" / "logs" / "services"
            
            if not log_dir.exists():
                return "[dim]—[/dim]"
            
            # Look for log files matching this service name
            log_files = list(log_dir.glob(f"{service_name}_*.log"))
            
            if not log_files:
                if is_running:
                    return "[yellow]📝[/yellow]"  # Service running but no logs yet
                else:
                    return "[dim]—[/dim]"  # Service not running, no logs
            
            # Check if we have recent log files
            recent_logs = []
            for log_file in log_files:
                try:
                    # Check if file was modified recently (within last hour)
                    import time
                    file_age = time.time() - log_file.stat().st_mtime
                    if file_age < 3600:  # 1 hour
                        recent_logs.append(log_file)
                except (OSError, AttributeError):
                    continue
            
            if recent_logs:
                return "[green]📋[/green]"  # Recent logs available
            elif log_files:
                return "[dim magenta]📋[/dim magenta]"  # Old logs available
            else:
                return "[dim]—[/dim]"
                
        except Exception:
            # If anything fails, just return a neutral indicator
            return "[dim]—[/dim]"

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
        # Create enhanced daemon status table
        table = Table(
            title="⚙️  LocalPort Daemon Status",
            title_style="bold blue",
            show_header=True,
            header_style="bold white on blue",
            border_style="blue",
            expand=False
        )
        
        table.add_column("Property", style="bold cyan", min_width=15)
        table.add_column("Value", style="white", min_width=20)

        # Check if we have status information
        if hasattr(data, 'status') and data.status:
            status_info = data.status
            is_running = getattr(status_info, 'running', False)

            # Add daemon information with enhanced formatting
            status_icon = "🟢" if is_running else "🔴"
            status_text = f"{status_icon} [green]Running[/green]" if is_running else f"{status_icon} [red]Stopped[/red]"
            table.add_row("Status", status_text)

            if is_running:
                if hasattr(status_info, 'pid') and status_info.pid:
                    table.add_row("Process ID", f"[bold]{status_info.pid}[/bold]")
                if hasattr(status_info, 'uptime_seconds') and status_info.uptime_seconds:
                    table.add_row("Uptime", f"[green]{format_uptime(status_info.uptime_seconds)}[/green]")
                if hasattr(status_info, 'active_services'):
                    service_count = status_info.active_services or 0
                    service_icon = "🚀" if service_count > 0 else "💤"
                    table.add_row("Active Services", f"{service_icon} [bold]{service_count}[/bold]")
                
                # Add helpful management commands
                table.add_row("", "")  # Spacer
                table.add_row("[dim]Management[/dim]", "[dim]Commands[/dim]")
                table.add_row("Stop daemon", "[dim]localport daemon stop[/dim]")
                table.add_row("View logs", "[dim]localport logs[/dim]")
                table.add_row("Service status", "[dim]localport status[/dim]")
            else:
                # Daemon is stopped - show helpful start commands
                table.add_row("", "")  # Spacer
                table.add_row("[dim]Quick Start[/dim]", "[dim]Commands[/dim]")
                table.add_row("Start daemon", "[dim]localport daemon start[/dim]")
                table.add_row("Start services", "[dim]localport start --all[/dim]")
                table.add_row("Get help", "[dim]localport --help[/dim]")
        else:
            # Fallback - show basic status based on success
            status_icon = "🔴"
            table.add_row("Status", f"{status_icon} [red]Stopped[/red]")
            message = getattr(data, 'message', 'Daemon is not running')
            table.add_row("Message", f"[dim]{message}[/dim]")
            
            # Add helpful start commands
            table.add_row("", "")  # Spacer
            table.add_row("[dim]Quick Start[/dim]", "[dim]Commands[/dim]")
            table.add_row("Start daemon", "[dim]localport daemon start[/dim]")
            table.add_row("Get help", "[dim]localport --help[/dim]")

        # Print the enhanced table directly
        self.console.print(table)

        return ""  # Return empty string since we printed directly

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
