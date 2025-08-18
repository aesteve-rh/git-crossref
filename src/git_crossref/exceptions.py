"""Custom exceptions for git-crossref."""


class GitSyncError(Exception):
    """Base exception for all git-crossref errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(GitSyncError):
    """Raised when there's an issue with configuration."""


class ConfigurationNotFoundError(ConfigurationError):
    """Raised when configuration file is not found."""

    def __init__(self, config_path: str):
        super().__init__(f"Configuration file not found: {config_path}")
        self.config_path = config_path


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration file is invalid."""

    def __init__(self, message: str, config_path: str | None = None):
        super().__init__(message)
        self.config_path = config_path


class GitRepositoryError(GitSyncError):
    """Base class for Git repository related errors."""

    def __init__(self, message: str, repository_url: str | None = None):
        super().__init__(message)
        self.repository_url = repository_url


class GitCloneError(GitRepositoryError):
    """Raised when repository cloning fails."""

    def __init__(self, repository_url: str, reason: str):
        message = f"Failed to clone repository '{repository_url}': {reason}"
        super().__init__(message, repository_url)
        self.reason = reason


class GitFetchError(GitRepositoryError):
    """Raised when repository fetching fails."""

    def __init__(self, repository_url: str, reason: str):
        message = f"Failed to fetch repository '{repository_url}': {reason}"
        super().__init__(message, repository_url)
        self.reason = reason


class GitObjectNotFoundError(GitRepositoryError):
    """Raised when a git object (blob, tree, commit) is not found."""

    def __init__(self, object_path: str, commit_hash: str, repository_url: str | None = None):
        message = f"Git object '{object_path}' not found at commit '{commit_hash}'"
        super().__init__(message, repository_url)
        self.object_path = object_path
        self.commit_hash = commit_hash


class InvalidCommitError(GitRepositoryError):
    """Raised when a commit hash or reference is invalid."""

    def __init__(self, commit_ref: str, repository_url: str | None = None):
        message = f"Invalid commit reference: '{commit_ref}'"
        super().__init__(message, repository_url)
        self.commit_ref = commit_ref


class SyncError(GitSyncError):
    """Base class for synchronization errors."""

    def __init__(self, message: str, source_path: str | None = None, dest_path: str | None = None):
        super().__init__(message)
        self.source_path = source_path
        self.dest_path = dest_path


class GitSyncFileNotFoundError(SyncError):
    """Raised when a source file is not found in the remote repository."""

    def __init__(self, source_path: str, commit_hash: str):
        message = f"File '{source_path}' not found at commit '{commit_hash}'"
        super().__init__(message, source_path)
        self.commit_hash = commit_hash


class LocalChangesError(SyncError):
    """Raised when local changes would be overwritten."""

    def __init__(self, dest_path: str):
        message = f"Local file '{dest_path}' has uncommitted changes"
        super().__init__(message, dest_path=dest_path)


class TransformationError(SyncError):
    """Raised when content transformation fails."""

    def __init__(self, file_path: str, reason: str):
        message = f"Transformation failed for '{file_path}': {reason}"
        super().__init__(message, dest_path=file_path)
        self.reason = reason


class DirectoryPreparationError(SyncError):
    """Raised when destination directory cannot be prepared."""

    def __init__(self, file_path: str, reason: str):
        message = f"Cannot prepare directory for '{file_path}': {reason}"
        super().__init__(message, dest_path=file_path)
        self.reason = reason


class GitFileNotFoundError(SyncError):
    """Raised when a file or pattern is not found in the repository."""

    def __init__(self, source_path: str, commit_hash: str, is_pattern: bool = False):
        if is_pattern:
            message = f"No files match pattern '{source_path}' in commit {commit_hash}"
        else:
            message = f"File '{source_path}' not found in commit {commit_hash}"
        super().__init__(message, dest_path=source_path)
        self.source_path = source_path
        self.commit_hash = commit_hash
        self.is_pattern = is_pattern


class OperationError(SyncError):
    """Raised when a sync or check operation fails."""

    def __init__(
        self, operation_name: str, source_path: str, reason: str, is_pattern: bool = False
    ):
        error_type = "pattern" if is_pattern else "file"
        message = f"Failed to {operation_name} {error_type} '{source_path}': {reason}"
        super().__init__(message, dest_path=source_path)
        self.operation_name = operation_name
        self.source_path = source_path
        self.is_pattern = is_pattern


class DirectoryNotFoundError(SyncError):
    """Raised when a source directory is not found in the remote repository."""

    def __init__(self, source_path: str, commit_hash: str):
        message = f"Directory '{source_path}' not found at commit '{commit_hash}'"
        super().__init__(message, source_path)
        self.commit_hash = commit_hash


class FileSystemError(GitSyncError):
    """Raised when there's a file system operation error."""

    def __init__(self, message: str, file_path: str | None = None):
        super().__init__(message)
        self.file_path = file_path


class GitSyncPermissionError(FileSystemError):
    """Raised when there's a permission error during file operations."""

    def __init__(self, file_path: str, operation: str):
        message = f"Permission denied for {operation} on '{file_path}'"
        super().__init__(message, file_path)
        self.operation = operation


class DiskSpaceError(FileSystemError):
    """Raised when there's insufficient disk space."""

    def __init__(self, required_space: int | None = None):
        message = "Insufficient disk space"
        if required_space:
            message += f" (required: {required_space} bytes)"
        super().__init__(message)
        self.required_space = required_space


class ValidationError(GitSyncError):
    """Raised when validation fails."""

    def __init__(self, message: str, field: str | None = None, value: str | None = None):
        super().__init__(message)
        self.field = field
        self.value = value


class RemoteNotFoundError(ConfigurationError):
    """Raised when a specified remote is not found in configuration."""

    def __init__(self, remote_name: str):
        message = f"Remote '{remote_name}' not found in configuration"
        super().__init__(message)
        self.remote_name = remote_name


class CacheError(GitSyncError):
    """Raised when there's an issue with the cache directory."""

    def __init__(self, message: str, cache_path: str | None = None):
        super().__init__(message)
        self.cache_path = cache_path


class NetworkError(GitSyncError):
    """Raised when there's a network-related error."""

    def __init__(self, message: str, url: str | None = None):
        super().__init__(message)
        self.url = url


class AuthenticationError(NetworkError):
    """Raised when authentication fails for a remote repository."""

    def __init__(self, repository_url: str):
        message = f"Authentication failed for repository: {repository_url}"
        super().__init__(message, repository_url)


class GitSyncConnectionError(NetworkError):
    """Raised when connection to remote repository fails."""

    def __init__(self, repository_url: str, reason: str | None = None):
        message = f"Connection failed for repository: {repository_url}"
        if reason:
            message += f" ({reason})"
        super().__init__(message, repository_url)
        self.reason = reason
