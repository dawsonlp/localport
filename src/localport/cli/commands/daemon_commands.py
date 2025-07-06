"""Daemon management commands for LocalPort CLI."""

import asyncio

import structlog
import typer
from rich.console import Console
from rich.table import Table

from ...application.services.daemon_manager import DaemonManager
from ...application.services.health_monitor_scheduler import HealthMonitorScheduler
from ...application.services.restart_manager import RestartManager
from ...application.services.service_manager import ServiceManager
from ...application.use_cases.manage_daemon import ManageDaemonUseCase
from ...infrastructure.adapters.adapter_factory import AdapterFactory
from ...infrastructure.health_checks.health_check_factory import HealthCheckFactory
from ...infrastructure.repositories.memory_service_repository import (
    MemoryServiceRepository,
)
from ...infrastructure.repositories.yaml_config_repository import YamlConfigRepository
from ..utils.progress_utils import EnhancedProgress, get_operation_messages
from ..utils.rich_utils import (
    create_error_panel,
    create_info_panel,
    create_success_panel,
    format_uptime,
)

logger = structlog.get_logger()
console = Console()


async def start_daemon_command(
    config_file: str | None = None,
    auto_start: bool = True,
    detach: bool = False
) -> None:
    """Start the LocalPort daemon."""
    try:
        # Initialize repositories and services
        service_repo = MemoryServiceRepository()
        config_repo = YamlConfigRepository()
        AdapterFactory()
        health_check_factory = HealthCheckFactory()

        service_manager = ServiceManager()
        restart_manager = RestartManager(service_manager)
        health_monitor = HealthMonitorScheduler(health_check_factory, restart_manager)

        DaemonManager(
            service_repository=service_repo,
            config_repository=config_repo,
            service_manager=service_manager,
            health_monitor=health_monitor
        )

        # Initialize use case
        daemon_use_case = ManageDaemonUseCase(
            service_repository=service_repo,
            service_manager=service_manager
        )

        # Start daemon with enhanced progress indication
        enhanced_progress = EnhancedProgress(console)
        messages = get_operation_messages("start")
        
        async def start_operation():
            from ...application.use_cases.manage_daemon import (
                DaemonCommand,
                ManageDaemonCommand,
            )

            command = ManageDaemonCommand(
                command=DaemonCommand.START,
                config_file=config_file
            )
            return await daemon_use_case.execute(command)

        result = await enhanced_progress.run_with_spinner(
            start_operation,
            messages["daemon"],
            messages["success"]
        )

        # Display results
        if result.success:
            if detach:
                # Background mode - show brief success message with next steps
                console.print(create_success_panel(
                    "Daemon Started",
                    f"LocalPort daemon started in background (PID: {result.pid})"
                ))
                
                if auto_start:
                    console.print(create_info_panel(
                        "Auto-start Enabled",
                        "Configured services will be started automatically"
                    ))
                
                # Show helpful next steps
                console.print("\n[dim]Next steps:[/dim]")
                console.print("  • Check status: [bold]localport daemon status[/bold]")
                console.print("  • View logs: [bold]localport logs[/bold]")
                console.print("  • Stop daemon: [bold]localport daemon stop[/bold]")
            else:
                # Foreground mode - show different message
                console.print(create_success_panel(
                    "Daemon Started",
                    f"LocalPort daemon started in foreground (PID: {result.pid})"
                ))

                if auto_start:
                    console.print(create_info_panel(
                        "Auto-start Enabled",
                        "Configured services will be started automatically"
                    ))

                console.print("[dim]Press Ctrl+C to stop the daemon[/dim]")
                try:
                    # Keep running until interrupted
                    while True:
                        await asyncio.sleep(1)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Stopping daemon...[/yellow]")
                    stop_command = ManageDaemonCommand(command=DaemonCommand.STOP)
                    stop_result = await daemon_use_case.execute(stop_command)
                    if stop_result.success:
                        console.print("[green]Daemon stopped successfully[/green]")
                    else:
                        console.print(f"[red]Error stopping daemon: {stop_result.error}[/red]")
        else:
            console.print(create_error_panel(
                "Failed to Start Daemon",
                result.error or "Unknown error occurred",
                "Check if another daemon is running: 'localport daemon status' or view logs: 'localport logs --daemon'"
            ))
            raise typer.Exit(1)

    except typer.Exit:
        # Re-raise typer.Exit to allow clean exit
        raise
    except Exception as e:
        logger.exception("Error starting daemon")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs in ~/.local/share/localport/logs/ or run with --verbose for more details."
        ))
        raise typer.Exit(1)


async def stop_daemon_command(force: bool = False) -> None:
    """Stop the LocalPort daemon."""
    try:
        # Initialize minimal setup for daemon management
        service_repo = MemoryServiceRepository()
        config_repo = YamlConfigRepository()
        AdapterFactory()
        health_check_factory = HealthCheckFactory()

        service_manager = ServiceManager()
        restart_manager = RestartManager(service_manager)
        health_monitor = HealthMonitorScheduler(health_check_factory, restart_manager)

        DaemonManager(
            service_repository=service_repo,
            config_repository=config_repo,
            service_manager=service_manager,
            health_monitor=health_monitor
        )

        # Initialize use case
        daemon_use_case = ManageDaemonUseCase(
            service_repository=service_repo,
            service_manager=service_manager
        )

        # Stop daemon with enhanced progress indication
        enhanced_progress = EnhancedProgress(console)
        messages = get_operation_messages("stop")
        
        async def stop_operation():
            from ...application.use_cases.manage_daemon import (
                DaemonCommand,
                ManageDaemonCommand,
            )

            command = ManageDaemonCommand(
                command=DaemonCommand.STOP,
                force=force
            )
            return await daemon_use_case.execute(command)

        result = await enhanced_progress.run_with_spinner(
            stop_operation,
            messages["daemon"],
            messages["success"]
        )

        # Display results
        if result.success:
            console.print(create_success_panel(
                "Daemon Stopped",
                "LocalPort daemon stopped successfully"
            ))
        else:
            console.print(create_error_panel(
                "Failed to Stop Daemon",
                result.error or "Unknown error occurred",
                "Try using --force flag or check if daemon is running."
            ))
            raise typer.Exit(1)

    except typer.Exit:
        # Re-raise typer.Exit to allow clean exit
        raise
    except Exception as e:
        logger.exception("Error stopping daemon")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs in ~/.local/share/localport/logs/ or run with --verbose for more details."
        ))
        raise typer.Exit(1)


async def restart_daemon_command(
    config_file: str | None = None,
    force: bool = False
) -> None:
    """Restart the LocalPort daemon."""
    try:
        # Initialize repositories and services
        service_repo = MemoryServiceRepository()
        config_repo = YamlConfigRepository()
        AdapterFactory()
        health_check_factory = HealthCheckFactory()

        service_manager = ServiceManager()
        restart_manager = RestartManager(service_manager)
        health_monitor = HealthMonitorScheduler(health_check_factory, restart_manager)

        DaemonManager(
            service_repository=service_repo,
            config_repository=config_repo,
            service_manager=service_manager,
            health_monitor=health_monitor
        )

        # Initialize use case
        daemon_use_case = ManageDaemonUseCase(
            service_repository=service_repo,
            service_manager=service_manager
        )

        # Restart daemon with enhanced progress indication
        enhanced_progress = EnhancedProgress(console)
        messages = get_operation_messages("restart")
        
        async def restart_operation():
            from ...application.use_cases.manage_daemon import (
                DaemonCommand,
                ManageDaemonCommand,
            )

            command = ManageDaemonCommand(
                command=DaemonCommand.RESTART,
                config_file=config_file,
                force=force
            )
            return await daemon_use_case.execute(command)

        result = await enhanced_progress.run_with_spinner(
            restart_operation,
            messages["daemon"],
            messages["success"]
        )

        # Display results
        if result.success:
            console.print(create_success_panel(
                "Daemon Restarted",
                f"LocalPort daemon restarted successfully (PID: {result.pid})"
            ))
        else:
            console.print(create_error_panel(
                "Failed to Restart Daemon",
                result.error or "Unknown error occurred",
                "Check the logs for more details."
            ))
            raise typer.Exit(1)

    except typer.Exit:
        # Re-raise typer.Exit to allow clean exit
        raise
    except Exception as e:
        logger.exception("Error restarting daemon")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs in ~/.local/share/localport/logs/ or run with --verbose for more details."
        ))
        raise typer.Exit(1)


async def status_daemon_command(watch: bool = False, refresh_interval: int = 5) -> None:
    """Show daemon status."""
    try:
        # Initialize minimal setup for daemon management
        service_repo = MemoryServiceRepository()
        config_repo = YamlConfigRepository()
        AdapterFactory()
        health_check_factory = HealthCheckFactory()

        service_manager = ServiceManager()
        restart_manager = RestartManager(service_manager)
        health_monitor = HealthMonitorScheduler(health_check_factory, restart_manager)

        DaemonManager(
            service_repository=service_repo,
            config_repository=config_repo,
            service_manager=service_manager,
            health_monitor=health_monitor
        )

        # Initialize use case
        daemon_use_case = ManageDaemonUseCase(
            service_repository=service_repo,
            service_manager=service_manager
        )

        async def show_status():
            """Show current daemon status."""
            from ...application.use_cases.manage_daemon import (
                DaemonCommand,
                ManageDaemonCommand,
            )

            command = ManageDaemonCommand(command=DaemonCommand.STATUS)
            result = await daemon_use_case.execute(command)

            if not result.success:
                console.print(create_error_panel(
                    "Failed to Get Daemon Status",
                    result.error or "Unknown error occurred"
                ))
                return

            # Create status table
            table = Table(title="Daemon Status")
            table.add_column("Property", style="bold blue")
            table.add_column("Value", style="white")

            # Check if we have status information
            if hasattr(result, 'status') and result.status:
                status_info = result.status
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
                table.add_row("Message", result.message or "Daemon is not running")

            console.clear() if watch else None
            console.print(table)

            # Show additional info
            if result.message and not result.success:
                console.print(f"\n[yellow]Note:[/yellow] {result.message}")

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

    except typer.Exit:
        # Re-raise typer.Exit to allow clean exit
        raise
    except Exception as e:
        logger.exception("Error getting daemon status")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs in ~/.local/share/localport/logs/ or run with --verbose for more details."
        ))
        raise typer.Exit(1)


async def reload_daemon_command() -> None:
    """Reload daemon configuration."""
    try:
        # Initialize minimal setup for daemon management
        service_repo = MemoryServiceRepository()
        config_repo = YamlConfigRepository()
        AdapterFactory()
        health_check_factory = HealthCheckFactory()

        service_manager = ServiceManager()
        restart_manager = RestartManager(service_manager)
        health_monitor = HealthMonitorScheduler(health_check_factory, restart_manager)

        DaemonManager(
            service_repository=service_repo,
            config_repository=config_repo,
            service_manager=service_manager,
            health_monitor=health_monitor
        )

        # Initialize use case
        daemon_use_case = ManageDaemonUseCase(
            service_repository=service_repo,
            service_manager=service_manager
        )

        # Reload daemon configuration with enhanced progress indication
        enhanced_progress = EnhancedProgress(console)
        messages = get_operation_messages("reload")
        
        async def reload_operation():
            from ...application.use_cases.manage_daemon import (
                DaemonCommand,
                ManageDaemonCommand,
            )

            command = ManageDaemonCommand(command=DaemonCommand.RELOAD)
            return await daemon_use_case.execute(command)

        result = await enhanced_progress.run_with_spinner(
            reload_operation,
            messages["daemon"],
            messages["success"]
        )

        # Display results
        if result.success:
            console.print(create_success_panel(
                "Configuration Reloaded",
                "Daemon configuration reloaded successfully"
            ))
        else:
            console.print(create_error_panel(
                "Failed to Reload Configuration",
                result.error or "Unknown error occurred",
                "Check if daemon is running and configuration file is valid."
            ))
            raise typer.Exit(1)

    except typer.Exit:
        # Re-raise typer.Exit to allow clean exit
        raise
    except Exception as e:
        logger.exception("Error reloading daemon configuration")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs in ~/.local/share/localport/logs/ or run with --verbose for more details."
        ))
        raise typer.Exit(1)


# Sync wrappers for Typer (since Typer doesn't support async directly)
def start_daemon_sync(
    config_file: str | None = typer.Option(None, "--config", "-c", help="Configuration file path"),
    auto_start: bool = typer.Option(True, "--auto-start/--no-auto-start", help="Auto-start configured services"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run daemon in foreground (don't detach)")
) -> None:
    """Start the LocalPort daemon."""
    # Invert the logic: default is detached (background), --foreground runs in foreground
    detach = not foreground
    asyncio.run(start_daemon_command(config_file, auto_start, detach))


def stop_daemon_sync(
    force: bool = typer.Option(False, "--force", "-f", help="Force stop daemon")
) -> None:
    """Stop the LocalPort daemon."""
    asyncio.run(stop_daemon_command(force))


def restart_daemon_sync(
    config_file: str | None = typer.Option(None, "--config", "-c", help="Configuration file path"),
    force: bool = typer.Option(False, "--force", "-f", help="Force restart daemon")
) -> None:
    """Restart the LocalPort daemon."""
    asyncio.run(restart_daemon_command(config_file, force))


def status_daemon_sync(
    watch: bool = typer.Option(False, "--watch", "-w", help="Watch mode - refresh periodically"),
    refresh_interval: int = typer.Option(5, "--interval", "-i", help="Refresh interval in seconds for watch mode")
) -> None:
    """Show daemon status."""
    asyncio.run(status_daemon_command(watch, refresh_interval))


def reload_daemon_sync() -> None:
    """Reload daemon configuration."""
    asyncio.run(reload_daemon_command())
