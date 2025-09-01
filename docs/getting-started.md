# Getting Started with LocalPort

> **🚧 ALPHA SOFTWARE**: LocalPort is currently in alpha testing. While core functionality works well, expect some rough edges and breaking changes. Please report issues and provide feedback!

This guide will walk you through setting up LocalPort from scratch and getting your first port forwards running in under 10 minutes.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** installed on your system
  - **⚠️ Important**: LocalPort requires Python 3.11 or newer
  - If you don't have Python 3.11+, see [Python Installation](#python-installation) below
- **pipx** or **UV** for package management (recommended)
- Access to either:
  - A Kubernetes cluster with `kubectl` configured
  - SSH access to remote servers
- Basic familiarity with YAML configuration files

### Python Installation

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

## Installation

LocalPort supports multiple installation methods. Choose the one that works best for your environment:

### Method 1: pipx (Recommended)

**Best for**: Most users, isolated installation, easy management

```bash
# Install pipx if you don't have it
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Install LocalPort
pipx install localport

# Verify installation
localport --version
```

### Method 2: uv (Fastest)

**Best for**: Modern Python workflows, fastest installation

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install LocalPort globally
uv tool install localport

# Verify installation
localport --version
```

### Method 3: pip (Traditional)

**Best for**: Virtual environments, CI/CD, traditional Python workflows

```bash
# In a virtual environment (recommended)
python3 -m venv localport-env
source localport-env/bin/activate  # On Windows: localport-env\Scripts\activate
pip install localport

# Or globally (not recommended)
pip install --user localport

# Verify installation
localport --version
```

### Installation Verification

All methods should result in the same functionality:

```bash
# Check version
localport --version

# Test basic commands
localport --help
localport config --help
```

### Troubleshooting Installation

**Command not found after installation:**
```bash
# For pipx users
pipx ensurepath
source ~/.bashrc  # or restart terminal

# For pip --user installs
export PATH="$HOME/.local/bin:$PATH"
```

**Python version issues:**
```bash
# Check your Python version
python3 --version  # Should be 3.11+

# If you have multiple Python versions
python3.11 -m pipx install localport
# or
python3.12 -m pip install localport
```

For more installation options and development setup, see the [main README](../README.md#installation).

## Your First Configuration

LocalPort offers two ways to set up your port forwarding services:

1. **Interactive Setup** (Recommended for beginners) - Use built-in commands to discover and configure services automatically
2. **Manual Configuration** - Create YAML configuration files directly

### Method 1: Interactive Setup (Recommended)

The easiest way to get started is using LocalPort's interactive configuration commands that automatically discover available services.

#### Adding Your First Kubernetes Service

```bash
# Interactive setup - LocalPort will guide you through the process
localport config add

# Or specify what you want upfront
localport config add --technology kubectl --resource postgres --namespace default
```

LocalPort will:
- Automatically discover Kubernetes resources and their available ports
- Resolve namespace ambiguity if the resource exists in multiple namespaces
- Suggest appropriate local ports
- Handle all the configuration details for you

#### Adding Your First SSH Connection

```bash
# Interactive setup for SSH
localport config add --technology ssh

# Or specify connection details
localport config add --technology ssh --host server.com --user myuser
```

#### Managing Your Connections

```bash
# List all configured connections
localport config list

# Remove a connection
localport config remove postgres

# View detailed connection information
localport config list --output json
```

### Method 2: Manual Configuration

If you prefer to create configuration files manually, create a file named `localport.yaml` in your current directory:

```yaml
version: "1.0"

services:
  # Example: Forward a PostgreSQL database from Kubernetes
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_name: postgres
      namespace: default
    tags: [database]
    description: "PostgreSQL database for development"

  # Example: Forward Redis via SSH tunnel
  - name: redis
    technology: ssh
    local_port: 6379
    remote_port: 6379
    connection:
      host: redis.example.com
      user: your-username
      key_file: ~/.ssh/id_rsa
    tags: [cache]
    description: "Redis cache server"
```

#### Customizing Manual Configuration

#### For Kubernetes Services

If you're using Kubernetes, update the `postgres` service configuration:

```yaml
- name: postgres
  technology: kubectl
  local_port: 5432
  remote_port: 5432
  connection:
    resource_type: service        # or 'deployment', 'pod'
    resource_name: postgres       # your actual service name
    namespace: default            # your namespace
    context: minikube            # your kubectl context (optional)
  tags: [database]
```

#### For SSH Tunnels

If you're using SSH, update the `redis` service configuration:

```yaml
- name: redis
  technology: ssh
  local_port: 6379
  remote_port: 6379
  connection:
    host: your-server.com         # your actual server
    user: your-username           # your SSH username
    key_file: ~/.ssh/id_rsa      # path to your SSH key
    port: 22                     # SSH port (optional, default 22)
  tags: [cache]
```

### Step 3: Validate Your Configuration

Before starting services, validate your configuration:

```bash
localport config validate
```

If there are any issues, LocalPort will show detailed error messages with suggestions for fixes.

## Starting Your First Services

### Start All Services

```bash
localport start --all
```

### Start Specific Services

```bash
localport start postgres redis
```

### Start Services by Tag

```bash
localport start --tag database
```

## Checking Service Status

Monitor your running services:

```bash
# Check current status
localport status

# Watch status in real-time
localport status --watch

# Get status in JSON format for scripting
localport status --output json
```

## Using Your Forwarded Services

Once your services are running, you can connect to them locally:

### PostgreSQL Example

```bash
# Connect using psql
psql -h localhost -p 5432 -U postgres

# Or using a connection string
psql postgresql://postgres@localhost:5432/mydb
```

### Redis Example

```bash
# Connect using redis-cli
redis-cli -h localhost -p 6379

# Test the connection
redis-cli -h localhost -p 6379 ping
```

## Troubleshooting with Service Logs

LocalPort automatically captures detailed logs from your port forwarding processes, making troubleshooting much easier:

### Viewing Service Logs

```bash
# List all available service logs
localport logs --list

# View logs for a specific service
localport logs --service postgres

# Search for errors in logs
localport logs --service postgres --grep "error"
localport logs --service postgres --grep "connection"

# Get the log file path for external tools
localport logs --service postgres --path
```

### Log Locations

LocalPort stores service logs in organized directories:

```bash
# Show log directory locations
localport logs --location

# Service logs are stored at:
# ~/.local/share/localport/logs/services/
```

### Using External Tools

```bash
# Follow logs in real-time with tail
tail -f $(localport logs --service postgres --path)

# View logs with less for easy navigation
less $(localport logs --service postgres --path)

# Search logs with grep
grep "error" $(localport logs --service postgres --path)
```

### What's in the Logs

Service logs contain:
- **Raw kubectl/ssh output** - Everything the underlying process produces
- **Connection events** - When connections start, stop, or fail
- **Error messages** - Detailed error information for troubleshooting
- **Metadata headers** - Service configuration and diagnostic information

### Common Troubleshooting Patterns

```bash
# Check if a service is having connection issues
localport logs --service postgres --grep "connection\|error\|failed"

# Look for recent activity
localport logs --service postgres | tail -50

# Check service status and logs together
localport status
localport logs --service postgres
```

## Stopping Services

### Stop Specific Services

```bash
localport stop postgres redis
```

### Stop All Services

```bash
localport stop --all
```

## Adding Health Monitoring

LocalPort can automatically monitor your services and restart them if they fail. Add health checks to your configuration:

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
      initial_delay: 1
      max_delay: 300
```

## Using Environment Variables

Keep sensitive information secure using environment variables:

```yaml
services:
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_name: postgres
      namespace: ${KUBE_NAMESPACE:default}
      context: ${KUBE_CONTEXT}
    health_check:
      type: postgres
      config:
        database: ${DB_NAME:postgres}
        user: ${DB_USER:postgres}
        password: ${DB_PASSWORD}
```

Set the environment variables:

```bash
export KUBE_NAMESPACE=production
export KUBE_CONTEXT=my-cluster
export DB_PASSWORD=secret-password
```

## Running in Daemon Mode

For production or long-running scenarios, use daemon mode:

```bash
# Start daemon with auto-start of services
localport daemon start --auto-start

# Check daemon status
localport daemon status

# Reload configuration without restart
localport daemon reload

# Stop daemon
localport daemon stop
```

## Configuration File Locations

LocalPort looks for configuration files in these locations (in order):

1. `./localport.yaml` (current directory)
2. `~/.config/localport/config.yaml`
3. `~/.localport.yaml`
4. `/etc/localport/config.yaml`

You can also specify a custom location:

```bash
localport --config /path/to/my/config.yaml start --all
```

## Common Issues and Solutions

### Port Already in Use

If you get a "port already in use" error:

```bash
# Check what's using the port
lsof -i :5432

# Kill the process if safe to do so
kill -9 <PID>

# Or choose a different local port in your config
```

### Kubernetes Connection Issues

If kubectl commands fail:

```bash
# Check your kubectl configuration
kubectl config current-context
kubectl config get-contexts

# Test connectivity
kubectl get pods -n default
```

### SSH Connection Issues

If SSH tunnels fail:

```bash
# Test SSH connectivity
ssh -i ~/.ssh/id_rsa user@host

# Check SSH key permissions
chmod 600 ~/.ssh/id_rsa
```

## Next Steps

Now that you have LocalPort running:

1. **Read the [Configuration Guide](configuration.md)** for advanced configuration options
2. **Check the [CLI Reference](cli-reference.md)** for all available commands
3. **Explore [Examples](examples/)** for real-world configuration patterns
4. **Set up [Health Monitoring](user-guide.md#health-monitoring)** for production use
5. **Configure [Daemon Mode](user-guide.md#daemon-mode)** for background operation

## Getting Help

If you run into issues:

1. **Check the [Troubleshooting Guide](troubleshooting.md)**
2. **Use verbose mode**: `localport --verbose start --all`
3. **Validate your config**: `localport config validate`
4. **Check logs**: `localport logs <service-name>`
5. **Open an issue** on GitHub with your configuration and error messages

Welcome to LocalPort! You're now ready to manage your port forwards like a pro. 🚀
