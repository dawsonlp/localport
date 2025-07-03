# CLI Reference

This guide provides comprehensive documentation for all LocalPort CLI commands, options, and usage patterns.

## Global Options

These options are available for all commands:

```bash
localport [GLOBAL_OPTIONS] COMMAND [COMMAND_OPTIONS]
```

### Global Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--config PATH` | `-c` | Path to configuration file | Auto-detected |
| `--verbose` | `-v` | Enable verbose logging | `false` |
| `--quiet` | `-q` | Suppress non-essential output | `false` |
| `--log-level LEVEL` | | Set log level (DEBUG, INFO, WARN, ERROR) | `INFO` |
| `--no-color` | | Disable colored output | `false` |
| `--output FORMAT` | `-o` | Output format (table, json, text) | `table` |
| `--version` | `-V` | Show version information | |
| `--help` | `-h` | Show help message | |

### Examples

```bash
# Use custom configuration file
localport --config /path/to/config.yaml start --all

# Enable verbose logging
localport --verbose start postgres

# Output in JSON format
localport --output json status

# Quiet mode (errors only)
localport --quiet start --all
```

## Service Management Commands

### `localport start`

Start port forwarding services.

```bash
localport start [OPTIONS] [SERVICES...]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--all` | `-a` | Start all enabled services |
| `--tag TAG` | `-t` | Start services with specific tag |
| `--wait` | | Wait for services to be healthy before returning |
| `--no-wait` | | Don't wait for health checks (default) |
| `--timeout SECONDS` | | Timeout for health checks (default: 30) |

#### Examples

```bash
# Start all services
localport start --all

# Start specific services
localport start postgres redis kafka

# Start services by tag
localport start --tag database
localport start --tag essential

# Start and wait for health checks
localport start --all --wait --timeout 60

# Start with verbose output
localport --verbose start postgres
```

#### Exit Codes

- `0`: All services started successfully
- `1`: One or more services failed to start
- `2`: Configuration error
- `130`: Interrupted by user (Ctrl+C)

### `localport stop`

Stop running port forwarding services.

```bash
localport stop [OPTIONS] [SERVICES...]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--all` | `-a` | Stop all running services |
| `--tag TAG` | `-t` | Stop services with specific tag |
| `--force` | `-f` | Force stop (kill processes) |
| `--timeout SECONDS` | | Timeout for graceful shutdown (default: 10) |

#### Examples

```bash
# Stop all services
localport stop --all

# Stop specific services
localport stop postgres redis

# Stop services by tag
localport stop --tag database

# Force stop with immediate termination
localport stop --all --force

# Stop with custom timeout
localport stop --all --timeout 30
```

#### Exit Codes

- `0`: All services stopped successfully
- `1`: One or more services failed to stop
- `2`: Configuration error

### `localport status`

Show status of port forwarding services.

```bash
localport status [OPTIONS] [SERVICES...]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--all` | `-a` | Show all services (including disabled) |
| `--tag TAG` | `-t` | Show services with specific tag |
| `--watch` | `-w` | Watch status in real-time |
| `--refresh SECONDS` | | Refresh interval for watch mode (default: 2) |
| `--health` | | Include detailed health information |

#### Examples

```bash
# Show status of all enabled services
localport status

# Show specific services
localport status postgres redis

# Show all services including disabled
localport status --all

# Show services by tag
localport status --tag database

# Watch status in real-time
localport status --watch

# Watch with custom refresh interval
localport status --watch --refresh 5

# Include health check details
localport status --health

# Output in JSON format
localport --output json status
```

#### Output Formats

**Table Format (default):**
```
Service   Status    Local Port  Remote Port  Technology  Health    Uptime
postgres  Running   5432        5432         kubectl     Healthy   2m 30s
redis     Stopped   6379        6379         ssh         -         -
```

**JSON Format:**
```json
{
  "services": [
    {
      "name": "postgres",
      "status": "running",
      "local_port": 5432,
      "remote_port": 5432,
      "technology": "kubectl",
      "health_status": "healthy",
      "uptime_seconds": 150,
      "process_id": 12345
    }
  ]
}
```

### `localport logs`

View logs for port forwarding services.

```bash
localport logs [OPTIONS] SERVICE
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--follow` | `-f` | Follow log output |
| `--tail LINES` | `-n` | Number of lines to show (default: 50) |
| `--since DURATION` | | Show logs since duration (e.g., 1h, 30m) |
| `--level LEVEL` | | Filter by log level |

#### Examples

```bash
# Show recent logs
localport logs postgres

# Follow logs in real-time
localport logs --follow postgres

# Show last 100 lines
localport logs --tail 100 postgres

# Show logs from last hour
localport logs --since 1h postgres

# Show only error logs
localport logs --level ERROR postgres
```

## Daemon Management Commands

### `localport daemon start`

Start LocalPort daemon for background operation.

```bash
localport daemon start [OPTIONS]
```

#### Options

| Option | Description |
|--------|-------------|
| `--auto-start` | Automatically start configured services |
| `--no-auto-start` | Don't start services automatically |
| `--pid-file PATH` | Path to PID file |
| `--log-file PATH` | Path to log file |

#### Examples

```bash
# Start daemon with auto-start
localport daemon start --auto-start

# Start daemon without auto-starting services
localport daemon start --no-auto-start

# Start with custom PID file
localport daemon start --pid-file /var/run/localport.pid
```

### `localport daemon stop`

Stop the LocalPort daemon.

```bash
localport daemon stop [OPTIONS]
```

#### Options

| Option | Description |
|--------|-------------|
| `--timeout SECONDS` | Timeout for graceful shutdown (default: 30) |
| `--force` | Force stop daemon |

#### Examples

```bash
# Stop daemon gracefully
localport daemon stop

# Stop with custom timeout
localport daemon stop --timeout 60

# Force stop daemon
localport daemon stop --force
```

### `localport daemon restart`

Restart the LocalPort daemon.

```bash
localport daemon restart [OPTIONS]
```

#### Options

| Option | Description |
|--------|-------------|
| `--timeout SECONDS` | Timeout for graceful shutdown (default: 30) |
| `--auto-start` | Auto-start services after restart |

#### Examples

```bash
# Restart daemon
localport daemon restart

# Restart with auto-start
localport daemon restart --auto-start
```

### `localport daemon status`

Show daemon status information.

```bash
localport daemon status [OPTIONS]
```

#### Examples

```bash
# Show daemon status
localport daemon status

# Show in JSON format
localport --output json daemon status
```

#### Output Example

```
Daemon Status: Running
PID: 12345
Started: 2024-01-15 10:30:00
Uptime: 2h 15m 30s
Managed Services: 4
Active Forwards: 3
Health Checks: Enabled
Last Health Check: 2024-01-15 12:44:30
```

### `localport daemon reload`

Reload daemon configuration without restart.

```bash
localport daemon reload [OPTIONS]
```

#### Examples

```bash
# Reload configuration
localport daemon reload

# Reload with verbose output
localport --verbose daemon reload
```

## Configuration Management Commands

### `localport config validate`

Validate configuration file.

```bash
localport config validate [OPTIONS]
```

#### Options

| Option | Description |
|--------|-------------|
| `--strict` | Enable strict validation mode |

#### Examples

```bash
# Validate current configuration
localport config validate

# Validate specific file
localport --config /path/to/config.yaml config validate

# Strict validation
localport config validate --strict
```

#### Output Example

```
✓ Configuration is valid
  - 4 services configured
  - 2 health checks configured
  - No validation errors found
```

### `localport config export`

Export configuration to file or stdout.

```bash
localport config export [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--output PATH` | `-o` | Output file path (default: stdout) |
| `--format FORMAT` | `-f` | Output format (yaml, json) (default: yaml) |
| `--service NAMES` | `-s` | Export specific services |
| `--tag TAG` | `-t` | Export services with specific tag |
| `--include-disabled` | | Include disabled services |
| `--no-defaults` | | Exclude default values |

#### Examples

```bash
# Export all configuration
localport config export

# Export to file
localport config export --output backup.yaml

# Export in JSON format
localport config export --format json

# Export specific services
localport config export --service postgres redis

# Export by tag
localport config export --tag database

# Export without defaults
localport config export --no-defaults

# Include disabled services
localport config export --include-disabled
```

## Output Formats

LocalPort supports multiple output formats for most commands:

### Table Format (Default)

Human-readable tabular output with colors and formatting.

```bash
localport status
```

### JSON Format

Machine-readable JSON output for scripting and automation.

```bash
localport --output json status
```

### Text Format

Simple text output for basic parsing.

```bash
localport --output text status
```

## Environment Variables

LocalPort recognizes these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LOCALPORT_CONFIG` | Path to configuration file | Auto-detected |
| `LOCALPORT_LOG_LEVEL` | Default log level | `INFO` |
| `LOCALPORT_NO_COLOR` | Disable colored output | `false` |
| `NO_COLOR` | Standard no-color environment variable | `false` |

## Exit Codes

LocalPort uses standard exit codes:

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error |
| `2` | Configuration error |
| `3` | Service error |
| `4` | Network error |
| `5` | Permission error |
| `130` | Interrupted by user (Ctrl+C) |

## Shell Completion

LocalPort supports shell completion for bash, zsh, and fish:

### Bash

```bash
# Add to ~/.bashrc
eval "$(_LOCALPORT_COMPLETE=bash_source localport)"
```

### Zsh

```bash
# Add to ~/.zshrc
eval "$(_LOCALPORT_COMPLETE=zsh_source localport)"
```

### Fish

```bash
# Add to ~/.config/fish/config.fish
eval (env _LOCALPORT_COMPLETE=fish_source localport)
```

## Configuration File Discovery

LocalPort searches for configuration files in this order:

1. `--config` command line option
2. `LOCALPORT_CONFIG` environment variable
3. `./localport.yaml` (current directory)
4. `~/.config/localport/config.yaml`
5. `~/.localport.yaml`
6. `/etc/localport/config.yaml`

## Logging

LocalPort uses structured logging with these levels:

- **DEBUG**: Detailed debugging information
- **INFO**: General information about operations
- **WARN**: Warning messages for potential issues
- **ERROR**: Error messages for failures

### Log Locations

- **Console**: All commands log to stderr by default
- **Daemon Mode**: Logs to `~/.local/share/localport/logs/daemon.log`
- **Service Logs**: Individual service logs in `~/.local/share/localport/logs/services/`

### Verbose Mode

Enable verbose mode for detailed output:

```bash
localport --verbose start --all
```

## Examples and Common Patterns

### Development Workflow

```bash
# Start development services
localport start --tag development

# Check status
localport status --tag development

# Follow logs for debugging
localport logs --follow api

# Stop when done
localport stop --tag development
```

### Production Deployment

```bash
# Start daemon with auto-start
localport daemon start --auto-start

# Check daemon status
localport daemon status

# Reload configuration after changes
localport daemon reload

# Monitor service health
localport status --health --watch
```

### Configuration Management

```bash
# Validate before deployment
localport config validate --strict

# Export current configuration
localport config export --output backup-$(date +%Y%m%d).yaml

# Export production services only
localport config export --tag production --output prod-config.yaml
```

### Troubleshooting

```bash
# Check service status with health details
localport status --health

# View recent logs
localport logs --tail 100 postgres

# Follow logs in real-time
localport logs --follow --level ERROR postgres

# Validate configuration
localport config validate

# Use verbose mode for debugging
localport --verbose start postgres
```

For more examples and use cases, see the [User Guide](user-guide.md) and [Examples](examples/) directory.
