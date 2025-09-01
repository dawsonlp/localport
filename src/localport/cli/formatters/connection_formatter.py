"""Formatters for connection management output."""

import json
from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table
from rich.text import Text

import structlog

from ...application.dto.connection_dto import ListConnectionsResponse
from ...domain.enums import ForwardingTechnology

logger = structlog.get_logger()


class ConnectionTableFormatter:
    """Formatter for connection list as Rich table."""
    
    def __init__(self, console: Console):
        """Initialize the table formatter.
        
        Args:
            console: Rich console for output
        """
        self.console = console
    
    def format_connections_list(self, response: ListConnectionsResponse) -> None:
        """Format connections list as a Rich table.
        
        Args:
            response: Response containing connections data
        """
        if not response.services:
            self.console.print("\n[yellow]No services configured.[/yellow]")
            self.console.print("Use 'localport config add' to add your first connection.")
            return
        
        # Create main table
        table = Table(
            title="📋 LocalPort Service Configurations",
            show_header=True,
            header_style="bold magenta",
            title_style="bold blue"
        )
        
        # Add columns
        table.add_column("Service", style="bold green", width=20)
        table.add_column("Technology", style="blue", width=10)
        table.add_column("Local Port", style="cyan", width=10)
        table.add_column("Remote Port", style="cyan", width=11)
        table.add_column("Target", style="white", width=25)
        table.add_column("Status", style="yellow", width=12)
        
        # Add rows
        for service in response.services:
            # Format technology
            tech_icon = "⚙️" if service.technology == "kubectl" else "🔗"
            technology = f"{tech_icon} {service.technology}"
            
            # Format ports
            local_port = f":{service.local_port}"
            remote_port = f":{service.remote_port}"
            
            # Format target based on technology
            if service.technology == "kubectl":
                connection = service.connection_params
                namespace = connection.get("namespace", "default")
                resource_name = connection.get("resource_name", "unknown")
                target = f"{namespace}/{resource_name}"
            elif service.technology == "ssh":
                connection = service.connection_params
                host = connection.get("host", "unknown")
                remote_host = connection.get("remote_host")
                if remote_host and remote_host != "localhost":
                    target = f"{host} → {remote_host}"
                else:
                    target = host
            else:
                target = "unknown"
            
            # Status (always "Configured" since these are just configurations)
            status = "[green]Configured[/green]"
            
            table.add_row(
                service.service_name,
                technology,
                local_port,
                remote_port,
                target,
                status
            )
        
        self.console.print("\n")
        self.console.print(table)
        
        # Add summary
        self._format_summary(response)
    
    def _format_summary(self, response: ListConnectionsResponse) -> None:
        """Format summary statistics.
        
        Args:
            response: Response containing connections data
        """
        self.console.print("\n")
        
        # Create summary table
        summary_table = Table(
            title="📊 Summary",
            show_header=False,
            title_style="bold blue",
            box=None
        )
        summary_table.add_column("Label", style="bold")
        summary_table.add_column("Value", style="green")
        
        # Total services
        summary_table.add_row("Total Services:", str(response.total_count))
        
        # Technology breakdown
        if response.technology_breakdown:
            for tech, count in response.technology_breakdown.items():
                tech_display = tech.title() if tech else "Unknown"
                summary_table.add_row(f"{tech_display}:", str(count))
        
        self.console.print(summary_table)
        
        # Add helpful commands
        self.console.print("\n[dim]💡 Helpful commands:[/dim]")
        self.console.print("[dim]  • localport config add     - Add new service[/dim]")
        self.console.print("[dim]  • localport start <name>  - Start a service[/dim]")
        self.console.print("[dim]  • localport status        - Check running services[/dim]")

    def format_add_success(
        self, 
        service_name: str, 
        technology: str,
        local_port: int,
        target_info: str
    ) -> None:
        """Format successful service addition.
        
        Args:
            service_name: Name of added service
            technology: Technology used (kubectl/ssh)
            local_port: Local port configured
            target_info: Target information
        """
        self.console.print("\n[bold green]✓ Service Added Successfully![/bold green]")
        
        # Create details table
        table = Table(
            title="Service Details",
            show_header=False,
            title_style="bold green",
            box=None
        )
        table.add_column("Field", style="bold blue")
        table.add_column("Value", style="white")
        
        table.add_row("Service Name:", service_name)
        table.add_row("Technology:", technology.title())
        table.add_row("Local Port:", f":{local_port}")
        table.add_row("Target:", target_info)
        
        self.console.print(table)
        
        # Add next steps
        self.console.print(f"\n[dim]💡 Next steps:[/dim]")
        self.console.print(f"[dim]  • localport start {service_name}  - Start the service[/dim]")
        self.console.print(f"[dim]  • localport status             - Check service status[/dim]")

    def format_remove_success(self, service_name: str, was_running: bool = False) -> None:
        """Format successful service removal.
        
        Args:
            service_name: Name of removed service
            was_running: Whether the service was running
        """
        self.console.print(f"\n[bold green]✓ Service '{service_name}' removed successfully![/bold green]")
        
        if was_running:
            self.console.print("[yellow]⚠️  Note: Service was running and has been stopped.[/yellow]")

    def format_discovery_info(
        self,
        resource_name: str,
        namespace: str,
        resource_type: str,
        available_ports: List[Dict[str, Any]]
    ) -> None:
        """Format discovered resource information.
        
        Args:
            resource_name: Name of discovered resource
            namespace: Namespace of resource
            resource_type: Type of resource (service, pod, etc.)
            available_ports: List of available ports
        """
        self.console.print(f"\n[bold blue]🔍 Resource Discovery Results[/bold blue]")
        
        # Resource info table
        info_table = Table(
            show_header=False,
            box=None
        )
        info_table.add_column("Field", style="bold")
        info_table.add_column("Value", style="green")
        
        info_table.add_row("Resource Name:", resource_name)
        info_table.add_row("Namespace:", namespace)
        info_table.add_row("Resource Type:", resource_type.title())
        info_table.add_row("Available Ports:", str(len(available_ports)))
        
        self.console.print(info_table)
        
        # Ports table if multiple ports
        if len(available_ports) > 1:
            self.console.print("\n[bold]Available Ports:[/bold]")
            
            ports_table = Table(show_header=True, header_style="bold magenta")
            ports_table.add_column("Port", style="green", width=8)
            ports_table.add_column("Protocol", style="blue", width=10)
            ports_table.add_column("Name", style="cyan")
            ports_table.add_column("Description", style="white")
            
            for port_info in available_ports:
                ports_table.add_row(
                    str(port_info.get("port", "unknown")),
                    port_info.get("protocol", "TCP"),
                    port_info.get("name", "-"),
                    port_info.get("description", "-")
                )
            
            self.console.print(ports_table)


class ConnectionJsonFormatter:
    """Formatter for connection list as JSON."""
    
    def __init__(self, console: Console):
        """Initialize the JSON formatter.
        
        Args:
            console: Rich console for output
        """
        self.console = console
    
    def format_connections_list(self, response: ListConnectionsResponse) -> None:
        """Format connections list as JSON.
        
        Args:
            response: Response containing connections data
        """
        # Convert response to dictionary
        output = {
            "total_count": response.total_count,
            "technology_breakdown": response.technology_breakdown,
            "services": []
        }
        
        for service in response.services:
            service_dict = {
                "name": service.service_name,
                "technology": service.technology,
                "local_port": service.local_port,
                "remote_port": service.remote_port,
                "connection_params": service.connection_params,
                "tags": getattr(service, 'tags', []),
                "description": getattr(service, 'description', None)
            }
            output["services"].append(service_dict)
        
        # Pretty print JSON
        json_output = json.dumps(output, indent=2, ensure_ascii=False)
        self.console.print(json_output)
    
    def format_add_success(
        self, 
        service_name: str, 
        technology: str,
        local_port: int,
        target_info: str
    ) -> None:
        """Format successful service addition as JSON.
        
        Args:
            service_name: Name of added service
            technology: Technology used (kubectl/ssh)
            local_port: Local port configured
            target_info: Target information
        """
        output = {
            "success": True,
            "action": "add_service",
            "service": {
                "name": service_name,
                "technology": technology,
                "local_port": local_port,
                "target": target_info
            },
            "message": f"Service '{service_name}' added successfully"
        }
        
        json_output = json.dumps(output, indent=2, ensure_ascii=False)
        self.console.print(json_output)
    
    def format_remove_success(self, service_name: str, was_running: bool = False) -> None:
        """Format successful service removal as JSON.
        
        Args:
            service_name: Name of removed service
            was_running: Whether the service was running
        """
        output = {
            "success": True,
            "action": "remove_service",
            "service_name": service_name,
            "was_running": was_running,
            "message": f"Service '{service_name}' removed successfully"
        }
        
        json_output = json.dumps(output, indent=2, ensure_ascii=False)
        self.console.print(json_output)
    
    def format_discovery_info(
        self,
        resource_name: str,
        namespace: str,
        resource_type: str,
        available_ports: List[Dict[str, Any]]
    ) -> None:
        """Format discovered resource information as JSON.
        
        Args:
            resource_name: Name of discovered resource
            namespace: Namespace of resource
            resource_type: Type of resource (service, pod, etc.)
            available_ports: List of available ports
        """
        output = {
            "discovery_result": {
                "resource_name": resource_name,
                "namespace": namespace,
                "resource_type": resource_type,
                "available_ports": available_ports
            }
        }
        
        json_output = json.dumps(output, indent=2, ensure_ascii=False)
        self.console.print(json_output)


class ConnectionFormatterFactory:
    """Factory for creating connection formatters."""
    
    @staticmethod
    def create_formatter(output_format: str, console: Console):
        """Create appropriate formatter based on output format.
        
        Args:
            output_format: Format type ('table' or 'json')
            console: Rich console for output
            
        Returns:
            Appropriate formatter instance
        """
        if output_format.lower() == 'json':
            return ConnectionJsonFormatter(console)
        else:
            return ConnectionTableFormatter(console)
