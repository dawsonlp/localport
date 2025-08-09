# SSH Bastion Host Support Implementation Checklist

## Problem Statement
LocalPort's SSH adapter currently hardcodes `localhost` as the tunnel destination, preventing proper bastion host tunneling to remote services like RDS instances.

## Required Changes

### 1. ConnectionInfo Value Object Enhancement
- [x] Add `remote_host` parameter to SSH connection configuration
- [x] Add `get_ssh_remote_host()` method to ConnectionInfo class
- [ ] Update SSH validation to handle optional remote_host parameter
- [x] Ensure backward compatibility (default to localhost if not specified)

**File**: `src/localport/domain/value_objects/connection_info.py`

### 2. SSH Adapter Modification
- [x] Modify SSH command construction to use configurable remote host
- [x] Update both `start_port_forward` and `start_port_forward_with_logging` methods
- [x] Change from: `f'{local_port}:localhost:{remote_port}'`
- [x] Change to: `f'{local_port}:{remote_host}:{remote_port}'`
- [x] Add logging to show the actual tunnel being created

**File**: `src/localport/infrastructure/adapters/ssh_adapter.py`

### 3. Configuration Validation
- [ ] Update SSH connection validation to accept remote_host parameter
- [ ] Ensure remote_host validation (non-empty string if provided)
- [ ] Update error messages to be helpful for bastion host scenarios

### 4. Documentation Updates
- [ ] Update SSH tunnel examples to show bastion host usage
- [ ] Add documentation for remote_host parameter
- [ ] Update configuration guide with bastion host examples

**File**: `docs/examples/ssh-tunnels.yaml`

### 5. Testing
- [ ] Test backward compatibility (existing configs without remote_host)
- [ ] Test bastion host scenario with remote_host parameter
- [ ] Validate configuration parsing and validation
- [ ] Test SSH command generation

## Implementation Details

### ConnectionInfo Changes
```python
def get_ssh_remote_host(self) -> str:
    """Get the SSH remote host for tunneling.
    
    Returns:
        Remote host for SSH tunnel destination, defaults to 'localhost'
    """
    if self.technology != ForwardingTechnology.SSH:
        raise ValueError("Not an SSH connection")
    return self.config.get("remote_host", "localhost")
```

### SSH Adapter Changes
```python
# Current:
'-L', f'{local_port}:localhost:{remote_port}',

# New:
remote_host = connection_info.get_ssh_remote_host()
'-L', f'{local_port}:{remote_host}:{remote_port}',
```

### Configuration Example
```yaml
- name: trilliant-postgres
  technology: ssh
  local_port: 5433
  remote_port: 5432
  connection:
    host: 23.20.253.252  # Bastion host
    user: ec2-user
    key_file: ~/.ssh/bastion_ssh_key.pem
    port: 22
    remote_host: trilliant-postgres.cr6usyu0w0w1.us-east-1.rds.amazonaws.com  # RDS endpoint
```

## Expected SSH Command Result
```bash
ssh -i ~/.ssh/bastion_ssh_key.pem -L 5433:trilliant-postgres.cr6usyu0w0w1.us-east-1.rds.amazonaws.com:5432 ec2-user@23.20.253.252
```

## Validation Steps
1. [ ] Configuration validates successfully
2. [ ] SSH command is constructed correctly
3. [ ] Tunnel establishes connection to RDS through bastion
4. [ ] Health checks work on local port 5433
5. [ ] Existing SSH configurations continue to work (backward compatibility)

## Files to Modify
1. `src/localport/domain/value_objects/connection_info.py`
2. `src/localport/infrastructure/adapters/ssh_adapter.py`
3. `docs/examples/ssh-tunnels.yaml`
4. `docs/configuration.md`

## Priority Order
1. ConnectionInfo enhancement (foundation)
2. SSH adapter modification (core functionality)
3. Configuration validation updates
4. Documentation updates
5. Testing and validation
