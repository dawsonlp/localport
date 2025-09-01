# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 🎯 Improved
- **User-Friendly Error Messages**: Replaced verbose technical error messages with concise, actionable feedback
  - SSH key not found errors now show safe paths (`~/.ssh/key.pem`) instead of full system paths
  - Added contextual information (service name, configuration source) to help users identify issues
  - Included actionable suggestions for common problems (e.g., "Ask your colleague to share the correct key file name")
  - Technical details still available via `--verbose` and `--debug` flags for developers
  - Particularly improves experience when sharing configuration files between team members

### 🔧 Technical
- Added structured error classification system with `LocalPortError` base class
- Implemented `SSHKeyNotFoundError` with built-in path sanitization and context enrichment  
- Created `ErrorFormatter` with multiple verbosity levels (normal, verbose, debug)
- Updated domain validation to use structured exceptions instead of generic `ValueError`
- Enhanced infrastructure layer to preserve error context through the application stack
- Added comprehensive integration tests for error formatting behavior

## [0.3.8] - 2025-01-08

### Added
- **SSH Bastion Host Support**: Complete SSH bastion host/jump server functionality for accessing internal resources
  - New `remote_host` parameter in SSH connection configuration
  - Support for connecting through bastion hosts to reach RDS databases and other internal services
  - Automatic SSH tunnel generation with proper bastion host routing
  - Real-world tested with AWS RDS through EC2 bastion hosts

### Enhanced
- **SSH Tunneling**: Significantly improved SSH tunneling capabilities
  - Enhanced `ConnectionInfo` value object with `get_ssh_remote_host()` method
  - Updated SSH adapter to use configurable remote hosts instead of hardcoded localhost
  - Fixed YAML configuration repository to properly pass `remote_host` parameter
  - Clean CLI experience with professional terminal output

### Configuration
- **Bastion Host Configuration**: New configuration format for SSH bastion scenarios
  ```yaml
  - name: database-service
    technology: ssh
    local_port: 5433
    remote_port: 5432
    connection:
      host: bastion.example.com      # Bastion/jump host
      user: ec2-user
      key_file: ~/.ssh/key.pem
      port: 22
      remote_host: internal-db.rds.amazonaws.com  # Target host behind bastion
  ```

### Compatibility
- **Backward Compatibility**: All existing SSH configurations continue to work unchanged
- **Migration**: No configuration changes required for existing SSH services
- **Version Management**: Proper version progression from v0.3.7.3 to v0.3.8

### Technical
- **SSH Command Generation**: Proper SSH command generation for bastion host scenarios
  - Example: `ssh -N -L 5433:internal-db.rds.amazonaws.com:5432 -i ~/.ssh/key.pem user@bastion.example.com`
- **Error Handling**: Enhanced error handling for SSH connection scenarios
- **Testing**: Comprehensive testing with real-world bastion host configurations

This release enables LocalPort users to easily access internal infrastructure through bastion hosts while maintaining the familiar LocalPort interface and experience. Perfect for accessing RDS databases, internal APIs, and other services behind corporate firewalls or in private subnets.

## [0.3.7.1] - 2025-01-05

### Fixed
- **Cluster Health Node Count**: Fixed cluster health monitoring showing 0 nodes instead of actual node count
- **Status Command Performance**: Improved performance by using lightweight kubectl client instead of full cluster health manager
- **Time Calculation Errors**: Fixed negative time displays in cluster health "Last Check" column
- **UI Layout Issues**: Removed API Server column from main status command to prevent truncation

### Technical
- **Domain Model Integrity**: Maintained proper `ClusterHealth` domain entities throughout the system
- **Lightweight Pattern**: Both status and cluster commands now use consistent fast kubectl client approach
- **Timezone Handling**: Proper UTC timezone calculations with negative value protection
- **Object Property Access**: Fixed to use `ClusterHealth` attributes instead of dictionary methods

## [0.3.7] - 2025-01-05

### Added
- **Cluster Health Monitoring**: Complete cluster health monitoring system for Kubernetes environments
  - Real-time cluster connectivity monitoring with configurable intervals
  - Automatic cluster discovery from kubectl services in configuration
  - Per-cluster configuration overrides via `cluster_contexts` section
- **New CLI Commands**: 
  - `localport cluster status` - Show detailed cluster health information
  - `localport cluster events` - Show recent cluster events with time filtering
  - `localport cluster pods` - Show pod status for active services
- **Enhanced Status Command**: 
  - Cluster health section automatically added to `localport status`
  - Color-coded health indicators (🟢🟡🔴) for instant visual feedback
  - Real-time cluster connectivity status and basic cluster statistics
- **Graceful Shutdown Infrastructure**: 
  - Enterprise-grade cooperative task management system
  - Signal handling with graceful shutdown coordination
  - Task lifecycle management with proper cleanup
  - Shutdown performance optimized to 2.84s average on macOS

### Improved
- **Mac Stability**: Significantly improved service stability on macOS systems
  - Enhanced daemon lifecycle management
  - Better handling of system sleep/wake cycles
  - Improved process cleanup and resource management
- **Configuration System**: Enhanced configuration validation and error handling
- **CLI User Experience**: Consistent error messages and helpful guidance throughout
- **Documentation**: Comprehensive CLI reference and troubleshooting guides

### Fixed
- **kubectl Compatibility**: Resolved compatibility issues across different kubectl versions
- **Service Restart Logic**: Improved service restart reliability and error recovery
- **Memory Management**: Better resource cleanup and memory usage optimization

### Technical
- **Architecture**: Clean hexagonal architecture with proper separation of concerns
- **Testing**: Comprehensive unit and integration test coverage
- **Performance**: Optimized for low resource usage and fast startup times
- **Logging**: Structured logging with configurable levels and service-specific logs

## [0.3.6] - 2024-12-15

### Added
- **Cluster Health Monitoring Foundation**: Core infrastructure for Kubernetes cluster monitoring
- **Health Check System**: Comprehensive health checking for services and clusters
- **Service Logging**: Individual service log capture and management

### Improved
- **Service Management**: Enhanced service lifecycle management
- **Error Handling**: Better error reporting and recovery mechanisms

## [0.3.5] - 2024-11-20

### Added
- **SSH Support**: Complete SSH tunneling support for remote services
- **Configuration Validation**: Enhanced configuration file validation
- **Service Tags**: Tag-based service organization and management

### Improved
- **CLI Interface**: Enhanced command-line interface with better help and error messages
- **Configuration Management**: Improved configuration file handling and validation

## [0.3.4] - 2024-10-15

### Added
- **Daemon Mode**: Background daemon operation for persistent service management
- **Health Monitoring**: Service health checking and automatic restart capabilities
- **Rich CLI Output**: Beautiful terminal output with colors and formatting

### Improved
- **Service Reliability**: Enhanced service startup and management
- **User Experience**: Improved CLI usability and error messages

## [0.3.3] - 2024-09-10

### Added
- **kubectl Integration**: Native Kubernetes port forwarding support
- **Service Configuration**: YAML-based service configuration system
- **Multi-Service Management**: Support for managing multiple services simultaneously

### Fixed
- **Port Conflicts**: Better handling of port conflicts and allocation
- **Process Management**: Improved subprocess handling and cleanup

## [0.3.2] - 2024-08-05

### Added
- **Configuration System**: Initial YAML configuration support
- **Service Management**: Basic service start/stop/status commands
- **Port Forwarding**: Core port forwarding functionality

### Improved
- **CLI Structure**: Organized command structure with subcommands
- **Error Handling**: Basic error handling and user feedback

## [0.3.1] - 2024-07-01

### Added
- **Initial Release**: Basic port forwarding functionality
- **CLI Framework**: Command-line interface foundation
- **Core Architecture**: Basic application structure and patterns

### Technical
- **Python 3.11+**: Modern Python with type hints and async support
- **Rich Library**: Beautiful terminal output and formatting
- **Typer Framework**: Modern CLI framework with automatic help generation

---

## Version Support

- **Current**: 0.3.8 (Active development and support)
- **Supported**: 0.3.7+ (Security updates and critical bug fixes)
- **Legacy**: 0.3.6 and below (No longer supported)

## Upgrade Guide

### From 0.3.7 to 0.3.8
- **New SSH Bastion Host Support**: Add `remote_host` parameter to SSH configurations for bastion scenarios
- **No Breaking Changes**: All existing SSH configurations work unchanged
- **Enhanced SSH Tunneling**: Improved SSH tunnel management and error handling
- **Configuration Example**: See v0.3.8 release notes for bastion host configuration format

### From 0.3.6 to 0.3.7
- No breaking changes
- New cluster health features are opt-in
- Existing configurations work unchanged
- Enhanced status command includes cluster health automatically

### From 0.3.5 to 0.3.6
- Configuration schema additions for cluster health
- New health check options available
- Service logging enabled by default

### From 0.3.4 to 0.3.5
- SSH configuration format changes
- New tag-based service management
- Enhanced validation requirements

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines and contribution process.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
