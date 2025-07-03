# LocalPort Implementation Design - Python

## Overview

This document provides a comprehensive implementation design for LocalPort, a universal port forwarding manager, using hexagonal architecture and modern Python best practices. The design emphasizes clean separation of concerns, testability, and extensibility while leveraging the latest Python tooling and libraries.

## Architecture Overview

### Hexagonal Architecture (Ports and Adapters)

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│                    (Typer + Rich)                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 Application Layer                           │
│              (Use Cases & Services)                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Service Manager │  │ Health Monitor  │  │ Config Mgr   │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   Domain Layer                              │
│                (Business Logic)                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │ Port Forward    │  │ Health Check    │  │ Service      │ │
│  │ Entities        │  │ Strategies      │  │ Definitions  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                Infrastructure Layer                         │
│                 (Adapters & Ports)                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────┐ │
│  │ Kubectl     │ │ SSH         │ │ File System │ │ Process│ │
│  │ Adapter     │ │ Adapter     │ │ Adapter     │ │ Manager│ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
localport/
├── src/
│   └── localport/
│       ├── __init__.py
│       ├── main.py                    # Entry point
│       ├── domain/                    # Core business logic
│       │   ├── __init__.py
│       │   ├── entities/
│       │   │   ├── __init__.py
│       │   │   ├── service.py         # Service entity
│       │   │   ├── port_forward.py    # Port forward entity
│       │   │   └── health_check.py    # Health check entity
│       │   ├── value_objects/
│       │   │   ├── __init__.py
│       │   │   ├── port.py            # Port value object
│       │   │   └── connection_info.py # Connection details
│       │   ├── repositories/
│       │   │   ├── __init__.py
│       │   │   ├── service_repository.py
│       │   │   └── config_repository.py
│       │   └── services/
│       │       ├── __init__.py
│       │       └── domain_services.py
│       ├── application/               # Use cases and application services
│       │   ├── __init__.py
│       │   ├── use_cases/
│       │   │   ├── __init__.py
│       │   │   ├── start_services.py
│       │   │   ├── stop_services.py
│       │   │   ├── monitor_services.py
│       │   │   └── manage_daemon.py
│       │   ├── services/
│       │   │   ├── __init__.py
│       │   │   ├── service_manager.py
│       │   │   ├── health_monitor.py
│       │   │   └── daemon_manager.py
│       │   └── dto/
│       │       ├── __init__.py
│       │       └── service_dto.py
│       ├── infrastructure/            # External adapters
│       │   ├── __init__.py
│       │   ├── adapters/
│       │   │   ├── __init__.py
│       │   │   ├── kubectl_adapter.py
│       │   │   ├── ssh_adapter.py
│       │   │   ├── file_config_adapter.py
│       │   │   └── process_adapter.py
│       │   ├── repositories/
│       │   │   ├── __init__.py
│       │   │   ├── yaml_config_repository.py
│       │   │   └── memory_service_repository.py
│       │   ├── health_checks/
│       │   │   ├── __init__.py
│       │   │   ├── tcp_health_check.py
│       │   │   ├── http_health_check.py
│       │   │   ├── kafka_health_check.py
│       │   │   └── postgres_health_check.py
│       │   └── logging/
│       │       ├── __init__.py
│       │       └── structured_logger.py
│       ├── cli/                       # Command-line interface
│       │   ├── __init__.py
│       │   ├── app.py                 # Main Typer app
│       │   ├── commands/
│       │   │   ├── __init__.py
│       │   │   ├── start.py
│       │   │   ├── stop.py
│       │   │   ├── status.py
│       │   │   └── daemon.py
│       │   ├── formatters/
│       │   │   ├── __init__.py
│       │   │   ├── table_formatter.py
│       │   │   └── json_formatter.py
│       │   └── utils/
│       │       ├── __init__.py
│       │       └── rich_utils.py
│       └── config/
│           ├── __init__.py
│           ├── settings.py
│           └── models.py
├── tests/
│   ├── unit/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── cli/
│   ├── integration/
│   │   ├── adapters/
│   │   └── end_to_end/
│   └── fixtures/
│       └── sample_configs/
├── docs/
│   ├── architecture.md
│   ├── configuration.md
│   └── development.md
├── scripts/
│   ├── setup-dev.sh
│   └── run-tests.sh
├── pyproject.toml
├── uv.lock
├── README.md
└── .gitignore
```

## Technology Stack

### Core Dependencies

```toml
[project]
name = "localport"
version = "0.1.0"
description = "Universal port forwarding manager with health monitoring"
requires-python = ">=3.13"
dependencies = [
    "typer[all]>=0.12.0",           # Modern CLI framework
    "rich>=13.7.0",                 # Rich text and beautiful formatting
    "pydantic>=2.8.0",              # Data validation and settings
    "pydantic-settings>=2.4.0",     # Settings management
    "pyyaml>=6.0.1",                # YAML configuration parsing
    "asyncio-mqtt>=0.16.0",         # Async MQTT for health checks
    "aiohttp>=3.9.0",               # Async HTTP client
    "psutil>=5.9.0",                # Cross-platform process utilities
    "structlog>=24.1.0",            # Structured logging
    "tenacity>=8.2.0",              # Retry logic with backoff
    "click>=8.1.0",                 # CLI utilities (Typer dependency)
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.12.0",
    "black>=24.0.0",
    "ruff>=0.5.0",
    "mypy>=1.10.0",
    "pre-commit>=3.7.0",
]
kafka = [
    "kafka-python>=2.0.2",         # Kafka health checks
]
postgres = [
    "psycopg[binary]>=3.2.0",      # PostgreSQL health checks
]
```

### Development Tools

- **UV**: Fast Python package installer and resolver
- **Virtual Environments**: Mandatory isolation for all environments
- **Black**: Code formatting
- **Ruff**: Fast Python linter
- **MyPy**: Static type checking
- **Pre-commit**: Git hooks for code quality

## Core Domain Design

### Domain Entities

```python
# src/localport/domain/entities/service.py
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

class ServiceStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"
    RESTARTING = "restarting"

class ForwardingTechnology(Enum):
    KUBECTL = "kubectl"
    SSH = "ssh"

@dataclass
class Service:
    """Core service entity representing a port forwarding service."""
    
    id: UUID
    name: str
    technology: ForwardingTechnology
    local_port: int
    remote_port: int
    connection_info: Dict[str, Any]
    status: ServiceStatus = ServiceStatus.STOPPED
    health_check_config: Optional[Dict[str, Any]] = None
    restart_policy: Optional[Dict[str, Any]] = None
    tags: list[str] = None
    description: Optional[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    @classmethod
    def create(
        cls,
        name: str,
        technology: ForwardingTechnology,
        local_port: int,
        remote_port: int,
        connection_info: Dict[str, Any],
        **kwargs
    ) -> "Service":
        """Factory method to create a new service."""
        return cls(
            id=uuid4(),
            name=name,
            technology=technology,
            local_port=local_port,
            remote_port=remote_port,
            connection_info=connection_info,
            **kwargs
        )
    
    def is_healthy(self) -> bool:
        """Check if service is in a healthy state."""
        return self.status == ServiceStatus.RUNNING
    
    def can_restart(self) -> bool:
        """Check if service can be restarted."""
        return self.status in [ServiceStatus.FAILED, ServiceStatus.STOPPED]
```

### Port Forward Entity

```python
# src/localport/domain/entities/port_forward.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

@dataclass
class PortForward:
    """Represents an active port forwarding process."""
    
    service_id: UUID
    process_id: Optional[int]
    local_port: int
    remote_port: int
    started_at: datetime
    last_health_check: Optional[datetime] = None
    restart_count: int = 0
    
    def is_process_alive(self) -> bool:
        """Check if the underlying process is still alive."""
        if not self.process_id:
            return False
        
        try:
            import psutil
            return psutil.pid_exists(self.process_id)
        except Exception:
            return False
    
    def increment_restart_count(self) -> None:
        """Increment the restart counter."""
        self.restart_count += 1
```

### Repository Interfaces

```python
# src/localport/domain/repositories/service_repository.py
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from ..entities.service import Service

class ServiceRepository(ABC):
    """Repository interface for service persistence."""
    
    @abstractmethod
    async def save(self, service: Service) -> None:
        """Save a service."""
        pass
    
    @abstractmethod
    async def find_by_id(self, service_id: UUID) -> Optional[Service]:
        """Find a service by ID."""
        pass
    
    @abstractmethod
    async def find_by_name(self, name: str) -> Optional[Service]:
        """Find a service by name."""
        pass
    
    @abstractmethod
    async def find_all(self) -> List[Service]:
        """Find all services."""
        pass
    
    @abstractmethod
    async def find_by_tags(self, tags: List[str]) -> List[Service]:
        """Find services by tags."""
        pass
    
    @abstractmethod
    async def delete(self, service_id: UUID) -> None:
        """Delete a service."""
        pass
```

## Application Layer Design

### Use Cases

```python
# src/localport/application/use_cases/start_services.py
from dataclasses import dataclass
from typing import List, Optional
import structlog

from ..services.service_manager import ServiceManager
from ..dto.service_dto import ServiceStartResult
from ...domain.repositories.service_repository import ServiceRepository

logger = structlog.get_logger()

@dataclass
class StartServicesCommand:
    """Command to start services."""
    service_names: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    all_services: bool = False

class StartServicesUseCase:
    """Use case for starting port forwarding services."""
    
    def __init__(
        self,
        service_repository: ServiceRepository,
        service_manager: ServiceManager
    ):
        self._service_repository = service_repository
        self._service_manager = service_manager
    
    async def execute(self, command: StartServicesCommand) -> List[ServiceStartResult]:
        """Execute the start services use case."""
        logger.info("Starting services", command=command)
        
        # Determine which services to start
        services = await self._resolve_services(command)
        
        # Start each service
        results = []
        for service in services:
            try:
                result = await self._service_manager.start_service(service)
                results.append(result)
                logger.info("Service started", service_name=service.name, result=result)
            except Exception as e:
                logger.error("Failed to start service", service_name=service.name, error=str(e))
                results.append(ServiceStartResult(
                    service_name=service.name,
                    success=False,
                    error=str(e)
                ))
        
        return results
    
    async def _resolve_services(self, command: StartServicesCommand) -> List[Service]:
        """Resolve which services to start based on command."""
        if command.all_services:
            return await self._service_repository.find_all()
        elif command.tags:
            return await self._service_repository.find_by_tags(command.tags)
        elif command.service_names:
            services = []
            for name in command.service_names:
                service = await self._service_repository.find_by_name(name)
                if service:
                    services.append(service)
                else:
                    logger.warning("Service not found", service_name=name)
            return services
        else:
            return []
```

### Service Manager

```python
# src/localport/application/services/service_manager.py
from typing import Dict, List, Optional
import asyncio
import structlog
from uuid import UUID

from ...domain.entities.service import Service, ServiceStatus
from ...domain.entities.port_forward import PortForward
from ...infrastructure.adapters.kubectl_adapter import KubectlAdapter
from ...infrastructure.adapters.ssh_adapter import SSHAdapter
from ..dto.service_dto import ServiceStartResult

logger = structlog.get_logger()

class ServiceManager:
    """Manages the lifecycle of port forwarding services."""
    
    def __init__(self):
        self._active_forwards: Dict[UUID, PortForward] = {}
        self._adapters = {
            ForwardingTechnology.KUBECTL: KubectlAdapter(),
            ForwardingTechnology.SSH: SSHAdapter(),
        }
    
    async def start_service(self, service: Service) -> ServiceStartResult:
        """Start a port forwarding service."""
        logger.info("Starting service", service_name=service.name)
        
        try:
            # Check if port is available
            if not await self._is_port_available(service.local_port):
                raise ValueError(f"Port {service.local_port} is already in use")
            
            # Get appropriate adapter
            adapter = self._adapters[service.technology]
            
            # Start the port forward
            process_id = await adapter.start_port_forward(
                service.local_port,
                service.remote_port,
                service.connection_info
            )
            
            # Create port forward entity
            port_forward = PortForward(
                service_id=service.id,
                process_id=process_id,
                local_port=service.local_port,
                remote_port=service.remote_port,
                started_at=datetime.now()
            )
            
            # Store active forward
            self._active_forwards[service.id] = port_forward
            
            # Update service status
            service.status = ServiceStatus.RUNNING
            
            logger.info("Service started successfully", 
                       service_name=service.name, 
                       process_id=process_id)
            
            return ServiceStartResult(
                service_name=service.name,
                success=True,
                process_id=process_id
            )
            
        except Exception as e:
            service.status = ServiceStatus.FAILED
            logger.error("Failed to start service", 
                        service_name=service.name, 
                        error=str(e))
            raise
    
    async def stop_service(self, service: Service) -> bool:
        """Stop a port forwarding service."""
        logger.info("Stopping service", service_name=service.name)
        
        port_forward = self._active_forwards.get(service.id)
        if not port_forward:
            logger.warning("No active forward found", service_name=service.name)
            return False
        
        try:
            adapter = self._adapters[service.technology]
            await adapter.stop_port_forward(port_forward.process_id)
            
            # Remove from active forwards
            del self._active_forwards[service.id]
            
            # Update service status
            service.status = ServiceStatus.STOPPED
            
            logger.info("Service stopped successfully", service_name=service.name)
            return True
            
        except Exception as e:
            logger.error("Failed to stop service", 
                        service_name=service.name, 
                        error=str(e))
            return False
    
    async def _is_port_available(self, port: int) -> bool:
        """Check if a local port is available."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return True
        except OSError:
            return False
```

## Infrastructure Layer Design

### Kubectl Adapter

```python
# src/localport/infrastructure/adapters/kubectl_adapter.py
import asyncio
import subprocess
from typing import Dict, Any, Optional
import structlog

logger = structlog.get_logger()

class KubectlAdapter:
    """Adapter for kubectl port-forward operations."""
    
    async def start_port_forward(
        self,
        local_port: int,
        remote_port: int,
        connection_info: Dict[str, Any]
    ) -> int:
        """Start a kubectl port-forward process."""
        
        # Extract connection details
        namespace = connection_info.get('namespace', 'default')
        resource_type = connection_info.get('resource_type', 'service')
        resource_name = connection_info['resource_name']
        context = connection_info.get('context')
        
        # Build kubectl command
        cmd = [
            'kubectl', 'port-forward',
            f'{resource_type}/{resource_name}',
            f'{local_port}:{remote_port}',
            '--namespace', namespace
        ]
        
        if context:
            cmd.extend(['--context', context])
        
        logger.info("Starting kubectl port-forward", 
                   command=' '.join(cmd))
        
        try:
            # Start the process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait a moment to ensure it starts successfully
            await asyncio.sleep(1)
            
            if process.returncode is not None:
                # Process has already terminated
                stdout, stderr = await process.communicate()
                raise RuntimeError(f"kubectl port-forward failed: {stderr.decode()}")
            
            logger.info("kubectl port-forward started", 
                       pid=process.pid,
                       local_port=local_port,
                       remote_port=remote_port)
            
            return process.pid
            
        except Exception as e:
            logger.error("Failed to start kubectl port-forward", error=str(e))
            raise
    
    async def stop_port_forward(self, process_id: int) -> None:
        """Stop a kubectl port-forward process."""
        try:
            import psutil
            process = psutil.Process(process_id)
            process.terminate()
            
            # Wait for graceful termination
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                process.kill()
                process.wait()
            
            logger.info("kubectl port-forward stopped", pid=process_id)
            
        except psutil.NoSuchProcess:
            logger.warning("Process not found", pid=process_id)
        except Exception as e:
            logger.error("Failed to stop kubectl port-forward", 
                        pid=process_id, 
                        error=str(e))
            raise
```

### Health Check Strategies

```python
# src/localport/infrastructure/health_checks/tcp_health_check.py
import asyncio
import socket
from typing import Dict, Any
import structlog

logger = structlog.get_logger()

class TCPHealthCheck:
    """TCP connectivity health check."""
    
    async def check(self, host: str, port: int, timeout: float = 5.0) -> bool:
        """Perform TCP health check."""
        try:
            # Create connection with timeout
            future = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(future, timeout=timeout)
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            logger.debug("TCP health check passed", host=host, port=port)
            return True
            
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
            logger.debug("TCP health check failed", 
                        host=host, 
                        port=port, 
                        error=str(e))
            return False

# src/localport/infrastructure/health_checks/kafka_health_check.py
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import structlog

logger = structlog.get_logger()

class KafkaHealthCheck:
    """Kafka-specific health check using bootstrap servers."""
    
    async def check(self, bootstrap_servers: str, timeout: float = 10.0) -> bool:
        """Check Kafka connectivity via bootstrap servers."""
        try:
            # Create a consumer to test connectivity
            consumer = KafkaConsumer(
                bootstrap_servers=bootstrap_servers,
                consumer_timeout_ms=int(timeout * 1000),
                api_version_auto_timeout_ms=int(timeout * 1000)
            )
            
            # Try to get metadata (this will test connectivity)
            metadata = consumer.list_consumer_groups()
            consumer.close()
            
            logger.debug("Kafka health check passed", 
                        bootstrap_servers=bootstrap_servers)
            return True
            
        except KafkaError as e:
            logger.debug("Kafka health check failed", 
                        bootstrap_servers=bootstrap_servers,
                        error=str(e))
            return False
        except Exception as e:
            logger.error("Unexpected error in Kafka health check", 
                        bootstrap_servers=bootstrap_servers,
                        error=str(e))
            return False
```

## CLI Design with Typer and Rich

### Main CLI Application

```python
# src/localport/cli/app.py
import typer
from rich.console import Console
from rich.table import Table
from typing import Optional, List

from .commands import start, stop, status, daemon

console = Console()
app = typer.Typer(
    name="localport",
    help="Universal port forwarding manager with health monitoring",
    rich_markup_mode="rich"
)

# Add command groups
app.add_typer(daemon.app, name="daemon", help="Daemon management commands")

# Add individual commands
app.command()(start.start_command)
app.command()(stop.stop_command)
app.command()(status.status_command)

@app.callback()
def main(
    ctx: typer.Context,
    config_file: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging"
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        help="Set log level (DEBUG, INFO, WARN, ERROR)"
    )
):
    """LocalPort - Universal port forwarding manager."""
    # Initialize global configuration
    ctx.ensure_object(dict)
    ctx.obj['config_file'] = config_file
    ctx.obj['verbose'] = verbose
    ctx.obj['log_level'] = log_level

if __name__ == "__main__":
    app()
```

### Start Command

```python
# src/localport/cli/commands/start.py
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing import Optional, List
import asyncio

from ...application.use_cases.start_services import StartServicesUseCase, StartServicesCommand
from ..formatters.table_formatter import format_service_results

console = Console()

def start_command(
    services: Optional[List[str]] = typer.Argument(
        None,
        help="Service names to start"
    ),
    group: Optional[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="Start services by group/tag"
    ),
    all_services: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Start all configured services"
    ),
    wait: bool = typer.Option(
        True,
        "--wait/--no-wait",
        help="Wait for services to be healthy before returning"
    )
):
    """Start port forwarding services."""
    
    if not services and not group and not all_services:
        console.print("[red]Error:[/red] Must specify services, group, or --all")
        raise typer.Exit(1)
    
    # Create command
    command = StartServicesCommand(
        service_names=services,
        tags=[group] if group else None,
        all_services=all_services
    )
    
    # Execute use case
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Starting services...", total=None)
        
        try:
            # Run async use case
            results = asyncio.run(_execute_start_use_case(command))
            
            progress.update(task, completed=True)
            
            # Display results
            format_service_results(console, results)
            
            # Check if any failed
            failed_count = sum(1 for r in results if not r.success)
            if failed_count > 0:
                console.print(f"\n[red]{failed_count} service(s) failed to start[/red]")
                raise typer.Exit(1)
            else:
                console.print(f"\n[green]Successfully started {len(results)} service(s)[/green]")
                
        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"[red]Error starting services: {e}[/red]")
            raise typer.Exit(1)

async def _execute_start_use_case(command: StartServicesCommand):
    """Execute the start services use case."""
    # This would be injected in a real application
    from ...infrastructure.repositories.yaml_config_repository import YamlConfigRepository
    from ...infrastructure.repositories.memory_service_repository import MemoryServiceRepository
    from ...application.services.service_manager import ServiceManager
    
    # Initialize dependencies
    config_repo = YamlConfigRepository()
    service_repo = MemoryServiceRepository()
    service_manager = ServiceManager()
    
    # Load services from config
    await config_repo.load_services(service_repo)
    
    # Execute use case
    use_case = StartServicesUseCase(service_repo, service_manager)
    return await use_case.execute(command)
```

## Configuration Management

### Configuration Models

```python
# src/localport/config/models.py
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, List, Optional
from enum import Enum

class ForwardingTechnology(str, Enum):
    KUBECTL = "kubectl"
    SSH = "ssh"

class HealthCheckType(str, Enum):
    TCP = "tcp"
    HTTP = "http"
    KAFKA = "kafka"
    POSTGRES = "postgres"

class HealthCheckConfig(BaseModel):
    """Health check configuration."""
    type: HealthCheckType
    interval: int = Field(default=30, description="Check interval in seconds")
    timeout: float = Field(default=5.0, description="Check timeout in seconds")
    failure_threshold: int = Field(default=3, description="Failures before restart")
    config: Dict[str, Any] = Field(default_factory=dict)

class RestartPolicy(BaseModel):
    """Service restart policy configuration."""
    enabled: bool = True
    max_attempts: int = Field(default=5, description="Maximum restart attempts")
    backoff_multiplier: float = Field(default=2.0, description="Exponential backoff multiplier")
    initial_delay: int = Field(default=1, description="Initial delay in seconds")
    max_delay: int = Field(default=300, description="Maximum delay in seconds")

class ServiceConfig(BaseModel):
    """Individual service configuration."""
    name: str = Field(description="Service name")
    technology: ForwardingTechnology = Field(description="Forwarding technology")
    local_port: int = Field(description="Local port to bind")
    remote_port: int = Field(description="Remote port to forward to")
    connection: Dict[str, Any] = Field(description="Connection-specific configuration")
    enabled: bool = Field(default=True, description="Whether service is enabled")
    tags: List[str] = Field(default_factory=list, description="Service tags")
    description: Optional[str] = Field(default=None, description="Service description")
    health_check: Optional[HealthCheckConfig] = Field(default=None)
    restart_policy: Optional[RestartPolicy] = Field(default=None)
    
    @validator('local_port', 'remote_port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v

class LocalPortConfig(BaseModel):
    """Main configuration model."""
    version: str = Field(default="1.0", description="Configuration version")
    services: List[ServiceConfig] = Field(description="List of services")
    defaults: Dict[str, Any] = Field(default_factory=dict, description="Default settings")
    
    class Config:
        env_prefix = "LOCALPORT_"
        env_file = ".env"
```

## Sample Configuration

### YAML Configuration Example

```yaml
# localport.yaml
version: "1.0"

defaults:
  health_check:
    type: tcp
    interval: 30
    timeout: 5.0
    failure_threshold: 3
  restart_policy:
    enabled: true
    max_attempts: 5
    backoff_multiplier: 2.0
    initial_delay: 1
    max_delay: 300

services:
  - name: postgres
    technology: kubectl
    local_port: 5432
    remote_port: 5432
    connection:
      resource_type: service
      resource_name: postgres
      namespace: default
      context: minikube
    tags: [database, essential]
    description: "PostgreSQL database"
    health_check:
      type: postgres
      config:
        database: postgres
        user: postgres
        password: ${POSTGRES_PASSWORD}

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
    health_check:
      type: kafka
      config:
        bootstrap_servers: "localhost:6092"

  - name: redis
    technology: ssh
    local_port: 6379
    remote_port: 6379
    connection:
      host: redis-server.example.com
      user: deploy
      key_file: ~/.ssh/id_rsa
    tags: [cache]
    description: "Redis cache server"
```

## Development Setup and Installation

### Development Environment Setup

```bash
#!/bin/bash
# scripts/setup-dev.sh

set -e

echo "Setting up LocalPort development environment..."

# Check Python version
python_version=$(python3 --version | cut -d' ' -f2)
required_version="3.13"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 13) else 1)"; then
    echo "Error: Python 3.13+ required, found $python_version"
    exit 1
fi

# Install UV if not present
if ! command -v uv &> /dev/null; then
    echo "Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
fi

# Create virtual environment
echo "Creating virtual environment..."
uv venv --python 3.13

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
uv sync --dev

# Install pre-commit hooks
echo "Setting up pre-commit hooks..."
uv run pre-commit install

# Run initial tests
echo "Running initial tests..."
uv run pytest tests/ -v

echo "Development environment setup complete!"
echo "To activate the environment: source .venv/bin/activate"
```

### Project Configuration (pyproject.toml)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "localport"
version = "0.1.0"
description = "Universal port forwarding manager with health monitoring"
readme = "README.md"
license = {file = "LICENSE"}
authors = [
    {name = "Your Name", email = "your.email@example.com"},
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Tools",
    "Topic :: System :: Networking",
]
requires-python = ">=3.13"
dependencies = [
    "typer[all]>=0.12.0",
    "rich>=13.7.0",
    "pydantic>=2.8.0",
    "pydantic-settings>=2.4.0",
    "pyyaml>=6.0.1",
    "aiohttp>=3.9.0",
    "psutil>=5.9.0",
    "structlog>=24.1.0",
    "tenacity>=8.2.0",
    "click>=8.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
    "pytest-mock>=3.12.0",
    "black>=24.0.0",
    "ruff>=0.5.0",
    "mypy>=1.10.0",
    "pre-commit>=3.7.0",
    "pytest-xdist>=3.5.0",
]
kafka = [
    "kafka-python>=2.0.2",
]
postgres = [
    "psycopg[binary]>=3.2.0",
]
all = [
    "localport[kafka,postgres]",
]

[project.urls]
Homepage = "https://github.com/yourusername/localport"
Repository = "https://github.com/yourusername/localport"
Documentation = "https://localport.readthedocs.io"
"Bug Tracker" = "https://github.com/yourusername/localport/issues"

[project.scripts]
localport = "localport.main:main"

[tool.hatch.build.targets.wheel]
packages = ["src/localport"]

[tool.black]
line-length = 88
target-version = ['py313']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''

[tool.ruff]
target-version = "py313"
line-length = 88
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
    "C4", # flake8-comprehensions
    "UP", # pyupgrade
]
ignore = [
    "E501",  # line too long, handled by black
    "B008",  # do not perform function calls in argument defaults
    "C901",  # too complex
]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]
"tests/**/*" = ["B011"]

[tool.mypy]
python_version = "3.13"
check_untyped_defs = true
disallow_any_generics = true
disallow_incomplete_defs = true
disallow_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_return_any = true
strict_equality = true

[[tool.mypy.overrides]]
module = [
    "kafka.*",
    "psutil.*",
]
ignore_missing_imports = true

[tool.pytest.ini_options]
minversion = "8.0"
addopts = "-ra -q --strict-markers --strict-config"
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "unit: marks tests as unit tests",
]

[tool.coverage.run]
source = ["src"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if self.debug:",
    "if settings.DEBUG",
    "raise AssertionError",
    "raise NotImplementedError",
    "if 0:",
    "if __name__ == .__main__.:",
    "class .*\\bProtocol\\):",
    "@(abc\\.)?abstractmethod",
]
```

## Installation Methods

### 1. Development Installation (using UV)

```bash
# Clone repository
git clone https://github.com/yourusername/localport.git
cd localport

# Setup development environment
./scripts/setup-dev.sh

# Activate virtual environment
source .venv/bin/activate

# Install in development mode
uv pip install -e .

# Run LocalPort
localport --help
```

### 2. End-User Installation (using pipx)

```bash
# Install from PyPI
pipx install localport

# Install from GitHub
pipx install git+https://github.com/yourusername/localport.git

# Install with optional dependencies
pipx install "localport[kafka,postgres]"

# Run LocalPort
localport --help
```

### 3. Direct Installation (using UV)

```bash
# Install from PyPI
uv tool install localport

# Install from GitHub
uv tool install git+https://github.com/yourusername/localport.git

# Run LocalPort
localport --help
```

## Testing Strategy

### Test Structure

```python
# tests/unit/domain/test_service_entity.py
import pytest
from uuid import uuid4
from localport.domain.entities.service import Service, ServiceStatus, ForwardingTechnology

class TestServiceEntity:
    """Unit tests for Service entity."""
    
    def test_create_service(self):
        """Test service creation."""
        service = Service.create(
            name="test-service",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={"resource_name": "test"}
        )
        
        assert service.name == "test-service"
        assert service.technology == ForwardingTechnology.KUBECTL
        assert service.local_port == 8080
        assert service.remote_port == 80
        assert service.status == ServiceStatus.STOPPED
        assert service.tags == []
    
    def test_service_health_check(self):
        """Test service health checking."""
        service = Service.create(
            name="test",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={}
        )
        
        assert not service.is_healthy()
        
        service.status = ServiceStatus.RUNNING
        assert service.is_healthy()
    
    def test_service_restart_capability(self):
        """Test service restart capability."""
        service = Service.create(
            name="test",
            technology=ForwardingTechnology.KUBECTL,
            local_port=8080,
            remote_port=80,
            connection_info={}
        )
        
        # Stopped service can restart
        assert service.can_restart()
        
        # Running service cannot restart
        service.status = ServiceStatus.RUNNING
        assert not service.can_restart()
        
        # Failed service can restart
        service.status = ServiceStatus.FAILED
        assert service.can_restart()

# tests/integration/test_kubectl_adapter.py
import pytest
import asyncio
from unittest.mock import patch, MagicMock
from localport.infrastructure.adapters.kubectl_adapter import KubectlAdapter

class TestKubectlAdapter:
    """Integration tests for kubectl adapter."""
    
    @pytest.mark.asyncio
    async def test_start_port_forward_success(self):
        """Test successful port forward start."""
        adapter = KubectlAdapter()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful process
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_process.returncode = None
            mock_subprocess.return_value = mock_process
            
            connection_info = {
                'resource_name': 'test-service',
                'namespace': 'default'
            }
            
            pid = await adapter.start_port_forward(8080, 80, connection_info)
            
            assert pid == 12345
            mock_subprocess.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_port_forward_failure(self):
        """Test port forward start failure."""
        adapter = KubectlAdapter()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock failed process
            mock_process = MagicMock()
            mock_process.returncode = 1
            mock_process.communicate.return_value = (b'', b'Error message')
            mock_subprocess.return_value = mock_process
            
            connection_info = {
                'resource_name': 'test-service',
                'namespace': 'default'
            }
            
            with pytest.raises(RuntimeError, match="kubectl port-forward failed"):
                await adapter.start_port_forward(8080, 80, connection_info)
```

## Deployment and Distribution

### GitHub Actions CI/CD

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.13"]

    steps:
    - uses: actions/checkout@v4
    
    - name: Install UV
      uses: astral-sh/setup-uv@v3
      with:
        version: "latest"
    
    - name: Set up Python ${{ matrix.python-version }}
      run: uv python install ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: uv sync --dev
    
    - name: Run linting
      run: |
        uv run ruff check .
        uv run black --check .
        uv run mypy src/
    
    - name: Run tests
      run: uv run pytest tests/ -v --cov=src/localport --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Install UV
      uses: astral-sh/setup-uv@v3
    
    - name: Build package
      run: uv build
    
    - name: Publish to PyPI
      if: startsWith(github.ref, 'refs/tags/')
      run: uv publish
      env:
        UV_PUBLISH_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
```

## Implementation Guidelines

### 1. Development Process

1. **Setup**: Use the provided setup script to initialize the development environment
2. **Code Quality**: All code must pass Black formatting, Ruff linting, and MyPy type checking
3. **Testing**: Maintain >90% test coverage with both unit and integration tests
4. **Documentation**: Document all public APIs and complex business logic
5. **Git Workflow**: Use feature branches with pull requests for all changes

### 2. Architecture Principles

- **Dependency Inversion**: All dependencies flow inward toward the domain
- **Single Responsibility**: Each class/module has one reason to change
- **Open/Closed**: Open for extension, closed for modification
- **Interface Segregation**: Clients depend only on interfaces they use
- **DRY Principle**: Don't repeat yourself - extract common functionality

### 3. Error Handling Strategy

- **Domain Layer**: Raise domain-specific exceptions
- **Application Layer**: Catch and translate exceptions to application errors
- **Infrastructure Layer**: Handle external system failures gracefully
- **CLI Layer**: Present user-friendly error messages

### 4. Logging and Monitoring

- **Structured Logging**: Use structlog for consistent, searchable logs
- **Log Levels**: DEBUG for development, INFO for operations, WARN/ERROR for issues
- **Metrics**: Track service health, restart counts, and performance metrics
- **Observability**: Include correlation IDs for request tracing

### 5. Security Considerations

- **Credential Management**: Never log or store credentials in plain text
- **Input Validation**: Validate all external inputs using Pydantic
- **Process Isolation**: Run port forwards in separate processes
- **Resource Limits**: Implement timeouts and resource constraints

## Implementation Checklist

### Phase 1: Project Foundation ✅ COMPLETED
- [x] **1.1 Initialize Project Structure**
  - [x] Create directory structure as defined in project layout
  - [x] Set up `pyproject.toml` with dependencies and configuration
  - [x] Create `uv.lock` file for reproducible builds
  - [x] Add `.gitignore` for Python projects
  - [x] Create `README.md` with basic project information

- [x] **1.2 Development Environment Setup**
  - [x] Create `scripts/setup-dev.sh` development setup script
  - [x] Configure pre-commit hooks with Black, Ruff, MyPy
  - [x] Set up GitHub Actions CI/CD pipeline
  - [x] Create basic test structure and fixtures
  - [x] Verify UV and pipx installation methods work

- [x] **1.3 Constructor Issues Resolution** ✅ COMPLETED
  - [x] Fix ServiceManager constructor calls (takes no parameters)
  - [x] Fix HealthMonitor constructor (add missing service_repository parameter)
  - [x] Fix DaemonManager constructor (add missing service_repository parameter)
  - [x] Fix ManageDaemonUseCase constructor and update to command pattern
  - [x] Fix MonitorServicesUseCase constructor and update to command pattern
  - [x] Fix YamlConfigRepository instantiation with proper config path parameter

- [x] **1.4 CLI Error Handling Implementation** ✅ COMPLETED
  - [x] Implement "fail fast and clean" error handling philosophy
  - [x] Add proper typer.Exit exception handling to prevent unnecessary tracebacks
  - [x] Create helpful configuration error messages with specific file locations
  - [x] Update error messages to include log locations (~/.local/share/localport/logs/)
  - [x] Implement clean exit behavior for all CLI commands
  - [x] Add Rich-formatted error panels with actionable suggestions

### Phase 2: Domain Layer Implementation
- [x] **2.1 Core Entities**
  - [x] Implement `Service` entity with factory methods
  - [x] Implement `PortForward` entity with process tracking
  - [x] Implement `HealthCheck` entity with status tracking
  - [x] Create value objects for `Port` and `ConnectionInfo`
  - [x] Add comprehensive unit tests for all entities

- [x] **2.2 Repository Interfaces**
  - [x] Define `ServiceRepository` abstract interface
  - [x] Define `ConfigRepository` abstract interface
  - [x] Create domain service interfaces
  - [x] Add repository contract tests
  - [x] Document repository patterns and usage

### Phase 3: Infrastructure Layer Implementation
- [x] **3.1 Port Forwarding Adapters**
  - [x] Implement `KubectlAdapter` with process management
  - [x] Implement `SSHAdapter` with tunnel management
  - [x] Create adapter factory and registration system
  - [x] Handle cross-platform process differences

- [x] **3.2 Health Check Strategies**
  - [x] Implement `TCPHealthCheck` strategy
  - [x] Implement `HTTPHealthCheck` strategy
  - [x] Implement `KafkaHealthCheck` strategy
  - [x] Implement `PostgreSQLHealthCheck` strategy
  - [x] Create health check factory and configuration

- [x] **3.3 Configuration Management**
  - [x] Implement `YamlConfigRepository` with validation
  - [x] Implement `MemoryServiceRepository` for runtime state
  - [x] Add environment variable substitution
  - [x] Create configuration validation and error handling
  - [x] Add sample configuration files

### Phase 4: Application Layer Implementation
- [x] **4.1 Use Cases**
  - [x] Implement `StartServicesUseCase` with error handling
  - [x] Implement `StopServicesUseCase` with graceful shutdown
  - [x] Implement `MonitorServicesUseCase` with health tracking
  - [x] Implement `ManageDaemonUseCase` for background operation
  - [x] Add comprehensive use case tests

- [x] **4.2 Application Services**
  - [x] Implement `ServiceManager` with lifecycle management
  - [x] Implement `HealthMonitor` with automatic restart logic
  - [x] Implement `DaemonManager` with background processing
  - [x] Add service coordination and error recovery
  - [x] Create application service integration tests

### Phase 5: CLI Interface Implementation ✅ PARTIALLY COMPLETED
- [x] **5.1 Core CLI Framework** ✅ COMPLETED
  - [x] Set up main Typer application with Rich formatting
  - [x] Implement global options and configuration loading
  - [x] Create command context and dependency injection
  - [x] Add error handling and user-friendly messages
  - [x] Implement help system and documentation

- [x] **5.2 Command Implementation** ✅ COMPLETED
  - [x] Implement `start` command with service selection
  - [x] Implement `stop` command with graceful shutdown
  - [x] Implement `status` command with formatted output
  - [x] Implement `daemon` command group for background mode
  - [x] Add progress indicators and interactive feedback

- [x] **5.3 Output Formatting** ✅ COMPLETED
  - [x] Create table formatters for service status
  - [x] Add Rich console styling and colors
  - [x] Create JSON formatters for scripting
  - [x] Implement log viewing and filtering
  - [x] Create export functionality for configurations

### Phase 6: Advanced Features
- [x] **6.1 Health Monitoring System** ✅ COMPLETED
  - [x] Implement continuous health checking
  - [x] Add exponential backoff for restart attempts
  - [x] Create health check scheduling and coordination
  - [x] Add health metrics collection and reporting
  - [x] Implement failure threshold and alerting

- [ ] **6.2 Daemon Mode**
  - [ ] Implement background daemon process
  - [ ] Add IPC for daemon communication
  - [ ] Create daemon status and control interface
  - [ ] Implement graceful daemon shutdown
  - [ ] Add daemon logging and monitoring

- [ ] **6.3 Configuration Management**
  - [ ] Add configuration file discovery and loading
  - [ ] Implement configuration validation and error reporting
  - [ ] Add configuration hot-reloading capability
  - [ ] Create configuration migration and versioning
  - [ ] Add configuration backup and restore

### Phase 7: Testing and Quality Assurance
- [ ] **7.1 Unit Testing**
  - [ ] Achieve >90% code coverage for domain layer
  - [ ] Achieve >90% code coverage for application layer
  - [ ] Achieve >90% code coverage for infrastructure layer
  - [ ] Add property-based testing for critical components
  - [ ] Create comprehensive test fixtures and mocks

- [ ] **7.2 Integration Testing**
  - [ ] Test kubectl adapter with real Kubernetes clusters
  - [ ] Test SSH adapter with real SSH connections
  - [ ] Test health checks with real services
  - [ ] Test configuration loading and validation
  - [ ] Add end-to-end workflow testing

- [ ] **7.3 Performance and Reliability Testing**
  - [ ] Test with multiple concurrent port forwards
  - [ ] Test restart behavior under various failure conditions
  - [ ] Test resource usage and memory leaks
  - [ ] Test cross-platform compatibility
  - [ ] Add stress testing for daemon mode

### Phase 8: Documentation and Distribution
- [ ] **8.1 User Documentation**
  - [ ] Write comprehensive README with examples
  - [ ] Create configuration guide with all options
  - [ ] Write troubleshooting guide for common issues
  - [ ] Create architecture documentation
  - [ ] Add API documentation for extensibility

- [ ] **8.2 Developer Documentation**
  - [ ] Document development setup and contribution guidelines
  - [ ] Create architecture decision records (ADRs)
  - [ ] Document testing strategies and patterns
  - [ ] Create extension guide for new adapters
  - [ ] Add code style and review guidelines

- [ ] **8.3 Packaging and Distribution**
  - [ ] Prepare package for PyPI publication
  - [ ] Test installation via pipx from PyPI
  - [ ] Test installation via pipx from GitHub
  - [ ] Test UV tool installation method
  - [ ] Create release automation and versioning

### Phase 9: Production Readiness
- [ ] **9.1 Security Review**
  - [ ] Audit credential handling and storage
  - [ ] Review input validation and sanitization
  - [ ] Test process isolation and privilege separation
  - [ ] Audit logging for sensitive information
  - [ ] Add security documentation and guidelines

- [ ] **9.2 Performance Optimization**
  - [ ] Profile and optimize startup time
  - [ ] Optimize memory usage for long-running processes
  - [ ] Optimize health check scheduling and batching
  - [ ] Add performance monitoring and metrics
  - [ ] Create performance benchmarks and regression tests

- [ ] **9.3 Production Deployment**
  - [ ] Create deployment guides for different environments
  - [ ] Add monitoring and observability integration
  - [ ] Create backup and recovery procedures
  - [ ] Add operational runbooks and troubleshooting
  - [ ] Prepare for production support and maintenance

### Phase 10: Release and Maintenance
- [ ] **10.1 Release Preparation**
  - [ ] Complete final testing and quality assurance
  - [ ] Prepare release notes and changelog
  - [ ] Create migration guides for breaking changes
  - [ ] Set up issue tracking and support processes
  - [ ] Prepare marketing and announcement materials

- [ ] **10.2 Post-Release Activities**
  - [ ] Monitor initial user adoption and feedback
  - [ ] Address critical bugs and issues promptly
  - [ ] Create user community and support channels
  - [ ] Plan future feature development roadmap
  - [ ] Establish maintenance and update schedule

## Deferred Tasks

The following tasks were specifically deferred from their original phases to maintain development momentum and focus on core functionality:

### Infrastructure Integration Tests (Deferred from Phase 3)
- [ ] **Comprehensive Adapter Integration Tests**
  - [ ] Test kubectl adapter with real Kubernetes clusters (kind/minikube)
  - [ ] Test SSH adapter with real SSH connections and key authentication
  - [ ] Test adapter factory with multiple concurrent adapters
  - [ ] Test adapter prerequisite checking across different environments
  - [ ] Test adapter process cleanup under various failure scenarios

- [ ] **Health Check Integration Tests**
  - [ ] Test Kafka health checks with real Kafka clusters
  - [ ] Test PostgreSQL health checks with real database instances
  - [ ] Test health check factory with external service dependencies
  - [ ] Test health check runner with real service failures and recoveries
  - [ ] Test health check configuration validation with edge cases

- [ ] **Configuration Integration Tests**
  - [ ] Test YAML configuration loading with complex environment setups
  - [ ] Test environment variable substitution with various shell environments
  - [ ] Test configuration validation with malformed YAML files
  - [ ] Test configuration backup and restore with file system permissions
  - [ ] Test configuration hot-reloading with file watchers

**Rationale for Deferral:**
These integration tests require external dependencies (Kubernetes clusters, Kafka brokers, PostgreSQL databases) and complex environment setup. While important for production readiness, they were deferred to allow completion of core infrastructure functionality first. These tests can be implemented in Phase 7 (Testing and Quality Assurance) when the full system is available for end-to-end testing.

---

**Progress Tracking:**
- **Total Tasks:** 100+ individual checklist items
- **Completed:** 35/100+ (35%)
- **Current Phase:** Phase 3 COMPLETED, Phase 4 IN PROGRESS
- **Estimated Timeline:** 8-12 weeks for MVP (Phases 1-5), 16-20 weeks for full implementation
- **Priority:** Focus on Phases 1-5 for MVP, Phases 6-10 for production readiness
- **Deferred Tasks:** 50+ additional tasks for advanced features and comprehensive testing

This comprehensive checklist provides a structured approach to implementing LocalPort using modern Python practices, hexagonal architecture, and the latest tooling ecosystem. Each phase builds upon the previous one, ensuring a solid foundation and systematic progress toward a production-ready port forwarding manager.

**Deferred Task Strategy:**
The deferred tasks represent important functionality that would enhance LocalPort's robustness, security, and enterprise readiness. These tasks are intentionally postponed to maintain development velocity and ensure core functionality is delivered first. They can be tackled in future iterations based on user feedback and requirements.
