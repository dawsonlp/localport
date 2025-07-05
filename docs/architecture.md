# LocalPort Architecture

This document provides a comprehensive overview of LocalPort's architecture, designed to help developers understand the system design and contribute effectively.

## Overview

LocalPort is built using **Hexagonal Architecture** (also known as Ports and Adapters), which provides clean separation of concerns, testability, and extensibility. The architecture ensures that business logic is isolated from external dependencies, making the system maintainable and adaptable.

## Hexagonal Architecture

```mermaid
graph TB
    subgraph "External World"
        CLI[CLI Interface]
        K8S[Kubernetes]
        SSH[SSH Servers]
        FS[File System]
        PROC[Processes]
    end
    
    subgraph "Infrastructure Layer (Adapters)"
        KCLI[kubectl Adapter]
        SSHA[SSH Adapter]
        FCONF[File Config Adapter]
        PROCA[Process Adapter]
        HCHK[Health Check Adapters]
    end
    
    subgraph "Application Layer (Use Cases)"
        START[Start Services]
        STOP[Stop Services]
        MONITOR[Monitor Services]
        DAEMON[Manage Daemon]
        SVCMGR[Service Manager]
        HMON[Health Monitor]
        DMGR[Daemon Manager]
    end
    
    subgraph "Domain Layer (Business Logic)"
        SVC[Service Entity]
        PF[Port Forward Entity]
        HC[Health Check Entity]
        REPO[Repository Interfaces]
        DOMAIN[Domain Services]
    end
    
    CLI --> START
    CLI --> STOP
    CLI --> MONITOR
    CLI --> DAEMON
    
    START --> SVCMGR
    STOP --> SVCMGR
    MONITOR --> HMON
    DAEMON --> DMGR
    
    SVCMGR --> SVC
    HMON --> HC
    DMGR --> SVC
    
    SVCMGR --> KCLI
    SVCMGR --> SSHA
    HMON --> HCHK
    
    KCLI --> K8S
    SSHA --> SSH
    FCONF --> FS
    PROCA --> PROC
```

## Layer Responsibilities

### 1. Domain Layer (Core Business Logic)

The innermost layer contains pure business logic with no external dependencies.

#### Entities
- **Service**: Represents a port forwarding service with its configuration
- **PortForward**: Represents an active port forwarding process
- **HealthCheck**: Represents health monitoring configuration and state

#### Value Objects
- **Port**: Encapsulates port number validation and behavior
- **ConnectionInfo**: Encapsulates connection details for different technologies

#### Repository Interfaces
- **ServiceRepository**: Interface for service persistence
- **ConfigRepository**: Interface for configuration management

#### Domain Services
- Business rules that don't belong to a specific entity
- Cross-entity operations and validations

### 2. Application Layer (Use Cases & Services)

Orchestrates domain objects to fulfill specific use cases.

#### Use Cases
- **StartServicesUseCase**: Coordinates starting multiple services
- **StopServicesUseCase**: Coordinates stopping services gracefully
- **MonitorServicesUseCase**: Manages health monitoring workflows
- **ManageDaemonUseCase**: Controls daemon lifecycle operations

#### Application Services
- **ServiceManager**: Manages service lifecycle and coordination
- **HealthMonitor**: Handles health checking and restart logic
- **DaemonManager**: Manages background daemon operations
- **ConfigurationManager**: Handles configuration hot-reloading

#### DTOs (Data Transfer Objects)
- **ServiceDTO**: Data structures for service information transfer
- **HealthDTO**: Data structures for health status information

### 3. Infrastructure Layer (Adapters)

Implements interfaces defined by inner layers and handles external system integration.

#### Port Forwarding Adapters
- **KubectlAdapter**: Implements kubectl port-forward operations
- **SSHAdapter**: Implements SSH tunnel management
- **AdapterFactory**: Creates appropriate adapters based on technology

#### Health Check Adapters
- **TCPHealthCheck**: Basic connectivity testing
- **HTTPHealthCheck**: Web service health endpoints
- **PostgreSQLHealthCheck**: Database-specific health checking
- **KafkaHealthCheck**: Message broker connectivity testing

#### Repository Implementations
- **YamlConfigRepository**: File-based configuration storage
- **MemoryServiceRepository**: In-memory service state management

#### External Integrations
- **ProcessAdapter**: System process management
- **FileSystemAdapter**: Configuration file operations

### 4. CLI Layer (User Interface)

Provides command-line interface using Typer and Rich for beautiful output.

#### Command Structure
- **ServiceCommands**: start, stop, status, logs
- **DaemonCommands**: daemon start, stop, restart, status, reload
- **ConfigCommands**: validate, export

#### Output Formatting
- **TableFormatter**: Human-readable tabular output
- **JSONFormatter**: Machine-readable JSON output
- **TextFormatter**: Simple text output for scripting

## Component Interactions

### Service Startup Flow

```mermaid
sequenceDiagram
    participant CLI
    participant StartUseCase
    participant ServiceManager
    participant KubectlAdapter
    participant HealthMonitor
    participant Service
    
    CLI->>StartUseCase: execute(command)
    StartUseCase->>ServiceManager: start_service(service)
    ServiceManager->>KubectlAdapter: start_port_forward()
    KubectlAdapter->>Service: update status
    ServiceManager->>HealthMonitor: start_monitoring(service)
    HealthMonitor-->>CLI: service started
```

### Health Monitoring Flow

```mermaid
sequenceDiagram
    participant HealthMonitor
    participant HealthChecker
    participant Service
    participant ServiceManager
    
    loop Every interval
        HealthMonitor->>HealthChecker: check_health()
        HealthChecker-->>HealthMonitor: health_result
        alt Health check failed
            HealthMonitor->>Service: increment_failure_count()
            alt Failure threshold reached
                HealthMonitor->>ServiceManager: restart_service()
                ServiceManager->>Service: restart()
            end
        else Health check passed
            HealthMonitor->>Service: reset_failure_count()
        end
    end
```

### Configuration Hot Reload Flow

```mermaid
sequenceDiagram
    participant FileWatcher
    participant ConfigManager
    participant ConfigDiffer
    participant DaemonManager
    participant ServiceManager
    
    FileWatcher->>ConfigManager: file_changed()
    ConfigManager->>ConfigManager: validate_config()
    ConfigManager->>ConfigDiffer: analyze_changes()
    ConfigDiffer-->>ConfigManager: diff_result
    ConfigManager->>DaemonManager: apply_changes(diff)
    DaemonManager->>ServiceManager: restart_affected_services()
```

## Design Patterns

### 1. Repository Pattern
Abstracts data access and provides a uniform interface for data operations.

```python
class ServiceRepository(ABC):
    @abstractmethod
    async def save(self, service: Service) -> None: ...
    
    @abstractmethod
    async def find_by_id(self, service_id: UUID) -> Optional[Service]: ...
```

### 2. Factory Pattern
Creates objects without specifying their concrete classes.

```python
class AdapterFactory:
    def create_adapter(self, technology: ForwardingTechnology) -> BaseAdapter:
        return self._adapters[technology]()
```

### 3. Strategy Pattern
Defines a family of algorithms and makes them interchangeable.

```python
class HealthCheckFactory:
    def create_health_checker(self, check_type: str) -> HealthChecker:
        return self._health_checkers[check_type]()
```

### 4. Observer Pattern
Allows objects to notify other objects about changes in their state.

```python
class HealthMonitor:
    async def _notify_health_change(self, service: Service, status: HealthStatus):
        for observer in self._observers:
            await observer.on_health_change(service, status)
```

### 5. Command Pattern
Encapsulates requests as objects, allowing parameterization and queuing.

```python
@dataclass
class StartServicesCommand:
    service_names: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    all_services: bool = False
```

## Technology Stack

### Core Dependencies
- **Python 3.13+**: Latest Python with modern features
- **Typer**: Modern CLI framework with Rich integration
- **Rich**: Beautiful terminal output and formatting
- **Pydantic**: Data validation and settings management
- **PyYAML**: YAML configuration parsing
- **asyncio**: Asynchronous programming support

### Optional Dependencies
- **kafka-python**: Kafka health check support
- **psycopg**: PostgreSQL health check support
- **aiohttp**: HTTP health check support
- **watchdog**: File system monitoring for hot reload

### Development Dependencies
- **pytest**: Testing framework with async support
- **black**: Code formatting
- **ruff**: Fast Python linter
- **mypy**: Static type checking
- **pre-commit**: Git hooks for code quality

## Extension Points

### 1. Adding New Adapters

To add support for a new port forwarding technology:

1. **Create Adapter Class**:
```python
class NewTechnologyAdapter(BaseAdapter):
    async def start_port_forward(self, local_port: int, remote_port: int, 
                                connection_info: Dict[str, Any]) -> int:
        # Implementation
        pass
```

2. **Register in Factory**:
```python
# In adapter_factory.py
self._adapters[ForwardingTechnology.NEW_TECH] = NewTechnologyAdapter
```

3. **Update Configuration Schema**:
```python
# In domain/entities/service.py
class ForwardingTechnology(Enum):
    NEW_TECH = "new_tech"
```

### 2. Adding New Health Checks

To add a new health check type:

1. **Create Health Checker**:
```python
class CustomHealthCheck:
    async def check(self, **kwargs) -> bool:
        # Implementation
        pass
```

2. **Register in Factory**:
```python
# In health_check_factory.py
self._health_checkers['custom'] = CustomHealthCheck
```

### 3. Adding New Output Formatters

To add a new output format:

1. **Create Formatter**:
```python
class XMLFormatter:
    def format_services(self, services: List[Service]) -> str:
        # Implementation
        pass
```

2. **Register in Router**:
```python
# In format_router.py
self._formatters[OutputFormat.XML] = XMLFormatter()
```

## Error Handling Strategy

### 1. Domain Layer
- Raises domain-specific exceptions
- Pure business rule violations
- No external system dependencies

### 2. Application Layer
- Catches and translates domain exceptions
- Handles use case orchestration errors
- Provides meaningful error context

### 3. Infrastructure Layer
- Handles external system failures
- Implements retry logic and circuit breakers
- Logs technical details for debugging

### 4. CLI Layer
- Presents user-friendly error messages
- Provides actionable guidance
- Maintains consistent error formatting

## Logging and Observability

### Structured Logging
LocalPort uses structured logging with consistent fields:

```python
logger.info("Service started", 
           service_name=service.name,
           local_port=service.local_port,
           technology=service.technology.value,
           process_id=process_id)
```

### Log Levels
- **DEBUG**: Detailed debugging information
- **INFO**: General operational information
- **WARN**: Warning conditions that should be noted
- **ERROR**: Error conditions that need attention

### Metrics and Monitoring
- Service health status tracking
- Restart count monitoring
- Performance metrics collection
- Configuration change auditing

## Security Considerations

### 1. Credential Management
- No credentials stored in plain text
- Environment variable substitution for secrets
- Secure key file handling for SSH

### 2. Process Isolation
- Port forwards run in separate processes
- Proper process cleanup on termination
- Resource limit enforcement

### 3. Input Validation
- All external inputs validated using Pydantic
- Configuration schema enforcement
- Port range and permission validation

### 4. Network Security
- Local-only port binding by default
- Configurable bind addresses
- Connection timeout enforcement

## Performance Considerations

### 1. Asynchronous Operations
- Non-blocking I/O for all network operations
- Concurrent health checking
- Parallel service startup/shutdown

### 2. Resource Management
- Efficient process management
- Memory-conscious data structures
- Configurable resource limits

### 3. Caching and Optimization
- Configuration caching
- Health check result caching
- Efficient file watching

## Testing Strategy

### 1. Unit Tests
- Domain logic testing with no external dependencies
- Mock external systems for isolation
- High coverage of business rules

### 2. Integration Tests
- Test adapter implementations with real systems
- End-to-end workflow testing
- Configuration validation testing

### 3. Contract Tests
- Repository interface compliance
- Adapter interface compliance
- Health checker interface compliance

## Shutdown Infrastructure Architecture (v0.3.7)

LocalPort v0.3.7 introduces enterprise-grade shutdown infrastructure that eliminates race conditions and provides graceful shutdown capabilities. This section details the shutdown architecture that resolves Mac service stability issues.

### Shutdown Infrastructure Overview

```mermaid
graph TB
    subgraph "Signal Sources"
        SIGTERM[SIGTERM Signal]
        SIGINT[SIGINT Signal]
        SIGUSR1[SIGUSR1 Signal]
        SIGHUP[SIGHUP Signal]
        CLI_STOP[CLI Stop Command]
    end
    
    subgraph "Shutdown Infrastructure"
        ASH[AsyncSignalHandler]
        TM[TaskManager]
        SC[ShutdownCoordinator]
        GSM[GracefulShutdownMixin]
        CT[CooperativeTask]
    end
    
    subgraph "Daemon Components"
        LD[LocalPortDaemon]
        HMS[HealthMonitorScheduler]
        SHMT[ServiceHealthMonitorTask]
        SM[ServiceManager]
        DM[DaemonManager]
    end
    
    SIGTERM --> ASH
    SIGINT --> ASH
    SIGUSR1 --> ASH
    SIGHUP --> ASH
    CLI_STOP --> SC
    
    ASH --> SC
    SC --> TM
    TM --> CT
    GSM --> CT
    
    LD --> ASH
    LD --> TM
    LD --> SC
    HMS --> CT
    SHMT --> CT
    
    SC --> HMS
    SC --> SM
    SC --> DM
```

### Multi-Phase Shutdown Process

```mermaid
sequenceDiagram
    participant Signal as Signal Source
    participant ASH as AsyncSignalHandler
    participant SC as ShutdownCoordinator
    participant TM as TaskManager
    participant HMS as HealthMonitorScheduler
    participant SM as ServiceManager
    participant CT as CooperativeTask
    
    Signal->>ASH: SIGTERM/SIGINT
    ASH->>ASH: Deduplicate signals
    ASH->>SC: initiate_shutdown()
    
    Note over SC: Phase 1: Stop New Work (2s)
    SC->>TM: stop_accepting_new_tasks()
    SC->>HMS: stop_new_monitoring()
    
    Note over SC: Phase 2: Complete Current (8s)
    SC->>TM: wait_for_current_tasks()
    SC->>HMS: complete_current_checks()
    
    Note over SC: Phase 3: Cancel Tasks (15s)
    SC->>TM: cancel_all_tasks()
    TM->>CT: request_shutdown()
    CT->>CT: cooperative_cleanup()
    CT-->>TM: shutdown_complete
    
    Note over SC: Phase 4: Force Cleanup (5s)
    SC->>TM: force_cleanup()
    SC->>SM: emergency_stop()
    
    SC-->>ASH: shutdown_complete
```

### Thread-Safe Signal Handling

```mermaid
sequenceDiagram
    participant OS as Operating System
    participant SH as Signal Handler
    participant ASH as AsyncSignalHandler
    participant EL as Event Loop
    participant SC as ShutdownCoordinator
    
    OS->>SH: SIGTERM (signal context)
    SH->>SH: Check signal deduplication
    
    alt Unix Platform
        SH->>EL: add_signal_handler()
        EL->>ASH: _async_signal_handler()
    else Windows Platform
        SH->>EL: call_soon_threadsafe()
        EL->>ASH: _handle_signal_async()
    end
    
    ASH->>ASH: Thread-safe coordination
    ASH->>SC: Signal event set
    SC->>SC: Begin shutdown process
```

### Cooperative Task Architecture

```mermaid
classDiagram
    class CooperativeTask {
        +name: str
        +check_interval: float
        +shutdown_requested: bool
        +start() async
        +stop() async
        +request_shutdown() async
        +_run_loop() async
        +_execute_iteration() async
        +_handle_iteration_error() async
    }
    
    class ServiceHealthMonitorTask {
        +service: Service
        +health_scheduler: HealthMonitorScheduler
        +check_interval: float
        +_execute_iteration() async
        +_handle_iteration_error() async
    }
    
    class TaskManager {
        +register_task() async
        +cancel_all_tasks() async
        +wait_for_completion() async
        +get_task_status() dict
        +force_cleanup() async
    }
    
    class GracefulShutdownMixin {
        +shutdown_timeout: float
        +shutdown_callbacks: list
        +register_shutdown_callback()
        +graceful_shutdown() async
    }
    
    CooperativeTask <|-- ServiceHealthMonitorTask
    TaskManager --> CooperativeTask : manages
    GracefulShutdownMixin --> CooperativeTask : provides patterns
```

### Health Monitor Shutdown Integration

```mermaid
sequenceDiagram
    participant SC as ShutdownCoordinator
    participant HMS as HealthMonitorScheduler
    participant SHMT as ServiceHealthMonitorTask
    participant TM as TaskManager
    participant HC as HealthChecker
    
    Note over SC: Shutdown signal received
    SC->>HMS: stop_monitoring()
    HMS->>SHMT: request_shutdown()
    
    loop Health Check Iteration
        SHMT->>SHMT: Check shutdown_requested
        alt Shutdown requested
            SHMT->>SHMT: Break monitoring loop
            SHMT->>TM: Task cleanup
            SHMT-->>HMS: Shutdown complete
        else Continue monitoring
            SHMT->>HC: perform_health_check()
            HC-->>SHMT: health_result
            SHMT->>SHMT: Process result
        end
    end
    
    HMS-->>SC: All monitoring stopped
```

### Task Manager Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Initializing
    Initializing --> Running : start()
    
    Running --> Stopping : shutdown_signal
    Running --> Running : register_task()
    Running --> Running : task_completion
    
    Stopping --> StopNewWork : Phase 1
    StopNewWork --> CompleteCurrent : timeout_or_complete
    CompleteCurrent --> CancelTasks : timeout_or_complete
    CancelTasks --> ForceCleanup : timeout_or_complete
    ForceCleanup --> Stopped : cleanup_complete
    
    Stopped --> [*]
    
    note right of Running
        - Accept new tasks
        - Monitor task health
        - Track resource usage
    end note
    
    note right of Stopping
        Multi-phase shutdown:
        1. Stop New Work (2s)
        2. Complete Current (8s)
        3. Cancel Tasks (15s)
        4. Force Cleanup (5s)
    end note
```

### Signal Handler State Machine

```mermaid
stateDiagram-v2
    [*] --> Initialized
    Initialized --> Listening : setup_signal_handlers()
    
    Listening --> SignalReceived : SIGTERM/SIGINT
    Listening --> ReloadRequested : SIGUSR1/SIGHUP
    Listening --> StatusRequested : SIGUSR2
    
    SignalReceived --> ShutdownInitiated : deduplicate_and_process
    ReloadRequested --> ConfigReloading : process_reload
    StatusRequested --> StatusReporting : process_status
    
    ConfigReloading --> Listening : reload_complete
    StatusReporting --> Listening : status_complete
    
    ShutdownInitiated --> ShuttingDown : coordinate_shutdown
    ShuttingDown --> Cleanup : shutdown_phases_complete
    Cleanup --> [*] : cleanup_complete
    
    note right of SignalReceived
        Thread-safe deduplication
        prevents multiple shutdown
        tasks from signal spam
    end note
```

### Resource Cleanup Flow

```mermaid
flowchart TD
    A[Shutdown Signal] --> B{Signal Type}
    B -->|SIGTERM/SIGINT| C[Graceful Shutdown]
    B -->|SIGUSR1/SIGHUP| D[Config Reload]
    B -->|SIGUSR2| E[Status Report]
    
    C --> F[Phase 1: Stop New Work]
    F --> G[Phase 2: Complete Current]
    G --> H[Phase 3: Cancel Tasks]
    H --> I[Phase 4: Force Cleanup]
    
    F --> F1[Stop accepting new tasks]
    F --> F2[Stop new health monitoring]
    F --> F3[Stop new service starts]
    
    G --> G1[Wait for current operations]
    G --> G2[Complete health checks]
    G --> G3[Finish service operations]
    
    H --> H1[Cancel background tasks]
    H --> H2[Stop health monitoring]
    H --> H3[Cancel cooperative tasks]
    
    I --> I1[Force task termination]
    I --> I2[Emergency service stop]
    I --> I3[Resource cleanup verification]
    
    I --> J[Shutdown Complete]
    
    style C fill:#e1f5fe
    style F fill:#f3e5f5
    style G fill:#e8f5e8
    style H fill:#fff3e0
    style I fill:#ffebee
```

### Performance Characteristics

The shutdown infrastructure provides the following performance characteristics:

| Phase | Timeout | Purpose | Performance Target |
|-------|---------|---------|-------------------|
| **Stop New Work** | 2 seconds | Prevent new operations | <100ms typical |
| **Complete Current** | 8 seconds | Finish ongoing work | <2s typical |
| **Cancel Tasks** | 15 seconds | Cooperative cancellation | <1s typical |
| **Force Cleanup** | 5 seconds | Emergency cleanup | <500ms typical |
| **Total Shutdown** | <30 seconds | Complete process | **2.84s achieved** |

### Error Handling and Recovery

```mermaid
flowchart TD
    A[Shutdown Error] --> B{Error Type}
    
    B -->|Signal Handler Error| C[Log and Continue]
    B -->|Task Cancellation Error| D[Force Termination]
    B -->|Resource Cleanup Error| E[Emergency Cleanup]
    B -->|Timeout Error| F[Next Phase]
    
    C --> G[Fallback Signal Handling]
    D --> H[Process Termination]
    E --> I[Resource Leak Logging]
    F --> J[Emergency Shutdown]
    
    G --> K[Shutdown Continues]
    H --> K
    I --> K
    J --> K
    
    K --> L[Cleanup Verification]
    L --> M[Shutdown Complete]
    
    style A fill:#ffebee
    style B fill:#fff3e0
    style M fill:#e8f5e8
```

## Future Architecture Considerations

### 1. Plugin System
- Dynamic adapter loading
- Third-party health check plugins
- Custom output formatter plugins

### 2. Distributed Deployment
- Multi-node daemon coordination
- Shared configuration management
- Load balancing and failover

### 3. API Integration
- REST API for programmatic access
- WebSocket for real-time updates
- GraphQL for flexible querying

### 4. Enhanced Shutdown Features
- Custom shutdown phases
- Pluggable shutdown strategies
- Distributed shutdown coordination
- Shutdown metrics and monitoring

This architecture provides a solid foundation for LocalPort's current functionality while maintaining flexibility for future enhancements and community contributions. The v0.3.7 shutdown infrastructure specifically addresses Mac service stability issues through enterprise-grade lifecycle management.
