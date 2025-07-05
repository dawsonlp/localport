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


async def _get_cluster_health_data() -> dict | None:
    """Get cluster health data using lightweight approach (same as status command)."""
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

        # Use lightweight kubectl client directly (same as status command)
        from ...infrastructure.cluster_monitoring.kubectl_client import KubectlClient
        from ...domain.entities.cluster_health import ClusterHealth
        
        kubectl_client = KubectlClient(timeout=30, retry_attempts=2)  # Use normal timeouts for detailed view
        
        cluster_data = {}
        for context in contexts:
            try:
                # Get basic cluster info and resource counts
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
                        events=[],  # Skip events for performance
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
        logger.error("Failed to get cluster health data", error=str(e))
        return None


def _format_cluster_health_status(cluster_health) -> str:
    """Format cluster health status with color indicators."""
    if not cluster_health:
        return "[dim]Unknown[/dim]"
    
    # cluster_health is now a ClusterHealth object, not a dict
    is_healthy = cluster_health.is_healthy
    last_check = cluster_health.last_check_time
    
    if is_healthy:
        status = "[green]🟢 Healthy[/green]"
    else:
        status = "[red]🔴 Unhealthy[/red]"
    
    if last_check:
        try:
            # last_check is already a datetime object, use UTC for consistency
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
        # Get cluster health data using lightweight approach
        cluster_data = await _get_cluster_health_data()
        
        if not cluster_data:
            console.print(create_error_panel(
                "Cluster Health Monitoring Unavailable",
                "Cluster health monitoring is not enabled or no kubectl services configured.",
                "Enable cluster health monitoring in your configuration or add kubectl services."
            ))
            raise typer.Exit(1)

        # Filter by context if specified
        if context:
            if context not in cluster_data:
                console.print(create_error_panel(
                    "Context Not Found",
                    f"Cluster context '{context}' not found in configuration.",
                    "Check your configuration or use a different context."
                ))
                raise typer.Exit(1)
            cluster_data = {context: cluster_data[context]}

        if output_format == OutputFormat.JSON:
            # JSON output
            import json
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

            for ctx, data in cluster_data.items():
                if data.get('error'):
                    # Error case
                    table.add_row(
                        ctx,
                        "[red]🔴 Error[/red]",
                        "Error",
                        "Error",
                        "Error",
                        "Error"
                    )
                else:
                    health_data = data.get('health')
                    cluster_info = data.get('info')
                    
                    # Format status
                    status = _format_cluster_health_status(health_data)
                    
                    # Format cluster info (cluster_info is a ClusterInfo object)
                    if cluster_info:
                        api_server = cluster_info.api_server_url or 'Unknown'
                    else:
                        api_server = 'Unknown'
                    
                    # Use health_data for node/pod counts (health_data is a ClusterHealth object)
                    if health_data:
                        node_count = health_data.total_nodes
                        pod_count = health_data.total_pods
                    else:
                        node_count = 0
                        pod_count = 0
                    
                    # Format last check time (health_data.last_check_time is a datetime object)
                    if health_data and health_data.last_check_time:
                        try:
                            last_check_str = health_data.last_check_time.strftime('%H:%M:%S')
                        except Exception:
                            last_check_str = str(health_data.last_check_time)
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
            contexts = await cluster_health_manager.get_monitored_contexts()

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
            contexts = await cluster_health_manager.get_monitored_contexts()

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
