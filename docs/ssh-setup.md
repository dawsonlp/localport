# SSH Setup Guide

This guide will help you set up SSH tunneling with LocalPort for secure access to remote services.

## Prerequisites

- OpenSSH client installed on your system
- SSH access to the target host
- Network connectivity to the target host

## Quick Start

### 1. Generate SSH Key Pair (Recommended)

```bash
# Generate a new SSH key pair
ssh-keygen -t rsa -b 4096 -f ~/.ssh/localport_key

# Copy the public key to the target host
ssh-copy-id -i ~/.ssh/localport_key.pub user@target-host
```

### 2. Test SSH Connection

```bash
# Test the connection
ssh -i ~/.ssh/localport_key user@target-host

# Test with specific port
ssh -i ~/.ssh/localport_key -p 2222 user@target-host
```

### 3. Configure LocalPort Service

Create or update your LocalPort configuration file:

```yaml
# ~/.config/localport/config.yaml
version: "1.0"

services:
  - name: my-database
    technology: ssh
    local_port: 5432
    remote_port: 5432
    connection:
      host: db.example.com
      user: deploy
      key_file: ~/.ssh/localport_key
      port: 22
    enabled: true
    tags: [database, production]
    description: "Production database via SSH tunnel"
    health_check:
      type: tcp
      interval: 30
      timeout: 5.0
      failure_threshold: 3
```

### 4. Start the Tunnel

```bash
# Start the specific service
localport start my-database

# Or start all enabled services
localport start
```

## Authentication Methods

### SSH Key Authentication (Recommended)

```yaml
connection:
  host: example.com
  user: deploy
  key_file: ~/.ssh/id_rsa
  port: 22
```

**Benefits:**
- More secure than passwords
- No interactive prompts
- Can be automated

### Password Authentication

```yaml
connection:
  host: example.com
  user: deploy
  password: ${SSH_PASSWORD}  # Use environment variable
  port: 22
```

**Requirements:**
- `sshpass` must be installed
- Less secure than key-based auth

**Install sshpass:**
```bash
# macOS
brew install sshpass

# Ubuntu/Debian
sudo apt-get install sshpass

# CentOS/RHEL
sudo yum install sshpass
```

## Configuration Examples

### Basic Database Tunnel

```yaml
services:
  - name: postgres-prod
    technology: ssh
    local_port: 5432
    remote_port: 5432
    connection:
      host: db.production.com
      user: tunnel-user
      key_file: ~/.ssh/production_key
    enabled: true
    description: "Production PostgreSQL database"
```

### Multiple Services on Same Host

```yaml
services:
  - name: app-database
    technology: ssh
    local_port: 5432
    remote_port: 5432
    connection:
      host: server.example.com
      user: deploy
      key_file: ~/.ssh/deploy_key
    enabled: true

  - name: app-redis
    technology: ssh
    local_port: 6379
    remote_port: 6379
    connection:
      host: server.example.com
      user: deploy
      key_file: ~/.ssh/deploy_key
    enabled: true
```

### Non-Standard SSH Port

```yaml
services:
  - name: legacy-service
    technology: ssh
    local_port: 8080
    remote_port: 80
    connection:
      host: legacy.example.com
      user: admin
      key_file: ~/.ssh/legacy_key
      port: 2222  # Non-standard SSH port
    enabled: true
```

### Environment Variables

```yaml
services:
  - name: dynamic-service
    technology: ssh
    local_port: 3000
    remote_port: 3000
    connection:
      host: ${SSH_HOST}
      user: ${SSH_USER}
      key_file: ${SSH_KEY_FILE}
      port: ${SSH_PORT:22}  # Default to 22 if not set
    enabled: true
```

## Security Best Practices

### SSH Key Management

1. **Use dedicated keys for LocalPort:**
   ```bash
   ssh-keygen -t rsa -b 4096 -f ~/.ssh/localport_key -C "localport-tunneling"
   ```

2. **Set proper permissions:**
   ```bash
   chmod 600 ~/.ssh/localport_key
   chmod 644 ~/.ssh/localport_key.pub
   ```

3. **Use SSH agent for key management:**
   ```bash
   ssh-add ~/.ssh/localport_key
   ```

### Connection Security

1. **Disable password authentication on servers:**
   ```bash
   # In /etc/ssh/sshd_config
   PasswordAuthentication no
   PubkeyAuthentication yes
   ```

2. **Use SSH configuration file:**
   ```bash
   # ~/.ssh/config
   Host tunnel-server
       HostName db.example.com
       User deploy
       IdentityFile ~/.ssh/localport_key
       Port 22
       StrictHostKeyChecking yes
   ```

3. **Limit SSH access:**
   ```bash
   # In /etc/ssh/sshd_config
   AllowUsers deploy tunnel-user
   ```

## Health Checks

LocalPort supports various health check types for SSH tunnels:

### TCP Health Check

```yaml
health_check:
  type: tcp
  interval: 30
  timeout: 5.0
  failure_threshold: 3
  config:
    host: localhost
    port: 5432
```

### HTTP Health Check

```yaml
health_check:
  type: http
  interval: 60
  timeout: 10.0
  failure_threshold: 2
  config:
    url: "http://localhost:8080/health"
    method: GET
    expected_status: 200
```

### Database Health Check

```yaml
health_check:
  type: postgres
  interval: 45
  timeout: 15.0
  failure_threshold: 2
  config:
    database: myapp
    user: ${DB_USER}
    password: ${DB_PASSWORD}
    host: localhost
    port: 5432
```

## Troubleshooting

### Common Issues

#### 1. SSH Connection Refused

**Symptoms:**
- `Connection refused` errors
- Tunnel fails to start

**Solutions:**
```bash
# Check if SSH service is running on target
ssh user@host

# Verify port and host
telnet host 22

# Check firewall rules
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS
```

#### 2. Permission Denied

**Symptoms:**
- `Permission denied (publickey)` errors
- Authentication failures

**Solutions:**
```bash
# Check key permissions
ls -la ~/.ssh/localport_key

# Fix permissions if needed
chmod 600 ~/.ssh/localport_key

# Test key authentication
ssh -i ~/.ssh/localport_key user@host

# Check if key is added to authorized_keys
ssh-copy-id -i ~/.ssh/localport_key.pub user@host
```

#### 3. Port Already in Use

**Symptoms:**
- `Address already in use` errors
- Local port conflicts

**Solutions:**
```bash
# Check what's using the port
lsof -i :5432
netstat -tulpn | grep 5432

# Kill conflicting process
sudo kill -9 <PID>

# Use different local port
local_port: 5433
```

#### 4. SSH Key Not Found

**Symptoms:**
- `SSH key file not found` errors
- File path issues

**Solutions:**
```bash
# Check if file exists
ls -la ~/.ssh/localport_key

# Use absolute path
key_file: /home/user/.ssh/localport_key

# Check file permissions
chmod 600 ~/.ssh/localport_key
```

### Diagnostic Commands

```bash
# Test SSH connectivity
localport ssh test my-service

# Validate configuration
localport config validate

# Check service status
localport status my-service

# View service logs
localport logs my-service

# Debug SSH connection
ssh -vvv -i ~/.ssh/key user@host
```

### Log Analysis

LocalPort creates detailed logs for SSH tunnels:

```bash
# View service logs
localport logs my-service

# Follow logs in real-time
localport logs my-service --follow

# View logs with timestamps
localport logs my-service --timestamps

# Export logs for analysis
localport logs my-service --export /tmp/ssh-debug.log
```

## Advanced Configuration

### SSH Agent Integration

```yaml
services:
  - name: agent-service
    technology: ssh
    local_port: 3000
    remote_port: 3000
    connection:
      host: example.com
      user: deploy
      # No key_file specified - will use SSH agent
    enabled: true
```

### Jump Host Configuration

For accessing services through a bastion/jump host:

```yaml
services:
  - name: secure-database
    technology: ssh
    local_port: 5432
    remote_port: 5432
    connection:
      host: bastion.example.com
      user: jump-user
      key_file: ~/.ssh/bastion_key
      # Additional SSH options for jump host
    enabled: true
    description: "Database via bastion host"
```

### Connection Multiplexing

For better performance with multiple tunnels to the same host:

```bash
# ~/.ssh/config
Host *.example.com
    ControlMaster auto
    ControlPath ~/.ssh/control-%r@%h:%p
    ControlPersist 10m
```

## Performance Tuning

### SSH Options

LocalPort automatically sets optimal SSH options:

- `ServerAliveInterval=30` - Keep connections alive
- `ServerAliveCountMax=3` - Max missed keepalives
- `StrictHostKeyChecking=no` - Don't prompt for host keys
- `UserKnownHostsFile=/dev/null` - Don't save host keys

### Resource Management

Monitor tunnel resource usage:

```bash
# Check tunnel processes
localport status --verbose

# Monitor system resources
top -p $(pgrep -f "ssh.*localport")

# Check network connections
netstat -an | grep :5432
```

## Integration Examples

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    image: myapp:latest
    environment:
      - DATABASE_URL=postgresql://user:pass@host.docker.internal:5432/db
    depends_on:
      - localport

  localport:
    image: localport:latest
    volumes:
      - ~/.ssh:/root/.ssh:ro
      - ~/.config/localport:/root/.config/localport:ro
    command: start --daemon
```

### Kubernetes

```yaml
# localport-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: localport-config
data:
  config.yaml: |
    version: "1.0"
    services:
      - name: external-db
        technology: ssh
        local_port: 5432
        remote_port: 5432
        connection:
          host: db.external.com
          user: tunnel
          key_file: /etc/ssh-keys/tunnel-key
        enabled: true
```

## Support

For additional help:

- Check the [troubleshooting guide](troubleshooting.md)
- View [CLI reference](cli-reference.md)
- See [configuration documentation](configuration.md)
- Report issues on [GitHub](https://github.com/dawsonlp/localport/issues)
