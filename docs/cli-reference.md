# CLI Reference

Complete reference for all LocalPort commands, options, and usage patterns. Every option
below matches the actual command signatures in the current release.

```bash
localport [GLOBAL_OPTIONS] COMMAND [ARGS] [COMMAND_OPTIONS]
```

## Global Options

Available on every command (specify them before the subcommand):

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--config PATH` | `-c` | Path to configuration file | Auto-detected |
| `--verbose` | `-v` | Increase verbosity: `-v` = info, `-vv` = debug (repeatable) | off |
| `--debug` | | Enable debug logging (equivalent to `-vv`) | `false` |
| `--quiet` | `-q` | Suppress non-essential output (errors only) | `false` |
| `--log-level LEVEL` | | Set log level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `--no-color` | | Disable colored output | `false` |
| `--output FORMAT` | `-o` | Output format (`table`, `json`, `text`) | `table` |
| `--version` | `-V` | Show version information and exit | |
| `--help` | `-h` | Show help message and exit | |

```bash
# Use a custom configuration file
localport --config /path/to/config.yaml start --all

# Increase verbosity
localport -v start postgres        # info
localport -vv start postgres       # debug

# JSON output for scripting
localport --output json status

# Quiet mode (errors only)
localport --quiet start --all
```

## Service Management Commands

### `localport start`

Start port forwarding services.

```bash
localport start [OPTIONS] [SERVICES]...
```

| Option | Short | Description |
|--------|-------|-------------|
| `--all` | `-a` | Start all configured services |
| `--tag TAG` | `-t` | Start services with the given tag (repeatable) |
| `--force` | `-f` | Force restart if already running |

```bash
localport start --all                 # start everything
localport start postgres redis kafka  # start specific services
localport start --tag database        # start by tag
localport start --force postgres      # restart even if already running
```

### `localport stop`

Stop running port forwarding services.

```bash
localport stop [OPTIONS] [SERVICES]...
```

| Option | Short | Description |
|--------|-------|-------------|
| `--all` | `-a` | Stop all running services |
| `--force` | `-f` | Force stop (kill processes) |

```bash
localport stop --all
localport stop postgres redis
localport stop --all --force
```

### `localport status`

Show the status of port forwarding services.

```bash
localport status [OPTIONS] [SERVICES]...
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--watch` | `-w` | Watch mode — refresh periodically | `false` |
| `--interval SECONDS` | `-i` | Refresh interval for watch mode | `5` |

```bash
localport status                      # all services
localport status postgres redis       # specific services
localport status --watch              # live view
localport status --watch --interval 2 # live view, refresh every 2s
localport --output json status        # machine-readable
```

**Table format (default):**

```
Service   Status    Local Port  Remote Port  Technology  Health    Uptime
postgres  Running   5432        5432         kubectl     Healthy   2m 30s
redis     Stopped   6379        6379         ssh         -         -
```

**JSON format:**

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

View service logs for troubleshooting and diagnostics.

```bash
localport logs [OPTIONS] [SERVICES]...
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--service SERVICE` | `-s` | Show logs for a specific service | |
| `--list` | | List all available service logs | `false` |
| `--location` | | Show log directory locations | `false` |
| `--path` | | Show the log file path (use with `--service`) | `false` |
| `--follow` | `-f` | Keep the log view open (real-time streaming is not yet implemented; prints current entries then waits) | `false` |
| `--lines N` | `-n` | Number of lines to show (`0` for all) | `100` |
| `--level LEVEL` | `-l` | Filter by log level (DEBUG, INFO, WARNING, ERROR) | |
| `--since TIME` | | Show logs since a time (ISO or relative, e.g. `1h`, `30m`) | |
| `--until TIME` | | Show logs until a time (ISO or relative) | |
| `--grep PATTERN` | `-g` | Filter log lines by pattern (case-insensitive) | |

```bash
localport logs --list                             # discover available logs
localport logs --location                         # show log directories
localport logs --service postgres                 # view a service's logs
localport logs --service postgres --path          # print the log file path
localport logs --service postgres --grep error    # filter by pattern

# Follow output live with external tools (recommended over --follow)
tail -f "$(localport logs --service postgres --path)"
```

**Log locations:**

- Service logs: `~/.local/share/localport/logs/services/`
- Daemon log: `~/.local/share/localport/logs/daemon.log`
- File naming: `<service-name>_<unique-id>.log`

Service logs capture the raw kubectl/ssh subprocess output plus metadata headers with
connection events, errors, and reconnections.

## Daemon Management Commands

### `localport daemon start`

Start the LocalPort daemon for background operation.

```bash
localport daemon start [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--config PATH` | `-c` | Configuration file path | Auto-detected |
| `--auto-start` / `--no-auto-start` | | Auto-start configured services | `--auto-start` |
| `--foreground` | `-f` | Run in the foreground (don't detach) | `false` |

```bash
localport daemon start --auto-start
localport daemon start --no-auto-start
localport daemon start --foreground     # useful for debugging / containers
```

### `localport daemon stop`

Stop the LocalPort daemon.

```bash
localport daemon stop [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--force` | `-f` | Force stop the daemon |

### `localport daemon restart`

Restart the LocalPort daemon.

```bash
localport daemon restart [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--config PATH` | `-c` | Configuration file path |
| `--force` | `-f` | Force restart |

### `localport daemon status`

Show daemon status information.

```bash
localport daemon status [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--watch` | `-w` | Watch mode — refresh periodically | `false` |
| `--interval SECONDS` | `-i` | Refresh interval for watch mode | `5` |

### `localport daemon reload`

Reload the daemon configuration without restarting (hot reload).

```bash
localport daemon reload
```

## Configuration Management Commands

### `localport config validate`

Validate a configuration file.

```bash
localport config validate [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--config PATH` | `-c` | Configuration file to validate |

### `localport config export`

Export configuration to a file or stdout.

```bash
localport config export [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output PATH` | `-o` | Output file path | stdout |
| `--format FORMAT` | `-f` | Export format (`yaml`, `json`) | `yaml` |
| `--include-defaults` / `--no-defaults` | | Include default settings | `--include-defaults` |
| `--include-disabled` | | Include disabled services | `false` |
| `--service NAME` | `-s` | Export specific services only (repeatable) | |
| `--tag TAG` | `-t` | Export services with the given tag (repeatable) | |

```bash
localport config export
localport config export --output backup.yaml
localport config export --format json
localport config export --tag database --output db.yaml
```

### `localport config add`

Add a connection to the configuration interactively or via flags.

```bash
localport config add [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--name NAME` | `-n` | Service name | |
| `--technology TECH` | `-t` | Technology (`kubectl` or `ssh`) | |
| `--local-port PORT` | `-l` | Local port | |
| `--remote-port PORT` | | Remote port | |
| `--resource NAME` | `-r` | Kubernetes resource name (kubectl) | |
| `--namespace NAME` | | Kubernetes namespace (kubectl) | |
| `--host HOST` | | SSH hostname (ssh) | |
| `--user USER` | `-u` | SSH username (ssh) | |
| `--key PATH` | `-k` | SSH key file (ssh) | |
| `--ssh-port PORT` | | SSH port (ssh) | `22` |

Run `localport config add` with no flags to be prompted for the missing values.

### `localport config remove`

Remove a connection from the configuration.

```bash
localport config remove SERVICE_NAME [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--force` | `-f` | Skip the confirmation prompt |

### `localport config list`

List the connections defined in the configuration.

```bash
localport config list
```

## Cluster Health Commands

Cluster commands require cluster health monitoring to be enabled in the configuration and
only report on clusters that have active kubectl services.

### `localport cluster status`

Show cluster health for the Kubernetes contexts used by services.

```bash
localport cluster status [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--context NAME` | `-c` | Show status for a specific cluster context |

### `localport cluster events`

Show recent cluster events that might affect services.

```bash
localport cluster events [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--context NAME` | `-c` | Cluster context | |
| `--since TIME` | `-s` | Show events since this time (e.g. `1h`, `30m`, `60s`) | `1h` |
| `--limit N` | `-l` | Maximum number of events to show | `20` |

### `localport cluster pods`

Show pod status for resources used by active services.

```bash
localport cluster pods [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--context NAME` | `-c` | Cluster context |
| `--namespace NAME` | `-n` | Specific namespace to check |

## SSH Commands

### `localport ssh test`

Test SSH connectivity for a configured service or an ad-hoc host.

```bash
localport ssh test [SERVICE_NAME] [OPTIONS]
```

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--host HOST` | `-h` | SSH host to test | |
| `--user USER` | `-u` | SSH username | |
| `--port PORT` | `-p` | SSH port | `22` |
| `--key-file PATH` | `-k` | SSH private key file | |
| `--config PATH` | `-c` | Configuration file path | |

```bash
localport ssh test my-tunnel                       # test a configured service
localport ssh test --host example.com --user deploy  # ad-hoc test
```

### `localport ssh validate`

Validate SSH configuration.

```bash
localport ssh validate [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--config PATH` | `-c` | Configuration file path |
| `--service NAME` | `-s` | Validate a specific service only |

## Output Formats

Most commands honor the global `--output` option:

- `table` (default) — human-readable, colored tabular output
- `json` — machine-readable output for scripting and automation
- `text` — simple text output for basic parsing

```bash
localport --output json status
localport --output text status
```

## Environment Variables

Any setting can be provided via an environment variable using the `LOCALPORT_` prefix
(a local `.env` file is also read). Common variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LOCALPORT_CONFIG_FILE` | Path to configuration file | Auto-detected |
| `LOCALPORT_LOG_LEVEL` | Default log level | `INFO` |
| `LOCALPORT_NO_COLOR` | Disable colored output | `false` |
| `LOCALPORT_RUNTIME_DIR` | Runtime directory for PID files and logs | Platform default |
| `LOCALPORT_SERVICE_LOGGING_ENABLED` | Capture kubectl/ssh subprocess logs | `true` |
| `LOCALPORT_SERVICE_LOG_RETENTION_DAYS` | Days to retain service logs | `3` |
| `NO_COLOR` | Standard no-color variable (honored by the terminal renderer) | unset |

## Configuration File Discovery

When `--config` is not given, LocalPort resolves the configuration file in this order:

1. `--config` / `-c` command-line option
2. `LOCALPORT_CONFIG_FILE` environment variable
3. `./localport.yaml`
4. `./localport.yml`
5. `./.localport.yaml`
6. `~/.localport.yaml`
7. `~/.config/localport/config.yaml`
8. `/etc/localport/config.yaml`

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (configuration, service, or runtime failure) |
| `130` | Interrupted by user (Ctrl+C) |

## Logging

LocalPort uses structured logging with the standard levels DEBUG, INFO, WARNING, and
ERROR. Console output goes to stderr; in daemon mode logs are written to
`~/.local/share/localport/logs/daemon.log`, and per-service subprocess output is captured
under `~/.local/share/localport/logs/services/`. Increase verbosity with `-v`/`-vv` or
`--debug`.

## Common Patterns

**Development workflow:**

```bash
localport start --tag development
localport status                         # (status/logs take service names; use tags at start/stop)
localport logs --service api --grep error
localport stop --all
```

**Daemon / background operation:**

```bash
localport daemon start --auto-start
localport daemon status
localport daemon reload                  # apply config changes without restart
localport status --watch
```

**Configuration management:**

```bash
localport config validate
localport config export --output "backup-$(date +%Y%m%d).yaml"
localport config export --tag production --output prod-config.yaml
```

For end-to-end setup, see the [Getting Started Guide](getting-started.md) and the
[Configuration Guide](configuration.md).
