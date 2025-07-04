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

If you haven't installed LocalPort yet, see the [main README](../README.md#installation) for detailed installation instructions using pipx, UV, or development setup.

Quick verification:
```bash
localport --version
```

## Your First Configuration

LocalPort uses YAML configuration files to define your port forwarding services. Let's create your first configuration.

### Step 1: Create a Configuration File

Create a file named `localport.yaml` in your current directory:

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

### Step 2: Customize for Your Environment

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
