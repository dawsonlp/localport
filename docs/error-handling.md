# Error Handling Guide

LocalPort implements a comprehensive error handling system designed to provide user-friendly error messages while preserving technical details for debugging when needed.

## Overview

The error handling system uses structured exceptions and intelligent formatting to:
- Provide concise, actionable error messages by default
- Hide sensitive information like full file paths  
- Offer progressive disclosure of technical details
- Give helpful suggestions for common problems
- Format errors consistently across all commands

## Error Verbosity Levels

LocalPort supports three verbosity levels for error output:

### Normal (Default)
```bash
localport start database-service
```
**Output Example:**
```
┌─ SSH Key Missing ─────────────────────────────────────────┐
│ ❌ SSH key file not found: ~/.ssh/project_key.pem        │
│                                                           │
│ 💡 Quick Fix:                                            │
│    • Provide valid SSH authentication credentials        │
│    • Generate SSH key: ssh-keygen -t rsa -f ~/.ssh/...  │
│    • Update config to point to correct SSH key path     │
│                                                           │
│ Use --verbose for technical details.                     │
└───────────────────────────────────────────────────────────┘
```

### Verbose Mode
```bash
localport start database-service --verbose
```
**Additional Context:**
- Service name and configuration source
- Sanitized context information (no sensitive paths)
- Multiple suggestions for resolution

### Debug Mode  
```bash
localport start database-service --debug
```
**Full Technical Details:**
- Complete error context including full file paths
- Error type and category information
- Stack traces and internal state
- All available troubleshooting information

## Common Error Scenarios

### SSH Key Configuration Issues

When sharing configurations with SSH key-based connections, team members often encounter missing key files.

**Problem:** Colleague uses shared config with different SSH key paths
```yaml
services:
  - name: database-tunnel
    technology: ssh
    connection:
      host: bastion.example.com
      user: ubuntu
      key_file: /Users/original_dev/.ssh/project_key.pem  # Won't exist for colleagues
```

**Old Verbose Output:**
```
ValueError: SSH key file not found: /Users/original_dev/.ssh/project_key.pem
  File "/path/to/connection_info.py", line 72, in get_ssh_key_file
    raise ValueError(f"SSH key file not found: {key_path}")
```

**New Concise Output:**
```
┌─ SSH Key Missing ─────────────────────────────────────────┐
│ ❌ SSH key file not found: ~/.ssh/project_key.pem        │
│                                                           │
│ 💡 Quick Fix:                                            │
│    • Provide valid SSH authentication credentials        │  
│    • Generate SSH key: ssh-keygen -t rsa                 │
│    • Update config to point to correct SSH key path     │
└───────────────────────────────────────────────────────────┘
```

### Multiple Service Failures

When multiple services fail (common with shared configs):

```
┌─ Multiple Errors ─────────────────────────────────────────┐
│ Found 2 errors:                                          │
│                                                           │
│ 1. ❌ SSH key file not found: ~/.ssh/prod_key.pem       │
│    💡 Generate key or update config path                 │
│                                                           │
│ 2. ❌ SSH key file not found: ~/.ssh/staging_key.pem    │  
│    💡 Generate key or update config path                 │
│                                                           │
│ Use --verbose for detailed error information.            │
└───────────────────────────────────────────────────────────┘
```

## Privacy and Security

The error handling system is designed with privacy in mind:

### Path Sanitization
- Full user paths are converted to safe display paths
- `/Users/johndoe/.ssh/key.pem` → `~/.ssh/key.pem`
- `/home/jane/.ssh/mykey.pem` → `~/.ssh/mykey.pem`
- `/opt/shared/key.pem` → `key.pem` (filename only for non-home paths)

### Sensitive Information Handling
- Passwords and secrets are never logged or displayed
- SSH key contents are never shown in error messages
- Full file paths are hidden unless in debug mode
- Usernames in paths are sanitized

## Error Categories

LocalPort classifies errors into categories for appropriate handling:

### User Errors (`user_error`)
- Missing configuration files
- Invalid SSH keys or credentials
- Incorrect service names or parameters
- **Formatting:** Red error icon, actionable suggestions

### System Errors (`system_error`) 
- Missing required tools (ssh, kubectl)
- Permission issues
- System resource limitations
- **Formatting:** Yellow warning icon, system-level suggestions

### Network Errors (`network_error`)
- Connection timeouts
- DNS resolution failures  
- Network unreachability
- **Formatting:** Blue network icon, connectivity suggestions

### Validation Errors (`validation_error`)
- Invalid configuration syntax
- Schema validation failures
- Parameter validation errors
- **Formatting:** Magenta validation icon, format guidance

## Structured Exception System

LocalPort uses structured exceptions that carry context and suggestions:

```python
# Example structured exception
SSHKeyNotFoundError(
    key_path="/full/path/to/key.pem",
    service_name="database-tunnel",
    suggestions=[
        "Generate SSH key if needed: ssh-keygen -t rsa",
        "Update config to point to correct SSH key file path"
    ]
)
```

## Integration with Commands

All LocalPort commands use the improved error formatting:

### Service Commands
```bash
localport start --all              # Concise errors for failed services
localport start --all --verbose    # Additional context and suggestions
localport start --all --debug      # Full technical details
```

### Configuration Commands
```bash
localport config validate          # User-friendly validation errors
localport config add ssh-service   # Clear guidance for missing inputs
```

### Cluster Commands  
```bash
localport cluster status           # Clean network error messages
localport cluster events --debug   # Full kubectl error details
```

## Best Practices for Sharing Configurations

### Team Configuration Sharing
1. **Use relative paths when possible:**
   ```yaml
   key_file: ~/.ssh/shared_project_key.pem  # Good
   key_file: /Users/alice/.ssh/key.pem      # Bad - user-specific
   ```

2. **Document key requirements:**
   ```yaml
   # This configuration requires:
   # - SSH key at ~/.ssh/shared_project_key.pem
   # - Public key installed on bastion.example.com
   services:
     - name: database-tunnel
       # ...
   ```

3. **Provide setup instructions:**
   ```bash
   # Generate required SSH key:
   ssh-keygen -t rsa -f ~/.ssh/shared_project_key.pem
   
   # Install public key on server:
   ssh-copy-id -i ~/.ssh/shared_project_key.pem.pub user@bastion.example.com
   ```

### Error Message Customization

For advanced users, error verbosity can be controlled:

```bash
# Environment variable for default verbosity
export LOCALPORT_VERBOSITY=1  # 0=normal, 1=verbose, 2=debug

# Per-command flags
localport start --quiet           # Suppress non-critical errors
localport start --verbose         # Show additional context
localport start --debug           # Show everything
```

## Troubleshooting Common Issues

### "SSH key file not found"
1. **Check the key path:** Verify file exists at the specified location
2. **Use absolute path:** Convert relative paths to absolute if needed
3. **Generate missing key:** `ssh-keygen -t rsa -f ~/.ssh/keyname.pem`
4. **Update permissions:** `chmod 600 ~/.ssh/keyname.pem`
5. **Install public key:** Copy to target server's authorized_keys

### "Configuration file not found"
1. **Check default locations:**
   - `./localport.yaml` (current directory)
   - `~/.config/localport/config.yaml` (user config)
2. **Use --config flag:** Specify custom location
3. **Initialize config:** `localport config init`

### "Service already running"
1. **Check status:** `localport status`
2. **Stop service:** `localport stop service-name`  
3. **Force restart:** `localport start service-name --force`

## Implementation Details

The error formatting system consists of:

### Core Components
- `ErrorFormatter` - Rich console formatting with verbosity levels
- `LocalPortError` - Base structured exception with context and suggestions
- `SSHKeyNotFoundError` - Specific exception for SSH key issues
- `VerbosityLevel` - Enum controlling detail level

### Integration Points
- CLI commands catch and format all exceptions
- Service adapters raise structured exceptions  
- Configuration validators provide helpful validation errors
- Use cases convert technical errors to user-friendly messages

### Testing
- Comprehensive test suite for error formatting
- Integration tests for common user scenarios
- Privacy testing to ensure sensitive data is not exposed

This error handling system ensures LocalPort provides helpful, actionable error messages while maintaining security and privacy standards.
