# LocalPort - Requirements Document

## Project Purpose

LocalPort is a universal port forwarding manager that provides reliable, automated port forwarding with health monitoring and auto-restart capabilities for development environments. Initially it supports only
kubectl port forwarding.

## What LocalPort Needs to Do

### 1. Managing Port Forwards

**Service Configuration**
- Users define their port forwarding services in a YAML configuration file
- Each service specifies which technology to use (kubectl, SSH, etc.), along with local port, remote port, and connection details
- Services can be organized into groups for easy batch operations (like "essential" or "messaging")
- Configuration gets validated before any forwards start to catch errors early

**Supporting Multiple Technologies**
- kubectl port-forward works as the primary method for Kubernetes services
- SSH tunneling provides an alternative for non-Kubernetes services
- The architecture supports adding new forwarding methods without changing existing code
- Each forwarding method plugs in as a separate adapter

**Handling Kafka's Complexity**
- Kafka advertised listeners require special handling - when Kafka tells clients to connect to `localhost:6092` but the actual service runs on port `9092`, LocalPort forwards `6092:9092`
- Health checks validate connectivity using the advertised port (what clients actually use)
- This ensures Kafka clients can connect properly without manual port juggling

### 2. Keeping Things Running

**Process Monitoring**
- LocalPort continuously watches all active port forwarding processes
- It detects when processes die unexpectedly (network issues, kubectl crashes, etc.)
- Process health gets tracked through both PID monitoring and actual connection testing

**Automatic Recovery**
- Failed port forwards restart automatically without user intervention
- Repeated failures trigger exponential backoff to avoid hammering broken services
- Restart attempts have limits to prevent infinite loops
- All restart events get logged with timestamps and failure reasons

**Health Monitoring**
- Periodic health checks verify that forwarded services are actually reachable
- Different check types support various scenarios: TCP connectivity, HTTP endpoints, Kafka bootstrap validation, PostgreSQL connections
- Consistently failing health checks trigger forward restarts
- Check intervals and failure thresholds can be configured per service

### 3. User Experience

**Command Line Interface**
- Modern CLI with rich formatting, colors, and clear output
- Start/stop individual services: `localport start postgres kafka`
- Work with service groups: `localport start --group essential`
- View status in formatted tables or JSON for scripting
- All common operations work with single, memorable commands

**Background Operation**
- Daemon mode runs LocalPort in the background, handling monitoring and restarts automatically
- Users can check status and control the daemon while it runs
- State persists across daemon restarts when possible
- Clean shutdown ensures all forwards terminate properly

**Logging and Visibility**
- Comprehensive logging captures all operations and decisions
- Users can view logs for specific services or time ranges
- Configurable log levels (DEBUG, INFO, WARN, ERROR) control verbosity
- Log rotation prevents disk space issues during long-running operations

### 4. Configuration

**Loading Configuration**
- YAML files provide the primary configuration method
- LocalPort searches standard locations automatically (current directory, user config directory, home directory)
- Custom configuration file paths can be specified via command line
- Configuration syntax and semantics get validated before use

**Service Definitions**
- Each service specifies its name, forwarding technology, connection details, and port mapping
- Optional health check configuration allows service-specific monitoring
- Resilience settings control restart behavior and failure thresholds
- Descriptive metadata (tags, descriptions) helps organize and document services

**Environment Integration**
- Environment variable substitution works in configuration files
- Existing kubectl contexts and SSH configurations are respected
- LocalPort integrates smoothly with standard development workflows

### 5. Handling Problems

**Graceful Error Handling**
- Network connectivity issues are handled gracefully without crashing
- Clear, actionable error messages help users understand and fix problems
- Individual forward failures don't affect other running forwards
- Proper resource cleanup happens during shutdown

**Port Conflicts**
- LocalPort detects when local ports are already in use
- Clear error messages identify port conflicts
- Alternative port suggestions help resolve conflicts quickly
- Port availability gets checked before starting forwards

**Service Availability**
- Missing or unavailable target services are handled appropriately
- Connection retries use appropriate backoff when services are starting up
- Temporary failures (service restarting) are distinguished from permanent ones (service deleted)

### 6. Installation and Compatibility

**Easy Installation**
- pipx installation provides isolated Python environments
- Modern Python packaging standards (pyproject.toml) ensure compatibility
- Python 3.13+ requirement leverages latest language features
- Dependencies are managed appropriately for different use cases

**Cross-Platform Support**
- Works on Linux, macOS, and Windows
- Process management adapts to platform-specific requirements
- File paths and configuration locations follow platform conventions

## Behavioral Scenarios

### Scenario 1: Basic Port Forward Lifecycle
1. User defines services in YAML configuration
2. User runs `localport start postgres kafka`
3. System validates configuration and checks port availability
4. System starts kubectl port-forward processes for specified services
5. System monitors processes and reports success/failure
6. User can query status and see active forwards
7. User runs `localport stop --all` to cleanly shut down

### Scenario 2: Auto-Restart on Failure
1. System has active port forwards running
2. Network connectivity is lost temporarily
3. kubectl processes terminate
4. System detects process termination within monitoring interval
5. System waits for restart delay, then attempts restart
6. System successfully re-establishes forwards when connectivity returns
7. System logs the failure and recovery events

### Scenario 3: Kafka Advertised Listener Handling
1. User configures Kafka service with `local_port: 6092` and `remote_port: 9092`
2. System starts port forward `6092:9092` to Kafka service
3. Kafka client connects to `localhost:6092` as advertised
4. System health check validates Kafka bootstrap connectivity on port 6092
5. Forward remains stable and handles Kafka protocol correctly

### Scenario 4: Daemon Mode Operation
1. User starts daemon with `localport daemon start`
2. Daemon loads configuration and starts all enabled services
3. Daemon runs in background, monitoring and restarting as needed
4. User can check status with `localport status` while daemon runs
5. User stops daemon with `localport daemon stop`
6. All forwards are cleanly terminated

## Success Criteria

- Port forwards remain stable during normal development work (8+ hours uptime)
- Failed forwards restart automatically within 30 seconds
- Kafka clients can connect reliably through advertised listener ports
- Configuration changes can be applied without manual process management
- System provides clear feedback on all operations and errors
- Installation and setup can be completed in under 5 minutes

## Non-Functional Requirements

- **Performance**: System overhead should be minimal (< 50MB memory, < 5% CPU when idle)
- **Reliability**: Auto-restart should succeed > 95% of the time for transient failures
- **Usability**: Common operations should require single commands with clear output
- **Maintainability**: Code should follow hexagonal architecture for easy extension
- **Security**: System should not store or log sensitive credentials
