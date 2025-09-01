"""Configuration management commands for LocalPort CLI."""

import asyncio
import json
from pathlib import Path
from typing import Optional

import structlog
import typer
import yaml
from rich.console import Console
from rich.table import Table

from ...application.dto.connection_dto import (
    AddConnectionRequest, 
    RemoveConnectionRequest, 
    ListConnectionsRequest
)
from ...application.services.connection_discovery_service import ConnectionDiscoveryService
from ...application.services.connection_validation_service import ConnectionValidationService
from ...application.use_cases.add_connection import AddConnectionUseCase
from ...application.use_cases.remove_connection import RemoveConnectionUseCase
from ...application.use_cases.list_connections import ListConnectionsUseCase
from ...config.config_path_manager import ConfigPathManager
from ...domain.enums import ForwardingTechnology
from ...domain.exceptions import (
    ServiceAlreadyExistsError,
    KubernetesResourceNotFoundError,
    MultipleNamespacesFoundError,
    NoPortsAvailableError,
    ValidationError
)
from ...infrastructure.adapters.kubernetes_discovery_adapter import KubernetesDiscoveryAdapter
from ...infrastructure.repositories.yaml_config_repository import YamlConfigRepository
from ..formatters.connection_formatter import ConnectionFormatterFactory
from ..formatters.output_format import OutputFormat
from ..utils.connection_prompts import ConnectionPrompts
from ..utils.error_formatter import ErrorFormatter
from ..utils.rich_utils import (
    create_error_panel,
    create_info_panel,
    create_success_panel,
)

logger = structlog.get_logger()
console = Console()


async def export_config_command(
    output_file: str | None = None,
    format: str = "yaml",
    include_defaults: bool = True,
    include_disabled: bool = False,
    services: list[str] | None = None,
    tags: list[str] | None = None,
    output_format: OutputFormat = OutputFormat.TABLE
) -> None:
    """Export LocalPort configuration to different formats."""
    try:
        # Load current configuration
        config_repo = YamlConfigRepository()

        # Use centralized config path manager to find config file
        active_config = ConfigPathManager.find_active_config()
        
        if not active_config or not active_config.exists:
            if output_format == OutputFormat.JSON:
                error_data = {
                    "timestamp": "2025-07-02T22:12:00.000000",
                    "command": "export",
                    "error": "No configuration file found",
                    "suggestion": "Create a configuration file first or specify --config"
                }
                console.print(json.dumps(error_data, indent=2))
            else:
                # Use centralized search paths display
                search_paths_text = await ConfigPathManager.format_search_paths_with_status()
                console.print(create_info_panel(
                    "No Configuration Found",
                    f"No configuration file found. Searched:\n{search_paths_text}\n\n" +
                    "Create a configuration file first or use --config to specify a custom location."
                ))
            return

        config_path = str(active_config.path)

        # Load configuration
        config_repo = YamlConfigRepository(config_path)
        config_data = await config_repo.load_configuration()

        # Filter services if specified
        filtered_services = []
        for service_config in config_data.get('services', []):
            # Filter by service names
            if services and service_config['name'] not in services:
                continue

            # Filter by tags
            if tags:
                service_tags = service_config.get('tags', [])
                if not any(tag in service_tags for tag in tags):
                    continue

            # Filter by enabled status
            if not include_disabled and not service_config.get('enabled', True):
                continue

            filtered_services.append(service_config)

        # Build export data
        export_data = {
            'version': config_data.get('version', '1.0'),
            'services': filtered_services
        }

        # Include defaults if requested
        if include_defaults and 'defaults' in config_data:
            export_data['defaults'] = config_data['defaults']

        # Add metadata
        export_data['_metadata'] = {
            'exported_at': '2025-07-02T22:12:00.000000',
            'exported_by': 'localport export',
            'source_file': config_path,
            'total_services': len(filtered_services),
            'filters_applied': {
                'services': services,
                'tags': tags,
                'include_disabled': include_disabled,
                'include_defaults': include_defaults
            }
        }

        # Format output based on requested format
        if format.lower() == 'json':
            formatted_output = json.dumps(export_data, indent=2, ensure_ascii=False)
        elif format.lower() == 'yaml':
            formatted_output = yaml.dump(export_data, default_flow_style=False, allow_unicode=True)
        else:
            raise ValueError(f"Unsupported export format: {format}. Supported formats: yaml, json")

        # Output to file or stdout
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(formatted_output)

            if output_format == OutputFormat.JSON:
                result_data = {
                    "timestamp": "2025-07-02T22:12:00.000000",
                    "command": "export",
                    "success": True,
                    "output_file": str(output_path),
                    "format": format,
                    "services_exported": len(filtered_services)
                }
                console.print(json.dumps(result_data, indent=2))
            else:
                console.print(create_success_panel(
                    "Configuration Exported",
                    f"Successfully exported {len(filtered_services)} service(s) to {output_path}\n" +
                    f"Format: {format.upper()}"
                ))
        else:
            # Output to stdout
            if output_format == OutputFormat.JSON:
                # For JSON output format, wrap the config in a response structure
                result_data = {
                    "timestamp": "2025-07-02T22:12:00.000000",
                    "command": "export",
                    "format": format,
                    "configuration": export_data
                }
                console.print(json.dumps(result_data, indent=2))
            else:
                # For table/text output, just print the formatted config
                console.print(formatted_output)

    except Exception as e:
        logger.exception("Error exporting configuration")
        if output_format == OutputFormat.JSON:
            error_data = {
                "timestamp": "2025-07-02T22:12:00.000000",
                "command": "export",
                "error": str(e),
                "success": False
            }
            console.print(json.dumps(error_data, indent=2))
        else:
            console.print(create_error_panel(
                "Export Failed",
                str(e),
                "Check the configuration file and export parameters."
            ))
        raise typer.Exit(1)


async def validate_config_command(
    config_file: str | None = None,
    output_format: OutputFormat = OutputFormat.TABLE
) -> None:
    """Validate LocalPort configuration file."""
    try:
        # Determine config file to validate
        if config_file:
            config_path = config_file
        else:
            # Use centralized config path manager to find config file
            active_config = ConfigPathManager.find_active_config()
            if active_config and active_config.exists:
                config_path = str(active_config.path)
            else:
                config_path = None

        if not config_path:
            if output_format == OutputFormat.JSON:
                error_data = {
                    "timestamp": "2025-07-02T22:12:00.000000",
                    "command": "validate",
                    "error": "No configuration file found",
                    "valid": False
                }
                console.print(json.dumps(error_data, indent=2))
            else:
                # Use centralized search paths display
                search_paths_text = await ConfigPathManager.format_search_paths_with_status()
                console.print(create_error_panel(
                    "No Configuration Found",
                    f"No configuration file found. Searched:\n{search_paths_text}\n\n" +
                    "Specify --config or create a configuration file."
                ))
            raise typer.Exit(1)

        # Validate configuration
        config_repo = YamlConfigRepository(config_path)
        config_data = await config_repo.load_configuration()

        # Perform validation checks
        validation_results = []

        # Check version
        version = config_data.get('version')
        if not version:
            validation_results.append({
                "level": "warning",
                "message": "No version specified in configuration",
                "suggestion": "Add 'version: \"1.0\"' to your configuration"
            })

        # Check services
        services = config_data.get('services', [])
        if not services:
            validation_results.append({
                "level": "warning",
                "message": "No services defined in configuration",
                "suggestion": "Add at least one service to your configuration"
            })

        # Validate each service
        service_names = set()
        used_ports = set()

        for i, service in enumerate(services):
            service_name = service.get('name')
            if not service_name:
                validation_results.append({
                    "level": "error",
                    "message": f"Service at index {i} has no name",
                    "suggestion": "Add a 'name' field to the service"
                })
                continue

            # Check for duplicate names
            if service_name in service_names:
                validation_results.append({
                    "level": "error",
                    "message": f"Duplicate service name: {service_name}",
                    "suggestion": "Service names must be unique"
                })
            service_names.add(service_name)

            # Check required fields
            required_fields = ['technology', 'local_port', 'remote_port', 'connection']
            for field in required_fields:
                if field not in service:
                    validation_results.append({
                        "level": "error",
                        "message": f"Service '{service_name}' missing required field: {field}",
                        "suggestion": f"Add '{field}' to service '{service_name}'"
                    })

            # Check port conflicts
            local_port = service.get('local_port')
            if local_port:
                if local_port in used_ports:
                    validation_results.append({
                        "level": "error",
                        "message": f"Port conflict: {local_port} used by multiple services",
                        "suggestion": "Each service must use a unique local port"
                    })
                used_ports.add(local_port)

                # Check port range
                if not (1 <= local_port <= 65535):
                    validation_results.append({
                        "level": "error",
                        "message": f"Invalid port number: {local_port} in service '{service_name}'",
                        "suggestion": "Port numbers must be between 1 and 65535"
                    })

        # Count validation results
        errors = [r for r in validation_results if r['level'] == 'error']
        warnings = [r for r in validation_results if r['level'] == 'warning']

        # Output results
        if output_format == OutputFormat.JSON:
            result_data = {
                "timestamp": "2025-07-02T22:12:00.000000",
                "command": "validate",
                "config_file": config_path,
                "valid": len(errors) == 0,
                "total_services": len(services),
                "errors": len(errors),
                "warnings": len(warnings),
                "validation_results": validation_results
            }
            console.print(json.dumps(result_data, indent=2))
        else:
            # Table format
            if validation_results:
                table = Table(title=f"Configuration Validation: {Path(config_path).name}")
                table.add_column("Level", style="bold")
                table.add_column("Message", style="white")
                table.add_column("Suggestion", style="dim")

                for result in validation_results:
                    level = result['level'].upper()
                    level_color = "red" if result['level'] == 'error' else "yellow"

                    table.add_row(
                        f"[{level_color}]{level}[/{level_color}]",
                        result['message'],
                        result['suggestion']
                    )

                console.print(table)

            # Summary
            if errors:
                console.print(f"\n[red]❌ Configuration is invalid: {len(errors)} error(s), {len(warnings)} warning(s)[/red]")
                raise typer.Exit(1)
            elif warnings:
                console.print(f"\n[yellow]⚠️  Configuration is valid but has {len(warnings)} warning(s)[/yellow]")
            else:
                console.print(f"\n[green]✅ Configuration is valid: {len(services)} service(s) defined[/green]")

    except Exception as e:
        logger.exception("Error validating configuration")
        if output_format == OutputFormat.JSON:
            error_data = {
                "timestamp": "2025-07-02T22:12:00.000000",
                "command": "validate",
                "error": str(e),
                "valid": False
            }
            console.print(json.dumps(error_data, indent=2))
        else:
            console.print(create_error_panel(
                "Validation Failed",
                str(e),
                "Check the configuration file syntax and structure."
            ))
        raise typer.Exit(1)


# Sync wrappers for Typer
def export_config_sync(
    ctx: typer.Context,
    output_file: str | None = typer.Option(None, "--output", "-o", help="Output file path (default: stdout)"),
    format: str = typer.Option("yaml", "--format", "-f", help="Export format (yaml, json)"),
    include_defaults: bool = typer.Option(True, "--include-defaults/--no-defaults", help="Include default settings"),
    include_disabled: bool = typer.Option(False, "--include-disabled", help="Include disabled services"),
    services: list[str] | None = typer.Option(None, "--service", "-s", help="Export specific services only"),
    tags: list[str] | None = typer.Option(None, "--tag", "-t", help="Export services with specific tags only")
) -> None:
    """Export LocalPort configuration to different formats.

    Examples:
        localport config export                     # Export to stdout as YAML
        localport config export --format json      # Export as JSON
        localport config export -o backup.yaml     # Export to file
        localport config export --service postgres # Export specific service
        localport config export --tag database     # Export services with tag
        localport --output json config export      # JSON command output
    """
    # Get output format from context
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    asyncio.run(export_config_command(output_file, format, include_defaults, include_disabled, services, tags, output_format))


def validate_config_sync(
    ctx: typer.Context,
    config_file: str | None = typer.Option(None, "--config", "-c", help="Configuration file to validate")
) -> None:
    """Validate LocalPort configuration file.

    Examples:
        localport config validate                   # Validate default config
        localport config validate --config my.yaml # Validate specific file
        localport --output json config validate    # JSON validation output
    """
    # Get output format from context
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    asyncio.run(validate_config_command(config_file, output_format))


# New Connection Management Commands

async def add_connection_command(
    service_name: Optional[str] = None,
    technology: Optional[str] = None,
    resource_name: Optional[str] = None,
    namespace: Optional[str] = None,
    local_port: Optional[int] = None,
    remote_port: Optional[int] = None,
    ssh_host: Optional[str] = None,
    ssh_user: Optional[str] = None,
    ssh_key: Optional[str] = None,
    ssh_port: int = 22,
    output_format: OutputFormat = OutputFormat.TABLE,
    verbosity: int = 0
) -> None:
    """Add a new connection configuration."""
    error_formatter = ErrorFormatter(verbosity)
    
    try:
        # Initialize repositories and services
        config_repo = YamlConfigRepository()
        validation_service = ConnectionValidationService(config_repo)
        
        # Determine technology if not provided
        if not technology:
            console.print("\n[bold blue]🚀 LocalPort Connection Setup[/bold blue]")
            console.print("Which technology would you like to use?")
            console.print("1. [green]kubectl[/green] - Kubernetes port forwarding")
            console.print("2. [blue]ssh[/blue] - SSH tunnel")
            
            while True:
                choice = typer.prompt("Choose technology (1 or 2)")
                if choice in ["1", "kubectl", "k8s", "kubernetes"]:
                    technology = "kubectl"
                    break
                elif choice in ["2", "ssh"]:
                    technology = "ssh"
                    break
                else:
                    console.print("[red]Please choose 1 (kubectl) or 2 (ssh)[/red]")
        
        # Handle kubectl connection
        if technology.lower() == "kubectl":
            await _handle_kubectl_connection(
                config_repo, validation_service, service_name, resource_name, 
                namespace, local_port, remote_port, output_format
            )
        
        # Handle SSH connection
        elif technology.lower() == "ssh":
            await _handle_ssh_connection(
                config_repo, validation_service, service_name, ssh_host, ssh_user,
                ssh_key, ssh_port, local_port, remote_port, output_format
            )
        
        else:
            raise ValidationError(f"Unsupported technology: {technology}. Use 'kubectl' or 'ssh'")
            
    except (ServiceAlreadyExistsError, KubernetesResourceNotFoundError, 
            MultipleNamespacesFoundError, NoPortsAvailableError, ValidationError) as e:
        error_formatter.format_error(e, output_format)
        raise typer.Exit(1)
    except Exception as e:
        logger.exception("Error adding connection")
        error_formatter.format_error(e, output_format)
        raise typer.Exit(1)


async def _handle_kubectl_connection(
    config_repo: YamlConfigRepository,
    validation_service: ConnectionValidationService,
    service_name: Optional[str],
    resource_name: Optional[str],
    namespace: Optional[str],
    local_port: Optional[int],
    remote_port: Optional[int],
    output_format: OutputFormat
) -> None:
    """Handle kubectl connection setup."""
    # Initialize discovery services
    discovery_adapter = KubernetesDiscoveryAdapter()
    discovery_service = ConnectionDiscoveryService(discovery_adapter)
    add_use_case = AddConnectionUseCase(config_repo, discovery_adapter)
    
    # Get resource name if not provided
    if not resource_name:
        resource_name = await ConnectionPrompts.prompt_for_kubectl_resource_name()
    
    # Get current namespace
    current_namespace = await discovery_adapter.get_current_namespace()
    
    # Get namespace if not provided
    if namespace is None:
        namespace = await ConnectionPrompts.prompt_for_kubectl_namespace(current_namespace)
        if namespace is None:  # User chose current namespace
            namespace = current_namespace
    
    # Show discovery progress
    ConnectionPrompts.show_discovery_progress(resource_name, namespace)
    
    # Create connection request
    request = AddConnectionRequest(
        service_name=service_name or resource_name,  # Default to resource name
        technology=ForwardingTechnology.KUBECTL,
        connection_params={
            "resource_name": resource_name,
            "namespace": namespace
        },
        options={
            "local_port": local_port,
            "remote_port": remote_port
        }
    )
    
    # Execute use case
    response = await add_use_case.execute(request)
    
    # Format output
    formatter = ConnectionFormatterFactory.create_formatter(output_format.value, console)
    
    if response.success:
        target_info = f"{namespace}/{resource_name}"
        if hasattr(formatter, 'format_add_success'):
            formatter.format_add_success(
                service_name=response.service_name,
                technology="kubectl",
                local_port=response.configuration_added.get("local_port", 0),
                target_info=target_info
            )
        else:
            formatter.format_add_success(
                service_name=response.service_name,
                technology="kubectl", 
                local_port=response.configuration_added.get("local_port", 0),
                target_info=target_info
            )


async def _handle_ssh_connection(
    config_repo: YamlConfigRepository,
    validation_service: ConnectionValidationService,
    service_name: Optional[str],
    ssh_host: Optional[str],
    ssh_user: Optional[str],
    ssh_key: Optional[str],
    ssh_port: int,
    local_port: Optional[int],
    remote_port: Optional[int],
    output_format: OutputFormat
) -> None:
    """Handle SSH connection setup."""
    add_use_case = AddConnectionUseCase(config_repo, None)
    
    # Get SSH connection details
    if not ssh_host:
        ssh_host = await ConnectionPrompts.prompt_for_ssh_host()
    
    if not ssh_user:
        ssh_user = await ConnectionPrompts.prompt_for_ssh_user()
    
    if not ssh_key:
        ssh_key = await ConnectionPrompts.prompt_for_ssh_key_file()
    
    if not remote_port:
        remote_port = await ConnectionPrompts.prompt_for_remote_port()
    
    if not local_port:
        local_port = await ConnectionPrompts.prompt_for_local_port(suggested=remote_port)
    
    # Get service name if not provided
    if not service_name:
        suggested_name = f"ssh-{ssh_host}".replace(".", "-")
        service_name = await ConnectionPrompts.prompt_for_service_name(suggested_name)
    
    # Show validation progress
    ConnectionPrompts.show_validation_progress(service_name)
    
    # Create connection request
    connection_params = {
        "host": ssh_host,
        "port": ssh_port
    }
    if ssh_user:
        connection_params["user"] = ssh_user
    if ssh_key:
        connection_params["key_file"] = ssh_key
        
    request = AddConnectionRequest(
        service_name=service_name,
        technology=ForwardingTechnology.SSH,
        connection_params=connection_params,
        options={
            "local_port": local_port,
            "remote_port": remote_port
        }
    )
    
    # Execute use case
    response = await add_use_case.execute(request)
    
    # Format output
    formatter = ConnectionFormatterFactory.create_formatter(output_format.value, console)
    
    if response.success:
        target_info = ssh_host
        if hasattr(formatter, 'format_add_success'):
            formatter.format_add_success(
                service_name=response.service_name,
                technology="ssh",
                local_port=response.configuration_added.get("local_port", 0),
                target_info=target_info
            )


async def remove_connection_command(
    service_name: str,
    force: bool = False,
    output_format: OutputFormat = OutputFormat.TABLE,
    verbosity: int = 0
) -> None:
    """Remove a connection configuration."""
    error_formatter = ErrorFormatter(verbosity)
    
    try:
        # Initialize repositories and services
        config_repo = YamlConfigRepository()
        remove_use_case = RemoveConnectionUseCase(config_repo, None)  # Service repo not needed for config removal
        
        # Check if service exists
        if not await config_repo.service_exists(service_name):
            console.print(f"[red]Error: Service '{service_name}' not found in configuration.[/red]")
            raise typer.Exit(1)
        
        # Confirm removal if not forced
        if not force:
            confirmed = await ConnectionPrompts.confirm_service_removal(service_name, False)  # TODO: Check if running
            if not confirmed:
                console.print("Removal cancelled.")
                return
        
        # Create removal request
        request = RemoveConnectionRequest(service_name=service_name)
        
        # Execute use case
        response = await remove_use_case.execute(request)
        
        # Format output
        formatter = ConnectionFormatterFactory.create_formatter(output_format.value, console)
        
        if response.success:
            formatter.format_remove_success(service_name, response.was_running)
        
    except Exception as e:
        logger.exception("Error removing connection")
        error_formatter.format_error(e, output_format)
        raise typer.Exit(1)


async def list_connections_command(
    output_format: OutputFormat = OutputFormat.TABLE,
    verbosity: int = 0
) -> None:
    """List all configured connections."""
    error_formatter = ErrorFormatter(verbosity)
    
    try:
        # Initialize repositories and services
        config_repo = YamlConfigRepository()
        list_use_case = ListConnectionsUseCase(config_repo)
        
        # Execute use case
        request = ListConnectionsRequest()  # Use default values
        response = await list_use_case.execute(request)
        
        # Format output
        formatter = ConnectionFormatterFactory.create_formatter(output_format.value, console)
        formatter.format_connections_list(response)
        
    except Exception as e:
        logger.exception("Error listing connections")
        error_formatter.format_error(e, output_format)
        raise typer.Exit(1)


# Sync wrappers for Typer

def add_connection_sync(
    ctx: typer.Context,
    service_name: Optional[str] = typer.Option(None, "--name", "-n", help="Service name"),
    technology: Optional[str] = typer.Option(None, "--technology", "-t", help="Technology (kubectl/ssh)"),
    resource_name: Optional[str] = typer.Option(None, "--resource", "-r", help="Kubernetes resource name"),
    namespace: Optional[str] = typer.Option(None, "--namespace", help="Kubernetes namespace"),
    local_port: Optional[int] = typer.Option(None, "--local-port", "-l", help="Local port"),
    remote_port: Optional[int] = typer.Option(None, "--remote-port", help="Remote port"),
    ssh_host: Optional[str] = typer.Option(None, "--host", help="SSH hostname"),
    ssh_user: Optional[str] = typer.Option(None, "--user", "-u", help="SSH username"),
    ssh_key: Optional[str] = typer.Option(None, "--key", "-k", help="SSH key file"),
    ssh_port: int = typer.Option(22, "--ssh-port", help="SSH port")
) -> None:
    """Add a new connection configuration.

    Examples:
        localport config add                                    # Interactive setup
        localport config add --technology kubectl --resource postgres    # Kubectl connection
        localport config add --technology ssh --host server.com         # SSH connection
        localport --output json config add                     # JSON output format
    """
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    verbosity = ctx.obj.get('verbosity', 0)
    
    asyncio.run(add_connection_command(
        service_name, technology, resource_name, namespace,
        local_port, remote_port, ssh_host, ssh_user, ssh_key, ssh_port,
        output_format, verbosity
    ))


def remove_connection_sync(
    ctx: typer.Context,
    service_name: str = typer.Argument(..., help="Name of service to remove"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt")
) -> None:
    """Remove a connection configuration.

    Examples:
        localport config remove postgres            # Remove postgres service
        localport config remove postgres --force    # Remove without confirmation
        localport --output json config remove postgres    # JSON output format
    """
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    verbosity = ctx.obj.get('verbosity', 0)
    
    asyncio.run(remove_connection_command(service_name, force, output_format, verbosity))


def list_connections_sync(
    ctx: typer.Context
) -> None:
    """List all configured connections.

    Examples:
        localport config list                       # List all connections
        localport --output json config list        # JSON output format
    """
    output_format = ctx.obj.get('output_format', OutputFormat.TABLE)
    verbosity = ctx.obj.get('verbosity', 0)
    
    asyncio.run(list_connections_command(output_format, verbosity))
