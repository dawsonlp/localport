"""SSH-specific commands for LocalPort CLI."""

import asyncio
from pathlib import Path

import structlog
import typer
from rich.console import Console
from rich.table import Table

from ...infrastructure.adapters.ssh_adapter import SSHAdapter
from ...infrastructure.repositories.yaml_config_repository import YamlConfigRepository
from ..utils.rich_utils import (
    create_error_panel,
    create_success_panel,
    format_service_name,
)

logger = structlog.get_logger()
console = Console()


async def test_ssh_connectivity_command(
    service_name: str | None = None,
    host: str | None = None,
    user: str | None = None,
    port: int = 22,
    key_file: str | None = None,
    config_file: str | None = None
) -> None:
    """Test SSH connectivity for a service or connection details."""
    try:
        ssh_adapter = SSHAdapter()
        
        # Determine connection info source
        if service_name:
            # Load from service configuration
            if config_file:
                config_path = Path(config_file)
            else:
                # Use default config discovery
                config_path = None
                for path in ["./localport.yaml", "~/.config/localport/config.yaml"]:
                    test_path = Path(path).expanduser()
                    if test_path.exists():
                        config_path = test_path
                        break

            if not config_path or not config_path.exists():
                console.print(create_error_panel(
                    "Configuration File Not Found",
                    "No configuration file found to load service details.",
                    "Create a config file or specify connection details directly with --host, --user, etc."
                ))
                raise typer.Exit(1)

            # Load service configuration
            config_repo = YamlConfigRepository(str(config_path))
            await config_repo.load_configuration()
            services = await config_repo.load_services()
            
            # Find the specified service
            target_service = None
            for service in services:
                if service.name == service_name:
                    target_service = service
                    break
            
            if not target_service:
                console.print(create_error_panel(
                    "Service Not Found",
                    f"Service '{service_name}' not found in configuration.",
                    f"Available services: {', '.join([s.name for s in services])}"
                ))
                raise typer.Exit(1)
            
            # Check if service uses SSH
            if target_service.technology.value != 'ssh':
                console.print(create_error_panel(
                    "Invalid Service Type",
                    f"Service '{service_name}' uses {target_service.technology.value}, not SSH.",
                    "SSH connectivity testing is only available for SSH services."
                ))
                raise typer.Exit(1)
            
            # Extract SSH connection info
            connection_info = target_service.connection_info.to_dict()['config']
            
        elif host:
            # Use provided connection details
            connection_info = {
                'host': host,
                'port': port,
                'user': user,
                'key_file': key_file
            }
        else:
            console.print(create_error_panel(
                "Missing Connection Details",
                "Either specify a service name or provide connection details.",
                "Examples:\n" +
                "• Test service: localport ssh test my-service\n" +
                "• Test direct: localport ssh test --host example.com --user myuser"
            ))
            raise typer.Exit(1)

        # Validate connection info first
        console.print("[blue]Validating SSH connection configuration...[/blue]")
        validation_errors = await ssh_adapter.validate_connection_info(connection_info)
        
        if validation_errors:
            console.print(create_error_panel(
                "Configuration Validation Failed",
                "SSH connection configuration has errors:",
                "\n".join(f"• {error}" for error in validation_errors)
            ))
            raise typer.Exit(1)
        
        console.print("[green]✓[/green] Configuration validation passed")

        # Test SSH connectivity
        console.print("[blue]Testing SSH connectivity...[/blue]")
        success, message = await ssh_adapter.validate_ssh_connectivity(connection_info)
        
        if success:
            console.print(create_success_panel(
                "SSH Connectivity Test Passed",
                f"Successfully connected to {connection_info['host']}:{connection_info.get('port', 22)}"
            ))
            
            # Show connection details
            table = Table(title="Connection Details")
            table.add_column("Property", style="bold blue")
            table.add_column("Value", style="green")
            
            table.add_row("Host", connection_info['host'])
            table.add_row("Port", str(connection_info.get('port', 22)))
            table.add_row("User", connection_info.get('user', 'default'))
            table.add_row("Key File", connection_info.get('key_file', 'none'))
            table.add_row("Password Auth", "yes" if connection_info.get('password') else "no")
            
            console.print(table)
            
        else:
            console.print(create_error_panel(
                "SSH Connectivity Test Failed",
                f"Failed to connect to {connection_info['host']}:{connection_info.get('port', 22)}",
                f"Error: {message}\n\n" +
                "Troubleshooting:\n" +
                "• Check if the host is reachable\n" +
                "• Verify SSH service is running on the target\n" +
                "• Confirm authentication credentials\n" +
                "• Check firewall settings"
            ))
            raise typer.Exit(1)

    except typer.Exit:
        # Re-raise typer.Exit to allow clean exit
        raise
    except Exception as e:
        logger.exception("Error testing SSH connectivity")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs for more details."
        ))
        raise typer.Exit(1)


async def validate_ssh_config_command(
    config_file: str | None = None,
    service_name: str | None = None
) -> None:
    """Validate SSH configuration in a config file."""
    try:
        # Determine config file path
        if config_file:
            config_path = Path(config_file)
        else:
            # Use default config discovery
            config_path = None
            for path in ["./localport.yaml", "~/.config/localport/config.yaml"]:
                test_path = Path(path).expanduser()
                if test_path.exists():
                    config_path = test_path
                    break

        if not config_path or not config_path.exists():
            console.print(create_error_panel(
                "Configuration File Not Found",
                f"Configuration file not found: {config_path or 'default locations'}",
                "Create a config file or specify the correct path."
            ))
            raise typer.Exit(1)

        # Load configuration
        config_repo = YamlConfigRepository(str(config_path))
        await config_repo.load_configuration()
        services = await config_repo.load_services()
        
        # Filter SSH services
        ssh_services = [s for s in services if s.technology.value == 'ssh']
        
        if not ssh_services:
            console.print(create_error_panel(
                "No SSH Services Found",
                "No SSH services found in the configuration file.",
                "Add SSH services to the configuration or check the file path."
            ))
            raise typer.Exit(1)
        
        # Filter by service name if specified
        if service_name:
            ssh_services = [s for s in ssh_services if s.name == service_name]
            if not ssh_services:
                console.print(create_error_panel(
                    "SSH Service Not Found",
                    f"SSH service '{service_name}' not found in configuration.",
                    f"Available SSH services: {', '.join([s.name for s in services if s.technology.value == 'ssh'])}"
                ))
                raise typer.Exit(1)

        # Validate each SSH service
        ssh_adapter = SSHAdapter()
        validation_results = []
        
        console.print(f"[blue]Validating {len(ssh_services)} SSH service(s)...[/blue]")
        
        for service in ssh_services:
            connection_info = service.connection_info.to_dict()['config']
            errors = await ssh_adapter.validate_connection_info(connection_info)
            
            validation_results.append({
                'service': service,
                'errors': errors,
                'valid': len(errors) == 0
            })

        # Display results
        table = Table(title="SSH Configuration Validation Results")
        table.add_column("Service", style="bold blue")
        table.add_column("Host", style="cyan")
        table.add_column("Port", style="yellow")
        table.add_column("Status", style="bold")
        table.add_column("Issues", style="red")

        valid_count = 0
        for result in validation_results:
            service = result['service']
            connection_info = service.connection_info.to_dict()['config']
            
            if result['valid']:
                status = "[green]✓ Valid[/green]"
                issues = ""
                valid_count += 1
            else:
                status = "[red]✗ Invalid[/red]"
                issues = f"{len(result['errors'])} error(s)"
            
            table.add_row(
                format_service_name(service.name),
                connection_info['host'],
                str(connection_info.get('port', 22)),
                status,
                issues
            )

        console.print(table)

        # Show detailed errors for invalid services
        invalid_services = [r for r in validation_results if not r['valid']]
        if invalid_services:
            console.print("\n[bold red]Validation Errors:[/bold red]")
            for result in invalid_services:
                service = result['service']
                console.print(f"\n[bold]{service.name}:[/bold]")
                for error in result['errors']:
                    console.print(f"  • {error}")

        # Summary
        if valid_count == len(ssh_services):
            console.print(create_success_panel(
                "All SSH Services Valid",
                f"All {valid_count} SSH service(s) passed validation."
            ))
        else:
            invalid_count = len(ssh_services) - valid_count
            console.print(create_error_panel(
                "Validation Issues Found",
                f"{invalid_count} of {len(ssh_services)} SSH service(s) have configuration issues.",
                "Fix the issues shown above and run validation again."
            ))
            raise typer.Exit(1)

    except typer.Exit:
        # Re-raise typer.Exit to allow clean exit
        raise
    except Exception as e:
        logger.exception("Error validating SSH configuration")
        console.print(create_error_panel(
            "Unexpected Error",
            str(e),
            "Check the logs for more details."
        ))
        raise typer.Exit(1)


# Sync wrappers for Typer
def test_ssh_connectivity_sync(
    service_name: str | None = typer.Argument(None, help="Service name to test (from config)"),
    host: str | None = typer.Option(None, "--host", "-h", help="SSH host to test"),
    user: str | None = typer.Option(None, "--user", "-u", help="SSH username"),
    port: int = typer.Option(22, "--port", "-p", help="SSH port"),
    key_file: str | None = typer.Option(None, "--key-file", "-k", help="SSH private key file"),
    config_file: str | None = typer.Option(None, "--config", "-c", help="Configuration file path")
) -> None:
    """Test SSH connectivity for a service or connection details."""
    asyncio.run(test_ssh_connectivity_command(service_name, host, user, port, key_file, config_file))


def validate_ssh_config_sync(
    config_file: str | None = typer.Option(None, "--config", "-c", help="Configuration file path"),
    service_name: str | None = typer.Option(None, "--service", "-s", help="Specific service to validate")
) -> None:
    """Validate SSH configuration in a config file."""
    asyncio.run(validate_ssh_config_command(config_file, service_name))
