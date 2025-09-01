# Configuration Management Guide

LocalPort provides powerful configuration management features that make it easy to discover, add, remove, and manage your port forwarding services through interactive commands and intelligent discovery.

## Overview

LocalPort offers two approaches to configuration management:

1. **Interactive Commands** - Automated discovery and guided setup
2. **Manual Configuration** - Direct YAML file editing

This guide focuses on the interactive commands that streamline the configuration process and reduce the number of manual inputs required.

## Interactive Configuration Commands

### Adding Connections

The `localport config add` command provides intelligent discovery and guided setup for both Kubernetes and SSH connections.

#### Kubectl Connections (Kubernetes)

LocalPort can automatically discover Kubernetes resources and configure port forwarding with minimal user input.

**Basic Usage:**
```bash
# Interactive setup - LocalPort guides you through the process
localport config add

# Quick setup for kubectl
localport config add --technology kubectl --resource my-service
```

**Advanced Usage:**
```bash
# Specify all details upfront
localport config add \
  --technology kubectl \
  --resource postgres-service \
  --namespace production \
  --name postgres \
  --local-port 5433

# Auto-discovery with namespace resolution
localport config add --technology kubectl --resource api-service
# LocalPort will search all namespaces if not found in current/default
```

**What LocalPort Does Automatically:**

1. **Resource Discovery**: Searches for the resource in current namespace, then default namespace, then all namespaces
2. **Port Discovery**: Automatically detects available ports from the Kubernetes resource
3. **Port Selection**: Auto-selects port if only one available, or prompts for selection if multiple
4. **Service Naming**: Defaults service name to resource name for convenience
5. **Namespace Resolution**: Handles resources found in multiple namespaces by prompting for selection

**Example Flow:**
```bash
$ localport config add --technology kubectl --resource web-app

🔍 Discovering Kubernetes resource 'web-app'...
✅ Found web-app in namespace 'staging'
📋 Available ports:
   1. http (8080/TCP)
   2. https (8443/TCP)
   3. metrics (9090/TCP)

Which port would you like to forward? [1]: 1
What local port should we use? [8080]: 8080

✅ Added kubectl connection 'web-app' successfully
   Local: localhost:8080 → staging/web-app:8080
```

#### SSH Connections

LocalPort guides you through SSH tunnel setup with validation and helpful prompts.

**Basic Usage:**
```bash
# Interactive SSH setup
localport config add --technology ssh

# Quick setup with host
localport config add --technology ssh --host server.example.com
```

**Advanced Usage:**
```bash
# Full SSH configuration
localport config add \
  --technology ssh \
  --name database-tunnel \
  --host bastion.company.com \
  --user deploy \
  --key ~/.ssh/production.pem \
  --local-port 5432 \
  --remote-port 5432
```

**SSH with Bastion Host (Jump Server):**
```bash
localport config add \
  --technology ssh \
  --host bastion.company.com \
  --user ec2-user \
  --key ~/.ssh/bastion.pem \
  --local-port 3306 \
  --remote-port 3306 \
  --remote-host internal-db.rds.amazonaws.com
```

**What LocalPort Validates:**

1. **SSH Connectivity**: Tests SSH key permissions and host connectivity
2. **Port Availability**: Checks if local port is already in use
3. **Service Names**: Validates uniqueness and naming conventions
4. **Key File Paths**: Verifies SSH key file exists and has correct permissions

### Listing Connections

View all configured connections with detailed information.

**Basic Usage:**
```bash
# List all connections in a table
localport config list

# JSON output for scripting
localport config list --output json

# View with verbose details
localport --verbose config list
```

**Example Output:**
```bash
$ localport config list

🚀 LocalPort Connection Configuration
┏━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Service    ┃ Technology ┃ Local    ┃ Target               ┃ Status     ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ postgres   │ kubectl    │ :5433    │ default/postgres:5432│ ⚪ Stopped │
│ redis      │ kubectl    │ :6379    │ cache/redis:6379     │ ⚪ Stopped │
│ api-tunnel │ ssh        │ :8080    │ server.com:80        │ ⚪ Stopped │
└────────────┴────────────┴──────────┴──────────────────────┴────────────┘

📊 Summary: 3 services | kubectl: 2, ssh: 1
💡 Use 'localport start <service>' to begin port forwarding
```

### Removing Connections

Remove connections from your configuration with confirmation prompts.

**Basic Usage:**
```bash
# Remove with confirmation prompt
localport config remove postgres

# Force removal without prompt
localport config remove postgres --force

# JSON output for scripting
localport --output json config remove postgres
```

**Safety Features:**

1. **Confirmation Prompts**: Prevents accidental deletion
2. **Running Service Detection**: Warns if service is currently running
3. **Backup Creation**: Automatically creates configuration backup before removal
4. **Rollback Support**: Can restore from backup if needed

**Example Flow:**
```bash
$ localport config remove postgres

⚠️  Service 'postgres' is currently running on port 5433
❓ Are you sure you want to remove this service? [y/N]: y
✅ Stopped service 'postgres'
✅ Removed service 'postgres' from configuration
💾 Configuration backup saved to ~/.config/localport/backups/
```

## Configuration Validation

LocalPort provides comprehensive configuration validation to catch issues before they cause problems.

### Validation Command

```bash
# Validate current configuration
localport config validate

# Validate specific file
localport config validate --config /path/to/config.yaml

# JSON validation output
localport --output json config validate
```

### What Gets Validated

1. **YAML Syntax**: Ensures configuration file is valid YAML
2. **Schema Validation**: Checks required fields and data types
3. **Port Conflicts**: Detects services using the same local port
4. **Service Names**: Validates uniqueness and naming conventions
5. **Connection Details**: Verifies Kubernetes resources and SSH hosts
6. **Value Ranges**: Ensures ports are in valid range (1-65535)

**Example Validation Output:**
```bash
$ localport config validate

Configuration Validation: localport.yaml
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Level   ┃ Message                                ┃ Suggestion                             ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ERROR   │ Service 'api' missing required field  │ Add 'technology' to service 'api'     │
│ WARNING │ No version specified in configuration  │ Add 'version: "1.0"' to config       │
│ ERROR   │ Port conflict: 8080 used by multiple  │ Each service must use a unique port    │
└─────────┴────────────────────────────────────────┴────────────────────────────────────────┘

❌ Configuration is invalid: 2 error(s), 1 warning(s)
```

## Configuration Export and Import

### Exporting Configuration

Export your configuration to different formats for backup, sharing, or migration.

```bash
# Export as YAML (default)
localport config export > backup.yaml

# Export as JSON
localport config export --format json > backup.json

# Export to specific file
localport config export --output backup.yaml

# Export specific services only
localport config export --service postgres --service redis

# Export services with specific tags
localport config export --tag database --tag cache

# Include metadata and defaults
localport config export --include-defaults --include-disabled
```

**Export Features:**

1. **Format Support**: YAML and JSON export formats
2. **Selective Export**: Export specific services or tags
3. **Metadata Inclusion**: Timestamps, source file, and filter information
4. **Default Handling**: Option to include/exclude default settings
5. **Disabled Services**: Option to include/exclude disabled services

### Configuration Backup and Recovery

LocalPort automatically creates backups during critical operations:

```bash
# Manual backup creation
localport config export --output ~/.config/localport/manual-backup-$(date +%Y%m%d).yaml

# List automatic backups
ls ~/.config/localport/backups/

# Restore from backup
cp ~/.config/localport/backups/config-backup-20250901.yaml ~/.config/localport/config.yaml
localport config validate
```

**Automatic Backup Triggers:**

- Service removal operations
- Configuration file updates
- Bulk modifications
- Before destructive operations

## Advanced Configuration Patterns

### Environment-Specific Configurations

Manage different configurations for development, staging, and production:

```bash
# Development environment
localport config add --technology kubectl --resource dev-postgres --namespace development

# Staging environment  
localport config add --technology kubectl --resource staging-postgres --namespace staging

# Production environment (via SSH tunnel for security)
localport config add --technology ssh --host prod-bastion.company.com --remote-host prod-db.internal
```

### Service Templates and Patterns

Common configuration patterns for different service types:

#### Database Services

```bash
# PostgreSQL
localport config add --technology kubectl --resource postgres --local-port 5432

# MySQL
localport config add --technology kubectl --resource mysql --local-port 3306

# Redis
localport config add --technology kubectl --resource redis --local-port 6379
```

#### Web Services

```bash
# API Services
localport config add --technology kubectl --resource api-service --local-port 8080

# Frontend Applications
localport config add --technology kubectl --resource frontend --local-port 3000

# Admin Interfaces
localport config add --technology kubectl --resource admin-ui --local-port 8081
```

#### Message Queues and Streaming

```bash
# RabbitMQ
localport config add --technology kubectl --resource rabbitmq --local-port 5672

# Apache Kafka
localport config add --technology kubectl --resource kafka --local-port 9092

# Redis Pub/Sub
localport config add --technology kubectl --resource redis-pubsub --local-port 6380
```

### Batch Operations

Perform operations on multiple services efficiently:

```bash
# Export multiple services
localport config export --service postgres --service redis --service api

# Remove multiple services (with confirmation)
for service in old-service-1 old-service-2 old-service-3; do
  localport config remove "$service" --force
done

# Add multiple similar services
for env in dev staging prod; do
  localport config add \
    --technology kubectl \
    --resource "${env}-postgres" \
    --namespace "$env" \
    --name "postgres-${env}" \
    --local-port "$((5432 + ${env#*[a-z]}))"
done
```

## Integration with Other Tools

### CI/CD Pipeline Integration

Use configuration management in automated workflows:

```bash
#!/bin/bash
# Deploy script example

# Validate configuration before deployment
if ! localport config validate --config deployments/localport-prod.yaml; then
  echo "Configuration validation failed"
  exit 1
fi

# Export current config for rollback
localport config export --output "backups/pre-deploy-$(date +%Y%m%d-%H%M%S).yaml"

# Deploy new configuration
cp deployments/localport-prod.yaml ~/.config/localport/config.yaml

echo "Configuration deployed successfully"
```

### Configuration Management Tools

Integration with configuration management systems:

**Ansible Integration:**
```yaml
- name: Configure LocalPort services
  shell: |
    localport config add \
      --technology kubectl \
      --resource "{{ item.resource }}" \
      --namespace "{{ item.namespace }}" \
      --local-port "{{ item.local_port }}"
  loop: "{{ localport_services }}"
```

**Docker Integration:**
```dockerfile
FROM alpine:latest
RUN pip install localport
COPY localport.yaml /etc/localport/config.yaml
CMD ["localport", "daemon", "start", "--config", "/etc/localport/config.yaml"]
```

## Troubleshooting Configuration Issues

### Common Configuration Problems

#### 1. Resource Not Found

```bash
# Problem: Kubernetes resource not found
$ localport config add --technology kubectl --resource missing-service

# Solution: Check available resources
kubectl get services,pods,deployments --all-namespaces | grep missing
```

#### 2. Port Conflicts

```bash
# Problem: Port already in use
$ localport config add --local-port 8080

# Solution: Check what's using the port
lsof -i :8080
# Or choose a different port
localport config add --local-port 8081
```

#### 3. SSH Connection Issues

```bash
# Problem: SSH connection fails
$ localport config add --technology ssh --host server.com

# Solution: Test SSH connectivity
ssh -i ~/.ssh/key.pem user@server.com
# Fix key permissions
chmod 600 ~/.ssh/key.pem
```

#### 4. Configuration File Issues

```bash
# Problem: Configuration file corruption
$ localport config validate

# Solution: Restore from backup
ls ~/.config/localport/backups/
cp ~/.config/localport/backups/latest-backup.yaml ~/.config/localport/config.yaml
```

### Debug Mode

Use verbose mode for detailed troubleshooting:

```bash
# Verbose output for all operations
localport --verbose config add --technology kubectl --resource debug-service

# Debug mode with maximum verbosity
localport --verbosity 2 config validate
```

### Configuration Reset

Reset configuration to clean state:

```bash
# Backup current configuration
localport config export --output emergency-backup.yaml

# Remove configuration file
rm ~/.config/localport/config.yaml

# Start fresh
localport config validate  # Will create new empty config
```

## Best Practices

### Service Naming

1. **Use descriptive names**: `postgres-staging` instead of `db1`
2. **Include environment**: `api-production`, `cache-development`
3. **Avoid special characters**: Use hyphens, not underscores or spaces
4. **Be consistent**: Follow a naming pattern across services

### Port Management

1. **Reserve port ranges**: 5400-5499 for databases, 8000-8099 for APIs
2. **Document port assignments**: Keep a reference of what ports are used
3. **Use consistent offsets**: prod on 5432, staging on 5433, dev on 5434

### Configuration Organization

1. **Use tags effectively**: `[database, production]`, `[api, development]`
2. **Group related services**: Keep services for the same application together
3. **Regular validation**: Run `localport config validate` before commits
4. **Backup frequently**: Export configurations before major changes

### Security Considerations

1. **Protect SSH keys**: Use proper file permissions (600)
2. **Use bastion hosts**: Don't expose production databases directly
3. **Rotate credentials**: Update SSH keys and passwords regularly
4. **Audit configurations**: Review who has access to what services

## Migration from Manual Configuration

If you have existing manual YAML configurations, you can gradually migrate to using the interactive commands:

### Step 1: Validate Existing Configuration

```bash
localport config validate
localport config list  # See current services
```

### Step 2: Export for Backup

```bash
localport config export --output migration-backup.yaml
```

### Step 3: Migrate Services One by One

```bash
# Remove old service
localport config remove old-service-name --force

# Add with new interactive command
localport config add --technology kubectl --resource new-service-name
```

### Step 4: Validate New Configuration

```bash
localport config validate
localport start --all  # Test that services work
```

## Summary

LocalPort's configuration management features provide:

✅ **Intelligent Discovery** - Automatic Kubernetes resource and port detection  
✅ **Guided Setup** - Interactive prompts reduce manual input requirements  
✅ **Safety Features** - Validation, backups, and confirmation prompts  
✅ **Flexible Output** - Table and JSON formats for both humans and scripts  
✅ **Comprehensive Validation** - Catch issues before they cause problems  
✅ **Export/Import** - Easy backup, sharing, and migration capabilities  

The interactive commands are designed to make configuration management faster, safer, and more user-friendly while maintaining the flexibility of manual YAML configuration when needed.

For more advanced topics, see:
- [CLI Reference](cli-reference.md) - Complete command documentation
- [Examples](examples/) - Real-world configuration patterns
- [Troubleshooting Guide](troubleshooting.md) - Solutions for common issues
