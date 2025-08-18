"""Tests for the exceptions module."""

from git_crossref.exceptions import (
    AuthenticationError,
    ConfigurationError,
    ConfigurationNotFoundError,
    GitSyncConnectionError,
    GitFileNotFoundError,
    GitCloneError,
    GitSyncError,
    InvalidConfigurationError,
    LocalChangesError,
    RemoteNotFoundError,
    SyncError,
    ValidationError,
)


class TestGitSyncError:
    """Test the base GitSyncError class."""

    def test_git_sync_error_basic(self):
        """Test basic GitSyncError creation."""
        error = GitSyncError("Test error")
        assert str(error) == "Test error"
        assert error.details == {}

    def test_git_sync_error_with_details(self):
        """Test GitSyncError with details."""
        details = {"file": "test.py", "line": 42}
        error = GitSyncError("Test error", details)
        assert str(error) == "Test error"
        assert error.details == details


class TestConfigurationErrors:
    """Test configuration-related exceptions."""

    def test_configuration_error(self):
        """Test ConfigurationError."""
        error = ConfigurationError("Config error")
        assert str(error) == "Config error"
        assert isinstance(error, GitSyncError)

    def test_configuration_not_found_error(self):
        """Test ConfigurationNotFoundError."""
        config_path = "/path/to/config"
        error = ConfigurationNotFoundError(config_path)
        assert config_path in str(error)
        assert error.config_path == config_path
        assert isinstance(error, ConfigurationError)

    def test_invalid_configuration_error(self):
        """Test InvalidConfigurationError."""
        message = "Invalid config"
        config_path = "/path/to/config"
        error = InvalidConfigurationError(message, config_path)
        assert str(error) == message
        assert error.config_path == config_path
        assert isinstance(error, ConfigurationError)

    def test_invalid_configuration_error_no_path(self):
        """Test InvalidConfigurationError without path."""
        message = "Invalid config"
        error = InvalidConfigurationError(message)
        assert str(error) == message
        assert error.config_path is None

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError("Schema validation failed")
        assert str(error) == "Schema validation failed"
        assert isinstance(error, GitSyncError)


class TestGitErrors:
    """Test Git-related exceptions."""

    def test_git_clone_error(self):
        """Test GitCloneError."""
        repo_url = "https://github.com/example/repo.git"
        reason = "Repository not found"
        error = GitCloneError(repo_url, reason)
        assert repo_url in str(error)
        assert reason in str(error)
        assert error.repository_url == repo_url
        assert error.reason == reason

    def test_authentication_error(self):
        """Test AuthenticationError."""
        repo_url = "https://github.com/example/repo.git"
        error = AuthenticationError(repo_url)
        assert repo_url in str(error)
        assert "authentication" in str(error).lower()
        assert error.url == repo_url

    def test_connection_error(self):
        """Test GitSyncConnectionError."""
        repo_url = "https://github.com/example/repo.git"
        reason = "Network timeout"
        error = GitSyncConnectionError(repo_url, reason)
        assert repo_url in str(error)
        assert reason in str(error)
        assert error.url == repo_url
        assert error.reason == reason

    def test_remote_not_found_error(self):
        """Test RemoteNotFoundError."""
        remote_name = "upstream"
        error = RemoteNotFoundError(remote_name)
        assert remote_name in str(error)
        assert error.remote_name == remote_name


class TestSyncErrors:
    """Test sync-related exceptions."""

    def test_sync_error(self):
        """Test SyncError."""
        error = SyncError("Sync failed")
        assert str(error) == "Sync failed"
        assert isinstance(error, GitSyncError)

    def test_file_not_found_error(self):
        """Test GitFileNotFoundError."""
        file_path = "src/utils.py"
        commit_hash = "abc123"
        error = GitFileNotFoundError(file_path, commit_hash)
        assert file_path in str(error)
        assert error.source_path == file_path
        assert error.commit_hash == commit_hash
        assert isinstance(error, SyncError)

    def test_local_changes_error(self):
        """Test LocalChangesError."""
        file_path = "src/utils.py"
        error = LocalChangesError(file_path)
        assert file_path in str(error)
        assert "uncommitted changes" in str(error).lower()
        assert error.dest_path == file_path
        assert isinstance(error, SyncError)


class TestErrorInheritance:
    """Test the exception inheritance hierarchy."""

    def test_all_errors_inherit_from_git_sync_error(self):
        """Test that all custom errors inherit from GitSyncError."""
        error_classes = [
            ConfigurationError,
            ConfigurationNotFoundError,
            InvalidConfigurationError,
            ValidationError,
            GitCloneError,
            AuthenticationError,
            GitSyncConnectionError,
            RemoteNotFoundError,
            SyncError,
            GitFileNotFoundError,
            LocalChangesError,
        ]

        for error_class in error_classes:
            # Create instance with minimal required args
            if error_class == ConfigurationNotFoundError:
                error = error_class("/path/to/config")
            elif error_class == InvalidConfigurationError:
                error = error_class("Invalid config")
            elif error_class == GitCloneError:
                error = error_class("https://example.com/repo.git", "reason")
            elif error_class == AuthenticationError:
                error = error_class("https://example.com/repo.git")
            elif error_class == GitSyncConnectionError:
                error = error_class("https://example.com/repo.git", "details")
            elif error_class == RemoteNotFoundError:
                error = error_class("remote")
            elif error_class == GitFileNotFoundError:
                error = error_class("file.py", "abc123")
            elif error_class == LocalChangesError:
                error = error_class("file.py")
            else:
                error = error_class("Test error")

            assert isinstance(error, GitSyncError)
            assert isinstance(error, Exception)
