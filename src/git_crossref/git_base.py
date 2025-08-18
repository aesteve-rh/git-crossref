"""Base Git operations and repository management."""

import subprocess

from git import Repo

from .config import get_git_root
from .logger import logger
from .repository_base import BaseRepository
from .status import SyncStatus


class GitBase(BaseRepository):
    """Base class for Git operations with shared local repository access."""

    def __init__(self):
        self.git_root = get_git_root()
        super().__init__(self.git_root)

    def _initialize_repo(self) -> Repo:
        """Initialize the local repository."""
        return Repo(self.git_root)

    @property
    def local_repo(self) -> Repo:
        """Get the local repository instance, initializing if needed."""
        return self.repo

    def get_local_file_hash(self, file_path: str) -> str | None:
        """Get the blob hash of a local file using git."""
        try:
            # Use git hash-object for reliable blob hash calculation
            result = subprocess.run(
                ["git", "hash-object", file_path],
                cwd=self.git_root,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def has_local_changes(self, file_path: str) -> bool:
        """Check if a file has local uncommitted changes using GitPython."""
        try:
            # Check unstaged changes (working directory vs index)
            for item in self.local_repo.index.diff(None):
                if item.a_path == file_path or item.b_path == file_path:
                    return True

            # Check staged changes (files in index vs HEAD)
            for item in self.local_repo.index.diff("HEAD"):
                if item.a_path == file_path or item.b_path == file_path:
                    return True

            # Check untracked files
            untracked_files = self.local_repo.untracked_files
            if file_path in untracked_files:
                return True

            return False

        except Exception:
            # If there's any error, assume no changes for safety
            return False

    def stage_files(self, results: list) -> None:
        """Stage all successfully synced files for commit."""
        synced_files = [r.file_sync.destination for r in results if r.status == SyncStatus.SUCCESS]

        if not synced_files:
            logger.info("No files were synced, nothing to stage")
            return

        try:
            # Stage the files using the existing local_repo instance
            self.local_repo.index.add(synced_files)
            logger.info("Staged %s synced files:", len(synced_files))
            for file_path in synced_files:
                logger.info("  staged: %s", file_path)

            print(f"\n✓ {len(synced_files)} files staged for commit")
            print("Use 'git commit' to create a commit with the synced changes")

        except Exception as e:
            logger.error("Failed to stage files: %s", e)
