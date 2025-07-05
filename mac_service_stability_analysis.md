# Mac Service Stability Analysis - LocalPort Diagnosis

## Executive Summary

Your Mac is experiencing kubectl port-forward process failures that cause LocalPort services to die during periods of inactivity (lunch breaks, extended periods away from computer). The root cause is **"error: lost connection to pod"** - a network connectivity issue triggered by Mac's idle/sleep behavior and power management when you're not actively using the system.

**Key Pattern**: Services stay stable during active work but fail during inactivity periods (lunch, breaks, overnight).

## Key Findings

### 1. Root Cause: Idle-Triggered Network Connection Drops
- **Primary Issue**: kubectl port-forward processes are losing connection to pods with "error: lost connection to pod"
- **Pattern**: Services fail during inactivity periods (lunch breaks, overnight, extended time away)
- **Stable During**: Active work sessions - connections remain stable when you're using the computer
- **Impact**: All 4 services (postgres, kafka, keycloak, keycloak-mgmt) affected during idle periods

### 2. Daemon Behavior Analysis
- **Daemon Status**: Running continuously for 10.4+ hours (good)
- **Health Check Frequency**: Every 30 seconds with 3-failure threshold
- **Restart Policy**: Working correctly - services restart after 3 consecutive failures
- **Why it waited for login**: It didn't - the daemon was actively restarting services all night, but they kept failing

### 3. Failure Pattern Timeline
From log analysis, services have been failing at these intervals:
- 07/04 21:26 → 01:13 → 02:01 → 02:31 → 03:32 → 03:44 → 05:01 → 05:20 → 06:53 → 07:10 → 07:27 → 07:50 → 09:06 → 09:25 → 10:07 → 10:34 → 10:46 → 11:01 → 11:17 → 11:34 → 11:43 → 11:49

This shows consistent failures every 15-45 minutes throughout the night.

## Mac-Specific Issues (Idle-Triggered)

### 1. Power Management Settings (The Primary Culprit)
Current settings that cause failures during inactivity:
- `disksleep: 10` - Disks sleep after 10 minutes of inactivity
- `displaysleep: 10` - Display sleeps after 10 minutes of inactivity
- `networkoversleep: 0` - **CRITICAL**: Network connections NOT maintained during sleep/idle
- `powernap: 1` - Power Nap can disrupt network connections during idle periods

### 2. Idle-State Network Behavior
- Mac aggressively manages network connections when system goes idle
- WiFi power management kicks in during inactivity
- TCP connections may be dropped to save power when no user activity detected
- `net.inet.tcp.always_keepalive: 0` - No keepalives to maintain idle connections

### 3. Activity-Based Process Management
- Mac deprioritizes background processes during idle periods
- kubectl port-forward processes are seen as "inactive" when you're away
- System may throttle or suspend network processes during extended inactivity

## Differences from Linux
Your Linux laptop likely:
- Has different power management (less aggressive)
- Different network stack behavior (more tolerant of long connections)
- Different process scheduling/cleanup policies
- May be using wired connection vs WiFi

## Recommended Solutions

### Immediate Fixes (High Impact)

#### 1. Improve Network Stability (Critical for Idle Periods)
```bash
# MOST IMPORTANT: Prevent network sleep when on AC power
sudo pmset -c networkoversleep 1

# Prevent display sleep from affecting network (extend or disable)
sudo pmset -c displaysleep 30  # Extend to 30 minutes, or set to 0 to disable

# Disable disk sleep when plugged in (helps maintain system responsiveness)
sudo pmset -c disksleep 0

# Ensure system doesn't sleep when plugged in
sudo pmset -c sleep 0

# Disable Power Nap which can interfere during idle periods
sudo pmset -c powernap 0
```

#### 2. Enable TCP Keepalives
```bash
# Enable TCP keepalives system-wide (temporary - resets on reboot)
sudo sysctl -w net.inet.tcp.always_keepalive=1

# Make permanent by adding to /etc/sysctl.conf:
echo "net.inet.tcp.always_keepalive=1" | sudo tee -a /etc/sysctl.conf
```

#### 3. Optimize LocalPort Configuration
Update your `~/.config/localport/config.yaml`:

```yaml
# Add to defaults section:
defaults:
  health_check:
    type: tcp
    interval: 60  # Increase from 30 to reduce check frequency
    timeout: 10.0  # Increase timeout
    failure_threshold: 5  # Increase threshold to be more tolerant
  restart_policy:
    enabled: true
    max_attempts: 10  # Increase max attempts
    backoff_multiplier: 1.5  # Reduce backoff multiplier
    initial_delay: 5  # Increase initial delay
    max_delay: 300
```

### Medium-Term Solutions

#### 4. kubectl Configuration Improvements
Add to your kubectl config or create a script wrapper:
```bash
# Add to ~/.kube/config or set environment variables:
export KUBECTL_EXTERNAL_DIFF=""
export KUBECTL_COMMAND_TIMEOUT=300

# Consider using kubectl with explicit timeouts:
kubectl port-forward --request-timeout=0s service/postgres-dev-cluster-rw 6432:5432
```

#### 5. Network Interface Optimization
```bash
# Check if you're on WiFi and consider ethernet
networksetup -listallhardwareports

# If on WiFi, disable WiFi power management:
sudo /System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport en0 prefs DisconnectOnLogout=NO
```

### Long-Term Solutions

#### 6. Alternative Connection Methods
Consider switching from kubectl port-forward to:
- **SSH tunnels** (more stable for long-running connections)
- **VPN connection** to cluster network
- **Ingress controllers** with stable external endpoints

#### 7. Monitoring and Alerting
Add monitoring to detect when services go down:
```bash
# Create a monitoring script
localport logs --follow | grep "lost connection" | while read line; do
    echo "$(date): Connection lost detected: $line" >> ~/localport-connection-issues.log
done
```

## Testing Your Fixes

### 1. Apply the immediate fixes above
### 2. Monitor for 24 hours:
```bash
# Watch daemon logs in real-time
localport logs --follow

# Check service status every few minutes
watch -n 300 'localport status'
```

### 3. Compare failure frequency
- Before: Failures during lunch breaks, overnight, extended idle periods
- Target: Services remain stable during inactivity periods (2+ hours idle)
- Test: Leave computer idle for 1-2 hours and check if services stay up

## Why This Happens More on Mac (Especially During Inactivity)

1. **Idle-State Power Management**: macOS aggressively manages power during inactivity periods
2. **Activity-Based Network Management**: Network connections are deprioritized when no user activity
3. **Display Sleep Correlation**: Network behavior changes when display sleeps (10 min timeout)
4. **WiFi Power Management**: More aggressive during idle periods vs. active use
5. **Background Process Throttling**: kubectl processes are throttled during extended inactivity
6. **User Presence Detection**: macOS treats "user away" differently than "user present but idle"

**Why it works during active work**: Your keyboard/mouse activity keeps the system in "active" mode, preventing aggressive power management of network connections.

## Expected Outcomes

After implementing these fixes:
- Services should stay up for hours instead of minutes
- Fewer restart cycles in the logs
- More stable development experience
- Reduced resource usage from constant restarts

## Monitoring Commands

```bash
# Check current power settings
pmset -g

# Monitor network connections
netstat -an | grep :6432

# Watch for kubectl processes
ps aux | grep kubectl

# Check system logs for network issues
log show --predicate 'subsystem == "com.apple.network"' --last 1h
```

The key insight is that this isn't a LocalPort daemon issue - it's a Mac network stability issue affecting the underlying kubectl processes. The daemon is working correctly by detecting failures and restarting services, but we need to address the root cause of why kubectl connections are dropping.
