# Changelog

All notable changes to LocalPort will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

- **Current**: 0.3.7 (Active development and support)
- **Supported**: 0.3.6+ (Security updates and critical bug fixes)
- **Legacy**: 0.3.5 and below (No longer supported)

## Upgrade Guide

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
