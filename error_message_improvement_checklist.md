# Error Message Improvement Checklist

## Problem Statement
When sharing configs with SSH key-based connections, colleagues get verbose error output instead of clean, helpful messages when they don't have access to the SSH keys. The current output creates "ugly screen full of text" instead of providing concise, actionable feedback.

## Current State Analysis
- ✅ Error formatting system exists (`ErrorFormatter`) with verbosity levels
- ✅ Structured exceptions exist (`SSHKeyNotFoundError`, etc.)
- ✅ Rich console formatting available
- ❌ Inconsistent usage of error formatter across adapters/CLI
- ❌ Raw exceptions might be leaking through without proper formatting

## Solution Design

### Phase 1: Error Handling Audit
- [x] Identify all places where SSH errors can occur
- [x] Check if CLI commands are using ErrorFormatter consistently
- [x] Find where verbose output is coming from (stack traces, raw exceptions)
- [x] Document current error flow from adapter → use case → CLI

### Phase 2: Clean Error Message Implementation
- [x] Ensure SSH adapter always throws LocalPortError subclasses
- [x] Update CLI commands to use ErrorFormatter with NORMAL verbosity by default
- [x] Add --verbose flag support for debugging
- [x] Create error message templates for common scenarios

### Phase 3: Common Error Scenarios
- [x] SSH key file not found (colleague sharing config)
- [x] SSH key permissions incorrect
- [x] Host unreachable / connection timeout
- [x] Authentication failed (wrong key, wrong user)
- [x] Port already in use

### Phase 4: Progressive Error Disclosure
- [x] NORMAL: Clean message + quick fix
- [x] VERBOSE: Add context and technical details  
- [x] DEBUG: Full stack traces and internals

## Target User Experience

### Current (Problem):
```
Traceback (most recent call last):
  File "/path/to/localport/connection_info.py", line 72, in get_ssh_key_file
    raise ValueError(f"SSH key file not found: {key_path}")
ValueError: SSH key file not found: /Users/colleague/.ssh/nonexistent_key.pem
  [20+ lines of stack trace]
```

### Desired (Solution):
```
❌ SSH Key Missing

SSH key file not found: ~/.ssh/nonexistent_key.pem

💡 Quick Fix:
   • Provide valid SSH authentication credentials for this connection
   • Generate SSH key if needed: ssh-keygen -t rsa -f ~/.ssh/nonexistent_key.pem
   • Update config to point to correct SSH key file path

Use --verbose for technical details.
```

## Implementation Tasks

### 1. Audit Current Error Handling
- [x] Check `start_services.py` use case error handling
- [x] Check CLI commands error handling in `service_commands.py`
- [x] Check SSH adapter error propagation
- [x] Find where stack traces are being printed

### 2. Implement Consistent Error Formatting
- [x] Update CLI command error handlers to use ErrorFormatter
- [x] Add verbosity flag support to commands
- [x] Ensure all SSH-related exceptions use LocalPortError
- [x] Create error message testing scenarios

### 3. Improve SSH-Specific Error Messages
- [x] SSH key not found (focus on colleague config sharing)
- [x] SSH connectivity failures
- [x] Authentication failures
- [x] Dependency missing (ssh, sshpass)

### 4. Add Verbosity Control
- [x] Default to NORMAL verbosity in CLI
- [x] Add --verbose flag for technical details
- [x] Add --debug flag for full diagnostics
- [x] Update help text to mention verbosity options

### 5. Testing & Validation
- [x] Test with missing SSH keys
- [x] Test with incorrect permissions
- [x] Test with unreachable hosts
- [x] Test verbosity flag behavior
- [x] Validate clean output formatting

## Success Criteria
1. **Clean by Default**: Normal error output fits in 5-10 lines with actionable advice
2. **Progressive Disclosure**: Users can get more details with --verbose/--debug
3. **Colleague Friendly**: Shared configs show helpful messages, not system paths
4. **Consistent**: All error types use the same formatting system
5. **Actionable**: Every error includes specific next steps

## Files to Modify
- `src/localport/cli/commands/service_commands.py` - Add error formatting
- `src/localport/application/use_cases/start_services.py` - Error propagation
- `src/localport/infrastructure/adapters/ssh_adapter.py` - Exception consistency  
- `src/localport/cli/app.py` - Add verbosity flags
- Test files for validation
