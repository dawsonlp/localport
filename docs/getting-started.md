# Getting Started with LocalPort

This guide walks you through installing LocalPort and getting your first port forwards
running in under 10 minutes.

## Prerequisites

- **Python 3.11+** (Linux or macOS — Windows is not supported). To install Python, see
  the [README](../README.md#installation).
- **pipx** or **uv** for package management (recommended)
- Access to a Kubernetes cluster with `kubectl` configured, and/or SSH access to a remote
  host
- Basic familiarity with YAML

## Installation

Choose the method that fits your environment. All produce the same `localport` command;
verify with `localport --version`.

### pipx (recommended)

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install localport
```

### uv (fastest)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install localport
```

### pip

```bash
python3 -m venv localport-env
source localport-env/bin/activate
pip install localport
```

**Command not found after install?** Run `pipx ensurepath` (pipx) or add
`~/.local/bin` to your `PATH` (pip `--user`), then restart your shell.

For more options, see the [README](../README.md#installation).

## Your First Configuration

You can set up services two ways: interactively, or by writing YAML directly.

### Interactive setup (recommended)

`localport config add` discovers available resources and guides you through the details:

```bash
# Prompted setup
localport config add

# kubectl service, specified upfront
localport config add --technology kubectl --resource postgres --namespace default

# SSH connection
localport config add --technology ssh --host server.com --user myuser
```

Manage your connections:

```bash
localport config list             # list configured connections
localport config remove postgres  # remove a connection
```

### Manual configuration

Create `localport.yaml` in the current directory:

```yaml
version: "1.0"

services:
  # PostgreSQL from Kubernetes
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_type: service       # or 'deployment', 'pod'
      resource_name: postgres
      namespace: default
      context: minikube            # optional
    tags: [database]
    description: "PostgreSQL database for development"

  # Redis via SSH tunnel
  - name: redis
    technology: ssh
    local_port: 6379
    remote_port: 6379
    connection:
      host: redis.example.com
      user: your-username
      key_file: ~/.ssh/id_rsa
      port: 22                     # optional, default 22
    tags: [cache]
    description: "Redis cache server"
```

See the [Configuration Guide](configuration.md) for all fields and the
[SSH Setup Guide](ssh-setup.md) for tunnel details.

### Validate your configuration

```bash
localport config validate
```

Validation reports detailed errors with suggested fixes.

## Starting Services

`start` requires service names, `--tag`, or `--all` (bare `localport start` does nothing):

```bash
localport start --all              # all services
localport start postgres redis     # specific services
localport start --tag database     # by tag
```

## Checking Status

```bash
localport status                   # current status
localport status --watch           # live view
localport --output json status     # machine-readable
```

## Using Your Forwarded Services

Once running, connect to the local ports:

```bash
psql -h localhost -p 5432 -U postgres
redis-cli -h localhost -p 6379 ping
```

## Viewing Service Logs

LocalPort captures raw kubectl/SSH output for each service:

```bash
localport logs --list                          # list available logs
localport logs --service postgres              # view a service's logs
localport logs --service postgres --grep error # filter by pattern
localport logs --service postgres --path       # print the log file path

tail -f "$(localport logs --service postgres --path)"   # follow with external tools
```

For diagnosing failures, see the [Troubleshooting Guide](troubleshooting.md).

## Stopping Services

```bash
localport stop postgres redis
localport stop --all
```

## Adding Health Monitoring

LocalPort can monitor services and restart them on failure. Add a `health_check` and
`restart_policy`:

```yaml
services:
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_name: postgres
      namespace: default
    health_check:
      type: postgres
      interval: 30
      timeout: 10.0
      failure_threshold: 3
      config:
        database: postgres
        user: postgres
        password: ${POSTGRES_PASSWORD}
    restart_policy:
      enabled: true
      max_attempts: 5
      backoff_multiplier: 2.0
```

See [Health Monitoring](configuration.md#health-checks) for all check types
and options.

## Using Environment Variables

Keep secrets out of your config with `${VAR}` or `${VAR:default}` substitution:

```yaml
connection:
  resource_name: postgres
  namespace: ${KUBE_NAMESPACE:default}
  context: ${KUBE_CONTEXT}
```

```bash
export KUBE_NAMESPACE=production
export KUBE_CONTEXT=my-cluster
```

## Running in Daemon Mode

For long-running scenarios, run LocalPort in the background:

```bash
localport daemon start --auto-start   # start daemon, auto-start services
localport daemon status
localport daemon reload               # apply config changes without restart
localport daemon stop
```

See [Daemon Management](cli-reference.md#daemon-management-commands) for all daemon
options.

## Configuration File Locations

LocalPort searches these paths in order (or pass `--config PATH`):

1. `./localport.yaml`
2. `~/.config/localport/config.yaml`
3. `~/.localport.yaml`
4. `/etc/localport/config.yaml`

## Common Issues

- **Port already in use** — find the holder with `lsof -i :5432` and stop it, or choose a
  different `local_port`.
- **kubectl fails** — check your context with `kubectl config current-context`.
- **SSH fails** — test with `ssh -i ~/.ssh/id_rsa user@host` and ensure key permissions
  are `600`.

For detailed diagnostics, see the [Troubleshooting Guide](troubleshooting.md).

## Next Steps

1. Read the [Configuration Guide](configuration.md) for advanced options
2. Browse the [CLI Reference](cli-reference.md) for all commands
3. Set up [SSH tunnels](ssh-setup.md) for remote services

## Getting Help

1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Use verbose mode: `localport -v start --all`
3. Validate your config: `localport config validate`
4. Check logs: `localport logs --service <name>`
5. Open an issue on [GitHub](https://github.com/dawsonlp/localport/issues) with your
   config and error messages
</content>
