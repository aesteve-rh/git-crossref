import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .exceptions import ConfigurationNotFoundError, InvalidConfigurationError
from .schema import validate_config_file


@dataclass
class Remote:
    """Configuration for a remote repository."""

    url: str
    base_path: str = ""
    version: str = "main"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Remote":
        """Create Remote from dictionary."""
        return cls(
            url=data["url"],
            base_path=data.get("base_path", ""),
            version=data.get("version", "main"),
        )


@dataclass
class FileSync:
    """Configuration for Git objects to sync from a remote (files, directories, or glob patterns).

    source can be:
    - Single file: "utils.py"
    - Directory: "src/" (must end with /)
    - Glob pattern: "util/*.py", "scripts/build*"
    """

    source: str
    destination: str
    hash: str | None = None
    ignore_changes: bool = False
    include_subdirs: bool = False
    transform: list[str] | None = None  # List of sed-like patterns: "s/old/new/g"
    exclude: list[str] | None = None  # List of glob patterns to exclude from matching

    @property
    def is_tree_sync(self) -> bool:
        """Check if this is a tree (directory) sync."""
        return self.source.endswith("/")

    @property
    def is_glob_sync(self) -> bool:
        """Check if this is a glob pattern sync."""
        return not self.is_tree_sync and ("*" in self.source or "?" in self.source)

    @property
    def is_blob_sync(self) -> bool:
        """Check if this is a single blob (file) sync."""
        return not self.is_tree_sync and not self.is_glob_sync

    @property
    def sync_type(self) -> str:
        """Get the sync type."""
        if self.is_tree_sync:
            return "directory"
        elif self.is_glob_sync:
            return "glob pattern"
        else:
            return "file"

    @property
    def git_object_type(self) -> str:
        """Get the Git object type being synced."""
        return "tree" if self.is_tree_sync else "blob"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileSync":
        """Create FileSync from dictionary."""
        return cls(
            source=data["source"],
            destination=data["destination"],
            hash=data.get("hash", data.get("version")),
            ignore_changes=data.get("ignore_changes", False),
            include_subdirs=data.get("include_subdirs", False),
            transform=data.get("transform"),
            exclude=data.get("exclude"),
        )


@dataclass
class GitSyncConfig:
    """Main configuration for git-crossref."""

    remotes: dict[str, Remote]
    files: dict[str, list[FileSync]]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GitSyncConfig":
        """Create GitSyncConfig from dictionary loaded from YAML."""
        remotes = {}
        for name, remote_data in data.get("remotes", {}).items():
            remotes[name] = Remote(
                url=remote_data["url"],
                base_path=remote_data.get("base_path", ""),
                version=remote_data.get("version", "main"),
            )

        files: dict[str, list[FileSync]] = {}
        for remote_name, file_list in data.get("files", {}).items():
            files[remote_name] = []
            for file_data in file_list:
                files[remote_name].append(FileSync.from_dict(file_data))

        return cls(remotes=remotes, files=files)


def get_git_root() -> Path:
    """Get the root directory of the current git repository."""
    try:
        result = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
        )
        return Path(result.rstrip().decode("utf8"))
    except subprocess.CalledProcessError as exc:
        raise InvalidConfigurationError("Not in a git repository") from exc


def load_config() -> GitSyncConfig:
    """Load and validate the git-sync configuration from repository root."""
    config_path = get_config_path()

    if not config_path.exists():
        raise ConfigurationNotFoundError(str(config_path))

    validate_config_file(str(config_path))
    # Then load using the existing method for backward compatibility
    with open(config_path, encoding="utf8") as stream:
        try:
            data = yaml.safe_load(stream)
            return GitSyncConfig.from_dict(data)
        except yaml.YAMLError as exc:
            raise InvalidConfigurationError(
                f"Invalid YAML in configuration file: {exc}", str(config_path)
            ) from exc


# Global config instance (loaded lazily)
_config: GitSyncConfig | None = None


def get_config() -> GitSyncConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_config_path() -> Path:
    """Get the path to the configuration file."""
    git_root = get_git_root()
    return git_root / ".gitcrossref"


def apply_transformations(content: str, transforms: list[str] | None) -> str:
    """Apply sed-like transformations to file content.

    Args:
        content: The original file content
        transforms: List of sed patterns like "s/old/new/g"

    Returns:
        The transformed content

    Raises:
        ValueError: If a transformation pattern is invalid
    """
    if not transforms:
        return content

    result = content
    for pattern in transforms:
        try:
            # Parse sed pattern: s/search/replace/flags
            if not pattern.startswith("s/"):
                raise ValueError(f"Invalid sed pattern: {pattern} (must start with 's/')")

            # Split pattern into parts
            parts = pattern[2:].split("/")
            if len(parts) < 2:
                raise ValueError(f"Invalid sed pattern: {pattern} (missing search/replace parts)")

            search = parts[0]
            replace = parts[1] if len(parts) > 1 else ""
            flags_str = parts[2] if len(parts) > 2 else ""

            # Convert sed flags to Python re flags
            flags = 0
            if "i" in flags_str:
                flags |= re.IGNORECASE
            if "m" in flags_str:
                flags |= re.MULTILINE
            if "x" in flags_str:
                flags |= re.VERBOSE

            # Apply transformation
            if "g" in flags_str:
                # Global replace (default in Python)
                result = re.sub(search, replace, result, flags=flags)
            else:
                # Replace only first occurrence
                result = re.sub(search, replace, result, count=1, flags=flags)

        except Exception as e:
            raise ValueError(f"Failed to apply transformation '{pattern}': {e}") from e

    return result


def get_transformed_content_hash(original_content: bytes, transforms: list[str] | None) -> str:
    """Calculate the hash of content after applying transformations.

    Args:
        original_content: The original file content as bytes
        transforms: List of sed patterns to apply

    Returns:
        The Git blob hash of the transformed content

    Raises:
        ValueError: If a transformation pattern is invalid
        UnicodeDecodeError: If content cannot be decoded as text for transformations
    """
    if not transforms:
        # No transformations, return hash of original content
        # Git blob hash format: "blob {size}\0{content}"
        blob_data = f"blob {len(original_content)}\0".encode() + original_content
        return hashlib.sha1(blob_data).hexdigest()

    # Apply transformations
    text_content = original_content.decode("utf-8")
    transformed_content = apply_transformations(text_content, transforms)
    transformed_bytes = transformed_content.encode("utf-8")

    # Calculate Git blob hash of transformed content
    blob_data = f"blob {len(transformed_bytes)}\0".encode() + transformed_bytes
    return hashlib.sha1(blob_data).hexdigest()
