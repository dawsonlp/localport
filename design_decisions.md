# Design Decisions

## Architecture

### Hexagonal Architecture
- **Decision**: Use hexagonal (ports and adapters) architecture
- **Rationale**: Provides clear separation of concerns, makes the application testable, and allows for easy swapping of external dependencies
- **Implementation**: 
  - Domain layer contains business logic and entities
  - Application layer contains use cases and services
  - Infrastructure layer contains adapters for external systems
  - CLI layer provides the user interface

### Dependency Injection
- **Decision**: Use dependency injection pattern
- **Rationale**: Improves testability and flexibility
- **Implementation**: Manual dependency injection in main application setup

## Technology Choices

### Python Version
- **Decision**: Require Python 3.13+
- **Rationale**: Access to latest language features, performance improvements, and modern typing capabilities
- **Impact**: May limit compatibility with older systems but ensures access to cutting-edge features

### CLI Framework
- **Decision**: Use Typer for CLI interface
- **Rationale**: 
  - Type-safe CLI development
  - Automatic help generation
  - Rich integration for beautiful output
  - Modern Python patterns
- **Alternative considered**: Click (Typer is built on Click but provides better type safety)

### Rich Output
- **Decision**: Use Rich for terminal formatting
- **Rationale**: 
  - Beautiful, professional terminal output
  - Tables, progress bars, and syntax highlighting
  - Excellent integration with Typer
  - Improves user experience significantly

### Configuration Management
- **Decision**: Use YAML for configuration files with Pydantic for validation
- **Rationale**: 
  - YAML is human-readable and widely adopted
  - Pydantic provides excellent validation and type safety
  - Easy to extend and maintain
- **Alternative considered**: TOML (chose YAML for better readability of complex nested structures)

### Async/Await
- **Decision**: Use asyncio for concurrent operations
- **Rationale**: 
  - Better performance for I/O-bound operations (health checks, network calls)
  - Modern Python concurrency patterns
  - Scales well with multiple port forwards

### Health Checking
- **Decision**: Implement pluggable health check system
- **Rationale**: 
  - Different services need different health check strategies
  - Extensible design allows for custom health checks
  - Improves reliability of port forwarding

### Process Management
- **Decision**: Use subprocess for external tool integration (kubectl, ssh)
- **Rationale**: 
  - Leverages existing, well-tested tools
  - Avoids reimplementing complex networking logic
  - Easier to maintain and debug

### Logging
- **Decision**: Use structlog for structured logging
- **Rationale**: 
  - Better for debugging and monitoring
  - JSON output for production environments
  - Rich integration for development

### Testing Strategy
- **Decision**: Comprehensive testing with pytest
- **Rationale**: 
  - Unit tests for business logic
  - Integration tests for external tool interaction
  - Separate test configurations for different environments

### Package Management
- **Decision**: Use UV for dependency management and building
- **Rationale**: 
  - Faster than pip/poetry
  - Modern Python packaging
  - Better dependency resolution
  - Excellent CI/CD integration

### Version Management
- **Decision**: Use Hatch VCS for dynamic versioning
- **Rationale**: 
  - Automatic version derivation from Git tags
  - Eliminates version mismatch issues
  - PEP 440 compliant version normalization
  - No manual version management required
- **Implementation**: 
  - Git tag `v0.1.0-alpha.6` → Package version `0.1.0a6`
  - Git tag `v1.0.0` → Package version `1.0.0`
  - Git tag `v1.2.3-beta.1` → Package version `1.2.3b1`
- **Problem Solved**: Previously Git tags and package versions didn't match, causing confusion

## Development Workflow

### Code Quality
- **Decision**: Use ruff, black, and mypy for code quality
- **Rationale**: 
  - Ruff provides fast linting
  - Black ensures consistent formatting
  - MyPy catches type errors early

### Pre-commit Hooks
- **Decision**: Use pre-commit for automated quality checks
- **Rationale**: Prevents low-quality code from being committed

### CI/CD
- **Decision**: Use GitHub Actions for CI/CD
- **Rationale**: 
  - Integrated with GitHub
  - Good ecosystem of actions
  - Free for open source projects

### Release Strategy
- **Decision**: Automated releases with Test PyPI for pre-releases
- **Rationale**: 
  - Safe testing before production releases
  - Automated publishing reduces manual errors
  - Clear separation between test and production environments

## Security Considerations

### Input Validation
- **Decision**: Validate all configuration inputs with Pydantic
- **Rationale**: Prevents configuration errors and potential security issues

### Process Isolation
- **Decision**: Run external processes with limited privileges where possible
- **Rationale**: Reduces attack surface

### Credential Management
- **Decision**: Never store credentials in configuration files
- **Rationale**: Security best practice - rely on external credential management

## Performance Considerations

### Concurrent Health Checks
- **Decision**: Run health checks concurrently
- **Rationale**: Improves responsiveness when managing multiple services

### Efficient Process Management
- **Decision**: Reuse processes where possible, clean shutdown
- **Rationale**: Reduces resource usage and improves reliability

## Extensibility

### Plugin Architecture
- **Decision**: Design for extensibility in health checks and adapters
- **Rationale**: Allows users to add custom functionality without modifying core code

### Configuration Schema
- **Decision**: Use flexible but validated configuration schema
- **Rationale**: Balances ease of use with type safety and validation

## Documentation Strategy

### Comprehensive Documentation
- **Decision**: Provide extensive documentation and examples
- **Rationale**: Improves adoption and reduces support burden

### CLI Help
- **Decision**: Rich, contextual help throughout the CLI
- **Rationale**: Improves user experience and reduces learning curve

## Deployment Strategy

### Multiple Installation Methods
- **Decision**: Support both pipx and UV for installation
- **Rationale**: 
  - pipx for traditional Python package management
  - UV for modern, fast package management
  - Provides flexibility for different user preferences

### Cross-Platform Support
- **Decision**: Support Linux, macOS, and Windows
- **Rationale**: Maximizes potential user base

### Container Support
- **Decision**: Design to work well in containerized environments
- **Rationale**: Modern deployment patterns often use containers

## Domain Model Design

### ConnectionInfo Value Object vs Dictionary
- **Decision**: Use ConnectionInfo value object instead of simple dictionary for connection information
- **Rationale**: 
  - **Type Safety**: Provides compile-time validation of connection parameters
  - **Domain-Driven Design**: Encapsulates connection logic and validation within the domain
  - **Immutability**: Value objects prevent accidental modification of connection data
  - **Rich Behavior**: Methods like `get_kubectl_namespace()` provide clean, type-safe APIs
  - **Validation**: Built-in validation for different connection types (kubectl vs SSH)
  - **Architectural Consistency**: Aligns with hexagonal architecture and DDD principles
- **Implementation**: 
  - Service entity uses `ConnectionInfo` instead of `dict[str, Any]`
  - YAML config repository creates ConnectionInfo objects using factory methods
  - Adapters consume ConnectionInfo objects with type-safe accessors
- **Trade-offs**: 
  - **Pro**: Better maintainability, fewer runtime errors, cleaner APIs
  - **Con**: Slightly more complex serialization, requires migration of existing code
- **Alternative Considered**: Simple dictionary approach (rejected due to lack of type safety and validation)

## Process Management Breakthrough

### Kubectl Process Persistence Issue
- **Problem**: kubectl processes started by LocalPort were terminating unexpectedly after the parent LocalPort process exited
- **Root Cause**: Using `asyncio.create_subprocess_exec` with stdout/stderr pipes kept references that prevented proper process detachment
- **Solution**: Switch to `subprocess.Popen` with `stdout=DEVNULL`, `stderr=DEVNULL`, and `start_new_session=True`
- **Result**: kubectl processes now survive after LocalPort exits and remain fully functional
- **Implementation**: 
  - Use `subprocess.Popen` instead of `asyncio.create_subprocess_exec`
  - Redirect all streams to `DEVNULL` to avoid keeping references
  - Set `start_new_session=True` for proper process group isolation
  - Store only PIDs in process tracking, not process objects
- **Testing**: Verified with PostgreSQL connection through kubectl port-forward
- **Impact**: Enables reliable, persistent port forwarding that survives CLI command completion
