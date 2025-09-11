"""Tests for the main CLI module."""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from git_crossref.main import cli


class TestCLI:
    """Test the main CLI interface."""

    @pytest.fixture
    def runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_cli_help(self, runner):
        """Test CLI help output."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert ".gitcrossref" in result.output
        assert "sync" in result.output
        assert "init" in result.output
        assert "check" in result.output

    def test_cli_version(self, runner):
        """Test CLI version output."""
        with patch("git_crossref.main.__version__", "1.0.0"):
            result = runner.invoke(cli, ["--version"])
            assert result.exit_code == 0
            assert "1.0.0" in result.output

    def test_cli_verbose_flag(self, runner):
        """Test CLI verbose flag."""
        with patch("git_crossref.main.configure_logging") as mock_configure:
            result = runner.invoke(cli, ["--verbose", "validate"])
            assert result.exit_code == 0
            mock_configure.assert_called_with(verbose=True)


class TestSyncCommand:
    """Test the sync command."""

    @pytest.fixture
    def runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_sync_help(self, runner):
        """Test sync command help."""
        result = runner.invoke(cli, ["sync", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output
        assert "--remote" in result.output
        assert "--dry-run" in result.output

    @patch("git_crossref.main.get_config")
    @patch("git_crossref.main.GitSyncOrchestrator")
    def test_sync_success(self, mock_orchestrator, mock_get_config, runner, sample_config):
        """Test successful sync operation."""
        mock_get_config.return_value = sample_config
        mock_instance = Mock()
        mock_instance.sync_all.return_value = []
        mock_orchestrator.return_value = mock_instance

        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        mock_instance.sync_all.assert_called_once_with(force=False, remote_filter=None)

    @patch("git_crossref.main.get_config")
    @patch("git_crossref.main.GitSyncOrchestrator")
    def test_sync_with_force(self, mock_orchestrator, mock_get_config, runner, sample_config):
        """Test sync with force flag."""
        mock_get_config.return_value = sample_config
        mock_instance = Mock()
        mock_instance.sync_all.return_value = []
        mock_orchestrator.return_value = mock_instance

        result = runner.invoke(cli, ["sync", "--force"])
        assert result.exit_code == 0
        mock_instance.sync_all.assert_called_once_with(force=True, remote_filter=None)

    @patch("git_crossref.main.get_config")
    @patch("git_crossref.main.GitSyncOrchestrator")
    def test_sync_with_remote_filter(
        self, mock_orchestrator, mock_get_config, runner, sample_config
    ):
        """Test sync with remote filter."""
        mock_get_config.return_value = sample_config
        mock_instance = Mock()
        mock_instance.sync_all.return_value = []
        mock_orchestrator.return_value = mock_instance

        result = runner.invoke(cli, ["sync", "--remote", "upstream"])
        assert result.exit_code == 0
        mock_instance.sync_all.assert_called_once_with(force=False, remote_filter="upstream")

    @patch("git_crossref.main.get_config")
    @patch("git_crossref.main.GitSyncOrchestrator")
    def test_sync_dry_run(self, mock_orchestrator, mock_get_config, runner, sample_config):
        """Test sync with dry-run flag."""
        mock_get_config.return_value = sample_config
        mock_instance = Mock()
        mock_instance.check_all.return_value = []
        mock_orchestrator.return_value = mock_instance

        result = runner.invoke(cli, ["sync", "--dry-run"])
        assert result.exit_code == 0
        mock_instance.check_all.assert_called_once_with(remote_filter=None)

    @patch("git_crossref.main.get_config")
    @patch("git_crossref.main.GitSyncOrchestrator")
    def test_sync_with_files(self, mock_orchestrator, mock_get_config, runner, sample_config):
        """Test sync with specific files."""
        mock_get_config.return_value = sample_config
        mock_instance = Mock()
        mock_instance.sync_files.return_value = []
        mock_orchestrator.return_value = mock_instance

        result = runner.invoke(cli, ["sync", "file1.py", "file2.py"])
        assert result.exit_code == 0
        mock_instance.sync_files.assert_called_once_with(["file1.py", "file2.py"], force=False)

    def test_sync_config_not_found(self, runner):
        """Test sync when config file not found."""
        from git_crossref.exceptions import ConfigurationNotFoundError

        with patch("git_crossref.main.get_config") as mock_get_config:
            mock_get_config.side_effect = ConfigurationNotFoundError("/path/to/config")
            result = runner.invoke(cli, ["sync"])
            assert result.exit_code == 1
            assert "Run 'git-crossref init' to create a configuration file." in result.output


class TestCheckCommand:
    """Test the check command."""

    @pytest.fixture
    def runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_check_help(self, runner):
        """Test check command help."""
        result = runner.invoke(cli, ["check", "--help"])
        assert result.exit_code == 0
        assert "--remote" in result.output

    @patch("git_crossref.main.get_config")
    @patch("git_crossref.main.GitSyncOrchestrator")
    def test_check_success(self, mock_orchestrator, mock_get_config, runner, sample_config):
        """Test successful check operation."""
        mock_get_config.return_value = sample_config
        mock_instance = Mock()
        mock_instance.check_all.return_value = []
        mock_orchestrator.return_value = mock_instance

        result = runner.invoke(cli, ["check"])
        assert result.exit_code == 0
        mock_instance.check_all.assert_called_once_with(remote_filter=None)


class TestInitCommand:
    """Test the init command."""

    @pytest.fixture
    def runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_init_help(self, runner):
        """Test init command help."""
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0
        assert "--clone" in result.output

    @patch("git_crossref.main.get_config_path")
    def test_init_success(self, mock_get_config_path, runner, temp_dir):
        """Test successful init operation."""
        config_path = temp_dir / ".gitcrossref"
        mock_get_config_path.return_value = config_path

        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0
        assert config_path.exists()
        assert "Edit this file to configure your remotes and files." in result.output

    @patch("git_crossref.main.get_config_path")
    def test_init_file_exists_no_overwrite(self, mock_get_config_path, runner, temp_dir):
        """Test init when file exists and user chooses not to overwrite."""
        config_path = temp_dir / ".gitcrossref"
        config_path.write_text("existing config")
        mock_get_config_path.return_value = config_path

        with patch("git_crossref.main.logger") as mock_logger:
            result = runner.invoke(cli, ["init"], input="n\n")
            assert result.exit_code == 0
            mock_logger.warning.assert_called_with("Configuration file already exists: %s", config_path)

    @patch("git_crossref.main.get_config_path")
    def test_init_file_exists_overwrite(self, mock_get_config_path, runner, temp_dir):
        """Test init when file exists - should just warn and exit."""
        config_path = temp_dir / ".gitcrossref"
        config_path.write_text("existing config")
        mock_get_config_path.return_value = config_path

        with patch("git_crossref.main.logger") as mock_logger:
            result = runner.invoke(cli, ["init"], input="y\n")
            assert result.exit_code == 0
            mock_logger.warning.assert_called_with("Configuration file already exists: %s", config_path)
            # When file exists, no output to stdout, just warning to stderr
            assert result.output == ""

    @patch("git_crossref.main.get_config_path")
    @patch("git_crossref.main.get_config")
    @patch("git_crossref.main.GitSyncOrchestrator")
    def test_init_with_clone(
        self,
        mock_orchestrator,
        mock_get_config,
        mock_get_config_path,
        runner,
        temp_dir,
        sample_config,
    ):
        """Test init with clone flag."""
        config_path = temp_dir / ".gitcrossref"
        mock_get_config_path.return_value = config_path
        mock_get_config.return_value = sample_config

        mock_instance = Mock()
        mock_repo = Mock()
        mock_instance.git_manager.get_repository.return_value = mock_repo
        mock_orchestrator.return_value = mock_instance

        result = runner.invoke(cli, ["init", "--clone"])
        assert result.exit_code == 0
        assert "Edit this file to configure your remotes and files." in result.output


class TestCloneCommand:
    """Test the clone command."""

    @pytest.fixture
    def runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_clone_help(self, runner):
        """Test clone command help."""
        result = runner.invoke(cli, ["clone", "--help"])
        assert result.exit_code == 0
        assert "--remote" in result.output

    @patch("git_crossref.main.get_config")
    @patch("git_crossref.main.GitSyncOrchestrator")
    def test_clone_all(self, mock_orchestrator, mock_get_config, runner, sample_config):
        """Test cloning all remotes."""
        mock_get_config.return_value = sample_config
        mock_instance = Mock()
        mock_repo = Mock()
        mock_instance.git_manager.get_repository.return_value = mock_repo
        mock_orchestrator.return_value = mock_instance

        with patch("git_crossref.main.logger") as mock_logger:
            result = runner.invoke(cli, ["clone"])
            assert result.exit_code == 0
            mock_logger.info.assert_any_call("Cloning all remote repositories...")
            mock_logger.info.assert_any_call("All remote repositories cloned successfully")

    @patch("git_crossref.main.get_config")
    @patch("git_crossref.main.GitSyncOrchestrator")
    def test_clone_specific_remote(self, mock_orchestrator, mock_get_config, runner, sample_config):
        """Test cloning specific remote."""
        mock_get_config.return_value = sample_config
        mock_instance = Mock()
        mock_repo = Mock()
        mock_instance.git_manager.get_repository.return_value = mock_repo
        mock_orchestrator.return_value = mock_instance

        with patch("git_crossref.main.logger") as mock_logger:
            result = runner.invoke(cli, ["clone", "--remote", "upstream"])
            assert result.exit_code == 0
            mock_logger.info.assert_any_call("Cloning remote repository: %s", "upstream")
            mock_logger.info.assert_any_call("Successfully cloned %s", "upstream")

    def test_clone_remote_not_found(self, runner, sample_config):
        """Test cloning non-existent remote."""
        with patch("git_crossref.main.get_config") as mock_get_config:
            mock_get_config.return_value = sample_config
            with patch("git_crossref.main.logger") as mock_logger:
                result = runner.invoke(cli, ["clone", "--remote", "nonexistent"])
                assert result.exit_code == 1
                mock_logger.error.assert_called_with("Remote '%s' not found in configuration", "nonexistent")


class TestCleanCommand:
    """Test the clean command."""

    @pytest.fixture
    def runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_clean_help(self, runner):
        """Test clean command help."""
        result = runner.invoke(cli, ["clean", "--help"])
        assert result.exit_code == 0

    @patch("git_crossref.main.get_config")
    @patch("git_crossref.main.GitSyncOrchestrator")
    def test_clean_success(self, mock_orchestrator, mock_get_config, runner, sample_config):
        """Test successful clean operation."""
        mock_get_config.return_value = sample_config
        mock_instance = Mock()
        mock_orchestrator.return_value = mock_instance

        result = runner.invoke(cli, ["clean"])
        assert result.exit_code == 0
        mock_instance.cleanup.assert_called_once()


class TestValidateCommand:
    """Test the validate command."""

    @pytest.fixture
    def runner(self):
        """Create a Click CLI runner."""
        return CliRunner()

    def test_validate_help(self, runner):
        """Test validate command help."""
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0

    @patch("git_crossref.main.get_config_path")
    @patch("git_crossref.main.validate_config_file")
    @patch("git_crossref.main.get_config")
    def test_validate_success(
        self, mock_get_config, mock_validate, mock_get_config_path, runner, sample_config, temp_dir
    ):
        """Test successful validation."""
        config_path = temp_dir / ".gitcrossref"
        mock_get_config_path.return_value = config_path
        mock_validate.return_value = {}
        mock_get_config.return_value = sample_config

        with patch("git_crossref.main.logger") as mock_logger:
            result = runner.invoke(cli, ["validate"])
            assert result.exit_code == 0
            mock_logger.info.assert_any_call("Configuration file is valid")
            mock_logger.info.assert_any_call("Schema validation passed for %s", temp_dir / ".gitcrossref")

    def test_validate_config_not_found(self, runner):
        """Test validation when config not found."""
        from git_crossref.exceptions import ConfigurationNotFoundError

        with patch("git_crossref.main.get_config_path") as mock_get_path:
            mock_get_path.return_value = "/nonexistent/config"
            with patch("git_crossref.main.validate_config_file") as mock_validate:
                mock_validate.side_effect = ConfigurationNotFoundError("/nonexistent/config")
                result = runner.invoke(cli, ["validate"])
                assert result.exit_code == 1
                assert "Run 'git-crossref init' to create a configuration file." in result.output
