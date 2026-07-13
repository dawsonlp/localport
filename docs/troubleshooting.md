# Troubleshooting Guide

This guide helps you diagnose and resolve issues with LocalPort using its service logging
and diagnostic capabilities.

## Quick Diagnostic Commands

When something isn't working, start here:

```bash
localport status              # service status
localport logs --list         # available service logs
localport config validate     # configuration errors
localport daemon status       # daemon state (if using daemon mode)
```

## Understanding Error Output

LocalPort formats errors with concise, actionable messages and hides sensitive details by
default. Increase verbosity when you need more:

- **Default** — a short message with a suggested fix.
- **`--verbose` / `-v`** — adds service context and sanitized configuration details.
- **`--debug` / `-vv`** — full technical details: complete file paths, error type, and
  stack traces.

```bash
localport start database-service              # concise
localport start database-service --verbose    # more context
localport start database-service --debug       # everything
```

A typical concise error:

```
┌─ SSH Key Missing ─────────────────────────────────────────┐
│ ❌ SSH key file not found: ~/.ssh/project_key.pem         │
│                                                            │
│ 💡 Quick Fix:                                             │
│    • Generate SSH key: ssh-keygen -t rsa -f ~/.ssh/...    │
│    • Update config to point to the correct SSH key path   │
│                                                            │
│ Use --verbose for technical details.                      │
└────────────────────────────────────────────────────────────┘
```

### Privacy in error messages

Error output is sanitized so configs are safe to share:

- User paths are shortened: `/Users/johndoe/.ssh/key.pem` → `~/.ssh/key.pem` (non-home
  paths show the filename only).
- Passwords, secrets, and SSH key contents are never logged or displayed.
- Full file paths appear only in `--debug` mode.

## Service Logging Overview

LocalPort captures raw output from kubectl and SSH processes, making troubleshooting far
more effective.

```bash
localport logs --location    # show log directories
```

Default locations:

- Service logs: `~/.local/share/localport/logs/services/`
- Daemon log: `~/.local/share/localport/logs/daemon.log`

Service logs are named `<service-name>_<unique-id>.log` and contain metadata headers, raw
subprocess output, connection events, and error messages.

## Common Issues and Solutions

### 1. Service won't start

**Symptoms:** service shows "Failed"; errors about port conflicts or connection failures.

```bash
localport status
localport logs --service <service-name>
localport logs --service <service-name> --grep "error\|failed\|refused"
localport config validate
```

#### Port already in use

```bash
lsof -i :<port-number>       # find the process holding the port
kill -9 <PID>                # stop it (if safe), or change local_port in your config
```

#### Kubernetes resource not found

```bash
kubectl get service <name> -n <namespace>
kubectl config current-context
kubectl get namespaces
```

#### SSH connection issues

```bash
ssh -i ~/.ssh/id_rsa user@host      # test manually
chmod 600 ~/.ssh/id_rsa             # fix key permissions
ssh -v -i ~/.ssh/id_rsa user@host   # verbose output
```

See the [SSH Setup Guide](ssh-setup.md) for authentication specifics.

### 2. Service starts but connection fails

**Symptoms:** service shows "Running" but you can't connect to the local port.

```bash
ss -tlnp | grep <port-number>                 # confirm the port is bound
localport logs --service <name> | tail -50
localport logs --service <name> --grep "connection\|bind\|listen"
```

If the forward process died, restart it:

```bash
localport stop <name>
localport start <name>
```

Verify the target is reachable directly:

```bash
kubectl port-forward service/<name> <local-port>:<remote-port> -n <namespace>
kubectl get endpoints <name> -n <namespace>
```

### 3. Health check failures

**Symptoms:** service shows "Unhealthy" or restarts frequently.

```bash
localport config export --service <name>
localport logs --service <name> --grep "health\|check\|timeout"
telnet localhost <port>                 # TCP checks
curl http://localhost:<port>/health     # HTTP checks
```

If the check is too aggressive, relax it:

```yaml
health_check:
  type: tcp
  interval: 60
  timeout: 10.0
  failure_threshold: 5
```

PostgreSQL checks need a password (`export DB_PASSWORD=...`). For Kafka, prefer a TCP
check with a longer interval and higher threshold. See the
[Configuration Guide](configuration.md#health-checks) for all options.

### 4. Unnecessary restarts during cluster outages

For kubectl services, LocalPort can monitor **cluster** health separately from service
health. With `cluster_aware: true` on a health check (and a `cluster_health` section),
LocalPort checks the cluster first and skips restarts when the cluster — not the service —
is the problem. This avoids restart loops during temporary connectivity issues and is
especially useful for Mac users hit by idle-state connection drops (see below). A 4-minute
cluster keepalive interval works well as a default. Configure it in the
[Configuration Guide](configuration.md#cluster-health-monitoring), and
inspect cluster state with `localport cluster status`.

### 5. Configuration issues

**Symptoms:** validation errors, services not loading, or unresolved environment
variables.

```bash
localport config validate
localport config export                  # see resolved values
echo $VARIABLE_NAME                      # confirm a variable is set
```

Check YAML syntax and indentation (spaces, not tabs):

```bash
python -c "import yaml; yaml.safe_load(open('localport.yaml'))"
```

Use defaults for optional variables: `namespace: ${KUBE_NAMESPACE:default}`.

### 6. Daemon mode issues

**Symptoms:** daemon won't start, services don't auto-start, or config changes aren't
applied.

```bash
localport daemon status
localport logs                    # daemon logs
ps aux | grep localport
```

If a stale daemon is running, restart it:

```bash
localport daemon stop
localport daemon start --auto-start
```

Check log-directory permissions if startup fails:

```bash
ls -la ~/.local/share/localport/logs/
mkdir -p ~/.local/share/localport/logs/services/
```

## Platform-Specific Issues

### macOS: services fail during inactivity (lunch breaks, overnight)

**Symptoms:**

- Services work during active use but fail after periods of inactivity
- Logs show "error: lost connection to pod"
- Services restart automatically when you return to the computer

**Root cause:** macOS aggressively manages network connections during idle periods to save
power. When you step away, power-saving mode can terminate kubectl port-forward processes.
macOS treats "user away" differently from "user present but idle", deprioritizing
background network connections and throttling kubectl port-forwards.

**Diagnostic steps:**

```bash
pmset -g                                          # current power settings
pmset -g | grep networkoversleep                  # the main culprit
localport logs --service <name> --grep "lost connection\|error.*connection"
```

**Solution — fix power management (the most effective fix):**

```bash
# MOST IMPORTANT: maintain network connections during idle (AC power)
sudo pmset -c networkoversleep 1

# Reduce power-saving interference
sudo pmset -c displaysleep 30    # extend, or 0 to disable
sudo pmset -c disksleep 0
sudo pmset -c sleep 0
sudo pmset -c powernap 0
```

Enable system-wide TCP keepalives:

```bash
sudo sysctl -w net.inet.tcp.always_keepalive=1
echo "net.inet.tcp.always_keepalive=1" | sudo tee -a /etc/sysctl.conf   # persist
```

Make your configuration more tolerant of brief drops:

```yaml
defaults:
  health_check:
    interval: 60
    timeout: 10.0
    failure_threshold: 5
  restart_policy:
    max_attempts: 10
    initial_delay: 5
    backoff_multiplier: 1.5
```

Also consider enabling cluster-aware health checking (see issue 4 above), which prevents
restart churn when idle drops affect cluster connectivity.

**Testing the fix:** apply the power settings, `localport start --all`, leave the machine
idle for 1-2 hours, then check `localport status` — services should still be healthy.

**Alternatives** if power-management changes don't suit your environment: SSH tunnels
(better built-in keepalive than kubectl), a VPN to the cluster network, ingress
controllers with stable endpoints, or a dedicated always-on machine to hold the tunnels.
These can be more resilient but may still be affected by idle-state management.

### macOS: general connection instability

```bash
localport logs --service <name> --grep "darwin\|macos\|network"
networksetup -listallhardwareports
```

If on Wi-Fi, consider Ethernet for more stable connections, and check interface stats with
`netstat -i`.

### Linux: permission and network issues

```bash
localport logs --service <name> --grep "linux\|permission\|network"
sudo ufw status
sudo iptables -L
```

## Advanced Troubleshooting

### Using external tools with service logs

```bash
tail -f "$(localport logs --service <name> --path)"
grep -E "(error|failed|timeout)" "$(localport logs --service <name> --path)"
less "$(localport logs --service <name> --path)"
```

### Debugging network issues

```bash
nc -l <port>            # listen in one terminal
nc localhost <port>     # connect in another
netstat -rn             # check routing
dig <hostname>          # DNS resolution
```

### Debugging Kubernetes issues

```bash
kubectl cluster-info
kubectl logs <pod-name> -n <namespace>
kubectl describe service <name> -n <namespace>
kubectl port-forward service/<name> <local-port>:<remote-port> -n <namespace>
```

### Debugging SSH issues

```bash
ssh -vvv -i ~/.ssh/id_rsa user@host       # maximum verbosity
ssh-add -l                                # keys in the agent
ssh -L <local-port>:localhost:<remote-port> -N user@host   # tunnel manually
```

### Managing log size

Logs auto-rotate at 10MB and are cleaned up after a few days. To remove old logs manually:

```bash
du -sh ~/.local/share/localport/logs/services/*
find ~/.local/share/localport/logs/services/ -name "*.log" -mtime +3 -delete
```

## Getting Help

When reporting an issue, include:

1. LocalPort version: `localport --version`
2. OS: `uname -a`
3. Python version: `python --version`
4. Sanitized config: `localport config export`
5. Service status: `localport --output json status`
6. Relevant logs: `localport logs --service <name>`
7. Full error output with `--verbose`

Community support:

- [GitHub Issues](https://github.com/dawsonlp/localport/issues) — bugs and feature requests
- [GitHub Discussions](https://github.com/dawsonlp/localport/discussions) — questions and tips
</content>
