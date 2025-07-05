# LocalPort v0.3.6: Cluster Health Monitor

## Feature Overview

**Intelligent Cluster Keepalive & Health Monitoring**

A new cluster-level health monitoring system that combines keepalive functionality, cluster intelligence gathering, and proactive service management. This feature addresses Mac idle-state connection issues while providing valuable cluster insights for better service management.

### Key Benefits
- **Prevents idle-state connection drops** (primary goal for Mac users)
- **Provides cluster intelligence** for smarter service management decisions
- **Scales efficiently** (one monitor per cluster, not per service)
- **Reduces service restart frequency** through proactive cluster monitoring
- **Enhances troubleshooting** with cluster-level diagnostic information

## Technical Architecture

### Core Components

#### 1. Cluster Health Monitor (`ClusterHealthMonitor`)
- **Location**: `src/localport/infrastructure/cluster_monitoring/`
- **Purpose**: Manages health monitoring for individual cluster contexts
- **Responsibilities**:
  - Execute periodic cluster health checks
  - Collect and cache cluster statistics
  - Provide abstract interface for cluster state queries
  - Handle cluster connectivity failures

#### 2. Cluster Health Manager (`ClusterHealthManager`)
- **Location**: `src/localport/application/services/`
- **Purpose**: Orchestrates cluster monitors across all active contexts
- **Responsibilities**:
  - Create/destroy cluster monitors based on active services
  - Route cluster health queries to appropriate monitors
  - Coordinate with existing health monitoring system
  - Manage cluster monitor lifecycle

#### 3. Cluster Health Provider Interface (`ClusterHealthProvider`)
- **Location**: `src/localport/domain/services/`
- **Purpose**: Abstract interface for cluster health queries
- **Methods**:
  ```python
  def is_cluster_healthy(self, context: str) -> bool
  def get_pod_status(self, context: str, namespace: str, resource_name: str) -> ResourceStatus
  def get_cluster_info(self, context: str) -> ClusterInfo
  def get_last_check_time(self, context: str) -> datetime
  def get_cluster_events(self, context: str, since: datetime) -> List[ClusterEvent]
  ```

#### 4. Data Models
- **Location**: `src/localport/domain/entities/`
- **New Entities**:
  - `ClusterInfo`: Basic cluster connectivity and version info
  - `ResourceStatus`: Pod/service status information
  - `ClusterEvent`: Recent cluster events
  - `ClusterHealth`: Overall cluster health state

### Data Collection Strategy

#### Primary Commands (4-minute interval)
1. **`kubectl cluster-info`**
   - Purpose: Basic connectivity + cluster health
   - Data: API server status, cluster version, core services

2. **`kubectl get pods -A --field-selector=status.phase!=Succeeded`**
   - Purpose: Active pod status across all namespaces
   - Data: Pod states, recent changes, failures
   - Filtered to exclude completed jobs

3. **`kubectl get nodes --no-headers`**
   - Purpose: Node health and capacity
   - Data: Node status, resource availability

#### Secondary Commands (triggered by events)
4. **`kubectl get events --sort-by='.lastTimestamp' --limit=50`**
   - Purpose: Recent cluster activity
   - Triggered: On cluster health changes or service failures

5. **`kubectl describe pod <specific-pod>`**
   - Purpose: Detailed pod diagnostics
   - Triggered: When service-specific pod issues detected

### Integration Points

#### With Health Monitoring System
- Cluster health failures trigger faster service health checks
- Service health checks can query cluster state before making restart decisions
- Cluster events inform service restart strategies

#### With Service Manager
- Pod status queries before service restart attempts
- Cluster health consideration in service start/stop decisions
- Intelligent error handling based on cluster state

#### With Restart Manager
- Cluster-aware restart policies
- Avoid restarts during cluster-wide issues
- Prioritize restarts based on cluster resource availability

## Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] **Create cluster monitoring directory structure**
  - [ ] `src/localport/infrastructure/cluster_monitoring/`
  - [ ] `src/localport/infrastructure/cluster_monitoring/__init__.py`
  - [ ] `src/localport/infrastructure/cluster_monitoring/cluster_health_monitor.py`
  - [ ] `src/localport/infrastructure/cluster_monitoring/kubectl_client.py`

- [ ] **Define domain entities**
  - [ ] `src/localport/domain/entities/cluster_info.py`
  - [ ] `src/localport/domain/entities/resource_status.py`
  - [ ] `src/localport/domain/entities/cluster_event.py`
  - [ ] `src/localport/domain/entities/cluster_health.py`

- [ ] **Create abstract interfaces**
  - [ ] `src/localport/domain/services/cluster_health_provider.py`
  - [ ] Update `src/localport/domain/services/__init__.py`

### Phase 2: Core Implementation
- [ ] **Implement ClusterHealthMonitor**
  - [ ] Basic kubectl command execution
  - [ ] Async health check loop (4-minute interval)
  - [ ] Data parsing and caching
  - [ ] Error handling and retry logic
  - [ ] Logging and metrics

- [ ] **Implement ClusterHealthManager**
  - [ ] Service registration/deregistration
  - [ ] Monitor lifecycle management
  - [ ] Context-based routing
  - [ ] Integration with existing health system

- [ ] **Create kubectl client wrapper**
  - [ ] Command execution with proper error handling
  - [ ] Context-aware command building
  - [ ] Output parsing utilities
  - [ ] Timeout and retry mechanisms

### Phase 3: Configuration System
- [ ] **Extend configuration schema**
  - [ ] Add cluster health monitoring section to YAML schema
  - [ ] Default configuration values
  - [ ] Per-cluster configuration overrides
  - [ ] Backward compatibility

- [ ] **Configuration structure**
  ```yaml
  defaults:
    cluster_health:
      enabled: true
      interval: 240  # 4 minutes
      timeout: 30    # 30 seconds per command
      retry_attempts: 2
      commands:
        cluster_info: true
        pod_status: true
        node_status: true
        events_on_failure: true
  ```

- [ ] **Update configuration validation**
  - [ ] Schema validation for new cluster health section
  - [ ] Sensible defaults and bounds checking
  - [ ] Migration from older config versions

### Phase 4: Integration with Existing Systems
- [ ] **Health Monitor Integration**
  - [ ] Modify `HealthMonitorScheduler` to include cluster monitors
  - [ ] Update health check logic to consider cluster state
  - [ ] Add cluster health to overall system health calculation

- [ ] **Service Manager Integration**
  - [ ] Add cluster health queries to service start/stop logic
  - [ ] Implement cluster-aware error handling
  - [ ] Pod status checking before service operations

- [ ] **Restart Manager Integration**
  - [ ] Cluster-aware restart policies
  - [ ] Delay restarts during cluster issues
  - [ ] Prioritize restarts based on cluster health

### Phase 5: CLI and User Interface
- [ ] **Extend status command**
  - [ ] Add cluster health section to `localport status`
  - [ ] Show cluster connectivity and basic stats
  - [ ] Color-coded cluster health indicators

- [ ] **New cluster command**
  - [ ] `localport cluster status` - detailed cluster information
  - [ ] `localport cluster events` - recent cluster events
  - [ ] `localport cluster pods` - pod status for active services

- [ ] **Enhanced logging**
  - [ ] Cluster health events in daemon logs
  - [ ] Cluster-specific log filtering
  - [ ] Integration with existing log commands

### Phase 6: Testing Strategy
- [ ] **Unit Tests**
  - [ ] `tests/unit/infrastructure/test_cluster_health_monitor.py`
  - [ ] `tests/unit/application/test_cluster_health_manager.py`
  - [ ] Mock kubectl command execution
  - [ ] Test data parsing and error handling

- [ ] **Integration Tests**
  - [ ] `tests/integration/test_cluster_monitoring.py`
  - [ ] Test with real kubectl commands (optional)
  - [ ] Test cluster monitor lifecycle
  - [ ] Test integration with health monitoring

- [ ] **End-to-End Tests**
  - [ ] Test Mac idle-state scenario
  - [ ] Test cluster failure scenarios
  - [ ] Test service restart behavior with cluster monitoring

### Phase 7: Documentation
- [ ] **User Documentation**
  - [ ] Update `docs/configuration.md` with cluster health settings
  - [ ] Update `docs/troubleshooting.md` with cluster health diagnostics
  - [ ] Add cluster monitoring section to `docs/getting-started.md`

- [ ] **Developer Documentation**
  - [ ] Architecture documentation for cluster monitoring
  - [ ] API documentation for ClusterHealthProvider
  - [ ] Integration guide for new cluster health features

- [ ] **CLI Reference**
  - [ ] Update `docs/cli-reference.md` with new cluster commands
  - [ ] Document new status output format
  - [ ] Add examples of cluster health usage

## Configuration Design

### Default Configuration
```yaml
version: "1.0"

defaults:
  cluster_health:
    enabled: true
    interval: 240  # 4 minutes
    timeout: 30    # 30 seconds per kubectl command
    retry_attempts: 2
    failure_threshold: 3  # Consecutive failures before marking cluster unhealthy
    
    # Commands to execute
    commands:
      cluster_info:
        enabled: true
        command: ["kubectl", "cluster-info", "--request-timeout=30s"]
      
      pod_status:
        enabled: true
        command: ["kubectl", "get", "pods", "-A", "--field-selector=status.phase!=Succeeded", "--no-headers"]
        
      node_status:
        enabled: true
        command: ["kubectl", "get", "nodes", "--no-headers"]
        
      events_on_failure:
        enabled: true
        command: ["kubectl", "get", "events", "--sort-by=.lastTimestamp", "--limit=50"]

  # Enhanced health check defaults
  health_check:
    type: tcp
    interval: 30
    timeout: 5.0
    failure_threshold: 3
    cluster_aware: true  # NEW: Consider cluster health in service health decisions

services:
  - name: postgres-dev
    # ... existing config ...
    cluster_health:
      # Optional per-service cluster health overrides
      monitor_pod: true  # Monitor specific pod for this service
      pod_selector: "app=postgres"
```

### Per-Cluster Overrides
```yaml
cluster_contexts:
  dev-hybrid-us-east-1:
    cluster_health:
      interval: 180  # More frequent for critical cluster
      commands:
        events_on_failure:
          enabled: true
          command: ["kubectl", "get", "events", "--namespace=postgres", "--limit=20"]
```

## CLI Integration

### Enhanced Status Output

The `localport status` command will be extended to include a new "Cluster Health" section that displays:

- **Cluster context names** (e.g., "dev-hybrid-us-east-1")
- **Cluster connectivity status** (Healthy/Unhealthy with color indicators)
- **Last check timestamp** and time since last successful check
- **Basic cluster statistics** (node count, active pod count, recent events count)
- **Color-coded health indicators** (🟢 green for healthy, 🔴 red for unhealthy, 🟡 yellow for warning)

### New Cluster Commands

Add a new `localport cluster` command group with subcommands:

- **`localport cluster status`** - Show detailed cluster information for all active contexts
  - Cluster version and API server status
  - Node health and resource availability
  - Pod status summary for services
  - Recent cluster events

- **`localport cluster events`** - Display recent cluster events that might affect services
  - Filterable by time range and event type
  - Highlights events related to active services
  - Shows event timestamps and descriptions

- **`localport cluster pods`** - Show pod status for resources used by active services
  - Pod health and restart counts
  - Resource usage and limits
  - Pod events and status changes

### Enhanced Logging Integration

- **Cluster health events** appear in daemon logs with appropriate log levels
- **Cluster-specific log filtering** options in `localport logs` command
- **Integration with existing log commands** to correlate service and cluster events

## Expected Outcomes

### Primary Goals Achievement

1. **Mac Idle-State Connection Stability**
   - Services remain stable during lunch breaks and overnight periods
   - Reduction in "lost connection to pod" errors by 90%+
   - Fewer service restart cycles during inactivity

2. **Improved Service Reliability**
   - 50% reduction in unnecessary service restarts
   - Faster detection of cluster-wide issues vs service-specific problems
   - More intelligent restart decisions based on cluster state

3. **Enhanced Troubleshooting**
   - Clear visibility into cluster health alongside service health
   - Correlation between cluster events and service failures
   - Proactive identification of cluster issues before they affect services

### Performance Improvements

- **Reduced Resource Usage**: Fewer kubectl processes due to shared cluster monitoring
- **Faster Issue Resolution**: Cluster context helps identify root causes quickly
- **Better User Experience**: Less frequent service interruptions and faster recovery

### Operational Benefits

- **Proactive Monitoring**: Issues detected before they cause service failures
- **Intelligent Automation**: Cluster-aware restart policies prevent futile restart attempts
- **Better Diagnostics**: Rich cluster information for troubleshooting

## Risk Assessment & Mitigation

### Technical Risks

1. **kubectl Command Overhead**
   - **Risk**: Additional kubectl commands may impact system performance
   - **Mitigation**: 4-minute intervals, efficient command selection, caching results
   - **Monitoring**: Track command execution time and system resource usage

2. **Cluster Permission Requirements**
   - **Risk**: Users may not have sufficient cluster permissions for all commands
   - **Mitigation**: Graceful degradation, configurable command sets, clear error messages
   - **Fallback**: Disable specific commands that fail due to permissions

3. **Network Connectivity Issues**
   - **Risk**: Cluster monitoring may fail during network issues
   - **Mitigation**: Retry logic, exponential backoff, offline mode detection
   - **Recovery**: Automatic resumption when connectivity is restored

### Operational Risks

1. **Configuration Complexity**
   - **Risk**: Additional configuration options may confuse users
   - **Mitigation**: Sensible defaults, clear documentation, optional features
   - **Support**: Configuration validation and helpful error messages

2. **Backward Compatibility**
   - **Risk**: Changes may break existing configurations
   - **Mitigation**: Gradual rollout, configuration migration, version detection
   - **Testing**: Comprehensive testing with existing configurations

### Mitigation Strategies

- **Feature Flags**: Cluster health monitoring can be disabled if issues arise
- **Graceful Degradation**: System continues to work if cluster monitoring fails
- **Comprehensive Testing**: Extensive testing across different cluster types and configurations
- **Documentation**: Clear troubleshooting guides and configuration examples

## Success Metrics

### Quantitative Metrics

1. **Connection Stability**
   - Target: 95% reduction in idle-state connection failures
   - Measurement: Count of "lost connection to pod" errors over time
   - Baseline: Current failure frequency during inactivity periods

2. **Service Uptime**
   - Target: 99%+ service availability during normal cluster operations
   - Measurement: Service uptime percentage over 24-hour periods
   - Improvement: Reduction in unnecessary restarts by 50%

3. **Issue Detection Time**
   - Target: Cluster issues detected within 4 minutes (one monitoring cycle)
   - Measurement: Time between cluster problem occurrence and detection
   - Benefit: Faster response to cluster-wide issues

4. **Resource Efficiency**
   - Target: No more than 5% increase in system resource usage
   - Measurement: CPU and memory usage of LocalPort daemon
   - Optimization: Shared monitoring reduces per-service overhead

### Qualitative Metrics

1. **User Experience**
   - Fewer support requests related to connection stability
   - Positive feedback on improved reliability
   - Reduced frustration with service interruptions

2. **Troubleshooting Effectiveness**
   - Faster issue resolution times
   - Better correlation between symptoms and root causes
   - More actionable diagnostic information

3. **Operational Confidence**
   - Increased trust in LocalPort for production-like environments
   - Better visibility into system health
   - Proactive issue identification

## Timeline Estimates

### Development Phases

**Phase 1: Core Infrastructure (Week 1-2)**
- Domain entities and interfaces: 3 days
- Basic cluster monitoring implementation: 5 days
- Initial kubectl client wrapper: 2 days

**Phase 2: Core Implementation (Week 3-4)**
- ClusterHealthMonitor with async loops: 4 days
- ClusterHealthManager with lifecycle management: 3 days
- Integration with existing health system: 3 days

**Phase 3: Configuration & Integration (Week 5-6)**
- Configuration schema and validation: 3 days
- Service Manager integration: 2 days
- Restart Manager integration: 2 days
- Health Monitor integration: 3 days

**Phase 4: CLI & User Interface (Week 7)**
- Enhanced status command: 2 days
- New cluster commands: 3 days
- Logging integration: 2 days

**Phase 5: Testing & Documentation (Week 8-9)**
- Unit and integration tests: 5 days
- End-to-end testing: 3 days
- Documentation updates: 2 days

**Phase 6: Polish & Release (Week 10)**
- Bug fixes and refinements: 3 days
- Performance optimization: 2 days
- Release preparation: 2 days

### Total Estimated Timeline: 10 weeks

## Dependencies

### External Dependencies

1. **kubectl Availability**
   - Requirement: kubectl must be installed and configured
   - Impact: Core functionality depends on kubectl access
   - Mitigation: Clear error messages and setup documentation

2. **Cluster Permissions**
   - Requirement: Read access to pods, nodes, events across namespaces
   - Impact: Some features may be limited without sufficient permissions
   - Mitigation: Graceful degradation and permission checking

3. **Network Connectivity**
   - Requirement: Stable network connection to Kubernetes clusters
   - Impact: Monitoring effectiveness depends on network reliability
   - Mitigation: Retry logic and offline detection

### Internal Dependencies

1. **Existing Health Monitoring System**
   - Integration point: Must work alongside current health checks
   - Risk: Changes to health system may affect cluster monitoring
   - Coordination: Close collaboration with health monitoring changes

2. **Configuration System**
   - Dependency: Configuration schema and validation framework
   - Impact: New configuration options must integrate cleanly
   - Requirement: Backward compatibility with existing configurations

3. **CLI Framework**
   - Dependency: Rich CLI utilities and formatting system
   - Integration: New commands must follow existing patterns
   - Consistency: Maintain consistent user experience

### Development Dependencies

1. **Testing Infrastructure**
   - Requirement: Mock kubectl commands for unit testing
   - Need: Test clusters for integration testing
   - Setup: CI/CD pipeline updates for new test requirements

2. **Documentation System**
   - Updates needed: CLI reference, configuration docs, troubleshooting guides
   - Maintenance: Keep documentation in sync with implementation
   - Examples: Provide clear configuration examples and use cases

This comprehensive plan provides a roadmap for implementing the Cluster Health Monitor feature in LocalPort v0.3.6, addressing the Mac idle-state connection issues while providing valuable cluster intelligence for all users.
