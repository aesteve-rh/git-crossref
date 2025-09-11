"""Base abstract class for Git object syncers."""

import fnmatch
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, NamedTuple

from git import Repo

from .config import Remote
from .exceptions import GitFileNotFoundError, OperationError
from .git_base import GitBase
from .logger import logger


class SyncSuccess(NamedTuple):
    """Result of a successful sync or check operation."""

    objects_processed: int
    message: str


class OperationMode(Enum):
    """Mode of operation for the template method."""

    SYNC = "sync"
    CHECK = "check"


@dataclass
class ProcessingStats:
    """Statistics from processing items."""

    synced_count: int = 0
    would_sync_count: int = 0
    up_to_date_count: int = 0
    failed_items: list[str] = field(default_factory=list)

    def total_files(self) -> int:
        """Get the total number of files processed."""
        return (
            self.synced_count
            + self.would_sync_count
            + self.up_to_date_count
            + len(self.failed_items)
        )

    def has_failures(self) -> bool:
        """Check if there were any failures."""
        return len(self.failed_items) > 0

    def generate_sync_result(self, source_path: str, is_glob_pattern: bool) -> SyncSuccess:
        """Generate a sync result from these statistics, raising exception if there were failures."""
        if self.failed_items:
            if is_glob_pattern:
                if self.synced_count > 0:
                    # Partial success - some files synced, some failed
                    reason = (
                        f"Synced {self.synced_count} files, failed: {', '.join(self.failed_items)}"
                    )
                else:
                    # Complete failure
                    reason = f"Failed: {', '.join(self.failed_items)}"
            else:
                # Single file error
                reason = self.failed_items[0]
            raise OperationError("sync", source_path, reason, is_glob_pattern)

        if is_glob_pattern:
            message = f"Successfully synced {self.synced_count} files matching pattern"
        else:
            message = "File synced successfully"

        return SyncSuccess(objects_processed=self.synced_count, message=message)

    def generate_check_result(self, is_glob_pattern: bool) -> SyncSuccess:
        """Generate a check result from these statistics, raising exception if there were failures."""
        total = self.total_files()

        if is_glob_pattern:
            if self.failed_items:
                reason = f"Would sync {self.would_sync_count}/{total} files, {len(self.failed_items)} have local changes: {', '.join(self.failed_items)}"
                raise OperationError("check", "pattern", reason, True)
            elif self.would_sync_count > 0:
                message = f"{self.would_sync_count}/{total} files matching pattern would be updated"
            else:
                message = (
                    f"All {self.up_to_date_count} files matching pattern are already up to date"
                )
        else:
            # Single file
            if self.failed_items:
                reason = f"Local file has uncommitted changes: {', '.join(self.failed_items)}"
                raise OperationError("check", "file", reason, False)
            elif self.would_sync_count > 0:
                message = "Would be updated (file differs from remote)"
            else:
                message = "File is already up to date"

        return SyncSuccess(objects_processed=total, message=message)


class BaseGitObjectSyncer(GitBase, ABC):
    """Abstract base class for syncing Git objects (blobs and trees)."""

    def __init__(self, repo: Repo, remote: Remote, git_root: Path):
        super().__init__()
        self.remote_repo = repo  # Use different name to avoid conflict with GitBase.repo property
        self.remote = remote
        # git_root is already set by GitBase.__init__() from get_git_root()
        # The passed git_root parameter is for compatibility and should match
        if git_root != self.git_root:
            logger.debug(
                "Note: git_root parameter (%s) differs from detected git root (%s)",
                git_root,
                self.git_root,
            )
        # Use the detected git_root from GitBase

    def _is_excluded(self, file_path: str, exclude_patterns: list[str] | None) -> bool:
        """Check if a file should be excluded based on exclude patterns.

        Args:
            file_path: The file path to check
            exclude_patterns: List of glob patterns to exclude

        Returns:
            True if the file should be excluded, False otherwise
        """
        if not exclude_patterns:
            return False

        return any(fnmatch.fnmatch(file_path, pattern) for pattern in exclude_patterns)

    @abstractmethod
    def can_handle(self, source_path: str) -> bool:
        """Check if this syncer can handle the given source path."""

    @abstractmethod
    def sync(
        self,
        source_path: str,
        destination_path: str,
        commit_hash: str,
        force: bool = False,
        ignore_changes: bool = False,
        include_subdirs: bool = False,
        transform: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> SyncSuccess:
        """Sync the Git object from source to destination."""

    @abstractmethod
    def check(
        self,
        source_path: str,
        destination_path: str,
        commit_hash: str,
        transform: list[str] | None = None,
        include_subdirs: bool = False,
        exclude: list[str] | None = None,
    ) -> SyncSuccess:
        """Check the status of the Git object without syncing."""

    def _resolve_full_path(self, file_path: str) -> str:
        """Resolve the full file path within the repository."""
        # Duplicate the logic from GitRepository._resolve_file_path
        file_path_obj = Path(file_path)

        if self.remote.base_path:
            base_path_obj = Path(self.remote.base_path)

            # Combine base path with file path and normalize
            combined_path = base_path_obj / file_path_obj

            # Resolve any relative components (.., .) without going to filesystem
            # This works entirely with path strings
            parts: list[str] = []
            for part in combined_path.parts:
                if part == "..":
                    if parts:  # Don't go above repository root
                        parts.pop()
                elif part != ".":  # Skip current directory references
                    parts.append(part)

            # Join the normalized parts
            if parts:
                return str(Path(*parts))
            else:
                return ""  # Empty path means repository root
        else:
            # No base path, file is at repository root
            return str(file_path_obj)

    def _get_local_file_hash(self, file_path: str | Path) -> str | None:
        """Get the hash of a local file using git."""
        return self.get_local_file_hash(str(file_path))

    def _has_local_changes(self, file_path: str | Path) -> bool:
        """Check if a local file has uncommitted changes."""
        return self.has_local_changes(str(file_path))

    def _resolve_commit_with_fetch(self, commit_hash: str):
        """
        Resolve a commit, fetching from remote if not found locally.

        Returns:
            git.Commit: The resolved commit object

        Raises:
            Exception: If the commit cannot be found even after fetching
        """
        import git

        try:
            # First try to get the commit directly
            return self.remote_repo.commit(commit_hash)
        except (git.BadName, git.BadObject):
            # Commit not found locally, try to fetch it
            logger.info("Commit %s not found locally, fetching from remote", commit_hash)
            try:
                origin = self.remote_repo.remotes.origin
                origin.fetch()
                logger.debug("Successfully fetched from remote")

                # Try again after fetch
                return self.remote_repo.commit(commit_hash)
            except Exception as fetch_error:
                logger.warning("Could not fetch from remote: %s", fetch_error)
                # Re-raise the original commit lookup error
                raise

    def _process_operation(
        self,
        source_path: str,
        destination_path: str,
        commit_hash: str,
        mode: OperationMode,
        force: bool = False,
        ignore_changes: bool = False,
        include_subdirs: bool = False,
        transform: list[str] | None = None,
        exclude: list[str] | None = None,
    ) -> SyncSuccess:
        """
        Template method that handles the common sync/check operation pattern.

        This method implements the common flow:
        1. Find matching items (files/trees)
        2. Validate they exist
        3. Process each item according to the operation mode
        4. Generate final result
        """
        try:
            # Step 1: Find matching items to process
            matched_items = self._find_matching_items(
                source_path, commit_hash, include_subdirs, exclude
            )

            # Step 2: Validate items exist
            if not matched_items:
                exception = self._handle_no_items_found(source_path, commit_hash)
                raise exception

            # Step 3: Process each item
            stats = ProcessingStats()

            for item_data in matched_items:
                try:
                    self._process_single_item(
                        item_data,
                        destination_path,
                        source_path,
                        mode,
                        force,
                        ignore_changes,
                        transform,
                        stats,
                    )
                except Exception as e:
                    # Extract file path from item_data for better error reporting
                    file_path = (
                        item_data[0]
                        if isinstance(item_data, tuple) and len(item_data) > 0
                        else "unknown"
                    )
                    stats.failed_items.append(f"{file_path}: {e}")

            # Step 4: Generate final result
            return self._generate_final_result(source_path, destination_path, mode, stats)

        except OperationError:
            # Re-raise OperationErrors without wrapping them
            raise
        except Exception as e:
            exception = self._handle_operation_error(source_path, mode, e)
            raise exception from e

    @abstractmethod
    def _find_matching_items(
        self,
        source_path: str,
        commit_hash: str,
        include_subdirs: bool,
        exclude: list[str] | None = None,
    ) -> list[Any]:
        """Find all items to process. Returns implementation-specific item data."""
        ...

    @abstractmethod
    def _process_single_item(
        self,
        item_data: Any,
        destination_path: str,
        source_path: str,
        mode: OperationMode,
        force: bool,
        ignore_changes: bool,
        transform: list[str] | None,
        stats: ProcessingStats,
    ) -> None:
        """Process a single item. Updates stats in-place."""

    @abstractmethod
    def _is_pattern(self, source_path: str) -> bool:
        """Check if the source path represents a pattern (e.g., glob for files, always False for trees)."""

    def _handle_no_items_found(self, source_path: str, commit_hash: str) -> Exception:
        """Handle the case when no items are found to process by returning an exception to raise."""
        is_pattern = self._is_pattern(source_path)
        return GitFileNotFoundError(source_path, commit_hash, is_pattern)

    @abstractmethod
    def _generate_final_result(
        self, source_path: str, destination_path: str, mode: OperationMode, stats: ProcessingStats
    ) -> SyncSuccess:
        """Generate the final result based on processing statistics."""

    def _handle_operation_error(
        self, source_path: str, mode: OperationMode, error: Exception
    ) -> Exception:
        """Handle errors that occur during the operation by returning an exception to raise."""
        is_pattern = self._is_pattern(source_path)
        operation_name = mode.value
        logger.error(
            "Failed to %s %s %s: %s",
            operation_name,
            "pattern" if is_pattern else "path",
            source_path,
            error,
        )
        return OperationError(operation_name, source_path, str(error), is_pattern)
