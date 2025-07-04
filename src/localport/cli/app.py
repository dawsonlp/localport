"""Main CLI application using Typer and Rich."""

import os
import sys

import structlog
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ..config.settings import Settings
from .formatters.output_format import OutputFormat
from .utils.rich_utils import setup_rich_logging

# Initialize console and logger
console = Console()
logger = structlog.get_logger()

# Create main Typer app
app = typer.Typer(
    name="localport",
    help="[bold blue]LocalPort[/bold blue] - Universal port forwarding manager with health monitoring",
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]}
)

# Global settings instance
settings: Settings | None = None


def version_callback(value: bool):
    """Show version information."""
    if value:
        from .. import __version__

        # Create a rich version display
        version_text = Text()
        version_text.append("LocalPort ", style="bold blue")
        version_text.append(f"v{__version__}", style="bold green")

        panel = Panel(
            version_text,
            title="[bold]Version Information[/bold]",
            border_style="blue",
            padding=(1, 2)
        )

        console.print(panel)
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version information and exit"
    ),
    config_file: str | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
        metavar="PATH"
    ),
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="Increase verbosity (-v for info, -vv for debug)"
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging (equivalent to -vv)"
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress non-essential output"
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Set log level",
        metavar="LEVEL",
        case_sensitive=False
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable colored output"
    ),
    output: str = typer.Option(
        "table",
        "--output",
        "-o",
        help="Output format (table, json, text)",
        metavar="FORMAT"
    )
):
    """
    [bold blue]LocalPort[/bold blue] - Universal port forwarding manager with health monitoring.

    LocalPort provides a unified interface for managing port forwards across different
    technologies (kubectl, SSH) with automatic health monitoring and restart capabilities.

    [bold]Examples:[/bold]

        [dim]# Start all configured services[/dim]
        localport start --all

        [dim]# Start specific services[/dim]
        localport start postgres redis

        [dim]# Check service status[/dim]
        localport status

        [dim]# Run in daemon mode[/dim]
        localport daemon start

    [bold]Configuration:[/bold]

    LocalPort looks for configuration files in the following locations:
    • ./localport.yaml
    • ~/.config/localport/config.yaml
    • /etc/localport/config.yaml

    Use --config to specify a custom configuration file.
    """
    global settings

    # Initialize context object
    ctx.ensure_object(dict)

    # Handle no-color option
    if no_color:
        console._color_system = None
        os.environ["NO_COLOR"] = "1"

    # Resolve verbosity level from flags
    def resolve_verbosity_level(verbosity_count: int, debug_flag: bool, quiet_flag: bool) -> int:
        """Resolve final verbosity level from flags."""
        if quiet_flag:
            return -1  # Quiet mode: errors only
        if debug_flag:
            return 2   # Debug level
        return min(verbosity_count, 2)  # Cap at debug level

    verbosity_level = resolve_verbosity_level(verbose, debug, quiet)

    # Map verbosity level to log level for backward compatibility
    if verbosity_level == -1:  # Quiet
        log_level = "ERROR"
        verbose_bool = False
    elif verbosity_level == 0:  # Clean (default)
        log_level = "WARNING"
        verbose_bool = False
    elif verbosity_level == 1:  # Informational
        log_level = "INFO"
        verbose_bool = True
    else:  # verbosity_level >= 2, Debug
        log_level = "DEBUG"
        verbose_bool = True

    # Validate output format
    try:
        output_format = OutputFormat.from_string(output)
    except ValueError as e:
        console.print(f"[red]Error:[/red] Invalid log level '{log_level}'. Valid levels: table, json, text")
        raise typer.Exit(1)

    # Setup logging with verbosity level
    setup_rich_logging(
        verbosity_level=verbosity_level,
        console=console
    )

    # Initialize settings
    try:
        settings = Settings(
            config_file=config_file,
            log_level=log_level.upper(),
            verbose=verbose_bool,
            quiet=quiet
        )

        # Store in context for commands
        ctx.obj.update({
            'settings': settings,
            'console': console,
            'config_file': config_file,
            'verbose': verbose_bool,  # Backward compatibility
            'verbosity_level': verbosity_level,  # New verbosity system
            'quiet': quiet,
            'log_level': log_level.upper(),
            'no_color': no_color,
            'output_format': output_format
        })

        logger.debug("CLI initialized",
                    config_file=config_file,
                    log_level=log_level,
                    verbosity_level=verbosity_level,
                    verbose=verbose_bool,
                    quiet=quiet)

    except Exception as e:
        console.print(f"[red]Error initializing LocalPort:[/red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


# Import command implementations
from .commands.config_commands import export_config_sync, validate_config_sync
from .commands.daemon_commands import (
    reload_daemon_sync,
    restart_daemon_sync,
    start_daemon_sync,
    status_daemon_sync,
    stop_daemon_sync,
)
from .commands.log_commands import logs_sync
from .commands.service_commands import (
    start_services_sync,
    status_services_sync,
    stop_services_sync,
)

# Service management commands
app.command(name="start")(start_services_sync)
app.command(name="stop")(stop_services_sync)
app.command(name="status")(status_services_sync)
app.command(name="logs")(logs_sync)


# Daemon command group
daemon_app = typer.Typer(
    name="daemon",
    help="Daemon management commands",
    no_args_is_help=True
)

# Add daemon commands
daemon_app.command(name="start")(start_daemon_sync)
daemon_app.command(name="stop")(stop_daemon_sync)
daemon_app.command(name="restart")(restart_daemon_sync)
daemon_app.command(name="status")(status_daemon_sync)
daemon_app.command(name="reload")(reload_daemon_sync)

# Add daemon subcommand
app.add_typer(daemon_app, name="daemon")


# Config command group
config_app = typer.Typer(
    name="config",
    help="Configuration management commands",
    no_args_is_help=True
)

# Add config commands
config_app.command(name="export")(export_config_sync)
config_app.command(name="validate")(validate_config_sync)

# Add config subcommand
app.add_typer(config_app, name="config")


def cli_main():
    """Entry point for the CLI application."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(130)  # Standard exit code for SIGINT
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        logger.exception("Unexpected CLI error")
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
