"""Syncer for Git blob objects (files), supporting both single files and glob patterns."""

import fnmatch
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from git.objects import Blob, Tree

from .base_syncer import BaseGitObjectSyncer, OperationMode, ProcessingStats, SyncSuccess
from .config import apply_transformations, get_transformed_content_hash
from .exceptions import DirectoryPreparationError, LocalChangesError, SyncError, TransformationError
from .logger import logger


@dataclass
class GlobPatternParts:
    """Represents the parsed components of a glob pattern.

    Attributes:
        base_path: The directory path before any wildcards (e.g., "src/utils" from "src/utils/*.py")
        pattern: The glob pattern part with wildcards (e.g., "*.py" from "src/utils/*.py")
                 None if no wildcards were found in the path
    """

    base_path: str = ""
    pattern: str | None = None

    @property
    def is_valid(self) -> bool:
        """Check if this represents a valid glob pattern."""
        return self.pattern is not None

    @property
    def has_wildcards(self) -> bool:
        """Check if the pattern contains wildcards."""
        return self.pattern is not None and ("*" in self.pattern or "?" in self.pattern)


class SyncOutcome(Enum):
    """Possible outcomes of a successful file sync operation."""

    SYNCED = auto()
    ALREADY_UP_TO_DATE = auto()


class BlobSyncer(BaseGitObjectSyncer):
    """Syncer for Git blob objects, supporting both single files and glob patterns."""

    def can_handle(self, source_path: str) -> bool:
        """Blob syncer handles files (no trailing slash) - both single files and glob patterns."""
        return not source_path.endswith("/")

    def _is_glob_pattern(self, source_path: str) -> bool:
        """Check if the source path contains glob wildcards."""
        return "*" in source_path or "?" in source_path

    def _is_pattern(self, source_path: str) -> bool:
        """Check if the source path represents a pattern (glob for files)."""
        return self._is_glob_pattern(source_path)

    def _find_matching_files(
        self, source_path: str, commit_hash: str, include_subdirs: bool = False
    ) -> list[tuple[str, Blob]]:
        """Find files matching the source path (either single file or glob pattern)."""
        commit = self._resolve_commit_with_fetch(commit_hash)

        if not self._is_glob_pattern(source_path):
            return self._find_single_file(commit, source_path)

        return self._find_glob_matches(commit, source_path, include_subdirs)

    def _find_single_file(self, commit, source_path: str) -> list[tuple[str, Blob]]:
        """Find a single file in the commit."""
        full_source_path = self._resolve_full_path(source_path)
        try:
            blob = commit.tree / full_source_path
            if not isinstance(blob, Blob):
                return []  # Not a file
            return [(source_path, blob)]
        except Exception:
            return []  # File not found

    def _find_glob_matches(
        self, commit, source_path: str, include_subdirs: bool
    ) -> list[tuple[str, Blob]]:
        """Find files matching a glob pattern."""
        pattern_parts = self._parse_glob_pattern(source_path)
        if not pattern_parts.is_valid:
            return []

        tree_obj = self._get_tree_for_base_path(commit, pattern_parts.base_path)
        if not tree_obj:
            return []

        # pattern_parts.pattern is guaranteed to be non-None since we checked is_valid
        assert pattern_parts.pattern is not None

        if include_subdirs:
            return self._match_files_recursive(
                tree_obj, pattern_parts.pattern, pattern_parts.base_path
            )
        else:
            return self._match_files_direct(tree_obj, pattern_parts.pattern)

    def _parse_glob_pattern(self, source_path: str) -> GlobPatternParts:
        """Parse a glob pattern to extract base path and pattern.

        Args:
            source_path: The source path that may contain glob patterns

        Returns:
            GlobPatternParts containing the base path and pattern components

        Examples:
            "src/utils/*.py" -> GlobPatternParts(base_path="src/utils", pattern="*.py")
            "*.txt" -> GlobPatternParts(base_path="", pattern="*.txt")
            "config.yaml" -> GlobPatternParts(base_path="", pattern=None)
        """
        pattern_path = Path(source_path)
        base_parts: list[str] = []

        for i, part in enumerate(pattern_path.parts):
            if "*" in part or "?" in part:
                glob_pattern = "/".join(pattern_path.parts[i:])
                base_path = "/".join(base_parts) if base_parts else ""
                return GlobPatternParts(base_path=base_path, pattern=glob_pattern)
            base_parts.append(part)

        return GlobPatternParts()

    def _get_tree_for_base_path(self, commit, base_path: str) -> Tree | None:
        """Get the tree object for the given base path."""
        full_base_path = self._resolve_full_path(base_path)
        try:
            tree_obj = commit.tree
            if full_base_path:
                tree_obj = commit.tree / full_base_path

            if not isinstance(tree_obj, Tree):
                return None
            return tree_obj
        except Exception:
            return None

    def _match_files_recursive(
        self, tree_obj: Tree, glob_pattern: str, base_path: str
    ) -> list[tuple[str, Blob]]:
        """Match files recursively in subdirectories."""
        matched_files = []
        full_base_path = self._resolve_full_path(base_path)

        for item in tree_obj.traverse():
            if isinstance(item, Blob):
                item_path = Path(item.path)
                if full_base_path:
                    full_base_path_obj = Path(full_base_path)
                    try:
                        relative_path = str(item_path.relative_to(full_base_path_obj))
                    except ValueError:
                        continue  # Skip items not in our base path
                else:
                    relative_path = str(item_path)

                if fnmatch.fnmatch(relative_path, glob_pattern):
                    matched_files.append((relative_path, item))

        return matched_files

    def _match_files_direct(self, tree_obj: Tree, glob_pattern: str) -> list[tuple[str, Blob]]:
        """Match files directly in the tree (no subdirectories)."""
        matched_files = []

        for item in tree_obj:
            if isinstance(item, Blob):
                relative_path = item.name
                if fnmatch.fnmatch(relative_path, glob_pattern):
                    matched_files.append((relative_path, item))

        return matched_files

    def _process_destination_path(
        self, source_path: str, destination_path: str, relative_path: str
    ) -> Path:
        """Process the destination path for a single file or glob pattern."""
        if self._is_glob_pattern(source_path):
            return Path(destination_path) / relative_path

        return Path(destination_path)

    def _find_matching_items(
        self,
        source_path: str,
        commit_hash: str,
        include_subdirs: bool,
        exclude: list[str] | None = None,
    ) -> list[tuple[str, Blob]]:
        """Find files matching the source path (either single file or glob pattern)."""
        matched_files = self._find_matching_files(source_path, commit_hash, include_subdirs)

        # Apply exclusion filters
        if exclude:
            filtered_files = []
            for relative_path, blob in matched_files:
                if not self._is_excluded(relative_path, exclude):
                    filtered_files.append((relative_path, blob))
                else:
                    logger.debug("Excluding file: %s", relative_path)
            return filtered_files

        return matched_files

    def _process_single_item(
        self,
        item_data: tuple[str, Blob],
        destination_path: str,
        source_path: str,
        mode: OperationMode,
        force: bool,
        ignore_changes: bool,
        transform: list[str] | None,
        stats: ProcessingStats,
    ) -> None:
        """Process a single file for sync or check operation."""
        relative_path, blob = item_data

        # Debug message for each file being processed
        dest_file_path = self._process_destination_path(
            source_path, destination_path, relative_path
        )
        logger.debug("Processing file: %s -> %s", relative_path, dest_file_path)

        if mode == OperationMode.SYNC:
            # Perform actual sync
            outcome = self._sync_single_file(
                relative_path,
                blob,
                destination_path,
                source_path,
                force,
                ignore_changes,
                transform,
            )
            if outcome == SyncOutcome.SYNCED:
                stats.synced_count += 1
            return

        # Check mode - determine what would happen
        local_path = self.git_root / dest_file_path

        if not local_path.exists():
            stats.would_sync_count += 1
            return

        local_hash = self._get_local_file_hash(dest_file_path)

        expected_hash = blob.hexsha
        if transform:
            try:
                content = blob.data_stream.read()
                expected_hash = get_transformed_content_hash(content, transform)
            except (UnicodeDecodeError, ValueError) as e:
                # If transformation fails, treat as binary or invalid transformation
                expected_hash = blob.hexsha
                logger.debug(
                    "Cannot apply transformations for check comparison of %s: %s", relative_path, e
                )

        if local_hash == expected_hash:
            stats.up_to_date_count += 1
        elif self._has_local_changes(dest_file_path):
            stats.failed_items.append(f"{relative_path} (local changes)")
        else:
            stats.would_sync_count += 1

    def _generate_final_result(
        self, source_path: str, destination_path: str, mode: OperationMode, stats: ProcessingStats
    ) -> SyncSuccess:
        """Generate the final result based on processing statistics."""
        is_glob = self._is_glob_pattern(source_path)

        if mode == OperationMode.SYNC:
            result = stats.generate_sync_result(source_path, is_glob)
            # Log successful sync operations
            if is_glob:
                logger.info(
                    "Synced glob %s -> %s (%s files)",
                    source_path,
                    destination_path,
                    stats.synced_count,
                )
            else:
                logger.info("Synced file %s -> %s", source_path, destination_path)
            return result
        else:
            return stats.generate_check_result(is_glob)

    def _should_sync_file(
        self,
        local_path: Path,
        dest_file_path: Path,
        blob: Blob,
        content: bytes,
        force: bool,
        ignore_changes: bool,
        transform: list[str] | None,
    ) -> bool:
        """
        Check if a file should be synced.

        Returns:
            True if the file should be synced, False if it's already up to date

        Raises:
            LocalChangesError: If the file has local changes that would be overwritten
            UnicodeDecodeError: If transformation requires text decoding but content is binary
            ValueError: If transformation configuration is invalid
        """
        if not local_path.exists() or force or ignore_changes:
            return True

        local_hash = self._get_local_file_hash(dest_file_path)

        expected_hash = blob.hexsha
        if transform:
            expected_hash = get_transformed_content_hash(content, transform)

        if local_hash == expected_hash:
            return False
        elif self._has_local_changes(dest_file_path):
            raise LocalChangesError(str(dest_file_path))

        return True

    def _prepare_directory(self, local_path: Path, relative_path: str) -> None:
        """Prepare the destination directory.

        Args:
            local_path: The target file path
            relative_path: Path for error messages

        Raises:
            DirectoryPreparationError: If directory cannot be prepared
        """
        if not local_path.parent.exists():
            local_path.parent.mkdir(parents=True, exist_ok=True)
        if not local_path.parent.is_dir():
            raise DirectoryPreparationError(
                relative_path, "parent path exists but is not a directory"
            )

    def _apply_transformations(
        self, content: bytes, transform: list[str] | None, relative_path: str
    ) -> bytes:
        """Apply transformations to content.

        Args:
            content: The original file content as bytes
            transform: List of sed-like transformation patterns
            relative_path: Path for logging purposes

        Returns:
            The transformed content as bytes

        Raises:
            TransformationError: If transformation fails
        """
        if not transform:
            return content

        try:
            transformed_content = apply_transformations(content.decode("utf-8"), transform)
            logger.debug("Applied %s transformations to %s", len(transform), relative_path)

            return transformed_content.encode("utf-8")

        except UnicodeDecodeError:
            logger.warning(
                "Cannot decode file %s as UTF-8, skipping transformations", relative_path
            )
            return content
        except ValueError as e:
            logger.error("Transformation failed for %s: %s", relative_path, e)
            raise TransformationError(relative_path, f"transformation failed: {e}") from e

    def _sync_single_file(
        self,
        relative_path: str,
        blob: Blob,
        destination_path: str,
        source_path: str,
        force: bool = False,
        ignore_changes: bool = False,
        transform: list[str] | None = None,
    ) -> SyncOutcome:
        """
        Sync a single file.

        Returns:
            SyncOutcome indicating what happened

        Raises:
            LocalChangesError: If file has local changes that would be overwritten
            TransformationError: If transformation configuration is invalid or fails
            DirectoryPreparationError: If destination directory cannot be prepared
            SyncError: If file writing or other sync operations fail
        """
        dest_file_path = self._process_destination_path(
            source_path, destination_path, relative_path
        )
        local_path = self.git_root / dest_file_path

        # Get the blob content (we'll need it for both comparison and sync)
        content = blob.data_stream.read()

        # Check if we should sync this file
        try:
            should_sync = self._should_sync_file(
                local_path,
                dest_file_path,
                blob,
                content,
                force,
                ignore_changes,
                transform,
            )
        except ValueError as e:
            # Invalid transformation configuration
            logger.error("Invalid transformation configuration for %s: %s", relative_path, e)
            raise TransformationError(relative_path, str(e)) from e

        if not should_sync:
            return SyncOutcome.ALREADY_UP_TO_DATE

        try:
            # Prepare destination directory
            self._prepare_directory(local_path, relative_path)

            # Apply transformations if specified
            transformed_content = self._apply_transformations(content, transform, relative_path)

            # Write the (possibly transformed) content
            with open(local_path, "wb") as f:
                f.write(transformed_content)

            logger.debug("Synced %s", relative_path)
            return SyncOutcome.SYNCED

        except (DirectoryPreparationError, TransformationError):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            raise SyncError(
                f"Failed to sync '{relative_path}': {e}", dest_path=relative_path
            ) from e

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
        """Sync files from remote to local (supports both single files and glob patterns)."""
        return self._process_operation(
            source_path,
            destination_path,
            commit_hash,
            OperationMode.SYNC,
            force,
            ignore_changes,
            include_subdirs,
            transform,
            exclude,
        )

    def check(
        self,
        source_path: str,
        destination_path: str,
        commit_hash: str,
        transform: list[str] | None = None,
        include_subdirs: bool = False,
        exclude: list[str] | None = None,
    ) -> SyncSuccess:
        """Check the status of files without syncing (supports single files and patterns)."""
        return self._process_operation(
            source_path,
            destination_path,
            commit_hash,
            OperationMode.CHECK,
            False,
            False,
            include_subdirs,
            transform,
            exclude,
        )
