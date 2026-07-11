"""Enhanced progress indicators for LocalPort CLI operations."""

import asyncio
from typing import Any, Callable, Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)


class EnhancedProgress:
    """Enhanced progress indicator with better visual feedback and messaging."""

    def __init__(self, console: Console):
        self.console = console

    def create_spinner_progress(self, show_elapsed: bool = True) -> Progress:
        """Create a spinner-based progress indicator for indeterminate operations.
        
        Args:
            show_elapsed: Whether to show elapsed time
            
        Returns:
            Configured Progress instance
        """
        columns = [
            SpinnerColumn(style="cyan"),
            TextColumn("[progress.description]{task.description}"),
        ]
        
        if show_elapsed:
            columns.append(TimeElapsedColumn())
            
        return Progress(
            *columns,
            console=self.console,
            transient=False,
            expand=False
        )

    def create_step_progress(self, total_steps: int) -> Progress:
        """Create a step-based progress indicator for multi-step operations.
        
        Args:
            total_steps: Total number of steps
            
        Returns:
            Configured Progress instance
        """
        return Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=False,
            expand=False
        )

    async def run_with_spinner(
        self,
        operation: Callable,
        description: str,
        success_message: Optional[str] = None,
        show_elapsed: bool = True
    ) -> Any:
        """Run an async operation with a spinner progress indicator.
        
        Args:
            operation: Async function to execute
            description: Description to show during operation
            success_message: Message to show on success (optional)
            show_elapsed: Whether to show elapsed time
            
        Returns:
            Result of the operation
        """
        with self.create_spinner_progress(show_elapsed) as progress:
            task = progress.add_task(description, total=None)
            
            try:
                result = await operation()
                progress.update(task, description=f"✅ {success_message or description}")
                await asyncio.sleep(0.5)  # Brief pause to show success
                return result
            except Exception as e:
                progress.update(task, description=f"❌ {description} failed")
                await asyncio.sleep(0.5)  # Brief pause to show failure
                raise

    async def run_with_steps(
        self,
        steps: list[tuple[str, Callable]],
        overall_description: str = "Processing"
    ) -> list[Any]:
        """Run multiple operations with step-by-step progress.
        
        Args:
            steps: List of (description, operation) tuples
            overall_description: Overall operation description
            
        Returns:
            List of results from each step
        """
        results = []
        total_steps = len(steps)
        
        with self.create_step_progress(total_steps) as progress:
            main_task = progress.add_task(overall_description, total=total_steps)
            
            for i, (step_description, operation) in enumerate(steps, 1):
                progress.update(
                    main_task, 
                    description=f"{overall_description}: {step_description}",
                    completed=i-1
                )
                
                try:
                    result = await operation()
                    results.append(result)
                    
                    # Update with success indicator
                    progress.update(
                        main_task,
                        description=f"{overall_description}: ✅ {step_description}",
                        completed=i
                    )
                    
                    # Brief pause to show step completion
                    await asyncio.sleep(0.3)
                    
                except Exception as e:
                    progress.update(
                        main_task,
                        description=f"{overall_description}: ❌ {step_description} failed",
                        completed=i
                    )
                    await asyncio.sleep(0.5)
                    raise
            
            # Final success message
            progress.update(
                main_task,
                description=f"✅ {overall_description} completed successfully",
                completed=total_steps
            )
            await asyncio.sleep(0.5)
            
        return results


def get_operation_messages(operation: str, count: int = 1) -> dict[str, str]:
    """Get descriptive messages for different operations.
    
    Args:
        operation: Operation type (start, stop, restart, etc.)
        count: Number of items being operated on
        
    Returns:
        Dictionary with operation messages
    """
    messages = {
        "start": {
            "single": "🚀 Starting service",
            "multiple": f"🚀 Starting {count} services",
            "daemon": "⚙️ Starting LocalPort daemon",
            "success": "✅ Started successfully",
            "checking": "🔍 Checking service health",
            "configuring": "⚙️ Loading configuration",
        },
        "stop": {
            "single": "🛑 Stopping service", 
            "multiple": f"🛑 Stopping {count} services",
            "daemon": "⚙️ Stopping LocalPort daemon",
            "success": "✅ Stopped successfully",
            "cleanup": "🧹 Cleaning up resources",
        },
        "restart": {
            "single": "🔄 Restarting service",
            "multiple": f"🔄 Restarting {count} services", 
            "daemon": "⚙️ Restarting LocalPort daemon",
            "success": "✅ Restarted successfully",
            "stopping": "🛑 Stopping current instance",
            "starting": "🚀 Starting new instance",
        },
        "reload": {
            "daemon": "🔄 Reloading daemon configuration",
            "success": "✅ Configuration reloaded",
            "validating": "✅ Validating configuration",
            "applying": "⚙️ Applying changes",
        },
        "status": {
            "checking": "🔍 Checking service status",
            "daemon": "🔍 Checking daemon status", 
            "health": "💚 Checking health status",
            "success": "✅ Status retrieved",
        }
    }
    
    return messages.get(operation, {
        "single": f"{operation.title()}ing service",
        "multiple": f"{operation.title()}ing {count} services",
        "daemon": f"{operation.title()}ing daemon",
        "success": f"✅ {operation.title()}ed successfully"
    })
