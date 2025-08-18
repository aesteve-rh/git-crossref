"""Syncer for Git tree objects (directories)."""

from pathlib import Path

from git.objects import Blob, Tree

from .base_syncer import BaseGitObjectSyncer, OperationMode, ProcessingStats, SyncSuccess
from .config import apply_transformations, get_transformed_content_hash
from .exceptions import GitFileNotFoundError, OperationError
from .logger import logger


class TreeSyncer(BaseGitObjectSyncer):
    """Syncer for Git tree objects (directories)."""

    def can_handle(self, source_path: str) -> bool:
        """Tree syncer handles directories (paths ending with /)."""
        return source_path.endswith("/")

    def _is_pattern(self, source_path: str) -> bool:
        """Check if the source path represents a pattern (always False for trees)."""
        return False

    def _find_matching_items(
        self,
        source_path: str,
        commit_hash: str,
        include_subdirs: bool,
        exclude: list[str] | None = None,
    ) -> list[tuple[str, Blob]]:
        """Find all blob files in the tree."""
        commit = self._resolve_commit_with_fetch(commit_hash)
        full_source_path = self._resolve_full_path(source_path.rstrip("/"))

        try:
            tree_obj = commit.tree / full_source_path if full_source_path else commit.tree
            if not isinstance(tree_obj, Tree):
                raise OperationError(
                    "sync", source_path, f"Path {source_path} is not a directory (tree)", False
                )
        except Exception as e:
            if "not a directory" not in str(e):
                raise GitFileNotFoundError(source_path, commit_hash, False) from e
            raise

        matched_files = []
        for item in tree_obj.traverse():
            if isinstance(item, Blob):
                # Calculate relative path within the tree
                item_path = Path(item.path)
                if full_source_path:
                    full_source_path_obj = Path(full_source_path)
                    try:
                        relative_path = str(item_path.relative_to(full_source_path_obj))
                    except ValueError:
                        continue  # Skip items not in our tree
                else:
                    relative_path = str(item_path)

                # Apply exclusion filters
                if exclude and self._is_excluded(relative_path, exclude):
                    logger.debug("Excluding file: %s", relative_path)
                    continue

                matched_files.append((relative_path, item))

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
        """Process a single file in the tree."""
        relative_path, blob = item_data

        # Calculate destination path
        dest_file_path = Path(destination_path) / relative_path
        local_path = self.git_root / dest_file_path
        logger.debug("Processing tree file: %s -> %s", relative_path, dest_file_path)

        if mode == OperationMode.SYNC:
            # Perform actual sync
            content = blob.data_stream.read()

            # Check if we should sync this file
            should_sync = True
            if local_path.exists() and not force and not ignore_changes:
                local_hash = self._get_local_file_hash(dest_file_path)
                expected_hash = blob.hexsha
                if transform:
                    try:
                        text_content = content.decode("utf-8")
                        transformed_content = apply_transformations(text_content, transform)
                        expected_hash = get_transformed_content_hash(content, transform)
                    except (UnicodeDecodeError, ValueError) as e:
                        from .exceptions import TransformationError

                        raise TransformationError(relative_path, str(e)) from e

                if local_hash == expected_hash:
                    should_sync = False
                elif self._has_local_changes(dest_file_path):
                    from .exceptions import LocalChangesError

                    raise LocalChangesError(str(dest_file_path))

            if should_sync:
                # Prepare destination directory
                if not local_path.parent.exists():
                    local_path.parent.mkdir(parents=True, exist_ok=True)

                # Apply transformations if specified
                final_content = content
                if transform:
                    try:
                        text_content = content.decode("utf-8")
                        transformed_content = apply_transformations(text_content, transform)
                        final_content = transformed_content.encode("utf-8")
                    except (UnicodeDecodeError, ValueError):
                        # Skip transformation for binary files
                        pass

                # Write the (possibly transformed) content
                with open(local_path, "wb") as f:
                    f.write(final_content)

                logger.debug("Synced %s", relative_path)
                stats.synced_count += 1
        else:
            # Check mode - determine what would happen
            if not local_path.exists():
                stats.would_sync_count += 1
                return

            local_hash = self._get_local_file_hash(dest_file_path)
            expected_hash = blob.hexsha
            if transform:
                try:
                    content = blob.data_stream.read()
                    expected_hash = get_transformed_content_hash(content, transform)
                except (UnicodeDecodeError, ValueError):
                    # If transformation fails, treat as binary
                    expected_hash = blob.hexsha

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
        if mode == OperationMode.SYNC:
            result = stats.generate_sync_result(source_path, False)
            logger.info(
                "Synced tree %s -> %s (%s files)", source_path, destination_path, stats.synced_count
            )
            return result
        else:
            return stats.generate_check_result(False)

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
        """Sync an entire directory tree from remote to local."""
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
        """Check the status of an entire directory tree without syncing."""
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
