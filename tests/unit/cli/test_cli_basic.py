"""Basic CLI tests for LocalPort."""

from unittest.mock import patch

from typer.testing import CliRunner

from localport.cli.app import app


class TestCLIBasic:
    """Test basic CLI functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_help_command(self):
        """Test that help command works."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "LocalPort" in result.stdout
        assert "Universal port forwarding manager" in result.stdout

    def test_version_command(self):
        """Test that version command works."""
        result = self.runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "LocalPort" in result.stdout
        assert "v0.1.0" in result.stdout

    def test_start_placeholder(self):
        """Test that start command shows placeholder message."""
        result = self.runner.invoke(app, ["start"])
        assert result.exit_code == 0
        assert "Start command not yet implemented" in result.stdout
        assert "Phase 5.2" in result.stdout

    def test_stop_placeholder(self):
        """Test that stop command shows placeholder message."""
        result = self.runner.invoke(app, ["stop"])
        assert result.exit_code == 0
        assert "Stop command not yet implemented" in result.stdout
        assert "Phase 5.2" in result.stdout

    def test_status_placeholder(self):
        """Test that status command shows placeholder message."""
        result = self.runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Status command not yet implemented" in result.stdout
        assert "Phase 5.2" in result.stdout

    def test_daemon_help(self):
        """Test that daemon help works."""
        result = self.runner.invoke(app, ["daemon", "--help"])
        assert result.exit_code == 0
        assert "Daemon management commands" in result.stdout

    def test_daemon_start_placeholder(self):
        """Test that daemon start shows placeholder message."""
        result = self.runner.invoke(app, ["daemon", "start"])
        assert result.exit_code == 0
        assert "Daemon start command not yet implemented" in result.stdout
        assert "Phase 5.2" in result.stdout

    def test_daemon_stop_placeholder(self):
        """Test that daemon stop shows placeholder message."""
        result = self.runner.invoke(app, ["daemon", "stop"])
        assert result.exit_code == 0
        assert "Daemon stop command not yet implemented" in result.stdout
        assert "Phase 5.2" in result.stdout

    def test_daemon_status_placeholder(self):
        """Test that daemon status shows placeholder message."""
        result = self.runner.invoke(app, ["daemon", "status"])
        assert result.exit_code == 0
        assert "Daemon status command not yet implemented" in result.stdout
        assert "Phase 5.2" in result.stdout

    def test_verbose_flag(self):
        """Test that verbose flag is accepted."""
        result = self.runner.invoke(app, ["--verbose", "start"])
        assert result.exit_code == 0
        assert "Start command not yet implemented" in result.stdout

    def test_quiet_flag(self):
        """Test that quiet flag is accepted."""
        result = self.runner.invoke(app, ["--quiet", "start"])
        assert result.exit_code == 0
        assert "Start command not yet implemented" in result.stdout

    def test_config_flag(self):
        """Test that config flag is accepted."""
        result = self.runner.invoke(app, ["--config", "/tmp/test.yaml", "start"])
        assert result.exit_code == 0
        assert "Start command not yet implemented" in result.stdout

    def test_log_level_flag(self):
        """Test that log-level flag is accepted."""
        result = self.runner.invoke(app, ["--log-level", "DEBUG", "start"])
        assert result.exit_code == 0
        assert "Start command not yet implemented" in result.stdout

    def test_no_color_flag(self):
        """Test that no-color flag is accepted."""
        result = self.runner.invoke(app, ["--no-color", "start"])
        assert result.exit_code == 0
        assert "Start command not yet implemented" in result.stdout

    def test_invalid_log_level(self):
        """Test that invalid log level shows error."""
        result = self.runner.invoke(app, ["--log-level", "INVALID", "start"])
        assert result.exit_code == 1
        assert "Invalid log level" in result.stdout

    @patch('localport.cli.app.Settings')
    def test_settings_initialization_error(self, mock_settings):
        """Test that settings initialization errors are handled."""
        mock_settings.side_effect = Exception("Test error")
        result = self.runner.invoke(app, ["start"])
        assert result.exit_code == 1
        assert "Error initializing LocalPort" in result.stdout
