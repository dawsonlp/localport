"""Interactive prompts for connection management."""

import asyncio
from typing import List, Optional

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table

import structlog

from ...domain.value_objects.discovery import DiscoveredPort

logger = structlog.get_logger()
console = Console()


class ConnectionPrompts:
    """Utility class for interactive prompts during connection management."""
    
    @staticmethod
    async def prompt_for_local_port(suggested: Optional[int] = None) -> int:
        """Prompt user for local port with optional suggestion.
        
        Args:
            suggested: Suggested port number
            
        Returns:
            Selected local port number
        """
        if suggested:
            console.print(f"\n[bold blue]Local Port Selection[/bold blue]")
            console.print(f"Suggested local port: [bold green]{suggested}[/bold green]")
            
            use_suggested = Confirm.ask(
                f"Use suggested port {suggested}?",
                default=True
            )
            
            if use_suggested:
                return suggested
        
        # Prompt for custom port
        while True:
            try:
                port = IntPrompt.ask(
                    "Enter local port",
                    default=suggested or 8080,
                    show_default=True
                )
                
                if 1 <= port <= 65535:
                    return port
                else:
                    console.print("[red]Error: Port must be between 1 and 65535[/red]")
                    
            except (ValueError, typer.Abort):
                console.print("[red]Error: Please enter a valid port number[/red]")
                continue

    @staticmethod
    async def prompt_for_namespace_selection(namespaces: List[str]) -> str:
        """Prompt user to select from multiple namespaces.
        
        Args:
            namespaces: List of available namespaces
            
        Returns:
            Selected namespace
        """
        console.print(f"\n[bold yellow]Multiple Namespaces Found[/bold yellow]")
        console.print("Resource found in multiple namespaces. Please select one:")
        
        # Create selection table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Namespace", style="green")
        
        for i, namespace in enumerate(namespaces, 1):
            table.add_row(str(i), namespace)
        
        console.print(table)
        
        while True:
            try:
                selection = IntPrompt.ask(
                    f"Select namespace (1-{len(namespaces)})",
                    choices=[str(i) for i in range(1, len(namespaces) + 1)]
                )
                
                return namespaces[selection - 1]
                
            except (ValueError, IndexError, typer.Abort):
                console.print(f"[red]Error: Please enter a number between 1 and {len(namespaces)}[/red]")
                continue

    @staticmethod
    async def prompt_for_port_selection(ports: List[DiscoveredPort]) -> DiscoveredPort:
        """Prompt user to select from multiple discovered ports.
        
        Args:
            ports: List of discovered ports
            
        Returns:
            Selected port
        """
        console.print(f"\n[bold blue]Port Selection[/bold blue]")
        console.print("Multiple ports available. Please select one:")
        
        # Create port selection table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=3)
        table.add_column("Port", style="green", width=6)
        table.add_column("Protocol", style="blue", width=8)
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        
        for i, port in enumerate(ports, 1):
            table.add_row(
                str(i),
                str(port.port),
                port.protocol,
                port.name or "-",
                port.description or "-"
            )
        
        console.print(table)
        
        # Auto-select if only one port
        if len(ports) == 1:
            console.print(f"[green]Auto-selecting the only available port: {ports[0].port}[/green]")
            return ports[0]
        
        while True:
            try:
                selection = IntPrompt.ask(
                    f"Select port (1-{len(ports)})",
                    choices=[str(i) for i in range(1, len(ports) + 1)]
                )
                
                return ports[selection - 1]
                
            except (ValueError, IndexError, typer.Abort):
                console.print(f"[red]Error: Please enter a number between 1 and {len(ports)}[/red]")
                continue

    @staticmethod
    async def prompt_for_ssh_host() -> str:
        """Prompt user for SSH hostname or IP address.
        
        Returns:
            SSH host
        """
        while True:
            host = Prompt.ask("Enter SSH hostname or IP address").strip()
            
            if host:
                return host
            else:
                console.print("[red]Error: Hostname cannot be empty[/red]")

    @staticmethod
    async def prompt_for_ssh_user() -> Optional[str]:
        """Prompt user for SSH username (optional).
        
        Returns:
            SSH username or None
        """
        user = Prompt.ask(
            "Enter SSH username (optional, press Enter to skip)",
            default=""
        ).strip()
        
        return user if user else None

    @staticmethod
    async def prompt_for_ssh_remote_port(default: int = 22) -> int:
        """Prompt user for SSH remote port.
        
        Args:
            default: Default SSH port
            
        Returns:
            SSH remote port
        """
        while True:
            try:
                port = IntPrompt.ask(
                    "Enter SSH port",
                    default=default,
                    show_default=True
                )
                
                if 1 <= port <= 65535:
                    return port
                else:
                    console.print("[red]Error: Port must be between 1 and 65535[/red]")
                    
            except (ValueError, typer.Abort):
                console.print("[red]Error: Please enter a valid port number[/red]")
                continue

    @staticmethod
    async def prompt_for_remote_port() -> int:
        """Prompt user for remote port (target port).
        
        Returns:
            Remote port number
        """
        while True:
            try:
                port = IntPrompt.ask("Enter remote port (target port)")
                
                if 1 <= port <= 65535:
                    return port
                else:
                    console.print("[red]Error: Port must be between 1 and 65535[/red]")
                    
            except (ValueError, typer.Abort):
                console.print("[red]Error: Please enter a valid port number[/red]")
                continue

    @staticmethod
    async def prompt_for_ssh_key_file() -> Optional[str]:
        """Prompt user for SSH key file path (optional).
        
        Returns:
            SSH key file path or None
        """
        key_file = Prompt.ask(
            "Enter path to SSH key file (optional, press Enter to skip)",
            default=""
        ).strip()
        
        return key_file if key_file else None

    @staticmethod
    async def prompt_for_service_name(suggested: Optional[str] = None) -> str:
        """Prompt user for service name with optional suggestion.
        
        Args:
            suggested: Suggested service name
            
        Returns:
            Service name
        """
        if suggested:
            console.print(f"\n[bold blue]Service Name[/bold blue]")
            console.print(f"Suggested name: [bold green]{suggested}[/bold green]")
            
            use_suggested = Confirm.ask(
                f"Use suggested name '{suggested}'?",
                default=True
            )
            
            if use_suggested:
                return suggested
        
        # Prompt for custom name
        while True:
            name = Prompt.ask(
                "Enter service name",
                default=suggested or ""
            ).strip()
            
            if name:
                return name
            else:
                console.print("[red]Error: Service name cannot be empty[/red]")

    @staticmethod
    async def confirm_service_removal(
        service_name: str,
        is_running: bool = False
    ) -> bool:
        """Prompt user to confirm service removal.
        
        Args:
            service_name: Name of service to remove
            is_running: Whether the service is currently running
            
        Returns:
            True if user confirms removal
        """
        console.print(f"\n[bold red]Remove Service Configuration[/bold red]")
        console.print(f"Service: [bold yellow]{service_name}[/bold yellow]")
        
        if is_running:
            console.print("[bold red]⚠️  WARNING: This service is currently running![/bold red]")
            console.print("You may want to stop the service first using: localport stop {service_name}")
        
        return Confirm.ask(
            f"Are you sure you want to remove '{service_name}' configuration?",
            default=False
        )

    @staticmethod
    async def prompt_for_kubectl_resource_name() -> str:
        """Prompt user for Kubernetes resource name.
        
        Returns:
            Resource name
        """
        while True:
            resource_name = Prompt.ask("Enter Kubernetes resource name").strip()
            
            if resource_name:
                return resource_name
            else:
                console.print("[red]Error: Resource name cannot be empty[/red]")

    @staticmethod
    async def prompt_for_kubectl_namespace(current_namespace: str) -> Optional[str]:
        """Prompt user for Kubernetes namespace.
        
        Args:
            current_namespace: Current context namespace
            
        Returns:
            Namespace or None to use current
        """
        console.print(f"\n[bold blue]Kubernetes Namespace[/bold blue]")
        console.print(f"Current namespace: [bold green]{current_namespace}[/bold green]")
        
        use_current = Confirm.ask(
            f"Use current namespace '{current_namespace}'?",
            default=True
        )
        
        if use_current:
            return None  # Use current namespace
        
        # Prompt for custom namespace
        namespace = Prompt.ask(
            "Enter namespace",
            default=""
        ).strip()
        
        return namespace if namespace else None

    @staticmethod
    def show_discovery_progress(resource_name: str, namespace: Optional[str] = None):
        """Show progress indicator for resource discovery.
        
        Args:
            resource_name: Resource being discovered
            namespace: Namespace being searched (optional)
        """
        if namespace:
            console.print(f"[dim]🔍 Discovering resource '{resource_name}' in namespace '{namespace}'...[/dim]")
        else:
            console.print(f"[dim]🔍 Discovering resource '{resource_name}' across all namespaces...[/dim]")

    @staticmethod
    def show_validation_progress(service_name: str):
        """Show progress indicator for service validation.
        
        Args:
            service_name: Service being validated
        """
        console.print(f"[dim]✓ Validating service configuration for '{service_name}'...[/dim]")

    @staticmethod
    def show_success_message(message: str):
        """Show a success message.
        
        Args:
            message: Success message to display
        """
        console.print(f"[bold green]✓ {message}[/bold green]")

    @staticmethod
    def show_warning_message(message: str):
        """Show a warning message.
        
        Args:
            message: Warning message to display
        """
        console.print(f"[bold yellow]⚠️  {message}[/bold yellow]")

    @staticmethod
    def show_info_message(message: str):
        """Show an info message.
        
        Args:
            message: Info message to display
        """
        console.print(f"[bold blue]ℹ️  {message}[/bold blue]")
