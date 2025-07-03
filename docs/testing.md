# Testing Guide

This guide covers LocalPort's testing strategy, patterns, and best practices for writing and maintaining tests.

## Testing Philosophy

LocalPort follows a comprehensive testing strategy that balances speed, reliability, and maintainability:

- **Unit Tests**: Fast, isolated tests for business logic
- **Integration Tests**: Test component interactions with real dependencies
- **End-to-End Tests**: Full workflow testing with real systems
- **Contract Tests**: Ensure interface compliance across layers

## Test Structure

### Directory Organization

```
tests/
├── unit/                           # Fast, isolated tests
│   ├── domain/                     # Domain entity and value object tests
│   │   ├── test_service_entity.py
│   │   ├── test_port_value_object.py
│   │   └── test_connection_info.py
│   ├── application/                # Application service tests
│   │   ├── test_service_manager.py
│   │   ├── test_health_monitor.py
│   │   └── test_use_cases.py
│   ├── infrastructure/             # Infrastructure tests (mocked)
│   │   ├── test_adapters.py
│   │   ├── test_health_checks.py
│   │   └── test_repositories.py
│   └── cli/                        # CLI command tests
│       ├── test_service_commands.py
│       ├── test_daemon_commands.py
│       └── test_formatters.py
├── integration/                    # Tests with real dependencies
│   ├── adapters/                   # Adapter integration tests
│   │   ├── test_kubectl_adapter.py
│   │   └── test_ssh_adapter.py
│   ├── health_checks/              # Health check integration tests
│   │   ├── test_postgres_health.py
│   │   └── test_http_health.py
│   └── end_to_end/                 # Full workflow tests
│       ├── test_service_lifecycle.py
│       └── test_daemon_operations.py
├── fixtures/                       # Test data and configurations
│   ├── sample_configs/             # Sample configuration files
│   │   ├── minimal.yaml
│   │   ├── complete.yaml
│   │   └── invalid.yaml
│   ├── k8s/                        # Kubernetes test resources
│   │   ├── test-service.yaml
│   │   └── test-deployment.yaml
│   └── __init__.py
└── conftest.py                     # Shared pytest configuration
```

### Test Naming Conventions

- **Test files**: `test_*.py` or `*_test.py`
- **Test classes**: `Test*` (e.g., `TestServiceManager`)
- **Test methods**: `test_*` (e.g., `test_start_service_success`)
- **Async test methods**: `test_*` with `@pytest.mark.asyncio`

## Unit Testing

### Domain Layer Testing

Domain tests focus on business logic without external dependencies:

```python
# tests/unit/domain/test_service_entity.py
import pytest
from localport.domain.entities.service import Service, ServiceStatus
from localport.domain.value_objects.port import Port
from localport.domain.value_objects.connection_info import ConnectionInfo

class TestService:
    """Unit tests for Service entity."""
    
    def test_create_service_success(self):
        """Test successful service creation with valid data."""
        service = Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test-service"}
        )
        
        assert service.name == "test-service"
        assert service.technology == ForwardingTechnology.KUBECTL
        assert service.local_port == Port(8080)
        assert service.remote_port == Port(80)
        assert service.status == ServiceStatus.STOPPED
        assert service.enabled is True
    
    def test_create_service_with_invalid_name(self):
        """Test service creation fails with invalid name."""
        with pytest.raises(ValueError, match="Service name cannot be empty"):
            Service.create(
                name="",
                technology=ForwardingTechnology.KUBECTL,
                local_port=8080,
                remote_port=80,
                connection_info={}
            )
    
    def test_create_service_with_invalid_port(self):
        """Test service creation fails with invalid port."""
        with pytest.raises(ValueError, match="Port must be between 1 and 65535"):
            Service.create(
                name="test",
                technology=ForwardingTechnology.KUBECTL,
                local_port=0,  # Invalid port
                remote_port=80,
                connection_info={}
            )
    
    def test_service_start_transition(self):
        """Test service status transition when starting."""
        service = Service.create(
            name="test",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={}
        )
        
        # Start the service
        service.start(process_id=12345)
        
        assert service.status == ServiceStatus.RUNNING
        assert service.process_id == 12345
        assert service.started_at is not None
    
    def test_service_stop_transition(self):
        """Test service status transition when stopping."""
        service = Service.create(
            name="test",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={}
        )
        
        # Start then stop the service
        service.start(process_id=12345)
        service.stop()
        
        assert service.status == ServiceStatus.STOPPED
        assert service.process_id is None
        assert service.stopped_at is not None
```

### Application Layer Testing

Application tests focus on use cases and service orchestration:

```python
# tests/unit/application/test_service_manager.py
import pytest
from unittest.mock import AsyncMock, Mock
from localport.application.services.service_manager import ServiceManager
from localport.domain.entities.service import Service
from localport.infrastructure.adapters.base_adapter import BaseAdapter

class TestServiceManager:
    """Unit tests for ServiceManager."""
    
    @pytest.fixture
    def mock_adapter_factory(self):
        """Mock adapter factory."""
        factory = Mock()
        adapter = AsyncMock(spec=BaseAdapter)
        adapter.start_port_forward.return_value = 12345
        factory.create_adapter.return_value = adapter
        return factory, adapter
    
    @pytest.fixture
    def service_manager(self, mock_adapter_factory):
        """Create ServiceManager with mocked dependencies."""
        factory, _ = mock_adapter_factory
        return ServiceManager(adapter_factory=factory)
    
    @pytest.fixture
    def sample_service(self):
        """Create a sample service for testing."""
        return Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test"}
        )
    
    @pytest.mark.asyncio
    async def test_start_service_success(
        self, 
        service_manager, 
        sample_service, 
        mock_adapter_factory
    ):
        """Test successful service startup."""
        _, mock_adapter = mock_adapter_factory
        
        result = await service_manager.start_service(sample_service)
        
        assert result.success is True
        assert sample_service.status == ServiceStatus.RUNNING
        assert sample_service.process_id == 12345
        mock_adapter.start_port_forward.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_service_failure(
        self, 
        service_manager, 
        sample_service, 
        mock_adapter_factory
    ):
        """Test service startup failure handling."""
        _, mock_adapter = mock_adapter_factory
        mock_adapter.start_port_forward.side_effect = Exception("Port in use")
        
        result = await service_manager.start_service(sample_service)
        
        assert result.success is False
        assert "Port in use" in result.error_message
        assert sample_service.status == ServiceStatus.STOPPED
    
    @pytest.mark.asyncio
    async def test_stop_service_success(
        self, 
        service_manager, 
        sample_service, 
        mock_adapter_factory
    ):
        """Test successful service shutdown."""
        _, mock_adapter = mock_adapter_factory
        
        # Start the service first
        await service_manager.start_service(sample_service)
        
        # Then stop it
        result = await service_manager.stop_service(sample_service)
        
        assert result.success is True
        assert sample_service.status == ServiceStatus.STOPPED
        mock_adapter.stop_port_forward.assert_called_once_with(12345)
```

### Infrastructure Layer Testing

Infrastructure tests use mocks to isolate external dependencies:

```python
# tests/unit/infrastructure/test_kubectl_adapter.py
import pytest
from unittest.mock import AsyncMock, patch
from localport.infrastructure.adapters.kubectl_adapter import KubectlAdapter

class TestKubectlAdapter:
    """Unit tests for KubectlAdapter."""
    
    @pytest.fixture
    def adapter(self):
        """Create KubectlAdapter instance."""
        return KubectlAdapter()
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_start_port_forward_success(self, mock_subprocess, adapter):
        """Test successful kubectl port-forward startup."""
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_subprocess.return_value = mock_process
        
        connection_info = {
            "resource_name": "test-service",
            "namespace": "default"
        }
        
        process_id = await adapter.start_port_forward(
            local_port=8080,
            remote_port=80,
            connection_info=connection_info
        )
        
        assert process_id == 12345
        mock_subprocess.assert_called_once()
        
        # Verify kubectl command
        call_args = mock_subprocess.call_args[0]
        assert call_args[0] == "kubectl"
        assert "port-forward" in call_args
        assert "8080:80" in call_args
    
    @pytest.mark.asyncio
    @patch('asyncio.create_subprocess_exec')
    async def test_start_port_forward_failure(self, mock_subprocess, adapter):
        """Test kubectl port-forward startup failure."""
        # Mock subprocess failure
        mock_subprocess.side_effect = OSError("kubectl not found")
        
        connection_info = {
            "resource_name": "test-service",
            "namespace": "default"
        }
        
        with pytest.raises(Exception, match="kubectl not found"):
            await adapter.start_port_forward(
                local_port=8080,
                remote_port=80,
                connection_info=connection_info
            )
```

### CLI Testing

CLI tests use Typer's testing utilities:

```python
# tests/unit/cli/test_service_commands.py
import pytest
from typer.testing import CliRunner
from unittest.mock import AsyncMock, patch
from localport.cli.app import app

class TestServiceCommands:
    """Unit tests for service CLI commands."""
    
    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()
    
    def test_start_command_help(self, runner):
        """Test start command help output."""
        result = runner.invoke(app, ["start", "--help"])
        
        assert result.exit_code == 0
        assert "Start port forwarding services" in result.stdout
        assert "--all" in result.stdout
        assert "--tag" in result.stdout
    
    @patch('localport.cli.commands.service_commands.start_services_use_case')
    def test_start_all_services(self, mock_use_case, runner):
        """Test starting all services."""
        mock_use_case.execute = AsyncMock(return_value=Mock(success=True))
        
        result = runner.invoke(app, ["start", "--all"])
        
        assert result.exit_code == 0
        assert "Starting all services" in result.stdout
        mock_use_case.execute.assert_called_once()
    
    @patch('localport.cli.commands.service_commands.start_services_use_case')
    def test_start_specific_services(self, mock_use_case, runner):
        """Test starting specific services."""
        mock_use_case.execute = AsyncMock(return_value=Mock(success=True))
        
        result = runner.invoke(app, ["start", "postgres", "redis"])
        
        assert result.exit_code == 0
        mock_use_case.execute.assert_called_once()
        
        # Verify command arguments
        call_args = mock_use_case.execute.call_args[0][0]
        assert call_args.service_names == ["postgres", "redis"]
    
    @patch('localport.cli.commands.service_commands.start_services_use_case')
    def test_start_services_by_tag(self, mock_use_case, runner):
        """Test starting services by tag."""
        mock_use_case.execute = AsyncMock(return_value=Mock(success=True))
        
        result = runner.invoke(app, ["start", "--tag", "database"])
        
        assert result.exit_code == 0
        call_args = mock_use_case.execute.call_args[0][0]
        assert call_args.tags == ["database"]
```

## Integration Testing

### Adapter Integration Tests

Integration tests verify adapters work with real external systems:

```python
# tests/integration/adapters/test_kubectl_adapter.py
import pytest
import asyncio
from localport.infrastructure.adapters.kubectl_adapter import KubectlAdapter

@pytest.mark.integration
class TestKubectlAdapterIntegration:
    """Integration tests for KubectlAdapter with real kubectl."""
    
    @pytest.fixture
    def adapter(self):
        """Create KubectlAdapter instance."""
        return KubectlAdapter()
    
    @pytest.mark.asyncio
    async def test_kubectl_available(self, adapter):
        """Test that kubectl is available and configured."""
        # This test verifies the test environment is set up correctly
        process = await asyncio.create_subprocess_exec(
            "kubectl", "version", "--client",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        assert process.returncode == 0, f"kubectl not available: {stderr.decode()}"
        assert "Client Version" in stdout.decode()
    
    @pytest.mark.asyncio
    async def test_port_forward_real_service(self, adapter):
        """Test port forwarding to a real Kubernetes service."""
        # This test requires a running Kubernetes cluster with a test service
        connection_info = {
            "resource_name": "kubernetes",  # API server service
            "namespace": "default"
        }
        
        try:
            process_id = await adapter.start_port_forward(
                local_port=8080,
                remote_port=443,
                connection_info=connection_info
            )
            
            assert process_id is not None
            
            # Wait a moment for port forward to establish
            await asyncio.sleep(2)
            
            # Verify the process is running
            process = await adapter._get_process(process_id)
            assert process is not None
            assert process.returncode is None
            
        finally:
            # Always cleanup
            if 'process_id' in locals():
                await adapter.stop_port_forward(process_id)
    
    @pytest.mark.asyncio
    async def test_port_forward_nonexistent_service(self, adapter):
        """Test port forwarding to a nonexistent service fails gracefully."""
        connection_info = {
            "resource_name": "nonexistent-service",
            "namespace": "default"
        }
        
        with pytest.raises(Exception):
            await adapter.start_port_forward(
                local_port=8080,
                remote_port=80,
                connection_info=connection_info
            )
```

### Health Check Integration Tests

```python
# tests/integration/health_checks/test_postgres_health.py
import pytest
import asyncio
from localport.infrastructure.health_checks.postgres_health_check import PostgresHealthCheck

@pytest.mark.integration
class TestPostgresHealthCheckIntegration:
    """Integration tests for PostgreSQL health checks."""
    
    @pytest.fixture
    def health_checker(self):
        """Create PostgreSQL health checker."""
        config = {
            "database": "postgres",
            "user": "postgres",
            "password": "testpass",
            "host": "localhost",
            "port": 5432
        }
        return PostgresHealthCheck(config)
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, health_checker):
        """Test successful health check against real PostgreSQL."""
        # This test requires a running PostgreSQL instance
        result = await health_checker.check()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_connection_failure(self):
        """Test health check failure with invalid connection."""
        config = {
            "database": "postgres",
            "user": "postgres",
            "password": "wrongpass",
            "host": "localhost",
            "port": 5432
        }
        health_checker = PostgresHealthCheck(config)
        
        result = await health_checker.check()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Test health check timeout with unreachable host."""
        config = {
            "database": "postgres",
            "user": "postgres",
            "password": "testpass",
            "host": "192.0.2.1",  # RFC 5737 test address
            "port": 5432
        }
        health_checker = PostgresHealthCheck(config)
        
        # This should timeout quickly
        start_time = asyncio.get_event_loop().time()
        result = await health_checker.check()
        end_time = asyncio.get_event_loop().time()
        
        assert result is False
        assert end_time - start_time < 10  # Should timeout within 10 seconds
```

## End-to-End Testing

### Full Workflow Tests

```python
# tests/integration/end_to_end/test_service_lifecycle.py
import pytest
import asyncio
import tempfile
import yaml
from pathlib import Path
from localport.cli.app import app
from typer.testing import CliRunner

@pytest.mark.e2e
class TestServiceLifecycle:
    """End-to-end tests for complete service lifecycle."""
    
    @pytest.fixture
    def test_config(self):
        """Create a temporary test configuration."""
        config = {
            "version": "1.0",
            "services": [
                {
                    "name": "test-service",
                    "technology": "kubectl",
                    "local_port": 8080,
                    "remote_port": 443,
                    "connection": {
                        "resource_name": "kubernetes",
                        "namespace": "default"
                    },
                    "enabled": True,
                    "health_check": {
                        "type": "tcp",
                        "interval": 10,
                        "timeout": 5.0,
                        "failure_threshold": 2
                    }
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            return Path(f.name)
    
    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()
    
    def test_complete_service_lifecycle(self, runner, test_config):
        """Test complete service lifecycle: start, status, stop."""
        try:
            # Validate configuration
            result = runner.invoke(app, ["--config", str(test_config), "config", "validate"])
            assert result.exit_code == 0
            
            # Start service
            result = runner.invoke(app, ["--config", str(test_config), "start", "--all"])
            assert result.exit_code == 0
            
            # Check status
            result = runner.invoke(app, ["--config", str(test_config), "status"])
            assert result.exit_code == 0
            assert "test-service" in result.stdout
            assert "Running" in result.stdout
            
            # Stop service
            result = runner.invoke(app, ["--config", str(test_config), "stop", "--all"])
            assert result.exit_code == 0
            
            # Verify stopped
            result = runner.invoke(app, ["--config", str(test_config), "status"])
            assert result.exit_code == 0
            assert "Stopped" in result.stdout
            
        finally:
            # Cleanup
            test_config.unlink()
    
    def test_daemon_mode_lifecycle(self, runner, test_config):
        """Test daemon mode service management."""
        try:
            # Start daemon
            result = runner.invoke(app, ["--config", str(test_config), "daemon", "start"])
            assert result.exit_code == 0
            
            # Check daemon status
            result = runner.invoke(app, ["daemon", "status"])
            assert result.exit_code == 0
            assert "Running" in result.stdout
            
            # Start services via daemon
            result = runner.invoke(app, ["start", "--all"])
            assert result.exit_code == 0
            
            # Check service status
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            
            # Stop daemon
            result = runner.invoke(app, ["daemon", "stop"])
            assert result.exit_code == 0
            
        finally:
            # Cleanup
            test_config.unlink()
```

## Test Configuration

### pytest Configuration

```python
# conftest.py
import pytest
import asyncio
from typing import Generator

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_config():
    """Provide a mock configuration for testing."""
    return {
        "version": "1.0",
        "services": [
            {
                "name": "test-service",
                "technology": "kubectl",
                "local_port": 8080,
                "remote_port": 80,
                "connection": {"resource_name": "test"},
                "enabled": True
            }
        ]
    }

@pytest.fixture
def sample_service():
    """Create a sample service for testing."""
    from localport.domain.entities.service import Service, ForwardingTechnology
    
    return Service.create(
        name="test-service",
        technology=ForwardingTechnology.KUBECTL,
        local_port=8080,
        remote_port=80,
        connection_info={"resource_name": "test"}
    )
```

### pytest.ini Configuration

```ini
# pytest.ini
[tool:pytest]
minversion = 6.0
addopts = 
    -ra
    --strict-markers
    --strict-config
    --cov=src/localport
    --cov-report=term-missing
    --cov-report=html
    --cov-report=xml
testpaths = tests
python_files = test_*.py *_test.py
python_classes = Test*
python_functions = test_*
markers =
    integration: Integration tests that require external dependencies
    e2e: End-to-end tests that test complete workflows
    slow: Tests that take a long time to run
    unit: Fast unit tests (default)
filterwarnings =
    error
    ignore::UserWarning
    ignore::DeprecationWarning
```

## Running Tests

### Basic Test Execution

```bash
# Run all tests
uv run pytest

# Run only unit tests
uv run pytest tests/unit/

# Run only integration tests
uv run pytest tests/integration/

# Run tests with coverage
uv run pytest --cov=src/localport --cov-report=html

# Run specific test file
uv run pytest tests/unit/domain/test_service_entity.py

# Run specific test method
uv run pytest tests/unit/domain/test_service_entity.py::TestService::test_create_service
```

### Test Filtering

```bash
# Run tests by marker
uv run pytest -m "not integration"  # Skip integration tests
uv run pytest -m "integration"      # Only integration tests
uv run pytest -m "not slow"         # Skip slow tests

# Run tests by keyword
uv run pytest -k "test_start"       # Tests with "start" in name
uv run pytest -k "Service"          # Tests with "Service" in name

# Run failed tests from last run
uv run pytest --lf

# Run tests in parallel (with pytest-xdist)
uv run pytest -n auto
```

### Continuous Integration

```bash
# CI test command (fast tests only)
uv run pytest tests/unit/ -v --cov=src/localport --cov-report=xml

# Full test suite (including integration)
uv run pytest -v --cov=src/localport --cov-report=xml

# Performance testing
uv run pytest tests/integration/ -v --durations=10
```

## Test Data Management

### Fixtures and Test Data

```python
# tests/fixtures/test_data.py
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class TestServiceConfig:
    """Test service configuration data."""
    name: str
    technology: str
    local_port: int
    remote_port: int
    connection: Dict[str, Any]
    enabled: bool = True

# Common test configurations
KUBECTL_SERVICE = TestServiceConfig(
    name="kubectl-test",
    technology="kubectl",
    local_port=8080,
    remote_port=80,
    connection={"resource_name": "test-service", "namespace": "default"}
)

SSH_SERVICE = TestServiceConfig(
    name="ssh-test",
    technology="ssh",
    local_port=8080,
    remote_port=80,
    connection={"host": "example.com", "user": "test", "key_file": "~/.ssh/id_rsa"}
)
```

### Mock Patterns

```python
# tests/unit/mocks.py
from unittest.mock import AsyncMock, Mock
from localport.infrastructure.adapters.base_adapter import BaseAdapter

class MockAdapter(AsyncMock):
    """Mock adapter for testing."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(spec=BaseAdapter, *args, **kwargs)
        self.start_port_forward.return_value = 12345
        self.stop_port_forward.return_value = None
        self.is_running.return_value = True

def create_mock_service_manager():
    """Create a mock service manager."""
    manager = Mock()
    manager.start_service = AsyncMock(return_value=Mock(success=True))
    manager.stop_service = AsyncMock(return_value=Mock(success=True))
    manager.get_service_status = Mock(return_value=Mock(status="running"))
    return manager
```

## Performance Testing

### Load Testing

```python
# tests/performance/test_concurrent_operations.py
import pytest
import asyncio
from localport.application.services.service_manager import ServiceManager

@pytest.mark.performance
class TestConcurrentOperations:
    """Performance tests for concurrent operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_service_starts(self):
        """Test starting multiple services concurrently."""
        service_manager = ServiceManager()
        services = [create_test_service(f"service-{i}") for i in range(10)]
        
        start_time = asyncio.get_event_loop().time()
        
        # Start all services concurrently
        tasks = [service_manager.start_service(service) for service in services]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time
        
        # Verify all services started successfully
        assert all(result.success for result in results if not isinstance(result, Exception))
        
        # Performance assertion (adjust based on requirements)
        assert duration < 5.0, f"Concurrent start took {duration:.2f}s, expected < 5.0s"
```

### Memory Testing

```python
# tests/performance/test_memory_usage.py
import pytest
import psutil
import os
from localport.application.services.health_monitor import HealthMonitor

@pytest.mark.performance
class TestMemoryUsage:
    """Memory usage tests."""
    
    def test_health_monitor_memory_usage(self):
        """Test health monitor memory usage over time."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create health monitor with many services
        health_monitor = HealthMonitor()
        services = [create_test_service(f"service-{i}") for i in range(100)]
        
        for service in services:
            health_monitor.add_service(service)
        
        current_memory = process.memory_info().rss
        memory_increase = current_memory - initial_memory
        
        # Memory increase should be reasonable (adjust threshold as needed)
        assert memory_increase < 50 * 1024 * 1024, f"Memory increased by {memory_increase / 1024 / 1024:.2f}MB"
```

## Best Practices

### Test Organization

1. **Group related tests** in classes
2. **Use descriptive test names** that explain what is being tested
3. **Follow AAA pattern**: Arrange, Act, Assert
4. **Keep tests independent** - no test should depend on another
5. **Use fixtures** for common setup and teardown

### Mocking Guidelines

1. **Mock external dependencies** in unit tests
2. **Use real dependencies** in integration tests
3. **Mock at the boundary** of your system
4. **Verify mock interactions** when behavior matters
5. **Reset mocks** between tests

### Async Testing

1. **Mark async tests** with `@pytest.mark.asyncio`
2. **Use AsyncMock** for async dependencies
3. **Handle async exceptions** properly
4. **Test timeout scenarios** with `asyncio.wait_for`
5. **Clean up async resources** in finally blocks

### Test Data

1. **Use factories** for creating test objects
2. **Keep test data minimal** but realistic
3. **Use fixtures** for reusable test data
4. **Avoid hardcoded values** that might change
5. **Clean up test data** after tests

This testing guide provides comprehensive coverage of LocalPort's testing strategy and practices. For implementation details, see the [Development Guide](development.md), and for contribution guidelines, see [CONTRIBUTING.md](../CONTRIBUTING.md).
