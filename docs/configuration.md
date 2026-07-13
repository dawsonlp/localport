# Configuration Guide

The single reference for LocalPort's YAML configuration format. For commands and
flags, see the [CLI Reference](cli-reference.md).

## File Structure

```yaml
version: "1.0"          # Configuration format version (required)
defaults:               # Global defaults inherited by every service (optional)
  health_check: { ... }
  restart_policy: { ... }
  cluster_health: { ... }
services:               # List of port-forwarding services (required)
  - name: postgres
    # ...
cluster_contexts:       # Per-context cluster_health overrides (optional)
  production:
    cluster_health: { ... }
```

## File Locations

When `--config`/`-c` is not given, LocalPort resolves the config file in this order
(first match wins):

1. `--config` / `-c` flag
2. `$LOCALPORT_CONFIG_FILE`
3. `./localport.yaml`
4. `./localport.yml`
5. `./.localport.yaml`
6. `~/.localport.yaml`
7. `~/.config/localport/config.yaml`
8. `/etc/localport/config.yaml`

## Services

Each entry in `services` describes one port forward.

### Required fields

```yaml
services:
  - name: my-service       # Unique service name
    technology: kubectl    # 'kubectl' or 'ssh'
    local_port: 5432       # Local port to bind (1-65535)
    remote_port: 5432      # Remote port to forward to (1-65535)
    connection: { ... }    # Technology-specific connection block
```

### Optional fields

```yaml
    enabled: true              # Enable/disable service (default: true)
    tags: [database, essential]  # Tags for grouping (see Tags)
    description: "..."         # Human-readable description
    health_check: { ... }      # Health monitoring (see Health Checks)
    restart_policy: { ... }    # Restart behavior (see Restart Policy)
```

## Connection

### Kubernetes (kubectl)

```yaml
connection:
  resource_name: postgres   # Resource to forward to (required)
  resource_type: service    # 'service', 'deployment', or 'pod' (default: service)
  namespace: default        # Kubernetes namespace (default: default)
  context: minikube         # kubectl context (optional; uses current if omitted)
```

### SSH

```yaml
connection:
  host: bastion.example.com  # Remote host or bastion (required)
  user: deploy               # SSH username (optional; falls back to SSH config/agent)
  port: 22                   # SSH port (default: 22)
  key_file: ~/.ssh/id_rsa    # Private key file (optional)
  remote_host: db.internal   # Target host when `host` is a bastion/jump server (optional)
  password: secret           # SSH password (optional, not recommended — prefer keys)
```

For SSH key generation, agent setup, and bastion mechanics, see [SSH Setup](ssh-setup.md).

## Health Checks

LocalPort can monitor each service and restart it when checks fail.

```yaml
health_check:
  type: tcp                # tcp | http | https | postgres | postgresql | kafka (required)
  interval: 30             # Seconds between checks (1-3600, default: 30)
  timeout: 5.0             # Per-check timeout in seconds (0.1-300, default: 5.0)
  failure_threshold: 3     # Consecutive failures before restart (1-100, default: 3)
  success_threshold: 1     # Consecutive successes to mark healthy (1-100, default: 1)
  cluster_aware: false     # Consider cluster health before restarting (kubectl only)
  config: { ... }          # Type-specific settings (below)
```

`postgres` and `postgresql` are equivalent. `cluster_aware` is covered under
[Cluster Health Monitoring](#cluster-health-monitoring).

### TCP

No `config` block needed — a successful TCP connect passes.

```yaml
health_check:
  type: tcp
```

### HTTP / HTTPS

```yaml
health_check:
  type: http               # or 'https'
  config:
    url: "http://localhost:8080/health"   # required
    method: GET                           # default: GET
    expected_status_codes: [200]          # default: [200, 201, 202, 204]
    expected_content: "ok"                # optional substring match
    verify_ssl: true                      # default: true
    headers:                              # optional request headers
      Authorization: "Bearer ${API_TOKEN}"
```

### PostgreSQL

Requires the `psycopg` extra.

```yaml
health_check:
  type: postgres
  config:
    host: localhost          # default: localhost
    port: 5432               # default: 5432
    database: postgres       # default: postgres
    user: postgres           # default: postgres
    password: ${DB_PASSWORD} # required — auth fails without it
    sslmode: require         # optional (e.g. disable, require)
```

Keep the password in an environment variable rather than in the file.

### Kafka

Requires the `kafka-python` extra.

```yaml
health_check:
  type: kafka
  interval: 45               # longer interval recommended
  failure_threshold: 3       # higher threshold recommended
  config:
    bootstrap_servers: "localhost:9092"   # default: localhost:9092
```

The Kafka check can be aggressive at detecting failures; prefer longer intervals and
higher thresholds, or fall back to a `tcp` check for basic connectivity.

## Restart Policy

Controls automatic restarts when a service fails.

```yaml
restart_policy:
  enabled: true            # Enable automatic restart (default: true)
  max_attempts: 5          # Max restart attempts (1-100, default: 5)
  backoff_multiplier: 2.0  # Exponential backoff multiplier (1.0-10.0, default: 2.0)
  initial_delay: 1         # Initial delay in seconds (1-3600, default: 1)
  max_delay: 300           # Max delay between restarts in seconds (1-86400, default: 300)
```

Delay grows exponentially, capped at `max_delay`:
`delay = min(initial_delay * backoff_multiplier ^ attempt, max_delay)`.

## Cluster Health Monitoring

Kubernetes port-forwards can drop when the *cluster* — not the service — has a
transient problem (a Mac waking from sleep, a VPN reconnect, brief API-server
unavailability). Cluster-aware monitoring checks cluster reachability before
restarting a service, so a healthy service isn't needlessly restarted for a
cluster-side blip.

Enable it per service with the `cluster_aware` health-check flag, and configure the
monitor under `defaults.cluster_health`:

```yaml
defaults:
  cluster_health:
    enabled: true          # Enable cluster health monitoring (default: true)
    interval: 240          # Seconds between cluster checks (60-3600, default: 240)
    timeout: 30            # Timeout per kubectl command, must be < interval (5-300, default: 30)
    retry_attempts: 2      # Retries for a failed command (0-10, default: 2)
    failure_threshold: 3   # Consecutive failures before cluster is unhealthy (1-100, default: 3)
    commands:              # Which kubectl checks to run (each defaults to true)
      cluster_info: true       # kubectl cluster-info
      pod_status: true         # kubectl get pods
      node_status: true        # kubectl get nodes
      events_on_failure: true  # kubectl get events (only after a failure)
```

LocalPort monitors only the contexts used by active kubectl services. View status with
`localport cluster status` (see the [CLI Reference](cli-reference.md)).

### Per-context overrides

`cluster_contexts.<context>.cluster_health` overrides the defaults for a specific
kubectl context. Values (including `commands`) are merged over `defaults.cluster_health`:

```yaml
cluster_contexts:
  production:
    cluster_health:
      interval: 120         # check production more often
      failure_threshold: 5
  development:
    cluster_health:
      interval: 600         # check development less often
      commands:
        node_status: false  # skip node checks here
```

## Defaults

`defaults` supplies values inherited by every service; a service overrides only the
fields it sets. The built-in defaults are:

```yaml
version: "1.0"
defaults:
  health_check:
    type: tcp
    interval: 30
    timeout: 5.0
    failure_threshold: 3
    success_threshold: 1
    cluster_aware: true
  restart_policy:
    enabled: true
    max_attempts: 5
    backoff_multiplier: 2.0
    initial_delay: 1
    max_delay: 300
  cluster_health:
    enabled: true
    interval: 240
    timeout: 30
    retry_attempts: 2
    failure_threshold: 3
    commands:
      cluster_info: true
      pod_status: true
      node_status: true
      events_on_failure: true
```

## Environment Variables

Any string value supports `${VAR}` and `${VAR:default}` substitution, applied before
the YAML is parsed:

```yaml
connection:
  namespace: ${KUBE_NAMESPACE}          # required — left as-is if unset (logs a warning)
  context: ${KUBE_CONTEXT:minikube}     # uses "minikube" if KUBE_CONTEXT is unset
health_check:
  config:
    password: ${DB_PASSWORD}
    host: ${DB_HOST:localhost}
```

Use this to keep passwords and environment-specific values out of the file.

## Tags

Tags are free-form labels for grouping related services:

```yaml
services:
  - name: postgres
    tags: [database, essential]
  - name: redis
    tags: [cache, essential]
```

Commands that act on tags (e.g. `localport start --tag essential`) are documented in the
[CLI Reference](cli-reference.md).

## Complete Example

```yaml
version: "1.0"

defaults:
  health_check:
    type: tcp
    interval: 30
    timeout: 5.0
    failure_threshold: 3
    cluster_aware: true
  restart_policy:
    enabled: true
    max_attempts: 5
    backoff_multiplier: 2.0
    initial_delay: 1
    max_delay: 300
  cluster_health:
    enabled: true
    interval: 240
    timeout: 30

services:
  # PostgreSQL over kubectl with a database health check
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_type: service
      resource_name: postgres
      namespace: ${KUBE_NAMESPACE:default}
      context: ${KUBE_CONTEXT:minikube}
    tags: [database, essential]
    description: "PostgreSQL database"
    health_check:
      type: postgres
      interval: 30
      timeout: 10.0
      config:
        database: ${DB_NAME:postgres}
        user: ${DB_USER:postgres}
        password: ${DB_PASSWORD}
    restart_policy:
      max_attempts: 3
      initial_delay: 2

  # Web API over kubectl with an HTTP health check
  - name: api
    technology: kubectl
    local_port: 8080
    remote_port: 80
    connection:
      resource_type: deployment
      resource_name: api-server
      namespace: default
    tags: [web, api]
    health_check:
      type: http
      interval: 15
      config:
        url: "http://localhost:8080/health"
        expected_status_codes: [200]

  # Redis over an SSH bastion
  - name: redis
    technology: ssh
    local_port: 6379
    remote_port: 6379
    connection:
      host: ${BASTION_HOST:bastion.example.com}
      user: ${SSH_USER:deploy}
      key_file: ${SSH_KEY_FILE:~/.ssh/id_rsa}
      remote_host: redis.internal
    tags: [cache, essential]
    health_check:
      type: tcp
      interval: 20

  # Monitoring service, disabled by default
  - name: prometheus
    technology: kubectl
    local_port: 9090
    remote_port: 9090
    connection:
      resource_name: prometheus-server
      namespace: monitoring
    enabled: false
    tags: [monitoring, optional]
    health_check:
      type: http
      interval: 60
      config:
        url: "http://localhost:9090/-/healthy"
    restart_policy:
      enabled: false
```

## Best Practices

- **Secrets:** keep passwords, tokens, and keys in environment variables; never commit
  them. Restrict the config file with `chmod 600 localport.yaml`.
- **Health checks:** prefer a specific check (`postgres`, `http`) over `tcp` when
  available; set intervals and timeouts to match the service, not so tight that they add
  overhead.
- **Cluster-aware:** enable `cluster_aware: true` for kubectl services to avoid needless
  restarts during transient cluster issues.
- **Restart policy:** enable it for production services and bound `max_attempts` to avoid
  infinite restart loops.
- **Organization:** use descriptive names, consistent tags, and `description` fields.

For validation and troubleshooting, run `localport config validate` (see the
[CLI Reference](cli-reference.md)) and consult the [Troubleshooting Guide](troubleshooting.md).
</content>
</invoke>
