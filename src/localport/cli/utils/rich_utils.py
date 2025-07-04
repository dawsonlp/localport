"""Rich utilities for CLI formatting and logging."""

import logging

import structlog
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install


def setup_rich_logging(
    verbosity_level: int = 0,
    console: Console | None = None,
    level: str | None = None,  # Backward compatibility
    verbose: bool | None = None  # Backward compatibility
) -> None:
    """Setup Rich-based logging with verbosity levels.

    Args:
        verbosity_level: Verbosity level (-1=quiet, 0=clean, 1=info, 2=debug)
        console: Rich console instance to use
        level: Legacy log level (for backward compatibility)
        verbose: Legacy verbose flag (for backward compatibility)
    """
    if console is None:
        console = Console()

    # Handle backward compatibility
    if level is not None or verbose is not None:
        # Legacy mode: convert old parameters to verbosity level
        if verbose:
            verbosity_level = 2 if level == "DEBUG" else 1
        else:
            verbosity_level = 0

    # Map verbosity to log levels
    log_level_map = {
        -1: logging.ERROR,    # Quiet: Only errors
        0: logging.WARNING,   # Clean: Only warnings/errors
        1: logging.INFO,      # Informational: Include info logs
        2: logging.DEBUG      # Debug: Everything
    }
    
    log_level = log_level_map.get(verbosity_level, logging.WARNING)
    
    # Install rich traceback handler
    install(console=console, show_locals=(verbosity_level >= 2))

    # Configure different output styles per verbosity level
    if verbosity_level <= 0:
        # Clean/Quiet mode: Minimal, structured output
        rich_handler = RichHandler(
            console=console,
            show_time=False,      # No timestamps
            show_path=False,      # No file paths
            show_level=False,     # No log levels
            rich_tracebacks=True,
            markup=True
        )
    elif verbosity_level == 1:
        # Info mode: Helpful context
        rich_handler = RichHandler(
            console=console,
            show_time=True,       # Show timestamps
            show_path=False,      # No file paths
            show_level=False,     # No log levels (cleaner)
            rich_tracebacks=True,
            markup=True
        )
    else:  # verbosity_level >= 2
        # Debug mode: Full details
        rich_handler = RichHandler(
            console=console,
            show_time=True,       # Show timestamps
            show_path=True,       # Show file paths
            show_level=True,      # Show log levels
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True
        )

    rich_handler.setLevel(log_level)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[rich_handler],
        force=True  # Override any existing configuration
    )

    # Configure structlog based on verbosity level
    if verbosity_level >= 2:
        # Debug mode: Use JSON renderer for structured output
        final_processor = structlog.processors.JSONRenderer()
    elif verbosity_level == 1:
        # Info mode: Use clean key-value renderer
        final_processor = structlog.processors.KeyValueRenderer(
            key_order=['timestamp', 'level', 'event'],
            drop_missing=True
        )
    else:
        # Clean/Quiet mode: Minimal output
        final_processor = structlog.processors.KeyValueRenderer(
            key_order=['event'],
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


def format_technology(technology) -> str:
    """Format technology name with appropriate styling.

    Args:
        technology: Technology name (kubectl, ssh, etc.) or ForwardingTechnology enum

    Returns:
        Formatted technology string
    """
    # Handle both string and enum types
    if hasattr(technology, 'value'):
        # It's an enum, get the string value
        tech_str = technology.value
    else:
        # It's already a string
        tech_str = str(technology)
    
    tech_colors = {
        "kubectl": "blue",
        "ssh": "green",
        "docker": "cyan"
    }
    color = tech_colors.get(tech_str.lower(), "white")
    return f"[{color}]{tech_str}[/{color}]"


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
