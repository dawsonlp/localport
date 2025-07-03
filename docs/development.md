# Development Guide

This guide covers day-to-day development workflows, best practices, and practical guidance for contributing to LocalPort.

## Quick Start for Developers

### Prerequisites

- **Python 3.13+** installed on your system
- **Git** for version control
- **UV** for fast package management (recommended)
- **Docker** (optional, for integration testing)
- **kubectl** and **SSH** access for testing adapters

### Development Environment Setup

1. **Clone the repository**:
```bash
git clone https://github.com/yourusername/localport.git
cd localport
```

2. **Run the setup script**:
```bash
./scripts/setup-dev.sh
```

3. **Activate the virtual environment**:
```bash
source .venv/bin/activate
```

4. **Verify installation**:
```bash
# Run tests
uv run pytest

# Check code quality
uv run black --check .
uv run ruff check .
uv run mypy src/

# Install in development mode
uv pip install -e .

# Test CLI
localport --help
```

## Project Structure

Understanding the project layout is crucial for effective development:

```
localport/
├── src/localport/                 # Main source code
│   ├── domain/                    # Business logic (pure Python)
│   │   ├── entities/              # Core business entities
│   │   ├── value_objects/         # Immutable value objects
│   │   ├── repositories/          # Repository interfaces
│   │   └── services/              # Domain services
│   ├── application/               # Use cases and application services
│   │   ├── use_cases/             # Business use cases
│   │   ├── services/              # Application services
│   │   └── dto/                   # Data transfer objects
│   ├── infrastructure/            # External system adapters
│   │   ├── adapters/              # Port forwarding adapters
│   │   ├── health_checks/         # Health check implementations
│   │   └── repositories/          # Repository implementations
│   ├── cli/                       # Command-line interface
│   │   ├── commands/              # CLI command implementations
│   │   ├── formatters/            # Output formatting
│   │   └── utils/                 # CLI utilities
│   └── config/                    # Configuration management
├── tests/                         # Test suite
│   ├── unit/                      # Unit tests (fast, isolated)
│   ├── integration/               # Integration tests (slower)
│   └── fixtures/                  # Test data and configurations
├── docs/                          # Documentation
├── scripts/                       # Development and deployment scripts
└── pyproject.toml                 # Project configuration
```

## Development Workflow

### 1. Feature Development Process

#### Starting a New Feature

1. **Create a feature branch**:
```bash
git checkout -b feature/add-new-adapter
```

2. **Understand the requirements**:
   - Read the issue description thoroughly
   - Check existing architecture documentation
   - Identify which layers will be affected

3. **Write tests first** (TDD approach):
```bash
# Create test file
touch tests/unit/infrastructure/test_new_adapter.py

# Write failing tests
uv run pytest tests/unit/infrastructure/test_new_adapter.py -v
```

4. **Implement the feature**:
   - Start with domain layer (if needed)
   - Move to application layer
   - Implement infrastructure layer
   - Add CLI integration (if needed)

5. **Verify implementation**:
```bash
# Run specific tests
uv run pytest tests/unit/infrastructure/test_new_adapter.py -v

# Run all tests
uv run pytest

# Check code quality
uv run black .
uv run ruff check .
uv run mypy src/
```

#### Example: Adding a New Health Check

1. **Domain Layer** (if new health check type):
```python
# src/localport/domain/entities/health_check.py
class HealthCheckType(Enum):
    NEW_TYPE = "new_type"
```

2. **Infrastructure Layer**:
```python
# src/localport/infrastructure/health_checks/new_health_check.py
class NewHealthCheck:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    async def check(self, **kwargs) -> bool:
        # Implementation
        pass
```

3. **Register in Factory**:
```python
# src/localport/infrastructure/health_checks/health_check_factory.py
def _register_optional_health_checkers(self) -> None:
    try:
        from .new_health_check import NewHealthCheck
        self._health_checkers['new_type'] = NewHealthCheck
    except ImportError:
        logger.debug("New health checker not available")
```

4. **Add Tests**:
```python
# tests/unit/infrastructure/test_new_health_check.py
import pytest
from localport.infrastructure.health_checks.new_health_check import NewHealthCheck

class TestNewHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        checker = NewHealthCheck({})
        result = await checker.check()
        assert result is True
```

### 2. Testing Strategy

#### Unit Tests
Focus on testing individual components in isolation:

```bash
# Run unit tests only
uv run pytest tests/unit/ -v

# Run with coverage
uv run pytest tests/unit/ --cov=src/localport --cov-report=html

# Run specific test file
uv run pytest tests/unit/domain/test_service_entity.py -v

# Run specific test method
uv run pytest tests/unit/domain/test_service_entity.py::TestService::test_create_service -v
```

#### Integration Tests
Test component interactions and external system integration:

```bash
# Run integration tests (requires external dependencies)
uv run pytest tests/integration/ -v

# Skip slow tests during development
uv run pytest -m "not slow"

# Run only adapter tests
uv run pytest tests/integration/adapters/ -v
```

#### Test Organization
```python
# tests/unit/domain/test_service_entity.py
import pytest
from localport.domain.entities.service import Service, ServiceStatus

class TestService:
    """Unit tests for Service entity."""
    
    def test_create_service(self):
        """Test service creation with valid data."""
        service = Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test"}
        )
        
        assert service.name == "test-service"
        assert service.status == ServiceStatus.STOPPED
    
    def test_service_validation(self):
        """Test service validation rules."""
        with pytest.raises(ValueError):
            Service.create(
                name="",  # Invalid empty name
                technology=ForwardingTechnology.KUBECTL,
                local_port=8080,
                remote_port=80,
                connection_info={}
            )
```

### 3. Code Quality Standards

#### Code Formatting
```bash
# Format code automatically
uv run black .

# Check formatting without changes
uv run black --check .

# Format specific file
uv run black src/localport/domain/entities/service.py
```

#### Linting
```bash
# Run linter
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .

# Check specific file
uv run ruff check src/localport/domain/entities/service.py
```

#### Type Checking
```bash
# Run type checker
uv run mypy src/

# Check specific file
uv run mypy src/localport/domain/entities/service.py

# Generate type coverage report
uv run mypy src/ --html-report mypy-report/
```

#### Pre-commit Hooks
Pre-commit hooks run automatically on `git commit`:

```bash
# Install hooks (done by setup script)
uv run pre-commit install

# Run hooks manually
uv run pre-commit run --all-files

# Update hook versions
uv run pre-commit autoupdate
```

### 4. Debugging

#### Local Development
```bash
# Run with debug logging
localport --log-level DEBUG start --all

# Use verbose mode
localport --verbose start postgres

# Check configuration
localport config validate --strict
```

#### Python Debugging
```python
# Add breakpoints in code
import pdb; pdb.set_trace()

# Or use modern debugger
import ipdb; ipdb.set_trace()

# For async code
import asyncio
import pdb
pdb.set_trace()
```

#### Testing with Real Services
```bash
# Start local Kubernetes cluster
kind create cluster --name localport-dev

# Deploy test services
kubectl apply -f tests/fixtures/k8s/

# Test with real services
localport --config tests/fixtures/sample_configs/localport.yaml start --all
```

### 5. Configuration Development

#### Working with Configuration
```bash
# Validate configuration during development
localport config validate

# Export current configuration
localport config export --output dev-config.yaml

# Test hot reloading
# 1. Start daemon
localport daemon start --auto-start

# 2. Edit configuration file
vim localport.yaml

# 3. Check if changes applied
localport status
```

#### Environment Variables
```bash
# Set up development environment
export DEV_KUBE_CONTEXT=kind-localport-dev
export DEV_DB_PASSWORD=devpass
export LOCALPORT_LOG_LEVEL=DEBUG

# Use .env file for development
echo "DEV_KUBE_CONTEXT=kind-localport-dev" > .env
echo "DEV_DB_PASSWORD=devpass" >> .env
```

## Common Development Tasks

### Adding a New CLI Command

1. **Create command function**:
```python
# src/localport/cli/commands/new_commands.py
import typer
from rich.console import Console

console = Console()

def new_command(
    name: str = typer.Argument(..., help="Name parameter"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
):
    """New command description."""
    if verbose:
        console.print(f"Processing {name} with verbose output")
    else:
        console.print(f"Processing {name}")
```

2. **Register command**:
```python
# src/localport/cli/app.py
from .commands.new_commands import new_command

app.command(name="new")(new_command)
```

3. **Add tests**:
```python
# tests/unit/cli/test_new_commands.py
from typer.testing import CliRunner
from localport.cli.app import app

runner = CliRunner()

def test_new_command():
    result = runner.invoke(app, ["new", "test-name"])
    assert result.exit_code == 0
    assert "Processing test-name" in result.stdout
```

### Adding Configuration Options

1. **Update domain model**:
```python
# src/localport/domain/entities/service.py
@dataclass
class Service:
    # ... existing fields ...
    new_option: Optional[str] = None
```

2. **Update configuration schema**:
```python
# src/localport/config/models.py
class ServiceConfig(BaseModel):
    # ... existing fields ...
    new_option: Optional[str] = Field(default=None, description="New option description")
```

3. **Add validation**:
```python
@validator('new_option')
def validate_new_option(cls, v):
    if v and len(v) < 3:
        raise ValueError('New option must be at least 3 characters')
    return v
```

### Performance Optimization

#### Profiling
```bash
# Profile specific operations
python -m cProfile -o profile.stats -m localport start --all

# Analyze profile
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
"
```

#### Memory Usage
```bash
# Monitor memory usage
python -m memory_profiler localport start --all

# Add memory profiling to code
from memory_profiler import profile

@profile
def memory_intensive_function():
    # Function implementation
    pass
```

#### Async Performance
```python
# Use asyncio debugging
import asyncio
import logging

# Enable asyncio debug mode
asyncio.get_event_loop().set_debug(True)
logging.getLogger('asyncio').setLevel(logging.DEBUG)
```

## Troubleshooting Common Issues

### Development Environment Issues

#### UV Installation Problems
```bash
# Reinstall UV
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Clear UV cache
uv cache clean

# Reinstall dependencies
rm -rf .venv
uv venv --python 3.13
uv sync --dev
```

#### Python Version Issues
```bash
# Check Python version
python --version

# Install Python 3.13 (Ubuntu/Debian)
sudo apt update
sudo apt install python3.13 python3.13-venv

# Install Python 3.13 (macOS with Homebrew)
brew install python@3.13
```

#### Import Errors
```bash
# Check if package is installed in development mode
pip list | grep localport

# Reinstall in development mode
uv pip install -e .

# Check Python path
python -c "import sys; print(sys.path)"
```

### Testing Issues

#### Test Discovery Problems
```bash
# Run with verbose test discovery
uv run pytest --collect-only

# Check test file naming
# Files must be named test_*.py or *_test.py
# Classes must be named Test*
# Functions must be named test_*
```

#### Async Test Issues
```python
# Ensure async tests are marked
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

#### Mock and Fixture Issues
```python
# Use pytest fixtures properly
@pytest.fixture
def sample_service():
    return Service.create(
        name="test",
        technology=ForwardingTechnology.KUBECTL,
        local_port=8080,
        remote_port=80,
        connection_info={}
    )

def test_with_fixture(sample_service):
    assert sample_service.name == "test"
```

### Code Quality Issues

#### Type Checking Errors
```bash
# Common mypy issues and solutions

# Missing type annotations
def function(param):  # Error: missing type annotation
    pass

def function(param: str) -> None:  # Fixed
    pass

# Import issues
from typing import Optional, List, Dict, Any

# Async function annotations
async def async_function() -> Optional[str]:
    return None
```

#### Linting Errors
```bash
# Common ruff issues

# Line too long (E501)
# Break long lines
very_long_variable_name = some_function_with_many_parameters(
    parameter1, parameter2, parameter3
)

# Unused imports (F401)
# Remove unused imports or use # noqa: F401

# Missing docstrings (D100)
def function():
    """Function docstring."""
    pass
```

## Best Practices

### Code Organization

1. **Follow hexagonal architecture layers**
2. **Keep domain logic pure** (no external dependencies)
3. **Use dependency injection** for testability
4. **Implement interfaces** before concrete classes
5. **Write tests first** when possible

### Error Handling

```python
# Domain layer - raise domain exceptions
class InvalidServiceConfiguration(Exception):
    """Raised when service configuration is invalid."""
    pass

# Application layer - catch and translate
try:
    service = Service.create(...)
except InvalidServiceConfiguration as e:
    logger.error("Service configuration error", error=str(e))
    raise ServiceCreationError(f"Failed to create service: {e}")

# CLI layer - user-friendly messages
try:
    await use_case.execute(command)
except ServiceCreationError as e:
    console.print(f"[red]Error:[/red] {e}")
    raise typer.Exit(1)
```

### Logging

```python
import structlog

logger = structlog.get_logger()

# Good logging practices
logger.info("Service started", 
           service_name=service.name,
           local_port=service.local_port,
           process_id=process_id)

# Avoid string formatting in log messages
logger.error("Service failed", 
            service_name=service.name,
            error=str(exception))
```

### Documentation

1. **Write docstrings** for all public functions and classes
2. **Update documentation** when changing behavior
3. **Include examples** in docstrings
4. **Document complex algorithms** with comments

```python
def complex_function(param: str) -> Optional[int]:
    """Process parameter and return result.
    
    Args:
        param: Input parameter to process
        
    Returns:
        Processed result or None if processing failed
        
    Example:
        >>> result = complex_function("test")
        >>> assert result == 42
    """
    # Complex processing logic here
    pass
```

## Test PyPI Publishing

For testing package distribution before publishing to production PyPI:

### Manual Test PyPI Publishing

1. **Trigger Test PyPI workflow from GitHub**:
   - Go to Actions tab in GitHub repository
   - Select "Test PyPI Publishing" workflow
   - Click "Run workflow"
   - Enter version (e.g., `0.1.0-alpha.1`)
   - Enable "Test installation after publishing"

2. **Local Test PyPI publishing**:
```bash
# Update version for testing
sed -i 's/version = ".*"/version = "0.1.0-alpha.1"/' pyproject.toml

# Build package
uv build

# Publish to Test PyPI
uv publish --index-url https://test.pypi.org/legacy/
# Enter your Test PyPI API token when prompted
```

### Testing Installation from Test PyPI

```bash
# Install from Test PyPI
pipx install --index-url https://test.pypi.org/simple/ --pip-args="--extra-index-url https://pypi.org/simple/" localport==0.1.0-alpha.1

# Test functionality
localport --version
localport --help

# Test all commands
localport config --help
localport daemon --help
localport start --help

# Clean up
pipx uninstall localport
```

### Pre-release Versioning

Use semantic versioning with pre-release identifiers:

- **Alpha releases**: `0.1.0-alpha.1`, `0.1.0-alpha.2`
- **Beta releases**: `0.1.0-beta.1`, `0.1.0-beta.2`
- **Release candidates**: `0.1.0-rc.1`, `0.1.0-rc.2`

### Automated Test PyPI Publishing

Pre-release tags automatically publish to Test PyPI:

```bash
# Create and push pre-release tag
git tag v0.1.0-alpha.1
git push origin v0.1.0-alpha.1

# This triggers:
# 1. GitHub release creation
# 2. Automatic Test PyPI publishing
# 3. Installation testing
```

### Test PyPI Troubleshooting

**Common Issues:**

1. **Package name conflicts**: Test PyPI shares namespace with PyPI
2. **Dependency resolution**: Use `--extra-index-url https://pypi.org/simple/`
3. **Version conflicts**: Ensure version doesn't exist on Test PyPI
4. **Token issues**: Verify `TEST_PYPI_API_TOKEN` secret is set correctly

**Verification Commands:**
```bash
# Check package on Test PyPI
curl -s https://test.pypi.org/pypi/localport/json | jq '.info.version'

# List available versions
curl -s https://test.pypi.org/pypi/localport/json | jq '.releases | keys'

# Check package metadata
pipx run --index-url https://test.pypi.org/simple/ --pip-args="--extra-index-url https://pypi.org/simple/" localport --version
```

This development guide provides the foundation for effective LocalPort development. For specific architectural details, see the [Architecture Guide](architecture.md), and for contribution guidelines, see [CONTRIBUTING.md](../CONTRIBUTING.md).
