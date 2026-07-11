# Design Decisions

## Service Management Redesign (2025-01-03)

### Problem
The service manager was auto-adopting external processes that weren't declared in the configuration, leading to confusion where services with names like "postgres-primary" and "postgres-readonly" would appear even when the configuration declared different service names like "uhes-postgres-dev" and "kafka-dev".

### Root Cause
The `get_service_status()` method was automatically "re-tracking" any kubectl processes it found running on the same ports, regardless of whether they were started by LocalPort or declared in the configuration.

### Solution
Implemented a strict three-category process management system:

#### Category A: Managed Processes
- In state file + in current config + process matches exactly
- These are fully managed (start/stop/restart/monitor)

#### Category B: Orphaned LocalPort Processes
- In state file + NOT in current config + process matches exactly
- These were started by LocalPort but removed from config
- LocalPort offers to clean these up (since we started them)

#### Category C: External Processes
- NOT in state file (regardless of whether they look like port forwards)
- LocalPort has no authority over these
- Simply report port conflicts and refuse to start

### Key Changes
1. **Removed auto-adoption logic** from `get_service_status()`
2. **Enhanced port conflict detection** with detailed error messages
3. **Added orphaned process detection** as separate functionality
4. **Strict state file authority** - only manage what we explicitly started
5. **Conservative approach** - never interfere with external processes

### Benefits
- Predictable behavior - only manages declared services
- Clear error messages for port conflicts
- No risk of interfering with user's other processes
- Proper separation of concerns between managed, orphaned, and external processes

### Implementation Details
- Modified `ServiceManager._is_port_available()` to provide detailed conflict information
- Removed auto-tracking logic from `get_service_status()`
- Added `detect_orphaned_processes()` method for cleanup operations
- Enhanced error messages to clearly distinguish between conflict types

## Deterministic Service Identity System (2025-07-03)

### Problem
Service IDs were generated using random UUIDs (`uuid4()`), causing state persistence to break across LocalPort restarts. When LocalPort reloaded configuration, it would generate new random IDs that didn't match the IDs in the state file, making running processes appear as "Stopped" even though they were actively running.

### Root Cause
The `Service.create()` method used `uuid4()` to generate a new random UUID each time, meaning:
- Same service configuration → Different IDs each time loaded
- State file contains processes with old random IDs
- Current configuration generates new random IDs
- No way to match running processes to current configuration

### Solution
Implemented deterministic service ID generation based on service configuration properties:

#### Service ID Generation Algorithm
```python
def generate_deterministic_id(name, technology, local_port, remote_port, connection_info) -> UUID:
    # Build stable config key from essential service properties
    config_key = f"{name}:{technology}:{local_port}:{remote_port}"
    
    # Add connection-specific details
    if technology == 'kubectl':
        config_key += f":{namespace}:{resource_name}:{resource_type}"
        if context: config_key += f":{context}"
    elif technology == 'ssh':
        config_key += f":{host}:{port}"
        if user: config_key += f":{user}"
    
    # Generate deterministic UUID using UUID5
    return uuid5(NAMESPACE_DNS, config_key)
```

#### What Service ID Identifies
- **Service Configuration**: A unique service declaration (name, ports, connection)
- **NOT Process Instance**: Runtime details like PID, start time, status

#### ID Stability Rules
**ID stays same when**:
- Configuration reloaded
- LocalPort restarted  
- Process restarted/failed

**ID changes when**:
- Service name changes
- Port configuration changes
- Connection details change (namespace, resource, host, etc.)

### Benefits
- **State Persistence**: Same service config always gets same ID
- **Process Tracking**: Can match running processes to current configuration
- **Restart Resilience**: Service identity survives LocalPort restarts
- **Configuration Changes**: Different configs get different IDs appropriately

### Migration Strategy
- Detect old-format state files with random UUIDs
- Match orphaned processes to current config by port/command validation
- Clean up unmatched processes safely
- Preserve user's running services during transition

### Implementation Details
- Modified `Service.create()` to use deterministic ID generation
- Added UUID5-based generation with stable namespace
- Implemented state migration logic for backward compatibility
- Added comprehensive tests for ID determinism and collision prevention


## Health Check Interface Standardization (2025-07-04)

### Problem
The health check system had inconsistent object-oriented design causing daemon restart loops and maintenance issues:

1. **Inconsistent Interface Contract**:
   - `TCPHealthCheck`: Has both `check()` and `check_with_config()` methods, returns `HealthCheckResult`
   - `HTTPHealthCheck`: Only has `check()` method, returns `bool`
   - Factory Protocol: Defines `check(**kwargs) -> bool` but implementations don't match

2. **Mixed Return Types**:
   - Some health checkers return `bool`
   - Others return `HealthCheckResult`
   - Scheduler needs conditional logic to handle both

3. **Inconsistent Constructor Patterns**:
   - `TCPHealthCheck`: `__init__()` takes no parameters
   - `HTTPHealthCheck`: `__init__(config: dict)` requires config
   - Factory fails when trying to create all with uniform pattern

4. **Violation of Liskov Substitution Principle**:
   - Health checkers can't be used interchangeably
   - Scheduler needs type-specific conditional logic

### Root Cause
The health check implementations evolved independently without a common abstract interface, leading to:
- Health check failures due to method signature mismatches
- Continuous service restarts (32+ failures observed)
- Complex, error-prone scheduler logic with type-specific branches
- Difficult maintenance and extension

### Solution
Implemented a standardized abstract interface that all health checkers must implement:

#### Abstract Health Checker Interface
```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class HealthChecker(ABC):
    """Abstract base class for all health checkers."""
    
    @abstractmethod
    async def check_health(self, config: Dict[str, Any]) -> HealthCheckResult:
        """Perform health check with given configuration."""
        pass
    
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration for this health checker."""
        pass
    
    @abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for this health checker."""
        pass
```

#### Design Principles
1. **Uniform Interface**: Single `check_health(config)` method for all implementations
2. **Consistent Return Type**: All health checkers return `HealthCheckResult`
3. **Configuration-Driven**: All configuration passed at check time, not constructor
4. **Polymorphic Usage**: All health checkers interchangeable via common interface
5. **Validation Separation**: Configuration validation separate from execution

### Benefits
- **Eliminates Restart Loops**: Consistent interface prevents method signature errors
- **Simplified Scheduler**: No more type-specific conditional logic
- **Better Maintainability**: Clear contract for all health checker implementations
- **Easy Extension**: New health checkers follow standard pattern
- **Polymorphic Design**: True object-oriented substitutability

### Implementation Strategy
1. **Create Abstract Base Class** with standardized interface
2. **Refactor Existing Health Checkers** to implement the interface uniformly
3. **Update Factory** to use consistent creation pattern
4. **Simplify Scheduler** to use polymorphic calls only
5. **Add Configuration Validation** at factory level

### Scheduler Simplification
Before (type-specific logic):
```python
if check_type == 'tcp':
    health_result = await health_checker.check_with_config(check_config)
    is_healthy = health_result.is_healthy
elif check_type == 'http':
    is_healthy = await health_checker.check(url=url, timeout=timeout)
# ... more type-specific branches
```

After (polymorphic):
```python
result = await health_checker.check_health(merged_config)
is_healthy = result.status == HealthCheckStatus.HEALTHY
```

### Implementation Details
- Created `HealthChecker` abstract base class with uniform interface
- Refactored all health checker implementations to inherit from base class
- Updated factory to create instances uniformly without constructor dependencies
- Simplified health monitor scheduler to use polymorphic method calls
- Added comprehensive configuration validation at factory level

## GitHub Actions Deprecation Fix (2025-07-03)

### Problem
GitHub Actions workflow was using deprecated actions that were generating warnings:
- `actions/create-release@v1` - deprecated and no longer maintained
- `actions/upload-release-asset@v1` - deprecated and no longer maintained

### Root Cause
These actions were deprecated because GitHub recommends using the GitHub CLI (`gh`) or REST API directly for better reliability and maintenance.

### Solution
Replaced deprecated actions with modern GitHub CLI commands:

#### Changes Made
1. **Replaced `actions/create-release@v1`** with `gh release create` command
   - Maintains all functionality (title, notes, prerelease detection)
   - Uses `--prerelease` flag for alpha/beta/rc versions
   - Uses `--notes-file` for changelog content

2. **Replaced `actions/upload-release-asset@v1`** with `gh release upload` command
   - Uploads assets directly to existing release
   - Maintains platform-specific asset naming
   - Preserves conditional logic for different file types

3. **Updated job outputs** to use tag_name instead of deprecated upload_url

### Benefits
- **No deprecation warnings** in GitHub Actions
- **Better error handling** and debugging with GitHub CLI
- **More maintainable** - follows current GitHub best practices
- **Same functionality** - all existing features preserved
- **Future-proof** - GitHub CLI is actively maintained

### Implementation Details
- Modified `.github/workflows/release.yml`
- Preserved all existing conditional logic and matrix strategies
- Maintained backward compatibility with existing release process
- No changes required to secrets or repository configuration

## Enhanced Logging for Daemon and Health Monitoring System (2025-07-06)

### Problem
The recent health monitoring bug was difficult to debug because the complex interactions between the daemon manager, service manager, and health monitor weren't well logged. The issue was hidden because each component appeared to be working individually, but their integration was broken.

### Root Cause
**Insufficient Logging Visibility**: The handoffs between components and decision-making processes lacked comprehensive logging, making it difficult to trace:
- Service status transitions between components
- Component integration points and data flow
- Health monitor decision making (why services are included/excluded)
- Service lifecycle events and state synchronization

### Solution
Implemented comprehensive logging enhancements across the daemon and health monitoring system:

#### 1. Enhanced Daemon Manager Logging (`_start_health_monitoring`)
- **Step-by-step process logging**: Each phase of health monitoring startup is clearly logged
- **Service status synchronization tracking**: Detailed logging of status changes during sync
- **Service eligibility evaluation**: Clear logging of which services will be monitored and why
- **Integration point logging**: Handoffs between service manager and health monitor

#### 2. Enhanced Health Monitor Scheduler Logging
- **Service analysis logging**: Detailed evaluation of each service for monitoring eligibility
- **Health check execution logging**: Comprehensive logging of health check process
- **Decision making transparency**: Clear logging of why services are monitored or skipped
- **Configuration and timing details**: Health check types, intervals, and configurations

#### 3. Enhanced Service Manager Logging
- **Service status queries**: Logging when service status is requested and what's returned
- **Process lifecycle tracking**: Better visibility into service start/stop operations
- **State transitions**: Clear logging of service status changes

### Key Logging Improvements

#### Service Status Synchronization
```
INFO: Starting health monitoring subsystem
INFO: Loaded services from repository (total_services=4, service_names=[...])
INFO: Initial service states from configuration:
INFO:   Service configuration state (service_name=X, config_status=STOPPED, has_health_check=true)
INFO: Synchronizing service statuses with service manager
INFO: Service status synchronization completed (status_changes=4, changes=[...])
```

#### Health Monitor Decision Making
```
INFO: Evaluating services for health monitoring eligibility:
INFO:   ✓ Service eligible for monitoring (service_name=X, will_monitor=true, health_check_type=tcp)
INFO:   ⊘ Service skipped - not running (service_name=Y, will_monitor=false, status=STOPPED)
INFO: Health monitoring startup complete (active_monitors=4, monitored_services=[...])
```

#### Health Check Execution
```
INFO: Starting health check (service_name=X, check_type=tcp, timeout=5.0, local_port=6432)
INFO: Executing health check (service_name=X, check_type=tcp, check_config={...})
INFO: Health check completed (service_name=X, is_healthy=true, response_time=0.001)
INFO: Health check result created (service_name=X, final_is_healthy=true)
```

### Benefits
- **Faster Debugging**: Complex integration issues are now immediately visible in logs
- **Clear Decision Tracking**: Every decision point is logged with context and reasoning
- **Component Integration Visibility**: Handoffs between components are clearly tracked
- **Service Lifecycle Transparency**: Service status changes and synchronization are fully logged
- **Health Check Transparency**: Complete visibility into health check execution and results

### Implementation Details
- Enhanced `DaemonManager._start_health_monitoring()` with step-by-step logging
- Added comprehensive service analysis logging in `HealthMonitorScheduler.start_monitoring()`
- Enhanced health check execution logging in `HealthMonitorScheduler._perform_health_check()`
- Added service status query logging in `ServiceManager.get_service_status()`
- Used structured logging with consistent field names and detailed context

### Verification
The enhanced logging successfully provides:
- ✅ Clear visibility into service status synchronization process
- ✅ Detailed health monitor decision making and service eligibility
- ✅ Comprehensive health check execution tracking
- ✅ Component integration and handoff transparency
- ✅ Service lifecycle and state transition logging

This logging enhancement ensures that future debugging of daemon and health monitoring issues will be significantly faster and more effective.

## Health Monitoring Service Status Synchronization Fix (2025-07-06)

### Problem
Health monitoring was not working in the daemon despite the health monitoring system being fully functional. Services showed "✓ Healthy" in status output but no actual health checks were executing.

### Root Cause
**Service Status Synchronization Issue**: The daemon manager was loading services from configuration with default `ServiceStatus.STOPPED` status, but the actual services were running and tracked by the service manager with `ServiceStatus.RUNNING` status. The health monitor only monitors services with `RUNNING` status, so it skipped all services.

**Flow of the Problem**:
1. **Configuration Repository**: Services loaded with `ServiceStatus.STOPPED` (default from YAML)
2. **Service Manager**: Services actually running, tracked separately with `ServiceStatus.RUNNING`
3. **Health Monitor**: Gets services from configuration repository, sees all as `STOPPED`
4. **Health Monitor**: Skips monitoring all services (only monitors `RUNNING` services)
5. **Status Command**: Gets status from service manager, shows "✓ Healthy" (but from service manager, not health monitoring)

### Solution
Added service status synchronization in the daemon manager before starting health monitoring:

```python
# CRITICAL FIX: Synchronize service statuses with service manager
# Services loaded from configuration have default STOPPED status, but may actually be running.
# We need to get the actual status from the service manager before starting health monitoring.
for service in services:
    # Get actual status from service manager and update the service object
    status_info = await self._service_manager.get_service_status(service)
    service.update_status(status_info.status)
```

This ensures that:
1. Services loaded from configuration get their actual runtime status
2. Health monitor sees services with correct `RUNNING` status
3. Health monitoring starts for all running services with health check configurations

### Benefits
- **Health Monitoring Works**: All running services with health check configs are now monitored
- **Accurate Status**: Service objects reflect actual runtime status, not just configuration defaults
- **Proper Integration**: Service manager and health monitor now work together correctly
- **No Breaking Changes**: Existing functionality preserved, just fixed the integration

### Verification
After the fix:
- ✅ Health checks execute on schedule (TCP every 30s, HTTP every 30s)
- ✅ All 4 services show "✓ Healthy" status from actual health monitoring
- ✅ Health check logs appear in daemon logs
- ✅ Both TCP and HTTP health checks working correctly

### Implementation Details
- Modified `DaemonManager._start_health_monitoring()` to synchronize service statuses
- Added service status synchronization before health monitor startup
- Used `ServiceManager.get_service_status()` to get actual runtime status
- Updated service objects with correct status before passing to health monitor
- Maintained backward compatibility with existing service management
