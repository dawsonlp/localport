"""YAML-based configuration repository implementation."""

import os
import re
from pathlib import Path
from typing import Any

import structlog

try:
    import yaml
except ImportError:
    yaml = None

from ...config.config_path_manager import ConfigPathManager
from ...domain.entities.service import Service
from ...domain.enums import ForwardingTechnology
from ...domain.repositories.config_repository import (
    ConfigRepository,
    ConfigurationError,
)
from ...domain.value_objects.connection_info import ConnectionInfo
from ...domain.value_objects.port import Port
from ...domain.exceptions import SSHKeyNotFoundError

logger = structlog.get_logger()


class YamlConfigRepository(ConfigRepository):
    """YAML file-based configuration repository with environment variable substitution."""

    def __init__(self, config_path: str | None = None):
        """Initialize YAML configuration repository.

        Args:
            config_path: Path to YAML configuration file
        """
        self.config_path = Path(config_path) if config_path else self._find_config_file()
        self._config_cache: dict[str, Any] | None = None
        self._env_var_pattern = re.compile(r'\$\{([^}]+)\}')

    def _find_config_file(self) -> Path:
        """Find configuration file in standard locations.

        Returns:
            Path to configuration file
        """
        # Use centralized config path manager
        active_config = ConfigPathManager.find_active_config()
        
        if active_config and active_config.exists:
            logger.info("Found configuration file", path=str(active_config.path))
            return active_config.path

        # Default to first search path if none found
        search_paths = ConfigPathManager.get_default_search_paths()
        default_path = search_paths[0]  # localport.yaml in current directory
        logger.debug("Using default configuration path", path=str(default_path))
        return default_path

    async def load_configuration(self) -> dict[str, Any]:
        """Load configuration from YAML file.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If configuration file doesn't exist
            yaml.YAMLError: If YAML parsing fails
        """
        if yaml is None:
            raise ImportError("PyYAML is required for YAML configuration. Install with: pip install pyyaml")

        if not self.config_path.exists():
            logger.warning("Configuration file not found", path=str(self.config_path))
            return await self.get_default_configuration()

        try:
            with open(self.config_path, encoding='utf-8') as f:
                content = f.read()

            # Substitute environment variables
            content = self._substitute_environment_variables(content)

            # Parse YAML
            config = yaml.safe_load(content) or {}

            # Cache the configuration
            self._config_cache = config

            logger.info("Loaded configuration",
                       path=str(self.config_path),
                       services_count=len(config.get('services', [])))

            return config

        except yaml.YAMLError as e:
            logger.error("Failed to parse YAML configuration",
                        path=str(self.config_path),
                        error=str(e))
            raise
        except Exception as e:
            logger.error("Failed to load configuration",
                        path=str(self.config_path),
                        error=str(e))
            raise

    async def save_configuration(self, config: dict[str, Any]) -> None:
        """Save configuration to YAML file.

        Args:
            config: Configuration dictionary to save
        """
        if yaml is None:
            raise ImportError("PyYAML is required for YAML configuration. Install with: pip install pyyaml")

        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write YAML file
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    config,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    indent=2,
                    allow_unicode=True
                )

            # Update cache
            self._config_cache = config

            logger.info("Saved configuration",
                       path=str(self.config_path),
                       services_count=len(config.get('services', [])))

        except Exception as e:
            logger.error("Failed to save configuration",
                        path=str(self.config_path),
                        error=str(e))
            raise

    async def validate_configuration(self, config: dict[str, Any]) -> list[str]:
        """Validate configuration structure and content.

        Args:
            config: Configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required top-level fields
        if not isinstance(config, dict):
            errors.append("Configuration must be a dictionary")
            return errors

        # Validate version
        version = config.get('version')
        if not version:
            errors.append("Missing required field: version")
        elif not isinstance(version, str):
            errors.append("Version must be a string")

        # Validate services
        services = config.get('services')
        if not services:
            errors.append("Missing required field: services")
        elif not isinstance(services, list):
            errors.append("Services must be a list")
        else:
            # Validate each service
            service_names = set()
            for i, service in enumerate(services):
                service_errors = self._validate_service(service, i)
                errors.extend(service_errors)

                # Check for duplicate service names
                name = service.get('name')
                if name:
                    if name in service_names:
                        errors.append(f"Duplicate service name: {name}")
                    else:
                        service_names.add(name)

        # Validate defaults (optional)
        defaults = config.get('defaults')
        if defaults is not None:
            if not isinstance(defaults, dict):
                errors.append("Defaults must be a dictionary")
            else:
                defaults_errors = self._validate_defaults(defaults)
                errors.extend(defaults_errors)

        if errors:
            logger.warning("Configuration validation failed",
                          errors=errors,
                          error_count=len(errors))
        else:
            logger.debug("Configuration validation passed")

        return errors

    def _validate_service(self, service: dict[str, Any], index: int) -> list[str]:
        """Validate a single service configuration.

        Args:
            service: Service configuration to validate
            index: Index of service in list (for error messages)

        Returns:
            List of validation errors
        """
        errors = []
        prefix = f"Service {index}"

        if not isinstance(service, dict):
            errors.append(f"{prefix}: must be a dictionary")
            return errors

        # Required fields
        required_fields = ['name', 'technology', 'local_port', 'remote_port', 'connection']
        for field in required_fields:
            if field not in service:
                errors.append(f"{prefix}: missing required field '{field}'")

        # Validate name
        name = service.get('name')
        if name is not None:
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{prefix}: name must be a non-empty string")

        # Validate technology
        technology = service.get('technology')
        if technology is not None:
            valid_technologies = ['kubectl', 'ssh']
            if technology not in valid_technologies:
                errors.append(f"{prefix}: technology must be one of {valid_technologies}")

        # Validate ports
        for port_field in ['local_port', 'remote_port']:
            port = service.get(port_field)
            if port is not None:
                if not isinstance(port, int) or not (1 <= port <= 65535):
                    errors.append(f"{prefix}: {port_field} must be an integer between 1 and 65535")

        # Validate connection
        connection = service.get('connection')
        if connection is not None:
            if not isinstance(connection, dict):
                errors.append(f"{prefix}: connection must be a dictionary")

        # Validate optional fields
        enabled = service.get('enabled')
        if enabled is not None and not isinstance(enabled, bool):
            errors.append(f"{prefix}: enabled must be a boolean")

        tags = service.get('tags')
        if tags is not None:
            if not isinstance(tags, list):
                errors.append(f"{prefix}: tags must be a list")
            elif not all(isinstance(tag, str) for tag in tags):
                errors.append(f"{prefix}: all tags must be strings")

        description = service.get('description')
        if description is not None and not isinstance(description, str):
            errors.append(f"{prefix}: description must be a string")

        # Validate health_check
        health_check = service.get('health_check')
        if health_check is not None:
            health_errors = self._validate_health_check(health_check, f"{prefix}.health_check")
            errors.extend(health_errors)

        # Validate restart_policy
        restart_policy = service.get('restart_policy')
        if restart_policy is not None:
            restart_errors = self._validate_restart_policy(restart_policy, f"{prefix}.restart_policy")
            errors.extend(restart_errors)

        return errors

    def _validate_health_check(self, health_check: dict[str, Any], prefix: str) -> list[str]:
        """Validate health check configuration.

        Args:
            health_check: Health check configuration
            prefix: Error message prefix

        Returns:
            List of validation errors
        """
        errors = []

        if not isinstance(health_check, dict):
            errors.append(f"{prefix}: must be a dictionary")
            return errors

        # Validate type
        check_type = health_check.get('type')
        if not check_type:
            errors.append(f"{prefix}: missing required field 'type'")
        else:
            valid_types = ['tcp', 'http', 'https', 'kafka', 'postgres', 'postgresql']
            if check_type not in valid_types:
                errors.append(f"{prefix}: type must be one of {valid_types}")

        # Validate numeric fields
        numeric_fields = {
            'interval': (1, 3600),  # 1 second to 1 hour
            'timeout': (0.1, 300),  # 0.1 second to 5 minutes
            'failure_threshold': (1, 100),
            'success_threshold': (1, 100)
        }

        for field, (min_val, max_val) in numeric_fields.items():
            value = health_check.get(field)
            if value is not None:
                if not isinstance(value, int | float) or not (min_val <= value <= max_val):
                    errors.append(f"{prefix}.{field}: must be a number between {min_val} and {max_val}")

        return errors

    def _validate_restart_policy(self, restart_policy: dict[str, Any], prefix: str) -> list[str]:
        """Validate restart policy configuration.

        Args:
            restart_policy: Restart policy configuration
            prefix: Error message prefix

        Returns:
            List of validation errors
        """
        errors = []

        if not isinstance(restart_policy, dict):
            errors.append(f"{prefix}: must be a dictionary")
            return errors

        # Validate enabled
        enabled = restart_policy.get('enabled')
        if enabled is not None and not isinstance(enabled, bool):
            errors.append(f"{prefix}.enabled: must be a boolean")

        # Validate numeric fields
        numeric_fields = {
            'max_attempts': (1, 100),
            'initial_delay': (1, 3600),
            'max_delay': (1, 86400),  # 1 day
            'backoff_multiplier': (1.0, 10.0)
        }

        for field, (min_val, max_val) in numeric_fields.items():
            value = restart_policy.get(field)
            if value is not None:
                if not isinstance(value, int | float) or not (min_val <= value <= max_val):
                    errors.append(f"{prefix}.{field}: must be a number between {min_val} and {max_val}")

        return errors

    def _validate_defaults(self, defaults: dict[str, Any]) -> list[str]:
        """Validate defaults configuration.

        Args:
            defaults: Defaults configuration

        Returns:
            List of validation errors
        """
        errors = []

        # Validate health_check defaults
        health_check = defaults.get('health_check')
        if health_check is not None:
            health_errors = self._validate_health_check(health_check, "defaults.health_check")
            errors.extend(health_errors)

        # Validate restart_policy defaults
        restart_policy = defaults.get('restart_policy')
        if restart_policy is not None:
            restart_errors = self._validate_restart_policy(restart_policy, "defaults.restart_policy")
            errors.extend(restart_errors)

        # Validate cluster_health defaults
        cluster_health = defaults.get('cluster_health')
        if cluster_health is not None:
            cluster_errors = self._validate_cluster_health(cluster_health, "defaults.cluster_health")
            errors.extend(cluster_errors)

        return errors

    def _validate_cluster_health(self, cluster_health: dict[str, Any], prefix: str) -> list[str]:
        """Validate cluster health configuration.

        Args:
            cluster_health: Cluster health configuration
            prefix: Error message prefix

        Returns:
            List of validation errors
        """
        errors = []

        if not isinstance(cluster_health, dict):
            errors.append(f"{prefix}: must be a dictionary")
            return errors

        # Validate enabled
        enabled = cluster_health.get('enabled')
        if enabled is not None and not isinstance(enabled, bool):
            errors.append(f"{prefix}.enabled: must be a boolean")

        # Validate numeric fields
        numeric_fields = {
            'interval': (60, 3600),  # 1 minute to 1 hour
            'timeout': (5, 300),     # 5 seconds to 5 minutes
            'retry_attempts': (0, 10),
            'failure_threshold': (1, 100)
        }

        for field, (min_val, max_val) in numeric_fields.items():
            value = cluster_health.get(field)
            if value is not None:
                if not isinstance(value, int | float) or not (min_val <= value <= max_val):
                    errors.append(f"{prefix}.{field}: must be a number between {min_val} and {max_val}")

        # Validate commands section
        commands = cluster_health.get('commands')
        if commands is not None:
            if not isinstance(commands, dict):
                errors.append(f"{prefix}.commands: must be a dictionary")
            else:
                valid_commands = ['cluster_info', 'pod_status', 'node_status', 'events_on_failure']
                for cmd_name, cmd_config in commands.items():
                    if cmd_name not in valid_commands:
                        errors.append(f"{prefix}.commands.{cmd_name}: unknown command (valid: {valid_commands})")
                    elif cmd_config is not None:
                        if isinstance(cmd_config, bool):
                            # Simple boolean enable/disable
                            continue
                        elif isinstance(cmd_config, dict):
                            # Detailed command configuration
                            cmd_enabled = cmd_config.get('enabled')
                            if cmd_enabled is not None and not isinstance(cmd_enabled, bool):
                                errors.append(f"{prefix}.commands.{cmd_name}.enabled: must be a boolean")
                        else:
                            errors.append(f"{prefix}.commands.{cmd_name}: must be a boolean or dictionary")

        return errors

    async def get_default_configuration(self) -> dict[str, Any]:
        """Get default configuration template.

        Returns:
            Default configuration dictionary
        """
        return {
            'version': '1.0',
            'services': [],
            'defaults': {
                'health_check': {
                    'type': 'tcp',
                    'interval': 30,
                    'timeout': 5.0,
                    'failure_threshold': 3,
                    'success_threshold': 1,
                    'cluster_aware': True  # NEW: Consider cluster health in service health decisions
                },
                'restart_policy': {
                    'enabled': True,
                    'max_attempts': 5,
                    'backoff_multiplier': 2.0,
                    'initial_delay': 1,
                    'max_delay': 300
                },
                'cluster_health': {
                    'enabled': True,
                    'interval': 240,  # 4 minutes
                    'timeout': 30,    # 30 seconds per kubectl command
                    'retry_attempts': 2,
                    'failure_threshold': 3,  # Consecutive failures before marking cluster unhealthy
                    
                    # Commands to execute
                    'commands': {
                        'cluster_info': True,
                        'pod_status': True,
                        'node_status': True,
                        'events_on_failure': True
                    }
                }
            }
        }

    def _substitute_environment_variables(self, content: str) -> str:
        """Substitute environment variables in configuration content.

        Args:
            content: Configuration content with ${VAR} placeholders

        Returns:
            Content with environment variables substituted
        """
        def replace_var(match):
            var_expr = match.group(1)

            # Handle default values: ${VAR:default}
            if ':' in var_expr:
                var_name, default_value = var_expr.split(':', 1)
                return os.getenv(var_name.strip(), default_value)
            else:
                var_name = var_expr.strip()
                value = os.getenv(var_name)

                if value is None:
                    logger.warning("Environment variable not found",
                                  variable=var_name,
                                  placeholder=match.group(0))
                    # Return the original placeholder if variable not found
                    return match.group(0)

                return value

        # Substitute all ${VAR} and ${VAR:default} patterns
        substituted = self._env_var_pattern.sub(replace_var, content)

        # Log substitutions for debugging
        if substituted != content:
            substitution_count = len(self._env_var_pattern.findall(content))
            logger.debug("Substituted environment variables",
                        count=substitution_count)

        return substituted

    def get_config_path(self) -> Path:
        """Get the path to the configuration file.

        Returns:
            Path to configuration file
        """
        return self.config_path

    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._config_cache = None
        logger.debug("Cleared configuration cache")

    async def reload_configuration(self) -> dict[str, Any]:
        """Reload configuration from file, bypassing cache.

        Returns:
            Reloaded configuration dictionary
        """
        self.clear_cache()
        return await self.load_configuration()

    async def backup_configuration(self, backup_path: str | None = None) -> str:
        """Create a backup of the current configuration file.

        Args:
            backup_path: Path for backup file (auto-generated if None)

        Returns:
            Path to backup file
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        if backup_path is None:
            timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f"{self.config_path}.backup_{timestamp}"

        backup_path = Path(backup_path)

        # Copy configuration file
        import shutil
        shutil.copy2(self.config_path, backup_path)

        logger.info("Created configuration backup",
                   original=str(self.config_path),
                   backup=str(backup_path))

        return str(backup_path)

    # Abstract method implementations
    async def load_services(self, config_path: Path | None = None) -> list[Service]:
        """Load services from configuration."""
        if config_path:
            old_path = self.config_path
            self.config_path = config_path
            try:
                config = await self._load_config_internal()
            finally:
                self.config_path = old_path
        else:
            config = await self._load_config_internal()

        services = []

        for service_config in config.get('services', []):
            try:
                # Parse technology and connection info
                technology = ForwardingTechnology(service_config['technology'])
                conn_config = service_config['connection']
                
                # Create ConnectionInfo based on technology
                if technology == ForwardingTechnology.KUBECTL:
                    connection_info = ConnectionInfo.kubectl(
                        resource_name=conn_config['resource_name'],
                        namespace=conn_config.get('namespace', 'default'),
                        resource_type=conn_config.get('resource_type', 'service'),
                        context=conn_config.get('context')
                    )
                elif technology == ForwardingTechnology.SSH:
                    connection_info = ConnectionInfo.ssh(
                        host=conn_config['host'],
                        user=conn_config.get('user'),
                        port=conn_config.get('port', 22),
                        key_file=conn_config.get('key_file'),
                        password=conn_config.get('password'),
                        remote_host=conn_config.get('remote_host')
                    )
                else:
                    raise ValueError(f"Unsupported technology: {technology}")

                # Create Service entity from configuration
                service = Service.create(
                    name=service_config['name'],
                    technology=technology,
                    local_port=service_config['local_port'],
                    remote_port=service_config['remote_port'],
                    connection_info=connection_info,
                    tags=service_config.get('tags', []),
                    description=service_config.get('description'),
                    health_check_config=service_config.get('health_check'),
                    restart_policy=service_config.get('restart_policy')
                )
                services.append(service)
            except SSHKeyNotFoundError as e:
                # Enrich SSH key error with service and config context
                enriched_error = SSHKeyNotFoundError(
                    key_path=e.context['key_path'],
                    service_name=service_config.get('name', 'unknown'),
                    config_source=str(self.config_path)
                )
                logger.error("SSH key not found for service",
                           service_name=service_config.get('name', 'unknown'),
                           key_path=e.context.get('safe_path', e.context['key_path']),
                           config_source=str(self.config_path))
                raise enriched_error
            except Exception as e:
                logger.error("Failed to create service from config",
                           service_name=service_config.get('name', 'unknown'),
                           error=str(e))
                raise ConfigurationError(f"Invalid service configuration: {e}")

        return services

    async def _load_config_internal(self) -> dict[str, Any]:
        """Internal method to load configuration without recursion."""
        if yaml is None:
            raise ImportError("PyYAML is required for YAML configuration. Install with: pip install pyyaml")

        if not self.config_path.exists():
            logger.warning("Configuration file not found", path=str(self.config_path))
            return await self.get_default_configuration()

        try:
            with open(self.config_path, encoding='utf-8') as f:
                content = f.read()

            # Substitute environment variables
            content = self._substitute_environment_variables(content)

            # Parse YAML
            config = yaml.safe_load(content) or {}

            # Cache the configuration
            self._config_cache = config

            logger.info("Loaded configuration",
                       path=str(self.config_path),
                       services_count=len(config.get('services', [])))

            return config

        except yaml.YAMLError as e:
            logger.error("Failed to parse YAML configuration",
                        path=str(self.config_path),
                        error=str(e))
            raise
        except Exception as e:
            logger.error("Failed to load configuration",
                        path=str(self.config_path),
                        error=str(e))
            raise

    async def get_default_config_paths(self) -> list[Path]:
        """Get list of default configuration file paths to search."""
        return [
            Path.cwd() / "localport.yaml",
            Path.cwd() / "localport.yml",
            Path.cwd() / ".localport.yaml",
            Path.home() / ".localport.yaml",
            Path.home() / ".config" / "localport" / "config.yaml",
            Path("/etc/localport/config.yaml"),
        ]

    async def find_config_file(self) -> Path | None:
        """Find the first existing configuration file in default locations."""
        search_paths = await self.get_default_config_paths()

        for path in search_paths:
            if path.exists():
                logger.info("Found configuration file", path=str(path))
                return path

        logger.debug("No configuration file found in default locations")
        return None

    async def substitute_environment_variables(self, config: dict[str, Any]) -> dict[str, Any]:
        """Substitute environment variables in configuration."""
        import json

        # Convert config to JSON string, substitute variables, then parse back
        config_str = json.dumps(config)
        substituted_str = self._substitute_environment_variables(config_str)

        try:
            return json.loads(substituted_str)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Failed to parse configuration after environment variable substitution: {e}")

    # Service Management Methods

    async def add_service_config(self, service: dict[str, Any]) -> None:
        """Add a new service configuration to the configuration file.
        
        Args:
            service: Service configuration dictionary to add
            
        Raises:
            ConfigurationError: If service cannot be added or configuration is invalid
            ServiceAlreadyExistsError: If a service with the same name already exists
        """
        from ...domain.exceptions import ServiceAlreadyExistsError
        
        logger.debug("Adding service configuration", service_name=service.get('name'))
        
        # Load current configuration
        config = await self.load_configuration()
        
        # Check if service already exists
        service_name = service.get('name')
        if not service_name:
            raise ConfigurationError("Service configuration missing 'name' field")
            
        if await self.service_exists(service_name):
            raise ServiceAlreadyExistsError(f"Service '{service_name}' already exists")
        
        # Create backup before modifying
        backup_path = None
        try:
            if self.config_path.exists():
                backup_path = await self.backup_configuration()
            
            # Add service to configuration
            if 'services' not in config:
                config['services'] = []
            
            config['services'].append(service)
            
            # Validate the updated configuration
            validation_errors = await self.validate_configuration(config)
            if validation_errors:
                raise ConfigurationError(f"Invalid service configuration: {'; '.join(validation_errors)}")
            
            # Save updated configuration
            await self.save_configuration(config)
            
            logger.info("Successfully added service configuration",
                       service_name=service_name,
                       total_services=len(config['services']))
                       
        except Exception as e:
            # Restore from backup if operation failed
            if backup_path and Path(backup_path).exists():
                logger.warning("Restoring configuration from backup due to error",
                              backup_path=backup_path, error=str(e))
                try:
                    import shutil
                    shutil.copy2(backup_path, self.config_path)
                    self.clear_cache()
                except Exception as restore_error:
                    logger.error("Failed to restore configuration backup",
                               backup_path=backup_path, error=str(restore_error))
            raise

    async def remove_service_config(self, service_name: str) -> bool:
        """Remove a service configuration from the configuration file.
        
        Args:
            service_name: Name of the service to remove
            
        Returns:
            True if service was removed, False if service was not found
            
        Raises:
            ConfigurationError: If there's an error updating the configuration
        """
        logger.debug("Removing service configuration", service_name=service_name)
        
        # Load current configuration
        config = await self.load_configuration()
        
        # Find and remove the service
        services = config.get('services', [])
        original_count = len(services)
        
        # Filter out the service to remove
        config['services'] = [s for s in services if s.get('name') != service_name]
        
        if len(config['services']) == original_count:
            logger.debug("Service not found for removal", service_name=service_name)
            return False
        
        # Create backup before modifying
        backup_path = None
        try:
            if self.config_path.exists():
                backup_path = await self.backup_configuration()
            
            # Save updated configuration
            await self.save_configuration(config)
            
            logger.info("Successfully removed service configuration",
                       service_name=service_name,
                       remaining_services=len(config['services']))
            return True
                       
        except Exception as e:
            # Restore from backup if operation failed
            if backup_path and Path(backup_path).exists():
                logger.warning("Restoring configuration from backup due to error",
                              backup_path=backup_path, error=str(e))
                try:
                    import shutil
                    shutil.copy2(backup_path, self.config_path)
                    self.clear_cache()
                except Exception as restore_error:
                    logger.error("Failed to restore configuration backup",
                               backup_path=backup_path, error=str(restore_error))
            raise

    async def get_service_names(self) -> list[str]:
        """Get the names of all configured services.
        
        Returns:
            List of service names from the configuration
            
        Raises:
            ConfigurationError: If configuration cannot be loaded
        """
        logger.debug("Getting service names")
        
        try:
            config = await self.load_configuration()
            services = config.get('services', [])
            
            service_names = []
            for service in services:
                name = service.get('name')
                if name:
                    service_names.append(name)
                else:
                    logger.warning("Found service without name in configuration")
            
            logger.debug("Retrieved service names", count=len(service_names))
            return service_names
            
        except Exception as e:
            logger.error("Failed to get service names", error=str(e))
            raise ConfigurationError(f"Failed to load configuration: {e}")

    async def service_exists(self, service_name: str) -> bool:
        """Check if a service with the given name exists in the configuration.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            True if service exists, False otherwise
            
        Raises:
            ConfigurationError: If configuration cannot be loaded
        """
        logger.debug("Checking if service exists", service_name=service_name)
        
        try:
            service_names = await self.get_service_names()
            exists = service_name in service_names
            
            logger.debug("Service existence check completed",
                        service_name=service_name, exists=exists)
            return exists
            
        except Exception as e:
            logger.error("Failed to check service existence",
                        service_name=service_name, error=str(e))
            raise ConfigurationError(f"Failed to check service existence: {e}")

    async def get_service_config(self, service_name: str) -> dict[str, Any] | None:
        """Get the configuration for a specific service.
        
        Args:
            service_name: Name of the service to get configuration for
            
        Returns:
            Service configuration dictionary, or None if service not found
            
        Raises:
            ConfigurationError: If configuration cannot be loaded
        """
        logger.debug("Getting service configuration", service_name=service_name)
        
        try:
            config = await self.load_configuration()
            services = config.get('services', [])
            
            for service in services:
                if service.get('name') == service_name:
                    logger.debug("Found service configuration", service_name=service_name)
                    return service
            
            logger.debug("Service configuration not found", service_name=service_name)
            return None
            
        except Exception as e:
            logger.error("Failed to get service configuration",
                        service_name=service_name, error=str(e))
            raise ConfigurationError(f"Failed to load configuration: {e}")

    async def update_service_config(self, service_name: str, service: dict[str, Any]) -> bool:
        """Update an existing service configuration.
        
        Args:
            service_name: Name of the service to update
            service: Updated service configuration dictionary
            
        Returns:
            True if service was updated, False if service was not found
            
        Raises:
            ConfigurationError: If there's an error updating the configuration
        """
        logger.debug("Updating service configuration", service_name=service_name)
        
        # Load current configuration
        config = await self.load_configuration()
        
        # Find and update the service
        services = config.get('services', [])
        updated = False
        
        for i, existing_service in enumerate(services):
            if existing_service.get('name') == service_name:
                # Update the service configuration
                services[i] = service
                updated = True
                break
        
        if not updated:
            logger.debug("Service not found for update", service_name=service_name)
            return False
        
        # Create backup before modifying
        backup_path = None
        try:
            if self.config_path.exists():
                backup_path = await self.backup_configuration()
            
            # Validate the updated configuration
            validation_errors = await self.validate_configuration(config)
            if validation_errors:
                raise ConfigurationError(f"Invalid service configuration: {'; '.join(validation_errors)}")
            
            # Save updated configuration
            await self.save_configuration(config)
            
            logger.info("Successfully updated service configuration",
                       service_name=service_name)
            return True
                       
        except Exception as e:
            # Restore from backup if operation failed
            if backup_path and Path(backup_path).exists():
                logger.warning("Restoring configuration from backup due to error",
                              backup_path=backup_path, error=str(e))
                try:
                    import shutil
                    shutil.copy2(backup_path, self.config_path)
                    self.clear_cache()
                except Exception as restore_error:
                    logger.error("Failed to restore configuration backup",
                               backup_path=backup_path, error=str(restore_error))
            raise

    async def get_configuration_path(self) -> Path:
        """Get the path to the currently active configuration file.
        
        Returns:
            Path to the configuration file being used
        """
        return self.config_path
