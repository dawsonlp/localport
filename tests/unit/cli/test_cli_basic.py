"""Tests for CLI basic functionality."""

from typer.testing import CliRunner

from localport.cli.app import app

runner = CliRunner()


class TestCLIBasic:
    """Test basic CLI command structure and options."""

    def test_version_command(self):
        """Test --version flag shows version info."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        # Version output contains version number
        assert "v" in result.stdout or "LocalPort" in result.stdout

    def test_help_command(self):
        """Test --help flag shows help."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "LocalPort" in result.stdout

    def test_start_command_exists(self):
        """Test that start command is registered."""
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0

    def test_stop_command_exists(self):
        """Test that stop command is registered."""
        result = runner.invoke(app, ["stop", "--help"])
        assert result.exit_code == 0

    def test_status_command_exists(self):
        """Test that status command is registered."""
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0

    def test_daemon_start_exists(self):
        """Test that daemon start command is registered."""
        result = runner.invoke(app, ["daemon", "start", "--help"])
        assert result.exit_code == 0

    def test_daemon_stop_exists(self):
        """Test that daemon stop command is registered."""
        result = runner.invoke(app, ["daemon", "stop", "--help"])
        assert result.exit_code == 0

    def test_daemon_status_exists(self):
        """Test that daemon status command is registered."""
        result = runner.invoke(app, ["daemon", "status", "--help"])
        assert result.exit_code == 0

    def test_config_commands_exist(self):
        """Test that config subcommands are registered."""
        result = runner.invoke(app, ["config", "--help"])
        assert result.exit_code == 0
        assert "export" in result.stdout.lower()
        assert "validate" in result.stdout.lower()

    def test_cluster_commands_exist(self):
        """Test that cluster subcommands are registered."""
        result = runner.invoke(app, ["cluster", "--help"])
        assert result.exit_code == 0
        assert "status" in result.stdout.lower()
        assert "events" in result.stdout.lower()
        assert "pods" in result.stdout.lower()

    def test_ssh_commands_exist(self):
        """Test that ssh subcommands are registered."""
        result = runner.invoke(app, ["ssh", "--help"])
        assert result.exit_code == 0

    def test_verbose_flag(self):
        """Test that --verbose flag is accepted."""
        result = runner.invoke(app, ["-v", "--help"])
        assert result.exit_code == 0

    def test_quiet_flag(self):
        """Test that --quiet flag is accepted."""
        result = runner.invoke(app, ["-q", "--help"])
        assert result.exit_code == 0

    def test_config_flag(self):
        """Test that --config flag is accepted."""
        result = runner.invoke(app, ["--config", "/tmp/test.yaml", "--help"])
        assert result.exit_code == 0

    def test_log_level_flag(self):
        """Test that --log-level flag is accepted."""
        result = runner.invoke(app, ["--log-level", "DEBUG", "--help"])
        assert result.exit_code == 0

    def test_no_color_flag(self):
        """Test that --no-color flag is accepted."""
        result = runner.invoke(app, ["--no-color", "--help"])
        assert result.exit_code == 0

    def test_output_format_flag(self):
        """Test that --output flag is accepted."""
        result = runner.invoke(app, ["--output", "json", "--help"])
        assert result.exit_code == 0
