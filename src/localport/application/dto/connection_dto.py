"""Data Transfer Objects for connection management operations."""

from dataclasses import dataclass
from typing import Any, Optional

from ...domain.enums import ForwardingTechnology
from ...domain.value_objects.discovery import KubernetesResource, DiscoveredPort


@dataclass
class AddConnectionRequest:
    """Request DTO for adding a new connection."""
    
    service_name: str | None
    technology: ForwardingTechnology
    connection_params: dict[str, Any]
    options: dict[str, Any] = None
    
    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.options is None:
            self.options = {}
    
    # kubectl-specific factory methods
    @classmethod
    def kubectl_request(
        cls,
        resource_name: str,
        local_port: int | None = None,
        service_name: str | None = None,
        namespace: str | None = None,
        resource_type: str = "service",
        context: str | None = None,
        **kwargs: Any
    ) -> "AddConnectionRequest":
        """Create a request for adding a kubectl connection.
        
        Args:
            resource_name: Name of the Kubernetes resource
            local_port: Local port to bind (optional, may be prompted for)
            service_name: Service name (defaults to resource_name if not provided)
            namespace: Kubernetes namespace (optional, will be discovered)
            resource_type: Type of resource (service, pod, deployment)
            context: Kubernetes context to use
            **kwargs: Additional options
            
        Returns:
            AddConnectionRequest for kubectl connection
        """
        connection_params = {
            "resource_name": resource_name,
            "resource_type": resource_type
        }
        
        if namespace:
            connection_params["namespace"] = namespace
        if context:
            connection_params["context"] = context
            
        options = {
            "local_port": local_port,
            **kwargs
        }
        
        return cls(
            service_name=service_name,
            technology=ForwardingTechnology.KUBECTL,
            connection_params=connection_params,
            options=options
        )
    
    @classmethod
    def ssh_request(
        cls,
        service_name: str,
        host: str,
        local_port: int | None = None,
        remote_port: int | None = None,
        user: str | None = None,
        port: int = 22,
        key_file: str | None = None,
        remote_host: str | None = None,
        **kwargs: Any
    ) -> "AddConnectionRequest":
        """Create a request for adding an SSH connection.
        
        Args:
            service_name: Name for the service
            host: SSH host to connect to
            local_port: Local port to bind (optional, may be prompted for)
            remote_port: Remote port to forward to (optional, may be prompted for)
            user: SSH username
            port: SSH port (default 22)
            key_file: Path to SSH private key file
            remote_host: Remote host for tunneling
            **kwargs: Additional options
            
        Returns:
            AddConnectionRequest for SSH connection
        """
        connection_params = {
            "host": host,
            "port": port
        }
        
        if user:
            connection_params["user"] = user
        if key_file:
            connection_params["key_file"] = key_file
        if remote_host:
            connection_params["remote_host"] = remote_host
            
        options = {
            "local_port": local_port,
            "remote_port": remote_port,
            **kwargs
        }
        
        return cls(
            service_name=service_name,
            technology=ForwardingTechnology.SSH,
            connection_params=connection_params,
            options=options
        )


@dataclass
class AddConnectionResponse:
    """Response DTO for adding a new connection."""
    
    success: bool
    service_name: str
    configuration_added: dict[str, Any]
    discovered_info: Optional[dict[str, Any]] = None
    warnings: list[str] = None
    message: str = ""
    
    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.warnings is None:
            self.warnings = []
    
    @classmethod
    def success_response(
        cls,
        service_name: str,
        configuration_added: dict[str, Any],
        discovered_info: Optional[dict[str, Any]] = None,
        warnings: list[str] = None,
        message: str = ""
    ) -> "AddConnectionResponse":
        """Create a success response."""
        return cls(
            success=True,
            service_name=service_name,
            configuration_added=configuration_added,
            discovered_info=discovered_info,
            warnings=warnings or [],
            message=message
        )
    
    @classmethod
    def failure_response(
        cls,
        service_name: str,
        message: str,
        warnings: list[str] = None
    ) -> "AddConnectionResponse":
        """Create a failure response."""
        return cls(
            success=False,
            service_name=service_name,
            configuration_added={},
            discovered_info=None,
            warnings=warnings or [],
            message=message
        )


@dataclass
class RemoveConnectionRequest:
    """Request DTO for removing a connection."""
    
    service_name: str
    force: bool = False  # Skip confirmation prompts
    backup: bool = True  # Create backup before removal


@dataclass
class RemoveConnectionResponse:
    """Response DTO for removing a connection."""
    
    success: bool
    service_name: str
    was_running: bool = False
    backup_path: str | None = None
    message: str = ""
    
    @classmethod
    def success_response(
        cls,
        service_name: str,
        was_running: bool = False,
        backup_path: str | None = None,
        message: str = ""
    ) -> "RemoveConnectionResponse":
        """Create a success response."""
        return cls(
            success=True,
            service_name=service_name,
            was_running=was_running,
            backup_path=backup_path,
            message=message
        )
    
    @classmethod
    def failure_response(
        cls,
        service_name: str,
        message: str
    ) -> "RemoveConnectionResponse":
        """Create a failure response."""
        return cls(
            success=False,
            service_name=service_name,
            was_running=False,
            backup_path=None,
            message=message
        )


@dataclass
class ServiceSummary:
    """Summary information about a configured service."""
    
    name: str
    technology: str
    target: str  # Human-readable target description
    local_port: int
    remote_port: int  # Add missing remote_port field
    connection_params: dict[str, Any]  # Add missing connection_params field
    enabled: bool = True
    tags: list[str] = None
    description: str | None = None
    
    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.tags is None:
            self.tags = []
        if self.connection_params is None:
            self.connection_params = {}
    
    @property
    def service_name(self) -> str:
        """Alias for name to match formatter expectations."""
        return self.name


@dataclass
class ListConnectionsRequest:
    """Request DTO for listing connections."""
    
    filter_technology: str | None = None  # Filter by technology (kubectl, ssh)
    filter_tags: list[str] = None  # Filter by tags
    include_disabled: bool = False  # Include disabled services
    sort_by: str = "name"  # Sort by: name, technology, local_port
    
    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.filter_tags is None:
            self.filter_tags = []


@dataclass
class ListConnectionsResponse:
    """Response DTO for listing connections."""
    
    success: bool
    services: list[ServiceSummary]
    total_count: int
    technology_breakdown: dict[str, int]
    message: str = ""
    
    def __post_init__(self) -> None:
        """Calculate derived properties."""
        if not hasattr(self, '_calculated'):
            self.total_count = len(self.services)
            self.technology_breakdown = self._calculate_technology_breakdown()
            self._calculated = True
    
    def _calculate_technology_breakdown(self) -> dict[str, int]:
        """Calculate the breakdown of services by technology."""
        breakdown = {}
        for service in self.services:
            tech = service.technology
            breakdown[tech] = breakdown.get(tech, 0) + 1
        return breakdown
    
    @classmethod
    def success_response(
        cls,
        services: list[ServiceSummary],
        message: str = ""
    ) -> "ListConnectionsResponse":
        """Create a success response."""
        return cls(
            success=True,
            services=services,
            total_count=len(services),
            technology_breakdown={},  # Will be calculated in __post_init__
            message=message
        )
    
    @classmethod
    def failure_response(
        cls,
        message: str
    ) -> "ListConnectionsResponse":
        """Create a failure response."""
        return cls(
            success=False,
            services=[],
            total_count=0,
            technology_breakdown={},
            message=message
        )


@dataclass
class DiscoveryResult:
    """DTO for Kubernetes resource discovery results."""
    
    found: bool
    resource: KubernetesResource | None = None
    multiple_namespaces: list[str] = None
    selected_namespace: str | None = None
    selected_port: DiscoveredPort | None = None
    warnings: list[str] = None
    
    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.multiple_namespaces is None:
            self.multiple_namespaces = []
        if self.warnings is None:
            self.warnings = []
    
    @classmethod
    def not_found(
        cls,
        warnings: list[str] = None
    ) -> "DiscoveryResult":
        """Create a not found result."""
        return cls(
            found=False,
            warnings=warnings or []
        )
    
    @classmethod
    def found_single(
        cls,
        resource: KubernetesResource,
        selected_port: DiscoveredPort | None = None,
        warnings: list[str] = None
    ) -> "DiscoveryResult":
        """Create a result for a resource found in a single namespace."""
        return cls(
            found=True,
            resource=resource,
            selected_port=selected_port,
            warnings=warnings or []
        )
    
    @classmethod
    def found_multiple_namespaces(
        cls,
        namespaces: list[str],
        warnings: list[str] = None
    ) -> "DiscoveryResult":
        """Create a result for a resource found in multiple namespaces."""
        return cls(
            found=True,
            multiple_namespaces=namespaces,
            warnings=warnings or []
        )
    
    @property
    def needs_namespace_selection(self) -> bool:
        """Check if namespace selection is needed."""
        return self.found and len(self.multiple_namespaces) > 0
    
    @property
    def needs_port_selection(self) -> bool:
        """Check if port selection is needed."""
        return (self.found and 
                self.resource is not None and 
                len(self.resource.available_ports) > 1 and 
                self.selected_port is None)
    
    @property
    def has_single_port(self) -> bool:
        """Check if the resource has exactly one port."""
        return (self.found and 
                self.resource is not None and 
                len(self.resource.available_ports) == 1)


@dataclass
class ValidationResult:
    """DTO for connection validation results."""
    
    valid: bool
    errors: list[str] = None
    warnings: list[str] = None
    suggestions: list[str] = None
    
    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.suggestions is None:
            self.suggestions = []
    
    @classmethod
    def success(
        cls,
        warnings: list[str] = None,
        suggestions: list[str] = None
    ) -> "ValidationResult":
        """Create a successful validation result."""
        return cls(
            valid=True,
            warnings=warnings or [],
            suggestions=suggestions or []
        )
    
    @classmethod
    def failure(
        cls,
        errors: list[str],
        warnings: list[str] = None,
        suggestions: list[str] = None
    ) -> "ValidationResult":
        """Create a failed validation result."""
        return cls(
            valid=False,
            errors=errors,
            warnings=warnings or [],
            suggestions=suggestions or []
        )
    
    @property
    def has_issues(self) -> bool:
        """Check if there are any errors or warnings."""
        return len(self.errors) > 0 or len(self.warnings) > 0
