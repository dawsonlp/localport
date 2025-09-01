# LocalPort Operations Guide

This guide provides comprehensive instructions for LocalPort deployment, configuration, and operations for use in Cline development workflows.

## Table of Contents
- [Installation & Deployment](#installation--deployment)
- [Configuration Management](#configuration-management)
- [Basic Operations](#basic-operations)
- [SSH Bastion Host Setup](#ssh-bastion-host-setup)
- [Logging & Troubleshooting](#logging--troubleshooting)
- [Git Workflow & Release Process](#git-workflow--release-process)

## Installation & Deployment

### Development Installation
```bash
# Clone and set up development environment
git clone https://github.com/dawsonlp/localport.git
cd localport
source .venv/bin/activate
pip install -e . --force-reinstall --no-deps

# Verify installation
localport --version
```

### Production Installation
```bash
# Install from PyPI (recommended)
pipx install localport

# Or install specific version
pipx install localport==v0.3.8.1

# Verify installation
localport --version
localport --help
```

### Version Management
- **Current Stable**: v0.3.8.1 (SSH bastion host support)
- **Development**: Auto-versioned as `v0.3.X.devN` in dev branch
- **Release Tags**: Follow semantic versioning (v0.3.8, v0.3.8.1, etc.)

## Configuration Management

### Configuration File Location
```bash
# Default configuration file location
$HOME/.config/localport/config.yaml

# Alternative locations (in order of precedence)
./localport.yaml                    # Current directory
./config/localport.yaml            # Local config directory
$HOME/.config/localport/config.yaml # User config directory
```

### Configuration File Structure
```yaml
# Basic service configuration
services:
  - name: service-name
    technology: ssh|kubectl
    local_port: 5433
    remote_port: 5432
    connection:
      # SSH connection details
      host: hostname-or-ip
      user: username
      key_file: ~/.ssh/key.pem
      port: 22
      # For bastion host scenarios
      remote_host: internal-target.example.com

# Cluster health monitoring (optional)
cluster_contexts:
  - name: dev-cluster
    context: dev-hybrid-us-east-1
    health_check_interval: 30
```

### Configuration Validation
```bash
# Validate configuration file
localport config validate

# Show current configuration
localport config show

# List all configured services
localport config list
```

## Basic Operations

### Service Management
```bash
# Start all services
localport start

# Start specific service
localport start service-name

# Stop all services
localport stop

# Stop specific service
localport stop service-name

# Check service status
localport status

# Check specific service status
localport status service-name
```

### Service Status Output
```
🚀 LocalPort Service Status
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Service      ┃   Status   ┃   Tech   ┃  Local   ┃ → Target        ┃   Health   ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ service-name │ 🟢 Running │   ssh    │  :5433   │ remote:5432     │ ✓ Healthy  │
└──────────────┴────────────┴──────────┴──────────┴─────────────────┴────────────┘

📊 Total: 1 | 🟢 Running: 1 | 💛 Healthy: 1
```

### Daemon Management
```bash
# Start daemon (background service management)
localport daemon start

# Stop daemon
localport daemon stop

# Check daemon status
localport daemon status

# Restart daemon
localport daemon restart
```

## SSH Bastion Host Setup

### Configuration for Bastion Hosts
```yaml
services:
  - name: rds-database
    technology: ssh
    local_port: 5433
    remote_port: 5432
    connection:
      host: bastion-host.example.com    # Jump host/bastion server
      user: ec2-user
      key_file: ~/.ssh/bastion_key.pem
      port: 22
      remote_host: internal-db.rds.amazonaws.com  # Target behind bastion
```

### Generated SSH Command
LocalPort automatically generates the correct SSH command:
```bash
ssh -N -L 5433:internal-db.rds.amazonaws.com:5432 \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -o LogLevel=INFO \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -p 22 \
    -i ~/.ssh/bastion_key.pem \
    ec2-user@bastion-host.example.com
```

### Backward Compatibility
- Existing SSH configurations without `remote_host` continue to work
- Default behavior: `remote_host` defaults to `localhost` if not specified
- No migration required for existing configurations

## Logging & Troubleshooting

### Log Management
```bash
# List available service logs
localport logs --list

# View logs for specific service
localport logs --service service-name

# Follow logs in real-time
localport logs --service service-name --follow

# View logs with specific number of lines
localport logs --service service-name --lines 50
```

### Log File Locations
```bash
# Service logs directory
$HOME/.local/share/localport/logs/services/

# Individual service log files
$HOME/.local/share/localport/logs/services/service-name_<id>.log

# Daemon logs
$HOME/.local/share/localport/logs/daemon.log
```

### Log Output Format
```
📋 Service Logs: service-name
Service ID: service-name_abc123
Log File: /Users/user/.local/share/localport/logs/services/service-name_abc123.log
Showing 15 lines

   1 === SERVICE START: service-name ===
   2 Timestamp: 2025-01-08T19:56:54.650852Z
   3 Service ID: service-name_abc123
   4 Process ID: 12345
   5 Local Port: :5433
   6 Target: bastion-host.example.com:5432
   7 Connection Type: ssh
   8 Platform: Darwin 24.5.0
   9 LocalPort Version: 0.3.8.1
  10 === SUBPROCESS OUTPUT BEGINS ===
  11 Connection established successfully
```

### Troubleshooting Commands
```bash
# Check port conflicts
lsof -i :5433

# Check running SSH processes
ps aux | grep ssh

# Kill specific process
kill <PID>

# Verbose output for debugging
localport start service-name --verbose

# Debug mode
localport start service-name --debug
```

### Common Issues & Solutions

**Port Already in Use**:
```bash
# Find conflicting process
lsof -i :5433

# Kill conflicting process
kill <PID>

# Or use different port in configuration
```

**SSH Key Issues**:
```bash
# Check SSH key permissions
chmod 600 ~/.ssh/key.pem

# Test SSH connection manually
ssh -i ~/.ssh/key.pem user@host
```

**Configuration Issues**:
```bash
# Validate configuration
localport config validate

# Check configuration syntax
cat ~/.config/localport/config.yaml
```

## Git Workflow & Release Process

### Branch Structure
- **main**: Production releases, tagged versions
- **qa**: Quality assurance, pre-production testing
- **dev**: Development branch, feature integration
- **feature/***: Feature development branches

### Development Workflow
```bash
# Create feature branch
git checkout dev
git checkout -b feature/feature-name

# Make changes and commit
git add .
git commit -m "feat: description of changes"

# Push and create PR
git push origin feature/feature-name
gh pr create --base dev --title "feat: Feature Name" --body "Description"

# Merge PR
gh pr merge --merge --delete-branch
```

### Release Process
```bash
# 1. Merge dev → qa
git checkout qa
git merge dev
git push origin qa

# 2. Merge qa → main
git checkout main
git merge qa
git push origin main

# 3. Create and push tag
git tag v0.3.X
git push origin v0.3.X

# 4. GitHub Actions automatically:
#    - Creates GitHub release
#    - Publishes to PyPI
#    - Builds distribution packages
```

### Version Bumping
- **Patch**: Bug fixes (v0.3.8 → v0.3.9)
- **Minor**: New features (v0.3.8 → v0.4.0)
- **Major**: Breaking changes (v0.3.8 → v1.0.0)

### Release Verification
```bash
# Check GitHub Actions status
gh run list --limit 5

# View specific workflow
gh run view <run-id>

# Check PyPI deployment
gh run view --job=<job-id>

# Verify release
gh release view v0.3.X
```

## Cluster Health Monitoring

### Configuration
```yaml
cluster_contexts:
  - name: dev-cluster
    context: dev-hybrid-us-east-1
    health_check_interval: 30
```

### Commands
```bash
# Check cluster health
localport cluster status

# View cluster events
localport cluster events

# Check cluster pods
localport cluster pods
```

### Health Status Output
```
🏗️  Cluster Health
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Context              ┃ Status          ┃ Nodes    ┃ Pods     ┃ Last Check   ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ dev-hybrid-us-east-1 │ 🟢 Healthy      │ 5        │ 44       │ 0s ago       │
└──────────────────────┴─────────────────┴──────────┴──────────┴──────────────┘
```

## SSH-Specific Commands

### SSH Tunnel Management
```bash
# List SSH-specific services
localport ssh list

# Test SSH connection
localport ssh test service-name

# Show SSH command that would be executed
localport ssh command service-name
```

### SSH Configuration Validation
```bash
# Validate SSH configuration
localport ssh validate

# Test SSH key access
localport ssh test-key ~/.ssh/key.pem user@host
```

## Best Practices

### Configuration Management
1. **Use absolute paths** for SSH key files
2. **Validate configuration** before committing changes
3. **Use descriptive service names** for easy identification
4. **Document bastion host setups** in configuration comments

### Development Workflow
1. **Always test locally** before creating PRs
2. **Use proper commit messages** following conventional commits
3. **Update CHANGELOG.md** for user-facing changes
4. **Test SSH connections manually** before automating

### Deployment Process
1. **Follow git flow**: dev → qa → main → tag
2. **Verify GitHub Actions** complete successfully
3. **Test PyPI deployment** with fresh installation
4. **Update documentation** for new features

### Troubleshooting
1. **Check logs first** using `localport logs`
2. **Validate configuration** with `localport config validate`
3. **Test SSH manually** before debugging LocalPort
4. **Use verbose/debug flags** for detailed output

## Quick Reference Commands

```bash
# Essential commands for daily use
localport --version                    # Check version
localport config validate             # Validate config
localport start service-name          # Start service
localport status                      # Check all services
localport logs --service service-name # View logs
localport stop service-name           # Stop service

# Development commands
pip install -e . --force-reinstall --no-deps  # Reinstall dev version
localport config show                         # Show current config
localport --debug start service-name          # Debug mode

# Git workflow commands
git checkout dev && git pull origin dev       # Update dev branch
gh pr create --base dev                       # Create PR
gh pr merge --merge --delete-branch           # Merge PR
git tag v0.3.X && git push origin v0.3.X     # Create release
```

---

**Last Updated**: January 8, 2025  
**LocalPort Version**: v0.3.8.1  
**Purpose**: Comprehensive operations guide for Cline development workflows
