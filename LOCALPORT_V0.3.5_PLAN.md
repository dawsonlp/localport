# LocalPort v0.3.5 - SSH Functionality Enhancement Plan

## Overview
LocalPort v0.3.5 will focus on making the existing SSH functionality production-ready by addressing interface compliance, adding comprehensive testing, improving resource management, and enhancing documentation.

## Release Goals
- ✅ Make SSH adapter fully compliant with `PortForwardingAdapter` interface
- ✅ Add comprehensive integration testing for SSH functionality
- ✅ Fix resource management and process lifecycle issues
- ✅ Enhance error handling and validation
- ✅ Improve documentation and user guidance

---

## Phase 1: Object-Oriented Design & Interface Compliance

### 1.1 SSH Adapter Interface Compliance
**Priority: CRITICAL**

#### Tasks:
- [ ] **Fix Missing Abstract Methods**
  - [ ] Implement `validate_connection_info(connection_info: dict[str, Any]) -> list[str]`
  - [ ] Implement `get_adapter_name() -> str`
  - [ ] Implement `get_required_tools() -> list[str]`
  - [ ] Rename `is_process_running()` to `is_port_forward_running()`

#### Design Principles:
- **Single Responsibility**: Each method has one clear purpose
- **Interface Segregation**: Implement only required interface methods
- **Dependency Inversion**: Depend on abstractions (base adapter) not concretions

#### Implementation Details:
```python
def get_adapter_name(self) -> str:
    """Return human-readable adapter name."""
    return "SSH Tunnel"

def get_required_tools(self) -> list[str]:
    """Return list of required external tools."""
    return ["ssh"]

async def validate_connection_info(self, connection_info: dict[str, Any]) -> list[str]:
    """Validate SSH connection configuration."""
    # Move validation logic from ConnectionInfo value object
    # Return list of validation errors (empty if valid)
```

### 1.2 Error Handling Standardization
**Priority: HIGH**

#### Tasks:
- [ ] **Create SSH-Specific Exceptions**
  - [ ] `SSHConnectionError(AdapterError)`
  - [ ] `SSHAuthenticationError(AdapterError)`
  - [ ] `SSHKeyFileError(AdapterError)`
  - [ ] `SSHProcessError(AdapterError)`

- [ ] **Standardize Error Responses**
  - [ ] Replace generic `RuntimeError` with specific exceptions
  - [ ] Add actionable error messages with troubleshooting hints
  - [ ] Implement error recovery strategies where possible

#### Design Principles:
- **Fail Fast**: Detect and report errors as early as possible
- **Explicit Error Types**: Use specific exception types for different failure modes
- **User-Friendly Messages**: Provide actionable guidance in error messages

### 1.3 Resource Management Improvements
**Priority: HIGH**

#### Tasks:
- [ ] **Fix File Handle Management**
  - [ ] Implement context managers for log file handling
  - [ ] Ensure proper cleanup on process termination
  - [ ] Add resource tracking and monitoring

- [ ] **Process Lifecycle Management**
  - [ ] Consolidate process tracking between `_active_processes` and psutil
  - [ ] Implement graceful shutdown with timeout handling
  - [ ] Add process health monitoring

#### Design Principles:
- **Resource Acquisition Is Initialization (RAII)**: Acquire resources in constructors, release in destructors
- **Explicit Cleanup**: Always provide explicit cleanup methods
- **Defensive Programming**: Handle resource cleanup even in error conditions

---

## Phase 2: Coding & Implementation

### 2.1 Core SSH Adapter Fixes
**Priority: CRITICAL**

#### Tasks:
- [ ] **Interface Method Implementation**
  ```python
  # File: src/localport/infrastructure/adapters/ssh_adapter.py
  
  async def validate_connection_info(self, connection_info: dict[str, Any]) -> list[str]:
      """Validate SSH connection configuration."""
      errors = []
      
      # Required fields validation
      if 'host' not in connection_info:
          errors.append("SSH connection requires 'host' field")
      elif not connection_info['host'].strip():
          errors.append("SSH host cannot be empty")
      
      # Port validation
      if 'port' in connection_info:
          try:
              port = int(connection_info['port'])
              if not 1 <= port <= 65535:
                  errors.append(f"SSH port {port} must be between 1 and 65535")
          except (ValueError, TypeError):
              errors.append("SSH port must be a valid integer")
      
      # Key file validation
      if 'key_file' in connection_info and connection_info['key_file']:
          key_path = Path(connection_info['key_file']).expanduser()
          if not key_path.exists():
              errors.append(f"SSH key file not found: {key_path}")
          elif not key_path.is_file():
              errors.append(f"SSH key path is not a file: {key_path}")
          else:
              # Check key file permissions (should be 600 or 400)
              stat_info = key_path.stat()
              if stat_info.st_mode & 0o077:
                  errors.append(f"SSH key file has overly permissive permissions: {key_path}")
      
      return errors
  ```

- [ ] **Resource Management Refactoring**
  ```python
  # Implement proper file handle management
  class LogFileManager:
      def __init__(self, log_file: Path):
          self.log_file = log_file
          self._handle: Optional[TextIO] = None
      
      async def __aenter__(self) -> TextIO:
          self._handle = open(self.log_file, 'a', encoding='utf-8', buffering=1)
          return self._handle
      
      async def __aexit__(self, exc_type, exc_val, exc_tb):
          if self._handle:
              self._handle.close()
              self._handle = None
  ```

### 2.2 Enhanced Validation and Pre-flight Checks
**Priority: MEDIUM**

#### Tasks:
- [ ] **SSH Connectivity Pre-checks**
  - [ ] Implement `validate_ssh_connectivity()` method
  - [ ] Add SSH agent detection and integration
  - [ ] Validate SSH configuration before starting tunnels

- [ ] **Dependency Validation**
  - [ ] Check for `ssh` command availability
  - [ ] Check for `sshpass` when password auth is used
  - [ ] Provide installation guidance for missing tools

#### Implementation:
```python
async def validate_ssh_connectivity(self, connection_info: dict[str, Any]) -> tuple[bool, str]:
    """Pre-flight SSH connectivity check."""
    host = connection_info['host']
    port = connection_info.get('port', 22)
    user = connection_info.get('user')
    
    # Build test command
    cmd = ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes']
    if user:
        cmd.append(f'{user}@{host}')
    else:
        cmd.append(host)
    cmd.extend(['-p', str(port), 'exit'])
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await asyncio.wait_for(process.wait(), timeout=10.0)
        
        if process.returncode == 0:
            return True, "SSH connectivity verified"
        else:
            return False, "SSH connection failed - check credentials and network"
    except Exception as e:
        return False, f"SSH connectivity check failed: {str(e)}"
```

### 2.3 Configuration and CLI Integration
**Priority: MEDIUM**

#### Tasks:
- [ ] **CLI Command Enhancements**
  - [ ] Add `localport ssh test <service>` command for connectivity testing
  - [ ] Add `localport ssh validate <config-file>` for configuration validation
  - [ ] Enhance status display with SSH-specific information

- [ ] **Configuration Validation**
  - [ ] Add SSH configuration schema validation
  - [ ] Provide helpful error messages for common misconfigurations
  - [ ] Add configuration examples and templates

---

## Phase 3: Testing Strategy

### 3.1 Unit Testing Enhancements
**Priority: HIGH**

#### Tasks:
- [ ] **SSH Adapter Unit Tests**
  ```python
  # File: tests/unit/infrastructure/test_ssh_adapter.py
  
  class TestSSHAdapter:
      async def test_get_adapter_name(self):
          adapter = SSHAdapter()
          assert adapter.get_adapter_name() == "SSH Tunnel"
      
      async def test_get_required_tools(self):
          adapter = SSHAdapter()
          assert adapter.get_required_tools() == ["ssh"]
      
      async def test_validate_connection_info_valid(self):
          adapter = SSHAdapter()
          connection_info = {
              'host': 'example.com',
              'port': 22,
              'user': 'testuser'
          }
          errors = await adapter.validate_connection_info(connection_info)
          assert errors == []
      
      async def test_validate_connection_info_missing_host(self):
          adapter = SSHAdapter()
          connection_info = {'port': 22}
          errors = await adapter.validate_connection_info(connection_info)
          assert "SSH connection requires 'host' field" in errors
  ```

- [ ] **Error Handling Tests**
  - [ ] Test all exception types and error conditions
  - [ ] Test error message clarity and actionability
  - [ ] Test error recovery mechanisms

### 3.2 Integration Testing
**Priority: CRITICAL**

#### Tasks:
- [ ] **SSH Integration Tests**
  ```python
  # File: tests/integration/adapters/test_ssh_adapter_integration.py
  
  @pytest.mark.integration
  class TestSSHAdapterIntegration:
      async def test_ssh_tunnel_lifecycle(self, ssh_test_server):
          """Test complete SSH tunnel lifecycle."""
          adapter = SSHAdapter()
          
          # Test connection validation
          errors = await adapter.validate_connection_info(ssh_test_server.connection_info)
          assert errors == []
          
          # Test tunnel creation
          pid = await adapter.start_port_forward(
              local_port=9999,
              remote_port=8080,
              connection_info=ssh_test_server.connection_info
          )
          assert pid > 0
          
          # Test tunnel is running
          assert await adapter.is_port_forward_running(pid)
          
          # Test tunnel cleanup
          await adapter.stop_port_forward(pid)
          assert not await adapter.is_port_forward_running(pid)
  ```

- [ ] **Mock SSH Server Setup**
  - [ ] Create test SSH server using Docker or embedded SSH daemon
  - [ ] Generate test SSH keys and configurations
  - [ ] Test various authentication methods

### 3.3 End-to-End Testing
**Priority: MEDIUM**

#### Tasks:
- [ ] **CLI Integration Tests**
  - [ ] Test SSH service configuration and startup via CLI
  - [ ] Test SSH service monitoring and health checks
  - [ ] Test SSH service logging and troubleshooting

- [ ] **Configuration File Tests**
  - [ ] Test SSH service definitions in YAML configuration
  - [ ] Test environment variable substitution
  - [ ] Test configuration validation and error reporting

### 3.4 Performance and Load Testing
**Priority: LOW**

#### Tasks:
- [ ] **Resource Usage Tests**
  - [ ] Test memory usage with multiple SSH tunnels
  - [ ] Test file handle management under load
  - [ ] Test process cleanup efficiency

- [ ] **Stress Testing**
  - [ ] Test rapid tunnel creation/destruction cycles
  - [ ] Test behavior under network interruptions
  - [ ] Test recovery from SSH process failures

---

## Phase 4: Documentation & User Experience

### 4.1 Technical Documentation
**Priority: HIGH**

#### Tasks:
- [ ] **API Documentation**
  - [ ] Document all SSH adapter public methods
  - [ ] Add code examples for common use cases
  - [ ] Document error conditions and recovery strategies

- [ ] **Architecture Documentation**
  - [ ] Update architecture diagrams to include SSH adapter
  - [ ] Document SSH-specific design decisions
  - [ ] Add sequence diagrams for SSH tunnel lifecycle

### 4.2 User Documentation
**Priority: HIGH**

#### Tasks:
- [ ] **SSH Setup Guide**
  ```markdown
  # File: docs/ssh-setup.md
  
  # SSH Setup Guide
  
  ## Prerequisites
  - OpenSSH client installed
  - SSH key pair generated or password authentication configured
  - Network connectivity to target hosts
  
  ## Quick Start
  1. Generate SSH key: `ssh-keygen -t rsa -b 4096`
  2. Copy key to target: `ssh-copy-id user@host`
  3. Configure LocalPort service with SSH connection details
  4. Start tunnel: `localport start <service-name>`
  
  ## Configuration Examples
  [Include practical examples from ssh-tunnels.yaml]
  
  ## Troubleshooting
  [Common issues and solutions]
  ```

- [ ] **Configuration Reference**
  - [ ] Document all SSH connection parameters
  - [ ] Provide configuration templates for common scenarios
  - [ ] Add validation rules and error explanations

### 4.3 Troubleshooting Documentation
**Priority: MEDIUM**

#### Tasks:
- [ ] **SSH Troubleshooting Guide**
  ```markdown
  # SSH Troubleshooting Guide
  
  ## Common Issues
  
  ### Connection Refused
  - Check host and port configuration
  - Verify SSH service is running on target
  - Check firewall rules
  
  ### Authentication Failed
  - Verify SSH key permissions (600 or 400)
  - Check SSH agent configuration
  - Validate username and key file path
  
  ### Permission Denied
  - Check SSH key is authorized on target
  - Verify user account exists and has shell access
  - Check SSH server configuration
  
  ## Diagnostic Commands
  - Test connectivity: `localport ssh test <service>`
  - Validate config: `localport ssh validate <config>`
  - Check logs: `localport logs <service>`
  ```

- [ ] **Error Message Catalog**
  - [ ] Document all SSH-specific error messages
  - [ ] Provide resolution steps for each error
  - [ ] Add links to relevant documentation sections

### 4.4 Examples and Templates
**Priority: MEDIUM**

#### Tasks:
- [ ] **Configuration Templates**
  - [ ] Basic SSH tunnel template
  - [ ] Database connection template
  - [ ] Multi-service template
  - [ ] High-security template

- [ ] **Real-world Examples**
  - [ ] Development environment setup
  - [ ] Production database access
  - [ ] Monitoring and metrics access
  - [ ] CI/CD pipeline integration

---

## Quality Assurance Checklist

### Code Quality
- [ ] All methods have comprehensive docstrings
- [ ] Type hints are complete and accurate
- [ ] Error handling follows project patterns
- [ ] Logging is consistent and informative
- [ ] Code follows project style guidelines

### Testing Coverage
- [ ] Unit test coverage > 90% for SSH adapter
- [ ] Integration tests cover all major workflows
- [ ] Error conditions are thoroughly tested
- [ ] Performance tests validate resource usage

### Documentation Quality
- [ ] All public APIs are documented
- [ ] User guides are clear and actionable
- [ ] Examples are tested and working
- [ ] Troubleshooting guides are comprehensive

### Security Review
- [ ] SSH key handling is secure
- [ ] Credentials are not logged or exposed
- [ ] File permissions are validated
- [ ] Network security best practices followed

---

## Success Criteria

### Functional Requirements
- [ ] SSH adapter fully implements `PortForwardingAdapter` interface
- [ ] SSH tunnels can be created, monitored, and destroyed reliably
- [ ] Both key-based and password authentication work correctly
- [ ] Service logging integration works for SSH tunnels
- [ ] Configuration validation provides helpful error messages

### Non-Functional Requirements
- [ ] SSH tunnel startup time < 5 seconds
- [ ] Memory usage scales linearly with number of tunnels
- [ ] No resource leaks during normal operation
- [ ] Graceful handling of network interruptions
- [ ] Clear error messages for all failure modes

### User Experience
- [ ] SSH setup documentation is clear and complete
- [ ] Configuration examples work out-of-the-box
- [ ] Troubleshooting guides resolve common issues
- [ ] CLI commands provide helpful feedback
- [ ] Error messages include actionable guidance

---

## Release Timeline

### Week 1: Core Implementation
- Days 1-2: Interface compliance fixes
- Days 3-4: Resource management improvements
- Days 5-7: Error handling standardization

### Week 2: Testing & Validation
- Days 1-3: Unit and integration test implementation
- Days 4-5: End-to-end testing setup
- Days 6-7: Performance and stress testing

### Week 3: Documentation & Polish
- Days 1-3: User documentation and guides
- Days 4-5: API documentation and examples
- Days 6-7: Final testing and release preparation

### Week 4: Release & Support
- Days 1-2: Release candidate testing
- Days 3-4: Final release and deployment
- Days 5-7: Post-release monitoring and support

---

## Risk Mitigation

### Technical Risks
- **SSH compatibility issues**: Test with multiple SSH implementations
- **Resource leaks**: Implement comprehensive resource tracking
- **Authentication failures**: Provide clear diagnostic tools

### User Experience Risks
- **Complex configuration**: Provide templates and validation
- **Poor error messages**: User-test all error conditions
- **Missing documentation**: Comprehensive review process

### Timeline Risks
- **Scope creep**: Strict adherence to defined requirements
- **Testing delays**: Parallel development and testing
- **Documentation lag**: Documentation written alongside code

---

## Post-Release Monitoring

### Metrics to Track
- SSH tunnel success/failure rates
- Resource usage patterns
- Common error conditions
- User adoption and feedback

### Support Preparation
- Monitor GitHub issues for SSH-related problems
- Prepare FAQ based on common questions
- Plan follow-up improvements based on user feedback
- Document lessons learned for future releases

---

*This plan follows LocalPort's established patterns of incremental, well-tested releases with comprehensive documentation and user support.*
