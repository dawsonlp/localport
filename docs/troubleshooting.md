# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with LocalPort using the comprehensive service logging and diagnostic capabilities.

## Quick Diagnostic Commands

When something isn't working, start with these commands:

```bash
# Check service status
localport status

# List available service logs
localport logs --list

# Validate configuration
localport config validate

# Check daemon status (if using daemon mode)
localport daemon status
```

## Service Logging Overview

LocalPort v0.3.4+ includes comprehensive service logging that captures raw output from kubectl and SSH processes, making troubleshooting much more effective.

### Log Locations

```bash
# Show log directory locations
localport logs --location

# Default locations:
# Service logs: ~/.local/share/localport/logs/services/
# Daemon logs:  ~/.local/share/localport/logs/daemon.log
```

### Log File Format

Service logs are named: `<service-name>_<unique-id>.log`

Each log file contains:
- **Metadata headers** with service configuration
- **Raw subprocess output** from kubectl/ssh
- **Connection events** and error messages
- **Platform-specific diagnostic information**

## Common Issues and Solutions

### 1. Service Won't Start

**Symptoms:**
- Service shows "Failed" status
- Error messages about port conflicts or connection failures

**Diagnostic Steps:**

```bash
# Check service status
localport status

# View service logs for detailed error information
localport logs --service <service-name>

# Look for specific error patterns
localport logs --service <service-name> --grep "error\|failed\|refused"

# Validate configuration
localport config validate
```

**Common Causes and Solutions:**

#### Port Already in Use
```bash
# Check what's using the port
lsof -i :<port-number>

# Example: Check port 5432
lsof -i :5432

# Kill the conflicting process (if safe)
kill -9 <PID>

# Or change the local port in your configuration
```

#### Kubernetes Resource Not Found
```bash
# Check if the resource exists
kubectl get service <service-name> -n <namespace>
kubectl get deployment <deployment-name> -n <namespace>
kubectl get pod <pod-name> -n <namespace>

# Check your kubectl context
kubectl config current-context
kubectl config get-contexts

# Verify namespace
kubectl get namespaces
```

#### SSH Connection Issues
```bash
# Test SSH connectivity manually
ssh -i ~/.ssh/id_rsa user@host

# Check SSH key permissions
ls -la ~/.ssh/id_rsa
chmod 600 ~/.ssh/id_rsa

# Test SSH with verbose output
ssh -v -i ~/.ssh/id_rsa user@host
```

### 2. Service Starts But Connection Fails

**Symptoms:**
- Service shows "Running" status
- Cannot connect to local port
- Connection refused errors

**Diagnostic Steps:**

```bash
# Check if the port is actually bound
netstat -tlnp | grep <port-number>
# or
ss -tlnp | grep <port-number>

# View recent service logs
localport logs --service <service-name> | tail -50

# Look for connection-related errors
localport logs --service <service-name> --grep "connection\|bind\|listen"
```

**Common Solutions:**

#### Port Forward Process Died
```bash
# Check service logs for process termination
localport logs --service <service-name> --grep "exit\|terminated\|killed"

# Restart the service
localport stop <service-name>
localport start <service-name>
```

#### Wrong Target Configuration
```bash
# Verify the remote service is accessible
kubectl port-forward service/<service-name> <local-port>:<remote-port> -n <namespace>

# Check service endpoints
kubectl get endpoints <service-name> -n <namespace>
```

### 3. Health Check Failures

**Symptoms:**
- Service shows "Unhealthy" status
- Frequent restarts
- Health check timeout errors

**Diagnostic Steps:**

```bash
# Check health check configuration
localport config export --service <service-name>

# View health check logs
localport logs --service <service-name> --grep "health\|check\|timeout"

# Test connectivity manually
telnet localhost <port>  # For TCP health checks
curl http://localhost:<port>/health  # For HTTP health checks
```

**Common Solutions:**

#### Health Check Too Aggressive
```yaml
# Adjust health check settings in configuration
health_check:
  type: tcp
  interval: 60        # Increase interval
  timeout: 10.0       # Increase timeout
  failure_threshold: 5  # Allow more failures
```

#### PostgreSQL Health Check Authentication
```bash
# Ensure password is set
export DB_PASSWORD=your-password

# Test database connection manually
psql -h localhost -p <port> -U <user> -d <database>
```

#### Kafka Health Check Issues
```yaml
# Use TCP health check instead for Kafka
health_check:
  type: tcp
  interval: 45
  timeout: 15.0
  failure_threshold: 3
```

### 4. Configuration Issues

**Symptoms:**
- Validation errors
- Services not loading
- Environment variable substitution failures

**Diagnostic Steps:**

```bash
# Validate configuration with detailed output
localport config validate --strict

# Check environment variables
echo $VARIABLE_NAME

# Export configuration to see resolved values
localport config export
```

**Common Solutions:**

#### YAML Syntax Errors
```bash
# Use a YAML validator
python -c "import yaml; yaml.safe_load(open('localport.yaml'))"

# Check indentation (use spaces, not tabs)
cat -A localport.yaml
```

#### Missing Environment Variables
```bash
# Set required variables
export KUBE_CONTEXT=my-cluster
export DB_PASSWORD=secret

# Use default values in configuration
connection:
  namespace: ${KUBE_NAMESPACE:default}
  context: ${KUBE_CONTEXT:minikube}
```

### 5. Daemon Mode Issues

**Symptoms:**
- Daemon won't start
- Services not auto-starting
- Configuration changes not applied

**Diagnostic Steps:**

```bash
# Check daemon status
localport daemon status

# View daemon logs
localport logs

# Check for daemon process
ps aux | grep localport
```

**Common Solutions:**

#### Daemon Already Running
```bash
# Stop existing daemon
localport daemon stop

# Start fresh daemon
localport daemon start --auto-start
```

#### Permission Issues
```bash
# Check log directory permissions
ls -la ~/.local/share/localport/logs/

# Create directories if missing
mkdir -p ~/.local/share/localport/logs/services/
```

### 6. Platform-Specific Issues

#### macOS Issues

##### Services Fail During Inactivity (Lunch Breaks, Overnight)

**Symptoms:**
- Services work fine during active computer use
- Services fail after periods of inactivity (lunch breaks, overnight)
- Log shows "error: lost connection to pod" messages
- Services restart automatically when you return to computer

**Root Cause:**
macOS aggressively manages network connections during idle periods to save power. When you step away from your computer, the system enters power-saving mode that can terminate kubectl port-forward processes.

**Diagnostic Steps:**
```bash
# Check current power management settings
pmset -g

# Look for idle-related connection drops in logs
localport logs --service <service-name> --grep "lost connection\|error.*connection"

# Check if networkoversleep is disabled (this is the main culprit)
pmset -g | grep networkoversleep
```

**Solution - Fix Power Management Settings:**

The most critical fix is to prevent network sleep during idle periods:

```bash
# MOST IMPORTANT: Maintain network connections during idle (AC power)
sudo pmset -c networkoversleep 1

# Prevent display sleep from affecting network connections
sudo pmset -c displaysleep 30  # Extend to 30 minutes, or 0 to disable

# Disable disk sleep when plugged in
sudo pmset -c disksleep 0

# Ensure system doesn't sleep when plugged in
sudo pmset -c sleep 0

# Disable Power Nap which can interfere during idle periods
sudo pmset -c powernap 0
```

**Additional Network Stability Improvements:**

```bash
# Enable TCP keepalives system-wide (temporary - resets on reboot)
sudo sysctl -w net.inet.tcp.always_keepalive=1

# Make TCP keepalives permanent
echo "net.inet.tcp.always_keepalive=1" | sudo tee -a /etc/sysctl.conf
```

**Configuration Adjustments for Better Idle Tolerance:**

Update your LocalPort configuration to be more tolerant of brief connection issues:

```yaml
defaults:
  health_check:
    interval: 60        # Increase from 30 seconds
    timeout: 10.0       # Increase timeout
    failure_threshold: 5  # Allow more failures before restart
  restart_policy:
    max_attempts: 10    # Increase max restart attempts
    initial_delay: 5    # Longer initial delay
    backoff_multiplier: 1.5  # Gentler backoff
```

**Testing the Fix:**
1. Apply the power management changes above
2. Start your services: `localport start --all`
3. Leave your computer idle for 1-2 hours
4. Return and check: `localport status`
5. Services should still be running and healthy

**Why This Happens:**
- macOS treats "user away" differently than "user present but idle"
- Network connections are deprioritized when no user activity is detected
- Display sleep (after 10 minutes) triggers more aggressive power management
- kubectl port-forward processes are seen as "background" and get throttled

**Alternative Solutions:**
If power management changes aren't suitable for your environment:

1. **Use SSH tunnels with keepalive settings** (may be more resilient than kubectl):
   ```yaml
   technology: ssh
   connection:
     host: bastion.example.com
     user: myuser
     remote_host: internal-service
     # SSH has better built-in keepalive mechanisms
   ```
   Note: SSH tunnels may still be affected by the same idle issues, but SSH has better built-in keepalive and reconnection mechanisms than kubectl port-forward.

2. **Use a VPN connection** to your cluster network (most reliable for idle periods)

3. **Set up ingress controllers** with stable external endpoints (eliminates port-forwarding entirely)

4. **Use a dedicated always-on machine** (like a small server or Raspberry Pi) to maintain the tunnels

**Important:** The power management fix above is the most effective solution. Alternative connection methods may still be affected by Mac's idle-state network management, though some (like VPN or ingress) can be more resilient.

##### General macOS Connection Issues

**Symptoms:**
- Frequent connection drops during active use
- Port forwarding instability
- Network-related errors

**Diagnostic Steps:**
```bash
# Check for macOS-specific errors in logs
localport logs --service <service-name> --grep "darwin\|macos\|network"

# Monitor system logs for network issues
log stream --predicate 'process == "kubectl"' --info

# Check WiFi vs Ethernet connection stability
networksetup -listallhardwareports
```

**Solutions:**
```bash
# If on WiFi, disable WiFi power management
sudo /System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport en0 prefs DisconnectOnLogout=NO

# Consider using Ethernet for more stable connections
# Check network interface statistics
netstat -i
```

#### Ubuntu/Linux Issues

**Symptoms:**
- Permission denied errors
- Network configuration issues

**Diagnostic Steps:**
```bash
# Check for Linux-specific errors
localport logs --service <service-name> --grep "linux\|permission\|network"

# Check firewall settings
sudo ufw status
sudo iptables -L
```

## Advanced Troubleshooting

### Using External Tools with Service Logs

```bash
# Follow logs in real-time
tail -f $(localport logs --service <service-name> --path)

# Search logs with advanced patterns
grep -E "(error|failed|timeout)" $(localport logs --service <service-name> --path)

# Analyze logs with awk
awk '/error/ {print $0}' $(localport logs --service <service-name> --path)

# View logs with less for easy navigation
less $(localport logs --service <service-name> --path)
```

### Debugging Network Issues

```bash
# Test local port binding
nc -l <port>  # In one terminal
nc localhost <port>  # In another terminal

# Check routing
netstat -rn

# Test DNS resolution
nslookup <hostname>
dig <hostname>
```

### Debugging Kubernetes Issues

```bash
# Check cluster connectivity
kubectl cluster-info

# View pod logs
kubectl logs <pod-name> -n <namespace>

# Check service endpoints
kubectl describe service <service-name> -n <namespace>

# Test port forward manually
kubectl port-forward service/<service-name> <local-port>:<remote-port> -n <namespace>
```

### Debugging SSH Issues

```bash
# Test SSH with maximum verbosity
ssh -vvv -i ~/.ssh/id_rsa user@host

# Check SSH agent
ssh-add -l

# Test SSH tunnel manually
ssh -L <local-port>:localhost:<remote-port> -N user@host
```

## Performance Troubleshooting

### High CPU Usage

```bash
# Check process CPU usage
top -p $(pgrep -f localport)

# Monitor system resources
htop

# Check for excessive health checking
localport logs --service <service-name> --grep "health.*check" | wc -l
```

### Memory Issues

```bash
# Check memory usage
ps aux | grep localport

# Monitor memory over time
watch 'ps aux | grep localport'
```

### Log File Size Issues

```bash
# Check log file sizes
du -sh ~/.local/share/localport/logs/services/*

# Clean up old logs (logs auto-rotate at 10MB)
find ~/.local/share/localport/logs/services/ -name "*.log" -mtime +3 -delete
```

## Getting Help

### Information to Include in Bug Reports

When reporting issues, include:

1. **LocalPort version**: `localport --version`
2. **Operating system**: `uname -a`
3. **Python version**: `python --version`
4. **Configuration** (sanitized): `localport config export`
5. **Service status**: `localport status --output json`
6. **Relevant logs**: `localport logs --service <service-name>`
7. **Error messages**: Full error output with `--verbose`

### Verbose Mode

Enable verbose mode for detailed debugging:

```bash
# Verbose output for all commands
localport --verbose start --all
localport --verbose status
localport --verbose daemon start
```

### Log Analysis Tips

1. **Start with recent logs**: `tail -100 <log-file>`
2. **Look for error patterns**: `grep -i error <log-file>`
3. **Check timestamps**: Look for timing patterns in failures
4. **Compare working vs failing**: Use diff to compare logs
5. **Check metadata headers**: Service configuration is logged at startup

### Community Support

- **GitHub Issues**: [Report bugs and request features](https://github.com/dawsonlp/localport/issues)
- **Discussions**: [Ask questions and share tips](https://github.com/dawsonlp/localport/discussions)
- **Documentation**: [Complete documentation](https://github.com/dawsonlp/localport/tree/main/docs)

## Prevention Tips

### Configuration Best Practices

1. **Use health checks** for critical services
2. **Set appropriate timeouts** based on service characteristics
3. **Use environment variables** for sensitive data
4. **Validate configuration** before deployment
5. **Use tags** to organize services

### Monitoring Best Practices

1. **Check status regularly**: `localport status`
2. **Monitor logs**: Set up log rotation and monitoring
3. **Use daemon mode** for production deployments
4. **Set up alerts** for service failures
5. **Regular configuration backups**: `localport config export`

### Maintenance Tasks

```bash
# Weekly maintenance
localport config validate
localport daemon reload  # If using daemon mode
localport logs --location  # Check log sizes

# Monthly maintenance
localport config export --output backup-$(date +%Y%m%d).yaml
# Clean up old logs if needed
```

This troubleshooting guide should help you quickly identify and resolve most issues with LocalPort. The comprehensive service logging in v0.3.4+ makes debugging much more effective than previous versions.
