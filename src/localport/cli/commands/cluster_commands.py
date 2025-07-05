"""Cluster management commands for LocalPort CLI."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import structlog
import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ...application.services.cluster_health_manager import ClusterHealthManager
from ...infrastructure.repositories.yaml_config_repository import YamlConfigRepository
from ..formatters.format_router import FormatRouter
from ..formatters.output_format import OutputFormat
from ..utils.rich_utils import (
    create_error_panel,
    create_success_panel,
)

logger = structlog.get_logger()
console = Console()


async def _load_cluster_health_manager() -> ClusterHealthManager | None:
    """Load cluster health manager with configuration."""
    try:
        # Load configuration (same logic as other commands)
        config_path = None
        for path in ["./localport.yaml", "~/.config/localport/config.yaml"]:
            test_path = Path(path).expanduser()
            if test_path.exists():
                config_path = test_path
                break

        if not config_path:
            return None

        # Load configuration
        config_repo = YamlConfigRepository(str(config_path))
        config = await config_repo.load_configuration()
        
        # Check if cluster health is enabled
        cluster_health_config = config.get('defaults', {}).get('cluster_health', {})
        if not cluster_health_config.get('enabled', True):
            return None

        # Initialize cluster health manager
        cluster_health_manager = ClusterHealthManager()
        
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

        # Start monitoring for each context
        for context in contexts:
            await cluster_health_manager.start_monitoring(context, cluster_health_config)

        return cluster_health_manager

    except Exception as e:
        logger.error("Failed to load cluster health manager", error=str(e))
        return None


def _format_cluster_health_status(cluster_health: dict[str, Any]) -> str:
    """Format cluster health status with color indicators."""
    if not cluster_health:
        return "[dim]Unknown[/dim]"
    
    is_healthy = cluster_health.get('is_healthy', False)
    last_check = cluster_health.get('last_check_time')
    
    if is_healthy:
        status = "[green]🟢 Healthy[/green]"
    else:
        status = "[red]🔴 Unhealthy[/red]"
    
    if last_check:
        try:
            last_check_dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
            time_ago = datetime.now().replace(tzinfo=last_check_dt.tzinfo) - last_check_dt
            if time_ago.total_seconds() < 60:
                time_str = f"{int(time_ago.total_seconds())}s ago"
            elif time_ago.total_seconds() < 3600:
                time_str = f"{int(time_ago.total_seconds() // 60)}m ago"
            else:
                time_str = f"{int(time_ago.total_seconds() // 3600)}h ago"
            status += f" [dim]({time_str})[/dim]"
        except Exception:
            pass
    
    return status


async def cluster_status_command(
    context: str | None = None,
    output_format: OutputFormat = OutputFormat.TABLE
) -> None:
    """Show detailed cluster health information."""
    try:
        cluster_health_manager = await _load_cluster_health_manager()
        
        if not cluster_health_manager:
            console.print(create_error_panel(
                "Cluster Health Monitoring Unavailable",
                "Cluster health monitoring is not enabled or no kubectl services configured.",
                "Enable cluster health monitoring in your configuration or add kubectl services."
            ))
            raise typer.Exit(1)

        # Get cluster health data
        if context:
            contexts = [context]
        else:
            contexts = list(cluster_health_manager.get_monitored_contexts())

        if not contexts:
            console.print(create_error_panel(
                "No Clusters Found",
                "No cluster contexts are currently being monitored.",
                "Add kubectl services to your configuration to enable cluster monitoring."
            ))
            raise typer.Exit(1)

        if output_format == OutputFormat.JSON:
            # JSON output
            import json
            cluster_data = {}
            for ctx in contexts:
                health_data = await cluster_health_manager.get_cluster_health(ctx)
                cluster_info = await cluster_health_manager.get_cluster_info(ctx)
                cluster_data[ctx] = {
                    'health': health_data,
                    'info': cluster_info
                }
            console.print(json.dumps(cluster_data, indent=2, default=str))
        else:
            # Table output
            table = Table(title="Cluster Health Status")
            table.add_column("Context", style="bold blue")
            table.add_column("Status", style="bold")
            table.add_column("API Server", style="cyan")
            table.add_column("Nodes", style="green")
            table.add_column("Pods", style="yellow")
            table.add_column("Last Check", style="dim")

            for ctx in contexts:
                try:
                    health_data = await cluster_health_manager.get_cluster_health(ctx)
                    cluster_info = await cluster_health_manager.get_cluster_info(ctx)
                    
                    # Format status
                    status = _format_cluster_health_status(health_data)
                    
                    # Format cluster info
                    api_server = cluster_info.get('api_server', 'Unknown') if cluster_info else 'Unknown'
                    node_count = cluster_info.get('node_count', 0) if cluster_info else 0
                    pod_count = cluster_info.get('pod_count', 0) if cluster_info else 0
                    
                    # Format last check time
                    last_check = health_data.get('last_check_time', '') if health_data else ''
                    if last_check:
                        try:
                            last_check_dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                            last_check_str = last_check_dt.strftime('%H:%M:%S')
                        except Exception:
                            last_check_str = last_check
                    else:
                        last_check_str = 'Never'
                    
                    table.add_row(
                        ctx,
                        status,
                        api_server,
                        str(node_count),
                        str(pod_count),
                        last_check_str
                    )
                    
                except Exception as e:
                    logger.error("Error getting cluster data", context=ctx, error=str(e))
                    table.add_row(
                        ctx,
                        "[red]🔴 Error[/red]",
                        "Error",
                        "Error",
                        "Error",
                        "Error"
                    )

            console.print(table)

    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Error getting cluster status")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs for more details."
        ))
        raise typer.Exit(1)


async def cluster_events_command(
    context: str | None = None,
    since: str = "1h",
    limit: int = 20,
    output_format: OutputFormat = OutputFormat.TABLE
) -> None:
    """Show recent cluster events."""
    try:
        cluster_health_manager = await _load_cluster_health_manager()
        
        if not cluster_health_manager:
            console.print(create_error_panel(
                "Cluster Health Monitoring Unavailable",
                "Cluster health monitoring is not enabled or no kubectl services configured.",
                "Enable cluster health monitoring in your configuration."
            ))
            raise typer.Exit(1)

        # Parse since parameter
        try:
            if since.endswith('h'):
                hours = int(since[:-1])
                since_dt = datetime.now() - timedelta(hours=hours)
            elif since.endswith('m'):
                minutes = int(since[:-1])
                since_dt = datetime.now() - timedelta(minutes=minutes)
            elif since.endswith('s'):
                seconds = int(since[:-1])
                since_dt = datetime.now() - timedelta(seconds=seconds)
            else:
                # Try to parse as ISO format
                since_dt = datetime.fromisoformat(since)
        except Exception:
            console.print(create_error_panel(
                "Invalid Time Format",
                f"Invalid time format: {since}",
                "Use formats like '1h', '30m', '60s' or ISO format."
            ))
            raise typer.Exit(1)

        # Get contexts
        if context:
            contexts = [context]
        else:
            contexts = list(cluster_health_manager.get_monitored_contexts())

        if not contexts:
            console.print(create_error_panel(
                "No Clusters Found",
                "No cluster contexts are currently being monitored.",
                "Add kubectl services to your configuration."
            ))
            raise typer.Exit(1)

        if output_format == OutputFormat.JSON:
            # JSON output
            import json
            events_data = {}
            for ctx in contexts:
                events = await cluster_health_manager.get_cluster_events(ctx, since_dt)
                events_data[ctx] = events[:limit] if events else []
            console.print(json.dumps(events_data, indent=2, default=str))
        else:
            # Table output
            table = Table(title=f"Cluster Events (last {since})")
            table.add_column("Context", style="bold blue")
            table.add_column("Time", style="dim")
            table.add_column("Type", style="cyan")
            table.add_column("Reason", style="yellow")
            table.add_column("Object", style="green")
            table.add_column("Message", style="white")

            for ctx in contexts:
                try:
                    events = await cluster_health_manager.get_cluster_events(ctx, since_dt)
                    if events:
                        for event in events[:limit]:
                            # Format event time
                            event_time = event.get('timestamp', '')
                            if event_time:
                                try:
                                    event_dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                                    time_str = event_dt.strftime('%H:%M:%S')
                                except Exception:
                                    time_str = event_time
                            else:
                                time_str = 'Unknown'
                            
                            # Format event type with color
                            event_type = event.get('type', 'Unknown')
                            if event_type == 'Warning':
                                type_str = f"[yellow]{event_type}[/yellow]"
                            elif event_type == 'Error':
                                type_str = f"[red]{event_type}[/red]"
                            else:
                                type_str = f"[green]{event_type}[/green]"
                            
                            table.add_row(
                                ctx,
                                time_str,
                                type_str,
                                event.get('reason', 'Unknown'),
                                event.get('object', 'Unknown'),
                                event.get('message', 'No message')[:60] + ('...' if len(event.get('message', '')) > 60 else '')
                            )
                    else:
                        table.add_row(
                            ctx,
                            "[dim]No events[/dim]",
                            "",
                            "",
                            "",
                            ""
                        )
                        
                except Exception as e:
                    logger.error("Error getting cluster events", context=ctx, error=str(e))
                    table.add_row(
                        ctx,
                        "[red]Error[/red]",
                        "",
                        "",
                        "",
                        str(e)
                    )

            console.print(table)

    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Error getting cluster events")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs for more details."
        ))
        raise typer.Exit(1)


async def cluster_pods_command(
    context: str | None = None,
    namespace: str | None = None,
    output_format: OutputFormat = OutputFormat.TABLE
) -> None:
    """Show pod status for active services."""
    try:
        cluster_health_manager = await _load_cluster_health_manager()
        
        if not cluster_health_manager:
            console.print(create_error_panel(
                "Cluster Health Monitoring Unavailable",
                "Cluster health monitoring is not enabled or no kubectl services configured.",
                "Enable cluster health monitoring in your configuration."
            ))
            raise typer.Exit(1)

        # Get contexts
        if context:
            contexts = [context]
        else:
            contexts = list(cluster_health_manager.get_monitored_contexts())

        if not contexts:
            console.print(create_error_panel(
                "No Clusters Found",
                "No cluster contexts are currently being monitored.",
                "Add kubectl services to your configuration."
            ))
            raise typer.Exit(1)

        if output_format == OutputFormat.JSON:
            # JSON output
            import json
            pods_data = {}
            for ctx in contexts:
                # Get pod status for this context
                # Note: This would need to be implemented in ClusterHealthManager
                pods_data[ctx] = {"message": "Pod status API not yet implemented"}
            console.print(json.dumps(pods_data, indent=2, default=str))
        else:
            # Table output
            table = Table(title="Pod Status for Active Services")
            table.add_column("Context", style="bold blue")
            table.add_column("Namespace", style="cyan")
            table.add_column("Pod", style="green")
            table.add_column("Status", style="bold")
            table.add_column("Restarts", style="yellow")
            table.add_column("Age", style="dim")

            for ctx in contexts:
                try:
                    # For now, show a placeholder message
                    # This would be implemented with actual pod status from ClusterHealthManager
                    table.add_row(
                        ctx,
                        namespace or "default",
                        "[dim]Pod status API not yet implemented[/dim]",
                        "[yellow]Pending[/yellow]",
                        "0",
                        "Unknown"
                    )
                        
                except Exception as e:
                    logger.error("Error getting pod status", context=ctx, error=str(e))
                    table.add_row(
                        ctx,
                        namespace or "default",
                        "[red]Error[/red]",
                        "[red]Error[/red]",
                        "Error",
                        "Error"
                    )

            console.print(table)

    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Error getting pod status")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs for more details."
        ))
        raise typer.Exit(1)


# Sync wrappers for Typer
def cluster_status_sync(
    ctx: typer.Context,
    context: str | None = typer.Option(None, "--context", "-c", help="Specific cluster context to check")
) -> None:
    """Show detailed cluster health information."""
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    asyncio.run(cluster_status_command(context, output_format))


def cluster_events_sync(
    ctx: typer.Context,
    context: str | None = typer.Option(None, "--context", "-c", help="Specific cluster context to check"),
    since: str = typer.Option("1h", "--since", "-s", help="Show events since this time (e.g., 1h, 30m, 60s)"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of events to show")
) -> None:
    """Show recent cluster events that might affect services."""
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    asyncio.run(cluster_events_command(context, since, limit, output_format))


def cluster_pods_sync(
    ctx: typer.Context,
    context: str | None = typer.Option(None, "--context", "-c", help="Specific cluster context to check"),
    namespace: str | None = typer.Option(None, "--namespace", "-n", help="Specific namespace to check")
) -> None:
    """Show pod status for resources used by active services."""
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    asyncio.run(cluster_pods_command(context, namespace, output_format))
