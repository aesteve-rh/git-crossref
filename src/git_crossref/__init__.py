"""Git-sync-files: A Git plugin for syncing specific files from multiple repositories."""

__version__ = "0.1.2"

# Export main exception classes for easy access
from .exceptions import (
    AuthenticationError,
    ConfigurationError,
    ConfigurationNotFoundError,
    GitCloneError,
    GitSyncConnectionError,
    GitSyncError,
    GitSyncFileNotFoundError,
    GitSyncPermissionError,
    InvalidConfigurationError,
    LocalChangesError,
    RemoteNotFoundError,
    SyncError,
)
from .status import SyncStatus

__all__ = [
    "AuthenticationError",
    "ConfigurationError",
    "ConfigurationNotFoundError",
    "GitSyncConnectionError",
    "GitSyncFileNotFoundError",
    "GitCloneError",
    "GitSyncError",
    "GitSyncPermissionError",
    "InvalidConfigurationError",
    "LocalChangesError",
    "RemoteNotFoundError",
    "SyncError",
    "SyncStatus",
]
