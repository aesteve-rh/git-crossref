"""Common test fixtures and utilities."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from git import Repo

from git_crossref.config import GitSyncConfig, Remote, FileSync


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_git_repo(temp_dir):
    """Create a mock git repository."""
    with patch("git_crossref.config.get_git_root") as mock_get_git_root:
        mock_get_git_root.return_value = temp_dir
        # Initialize a real git repo for testing
        repo = Repo.init(temp_dir)
        # Create initial commit
        (temp_dir / "README.md").write_text("# Test Repo")
        repo.index.add(["README.md"])
        repo.index.commit("Initial commit")
        yield repo


@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    return GitSyncConfig(
        remotes={
            "upstream": Remote(
                url="https://github.com/example/upstream.git", base_path="src", version="main"
            ),
            "fork": Remote(url="https://github.com/user/fork.git", version="develop"),
        },
        files={
            "upstream": [
                FileSync(source="utils.py", destination="lib/utils.py"),
                FileSync(source="config.yaml", destination="config/app.yaml", hash="abc123def456"),
            ],
            "fork": [FileSync(source="docs/", destination="documentation/")],
        },
    )


@pytest.fixture
def sample_config_file(temp_dir, sample_config):
    """Create a sample configuration file."""
    config_path = temp_dir / ".gitcrossref"

    config_data = {
        "remotes": {
            name: {
                key: value
                for key, value in {
                    "url": remote.url,
                    "base_path": remote.base_path,
                    "version": remote.version,
                }.items()
                if value  # Only include non-empty values
            }
            for name, remote in sample_config.remotes.items()
        },
        "files": {
            remote_name: [
                {
                    "source": fs.source,
                    "destination": fs.destination,
                    **({"hash": fs.hash} if fs.hash else {}),
                    **({"ignore_changes": fs.ignore_changes} if fs.ignore_changes else {}),
                }
                for fs in file_list
            ]
            for remote_name, file_list in sample_config.files.items()
        },
    }

    with open(config_path, "w") as f:
        yaml.dump(config_data, f)

    return config_path


@pytest.fixture
def mock_logger():
    """Mock the logger module."""
    with patch("git_crossref.logger") as mock:
        yield mock


@pytest.fixture
def mock_git_repository():
    """Mock GitRepository class."""
    with patch("git_crossref.git_ops.GitRepository") as mock:
        instance = Mock()
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_orchestrator():
    """Mock GitSyncOrchestrator."""
    with patch("git_crossref.sync.GitSyncOrchestrator") as mock:
        instance = Mock()
        mock.return_value = instance
        yield instance
