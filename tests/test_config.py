"""Tests for the config module."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from git_crossref.config import (
    FileSync,
    GitSyncConfig,
    Remote,
    get_config_path,
    get_git_root,
    load_config,
)
from git_crossref.exceptions import (
    ConfigurationNotFoundError,
    InvalidConfigurationError,
)


class TestRemote:
    """Test the Remote dataclass."""

    def test_remote_defaults(self):
        """Test Remote with default values."""
        remote = Remote(url="https://github.com/example/repo.git")
        assert remote.url == "https://github.com/example/repo.git"
        assert remote.base_path == ""
        assert remote.version == "main"

    def test_remote_custom_values(self):
        """Test Remote with custom values."""
        remote = Remote(
            url="https://github.com/example/repo.git", base_path="src/lib", version="v1.0.0"
        )
        assert remote.url == "https://github.com/example/repo.git"
        assert remote.base_path == "src/lib"
        assert remote.version == "v1.0.0"

    def test_remote_from_dict(self):
        """Test Remote.from_dict method."""
        data = {
            "url": "https://github.com/example/repo.git",
            "base_path": "src",
            "version": "develop",
        }
        remote = Remote.from_dict(data)
        assert remote.url == "https://github.com/example/repo.git"
        assert remote.base_path == "src"
        assert remote.version == "develop"

    def test_remote_from_dict_minimal(self):
        """Test Remote.from_dict with minimal data."""
        data = {"url": "https://github.com/example/repo.git"}
        remote = Remote.from_dict(data)
        assert remote.url == "https://github.com/example/repo.git"
        assert remote.base_path == ""
        assert remote.version == "main"


class TestFileSync:
    """Test the FileSync dataclass."""

    def test_file_sync_defaults(self):
        """Test FileSync with default values."""
        file_sync = FileSync(source="file.py", destination="dest/file.py")
        assert file_sync.source == "file.py"
        assert file_sync.destination == "dest/file.py"
        assert file_sync.hash is None
        assert file_sync.ignore_changes is False

    def test_file_sync_custom_values(self):
        """Test FileSync with custom values."""
        file_sync = FileSync(
            source="dir/", destination="target/", hash="abc123", ignore_changes=True
        )
        assert file_sync.source == "dir/"
        assert file_sync.destination == "target/"
        assert file_sync.hash == "abc123"
        assert file_sync.ignore_changes is True

    def test_is_tree_sync(self):
        """Test is_tree_sync property."""
        file_sync = FileSync(source="file.py", destination="dest/file.py")
        assert file_sync.is_tree_sync is False

        tree_sync = FileSync(source="dir/", destination="dest/")
        assert tree_sync.is_tree_sync is True

    def test_sync_type(self):
        """Test sync_type property."""
        file_sync = FileSync(source="file.py", destination="dest/file.py")
        assert file_sync.sync_type == "file"

        tree_sync = FileSync(source="dir/", destination="dest/")
        assert tree_sync.sync_type == "directory"

        glob_sync = FileSync(source="*.py", destination="dest/")
        assert glob_sync.sync_type == "glob pattern"

    def test_file_sync_from_dict(self):
        """Test FileSync.from_dict method."""
        data = {
            "source": "src/file.py",
            "destination": "lib/file.py",
            "hash": "def456",
            "ignore_changes": True,
        }
        file_sync = FileSync.from_dict(data)
        assert file_sync.source == "src/file.py"
        assert file_sync.destination == "lib/file.py"
        assert file_sync.hash == "def456"
        assert file_sync.ignore_changes is True

    def test_file_sync_from_dict_minimal(self):
        """Test FileSync.from_dict with minimal data."""
        data = {"source": "file.py", "destination": "dest/file.py"}
        file_sync = FileSync.from_dict(data)
        assert file_sync.source == "file.py"
        assert file_sync.destination == "dest/file.py"
        assert file_sync.hash is None
        assert file_sync.ignore_changes is False


class TestGitSyncConfig:
    """Test the GitSyncConfig dataclass."""

    def test_git_sync_config(self, sample_config):
        """Test GitSyncConfig creation."""
        assert len(sample_config.remotes) == 2
        assert "upstream" in sample_config.remotes
        assert "fork" in sample_config.remotes
        assert len(sample_config.files) == 2

    def test_git_sync_config_from_dict(self):
        """Test GitSyncConfig.from_dict method."""
        data = {
            "remotes": {
                "origin": {"url": "https://github.com/example/repo.git", "version": "main"}
            },
            "files": {"origin": [{"source": "file.py", "destination": "dest/file.py"}]},
        }
        config = GitSyncConfig.from_dict(data)
        assert len(config.remotes) == 1
        assert "origin" in config.remotes
        assert config.remotes["origin"].url == "https://github.com/example/repo.git"
        assert len(config.files["origin"]) == 1


class TestConfigFunctions:
    """Test configuration utility functions."""

    def test_get_git_root(self, mock_git_repo):
        """Test get_git_root function."""
        root = get_git_root()
        assert isinstance(root, Path)

    def test_get_git_root_not_in_repo(self):
        """Test get_git_root when not in a git repository."""
        with patch("subprocess.check_output") as mock_subprocess:
            mock_subprocess.side_effect = subprocess.CalledProcessError(128, "git")
            with pytest.raises(InvalidConfigurationError):
                get_git_root()

    def test_get_config_path(self, temp_dir):
        """Test get_config_path function."""
        with patch("git_crossref.config.get_git_root") as mock_get_git_root:
            mock_get_git_root.return_value = temp_dir
            config_path = get_config_path()
            assert config_path == temp_dir / ".gitcrossref"

    def test_load_config_success(self, sample_config_file):
        """Test successful config loading."""
        with patch("git_crossref.config.get_config_path") as mock_get_path:
            mock_get_path.return_value = sample_config_file
            with patch("git_crossref.config.validate_config_file") as mock_validate:
                mock_validate.return_value = {}
                config = load_config()
                assert isinstance(config, GitSyncConfig)
                assert len(config.remotes) == 2

    def test_load_config_not_found(self, temp_dir):
        """Test config loading when file doesn't exist."""
        non_existent = temp_dir / "nonexistent.yaml"
        with patch("git_crossref.config.get_config_path") as mock_get_path:
            mock_get_path.return_value = non_existent
            with pytest.raises(ConfigurationNotFoundError):
                load_config()

    def test_load_config_invalid_yaml(self, temp_dir):
        """Test config loading with invalid YAML."""
        invalid_config = temp_dir / ".gitcrossref"
        invalid_config.write_text("invalid: yaml: content: [")

        with patch("git_crossref.config.get_config_path") as mock_get_path:
            mock_get_path.return_value = invalid_config
            with patch("git_crossref.config.validate_config_file") as mock_validate:
                mock_validate.return_value = {}
                with pytest.raises(InvalidConfigurationError):
                    load_config()

    def test_load_config_validation_error(self, sample_config_file):
        """Test config loading with validation error."""
        with patch("git_crossref.config.get_config_path") as mock_get_path:
            mock_get_path.return_value = sample_config_file
            with patch("git_crossref.config.validate_config_file") as mock_validate:
                from git_crossref.exceptions import ValidationError

                mock_validate.side_effect = ValidationError("Invalid schema")
                with pytest.raises(ValidationError):
                    load_config()
