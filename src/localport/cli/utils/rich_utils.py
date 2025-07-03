"""Rich utilities for CLI formatting and logging."""

import logging

import structlog
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install


def setup_rich_logging(
    level: str = "INFO",
    verbose: bool = False,
    console: Console | None = None
) -> None:
    """Setup Rich-based logging for the CLI.

    Args:
        level: Logging level (DEBUG, INFO, WARN, ERROR)
        verbose: Enable verbose logging
        console: Rich console instance to use
    """
    if console is None:
        console = Console()

    # Install rich traceback handler
    install(console=console, show_locals=verbose)

    # Configure log level
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Setup Rich handler for standard logging
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=verbose,
        rich_tracebacks=True,
        tracebacks_show_locals=verbose
    )
    rich_handler.setLevel(log_level)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[rich_handler]
    )

    # Configure structlog to work properly with Rich
    if verbose:
        # For verbose mode, use JSON renderer for structured output
        final_processor = structlog.processors.JSONRenderer()
    else:
        # For normal mode, use a simple key-value renderer that works with Rich
        final_processor = structlog.processors.KeyValueRenderer(
            key_order=['timestamp', 'level', 'event'],
            drop_missing=True
        )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            final_processor,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_status_color(status: str) -> str:
    """Get Rich color for service status.

    Args:
        status: Service status string

    Returns:
        Rich color name
    """
    status_colors = {
        "running": "green",
        "stopped": "red",
        "starting": "yellow",
        "failed": "bright_red",
        "restarting": "orange3",
        "unknown": "dim"
    }
    return status_colors.get(status.lower(), "white")


def format_uptime(seconds: float) -> str:
    """Format uptime in a human-readable format.

    Args:
        seconds: Uptime in seconds

    Returns:
        Formatted uptime string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h"
    else:
        days = seconds / 86400
        return f"{days:.1f}d"


def format_port(port: int) -> str:
    """Format port number with appropriate styling.

    Args:
        port: Port number

    Returns:
        Formatted port string
    """
    return f"[cyan]{port}[/cyan]"


def format_service_name(name: str) -> str:
    """Format service name with appropriate styling.

    Args:
        name: Service name

    Returns:
        Formatted service name
    """
    return f"[bold blue]{name}[/bold blue]"


def format_technology(technology: str) -> str:
    """Format technology name with appropriate styling.

    Args:
        technology: Technology name (kubectl, ssh, etc.)

    Returns:
        Formatted technology string
    """
    tech_colors = {
        "kubectl": "blue",
        "ssh": "green",
        "docker": "cyan"
    }
    color = tech_colors.get(technology.lower(), "white")
    return f"[{color}]{technology}[/{color}]"


def format_health_status(is_healthy: bool, failure_count: int = 0) -> str:
    """Format health status with appropriate styling.

    Args:
        is_healthy: Whether the service is healthy
        failure_count: Number of consecutive failures

    Returns:
        Formatted health status string
    """
    if is_healthy:
        return "[green]✓ Healthy[/green]"
    else:
        if failure_count > 0:
            return f"[red]✗ Unhealthy ({failure_count} failures)[/red]"
        else:
            return "[red]✗ Unhealthy[/red]"


def create_error_panel(title: str, message: str, suggestion: str | None = None) -> str:
    """Create a formatted error panel.

    Args:
        title: Error title
        message: Error message
        suggestion: Optional suggestion for fixing the error

    Returns:
        Formatted error panel markup
    """
    from rich.panel import Panel
    from rich.text import Text

    content = Text()
    content.append(message, style="red")

    if suggestion:
        content.append("\n\n")
        content.append("💡 Suggestion: ", style="yellow")
        content.append(suggestion, style="white")

    panel = Panel(
        content,
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
        padding=(1, 2)
    )

    return panel


def create_success_panel(title: str, message: str) -> str:
    """Create a formatted success panel.

    Args:
        title: Success title
        message: Success message

    Returns:
        Formatted success panel markup
    """
    from rich.panel import Panel
    from rich.text import Text

    content = Text()
    content.append("✓ ", style="green")
    content.append(message, style="white")

    panel = Panel(
        content,
        title=f"[bold green]{title}[/bold green]",
        border_style="green",
        padding=(1, 2)
    )

    return panel


def create_info_panel(title: str, message: str) -> str:
    """Create a formatted info panel.

    Args:
        title: Info title
        message: Info message

    Returns:
        Formatted info panel markup
    """
    from rich.panel import Panel
    from rich.text import Text

    content = Text()
    content.append("ℹ ", style="blue")
    content.append(message, style="white")

    panel = Panel(
        content,
        title=f"[bold blue]{title}[/bold blue]",
        border_style="blue",
        padding=(1, 2)
    )

    return panel
