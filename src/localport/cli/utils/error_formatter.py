"""
Error formatting utilities for LocalPort CLI.

This module provides user-friendly error message formatting with support
for different verbosity levels and Rich console formatting.
"""

from enum import Enum
from typing import Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown

from localport.domain.exceptions import (
    LocalPortError, 
    ErrorCategory,
    SSHKeyNotFoundError,
    ConfigurationValidationError,
    NetworkConnectionError
)


class VerbosityLevel(Enum):
    """Verbosity levels for error message formatting."""
    NORMAL = "normal"
    VERBOSE = "verbose" 
    DEBUG = "debug"


class ErrorFormatter:
    """
    Formats LocalPort errors for CLI display with appropriate verbosity levels.
    
    Transforms technical exceptions into user-friendly messages while preserving
    technical details for debugging when requested.
    """
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        
        # Error category to emoji mapping
        self.category_icons = {
            ErrorCategory.USER_ERROR: "❌",
            ErrorCategory.SYSTEM_ERROR: "⚠️", 
            ErrorCategory.NETWORK_ERROR: "🌐",
            ErrorCategory.VALIDATION_ERROR: "📝"
        }
        
        # Error category to color mapping
        self.category_colors = {
            ErrorCategory.USER_ERROR: "red",
            ErrorCategory.SYSTEM_ERROR: "yellow",
            ErrorCategory.NETWORK_ERROR: "blue", 
            ErrorCategory.VALIDATION_ERROR: "magenta"
        }
    
    def format_error(
        self, 
        error: Exception, 
        verbosity: VerbosityLevel = VerbosityLevel.NORMAL
    ) -> Panel:
        """
        Format an error for display based on verbosity level.
        
        Args:
            error: Exception to format (preferably LocalPortError)
            verbosity: Level of detail to include
            
        Returns:
            Rich Panel with formatted error message
        """
        if isinstance(error, LocalPortError):
            return self._format_localport_error(error, verbosity)
        else:
            return self._format_generic_error(error, verbosity)
    
    def _format_localport_error(
        self, 
        error: LocalPortError, 
        verbosity: VerbosityLevel
    ) -> Panel:
        """Format a LocalPortError with structured information."""
        
        # Get icon and color for error category
        icon = self.category_icons.get(error.category, "❓")
        color = self.category_colors.get(error.category, "white")
        
        # Build content based on verbosity level
        if verbosity == VerbosityLevel.NORMAL:
            content = self._build_normal_content(error, icon)
        elif verbosity == VerbosityLevel.VERBOSE:
            content = self._build_verbose_content(error, icon)
        else:  # DEBUG
            content = self._build_debug_content(error, icon)
        
        # Create title based on error type
        title = self._get_error_title(error)
        
        return Panel(
            content,
            title=f"[{color}]{title}[/{color}]",
            border_style=color,
            padding=(1, 2)
        )
    
    def _build_normal_content(self, error: LocalPortError, icon: str) -> Text:
        """Build normal verbosity content (user-friendly only)."""
        content = Text()
        
        # Main error message
        content.append(f"{icon} {error.message}\n\n", style="bold")
        
        # Quick fix suggestions
        if error.suggestions:
            content.append("💡 Quick Fix:\n", style="cyan bold")
            for suggestion in error.suggestions:
                content.append(f"   • {suggestion}\n", style="cyan")
            content.append("\n")
        
        # Hint about verbose mode
        content.append("Use --verbose for technical details.", style="dim")
        
        return content
    
    def _build_verbose_content(self, error: LocalPortError, icon: str) -> Text:
        """Build verbose content (user-friendly + context)."""
        content = Text()
        
        # Main error message
        content.append(f"{icon} {error.message}\n", style="bold")
        
        # Context information
        if error.context:
            content.append("\nContext:\n", style="yellow bold")
            for key, value in error.context.items():
                if value is not None and key != "key_path":  # Hide full paths in verbose
                    content.append(f"   {key}: {value}\n", style="yellow")
        
        # Suggestions
        if error.suggestions:
            content.append("\n💡 Suggestions:\n", style="cyan bold")
            for suggestion in error.suggestions:
                content.append(f"   • {suggestion}\n", style="cyan")
        
        # Technical details
        if error.technical_details:
            content.append("\nTechnical Details:\n", style="red bold")
            content.append(f"{error.technical_details}\n", style="red dim")
        
        return content
    
    def _build_debug_content(self, error: LocalPortError, icon: str) -> Text:
        """Build debug content (everything including internals)."""
        content = Text()
        
        # Main error message
        content.append(f"{icon} {error.message}\n", style="bold")
        
        # Full context (including sensitive info for debugging)
        content.append("\nFull Context:\n", style="yellow bold")
        for key, value in error.context.items():
            content.append(f"   {key}: {value}\n", style="yellow")
        
        # Error category and type
        content.append(f"\nError Type: {type(error).__name__}\n", style="magenta")
        content.append(f"Category: {error.category.value}\n", style="magenta")
        
        # Suggestions
        if error.suggestions:
            content.append("\n💡 Suggestions:\n", style="cyan bold")
            for suggestion in error.suggestions:
                content.append(f"   • {suggestion}\n", style="cyan")
        
        # Technical details
        if error.technical_details:
            content.append("\nTechnical Details:\n", style="red bold")
            content.append(f"{error.technical_details}\n", style="red dim")
        
        return content
    
    def _format_generic_error(
        self, 
        error: Exception, 
        verbosity: VerbosityLevel
    ) -> Panel:
        """Format a generic exception (fallback for non-LocalPort errors)."""
        
        content = Text()
        content.append(f"⚠️ {str(error)}\n", style="bold red")
        
        if verbosity != VerbosityLevel.NORMAL:
            content.append(f"\nError Type: {type(error).__name__}\n", style="yellow")
            
        if verbosity == VerbosityLevel.DEBUG:
            import traceback
            content.append("\nFull Traceback:\n", style="red bold")
            content.append(traceback.format_exc(), style="red dim")
        
        return Panel(
            content,
            title="[red]Unexpected Error[/red]",
            border_style="red",
            padding=(1, 2)
        )
    
    def _get_error_title(self, error: LocalPortError) -> str:
        """Get appropriate title for error type."""
        if isinstance(error, SSHKeyNotFoundError):
            return "SSH Key Missing"
        elif isinstance(error, ConfigurationValidationError):
            return "Configuration Error"
        elif isinstance(error, NetworkConnectionError):
            return "Connection Error"
        elif error.category == ErrorCategory.USER_ERROR:
            return "User Action Required"
        elif error.category == ErrorCategory.SYSTEM_ERROR:
            return "System Error"
        elif error.category == ErrorCategory.NETWORK_ERROR:
            return "Network Error"
        elif error.category == ErrorCategory.VALIDATION_ERROR:
            return "Validation Error"
        else:
            return "Error"
    
    def format_multiple_errors(
        self, 
        errors: list[Exception], 
        verbosity: VerbosityLevel = VerbosityLevel.NORMAL
    ) -> Panel:
        """
        Format multiple errors in a single panel.
        
        Args:
            errors: List of exceptions to format
            verbosity: Level of detail to include
            
        Returns:
            Rich Panel with formatted error messages
        """
        if not errors:
            return Panel("No errors to display", title="Errors")
        
        if len(errors) == 1:
            return self.format_error(errors[0], verbosity)
        
        content = Text()
        content.append(f"Found {len(errors)} errors:\n\n", style="bold red")
        
        for i, error in enumerate(errors, 1):
            content.append(f"{i}. ", style="bold")
            
            if isinstance(error, LocalPortError):
                icon = self.category_icons.get(error.category, "❓")
                content.append(f"{icon} {error.message}\n", style="red")
                
                if verbosity != VerbosityLevel.NORMAL and error.suggestions:
                    for suggestion in error.suggestions[:2]:  # Limit suggestions in multi-error view
                        content.append(f"   💡 {suggestion}\n", style="cyan dim")
            else:
                content.append(f"⚠️ {str(error)}\n", style="red")
            
            content.append("\n")
        
        if verbosity == VerbosityLevel.NORMAL:
            content.append("Use --verbose for detailed error information.", style="dim")
        
        return Panel(
            content,
            title="[red]Multiple Errors[/red]",
            border_style="red",
            padding=(1, 2)
        )
    
    def print_error(
        self, 
        error: Exception, 
        verbosity: VerbosityLevel = VerbosityLevel.NORMAL
    ) -> None:
        """Print formatted error to console."""
        panel = self.format_error(error, verbosity)
        self.console.print(panel)
    
    def print_multiple_errors(
        self, 
        errors: list[Exception], 
        verbosity: VerbosityLevel = VerbosityLevel.NORMAL
    ) -> None:
        """Print multiple formatted errors to console."""
        panel = self.format_multiple_errors(errors, verbosity)
        self.console.print(panel)


def create_error_panel(
    error: Exception,
    verbosity: VerbosityLevel = VerbosityLevel.NORMAL,
    console: Optional[Console] = None
) -> Panel:
    """
    Convenience function to create an error panel.
    
    This function provides backward compatibility with existing code
    while using the new error formatting system.
    """
    formatter = ErrorFormatter(console)
    return formatter.format_error(error, verbosity)
