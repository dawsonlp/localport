# LocalPort

> **Universal port forwarding manager with intelligent health monitoring**

LocalPort is a Python CLI that manages port forwarding across kubectl and SSH with
automatic health monitoring, intelligent restart policies, and a background daemon.
Feedback and issue reports are welcome.

## Why LocalPort?

- **Universal** — kubectl and SSH tunnels managed with one tool
- **Self-healing** — health monitoring with restart policies and exponential backoff
- **Hot reload** — config changes applied live in daemon mode (via [watchdog](https://github.com/gorakhargosh/watchdog))
- **Daemon mode** — background operation with monitoring
- **Rich CLI** — clean output with progressive verbosity (`-v`, `-vv`, `--debug`)
- **Flexible config** — YAML with environment variable substitution and validation

## Installation

**Python 3.11+ required.** LocalPort runs on Linux and macOS only (the daemon relies on
POSIX `fork` and Unix signals — Windows is not supported).

```bash
# pipx (recommended)
pipx install localport

# with optional health-check extras
pipx install "localport[kafka,postgres]"

# or with uv
uv tool install localport
```

Install from GitHub or Test PyPI:

```bash
pipx install git+https://github.com/dawsonlp/localport.git
pipx install git+https://github.com/dawsonlp/localport.git@v1.1.1   # specific tag
```

Need Python 3.11+? Install it via Homebrew (`brew install python@3.11`), your distro's
package manager, or [pyenv](https://github.com/pyenv/pyenv). Verify with
`localport --version`.

## Quick Start (5 minutes)

1. Create `localport.yaml`:

```yaml
version: "1.0"

services:
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_name: postgres
      namespace: default
    tags: [database]

  - name: redis
    technology: kubectl
    local_port: 6379
    remote_port: 6379
    connection:
      resource_name: redis
      namespace: default
    tags: [cache]
```

2. Start your services (`start` requires service names, `--tag`, or `--all`):

```bash
localport start --all              # everything
localport start postgres redis     # specific services
localport start --tag database     # by tag
```

3. Check status and connect:

```bash
localport status
psql -h localhost -p 5432 -U postgres
redis-cli -h localhost -p 6379
```

Your services are now forwarded locally with automatic health monitoring and restarts.
See the [full command list](docs/cli-reference.md) and [configuration options](docs/configuration.md).

## Documentation

- **[Getting Started](docs/getting-started.md)** — step-by-step setup for new users
- **[Configuration Guide](docs/configuration.md)** — complete YAML reference
- **[CLI Reference](docs/cli-reference.md)** — all commands and options
- **[SSH Setup](docs/ssh-setup.md)** — keys, bastion hosts, and tunneling
- **[Troubleshooting](docs/troubleshooting.md)** — when things go wrong
- **[Architecture](docs/architecture.md)** — technical overview
- **[Contributing](CONTRIBUTING.md)** — development setup and guidelines

## Status

**Stable (v1.x)** — core functionality is production-ready.

Implemented:

- kubectl port forwarding (services, deployments, pods)
- SSH port forwarding, including bastion/jump hosts
- Health monitoring (TCP, HTTP/HTTPS, Kafka, PostgreSQL) with restart policies
- Daemon mode with hot configuration reload
- Cluster health monitoring for Kubernetes contexts
- Configuration management (`config add`/`remove`/`list`/`validate`/`export`)
- Service logging and diagnostics

PostgreSQL and Kafka health checks need the optional extras
(`localport[postgres]`, `localport[kafka]`) and credentials — see the
[Configuration Guide](docs/configuration.md).

## Roadmap

Direction, not commitments — priorities follow community demand and contributions:

- **Reverse proxy** — HTTP/HTTPS proxying with load balancing
- **Advanced routing** — multi-hop and service-mesh connectivity
- **Enhanced logging** — ring-buffer storage with real-time streaming
- **AI integration** — natural-language service management via MCP
- **Enterprise security** — mTLS, RBAC, and identity-provider integration
- **Developer tools** — IDE plugins and environment templates

See the [full roadmap](docs/roadmap.md) and vote on [GitHub issues](https://github.com/dawsonlp/localport/issues).

## Links

- [Changelog](CHANGELOG.md) — release notes and version history
- [GitHub Issues](https://github.com/dawsonlp/localport/issues) — bugs and feature requests
- [License](LICENSE) — MIT
</content>
</invoke>
