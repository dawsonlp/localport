"""Discovery value objects for representing discovered resources and ports."""

from dataclasses import dataclass
from typing import Any
import re

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class DiscoveredPort:
    """Value object representing a discovered port on a resource."""
    
    port: int
    protocol: str = "tcp"
    name: str | None = None
    description: str | None = None
    
    def __post_init__(self) -> None:
        """Validate port information after creation."""
        if not isinstance(self.port, int) or not (1 <= self.port <= 65535):
            raise ValueError(f"Port must be an integer between 1 and 65535, got {self.port}")
        
        if self.protocol not in ["tcp", "udp", "sctp"]:
            raise ValueError(f"Protocol must be tcp, udp, or sctp, got {self.protocol}")
    
    @property
    def display_name(self) -> str:
        """Get a human-readable display name for the port."""
        if self.name:
            return f"{self.port}/{self.protocol} ({self.name})"
        return f"{self.port}/{self.protocol}"
    
    @property
    def full_description(self) -> str:
        """Get a full description including port, protocol, name, and description."""
        desc = self.display_name
        if self.description:
            desc += f" - {self.description}"
        return desc


@dataclass(frozen=True)  
class KubernetesResource:
    """Value object representing a discovered Kubernetes resource."""
    
    name: str
    namespace: str
    resource_type: str = "service"
    available_ports: list[DiscoveredPort] = None
    labels: dict[str, str] = None
    annotations: dict[str, str] = None
    
    def __post_init__(self) -> None:
        """Initialize defaults and validate resource information."""
        # Handle mutable defaults
        if self.available_ports is None:
            object.__setattr__(self, 'available_ports', [])
        if self.labels is None:
            object.__setattr__(self, 'labels', {})
        if self.annotations is None:
            object.__setattr__(self, 'annotations', {})
        
        # Validate resource name (basic Kubernetes naming)
        self._validate_kubernetes_name(self.name, "resource name")
        self._validate_kubernetes_name(self.namespace, "namespace")
        
        # Validate resource type
        valid_types = ["service", "pod", "deployment"]
        if self.resource_type not in valid_types:
            raise ValueError(f"Resource type must be one of {valid_types}, got {self.resource_type}")
    
    @staticmethod
    def _validate_kubernetes_name(name: str, field_name: str) -> None:
        """Validate a Kubernetes name according to naming conventions.
        
        Args:
            name: Name to validate
            field_name: Name of the field for error messages
            
        Raises:
            ValueError: If name is invalid
        """
        if not name or not name.strip():
            raise ValueError(f"Kubernetes {field_name} cannot be empty")
        
        # Check length (Kubernetes limit is 253 for most names)
        if len(name) > 253:
            raise ValueError(f"Kubernetes {field_name} cannot exceed 253 characters")
        
        # Check for valid characters (lowercase alphanumeric, hyphens, dots)
        # Simplified validation - real Kubernetes validation is more complex
        if not re.match(r'^[a-z0-9.-]+$', name):
            raise ValueError(f"Kubernetes {field_name} must contain only lowercase letters, numbers, hyphens, and dots")
        
        # Must not start or end with hyphen or dot
        if name.startswith('-') or name.startswith('.') or name.endswith('-') or name.endswith('.'):
            raise ValueError(f"Kubernetes {field_name} cannot start or end with hyphen or dot")
    
    @property
    def qualified_name(self) -> str:
        """Get the fully qualified name of the resource."""
        return f"{self.name}.{self.namespace}"
    
    @property
    def has_ports(self) -> bool:
        """Check if the resource has any available ports."""
        return len(self.available_ports) > 0
    
    @property
    def single_port(self) -> DiscoveredPort | None:
        """Get the single port if there's exactly one, otherwise None."""
        if len(self.available_ports) == 1:
            return self.available_ports[0]
        return None
    
    def get_port_by_number(self, port_number: int) -> DiscoveredPort | None:
        """Get a port by its number.
        
        Args:
            port_number: Port number to find
            
        Returns:
            DiscoveredPort if found, None otherwise
        """
        for port in self.available_ports:
            if port.port == port_number:
                return port
        return None
    
    def get_ports_by_protocol(self, protocol: str) -> list[DiscoveredPort]:
        """Get all ports with a specific protocol.
        
        Args:
            protocol: Protocol to filter by (tcp, udp, sctp)
            
        Returns:
            List of ports with the specified protocol
        """
        return [port for port in self.available_ports if port.protocol == protocol]
    
    def get_default_port(self) -> DiscoveredPort | None:
        """Get the default port to use for forwarding.
        
        Logic:
        1. If only one port, return it
        2. If multiple ports, prefer named ports with common service names
        3. Otherwise return the first TCP port
        4. If no TCP ports, return the first port
        
        Returns:
            Default port to use, or None if no ports available
        """
        if not self.available_ports:
            return None
        
        if len(self.available_ports) == 1:
            return self.available_ports[0]
        
        # Prefer common service port names
        common_names = ["http", "https", "web", "api", "rest", "grpc", "postgresql", "postgres", "mysql", "redis", "mongo", "mongodb"]
        for name in common_names:
            for port in self.available_ports:
                if port.name and name in port.name.lower():
                    return port
        
        # Prefer TCP ports
        tcp_ports = self.get_ports_by_protocol("tcp")
        if tcp_ports:
            return tcp_ports[0]
        
        # Return first available port
        return self.available_ports[0]
    
    @classmethod
    def from_kubectl_output(
        cls,
        name: str,
        namespace: str,
        resource_type: str,
        kubectl_json: dict[str, Any]
    ) -> "KubernetesResource":
        """Create a KubernetesResource from kubectl JSON output.
        
        Args:
            name: Resource name
            namespace: Resource namespace
            resource_type: Type of resource (service, pod, deployment)
            kubectl_json: JSON output from kubectl get command
            
        Returns:
            KubernetesResource instance
        """
        available_ports = []
        labels = kubectl_json.get("metadata", {}).get("labels", {}) or {}
        annotations = kubectl_json.get("metadata", {}).get("annotations", {}) or {}
        
        # Extract ports based on resource type
        if resource_type == "service":
            ports_spec = kubectl_json.get("spec", {}).get("ports", [])
            for port_spec in ports_spec:
                port_num = port_spec.get("port")
                target_port = port_spec.get("targetPort", port_num)
                protocol = port_spec.get("protocol", "TCP").lower()
                port_name = port_spec.get("name")
                
                if port_num:
                    # Use targetPort if it's different from port
                    actual_port = target_port if isinstance(target_port, int) else port_num
                    discovered_port = DiscoveredPort(
                        port=actual_port,
                        protocol=protocol,
                        name=port_name
                    )
                    available_ports.append(discovered_port)
        
        elif resource_type == "pod":
            containers = kubectl_json.get("spec", {}).get("containers", [])
            for container in containers:
                container_ports = container.get("ports", [])
                for port_spec in container_ports:
                    port_num = port_spec.get("containerPort")
                    protocol = port_spec.get("protocol", "TCP").lower()
                    port_name = port_spec.get("name")
                    
                    if port_num:
                        discovered_port = DiscoveredPort(
                            port=port_num,
                            protocol=protocol,
                            name=port_name
                        )
                        available_ports.append(discovered_port)
        
        elif resource_type == "deployment":
            # For deployments, extract ports from pod template spec
            pod_spec = kubectl_json.get("spec", {}).get("template", {}).get("spec", {})
            containers = pod_spec.get("containers", [])
            for container in containers:
                container_ports = container.get("ports", [])
                for port_spec in container_ports:
                    port_num = port_spec.get("containerPort")
                    protocol = port_spec.get("protocol", "TCP").lower()
                    port_name = port_spec.get("name")
                    
                    if port_num:
                        discovered_port = DiscoveredPort(
                            port=port_num,
                            protocol=protocol,
                            name=port_name
                        )
                        available_ports.append(discovered_port)
        
        return cls(
            name=name,
            namespace=namespace,
            resource_type=resource_type,
            available_ports=available_ports,
            labels=labels,
            annotations=annotations
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary representation of the resource
        """
        return {
            "name": self.name,
            "namespace": self.namespace,
            "resource_type": self.resource_type,
            "available_ports": [
                {
                    "port": port.port,
                    "protocol": port.protocol,
                    "name": port.name,
                    "description": port.description
                }
                for port in self.available_ports
            ],
            "labels": dict(self.labels),
            "annotations": dict(self.annotations),
            "qualified_name": self.qualified_name,
            "has_ports": self.has_ports
        }
