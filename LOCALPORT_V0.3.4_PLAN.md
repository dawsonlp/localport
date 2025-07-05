# LocalPort v0.3.4 Implementation Plan: Enhanced Service Logging

## 🎯 Executive Summary

**Release Goal**: Implement dual-stream logging architecture to enable comprehensive service diagnostics and resolve platform-specific connection stability issues.

**Primary Motivation**: Ubuntu systems show significantly better connection stability than macOS. Current logging sends kubectl/ssh output to `/dev/null`, preventing diagnosis of platform-specific issues.

**Key Deliverable**: Service-specific log files with raw subprocess output, intelligent rotation, and intuitive CLI access.

## 🏗️ Technical Architecture

### Dual-Stream Logging Design

#### Current System (Structured Logs)
- **Format**: JSON structured logs via Python logging
- **Purpose**: Application state, daemon lifecycle, health checks
- **Location**: `~/.local/share/localport/logs/daemon.log`
- **Audience**: Developers, automated monitoring

#### New System (Service Logs)
- **Format**: Raw subprocess output with metadata headers
- **Purpose**: kubectl/ssh diagnostics, connection troubleshooting
- **Location**: `~/.local/share/localport/logs/services/<service_id>.log`
- **Audience**: Users troubleshooting connectivity issues

### Directory Structure
```
~/.local/share/localport/logs/
├── daemon.log                           # Existing structured logs
└── services/                            # New service logs
    ├── uhes-postgres-dev_abc123.log     # Service logs with unique ID
    ├── uhes-postgres-dev_abc123.log.1   # Rotated logs
    ├── kafka-dev_def456.log
    └── keycloak_ghi789.log
```

### Service Log Format
```
=== SERVICE START: uhes-postgres-dev ===
Timestamp: 2025-07-04T18:30:00Z
Service ID: uhes-postgres-dev_abc123
Process ID: 12345
Local Port: 6432
Target: remote:5432
Connection Type: kubectl
Namespace: default
Resource: service/postgres
Platform: macOS 14.2.1
LocalPort Version: 0.3.4
=== KUBECTL OUTPUT BEGINS ===
Forwarding from 127.0.0.1:6432 -> 5432
Forwarding from [::1]:6432 -> 5432
Handling connection for 6432
...
```

## 📋 Implementation Checklist

### Phase 1: Core Infrastructure (Foundation)

#### 1.1 Service Log Management
- [ ] **Create `ServiceLogManager` class**
  - [ ] Location: `src/localport/infrastructure/logging/service_log_manager.py`
  - [ ] Generate unique service IDs (service_name + timestamp hash)
  - [ ] Create service-specific log directories with proper permissions
  - [ ] Write metadata headers on service start
  - [ ] Handle cross-platform path differences

- [ ] **Implement log rotation logic**
  - [ ] Size-based rotation (10MB threshold)
  - [ ] Time-based cleanup (3-day retention)
  - [ ] Atomic file operations for safe rotation
  - [ ] Handle concurrent access with file locking
  - [ ] Graceful handling of disk space issues

- [ ] **Create log directory management**
  - [ ] Ensure `~/.local/share/localport/logs/services/` exists
  - [ ] Handle permission errors gracefully
  - [ ] Cross-platform path resolution
  - [ ] Cleanup orphaned log files

#### 1.2 Process Output Capture
- [ ] **Modify subprocess spawning in adapters**
  - [ ] Replace `/dev/null` redirects with service log files
  - [ ] Maintain real-time output streaming
  - [ ] Handle process termination and cleanup
  - [ ] Ensure no blocking on log writes

- [ ] **Update `kubectl_adapter.py`**
  - [ ] Integrate with ServiceLogManager
  - [ ] Capture kubectl port-forward stdout/stderr
  - [ ] Log connection events, errors, and reconnections
  - [ ] Handle kubectl-specific error patterns

- [ ] **Update `ssh_adapter.py`**
  - [ ] Apply same logging pattern as kubectl
  - [ ] Capture SSH tunnel output and diagnostics
  - [ ] Handle SSH-specific connection issues
  - [ ] Log authentication and key-related errors

#### 1.3 Integration with Existing Systems
- [ ] **Enhance structured logging**
  - [ ] Add service log file references to structured logs
  - [ ] Cross-reference service IDs between systems
  - [ ] Maintain timestamp synchronization
  - [ ] Log service log rotation events

### Phase 2: CLI Integration (User Interface)

#### 2.1 Enhanced Log Commands
- [ ] **Core log access commands**
  - [ ] `localport logs --list` - Show all available service logs with metadata
  - [ ] `localport logs --location` - Show log directory paths
  - [ ] `localport logs <service>` - Show latest service log content
  - [ ] `localport logs <service> --follow` - Stream service logs in real-time
  - [ ] `localport logs <service> --path` - Show log file path for external tools

- [ ] **Advanced log features**
  - [ ] `--tail N` - Show last N lines (default 100)
  - [ ] `--since TIME` - Show logs since timestamp (1h, 30m, 2d formats)
  - [ ] `--all` - Show all rotated files for service
  - [ ] `--grep PATTERN` - Filter log lines by pattern
  - [ ] Service name auto-completion via shell completion
  - [ ] Fuzzy service name matching for user convenience

- [ ] **User guidance features**
  - [ ] Add log access hints to `localport status` output
  - [ ] Include log instructions in error messages
  - [ ] Help text with common log access patterns
  - [ ] Examples in `--help` output

#### 2.2 Status Display Enhancement
- [ ] **Integrate log access into status command**
  - [ ] Show log file status in service details
  - [ ] Display log file sizes and rotation status
  - [ ] Add helpful tips about log access
  - [ ] Include recent error indicators from service logs

- [ ] **Enhanced service information**
  - [ ] Show service ID in status output
  - [ ] Indicate if service logs are available
  - [ ] Display last log activity timestamp
  - [ ] Show log file count for each service

### Phase 3: Testing Strategy

#### 3.1 Unit Tests
- [ ] **ServiceLogManager tests**
  - [ ] Unique ID generation and collision handling
  - [ ] Log rotation logic with various file sizes
  - [ ] File cleanup and retention policy enforcement
  - [ ] Cross-platform path handling (Windows, macOS, Linux)
  - [ ] Concurrent access and file locking

- [ ] **Adapter integration tests**
  - [ ] Mock subprocess output capture
  - [ ] Verify log file creation and content
  - [ ] Test error handling scenarios
  - [ ] Validate metadata header format

- [ ] **CLI command tests**
  - [ ] Test all new log command variations
  - [ ] Verify service name matching and completion
  - [ ] Test output formatting and filtering
  - [ ] Validate error handling for missing services

#### 3.2 Integration Tests
- [ ] **End-to-end service logging**
  - [ ] Start service and verify log file creation
  - [ ] Verify metadata headers are correctly written
  - [ ] Test log rotation with simulated large output
  - [ ] Test cleanup after service stops
  - [ ] Verify structured log cross-references

- [ ] **CLI integration tests**
  - [ ] Test log commands with real service logs
  - [ ] Verify real-time streaming functionality
  - [ ] Test service name auto-completion
  - [ ] Validate log file path resolution

#### 3.3 Manual Testing Protocol
- [ ] **Platform comparison testing**
  - [ ] Start identical services on macOS and Ubuntu
  - [ ] Compare kubectl output patterns and error rates
  - [ ] Document stability differences in service logs
  - [ ] Verify log rotation works consistently across platforms

- [ ] **Connection failure scenarios**
  - [ ] Simulate network interruptions and recovery
  - [ ] Verify comprehensive error capture in service logs
  - [ ] Test kubectl reconnection behavior logging
  - [ ] Document platform-specific error patterns

- [ ] **Long-running stability tests**
  - [ ] Run services for 24+ hours with logging enabled
  - [ ] Verify log rotation occurs correctly
  - [ ] Monitor disk usage and cleanup
  - [ ] Test daemon restart with existing service logs

### Phase 4: Documentation

#### 4.1 User Documentation
- [ ] **Update CLI reference documentation**
  - [ ] Document all new `localport logs` command flags
  - [ ] Add comprehensive examples for common use cases
  - [ ] Include troubleshooting workflows using service logs
  - [ ] Document log file locations and formats

- [ ] **Create troubleshooting guide**
  - [ ] "Diagnosing Connection Issues" section with service logs
  - [ ] Platform-specific troubleshooting tips (macOS vs Ubuntu)
  - [ ] Log analysis examples and common patterns
  - [ ] Integration with external log analysis tools

- [ ] **Update getting started guide**
  - [ ] Include service logging in basic workflows
  - [ ] Add log access to common troubleshooting steps
  - [ ] Document log retention and cleanup behavior

#### 4.2 Developer Documentation
- [ ] **Architecture documentation**
  - [ ] Document dual-stream logging design principles
  - [ ] ServiceLogManager API reference and usage patterns
  - [ ] Integration patterns for new adapters
  - [ ] Cross-platform considerations and best practices

- [ ] **Update design decisions document**
  - [ ] Document logging architecture choices and trade-offs
  - [ ] Explain rotation and retention policy rationale
  - [ ] Cross-reference with existing structured logging
  - [ ] Future extensibility considerations

### Phase 5: Configuration & Polish

#### 5.1 Configuration Options
- [ ] **Add logging configuration to settings**
  - [ ] Configurable retention period (default 3 days)
  - [ ] Configurable rotation size (default 10MB)
  - [ ] Option to disable service logging entirely
  - [ ] Log level configuration for future use
  - [ ] Custom log directory location

#### 5.2 Performance & Reliability
- [ ] **Optimize log writing performance**
  - [ ] Implement buffered writes to reduce I/O overhead
  - [ ] Async log rotation to avoid blocking service operations
  - [ ] Handle disk space exhaustion gracefully
  - [ ] Monitor and limit memory usage for log buffers

- [ ] **Comprehensive error handling**
  - [ ] Graceful degradation if logging fails
  - [ ] Fallback to `/dev/null` if log directory unavailable
  - [ ] User notification of logging issues via structured logs
  - [ ] Recovery mechanisms for corrupted log files

## 🧪 Testing Strategy Details

### Automated Tests (70% coverage)
- **Unit tests**: ServiceLogManager, log rotation logic, CLI commands
- **Integration tests**: Adapter modifications, end-to-end logging workflows
- **Mock tests**: Subprocess output capture without external dependencies
- **Performance tests**: Log writing overhead, rotation efficiency

### Manual Tests (30% coverage)
- **Platform comparison**: Real kubectl/ssh behavior differences
- **Long-running stability**: Multi-hour service logging validation
- **Edge cases**: Network failures, disk space issues, permission problems
- **User experience**: CLI usability and workflow validation

## 📦 Release Criteria for v0.3.4

### Must Have (Release Blockers)
- [ ] Service logs capture kubectl/ssh output correctly
- [ ] Log rotation and cleanup working reliably
- [ ] `localport logs --service <name>` command functional
- [ ] `localport logs --list` shows available service logs
- [ ] No regressions in existing functionality
- [ ] Cross-platform compatibility (macOS, Ubuntu, Windows)

### Should Have (High Priority)
- [ ] Real-time log streaming with `--follow`
- [ ] Service name auto-completion working
- [ ] Cross-platform testing completed successfully
- [ ] Documentation updated comprehensively
- [ ] Performance impact minimal (< 5% overhead)

### Nice to Have (Future Enhancements)
- [ ] Advanced log filtering options (`--grep`, `--since`)
- [ ] Log compression for older files
- [ ] Integration with external log viewers
- [ ] Configurable log formats
- [ ] Log export functionality

## 🎯 Success Metrics

### Technical Metrics
- **Diagnostic Capability**: Ability to identify macOS vs Ubuntu stability differences
- **Performance Impact**: < 5% overhead on service startup/operation
- **Reliability**: 99.9% log capture success rate
- **Storage Efficiency**: Effective rotation and cleanup

### User Experience Metrics
- **Discoverability**: Users can find service logs within 30 seconds
- **Usability**: Common troubleshooting workflows require < 3 commands
- **Clarity**: Log output provides actionable diagnostic information

## 🚀 Implementation Timeline

### Week 1: Foundation
- ServiceLogManager implementation
- Basic log rotation logic
- Adapter modifications for output capture

### Week 2: CLI Integration
- Enhanced log commands
- Service name matching and completion
- Status display integration

### Week 3: Testing & Polish
- Comprehensive test suite
- Performance optimization
- Error handling improvements

### Week 4: Documentation & Release
- User and developer documentation
- Manual testing and validation
- Release preparation and deployment

## 🔄 Future Enhancements (v0.3.5+)

### Advanced Diagnostics
- **Log analysis tools**: Built-in pattern recognition for common issues
- **Performance metrics**: Connection latency and stability tracking
- **Alerting**: Proactive notification of connection issues

### Integration Improvements
- **External tools**: Integration with popular log viewers (less, tail, grep)
- **Export formats**: JSON, CSV export for analysis tools
- **Monitoring**: Integration with monitoring systems

### Platform Optimization
- **macOS improvements**: Specific optimizations based on diagnostic findings
- **Windows support**: Full Windows compatibility and testing
- **Container environments**: Optimized logging for containerized deployments

---

This comprehensive plan provides the foundation for implementing enhanced service logging in LocalPort v0.3.4, enabling the diagnostic capabilities needed to understand and resolve platform-specific connection stability issues while maintaining the excellent user experience established in previous releases.
