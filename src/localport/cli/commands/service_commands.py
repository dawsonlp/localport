"""Service management commands for LocalPort CLI."""

import asyncio
from typing import Optional, List
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import structlog

from ...application.use_cases.start_services import StartServicesUseCase
from ...application.use_cases.stop_services import StopServicesUseCase
from ...application.use_cases.monitor_services import MonitorServicesUseCase
from ...infrastructure.repositories.memory_service_repository import MemoryServiceRepository
from ...infrastructure.repositories.yaml_config_repository import YamlConfigRepository
from ...infrastructure.adapters.adapter_factory import AdapterFactory
from ...infrastructure.health_checks.health_check_factory import HealthCheckFactory
from ...application.services.service_manager import ServiceManager
from ..utils.rich_utils import (
    format_service_name, format_port, format_technology, format_health_status,
    get_status_color, format_uptime, create_error_panel, create_success_panel
)

logger = structlog.get_logger()
console = Console()


async def start_services_command(
    services: Optional[List[str]] = None,
    all_services: bool = False,
    tags: Optional[List[str]] = None,
    config_file: Optional[str] = None,
    force: bool = False
) -> None:
    """Start port forwarding services."""
    try:
        # Load configuration
        if config_file:
            config_path = Path(config_file)
        else:
            # Use default config discovery
            config_path = None
            for path in ["./localport.yaml", "~/.config/localport/config.yaml"]:
                test_path = Path(path).expanduser()
                if test_path.exists():
                    config_path = test_path
                    break
        
        if not config_path or not config_path.exists():
            console.print(create_error_panel(
                "Configuration Not Found",
                "No configuration file found. Please create a localport.yaml file in one of these locations:\n" +
                "• ./localport.yaml (current directory)\n" +
                "• ~/.config/localport/config.yaml (user config)\n" +
                "• ~/.localport.yaml (user home)\n" +
                "Or specify a custom path with --config.",
                "Run 'localport init' to create a sample configuration file."
            ))
            raise typer.Exit(1)
        
        # Initialize repositories and services with config path
        service_repo = MemoryServiceRepository()
        config_repo = YamlConfigRepository(str(config_path))
        adapter_factory = AdapterFactory()
        health_check_factory = HealthCheckFactory()
        service_manager = ServiceManager()
        
        # Load services from config
        config_data = await config_repo.load_configuration()
        
        # Initialize use case
        start_use_case = StartServicesUseCase(
            service_manager=service_manager,
            config_repository=config_repo
        )
        
        # Determine which services to start
        if all_services:
            service_names = None  # Start all services
        elif services:
            service_names = services
        elif tags:
            # Filter services by tags (would need to implement tag filtering)
            service_names = None  # For now, start all
        else:
            console.print("[yellow]No services specified. Use --all to start all services or specify service names.[/yellow]")
            raise typer.Exit(1)
        
        # Start services with progress indication
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Starting services...", total=None)
            
            result = await start_use_case.execute(
                service_names=service_names,
                force_restart=force
            )
            
            progress.update(task, completed=True)
        
        # Display results
        if result.success:
            console.print(create_success_panel(
                "Services Started",
                f"Successfully started {len(result.started_services)} service(s)"
            ))
            
            # Show started services table
            if result.started_services:
                table = Table(title="Started Services")
                table.add_column("Service", style="bold blue")
                table.add_column("Technology", style="cyan")
                table.add_column("Local Port", style="green")
                table.add_column("Target", style="yellow")
                table.add_column("Status", style="bold")
                
                for service_name in result.started_services:
                    # Get service details (would need to implement service lookup)
                    table.add_row(
                        format_service_name(service_name),
                        format_technology("kubectl"),  # Placeholder
                        format_port(8080),  # Placeholder
                        "pod/service:8080",  # Placeholder
                        "[green]Running[/green]"
                    )
                
                console.print(table)
        else:
            console.print(create_error_panel(
                "Failed to Start Services",
                result.error or "Unknown error occurred",
                "Check the logs for more details or try with --verbose flag."
            ))
            raise typer.Exit(1)
            
    except typer.Exit:
        # Re-raise typer.Exit to allow clean exit
        raise
    except Exception as e:
        logger.exception("Error starting services")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs in ~/.local/share/localport/logs/ or run with --verbose for more details."
        ))
        raise typer.Exit(1)


async def stop_services_command(
    services: Optional[List[str]] = None,
    all_services: bool = False,
    force: bool = False
) -> None:
    """Stop port forwarding services."""
    try:
        # Initialize repositories and services
        service_repo = MemoryServiceRepository()
        adapter_factory = AdapterFactory()
        health_check_factory = HealthCheckFactory()
        service_manager = ServiceManager()
        
        # Initialize use case
        stop_use_case = StopServicesUseCase(service_manager=service_manager)
        
        # Determine which services to stop
        if all_services:
            service_names = None  # Stop all services
        elif services:
            service_names = services
        else:
            console.print("[yellow]No services specified. Use --all to stop all services or specify service names.[/yellow]")
            raise typer.Exit(1)
        
        # Stop services with progress indication
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Stopping services...", total=None)
            
            result = await stop_use_case.execute(
                service_names=service_names,
                force=force
            )
            
            progress.update(task, completed=True)
        
        # Display results
        if result.success:
            console.print(create_success_panel(
                "Services Stopped",
                f"Successfully stopped {len(result.stopped_services)} service(s)"
            ))
        else:
            console.print(create_error_panel(
                "Failed to Stop Services",
                result.error or "Unknown error occurred",
                "Check the logs for more details or try with --force flag."
            ))
            raise typer.Exit(1)
            
    except typer.Exit:
        # Re-raise typer.Exit to allow clean exit
        raise
    except Exception as e:
        logger.exception("Error stopping services")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs in ~/.local/share/localport/logs/ or run with --verbose for more details."
        ))
        raise typer.Exit(1)


async def status_services_command(
    services: Optional[List[str]] = None,
    watch: bool = False,
    refresh_interval: int = 5
) -> None:
    """Show service status."""
    try:
        # Initialize repositories and services
        service_repo = MemoryServiceRepository()
        adapter_factory = AdapterFactory()
        health_check_factory = HealthCheckFactory()
        service_manager = ServiceManager()
        
        # Initialize use case
        monitor_use_case = MonitorServicesUseCase(
            service_repository=service_repo,
            service_manager=service_manager
        )
        
        async def show_status():
            """Show current status."""
            from ...application.use_cases.monitor_services import MonitorServicesCommand
            
            command = MonitorServicesCommand(
                service_names=services,
                all_services=services is None
            )
            result = await monitor_use_case.execute(command)
            
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
            if result.services:
                for service_info in result.services:
                    status_color = get_status_color(service_info.status.value if hasattr(service_info.status, 'value') else str(service_info.status))
                    health_status = format_health_status(
                        service_info.is_healthy,
                        0  # Placeholder for failure count
                    )
                    
                    table.add_row(
                        format_service_name(service_info.name),
                        f"[{status_color}]{str(service_info.status).title()}[/{status_color}]",
                        format_technology("kubectl"),  # Placeholder
                        format_port(service_info.local_port),
                        f"remote:{service_info.remote_port}",  # Placeholder
                        health_status,
                        format_uptime(service_info.uptime_seconds or 0)
                    )
            else:
                table.add_row("No services found", "-", "-", "-", "-", "-", "-")
            
            console.clear() if watch else None
            console.print(table)
            
            # Show summary
            summary = f"Total: {result.total_services} | Running: {result.running_services} | Healthy: {result.healthy_services}"
            console.print(f"\n[dim]{summary}[/dim]")
        
        if watch:
            # Watch mode - refresh periodically
            try:
                while True:
                    await show_status()
                    await asyncio.sleep(refresh_interval)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped watching[/yellow]")
        else:
            # Single status check
            await show_status()
            
    except Exception as e:
        logger.exception("Error getting service status")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs for more details."
        ))
        raise typer.Exit(1)


# Sync wrappers for Typer (since Typer doesn't support async directly)
def start_services_sync(
    services: Optional[List[str]] = typer.Argument(None, help="Service names to start"),
    all_services: bool = typer.Option(False, "--all", "-a", help="Start all configured services"),
    tags: Optional[List[str]] = typer.Option(None, "--tag", "-t", help="Start services with specific tags"),
    force: bool = typer.Option(False, "--force", "-f", help="Force restart if already running")
) -> None:
    """Start port forwarding services."""
    asyncio.run(start_services_command(services, all_services, tags, None, force))


def stop_services_sync(
    services: Optional[List[str]] = typer.Argument(None, help="Service names to stop"),
    all_services: bool = typer.Option(False, "--all", "-a", help="Stop all running services"),
    force: bool = typer.Option(False, "--force", "-f", help="Force stop services")
) -> None:
    """Stop port forwarding services."""
    asyncio.run(stop_services_command(services, all_services, force))


def status_services_sync(
    services: Optional[List[str]] = typer.Argument(None, help="Service names to check"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch mode - refresh periodically"),
    refresh_interval: int = typer.Option(5, "--interval", "-i", help="Refresh interval in seconds for watch mode")
) -> None:
    """Show service status."""
    asyncio.run(status_services_command(services, watch, refresh_interval))
