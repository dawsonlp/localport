"""Configuration management commands for LocalPort CLI."""

import asyncio
import json
from pathlib import Path

import structlog
import typer
import yaml
from rich.console import Console
from rich.table import Table

from ...infrastructure.repositories.yaml_config_repository import YamlConfigRepository
from ..formatters.output_format import OutputFormat
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

        # Try to find existing config file
        config_path = None
        for path in ["./localport.yaml", "~/.config/localport/config.yaml", "~/.localport.yaml"]:
            test_path = Path(path).expanduser()
            if test_path.exists():
                config_path = str(test_path)
                break

        if not config_path:
            if output_format == OutputFormat.JSON:
                error_data = {
                    "timestamp": "2025-07-02T22:12:00.000000",
                    "command": "export",
                    "error": "No configuration file found",
                    "suggestion": "Create a configuration file first or specify --config"
                }
                console.print(json.dumps(error_data, indent=2))
            else:
                console.print(create_info_panel(
                    "No Configuration Found",
                    "No configuration file found in standard locations:\n" +
                    "• ./localport.yaml\n" +
                    "• ~/.config/localport/config.yaml\n" +
                    "• ~/.localport.yaml\n\n" +
                    "Create a configuration file first or use --config to specify a custom location."
                ))
            return

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
            # Try to find existing config file
            config_path = None
            for path in ["./localport.yaml", "~/.config/localport/config.yaml", "~/.localport.yaml"]:
                test_path = Path(path).expanduser()
                if test_path.exists():
                    config_path = str(test_path)
                    break

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
                console.print(create_error_panel(
                    "No Configuration Found",
                    "No configuration file found. Specify --config or create a configuration file."
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
