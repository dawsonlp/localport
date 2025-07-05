"""Log viewing and filtering commands for LocalPort CLI."""

import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path

import structlog
import typer
from rich.console import Console
from rich.table import Table

from ..formatters.format_router import FormatRouter
from ..formatters.output_format import OutputFormat
from ..utils.rich_utils import create_error_panel, create_info_panel
from ...infrastructure.logging.service_log_manager import get_service_log_manager

logger = structlog.get_logger()
console = Console()


async def logs_command(
    services: list[str] | None = None,
    level: str | None = None,
    since: str | None = None,
    until: str | None = None,
    follow: bool = False,
    lines: int = 100,
    grep: str | None = None,
    output_format: OutputFormat = OutputFormat.TABLE
) -> None:
    """View and filter LocalPort service logs."""
    try:
        # Get log directory
        log_dir = Path.home() / ".local" / "share" / "localport" / "logs"

        if not log_dir.exists():
            console.print(create_info_panel(
                "No Logs Found",
                f"Log directory does not exist: {log_dir}\n" +
                "This is normal if LocalPort hasn't been run yet or no services have been started."
            ))
            return

        # Initialize format router
        format_router = FormatRouter(console)

        # Parse time filters
        since_dt = _parse_time_filter(since) if since else None
        until_dt = _parse_time_filter(until) if until else None

        # Compile grep pattern if provided
        grep_pattern = re.compile(grep, re.IGNORECASE) if grep else None

        # Get log entries
        log_entries = await _get_log_entries(
            log_dir=log_dir,
            services=services,
            level=level,
            since=since_dt,
            until=until_dt,
            lines=lines,
            grep_pattern=grep_pattern
        )

        if follow:
            # Follow mode - continuously tail logs
            await _follow_logs(
                log_dir=log_dir,
                services=services,
                level=level,
                grep_pattern=grep_pattern,
                output_format=output_format,
                format_router=format_router,
                initial_entries=log_entries
            )
        else:
            # Single output
            _display_logs(log_entries, output_format, format_router)

    except Exception as e:
        logger.exception("Error viewing logs")
        if output_format == OutputFormat.JSON:
            error_output = format_router.service_status_json._format_error("log_viewing_error", str(e))
            console.print(error_output)
        else:
            console.print(create_error_panel(
                "Error Viewing Logs",
                str(e),
                "Check if the log directory exists and is readable."
            ))
        raise typer.Exit(1)


async def _get_log_entries(
    log_dir: Path,
    services: list[str] | None = None,
    level: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    lines: int = 100,
    grep_pattern: re.Pattern | None = None
) -> list[dict]:
    """Get log entries based on filters."""
    entries = []

    # Find log files
    log_files = []
    if services:
        # Look for specific service log files
        for service in services:
            service_logs = list(log_dir.glob(f"*{service}*.log"))
            log_files.extend(service_logs)
    else:
        # Get all log files
        log_files = list(log_dir.glob("*.log"))

    # If no specific log files found, try the main log file
    if not log_files:
        main_log = log_dir / "localport.log"
        if main_log.exists():
            log_files = [main_log]

    # Read and parse log files
    for log_file in log_files:
        try:
            with open(log_file, encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    # Parse log entry
                    entry = _parse_log_line(line, log_file.name, line_num)
                    if not entry:
                        continue

                    # Apply filters
                    if level and entry.get('level', '').upper() != level.upper():
                        continue

                    if since and entry.get('timestamp') and entry['timestamp'] < since:
                        continue

                    if until and entry.get('timestamp') and entry['timestamp'] > until:
                        continue

                    if grep_pattern and not grep_pattern.search(line):
                        continue

                    entries.append(entry)

        except Exception as e:
            logger.warning("Failed to read log file", file=str(log_file), error=str(e))

    # Sort by timestamp and limit
    entries.sort(key=lambda x: x.get('timestamp', datetime.min))
    return entries[-lines:] if lines > 0 else entries


def _parse_log_line(line: str, filename: str, line_num: int) -> dict | None:
    """Parse a log line into structured data."""
    try:
        # Try to parse structured log format first
        # Example: timestamp='2025-07-02T22:03:33.041973' level='info' event='...'
        if "timestamp=" in line and "level=" in line:
            entry = {'raw_line': line, 'file': filename, 'line_number': line_num}

            # Extract timestamp
            timestamp_match = re.search(r"timestamp='([^']+)'", line)
            if timestamp_match:
                try:
                    entry['timestamp'] = datetime.fromisoformat(timestamp_match.group(1).replace('Z', '+00:00'))
                except ValueError:
                    pass

            # Extract level
            level_match = re.search(r"level='([^']+)'", line)
            if level_match:
                entry['level'] = level_match.group(1)

            # Extract event/message
            event_match = re.search(r"event='([^']+)'", line)
            if event_match:
                entry['message'] = event_match.group(1)

            # Extract logger name
            logger_match = re.search(r"logger='([^']+)'", line)
            if logger_match:
                entry['logger'] = logger_match.group(1)

            return entry

        # Try to parse standard log format
        # Example: [22:03:33] INFO     message...
        timestamp_match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]\s+(\w+)\s+(.+)', line)
        if timestamp_match:
            time_str, level, message = timestamp_match.groups()

            # Create timestamp for today with the time
            today = datetime.now().date()
            time_parts = time_str.split(':')
            timestamp = datetime.combine(
                today,
                datetime.min.time().replace(
                    hour=int(time_parts[0]),
                    minute=int(time_parts[1]),
                    second=int(time_parts[2])
                )
            )

            return {
                'timestamp': timestamp,
                'level': level,
                'message': message.strip(),
                'raw_line': line,
                'file': filename,
                'line_number': line_num
            }

        # Fallback - treat as unstructured log
        return {
            'timestamp': datetime.now(),  # Use current time as fallback
            'level': 'INFO',
            'message': line,
            'raw_line': line,
            'file': filename,
            'line_number': line_num
        }

    except Exception:
        return None


def _parse_time_filter(time_str: str) -> datetime:
    """Parse time filter string into datetime."""
    try:
        # Try ISO format first
        return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    except ValueError:
        pass

    try:
        # Try relative time (e.g., "1h", "30m", "2d")
        if time_str.endswith('s'):
            seconds = int(time_str[:-1])
            return datetime.now() - timedelta(seconds=seconds)
        elif time_str.endswith('m'):
            minutes = int(time_str[:-1])
            return datetime.now() - timedelta(minutes=minutes)
        elif time_str.endswith('h'):
            hours = int(time_str[:-1])
            return datetime.now() - timedelta(hours=hours)
        elif time_str.endswith('d'):
            days = int(time_str[:-1])
            return datetime.now() - timedelta(days=days)
    except ValueError:
        pass

    raise ValueError(f"Invalid time format: {time_str}. Use ISO format or relative time (1h, 30m, 2d)")


async def _follow_logs(
    log_dir: Path,
    services: list[str] | None,
    level: str | None,
    grep_pattern: re.Pattern | None,
    output_format: OutputFormat,
    format_router: FormatRouter,
    initial_entries: list[dict]
) -> None:
    """Follow logs in real-time."""
    # Display initial entries
    _display_logs(initial_entries, output_format, format_router)

    # TODO: Implement real-time log following
    # This would require file watching or periodic polling
    console.print("\n[yellow]Note: Real-time log following not yet implemented.[/yellow]")
    console.print("[dim]Press Ctrl+C to exit[/dim]")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped following logs[/yellow]")


def _display_logs(entries: list[dict], output_format: OutputFormat, format_router: FormatRouter) -> None:
    """Display log entries in the specified format."""
    if output_format == OutputFormat.JSON:
        # JSON format
        import json

        from ..formatters.json_formatter import JSONEncoder

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "command": "logs",
            "total_entries": len(entries),
            "entries": entries
        }

        json_output = json.dumps(log_data, cls=JSONEncoder, indent=2, ensure_ascii=False)
        console.print(json_output)

    elif output_format == OutputFormat.TEXT:
        # Plain text format for Linux command processing
        for entry in entries:
            # Format: TIMESTAMP LEVEL [FILE:LINE] MESSAGE
            timestamp = entry.get('timestamp', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
            level = entry.get('level', 'INFO').upper()
            file_info = f"{entry.get('file', 'unknown')}:{entry.get('line_number', 0)}"
            message = entry.get('message', entry.get('raw_line', ''))

            print(f"{timestamp} {level:8} [{file_info}] {message}")

    else:
        # Table format (default)
        if not entries:
            console.print(create_info_panel(
                "No Log Entries",
                "No log entries found matching the specified filters."
            ))
            return

        table = Table(title="LocalPort Logs")
        table.add_column("Time", style="dim")
        table.add_column("Level", style="bold")
        table.add_column("Source", style="cyan")
        table.add_column("Message", style="white")

        for entry in entries:
            timestamp = entry.get('timestamp', datetime.now())
            time_str = timestamp.strftime('%H:%M:%S')

            level = entry.get('level', 'INFO').upper()
            level_color = {
                'DEBUG': 'dim',
                'INFO': 'blue',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bright_red'
            }.get(level, 'white')

            source = entry.get('logger', entry.get('file', 'unknown'))
            message = entry.get('message', entry.get('raw_line', ''))

            # Truncate long messages
            if len(message) > 80:
                message = message[:77] + "..."

            table.add_row(
                time_str,
                f"[{level_color}]{level}[/{level_color}]",
                source,
                message
            )

        console.print(table)
        console.print(f"\n[dim]Showing {len(entries)} log entries[/dim]")


# Enhanced sync wrapper for Typer with new service logging features
def logs_sync(
    ctx: typer.Context,
    services: list[str] | None = typer.Argument(None, help="Service names to filter logs"),
    level: str | None = typer.Option(None, "--level", "-l", help="Filter by log level (DEBUG, INFO, WARNING, ERROR)"),
    since: str | None = typer.Option(None, "--since", help="Show logs since time (ISO format or relative like '1h', '30m')"),
    until: str | None = typer.Option(None, "--until", help="Show logs until time (ISO format or relative like '1h', '30m')"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output in real-time"),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines to show (0 for all)"),
    grep: str | None = typer.Option(None, "--grep", "-g", help="Filter logs by pattern (case-insensitive)"),
    # New service logging options
    list_services: bool = typer.Option(False, "--list", help="List all available service logs"),
    location: bool = typer.Option(False, "--location", help="Show log directory locations"),
    service: str | None = typer.Option(None, "--service", "-s", help="Show logs for a specific service"),
    path: bool = typer.Option(False, "--path", help="Show log file path for a service (use with --service)")
) -> None:
    """View and filter LocalPort service logs.

    [bold]Enhanced Service Logging (v0.3.4+):[/bold]
    
    LocalPort now captures raw subprocess output from kubectl and SSH processes
    in dedicated service log files, providing comprehensive diagnostic information.

    [bold]Examples:[/bold]
    
        [dim]# Show recent daemon logs (default behavior)[/dim]
        localport logs
        
        [dim]# List all available service logs[/dim]
        localport logs --list
        
        [dim]# Show logs for a specific service[/dim]
        localport logs --service postgres
        localport logs -s postgres
        
        [dim]# Show service log file path[/dim]
        localport logs --service postgres --path
        
        [dim]# Show log directory locations[/dim]
        localport logs --location
        
        [dim]# Filter service logs[/dim]
        localport logs --service postgres --grep "error"
        localport logs --service postgres --lines 50
        
        [dim]# Legacy service filtering (searches all logs)[/dim]
        localport logs postgres
        localport logs --level ERROR
        localport logs --since 1h
        
        [dim]# Output formats[/dim]
        localport --output text logs --service postgres
        localport --output json logs --list

    [bold]Service vs Daemon Logs:[/bold]
    
    • [cyan]Service logs[/cyan]: Raw kubectl/SSH output for each service instance
    • [cyan]Daemon logs[/cyan]: Structured LocalPort application logs
    • Use --service for service-specific diagnostics
    • Use default behavior for daemon/application logs
    """
    # Get output format from context
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    
    # Handle new service logging commands
    if list_services:
        asyncio.run(list_service_logs_command(output_format))
        return
    
    if location:
        asyncio.run(show_log_location_command(output_format))
        return
    
    if service:
        if path:
            # Show service log file path
            try:
                service_log_manager = get_service_log_manager()
                service_logs = service_log_manager.list_service_logs()
                
                # Find matching service logs (fuzzy matching)
                matching_logs = [
                    log for log in service_logs 
                    if service.lower() in log["service_name"].lower()
                ]
                
                if not matching_logs:
                    if output_format == OutputFormat.JSON:
                        import json
                        error_data = {"error": "service_not_found", "service": service}
                        console.print(json.dumps(error_data))
                    else:
                        available_services = [log["service_name"] for log in service_logs]
                        console.print(create_error_panel(
                            f"Service '{service}' Not Found",
                            f"No service logs found matching '{service}'.",
                            f"Available services: {', '.join(available_services) if available_services else 'None'}"
                        ))
                    raise typer.Exit(1)
                
                # Use most recent if multiple matches
                target_log = max(matching_logs, key=lambda x: x["modified"])
                
                if output_format == OutputFormat.JSON:
                    import json
                    path_data = {
                        "service_name": target_log["service_name"],
                        "service_id": target_log["service_id"],
                        "log_file": str(target_log["log_file"])
                    }
                    console.print(json.dumps(path_data, indent=2))
                else:
                    console.print(str(target_log["log_file"]))
                    
            except Exception as e:
                if output_format == OutputFormat.JSON:
                    import json
                    error_data = {"error": "path_lookup_error", "message": str(e)}
                    console.print(json.dumps(error_data))
                else:
                    console.print(create_error_panel(
                        "Error Getting Log Path",
                        str(e),
                        "Check if the service exists and logs are accessible."
                    ))
                raise typer.Exit(1)
        else:
            # Show service logs
            asyncio.run(show_service_log_command(service, lines, follow, grep, output_format))
        return
    
    # Default behavior: show daemon logs (backward compatibility)
    asyncio.run(logs_command(services, level, since, until, follow, lines, grep, output_format))


# New service logging commands for v0.3.4

async def list_service_logs_command(output_format: OutputFormat = OutputFormat.TABLE) -> None:
    """List all available service logs with metadata."""
    try:
        service_log_manager = get_service_log_manager()
        service_logs = service_log_manager.list_service_logs()
        
        if output_format == OutputFormat.JSON:
            import json
            from ..formatters.json_formatter import JSONEncoder
            
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "command": "logs --list",
                "total_services": len(service_logs),
                "services": [
                    {
                        "service_id": log["service_id"],
                        "service_name": log["service_name"],
                        "log_file": str(log["log_file"]),
                        "size_bytes": log["size"],
                        "size_mb": round(log["size"] / (1024 * 1024), 2),
                        "modified": log["modified"].isoformat(),
                        "is_active": log["is_active"],
                        "rotated_files": log["rotated_files"]
                    }
                    for log in service_logs
                ]
            }
            
            json_output = json.dumps(log_data, cls=JSONEncoder, indent=2, ensure_ascii=False)
            console.print(json_output)
            
        elif output_format == OutputFormat.TEXT:
            # Plain text format
            for log in service_logs:
                size_mb = round(log["size"] / (1024 * 1024), 2)
                status = "active" if log["is_active"] else "stopped"
                rotated = f" ({log['rotated_files']} rotated)" if log["rotated_files"] > 0 else ""
                print(f"{log['service_name']} ({status}, {size_mb}MB{rotated})")
                
        else:
            # Table format (default)
            if not service_logs:
                console.print(create_info_panel(
                    "No Service Logs Found",
                    "No service logs are available. This is normal if no services have been started yet."
                ))
                return
                
            table = Table(title="🚀 Available Service Logs")
            table.add_column("Service", style="cyan", no_wrap=True)
            table.add_column("Status", style="bold")
            table.add_column("Size", style="dim", justify="right")
            table.add_column("Last Modified", style="dim")
            table.add_column("Files", style="dim", justify="center")
            
            for log in service_logs:
                # Format size
                size_mb = log["size"] / (1024 * 1024)
                if size_mb < 0.1:
                    size_str = f"{log['size']} B"
                else:
                    size_str = f"{size_mb:.1f} MB"
                
                # Format status
                if log["is_active"]:
                    status = "[green]🟢 Active[/green]"
                else:
                    status = "[dim]⚫ Stopped[/dim]"
                
                # Format modified time
                modified = log["modified"]
                if modified.date() == datetime.now().date():
                    time_str = modified.strftime("%H:%M:%S")
                else:
                    time_str = modified.strftime("%m/%d %H:%M")
                
                # Format file count
                total_files = 1 + log["rotated_files"]
                files_str = str(total_files) if total_files == 1 else f"{total_files} files"
                
                table.add_row(
                    log["service_name"],
                    status,
                    size_str,
                    time_str,
                    files_str
                )
            
            console.print(table)
            console.print(f"\n[dim]💡 Tip: Use 'localport logs <service>' to view specific service logs[/dim]")
            
    except Exception as e:
        logger.exception("Error listing service logs")
        if output_format == OutputFormat.JSON:
            error_data = {"error": "service_log_listing_error", "message": str(e)}
            console.print(json.dumps(error_data))
        else:
            console.print(create_error_panel(
                "Error Listing Service Logs",
                str(e),
                "Check if the service log manager is properly initialized."
            ))
        raise typer.Exit(1)


async def show_log_location_command(output_format: OutputFormat = OutputFormat.TABLE) -> None:
    """Show service log directory locations."""
    try:
        service_log_manager = get_service_log_manager()
        log_directory = service_log_manager.get_log_directory()
        daemon_log_dir = log_directory.parent
        
        if output_format == OutputFormat.JSON:
            import json
            
            location_data = {
                "timestamp": datetime.now().isoformat(),
                "command": "logs --location",
                "daemon_logs": str(daemon_log_dir),
                "service_logs": str(log_directory),
                "exists": log_directory.exists()
            }
            
            json_output = json.dumps(location_data, indent=2, ensure_ascii=False)
            console.print(json_output)
            
        elif output_format == OutputFormat.TEXT:
            # Plain text format
            print(f"Service logs: {log_directory}")
            print(f"Daemon logs: {daemon_log_dir}")
            
        else:
            # Table format (default)
            table = Table(title="📁 LocalPort Log Locations")
            table.add_column("Type", style="cyan")
            table.add_column("Location", style="white")
            table.add_column("Status", style="bold")
            
            # Service logs
            service_status = "[green]✓ Exists[/green]" if log_directory.exists() else "[yellow]⚠ Not Created[/yellow]"
            table.add_row("Service Logs", str(log_directory), service_status)
            
            # Daemon logs
            daemon_status = "[green]✓ Exists[/green]" if daemon_log_dir.exists() else "[yellow]⚠ Not Created[/yellow]"
            table.add_row("Daemon Logs", str(daemon_log_dir), daemon_status)
            
            console.print(table)
            
            if not log_directory.exists():
                console.print("\n[dim]💡 Service log directory will be created when the first service starts[/dim]")
                
    except Exception as e:
        logger.exception("Error showing log locations")
        if output_format == OutputFormat.JSON:
            error_data = {"error": "log_location_error", "message": str(e)}
            console.print(json.dumps(error_data))
        else:
            console.print(create_error_panel(
                "Error Showing Log Locations",
                str(e),
                "Check if the service log manager is properly initialized."
            ))
        raise typer.Exit(1)


async def show_service_log_command(
    service_name: str,
    lines: int = 100,
    follow: bool = False,
    grep: str | None = None,
    output_format: OutputFormat = OutputFormat.TABLE
) -> None:
    """Show logs for a specific service."""
    try:
        service_log_manager = get_service_log_manager()
        service_logs = service_log_manager.list_service_logs()
        
        # Find matching service logs (fuzzy matching)
        matching_logs = [
            log for log in service_logs 
            if service_name.lower() in log["service_name"].lower()
        ]
        
        if not matching_logs:
            if output_format == OutputFormat.JSON:
                error_data = {"error": "service_not_found", "service": service_name}
                console.print(json.dumps(error_data))
            else:
                available_services = [log["service_name"] for log in service_logs]
                console.print(create_error_panel(
                    f"Service '{service_name}' Not Found",
                    f"No service logs found matching '{service_name}'.",
                    f"Available services: {', '.join(available_services) if available_services else 'None'}"
                ))
            raise typer.Exit(1)
        
        # If multiple matches, use the most recent one
        if len(matching_logs) > 1:
            target_log = max(matching_logs, key=lambda x: x["modified"])
            if output_format != OutputFormat.JSON:
                console.print(f"[yellow]Multiple matches found, showing most recent: {target_log['service_name']}[/yellow]")
        else:
            target_log = matching_logs[0]
        
        # Read and display the log file
        log_file = target_log["log_file"]
        
        if not log_file.exists():
            if output_format == OutputFormat.JSON:
                error_data = {"error": "log_file_not_found", "file": str(log_file)}
                console.print(json.dumps(error_data))
            else:
                console.print(create_error_panel(
                    "Log File Not Found",
                    f"Log file does not exist: {log_file}",
                    "The service may have been stopped and logs cleaned up."
                ))
            raise typer.Exit(1)
        
        # Compile grep pattern if provided
        grep_pattern = re.compile(grep, re.IGNORECASE) if grep else None
        
        # Read log file
        log_lines = []
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.rstrip('\n\r')
                    if grep_pattern and not grep_pattern.search(line):
                        continue
                    log_lines.append({
                        'line_number': line_num,
                        'content': line,
                        'timestamp': datetime.now()  # We could parse timestamps from service logs
                    })
        except Exception as e:
            if output_format == OutputFormat.JSON:
                error_data = {"error": "log_read_error", "message": str(e)}
                console.print(json.dumps(error_data))
            else:
                console.print(create_error_panel(
                    "Error Reading Log File",
                    str(e),
                    "Check if the log file is readable and not corrupted."
                ))
            raise typer.Exit(1)
        
        # Apply line limit
        if lines > 0:
            log_lines = log_lines[-lines:]
        
        # Display logs
        if output_format == OutputFormat.JSON:
            import json
            
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "command": f"logs {service_name}",
                "service_name": target_log["service_name"],
                "service_id": target_log["service_id"],
                "log_file": str(log_file),
                "total_lines": len(log_lines),
                "lines": [
                    {
                        "line_number": line["line_number"],
                        "content": line["content"]
                    }
                    for line in log_lines
                ]
            }
            
            json_output = json.dumps(log_data, indent=2, ensure_ascii=False)
            console.print(json_output)
            
        elif output_format == OutputFormat.TEXT:
            # Plain text format - just output the log lines
            for line in log_lines:
                print(line["content"])
                
        else:
            # Rich format (default)
            if not log_lines:
                console.print(create_info_panel(
                    "No Log Content",
                    f"No log content found for service '{target_log['service_name']}'."
                ))
                return
            
            # Show header with service info
            console.print(f"\n[bold cyan]📋 Service Logs: {target_log['service_name']}[/bold cyan]")
            console.print(f"[dim]Service ID: {target_log['service_id']}[/dim]")
            console.print(f"[dim]Log File: {log_file}[/dim]")
            console.print(f"[dim]Showing {len(log_lines)} lines{' (filtered)' if grep else ''}[/dim]\n")
            
            # Display log content with line numbers
            for line in log_lines:
                line_num_str = f"{line['line_number']:4d}"
                console.print(f"[dim]{line_num_str}[/dim] {line['content']}")
            
            console.print(f"\n[dim]💡 Use --follow to stream logs in real-time[/dim]")
        
        # TODO: Implement follow mode for service logs
        if follow:
            console.print("\n[yellow]Note: Real-time following for service logs not yet implemented.[/yellow]")
            
    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Error showing service log")
        if output_format == OutputFormat.JSON:
            error_data = {"error": "service_log_error", "message": str(e)}
            console.print(json.dumps(error_data))
        else:
            console.print(create_error_panel(
                "Error Showing Service Log",
                str(e),
                "Check if the service exists and logs are accessible."
            ))
        raise typer.Exit(1)


# Sync wrappers for new commands

def list_service_logs_sync(ctx: typer.Context) -> None:
    """List all available service logs with metadata."""
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    asyncio.run(list_service_logs_command(output_format))


def show_log_location_sync(ctx: typer.Context) -> None:
    """Show service log directory locations."""
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    asyncio.run(show_log_location_command(output_format))


def show_service_log_sync(
    ctx: typer.Context,
    service_name: str,
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines to show (0 for all)"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output in real-time"),
    grep: str | None = typer.Option(None, "--grep", "-g", help="Filter logs by pattern (case-insensitive)")
) -> None:
    """Show logs for a specific service."""
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    asyncio.run(show_service_log_command(service_name, lines, follow, grep, output_format))
