"""
Domain-level exception classes for LocalPort.

This module defines the error classification system used throughout LocalPort
to provide better error handling and user-friendly error messages.
"""

from enum import Enum
from typing import Optional, Dict, Any


class ErrorCategory(Enum):
    """Error categories for classification and formatting."""
    USER_ERROR = "user_error"
    SYSTEM_ERROR = "system_error"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"


class LocalPortError(Exception):
    """
    Base exception class for all LocalPort errors.
    
    Provides structured error information that can be formatted
    appropriately for different user contexts.
    """
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[list[str]] = None,
        technical_details: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.context = context or {}
        self.suggestions = suggestions or []
        self.technical_details = technical_details


class UserError(LocalPortError):
    """Base class for errors that require user action."""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[list[str]] = None,
        technical_details: Optional[str] = None
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.USER_ERROR,
            context=context,
            suggestions=suggestions,
            technical_details=technical_details
        )


class SystemError(LocalPortError):
    """Base class for system/environment errors."""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[list[str]] = None,
        technical_details: Optional[str] = None
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.SYSTEM_ERROR,
            context=context,
            suggestions=suggestions,
            technical_details=technical_details
        )


class NetworkError(LocalPortError):
    """Base class for network/connection errors."""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[list[str]] = None,
        technical_details: Optional[str] = None
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.NETWORK_ERROR,
            context=context,
            suggestions=suggestions,
            technical_details=technical_details
        )


class ValidationError(LocalPortError):
    """Base class for configuration validation errors."""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[list[str]] = None,
        technical_details: Optional[str] = None
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION_ERROR,
            context=context,
            suggestions=suggestions,
            technical_details=technical_details
        )


class SSHKeyNotFoundError(UserError):
    """
    Raised when an SSH key file cannot be found.
    
    This is the specific error that replaces the verbose ValueError
    from connection_info.py:72.
    """
    
    def __init__(
        self,
        key_path: str,
        service_name: Optional[str] = None,
        config_source: Optional[str] = None
    ):
        # Create user-friendly path (hide full system paths)
        safe_path = self._make_safe_path(key_path)
        
        message = f"SSH key file not found: {safe_path}"
        if service_name:
            message = f"SSH key file {safe_path} not found for service '{service_name}'"
            
        context = {
            "key_path": key_path,
            "safe_path": safe_path,
            "service_name": service_name,
            "config_source": config_source
        }
        
        suggestions = [
            "Provide valid SSH authentication credentials for this connection",
            f"Generate SSH key if needed: ssh-keygen -t rsa -f {safe_path}, then install public key on server",
            "Update config to point to correct SSH key file path"
        ]
        
        technical_details = f"File not found at: {key_path}"
        
        super().__init__(
            message=message,
            context=context,
            suggestions=suggestions,
            technical_details=technical_details
        )
    
    @staticmethod
    def _make_safe_path(full_path: str) -> str:
        """
        Convert full system path to safe display path.
        
        Examples:
        /Users/puneetvyas/.ssh/key.pem -> ~/.ssh/key.pem
        /home/user/.ssh/key.pem -> ~/.ssh/key.pem
        """
        import os
        from pathlib import Path
        
        path = Path(full_path)
        home = Path.home()
        
        try:
            # Try to make relative to home directory
            relative_path = path.relative_to(home)
            return f"~/{relative_path}"
        except ValueError:
            # If not under home directory, just show filename
            return path.name


class ConfigurationValidationError(ValidationError):
    """Raised when configuration validation fails."""
    
    def __init__(
        self,
        message: str,
        config_field: Optional[str] = None,
        config_source: Optional[str] = None
    ):
        context = {
            "config_field": config_field,
            "config_source": config_source
        }
        
        suggestions = [
            "Check the configuration file syntax",
            "Refer to documentation for correct format",
            "Use 'localport config validate' to check configuration"
        ]
        
        super().__init__(
            message=message,
            context=context,
            suggestions=suggestions
        )


class NetworkConnectionError(NetworkError):
    """Raised when network connections fail."""
    
    def __init__(
        self,
        message: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        service_name: Optional[str] = None
    ):
        context = {
            "host": host,
            "port": port,
            "service_name": service_name
        }
        
        suggestions = [
            "Check network connectivity",
            "Verify host and port are correct",
            "Check firewall settings"
        ]
        
        if host and port:
            suggestions.append(f"Test connection manually: telnet {host} {port}")
            
        super().__init__(
            message=message,
            context=context,
            suggestions=suggestions
        )


# Configuration Management Exceptions

class ServiceAlreadyExistsError(UserError):
    """Raised when trying to add a service that already exists."""
    
    def __init__(
        self,
        service_name: str,
        config_source: Optional[str] = None
    ):
        message = f"Service '{service_name}' already exists in configuration"
        
        context = {
            "service_name": service_name,
            "config_source": config_source
        }
        
        # Generate alternative names
        alternatives = [
            f"{service_name}-2",
            f"{service_name}-dev",
            f"{service_name}-staging",
            f"my-{service_name}"
        ]
        
        suggestions = [
            f"Use a different service name (suggestions: {', '.join(alternatives[:2])})",
            f"Remove the existing service first: localport config remove {service_name}",
            "List existing services: localport config list"
        ]
        
        technical_details = f"Service name '{service_name}' conflicts with existing configuration"
        
        super().__init__(
            message=message,
            context=context,
            suggestions=suggestions,
            technical_details=technical_details
        )


class ServiceNotFoundError(UserError):
    """Raised when trying to access a service that doesn't exist."""
    
    def __init__(
        self,
        service_name: str,
        available_services: Optional[list[str]] = None,
        config_source: Optional[str] = None
    ):
        message = f"Service '{service_name}' not found in configuration"
        
        context = {
            "service_name": service_name,
            "available_services": available_services or [],
            "config_source": config_source
        }
        
        suggestions = [
            "Check the service name spelling",
            "List available services: localport config list"
        ]
        
        # Add suggestions for similar service names if available
        if available_services:
            # Simple similarity check - find services that start with same letter or contain similar patterns
            similar = [s for s in available_services if s.lower().startswith(service_name.lower()[:2])]
            if similar:
                suggestions.insert(1, f"Did you mean one of these? {', '.join(similar[:3])}")
            
            if len(available_services) <= 5:
                suggestions.append(f"Available services: {', '.join(available_services)}")
        
        technical_details = f"Service '{service_name}' does not exist in configuration"
        
        super().__init__(
            message=message,
            context=context,
            suggestions=suggestions,
            technical_details=technical_details
        )


class KubernetesResourceNotFoundError(UserError):
    """Raised when a Kubernetes resource cannot be found."""
    
    def __init__(
        self,
        resource_name: str,
        namespace: Optional[str] = None,
        resource_type: str = "service",
        context_name: Optional[str] = None,
        similar_resources: Optional[list[str]] = None
    ):
        if namespace:
            message = f"Kubernetes {resource_type} '{resource_name}' not found in namespace '{namespace}'"
        else:
            message = f"Kubernetes {resource_type} '{resource_name}' not found"
            
        context = {
            "resource_name": resource_name,
            "namespace": namespace,
            "resource_type": resource_type,
            "context_name": context_name,
            "similar_resources": similar_resources or []
        }
        
        suggestions = [
            "Check the resource name spelling",
            f"Verify the resource exists: kubectl get {resource_type}s",
            "Check if you're connected to the correct Kubernetes cluster"
        ]
        
        if namespace:
            suggestions.insert(2, f"Check the namespace: kubectl get {resource_type}s -n {namespace}")
        else:
            suggestions.insert(2, "Try specifying a different namespace with --namespace flag")
            
        if similar_resources:
            suggestions.insert(1, f"Did you mean one of these? {', '.join(similar_resources[:3])}")
            
        technical_details = f"Resource {resource_type}/{resource_name} not found via kubectl"
        
        super().__init__(
            message=message,
            context=context,
            suggestions=suggestions,
            technical_details=technical_details
        )


class MultipleNamespacesFoundError(UserError):
    """Raised when a resource is found in multiple namespaces."""
    
    def __init__(
        self,
        resource_name: str,
        namespaces: list[str],
        resource_type: str = "service"
    ):
        message = f"Kubernetes {resource_type} '{resource_name}' found in multiple namespaces"
        
        context = {
            "resource_name": resource_name,
            "namespaces": namespaces,
            "resource_type": resource_type
        }
        
        # Format namespace options for user selection
        namespace_options = [f"--namespace {ns}" for ns in namespaces[:3]]
        
        suggestions = [
            "Specify which namespace to use:",
            f"Use one of: {', '.join(namespace_options)}",
            f"Or use the interactive prompt to select a namespace"
        ]
        
        if len(namespaces) > 3:
            suggestions.append(f"Found in {len(namespaces)} namespaces total")
            
        technical_details = f"Resource {resource_type}/{resource_name} exists in namespaces: {', '.join(namespaces)}"
        
        super().__init__(
            message=message,
            context=context,
            suggestions=suggestions,
            technical_details=technical_details
        )


class NoPortsAvailableError(UserError):
    """Raised when a Kubernetes resource has no discoverable ports."""
    
    def __init__(
        self,
        resource_name: str,
        namespace: str,
        resource_type: str = "service"
    ):
        message = f"Kubernetes {resource_type} '{resource_name}' has no available ports for forwarding"
        
        context = {
            "resource_name": resource_name,
            "namespace": namespace,
            "resource_type": resource_type
        }
        
        suggestions = [
            f"Check if the {resource_type} has ports defined: kubectl describe {resource_type} {resource_name} -n {namespace}",
            "Manually specify ports using --local-port and --remote-port flags",
            f"Verify the {resource_type} is properly configured and running"
        ]
        
        if resource_type == "service":
            suggestions.insert(1, "Try port-forwarding to a pod instead of the service")
        elif resource_type == "deployment":
            suggestions.insert(1, "Check if the deployment pods have containerPort specifications")
        
        technical_details = f"No port specifications found in {resource_type} {resource_name}"
        
        super().__init__(
            message=message,
            context=context,
            suggestions=suggestions,
            technical_details=technical_details
        )
