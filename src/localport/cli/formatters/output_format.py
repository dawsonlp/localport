"""Output format enumeration for CLI commands."""

from enum import Enum


class OutputFormat(str, Enum):
    """Supported output formats for CLI commands."""

    TABLE = "table"
    JSON = "json"
    TEXT = "text"
    YAML = "yaml"  # Future extension

    def __str__(self) -> str:
        """Return the string value of the format."""
        return self.value

    @classmethod
    def from_string(cls, value: str) -> "OutputFormat":
        """Create OutputFormat from string value.

        Args:
            value: String representation of the format

        Returns:
            OutputFormat enum value

        Raises:
            ValueError: If the format is not supported
        """
        try:
            return cls(value.lower())
        except ValueError:
            valid_formats = [f.value for f in cls]
            raise ValueError(f"Unsupported output format '{value}'. Valid formats: {valid_formats}")
