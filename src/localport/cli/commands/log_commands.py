"""Log viewing and filtering commands for LocalPort CLI."""

import asyncio
from typing import Optional, List
from pathlib import Path
from datetime import datetime, timedelta
import re

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text
import structlog

from ..formatters.format_router import FormatRouter
from ..formatters.output_format import OutputFormat
from ..utils.rich_utils import create_error_panel, create_info_panel

logger = structlog.get_logger()
console = Console()


async def logs_command(
    services: Optional[List[str]] = None,
    level: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    follow: bool = False,
    lines: int = 100,
    grep: Optional[str] = None,
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
    services: Optional[List[str]] = None,
    level: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    lines: int = 100,
    grep_pattern: Optional[re.Pattern] = None
) -> List[dict]:
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
            with open(log_file, 'r', encoding='utf-8') as f:
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


def _parse_log_line(line: str, filename: str, line_num: int) -> Optional[dict]:
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
    services: Optional[List[str]],
    level: Optional[str],
    grep_pattern: Optional[re.Pattern],
    output_format: OutputFormat,
    format_router: FormatRouter,
    initial_entries: List[dict]
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


def _display_logs(entries: List[dict], output_format: OutputFormat, format_router: FormatRouter) -> None:
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


# Sync wrapper for Typer
def logs_sync(
    ctx: typer.Context,
    services: Optional[List[str]] = typer.Argument(None, help="Service names to filter logs"),
    level: Optional[str] = typer.Option(None, "--level", "-l", help="Filter by log level (DEBUG, INFO, WARNING, ERROR)"),
    since: Optional[str] = typer.Option(None, "--since", help="Show logs since time (ISO format or relative like '1h', '30m')"),
    until: Optional[str] = typer.Option(None, "--until", help="Show logs until time (ISO format or relative like '1h', '30m')"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output in real-time"),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines to show (0 for all)"),
    grep: Optional[str] = typer.Option(None, "--grep", "-g", help="Filter logs by pattern (case-insensitive)")
) -> None:
    """View and filter LocalPort service logs.
    
    Examples:
        localport logs                          # Show recent logs
        localport logs postgres                 # Show logs for postgres service
        localport logs --level ERROR            # Show only error logs
        localport logs --since 1h              # Show logs from last hour
        localport logs --grep "failed"         # Show logs containing "failed"
        localport --output text logs           # Plain text output for piping
        localport --output json logs           # JSON output for processing
    """
    # Get output format from context
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    asyncio.run(logs_command(services, level, since, until, follow, lines, grep, output_format))
