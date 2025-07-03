"""Configuration change detection and analysis service."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class ChangeType(Enum):
    """Types of configuration changes."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class ServiceChange:
    """Represents a change to a service configuration."""
    service_name: str
    change_type: ChangeType
    old_config: dict[str, Any] | None = None
    new_config: dict[str, Any] | None = None
    changed_fields: set[str] = None

    def __post_init__(self):
        if self.changed_fields is None:
            self.changed_fields = set()

    @property
    def requires_restart(self) -> bool:
        """Check if this change requires a service restart."""
        if self.change_type in [ChangeType.ADDED, ChangeType.REMOVED]:
            return True

        # Fields that require restart when changed
        restart_required_fields = {
            'technology', 'local_port', 'remote_port', 'connection',
            'enabled'  # Enabling/disabling requires restart
        }

        return bool(self.changed_fields.intersection(restart_required_fields))

    @property
    def requires_health_monitor_restart(self) -> bool:
        """Check if this change requires health monitor restart."""
        if self.change_type in [ChangeType.ADDED, ChangeType.REMOVED]:
            return True

        # Fields that affect health monitoring
        health_monitor_fields = {
            'health_check', 'restart_policy'
        }

        return bool(self.changed_fields.intersection(health_monitor_fields))


@dataclass
class ConfigurationDiff:
    """Represents differences between two configurations."""
    service_changes: list[ServiceChange]
    defaults_changed: bool = False
    version_changed: bool = False
    old_version: str | None = None
    new_version: str | None = None

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return (
            len(self.service_changes) > 0 or
            self.defaults_changed or
            self.version_changed
        )

    @property
    def services_requiring_restart(self) -> list[str]:
        """Get list of services that require restart."""
        return [
            change.service_name
            for change in self.service_changes
            if change.requires_restart
        ]

    @property
    def requires_health_monitor_restart(self) -> bool:
        """Check if health monitor needs to be restarted."""
        return any(
            change.requires_health_monitor_restart
            for change in self.service_changes
        ) or self.defaults_changed

    def get_changes_by_type(self, change_type: ChangeType) -> list[ServiceChange]:
        """Get changes of a specific type."""
        return [
            change for change in self.service_changes
            if change.change_type == change_type
        ]

    def get_change_summary(self) -> dict[str, int]:
        """Get summary of changes by type."""
        summary = {change_type.value: 0 for change_type in ChangeType}

        for change in self.service_changes:
            summary[change.change_type.value] += 1

        return summary


class ConfigurationDiffer:
    """Detects and analyzes configuration changes."""

    def __init__(self):
        """Initialize the configuration differ."""
        pass

    async def compare_configurations(
        self,
        old_config: dict[str, Any],
        new_config: dict[str, Any]
    ) -> ConfigurationDiff:
        """Compare two configurations and return differences.

        Args:
            old_config: Previous configuration
            new_config: New configuration

        Returns:
            Configuration diff object
        """
        logger.debug("Comparing configurations")

        # Check version changes
        old_version = old_config.get('version')
        new_version = new_config.get('version')
        version_changed = old_version != new_version

        # Check defaults changes
        old_defaults = old_config.get('defaults', {})
        new_defaults = new_config.get('defaults', {})
        defaults_changed = old_defaults != new_defaults

        # Compare services
        service_changes = await self._compare_services(
            old_config.get('services', []),
            new_config.get('services', [])
        )

        diff = ConfigurationDiff(
            service_changes=service_changes,
            defaults_changed=defaults_changed,
            version_changed=version_changed,
            old_version=old_version,
            new_version=new_version
        )

        logger.info("Configuration comparison completed",
                   total_changes=len(service_changes),
                   defaults_changed=defaults_changed,
                   version_changed=version_changed,
                   services_requiring_restart=len(diff.services_requiring_restart))

        return diff

    async def _compare_services(
        self,
        old_services: list[dict[str, Any]],
        new_services: list[dict[str, Any]]
    ) -> list[ServiceChange]:
        """Compare service configurations.

        Args:
            old_services: Previous service configurations
            new_services: New service configurations

        Returns:
            List of service changes
        """
        changes = []

        # Create lookup maps by service name
        old_services_map = {svc.get('name'): svc for svc in old_services if svc.get('name')}
        new_services_map = {svc.get('name'): svc for svc in new_services if svc.get('name')}

        # Find all service names
        all_service_names = set(old_services_map.keys()) | set(new_services_map.keys())

        for service_name in all_service_names:
            old_service = old_services_map.get(service_name)
            new_service = new_services_map.get(service_name)

            if old_service is None:
                # Service was added
                changes.append(ServiceChange(
                    service_name=service_name,
                    change_type=ChangeType.ADDED,
                    new_config=new_service
                ))

            elif new_service is None:
                # Service was removed
                changes.append(ServiceChange(
                    service_name=service_name,
                    change_type=ChangeType.REMOVED,
                    old_config=old_service
                ))

            else:
                # Service exists in both - check for changes
                changed_fields = self._find_changed_fields(old_service, new_service)

                if changed_fields:
                    changes.append(ServiceChange(
                        service_name=service_name,
                        change_type=ChangeType.MODIFIED,
                        old_config=old_service,
                        new_config=new_service,
                        changed_fields=changed_fields
                    ))
                else:
                    changes.append(ServiceChange(
                        service_name=service_name,
                        change_type=ChangeType.UNCHANGED,
                        old_config=old_service,
                        new_config=new_service
                    ))

        return changes

    def _find_changed_fields(
        self,
        old_service: dict[str, Any],
        new_service: dict[str, Any]
    ) -> set[str]:
        """Find which fields changed between two service configurations.

        Args:
            old_service: Previous service configuration
            new_service: New service configuration

        Returns:
            Set of field names that changed
        """
        changed_fields = set()

        # Get all field names from both configurations
        all_fields = set(old_service.keys()) | set(new_service.keys())

        for field in all_fields:
            old_value = old_service.get(field)
            new_value = new_service.get(field)

            if not self._values_equal(old_value, new_value):
                changed_fields.add(field)

        return changed_fields

    def _values_equal(self, old_value: Any, new_value: Any) -> bool:
        """Check if two values are equal, handling nested structures.

        Args:
            old_value: Previous value
            new_value: New value

        Returns:
            True if values are equal
        """
        # Handle None values
        if old_value is None and new_value is None:
            return True
        if old_value is None or new_value is None:
            return False

        # Handle different types
        if not isinstance(old_value, type(new_value)) and not isinstance(new_value, type(old_value)):
            return False

        # Handle dictionaries recursively
        if isinstance(old_value, dict):
            if set(old_value.keys()) != set(new_value.keys()):
                return False

            for key in old_value.keys():
                if not self._values_equal(old_value[key], new_value[key]):
                    return False

            return True

        # Handle lists
        if isinstance(old_value, list):
            if len(old_value) != len(new_value):
                return False

            for i in range(len(old_value)):
                if not self._values_equal(old_value[i], new_value[i]):
                    return False

            return True

        # Handle primitive types
        return old_value == new_value

    async def get_affected_services(self, diff: ConfigurationDiff) -> list[str]:
        """Get list of services affected by configuration changes.

        Args:
            diff: Configuration diff

        Returns:
            List of affected service names
        """
        affected_services = []

        for change in diff.service_changes:
            if change.change_type != ChangeType.UNCHANGED:
                affected_services.append(change.service_name)

        return affected_services

    async def requires_service_restart(
        self,
        service_name: str,
        diff: ConfigurationDiff
    ) -> bool:
        """Check if a specific service requires restart.

        Args:
            service_name: Name of service to check
            diff: Configuration diff

        Returns:
            True if service requires restart
        """
        for change in diff.service_changes:
            if change.service_name == service_name:
                return change.requires_restart

        return False

    def format_diff_summary(self, diff: ConfigurationDiff) -> str:
        """Format a human-readable summary of configuration changes.

        Args:
            diff: Configuration diff

        Returns:
            Formatted summary string
        """
        if not diff.has_changes:
            return "No configuration changes detected"

        summary_parts = []

        # Version changes
        if diff.version_changed:
            summary_parts.append(f"Version: {diff.old_version} → {diff.new_version}")

        # Defaults changes
        if diff.defaults_changed:
            summary_parts.append("Defaults configuration changed")

        # Service changes summary
        change_summary = diff.get_change_summary()
        service_parts = []

        for change_type, count in change_summary.items():
            if count > 0:
                service_parts.append(f"{count} {change_type}")

        if service_parts:
            summary_parts.append(f"Services: {', '.join(service_parts)}")

        # Restart requirements
        restart_services = diff.services_requiring_restart
        if restart_services:
            summary_parts.append(f"Restart required: {', '.join(restart_services)}")

        if diff.requires_health_monitor_restart:
            summary_parts.append("Health monitor restart required")

        return "; ".join(summary_parts)

    def format_detailed_diff(self, diff: ConfigurationDiff) -> str:
        """Format a detailed view of configuration changes.

        Args:
            diff: Configuration diff

        Returns:
            Detailed formatted diff string
        """
        if not diff.has_changes:
            return "No configuration changes detected"

        lines = []

        # Version changes
        if diff.version_changed:
            lines.append(f"Version changed: {diff.old_version} → {diff.new_version}")
            lines.append("")

        # Defaults changes
        if diff.defaults_changed:
            lines.append("Defaults configuration changed")
            lines.append("")

        # Service changes
        if diff.service_changes:
            lines.append("Service changes:")

            for change in diff.service_changes:
                if change.change_type == ChangeType.UNCHANGED:
                    continue

                lines.append(f"  {change.service_name}: {change.change_type.value}")

                if change.change_type == ChangeType.MODIFIED and change.changed_fields:
                    fields_str = ", ".join(sorted(change.changed_fields))
                    lines.append(f"    Changed fields: {fields_str}")

                if change.requires_restart:
                    lines.append("    ⚠️  Restart required")

                if change.requires_health_monitor_restart:
                    lines.append("    🔄 Health monitor restart required")

                lines.append("")

        return "\n".join(lines).strip()
