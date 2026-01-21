"""File synchronization logic for git-crossref."""

from dataclasses import dataclass

from .config import FileSync, GitSyncConfig, get_git_root
from .git_ops import GitSyncManager
from .logger import logger
from .status import SyncStatus


@dataclass
class SyncResult:
    """Result of a file sync operation."""

    file_sync: FileSync
    remote_name: str
    status: SyncStatus
    message: str
    files_processed: int = 1
    local_hash: str | None = None
    remote_hash: str | None = None

    @property
    def objects_synced(self) -> int:
        """Backward compatibility property for tests."""
        return self.files_processed


class FileSyncer:
    """Handles synchronization of individual files."""

    def __init__(self, config: GitSyncConfig, git_manager: GitSyncManager):
        self.config = config
        self.git_manager = git_manager
        self.git_root = get_git_root()

    def sync_file(self, remote_name: str, file_sync: FileSync, force: bool = False) -> SyncResult:
        """Sync content from a remote repository using the appropriate strategy."""
        if remote_name not in self.config.remotes:
            return SyncResult(
                file_sync=file_sync,
                remote_name=remote_name,
                status=SyncStatus.ERROR,
                message=f"Remote '{remote_name}' not found in configuration",
            )

        remote = self.config.remotes[remote_name]
        repo_manager = self.git_manager.get_repository(remote_name, remote)

        # Determine which commit/version to use
        target_commit = file_sync.hash or remote.version

        # Create appropriate syncer using polymorphism
        syncer = self.git_manager.create_syncer(remote, repo_manager.repo, file_sync.source)

        logger.info("Syncing %s -> %s", file_sync.source, file_sync.destination)

        try:
            git_result = syncer.sync(
                file_sync.source,
                file_sync.destination,
                target_commit,
                force=force,
                ignore_changes=file_sync.ignore_changes,
                include_subdirs=file_sync.include_subdirs,
                transform=file_sync.transform,
                exclude=file_sync.exclude,
            )

            return SyncResult(
                file_sync=file_sync,
                remote_name=remote_name,
                status=SyncStatus.SUCCESS,
                message=git_result.message,
                files_processed=git_result.objects_processed,
                local_hash=None,  # Not applicable for polymorphic sync
                remote_hash=None,  # Not applicable for polymorphic sync
            )

        except Exception as e:
            logger.error("Error syncing %s: %s", file_sync.source, e)
            return SyncResult(
                file_sync=file_sync,
                remote_name=remote_name,
                status=SyncStatus.ERROR,
                message=f"Sync failed: {e}",
            )

    def check_file(self, remote_name: str, file_sync: FileSync) -> SyncResult:
        """Check the status of a file without syncing it using polymorphic syncers."""
        if remote_name not in self.config.remotes:
            return SyncResult(
                file_sync=file_sync,
                remote_name=remote_name,
                status=SyncStatus.ERROR,
                message=f"Remote '{remote_name}' not found in configuration",
            )

        remote = self.config.remotes[remote_name]
        repo_manager = self.git_manager.get_repository(remote_name, remote)

        # Determine which commit/version to use
        target_commit = file_sync.hash or remote.version

        # Create appropriate syncer using polymorphism (same as sync_file)
        syncer = self.git_manager.create_syncer(remote, repo_manager.repo, file_sync.source)

        try:
            git_result = syncer.check(
                file_sync.source,
                file_sync.destination,
                target_commit,
                transform=file_sync.transform,
                include_subdirs=file_sync.include_subdirs,
                exclude=file_sync.exclude,
            )

            try:
                status = SyncStatus.from_text(git_result.message)
            except ValueError:
                logger.warning(
                    "Unrecognized check status for %s: %s",
                    file_sync.destination,
                    git_result.message,
                )
                status = SyncStatus.ERROR

            return SyncResult(
                file_sync=file_sync,
                remote_name=remote_name,
                status=status,
                message=git_result.message,
                files_processed=git_result.objects_processed,
                local_hash=None,  # Not applicable for polymorphic check
                remote_hash=None,  # Not applicable for polymorphic check
            )

        except Exception as e:
            logger.error("Error checking %s: %s", file_sync.source, e)
            return SyncResult(
                file_sync=file_sync,
                remote_name=remote_name,
                status=SyncStatus.ERROR,
                message=f"Check failed: {e}",
            )


class GitSyncOrchestrator:
    """Orchestrates file synchronization operations."""

    def __init__(self, config: GitSyncConfig):
        self.config = config
        self.git_manager = GitSyncManager()
        self.syncer = FileSyncer(config, self.git_manager)

    def sync_all(self, force: bool = False, remote_filter: str | None = None) -> list[SyncResult]:
        """Sync all configured files."""
        results = []

        for remote_name, file_list in self.config.files.items():
            if remote_filter and remote_name != remote_filter:
                continue

            for file_sync in file_list:
                result = self.syncer.sync_file(remote_name, file_sync, force)
                results.append(result)

        return results

    def sync_files(self, file_patterns: list[str], force: bool = False) -> list[SyncResult]:
        """Sync specific files by destination pattern."""
        results = []

        for remote_name, file_list in self.config.files.items():
            for file_sync in file_list:
                # Check if this file matches any of the patterns
                if any(pattern in file_sync.destination for pattern in file_patterns):
                    result = self.syncer.sync_file(remote_name, file_sync, force)
                    results.append(result)

        return results

    def check_all(self, remote_filter: str | None = None) -> list[SyncResult]:
        """Check status of all configured files."""
        results = []

        for remote_name, file_list in self.config.files.items():
            if remote_filter and remote_name != remote_filter:
                continue

            for file_sync in file_list:
                result = self.syncer.check_file(remote_name, file_sync)
                results.append(result)

        return results

    def check_files(self, file_patterns: list[str]) -> list[SyncResult]:
        """Check status of specific files by destination pattern."""
        results = []

        for remote_name, file_list in self.config.files.items():
            for file_sync in file_list:
                if any(pattern in file_sync.destination for pattern in file_patterns):
                    result = self.syncer.check_file(remote_name, file_sync)
                    results.append(result)

        return results

    def cleanup(self) -> None:
        """Clean up temporary resources."""
        self.git_manager.cleanup_cache()


def format_sync_results(
    results: list[SyncResult], verbose: bool = False, dry_run: bool = False
) -> str:
    """Format sync results for display."""
    if not results:
        return "No files to sync."

    output = []

    # Group results by status using the enum values directly
    success = [r for r in results if r.status == SyncStatus.SUCCESS]
    skipped = [r for r in results if r.status == SyncStatus.SKIPPED]
    errors = [r for r in results if r.status == SyncStatus.ERROR]
    local_changes = [r for r in results if r.status == SyncStatus.LOCAL_CHANGES]
    not_found = [r for r in results if r.status == SyncStatus.NOT_FOUND]
    needs_update = [r for r in results if r.status == SyncStatus.NEEDS_UPDATE]

    def format_file_list(file_results: list[SyncResult], status_type: SyncStatus) -> None:
        if not file_results:
            return

        # Calculate total files processed across all results
        total_files = sum(result.files_processed for result in file_results)

        # Use the new colored string method for headers
        title = f"{status_type.to_colored_string()} ({total_files} files)"
        output.append(f"\n{title}:")

        for result in file_results:
            prefix = (
                f"  {result.remote_name}:{result.file_sync.source} -> "
                f"{result.file_sync.destination}"
            )

            # Add dry-run specific messaging
            if dry_run and status_type in (
                SyncStatus.SUCCESS,
                SyncStatus.LOCAL_CHANGES,
                SyncStatus.NEEDS_UPDATE,
            ):
                match status_type:
                    case SyncStatus.SUCCESS:
                        action = "would sync"
                    case SyncStatus.LOCAL_CHANGES:
                        action = "would skip (local changes)"
                    case SyncStatus.NEEDS_UPDATE:
                        action = "needs update"
                message = f"{action}: {result.message}"
            else:
                message = result.message

            if verbose:
                hash_info = ""
                if result.local_hash or result.remote_hash:
                    hash_info = (
                        f" (local: {result.local_hash[:8] if result.local_hash else 'none'}, "
                        f"remote: {result.remote_hash[:8] if result.remote_hash else 'none'})"
                    )
                output.append(f"{prefix}{hash_info}")
                output.append(f"    {message}")
            else:
                output.append(f"{prefix}: {message}")

    # Use the enum values to get consistent formatting
    if success:
        format_file_list(success, SyncStatus.SUCCESS)
    if skipped:
        format_file_list(skipped, SyncStatus.SKIPPED)
    if needs_update:
        format_file_list(needs_update, SyncStatus.NEEDS_UPDATE)
    if local_changes:
        format_file_list(local_changes, SyncStatus.LOCAL_CHANGES)
    if not_found:
        format_file_list(not_found, SyncStatus.NOT_FOUND)
    if errors:
        format_file_list(errors, SyncStatus.ERROR)

    # Summary - use actual file counts
    success_files = sum(r.files_processed for r in success)
    skipped_files = sum(r.files_processed for r in skipped)
    needs_update_files = sum(r.files_processed for r in needs_update)
    local_changes_files = sum(r.files_processed for r in local_changes)
    not_found_files = sum(r.files_processed for r in not_found)
    errors_files = sum(r.files_processed for r in errors)
    total_files = sum(r.files_processed for r in results)

    output.append(
        f"\nSummary: {success_files} synced, {skipped_files} skipped, "
        f"{needs_update_files} need update, {local_changes_files} with local changes, "
        f"{not_found_files} not found, {errors_files} errors out of {total_files} total files."
    )

    return "\n".join(output)
