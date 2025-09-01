"""Service management commands for LocalPort CLI."""

import asyncio
from pathlib import Path

import structlog
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ...application.services.service_manager import ServiceManager
from ...application.services.cluster_health_manager import ClusterHealthManager
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
from ..utils.error_formatter import ErrorFormatter, VerbosityLevel

logger = structlog.get_logger()
console = Console()


async def _check_daemon_running() -> bool:
    """Check if LocalPort daemon is currently running."""
    try:
        import psutil
        
        # Look for LocalPort daemon processes
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if (cmdline and 
                    len(cmdline) > 0 and 
                    'python' in cmdline[0] and 
                    any('localport' in arg and 'daemon' in arg for arg in cmdline)):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        return False
        
    except ImportError:
        # If psutil is not available, assume daemon is not running
        logger.warning("psutil not available, cannot check daemon status")
        return False
    except Exception as e:
        logger.warning("Error checking daemon status", error=str(e))
        return False


async def start_services_command(
    services: list[str] | None = None,
    all_services: bool = False,
    tags: list[str] | None = None,
    config_file: str | None = None,
    force: bool = False,
    output_format: OutputFormat = OutputFormat.TABLE,
    verbosity_level: int = 0
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
            # Use improved error formatting for service failures
            error_formatter = ErrorFormatter(console)
            
            # Convert verbosity level integer to VerbosityLevel enum
            if verbosity_level >= 2:
                error_verbosity = VerbosityLevel.DEBUG
            elif verbosity_level >= 1:
                error_verbosity = VerbosityLevel.VERBOSE
            else:
                error_verbosity = VerbosityLevel.NORMAL
            
            # Convert service errors to structured exceptions where possible
            structured_errors = []
            for service_name, error_msg in result.errors.items():
                # Check if this is an SSH key error (common shared config problem)
                from ...domain.exceptions import SSHKeyNotFoundError, LocalPortError
                
                if "SSH key file not found" in str(error_msg) or "key file not found" in str(error_msg).lower():
                    # Extract key path from error message if possible
                    import re
                    key_match = re.search(r'([~\/][^\s]+\.(?:pem|key|rsa|ed25519))', str(error_msg))
                    key_path = key_match.group(1) if key_match else "unknown"
                    
                    structured_errors.append(SSHKeyNotFoundError(
                        key_path=key_path,
                        service_name=service_name
                    ))
                else:
                    # Generic error - create a LocalPortError for consistent formatting
                    from ...domain.exceptions import UserError
                    structured_errors.append(UserError(
                        message=f"Failed to start service '{service_name}': {error_msg}",
                        suggestions=[
                            "Check service configuration",
                            "Verify connection details",
                            "Use --verbose for detailed error information"
                        ]
                    ))
            
            # Display formatted errors
            if len(structured_errors) == 1:
                error_formatter.print_error(structured_errors[0], error_verbosity)
            else:
                error_formatter.print_multiple_errors(structured_errors, error_verbosity)
            
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
    force: bool = False,
    config_file: str | None = None
) -> None:
    """Stop port forwarding services."""
    try:
        # Check if daemon is running first
        daemon_running = await _check_daemon_running()
        
        if daemon_running and not force:
            console.print(create_error_panel(
                "Daemon is Running",
                "LocalPort daemon is currently running and will automatically restart stopped services.\n\n" +
                "This means services will be stopped and immediately restarted, causing the stop command to hang.",
                "Choose one of these options:\n" +
                "• Stop the daemon first: 'localport daemon stop'\n" +
                "• Use force flag to stop anyway: 'localport stop --all --force'\n" +
                "• Restart services instead: 'localport start --force <service-names>'"
            ))
            raise typer.Exit(1)
        
        if daemon_running and force:
            console.print("[yellow]⚠️  Warning: Daemon is running. Services may be restarted automatically after stopping.[/yellow]")

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

            # Get cluster health information if available
            cluster_health_data = await _get_cluster_health_for_status(config_repo)

            # Format output based on requested format
            if output_format == OutputFormat.JSON:
                # For JSON output, include cluster health data
                formatted_output = format_router.format_service_status(result, output_format)
                # TODO: Enhance JSON formatter to include cluster health
                console.print(formatted_output)
            else:
                # For table output, clear screen if watching, then show services and cluster health
                if watch:
                    console.clear()
                
                # Show service status
                format_router.format_service_status(result, output_format)
                
                # Show cluster health section
                if cluster_health_data:
                    console.print()  # Add spacing
                    _display_cluster_health_section(cluster_health_data)

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
            # Use new error formatting system with verbosity from context
            verbosity_level = VerbosityLevel.NORMAL
            if output_format != OutputFormat.JSON:
                # Get verbosity from CLI context if available
                try:
                    ctx_verbosity = ctx.obj.get('verbosity_level', 0) if hasattr(ctx, 'obj') and ctx.obj else 0
                    if ctx_verbosity >= 2:
                        verbosity_level = VerbosityLevel.DEBUG
                    elif ctx_verbosity >= 1:
                        verbosity_level = VerbosityLevel.VERBOSE
                except:
                    pass  # Fall back to normal verbosity
            
            error_formatter = ErrorFormatter(console)
            error_formatter.print_error(e, verbosity_level)
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
    # Get config file, output format, and verbosity from context
    config_file = ctx.obj.get('config_file')
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    verbosity_level = ctx.obj.get('verbosity_level', 0)
    asyncio.run(start_services_command(services, all_services, tags, config_file, force, output_format, verbosity_level))


def stop_services_sync(
    ctx: typer.Context,
    services: list[str] | None = typer.Argument(None, help="Service names to stop"),
    all_services: bool = typer.Option(False, "--all", "-a", help="Stop all running services"),
    force: bool = typer.Option(False, "--force", "-f", help="Force stop services")
) -> None:
    """Stop port forwarding services."""
    # Get config file from context
    config_file = ctx.obj.get('config_file')
    asyncio.run(stop_services_command(services, all_services, force, config_file))


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


async def _get_cluster_health_for_status(config_repo: YamlConfigRepository | None) -> dict | None:
    """Get cluster health data for status display (lightweight but proper domain entities)."""
    if not config_repo:
        return None
    
    try:
        # Load configuration to check if cluster health is enabled
        config = await config_repo.load_configuration()
        cluster_health_config = config.get('defaults', {}).get('cluster_health', {})
        
        if not cluster_health_config.get('enabled', True):
            return None

        # Load services to determine which clusters to monitor
        services = await config_repo.load_services()
        kubectl_services = [s for s in services if s.technology.value == 'kubectl']
        
        if not kubectl_services:
            return None

        # Extract unique cluster contexts
        contexts = set()
        for service in kubectl_services:
            context = service.connection_info.get_kubectl_context()
            if context:
                contexts.add(context)

        if not contexts:
            return None

        # Use lightweight kubectl client directly for status display
        from ...infrastructure.cluster_monitoring.kubectl_client import KubectlClient
        from ...domain.entities.cluster_health import ClusterHealth
        
        kubectl_client = KubectlClient(timeout=10, retry_attempts=1)  # Faster for status
        
        cluster_data = {}
        for context in contexts:
            try:
                # Get basic cluster info and resource counts quickly
                cluster_info = await kubectl_client.get_cluster_info(context)
                
                if cluster_info.is_reachable:
                    # Get node and pod counts
                    nodes = await kubectl_client.get_node_statuses(context)
                    pods = await kubectl_client.get_pod_statuses(context)
                    
                    # Create proper ClusterHealth entity using the domain factory method
                    cluster_health = ClusterHealth.create_healthy(
                        context=context,
                        cluster_info=cluster_info,
                        nodes=nodes,
                        pods=pods,
                        events=[],  # Skip events for status display performance
                        check_duration=None
                    )
                    
                    cluster_data[context] = {
                        'health': cluster_health,
                        'info': cluster_info
                    }
                else:
                    # Cluster not reachable - create unhealthy ClusterHealth
                    cluster_health = ClusterHealth.create_unhealthy(
                        context=context,
                        error=cluster_info.error_message or "Cluster not reachable"
                    )
                    
                    cluster_data[context] = {
                        'health': cluster_health,
                        'info': cluster_info,
                        'error': cluster_info.error_message or "Cluster not reachable"
                    }
                    
            except Exception as e:
                logger.debug("Error getting cluster health for context", context=context, error=str(e))
                # Create unhealthy ClusterHealth for errors
                cluster_health = ClusterHealth.create_unhealthy(
                    context=context,
                    error=str(e)
                )
                cluster_data[context] = {
                    'health': cluster_health,
                    'info': None,
                    'error': str(e)
                }

        return cluster_data if cluster_data else None

    except Exception as e:
        logger.debug("Error getting cluster health for status", error=str(e))
        return None


def _display_cluster_health_section(cluster_data: dict) -> None:
    """Display cluster health section in status output."""
    from datetime import datetime
    from rich.panel import Panel
    
    # Create cluster health table
    table = Table(title="🏗️  Cluster Health", show_header=True, header_style="bold blue")
    table.add_column("Context", style="bold blue", width=20)
    table.add_column("Status", style="bold", width=15)
    table.add_column("Nodes", style="green", width=8)
    table.add_column("Pods", style="yellow", width=8)
    table.add_column("Last Check", style="dim", width=12)

    for context, data in cluster_data.items():
        if data.get('error'):
            # Error case
            table.add_row(
                context,
                "[red]🔴 Error[/red]",
                "Error",
                "Error",
                "Error"
            )
        else:
            health_data = data.get('health', {})
            cluster_info = data.get('info', {})
            
            # Format status with color indicators (health_data is a ClusterHealth object)
            if health_data:
                is_healthy = health_data.is_healthy
                last_check = health_data.last_check_time
                
                if is_healthy:
                    status = "[green]🟢 Healthy[/green]"
                else:
                    status = "[red]🔴 Unhealthy[/red]"
                
                # Format last check time (last_check is already a datetime object)
                if last_check:
                    try:
                        from datetime import timezone
                        now = datetime.now(timezone.utc) if last_check.tzinfo else datetime.now()
                        if last_check.tzinfo is None:
                            # If last_check is naive, assume it's UTC and make it timezone-aware
                            last_check = last_check.replace(tzinfo=timezone.utc)
                            now = datetime.now(timezone.utc)
                        
                        time_ago = now - last_check
                        total_seconds = abs(time_ago.total_seconds())  # Use abs to avoid negative values
                        
                        if total_seconds < 60:
                            time_str = f"{int(total_seconds)}s ago"
                        elif total_seconds < 3600:
                            time_str = f"{int(total_seconds // 60)}m ago"
                        else:
                            time_str = f"{int(total_seconds // 3600)}h ago"
                    except Exception:
                        time_str = "Unknown"
                else:
                    time_str = "Never"
            else:
                status = "[dim]Unknown[/dim]"
                time_str = "Unknown"
            
            # Format cluster info (cluster_info is a ClusterInfo object)
            if cluster_info:
                api_server = cluster_info.api_server_url or 'Unknown'
                # Use health_data for node/pod counts since ClusterInfo doesn't have them
                node_count = str(health_data.total_nodes if health_data else 0)
                pod_count = str(health_data.total_pods if health_data else 0)
            else:
                api_server = "Unknown"
                node_count = "0"
                pod_count = "0"
            
            table.add_row(
                context,
                status,
                node_count,
                pod_count,
                time_str
            )

    console.print(table)
    
    # Add helpful note if cluster health is available
    if cluster_data:
        console.print("[dim]💡 Use 'localport cluster status' for detailed cluster information[/dim]")
