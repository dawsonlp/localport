"""Service management commands for LocalPort CLI."""

import asyncio
from pathlib import Path

import structlog
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ...application.services.service_manager import ServiceManager
from ...application.use_cases.monitor_services import MonitorServicesUseCase
from ...application.use_cases.start_services import StartServicesUseCase
from ...application.use_cases.stop_services import StopServicesUseCase
from ...infrastructure.adapters.adapter_factory import AdapterFactory
from ...infrastructure.health_checks.health_check_factory import HealthCheckFactory
from ...infrastructure.repositories.memory_service_repository import (
    MemoryServiceRepository,
)
from ...infrastructure.repositories.yaml_config_repository import YamlConfigRepository
from ..formatters.format_router import FormatRouter
from ..formatters.output_format import OutputFormat
from ..utils.rich_utils import (
    create_error_panel,
    create_success_panel,
    format_port,
    format_service_name,
    format_technology,
)

logger = structlog.get_logger()
console = Console()


async def start_services_command(
    services: list[str] | None = None,
    all_services: bool = False,
    tags: list[str] | None = None,
    config_file: str | None = None,
    force: bool = False,
    output_format: OutputFormat = OutputFormat.TABLE
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
            # Determine which specific path was attempted if config_file was provided
            if config_file:
                attempted_path = Path(config_file).expanduser().resolve()
                console.print(create_error_panel(
                    "Configuration File Not Found",
                    f"Configuration file not found: {attempted_path}",
                    f"Create the file or check the path. Run 'localport config init --help' for setup guidance."
                ))
            else:
                console.print(create_error_panel(
                    "No Configuration Found",
                    "No configuration file found in default locations:\n" +
                    "• ./localport.yaml (current directory)\n" +
                    "• ~/.config/localport/config.yaml (user config directory)\n" +
                    "• ~/.localport.yaml (user home directory)",
                    "Create a config file: 'localport config init' or specify custom path with --config /path/to/config.yaml"
                ))
            raise typer.Exit(1)

        # Initialize repositories and services with config path
        service_repo = MemoryServiceRepository()
        config_repo = YamlConfigRepository(str(config_path))
        AdapterFactory()
        HealthCheckFactory()
        service_manager = ServiceManager()

        # Load services from config
        await config_repo.load_configuration()
        
        # Load services into the service repository
        loaded_services = await config_repo.load_services()
        for service in loaded_services:
            await service_repo.save(service)

        # Initialize use case
        start_use_case = StartServicesUseCase(
            service_repository=service_repo,
            service_manager=service_manager
        )

        # Determine which services to start
        if all_services:
            service_names = None  # Start all services
            all_services_flag = True
        elif services:
            service_names = services  # These are service name strings from CLI
            all_services_flag = False
        elif tags:
            service_names = None
            all_services_flag = False
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

            # Create command object
            from ...application.use_cases.start_services import StartServicesCommand
            command = StartServicesCommand(
                service_names=service_names,
                tags=tags,
                all_services=all_services_flag,
                force_restart=force
            )

            result = await start_use_case.execute(command)

            progress.update(task, completed=True)

        # Display results
        if result.success_count > 0:
            console.print(create_success_panel(
                "Services Started",
                f"Successfully started {result.success_count} service(s)"
            ))

            # Show started services table
            if result.successful_services:
                table = Table(title="Started Services")
                table.add_column("Service", style="bold blue")
                table.add_column("Technology", style="cyan")
                table.add_column("Local Port", style="green")
                table.add_column("Target", style="yellow")
                table.add_column("Status", style="bold")

                for service_name in result.successful_services:
                    # Get service details from the loaded services
                    service_details = None
                    for service in loaded_services:
                        if service.name == service_name:
                            service_details = service
                            break
                    
                    if service_details:
                        # Build target string based on technology
                        if service_details.technology.value == "kubectl":
                            target = f"{service_details.connection_info.get_kubectl_resource_type()}/{service_details.connection_info.get_kubectl_resource_name()}:{service_details.remote_port}"
                        else:
                            target = f"remote:{service_details.remote_port}"
                        
                        table.add_row(
                            format_service_name(service_name),
                            format_technology(service_details.technology.value),
                            format_port(service_details.local_port),
                            target,
                            "[green]Running[/green]"
                        )
                    else:
                        # Fallback if service details not found
                        table.add_row(
                            format_service_name(service_name),
                            format_technology("unknown"),
                            format_port(0),
                            "unknown",
                            "[green]Running[/green]"
                        )

                console.print(table)

        if result.failure_count > 0:
            error_messages = []
            for service_name, error in result.errors.items():
                error_messages.append(f"• {service_name}: {error}")
            
            console.print(create_error_panel(
                "Failed to Start Some Services",
                f"Failed to start {result.failure_count} service(s):\n" + "\n".join(error_messages),
                "Check the logs for more details or try with --verbose flag."
            ))
            
            if result.success_count == 0:
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
    services: list[str] | None = None,
    all_services: bool = False,
    force: bool = False
) -> None:
    """Stop port forwarding services."""
    try:
        # Load configuration (same logic as start command)
        config_path = None
        for path in ["./localport.yaml", "~/.config/localport/config.yaml"]:
            test_path = Path(path).expanduser()
            if test_path.exists():
                config_path = test_path
                break

        # Initialize repositories and services
        service_repo = MemoryServiceRepository()
        config_repo = YamlConfigRepository(str(config_path)) if config_path else None
        AdapterFactory()
        HealthCheckFactory()
        service_manager = ServiceManager()

        # Load services from config if available
        if config_repo:
            await config_repo.load_configuration()
            loaded_services = await config_repo.load_services()
            for service in loaded_services:
                await service_repo.save(service)

        # Initialize use case
        stop_use_case = StopServicesUseCase(
            service_repository=service_repo,
            service_manager=service_manager
        )

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

            # Create command object
            from ...application.use_cases.stop_services import StopServicesCommand
            command = StopServicesCommand(
                service_names=service_names,
                all_services=all_services,
                force_stop=force
            )

            result = await stop_use_case.execute(command)

            progress.update(task, completed=True)

        # Display results
        if result.success_count > 0:
            console.print(create_success_panel(
                "Services Stopped",
                f"Successfully stopped {result.success_count} service(s)"
            ))

        if result.failure_count > 0:
            error_messages = []
            for service_name, error in result.errors.items():
                error_messages.append(f"• {service_name}: {error}")
            
            console.print(create_error_panel(
                "Failed to Stop Some Services",
                f"Failed to stop {result.failure_count} service(s):\n" + "\n".join(error_messages),
                "Check the logs for more details or try with --force flag."
            ))
            
            if result.success_count == 0:
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
    services: list[str] | None = None,
    watch: bool = False,
    refresh_interval: int = 5,
    output_format: OutputFormat = OutputFormat.TABLE
) -> None:
    """Show service status."""
    try:
        # Load configuration (same logic as start command)
        config_path = None
        for path in ["./localport.yaml", "~/.config/localport/config.yaml"]:
            test_path = Path(path).expanduser()
            if test_path.exists():
                config_path = test_path
                break

        # Initialize repositories and services
        service_repo = MemoryServiceRepository()
        config_repo = YamlConfigRepository(str(config_path)) if config_path else None
        AdapterFactory()
        HealthCheckFactory()
        service_manager = ServiceManager()

        # Load services from config if available
        if config_repo:
            await config_repo.load_configuration()
            loaded_services = await config_repo.load_services()
            
            # Migrate state from random UUIDs to deterministic UUIDs
            migration_count = service_manager.migrate_state_to_deterministic_ids(loaded_services)
            if migration_count > 0:
                logger.info("Migrated state to deterministic IDs", count=migration_count)
            
            for service in loaded_services:
                await service_repo.save(service)

        # Initialize use case
        monitor_use_case = MonitorServicesUseCase(
            service_repository=service_repo,
            service_manager=service_manager
        )

        # Initialize format router
        format_router = FormatRouter(console)

        async def show_status():
            """Show current status."""
            from ...application.use_cases.monitor_services import MonitorServicesCommand

            command = MonitorServicesCommand(
                service_names=services,
                all_services=services is None
            )
            result = await monitor_use_case.execute(command)

            # Format output based on requested format
            if output_format == OutputFormat.JSON:
                # For JSON output, get the formatted string and print it
                formatted_output = format_router.format_service_status(result, output_format)
                console.print(formatted_output)
            else:
                # For table output, clear screen if watching, then let formatter print directly
                if watch:
                    console.clear()
                format_router.format_service_status(result, output_format)

        if watch:
            # Watch mode - refresh periodically
            if output_format == OutputFormat.JSON:
                # For JSON watch mode, output one JSON object per refresh
                try:
                    while True:
                        await show_status()
                        await asyncio.sleep(refresh_interval)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Stopped watching[/yellow]")
            else:
                # For table watch mode, clear and refresh
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
        if output_format == OutputFormat.JSON:
            # For JSON output, format error as JSON
            error_formatter = format_router.service_status_json
            error_output = error_formatter._format_error("service_status_error", str(e))
            console.print(error_output)
        else:
            console.print(create_error_panel(
                "Unexpected Error",
                str(e),
                "Check the logs for more details."
            ))
        raise typer.Exit(1)


# Sync wrappers for Typer (since Typer doesn't support async directly)
def start_services_sync(
    ctx: typer.Context,
    services: list[str] | None = typer.Argument(None, help="Service names to start"),
    all_services: bool = typer.Option(False, "--all", "-a", help="Start all configured services"),
    tags: list[str] | None = typer.Option(None, "--tag", "-t", help="Start services with specific tags"),
    force: bool = typer.Option(False, "--force", "-f", help="Force restart if already running")
) -> None:
    """Start port forwarding services."""
    # Get output format from context
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    asyncio.run(start_services_command(services, all_services, tags, None, force, output_format))


def stop_services_sync(
    services: list[str] | None = typer.Argument(None, help="Service names to stop"),
    all_services: bool = typer.Option(False, "--all", "-a", help="Stop all running services"),
    force: bool = typer.Option(False, "--force", "-f", help="Force stop services")
) -> None:
    """Stop port forwarding services."""
    asyncio.run(stop_services_command(services, all_services, force))


def status_services_sync(
    ctx: typer.Context,
    services: list[str] | None = typer.Argument(None, help="Service names to check"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch mode - refresh periodically"),
    refresh_interval: int = typer.Option(5, "--interval", "-i", help="Refresh interval in seconds for watch mode")
) -> None:
    """Show service status."""
    # Get output format from context
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    asyncio.run(status_services_command(services, watch, refresh_interval, output_format))
