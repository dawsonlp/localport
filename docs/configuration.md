# Configuration Guide

This guide provides comprehensive documentation for LocalPort's YAML configuration format, covering all available options and advanced features.

## Configuration File Structure

LocalPort uses YAML configuration files with the following top-level structure:

```yaml
version: "1.0"                    # Configuration format version
defaults:                         # Global default settings (optional)
  health_check: { ... }
  restart_policy: { ... }
services:                         # List of port forwarding services
  - name: service1
    # ... service configuration
  - name: service2
    # ... service configuration
```

## Configuration File Locations

LocalPort searches for configuration files in the following order:

1. `./localport.yaml` (current directory)
2. `~/.config/localport/config.yaml`
3. `~/.localport.yaml`
4. `/etc/localport/config.yaml`

You can also specify a custom location:

```bash
localport --config /path/to/config.yaml start --all
```

## Service Configuration

Each service in the `services` list requires these core fields:

### Required Fields

```yaml
services:
  - name: my-service              # Unique service name
    technology: kubectl           # Technology: 'kubectl' or 'ssh'
    local_port: 5432             # Local port to bind
    remote_port: 5432            # Remote port to forward to
    connection:                  # Technology-specific connection details
      # ... connection configuration
```

### Optional Fields

```yaml
services:
  - name: my-service
    # ... required fields ...
    enabled: true                # Enable/disable service (default: true)
    tags: [database, essential]  # Tags for grouping services
    description: "My service"    # Human-readable description
    health_check:               # Health monitoring configuration
      # ... health check options
    restart_policy:             # Restart behavior configuration
      # ... restart policy options
```

## Connection Configuration

Connection configuration varies by technology:

### Kubernetes (kubectl)

```yaml
services:
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_type: service      # 'service', 'deployment', or 'pod'
      resource_name: postgres     # Name of the Kubernetes resource
      namespace: default          # Kubernetes namespace
      context: minikube          # kubectl context (optional)
```

**Connection Fields:**
- `resource_type` (optional): Type of Kubernetes resource. Default: `service`
- `resource_name` (required): Name of the resource to forward to
- `namespace` (optional): Kubernetes namespace. Default: `default`
- `context` (optional): kubectl context to use. Uses current context if not specified

### SSH Tunnels

```yaml
services:
  - name: redis
    technology: ssh
    local_port: 6379
    remote_port: 6379
    connection:
      host: redis.example.com     # Remote host
      user: deploy               # SSH username
      port: 22                   # SSH port (optional, default: 22)
      key_file: ~/.ssh/id_rsa    # SSH private key file (optional)
      password: secret           # SSH password (optional, not recommended)
```

**Connection Fields:**
- `host` (required): Remote hostname or IP address
- `user` (required): SSH username
- `port` (optional): SSH port. Default: `22`
- `key_file` (optional): Path to SSH private key file
- `password` (optional): SSH password. **Not recommended** - use key-based authentication

## Health Check Configuration

LocalPort supports multiple health check types for automatic service monitoring:

### TCP Health Check

Basic connectivity testing:

```yaml
health_check:
  type: tcp
  interval: 30                   # Check interval in seconds
  timeout: 5.0                   # Timeout in seconds
  failure_threshold: 3           # Failures before restart
  success_threshold: 1           # Successes to mark healthy
```

### HTTP Health Check

Web service health endpoints:

```yaml
health_check:
  type: http                     # or 'https'
  interval: 30
  timeout: 5.0
  failure_threshold: 3
  success_threshold: 1
  config:
    url: "http://localhost:8080/health"
    method: GET                  # HTTP method (default: GET)
    expected_status: 200         # Expected status code
    headers:                     # Optional headers
      User-Agent: "LocalPort-HealthCheck/1.0"
      Authorization: "Bearer ${API_TOKEN}"
```

### PostgreSQL Health Check

Database connectivity testing (requires `psycopg`):

```yaml
health_check:
  type: postgres
  interval: 30
  timeout: 10.0
  failure_threshold: 3
  config:
    database: postgres           # Database name
    user: postgres              # Database user
    password: ${DB_PASSWORD}    # Database password (REQUIRED)
    host: localhost             # Database host (default: localhost)
    port: 5432                  # Database port (default: 5432)
```

> **⚠️ Important**: PostgreSQL health checks require a password to be configured. Use environment variables to keep passwords secure:
> ```bash
> export DB_PASSWORD=your-secure-password
> ```
> Without a password, the health check will fail with authentication errors.

### Kafka Health Check

Message broker connectivity (requires `kafka-python`):

```yaml
health_check:
  type: kafka
  interval: 45                    # Longer interval recommended
  timeout: 15.0
  failure_threshold: 3            # Higher threshold recommended
  config:
    bootstrap_servers: "localhost:9092"  # Kafka bootstrap servers
```

> **⚠️ Known Issue**: The Kafka health check may be too aggressive in detecting failures. Consider using:
> - Longer intervals (45-60 seconds)
> - Higher failure thresholds (3-5 failures)
> - TCP health checks as an alternative for basic connectivity testing

## Restart Policy Configuration

Configure automatic restart behavior when services fail:

```yaml
restart_policy:
  enabled: true                  # Enable automatic restart
  max_attempts: 5               # Maximum restart attempts
  backoff_multiplier: 2.0       # Exponential backoff multiplier
  initial_delay: 1              # Initial delay in seconds
  max_delay: 300                # Maximum delay in seconds
```

**Restart Policy Fields:**
- `enabled` (optional): Enable automatic restart. Default: `true`
- `max_attempts` (optional): Maximum restart attempts. Default: `5`
- `backoff_multiplier` (optional): Exponential backoff multiplier. Default: `2.0`
- `initial_delay` (optional): Initial delay before first restart. Default: `1` second
- `max_delay` (optional): Maximum delay between restarts. Default: `300` seconds

**Restart Delay Calculation:**
```
delay = min(initial_delay * (backoff_multiplier ^ attempt), max_delay)
```

## Default Configuration

Use the `defaults` section to set global defaults for all services:

```yaml
version: "1.0"

defaults:
  health_check:
    type: tcp
    interval: 30
    timeout: 5.0
    failure_threshold: 3
    success_threshold: 1
  restart_policy:
    enabled: true
    max_attempts: 5
    backoff_multiplier: 2.0
    initial_delay: 1
    max_delay: 300

services:
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_name: postgres
      namespace: default
    # Inherits defaults, can override specific fields
    health_check:
      type: postgres
      config:
        database: postgres
        user: postgres
        password: ${POSTGRES_PASSWORD}
```

## Environment Variable Substitution

LocalPort supports environment variable substitution using `${VAR}` or `${VAR:default}` syntax:

### Basic Substitution

```yaml
services:
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_name: postgres
      namespace: ${KUBE_NAMESPACE}        # Required variable
      context: ${KUBE_CONTEXT:minikube}   # Optional with default
```

### With Default Values

```yaml
connection:
  host: ${DB_HOST:localhost}
  user: ${DB_USER:postgres}
  password: ${DB_PASSWORD}
  key_file: ${SSH_KEY_FILE:~/.ssh/id_rsa}
```

### In Health Check Configuration

```yaml
health_check:
  type: postgres
  config:
    database: ${DB_NAME:postgres}
    user: ${DB_USER:postgres}
    password: ${DB_PASSWORD}
    host: ${DB_HOST:localhost}
    port: ${DB_PORT:5432}
```

## Service Tags

Use tags to group and manage related services:

```yaml
services:
  - name: postgres
    tags: [database, essential, backend]
    # ... configuration

  - name: redis
    tags: [cache, essential, backend]
    # ... configuration

  - name: prometheus
    tags: [monitoring, optional]
    # ... configuration
```

**Using Tags:**

```bash
# Start all essential services
localport start --tag essential

# Start all database services
localport start --tag database

# Export monitoring services
localport config export --tag monitoring
```

## Complete Example Configuration

Here's a comprehensive example showing all features:

```yaml
version: "1.0"

# Global defaults
defaults:
  health_check:
    type: tcp
    interval: 30
    timeout: 5.0
    failure_threshold: 3
    success_threshold: 1
  restart_policy:
    enabled: true
    max_attempts: 5
    backoff_multiplier: 2.0
    initial_delay: 1
    max_delay: 300

services:
  # PostgreSQL database with custom health check
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_type: service
      resource_name: postgres
      namespace: ${KUBE_NAMESPACE:default}
      context: ${KUBE_CONTEXT:minikube}
    enabled: true
    tags: [database, essential]
    description: "PostgreSQL database for development"
    health_check:
      type: postgres
      interval: 30
      timeout: 10.0
      failure_threshold: 3
      config:
        database: ${DB_NAME:postgres}
        user: ${DB_USER:postgres}
        password: ${DB_PASSWORD}
    restart_policy:
      max_attempts: 3
      initial_delay: 2

  # Kafka message broker
  - name: kafka
    technology: kubectl
    local_port: 9092
    remote_port: 9092
    connection:
      resource_name: kafka
      namespace: kafka
    enabled: true
    tags: [messaging, essential]
    description: "Kafka message broker"
    health_check:
      type: kafka
      interval: 45
      timeout: 15.0
      failure_threshold: 2
      config:
        bootstrap_servers: "localhost:9092"

  # Redis cache via SSH
  - name: redis
    technology: ssh
    local_port: 6379
    remote_port: 6379
    connection:
      host: ${REDIS_HOST:redis.example.com}
      user: ${SSH_USER:deploy}
      key_file: ${SSH_KEY_FILE:~/.ssh/id_rsa}
      port: 22
    enabled: true
    tags: [cache, essential]
    description: "Redis cache server"
    health_check:
      type: tcp
      interval: 20
      timeout: 3.0
      failure_threshold: 5

  # Web API with HTTP health check
  - name: api
    technology: kubectl
    local_port: 8080
    remote_port: 80
    connection:
      resource_type: deployment
      resource_name: api-server
      namespace: default
    enabled: true
    tags: [web, api]
    description: "Main API server"
    health_check:
      type: http
      interval: 15
      timeout: 5.0
      failure_threshold: 3
      config:
        url: "http://localhost:8080/health"
        method: GET
        expected_status: 200
        headers:
          User-Agent: "LocalPort-HealthCheck/1.0"

  # Monitoring service (disabled by default)
  - name: prometheus
    technology: kubectl
    local_port: 9090
    remote_port: 9090
    connection:
      resource_name: prometheus-server
      namespace: monitoring
    enabled: false
    tags: [monitoring, optional]
    description: "Prometheus monitoring server"
    health_check:
      type: http
      interval: 60
      timeout: 10.0
      failure_threshold: 2
      config:
        url: "http://localhost:9090/-/healthy"
    restart_policy:
      enabled: false
```

## Configuration Validation

LocalPort provides comprehensive configuration validation:

```bash
# Validate current configuration
localport config validate

# Validate specific file
localport config validate --config /path/to/config.yaml
```

**Common Validation Errors:**

- **Missing required fields**: Service name, technology, ports, connection details
- **Invalid port numbers**: Must be between 1 and 65535
- **Duplicate service names**: Each service must have a unique name
- **Port conflicts**: Each service must use a unique local port
- **Invalid health check configuration**: Missing required config fields
- **Invalid restart policy values**: Out of range values for delays, attempts

## Configuration Export and Import

### Export Configuration

```bash
# Export all services
localport config export

# Export to file
localport config export --output backup.yaml

# Export specific services
localport config export --service postgres redis

# Export by tags
localport config export --tag essential

# Export in JSON format
localport config export --format json

# Export without defaults
localport config export --no-defaults

# Export including disabled services
localport config export --include-disabled
```

### Import Configuration

LocalPort automatically loads configuration from the standard locations. To use a different configuration file:

```bash
localport --config /path/to/config.yaml start --all
```

## Best Practices

### Security

1. **Use environment variables** for sensitive data like passwords and API keys
2. **Use SSH key authentication** instead of passwords
3. **Set appropriate file permissions** on configuration files: `chmod 600 localport.yaml`
4. **Don't commit secrets** to version control

### Organization

1. **Use descriptive service names** that clearly identify the service
2. **Group related services** with consistent tags
3. **Add descriptions** to document service purposes
4. **Use consistent naming conventions** across environments

### Health Monitoring

1. **Configure appropriate intervals** - not too frequent to avoid overhead
2. **Set reasonable timeouts** based on service characteristics
3. **Use specific health checks** (postgres, http) over generic TCP when possible
4. **Test health check endpoints** before deploying

### Restart Policies

1. **Enable restart policies** for production services
2. **Set appropriate max_attempts** to avoid infinite restart loops
3. **Use exponential backoff** to avoid overwhelming failing services
4. **Monitor restart patterns** to identify underlying issues

## Troubleshooting Configuration

### Common Issues

**Service won't start:**
- Check port availability: `lsof -i :5432`
- Verify connection details (kubectl context, SSH connectivity)
- Check service logs: `localport logs service-name`

**Health checks failing:**
- Test connectivity manually
- Verify health check configuration
- Check timeout values
- Review health check logs

**Environment variables not substituted:**
- Verify variable names and syntax
- Check if variables are exported: `echo $VAR_NAME`
- Use default values for optional variables

**Configuration validation errors:**
- Run `localport config validate` for detailed error messages
- Check YAML syntax with a YAML validator
- Verify all required fields are present

For more troubleshooting help, see the [Troubleshooting Guide](troubleshooting.md).
