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
