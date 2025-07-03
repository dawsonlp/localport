# LocalPort Design Decisions

## Recent Design Decisions (January 2025)

### 1. Constructor Argument Resolution ✅ COMPLETED
**Problem**: Multiple constructor mismatches causing CLI failures
**Decision**: Fixed all constructor calls to match actual class definitions
**Rationale**: Hexagonal architecture requires proper dependency injection
**Implementation**:
- ServiceManager: Takes no parameters (was incorrectly called with parameters)
- HealthMonitor: Requires `service_repository`, `service_manager`, `health_check_factory`
- DaemonManager: Requires `service_repository`, `config_repository`, `service_manager`, `health_monitor`
- ManageDaemonUseCase: Requires `service_repository`, `service_manager` (not daemon_manager)
- MonitorServicesUseCase: Requires `service_repository`, `service_manager`
- YamlConfigRepository: Takes config_path in constructor (not via set_config_file method)

**Impact**: All CLI commands now instantiate correctly without TypeErrors

### 2. "Fail Fast and Clean" Error Handling Philosophy ✅ COMPLETED
**Problem**: CLI showing confusing tracebacks for expected error conditions
**Decision**: Implement clean exit behavior - "if you can't do something useful with an exception, just die"
**Rationale**: Better user experience with clear, actionable error messages
**Implementation**:
- Added `typer.Exit` exception handling to prevent unnecessary tracebacks
- Configuration errors show helpful messages and exit cleanly
- Only genuine unexpected errors show "Unexpected Error" panels
- All error messages include specific log locations

**Impact**: Professional CLI experience with no confusing error noise

### 3. Command Pattern for Use Case Interfaces ✅ COMPLETED
**Problem**: Direct method calls on use cases were inconsistent
**Decision**: Updated all use case calls to use command pattern with `execute()` method
**Rationale**: Consistent interface and better separation of concerns
**Implementation**:
- ManageDaemonUseCase now uses `execute(ManageDaemonCommand)`
- MonitorServicesUseCase now uses `execute(MonitorServicesCommand)`
- All commands properly instantiated with required parameters

**Impact**: Cleaner, more maintainable code structure with consistent patterns

### 4. Enhanced Configuration Error Messages ✅ COMPLETED
**Problem**: Generic "config not found" errors weren't helpful
**Decision**: Provide specific guidance on where to place configuration files
**Rationale**: Follow Unix conventions and guide users toward success
**Implementation**:
```
No configuration file found. Please create a localport.yaml file in one of these locations:
• ./localport.yaml (current directory)
• ~/.config/localport/config.yaml (user config)
• ~/.localport.yaml (user home)
Or specify a custom path with --config.
```

**Impact**: Users know exactly where to place config files

### 5. Specific Log Location Guidance ✅ COMPLETED
**Problem**: Error messages said "check the logs" without saying where
**Decision**: Include specific log paths in all error messages
**Rationale**: Reduce user friction when troubleshooting
**Implementation**: All error messages now include "Check the logs in ~/.local/share/localport/logs/ or run with --verbose for more details."

**Impact**: Users can easily find logs for troubleshooting

## Architecture Decisions

### Hexagonal Architecture Compliance
**Decision**: Maintain strict hexagonal architecture boundaries
**Rationale**: Clean separation of concerns and testability
**Status**: ✅ Maintained throughout constructor fixes

### Rich-based UI Framework
**Decision**: Use Rich library for all CLI output formatting
**Rationale**: Professional user experience with beautiful formatting
**Status**: ✅ Implemented with error panels, tables, and progress indicators

### Async/Await Throughout
**Decision**: Use async/await for all I/O operations
**Rationale**: Better performance and modern Python practices
**Status**: ✅ Maintained in all use cases and adapters

## Development Process Decisions

### Error Handling Strategy
**Decision**: Distinguish between expected and unexpected errors
**Rationale**: Expected errors (like missing config) should show helpful messages, unexpected errors should show technical details
**Implementation**: 
- Expected errors: Clean exit with helpful guidance
- Unexpected errors: Technical details with log locations

### Testing Approach
**Decision**: Focus on constructor and integration issues first, comprehensive testing later
**Rationale**: Get basic functionality working before extensive test coverage
**Status**: Constructor issues resolved, ready for comprehensive testing phase

### Documentation Strategy
**Decision**: Maintain both design_decisions.md and implementation_design_python.md
**Rationale**: 
- design_decisions.md: Records specific decisions made during development
- implementation_design_python.md: Comprehensive implementation guide and checklist
**Status**: ✅ Separated concerns to avoid duplication

## Next Phase Priorities

1. **Configuration Management**: Implement `localport init` command for easy setup
2. **Service Implementation**: Complete actual service start/stop functionality  
3. **Health Monitoring**: Implement health check system
4. **Daemon Process Management**: Complete background daemon functionality

## Lessons Learned

1. **Constructor Validation**: Always verify constructor signatures match usage
2. **Error UX**: Clean, helpful error messages are as important as functionality
3. **Command Patterns**: Consistent interfaces reduce cognitive load
4. **User Guidance**: Specific, actionable error messages save user time
5. **Clean Exits**: Avoid technical noise in user-facing error scenarios
