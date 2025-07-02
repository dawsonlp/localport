# LocalPort

A universal port forwarding manager with health monitoring and auto-restart capabilities for development environments.

## Overview

LocalPort is a modern Python CLI tool that provides reliable, automated port forwarding with comprehensive health monitoring. It supports multiple forwarding technologies (kubectl, SSH) and includes intelligent restart logic to keep your development services accessible.

## Features

- **Universal Port Forwarding**: Support for kubectl port-forward and SSH tunneling
- **Health Monitoring**: Continuous health checks with automatic restart on failure
- **Kafka Support**: Special handling for Kafka advertised listeners
- **Daemon Mode**: Background operation with monitoring and control
- **Rich CLI**: Beautiful command-line interface with progress indicators
- **Configuration Management**: YAML-based configuration with environment variable support
- **Cross-Platform**: Works on Linux, macOS, and Windows

## Quick Start

### Installation

```bash
# Install from PyPI (when available)
pipx install localport

# Install from GitHub
pipx install git+https://github.com/dawsonlp/localport.git

# Install with optional dependencies
pipx install "localport[kafka,postgres]"
```

### Basic Usage

```bash
# Start specific services
localport start postgres kafka

# Start all services in a group
localport start --group essential

# Start all configured services
localport start --all

# Check service status
localport status

# Stop services
localport stop postgres kafka

# Run in daemon mode
localport daemon start
```

### Configuration

Create a `localport.yaml` file:

```yaml
version: "1.0"

services:
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_type: service
      resource_name: postgres
      namespace: default
    tags: [database, essential]
    description: "PostgreSQL database"

  - name: kafka
    technology: kubectl
    local_port: 6092
    remote_port: 9092
    connection:
      resource_type: service
      resource_name: kafka
      namespace: kafka
    tags: [messaging, essential]
    description: "Kafka message broker"
```

## Development

### Requirements

- Python 3.13+
- UV (for dependency management)
- Virtual environment support

### Setup

```bash
# Clone the repository
git clone https://github.com/dawsonlp/localport.git
cd localport

# Setup development environment
./scripts/setup-dev.sh

# Activate virtual environment
source .venv/bin/activate

# Install in development mode
uv pip install -e .

# Run tests
uv run pytest
```

## Architecture

LocalPort is built using hexagonal architecture with clean separation of concerns:

- **Domain Layer**: Core business logic and entities
- **Application Layer**: Use cases and application services
- **Infrastructure Layer**: External adapters (kubectl, SSH, health checks)
- **CLI Layer**: Command-line interface with Rich formatting

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Status

🚧 **Under Development** - This project is currently in active development. See the [implementation checklist](implementation_design_python.md#implementation-checklist) for current progress.

## Documentation

- [Requirements](localport.md) - Detailed project requirements
- [Implementation Design](implementation_design_python.md) - Technical architecture and implementation guide
- [Configuration Guide](docs/configuration.md) - Configuration options and examples (coming soon)
- [Development Guide](docs/development.md) - Development setup and contribution guidelines (coming soon)
