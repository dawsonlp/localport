# Configuration Management Enhancement Design

## Overview

This document outlines the design for enhancing LocalPort's configuration management capabilities with intelligent connection management commands. The goal is to provide users with efficient CLI commands to add, remove, and audit connections without manually editing YAML files.

## Current State Analysis

### Existing Functionality
- `localport config export` - Export configuration to YAML/JSON formats
- `localport config validate` - Validate configuration file syntax and structure
- Manual YAML file editing for connection management

### Gaps Identified
1. **No CLI command to add new connections** - Users must manually edit YAML
2. **No CLI command to remove connections** - Users must manually edit YAML  
3. **Limited audit capabilities** - Only basic validation exists

## Design Goals

### Primary Objectives
1. **Minimize user input** - Auto-discover information where possible
2. **Intelligent defaults** - Use sensible defaults for optional parameters
3. **Technology-specific optimization** - Different flows for kubectl vs SSH
4. **Maintain existing patterns** - Follow established CLI conventions

### Success Criteria
- Users can add a kubectl connection with minimal input (2-3 prompts maximum)
- Users can add an SSH connection with essential information only
- Configuration remains valid and follows existing schema
- Commands integrate seamlessly with existing CLI structure

## Command Design

### New Commands

#### 1. `localport config add [service-name] [--kubectl|--ssh]`
**Purpose:** Add a new connection to configuration

**Technology-Specific Flows:**

**kubectl Flow:**
```bash
# Ultra-minimal flow
$ localport config add --kubectl postgres-service
? Local port: 5433

🔍 Found postgres-service in namespace 'production'
🔍 Discovered ports: 5432/tcp (postgresql)
✅ Auto-selected port 5432 (only available port)
✅ Added service 'postgres-service' forwarding localhost:5433 → postgres-service:5432
```

**SSH Flow:**
```bash
# Minimal required input
$ localport config add my-database --ssh  
? SSH Host: db.example.com
? Local port: 5433
? Remote port: 5432
✅ Added service 'my-database' forwarding localhost:5433 → db.example.com:5432
```

#### 2. `localport config remove <service-name>`
**Purpose:** Remove a connection from configuration

```bash
$ localport config remove postgres-service
? Are you sure you want to remove 'postgres-service'? (y/N) y
✅ Removed service 'postgres-service' from configuration
```

#### 3. `localport config list`
**Purpose:** Enhanced audit view of all connections

```bash
$ localport config list
📋 Configuration Services
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ Service                ┃ Technology ┃ Target                        ┃ Local Port   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ postgres-service       │ kubectl    │ postgres-service:5432 (prod) │ :5433        │
│ redis-cache           │ kubectl    │ redis-cache:6379 (dev)       │ :6380        │
│ my-database           │ ssh        │ db.example.com:5432          │ :5434        │
└────────────────────────┴────────────┴───────────────────────────────┴──────────────┘

📊 Total: 3 services | kubectl: 2 | ssh: 1
```

## Technical Implementation

### Required Parameters Analysis

#### kubectl Connections (Minimal Required)
- `resource_name`: Kubernetes resource to forward to
- `local_port`: Local port to bind
- `remote_port`: **Auto-discovered** from Kubernetes resource

#### SSH Connections (Minimal Required)  
- `host`: SSH host (hostname or IP)
- `local_port`: Local port to bind
- `remote_port`: Must be specified (no auto-discovery)

### Intelligent Auto-Discovery

#### kubectl Resource Discovery
```bash
# Discovery sequence:
1. kubectl get service <name> -n $(current-namespace)
2. If not found: kubectl get service <name> -n default
3. If not found: kubectl get service <name> --all-namespaces
4. Parse JSON output to extract available ports
5. Auto-select if single port, prompt if multiple
```

#### Namespace Handling Strategy
1. **Try current kubectl context's default namespace first**
2. **Fallback to "default" namespace if different**
3. **Search across namespaces if resource not found**
4. **Allow explicit override with `--namespace` flag**

### Service Naming Strategy

#### kubectl Services
- **Default:** Service name = Resource name
- **Override:** `--name` flag allows custom service name
- **Example:** `postgres-service` resource becomes `postgres-service` service by default

#### SSH Services
- **Required:** Explicit service name (host ≠ service name)
- **Reason:** SSH hosts don't map directly to logical service names

## User Experience Flows

### kubectl Connection - Minimal Flow
```bash
$ localport config add --kubectl postgres-service
```

**Internal Process:**
1. Check if `postgres-service` resource exists in current namespace
2. If not found, search other namespaces and prompt for selection
3. Discover available ports on the resource
4. If single port, auto-select; if multiple, prompt user
5. Prompt for local port
6. Create service entry with name=resource_name
7. Save to configuration file

### kubectl Connection - Advanced Options
```bash
$ localport config add --kubectl postgres-service --name my-postgres --namespace production --local-port 5433
```

**Internal Process:**
1. Use explicitly provided parameters
2. Skip discovery where values are provided
3. Validate resource exists in specified namespace
4. Create service entry and save

### SSH Connection Flow
```bash  
$ localport config add my-database --ssh
```

**Internal Process:**
1. Prompt for SSH host
2. Prompt for local port
3. Prompt for remote port
4. Create SSH service entry with provided name
5. Save to configuration file

### Enhanced Discovery Flow
```bash
$ localport config add --kubectl redis-cache
❌ redis-cache not found in namespace 'default'
🔍 Found redis-cache in these namespaces:
  [1] development  
  [2] staging
? Select namespace: 1

🔍 Discovered ports on redis-cache:
  [1] 6379/tcp (redis)
  [2] 8080/tcp (metrics)  
? Select remote port: 1
? Local port: 6380

✅ Added service 'redis-cache' forwarding localhost:6380 → redis-cache:6379 (development)
```

## Implementation Strategy

### Phase 1: Core Add Command
1. **Create `add_connection_command.py`** in `src/localport/cli/commands/`
2. **Implement kubectl discovery logic** using existing kubectl infrastructure
3. **Add basic interactive prompts** using Rich/Typer
4. **Update configuration repository** with new service entries

### Phase 2: Remove and List Commands  
1. **Implement `remove` command** with confirmation prompts
2. **Enhance `list` command** with rich formatting
3. **Add validation** to prevent removing running services

### Phase 3: Advanced Features
1. **Add `--dry-run` flag** to preview changes
2. **Implement backup/restore** for configuration changes
3. **Add batch operations** for multiple services

### Integration Points

#### CLI Structure
```
src/localport/cli/commands/config_commands.py
├── add_connection_sync()      # NEW
├── remove_connection_sync()   # NEW  
├── list_connections_sync()    # NEW
├── export_config_sync()       # EXISTING
└── validate_config_sync()     # EXISTING
```

#### Repository Integration
```python
# Extend YamlConfigRepository with:
async def add_service(self, service: dict) -> None
async def remove_service(self, service_name: str) -> None  
async def list_services(self) -> list[dict]
```

#### Discovery Services
```python
# New discovery services:
class KubernetesResourceDiscovery:
    async def find_resource(self, name: str, namespace: str = None)
    async def get_available_ports(self, resource_name: str, namespace: str)
    async def get_current_namespace(self) -> str
```

## Configuration Schema Impact

### No Schema Changes Required
The new commands will generate standard LocalPort configuration entries that conform to the existing schema:

```yaml
version: "1.0"
services:
  - name: postgres-service          # Auto-generated from resource name
    technology: kubectl
    local_port: 5433
    remote_port: 5432               # Auto-discovered
    connection:
      resource_name: postgres-service
      namespace: production         # Auto-discovered
      resource_type: service        # Default
      
  - name: my-database              # User-provided
    technology: ssh  
    local_port: 5434
    remote_port: 5432              # User-provided
    connection:
      host: db.example.com         # User-provided
      port: 22                     # Default
```

## Error Handling

### kubectl-Specific Errors
- **Resource not found:** Search other namespaces, provide suggestions
- **Multiple namespaces:** Present selection menu
- **No ports available:** Graceful error with manual override option
- **kubectl not available:** Clear error message with installation instructions

### SSH-Specific Errors  
- **Invalid host:** Validate hostname/IP format
- **Port conflicts:** Check for existing local port usage
- **Connection test failures:** Optional connectivity test with clear error messages

### General Errors
- **Configuration file locked:** Handle concurrent access gracefully
- **Invalid service name:** Validate against existing services
- **Missing permissions:** Clear error messages for file system issues

## Testing Strategy

### Unit Tests
```python
# Test kubectl discovery logic
test_kubectl_resource_discovery()
test_kubectl_port_discovery()  
test_kubectl_namespace_resolution()

# Test SSH validation
test_ssh_host_validation()
test_ssh_port_validation()

# Test configuration operations
test_add_service_to_config()
test_remove_service_from_config()
```

### Integration Tests
```python
# Test full user flows
test_kubectl_add_flow_minimal()
test_kubectl_add_flow_multiple_ports()
test_kubectl_add_flow_multiple_namespaces()
test_ssh_add_flow()
test_remove_service_flow()
test_list_services_flow()
```

### Manual Testing Scenarios
1. **kubectl service with single port** - Should auto-select port
2. **kubectl service with multiple ports** - Should prompt for selection
3. **kubectl service in different namespace** - Should find and prompt
4. **SSH connection with bastion host** - Should handle remote_host parameter
5. **Service name conflicts** - Should prevent duplicates
6. **Invalid resource names** - Should provide helpful errors

## Security Considerations

### SSH Key Handling
- **Never prompt for passwords** in CLI
- **Validate key file paths** before saving to configuration
- **Use existing SSH key error handling** from recent improvements

### Configuration File Security
- **Preserve file permissions** when modifying configuration
- **Create backup before modifications** to prevent data loss
- **Validate configuration integrity** after each change

## Documentation Updates

### CLI Help Text
- Update `localport config --help` to include new commands
- Add examples for each command in help text
- Document all flags and options

### User Guides
- Update getting started guide with new add/remove workflows
- Create configuration management best practices guide
- Add troubleshooting section for discovery failures

## Rollout Plan

### Development Phases
1. **Phase 1 (2 weeks):** Core add command for kubectl
2. **Phase 2 (1 week):** SSH add command and remove command
3. **Phase 3 (1 week):** Enhanced list command and polish

### Testing Timeline
- **Week 1:** Unit tests and basic integration tests
- **Week 2:** Manual testing with various Kubernetes environments
- **Week 3:** Beta testing with real user configurations

### Deployment Strategy
- **Alpha release:** Internal testing only
- **Beta release:** Opt-in feature flag for early adopters
- **Stable release:** Default enabled after successful beta period

## Success Metrics

### Efficiency Metrics
- **kubectl connections:** ≤ 3 user inputs required
- **SSH connections:** ≤ 4 user inputs required
- **Discovery success rate:** > 90% for common resources

### User Experience Metrics
- **Configuration errors:** < 5% of generated configurations invalid
- **User satisfaction:** Positive feedback on reduced manual editing
- **Adoption rate:** > 80% of new connections created via CLI vs manual editing

---

**Document Version:** 1.0  
**Created:** September 1, 2025  
**Author:** LocalPort Development Team  
**Status:** Ready for Implementation
