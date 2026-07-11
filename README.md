# LocalPort

> **Universal port forwarding manager with intelligent health monitoring**

LocalPort is a modern Python CLI tool that simplifies port forwarding across different technologies (kubectl, SSH) while providing features like automatic health monitoring, intelligent restart policies, and daemon-mode operation. Feedback and issue reports are welcome.

## ✨ Why LocalPort?

- **🔄 Universal**: Works with kubectl, SSH, and more - one tool for all your port forwarding needs
- **🏥 Self-Healing**: Automatic health monitoring with intelligent restart policies and exponential backoff
- **⚡ Hot Reload**: Configuration changes applied instantly in daemon mode (powered by [watchdog](https://github.com/gorakhargosh/watchdog))
- **🎯 Production Ready**: Daemon mode for background operation with comprehensive monitoring
- **🎨 Beautiful CLI**: Rich terminal interface with clean output and progressive verbosity
- **🔧 Flexible**: YAML configuration with environment variable support and validation

## 🚀 Quick Start

### Installation

#### Production Release (PyPI)
> **Note**: LocalPort is available on production PyPI.

> **⚠️ Python 3.11+ Required**: LocalPort requires Python 3.11 or newer. If you don't have Python 3.11+, see [Python Installation](#python-installation) below.

```bash
# Install with pipx (recommended)
pipx install localport

# Install with optional dependencies for advanced health checks
pipx install "localport[kafka,postgres]"

# Alternative: Install with UV
uv tool install localport
```

#### Python Installation

If you don't have Python 3.11+, install it first:

**macOS (using Homebrew):**
```bash
brew install python@3.11
# or for latest version
brew install python@3.12
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-pip
# or for newer version
sudo apt install python3.12 python3.12-venv python3.12-pip
```

**Windows:**
- Download from [python.org](https://www.python.org/downloads/) (3.11+ versions)
- Or use [pyenv-win](https://github.com/pyenv-win/pyenv-win)

**Using pyenv (cross-platform):**
```bash
pyenv install 3.11.0  # or 3.12.0, 3.13.0
pyenv global 3.11.0
```

**Verify installation:**
```bash
python3.11 --version  # Should show Python 3.11.x or newer
```

#### Test PyPI (Development Versions)
```bash
# Install development versions from Test PyPI
pipx install --index-url https://test.pypi.org/simple/ --pip-args="--extra-index-url https://pypi.org/simple/" localport
```

#### Development Installation (GitHub)
```bash
# Install latest from GitHub
pipx install git+https://github.com/dawsonlp/localport.git

# Install specific version/tag
pipx install git+https://github.com/dawsonlp/localport.git@v1.1.1

# Development: Install from source
git clone https://github.com/dawsonlp/localport.git
cd localport && ./scripts/setup-dev.sh
```

### 5-Minute Setup

1. **Create a configuration file** (`localport.yaml`):

```yaml
version: "1.0"

services:
  # Forward PostgreSQL from Kubernetes
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_name: postgres
      namespace: default
    tags: [database]

  # Forward Redis from Kubernetes
  - name: redis
    technology: kubectl
    local_port: 6379
    remote_port: 6379
    connection:
      resource_name: redis
      namespace: default
    tags: [cache]
```

2. **Start your services**:

```bash
# Start all services
localport start --all

# Start specific services
localport start postgres redis

# Start services by tag
localport start --tag database
```

3. **Check status**:

```bash
localport status
```

4. **Use your forwarded services**:

```bash
# Connect to PostgreSQL
psql -h localhost -p 5432 -U postgres

# Connect to Redis
redis-cli -h localhost -p 6379
```

That's it! Your services are now accessible locally with automatic health monitoring and restart capabilities.

## 📖 Documentation

### Getting Started
- **[Getting Started Guide](docs/getting-started.md)** - Step-by-step setup for new users
- **[Configuration Guide](docs/configuration.md)** - Complete configuration reference
- **[CLI Reference](docs/cli-reference.md)** - All commands and options

### User Guides
- **[CLI Reference](docs/cli-reference.md)** - All commands and options
- **[Development Guide](docs/development.md)** - Development setup and contribution guidelines
- **[Architecture Guide](docs/architecture.md)** - Technical architecture overview

## 🎯 Core Features

### Service Management
```bash
# Start services
localport start postgres redis              # Specific services
localport start --tag database             # By tag
localport start --all                      # All services

# Monitor services
localport status                           # Current status
localport status --watch                   # Live monitoring

# Stop services
localport stop postgres redis              # Specific services
localport stop --all                      # All services
```

### Service Logging & Diagnostics
```bash
# View all available service logs
localport logs --list

# View specific service logs
localport logs --service postgres

# Get log file path for external tools
localport logs --service postgres --path

# Filter logs with grep
localport logs --service postgres --grep "error"

# Show log directory locations
localport logs --location

# Use with external tools
tail -f $(localport logs --service postgres --path)
```

### Daemon Mode (Background Operation)
```bash
# Start daemon for background operation
localport daemon start --auto-start

# Check daemon status
localport daemon status

# Reload configuration without restart
localport daemon reload

# Stop daemon
localport daemon stop
```

### Configuration Management
```bash
# Validate configuration
localport config validate

# Export configuration
localport config export --format json

# Export specific services
localport config export --tag database --output backup.yaml
```

## 🔧 Configuration

### Basic Configuration

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
```

### Advanced Configuration with Health Monitoring

```yaml
version: "1.0"

# Global defaults
defaults:
  health_check:
    type: tcp
    interval: 30
    timeout: 5.0
    failure_threshold: 3
  restart_policy:
    enabled: true
    max_attempts: 5
    backoff_multiplier: 2.0

services:
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_type: service
      resource_name: postgres
      namespace: default
      context: ${KUBE_CONTEXT:minikube}
    enabled: true
    tags: [database, essential]
    description: "PostgreSQL database"
    health_check:
      type: postgres
      config:
        database: postgres
        user: postgres
        password: ${POSTGRES_PASSWORD}
    restart_policy:
      max_attempts: 3
      initial_delay: 2
```

**Supported Health Check Types:**
- **TCP**: Basic connectivity testing
- **HTTP/HTTPS**: Web service health endpoints
- **Kafka**: Message broker connectivity (requires `kafka-python`)
- **PostgreSQL**: Database connectivity (requires `psycopg`)

## 🛠️ Supported Technologies

### Kubernetes (kubectl)
```yaml
- name: service-name
  technology: kubectl
  connection:
    resource_type: service        # service, deployment, pod
    resource_name: my-service
    namespace: default
    context: minikube            # optional
```

### SSH Tunnels

SSH port forwarding is fully supported, including bastion/jump hosts via `remote_host`.

```yaml
- name: service-name
  technology: ssh
  local_port: 5432
  remote_port: 5432
  connection:
    host: remote-server.com
    user: deploy                 # optional (falls back to SSH config / agent)
    port: 22                     # optional, default 22
    key_file: ~/.ssh/id_rsa      # optional
    remote_host: db.internal     # optional, for bastion/jump-host tunneling
    password: secret             # optional (not recommended; use keys)
```

See the [SSH Setup Guide](docs/ssh-setup.md) for bastion hosts, key management, and the
`localport ssh test` / `localport ssh validate` helper commands.

## 🌟 Advanced Features

### Hot Configuration Reloading (Daemon Mode)

When running in daemon mode, LocalPort automatically detects configuration changes and applies them without restarting services:

```bash
# Start daemon mode first
localport daemon start --auto-start

# Edit your localport.yaml file
vim localport.yaml

# Changes are automatically applied in daemon mode!
# Check what changed:
localport daemon status
localport status
```

> **Note**: Hot reloading only works in daemon mode. For standalone commands, you'll need to restart services manually after configuration changes.

### Multiple Output Formats

```bash
# Table format (default)
localport status

# JSON for scripting
localport status --output json

# Text for simple parsing
localport status --output text
```

### Environment Variables

Use environment variable substitution for sensitive data:

```yaml
connection:
  host: ${DB_HOST:localhost}
  user: ${DB_USER}
  password: ${DB_PASSWORD}
  key_file: ${SSH_KEY_FILE:~/.ssh/id_rsa}
```

## 🚀 Development

### Requirements

- Python 3.11+
- UV (for dependency management)
- Virtual environment support

### Setup

```bash
# Clone the repository
git clone https://github.com/dawsonlp/localport.git
cd localport

# Setup development environment
./scripts/setup-dev.sh

# Activate virtual environment
source .venv/bin/activate

# Install in development mode
uv pip install -e .

# Run tests
uv run pytest
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 📊 Status

**Stable (v1.x)** — core functionality is production-ready.

> **Platform:** Linux and macOS. The daemon relies on POSIX features (forking and Unix signals), so Windows is not supported.

**Implemented:**
- ✅ kubectl port forwarding (services, deployments, pods)
- ✅ SSH port forwarding, including bastion/jump hosts
- ✅ Health monitoring (TCP, HTTP/HTTPS, Kafka, PostgreSQL) with intelligent restart policies
- ✅ Daemon mode with hot configuration reload
- ✅ Cluster health monitoring for Kubernetes contexts
- ✅ Configuration management (`config add`/`remove`/`list`/`validate`/`export`)
- ✅ Service logging and diagnostics
- ✅ Progressive verbosity (`-v`, `-vv`, `--debug`) with clean default output

**Notes:**
- **PostgreSQL / Kafka health checks** require the optional extras (`localport[postgres]`, `localport[kafka]`) and appropriate credentials — see the [Configuration Guide](docs/configuration.md).

## 🗺️ Roadmap

LocalPort is actively evolving with exciting features planned for future releases. Our development is driven by community needs and contributions.

### Upcoming Features

- **🌐 Reverse Proxy Support**: HTTP/HTTPS reverse proxies with load balancing
- **🔗 Advanced Routing**: Multi-hop routing and service mesh capabilities  
- **📊 Enhanced Logging**: Ring buffer storage with real-time streaming
- **🤖 AI Integration**: Natural language service management via MCP
- **🔒 Enterprise Security**: mTLS, RBAC, and identity provider integration
- **🛠️ Developer Tools**: IDE plugins and environment templates

### Community-Driven Development

**⚠️ Important**: Features are prioritized based on community demand, contributor availability, and technical feasibility. There are no commitments to specific timelines or delivery sequences.

**Get Involved**:
- 🗳️ **Vote on features** by reacting to GitHub issues
- 💬 **Join discussions** to share your use cases
- 🛠️ **Contribute** by implementing features you need
- 📝 **Request features** with detailed GitHub issues

**📖 [View Full Roadmap](docs/roadmap.md)** - Detailed feature descriptions, use cases, and contribution opportunities.

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes and version history.

## 🔗 Links

- [Changelog](CHANGELOG.md) - Detailed release notes and version history
- [Development Guide](docs/development.md) - Development setup and contribution guidelines
- [Architecture Guide](docs/architecture.md) - Technical architecture overview
