"""Git operations for syncing files and directories from remote repositories using bare clones."""

import hashlib
import shutil
from pathlib import Path

import git
from git import Repo

from .base_syncer import BaseGitObjectSyncer
from .blob_syncer import BlobSyncer
from .config import Remote
from .exceptions import AuthenticationError, GitCloneError, GitSyncConnectionError
from .git_base import GitBase
from .logger import logger
from .repository_base import BaseRepository
from .tree_syncer import TreeSyncer


class GitRepository(BaseRepository):
    """Manages a bare clone of a remote repository for efficient object access."""

    def __init__(self, remote: Remote, cache_dir: Path):
        self.remote = remote
        self.cache_dir = cache_dir
        self.repo_path = cache_dir / self._get_repo_name()
        super().__init__(self.repo_path)

    def _get_repo_name(self) -> str:
        """Get a unique name for this repository based on URL."""
        # Create a hash of the URL to ensure uniqueness
        url_hash = hashlib.md5(self.remote.url.encode()).hexdigest()[:8]
        repo_name = self.remote.url.split("/")[-1].replace(".git", "")
        return f"{repo_name}_{url_hash}"

    def _initialize_repo(self) -> Repo:
        """Initialize the repository, cloning if needed."""
        if not self.repo_path.exists():
            return self._clone_bare()
        else:
            repo = Repo(self.repo_path)
            self._update_repo(repo)
            return repo

    def _clone_bare(self) -> Repo:
        """Clone the repository as a bare repository."""
        logger.info("Cloning %s", self.remote.url)
        self.repo_path.mkdir(parents=True, exist_ok=True)

        try:
            # Use GitPython for bare cloning
            repo = Repo.clone_from(self.remote.url, self.repo_path, bare=True)

            # Configure the refspec for bare repositories to enable proper fetching
            # This prevents the "Remote 'origin' has no refspec set" warning
            origin = repo.remotes.origin
            origin.config_writer.set("fetch", "+refs/heads/*:refs/heads/*")

            logger.info("Successfully cloned %s", self.remote.url)
            return repo
        except git.GitCommandError as e:
            error_msg = str(e).lower()
            if "authentication failed" in error_msg or "access denied" in error_msg:
                raise AuthenticationError(self.remote.url) from e
            elif "could not resolve host" in error_msg or "network" in error_msg:
                raise GitSyncConnectionError(self.remote.url, str(e)) from e
            else:
                raise GitCloneError(self.remote.url, str(e)) from e
        except Exception as e:
            raise GitCloneError(self.remote.url, str(e)) from e

    def _update_repo(self, repo: Repo) -> None:
        """Update the repository to fetch latest changes."""
        try:
            logger.info("Updating cache for %s", self.remote.url)
            origin = repo.remotes.origin
            # Fetch all refs for bare repository
            origin.fetch()
            logger.debug("Successfully updated cache for %s", self.remote.url)
        except Exception as e:
            logger.warning("Failed to update repository %s: %s", self.remote.url, e)

    def get_file_at_commit(self, file_path: str, commit_hash: str | None = None) -> bytes | None:
        """Get file contents at a specific commit or default version."""
        try:
            # Ensure repository is initialized
            repo = self.repo

            # If no commit hash provided, use the default version
            if commit_hash is None:
                commit_hash = self.remote.version

            # Resolve commit hash from branch/tag if needed
            resolved_commit = self._resolve_commit_hash(commit_hash)

            # Ensure we have the commit
            if not self._has_commit(resolved_commit):
                self._fetch_commit(resolved_commit)

            # Resolve the full path within the repository
            full_path = self._resolve_file_path(file_path)

            # Get the file blob at the specified commit
            commit = repo.commit(resolved_commit)
            blob = commit.tree / full_path
            return blob.data_stream.read()

        except Exception as e:
            logger.error("Error getting file %s at %s: %s", file_path, commit_hash, e)
            return None

    def get_file_hash(self, file_path: str, commit_hash: str | None = None) -> str | None:
        """Get the blob hash of a file at a specific commit."""
        try:
            # Ensure repository is initialized
            repo = self.repo

            if commit_hash is None:
                commit_hash = self.remote.version

            # Resolve commit hash from branch/tag if needed
            resolved_commit = self._resolve_commit_hash(commit_hash)

            if not self._has_commit(resolved_commit):
                self._fetch_commit(resolved_commit)

            full_path = self._resolve_file_path(file_path)
            commit = repo.commit(resolved_commit)
            blob = commit.tree / full_path
            return blob.hexsha

        except Exception as e:
            logger.error("Error getting hash for %s at %s: %s", file_path, commit_hash, e)
            return None

    def _has_commit(self, commit_hash: str) -> bool:
        """Check if we have a specific commit."""
        try:
            repo = self.repo
            repo.commit(commit_hash)
            return True
        except (git.BadName, git.BadObject):
            return False

    def _fetch_commit(self, commit_hash: str) -> None:
        """Fetch a specific commit if we don't have it."""
        if self._repo is None:
            return
        try:
            logger.info("Fetching commit %s", commit_hash)
            origin = self._repo.remotes.origin
            # For bare repos, fetch all refs to ensure we have the commit
            origin.fetch()
            logger.debug("Successfully fetched commit %s", commit_hash)
        except Exception as e:
            logger.warning("Could not fetch commit %s: %s", commit_hash, e)

    def _resolve_commit_hash(self, ref: str) -> str:
        """Resolve a branch/tag/commit reference to a commit hash."""
        try:
            repo = self.repo
            # Try to resolve as a reference (branch/tag)
            if ref.startswith("origin/"):
                # Already prefixed with origin
                return repo.commit(ref).hexsha
            else:
                # Try with origin/ prefix first for branches
                try:
                    return repo.commit(f"origin/{ref}").hexsha
                except (git.BadName, git.BadObject):
                    # Fall back to direct reference (tag or commit hash)
                    return repo.commit(ref).hexsha
        except (git.BadName, git.BadObject):
            # If all else fails, return the original ref (might be a commit hash)
            return ref

    def _resolve_file_path(self, file_path: str) -> str:
        """Resolve the full file path within the repository."""
        file_path_obj = Path(file_path)

        if self.remote.base_path:
            base_path_obj = Path(self.remote.base_path)
            combined_path = base_path_obj / file_path_obj

            parts: list[str] = []
            for part in combined_path.parts:
                if part == "..":
                    if parts:  # Don't go above repository root
                        parts.pop()
                elif part != ".":  # Skip current directory references
                    parts.append(part)

            if parts:
                return str(Path(*parts))
            return ""  # Empty path means repository root

        # No base path, file is at repository root
        return str(file_path_obj)


class GitSyncManager(GitBase):
    """Manages git operations for file synchronization."""

    def __init__(self):
        super().__init__()
        self.cache_dir = self.git_root / ".git" / "crossref-cache"
        self.cache_dir.mkdir(exist_ok=True)
        self._repositories: dict[str, GitRepository] = {}

    def get_repository(self, name: str, remote: Remote) -> GitRepository:
        """Get or create a repository manager for the given remote."""
        if name not in self._repositories:
            self._repositories[name] = GitRepository(remote, self.cache_dir)
        return self._repositories[name]

    def create_syncer(self, remote: Remote, repo: Repo, source_path: str) -> BaseGitObjectSyncer:
        """Create the appropriate syncer for the source path using polymorphism."""
        # Try tree syncer first (directories ending with /)
        tree_syncer = TreeSyncer(repo, remote, self.git_root)
        if tree_syncer.can_handle(source_path):
            logger.debug("Using TreeSyncer for %s", source_path)
            return tree_syncer

        # Use unified blob syncer for both single files and glob patterns
        blob_syncer = BlobSyncer(repo, remote, self.git_root)
        assert blob_syncer.can_handle(source_path)

        logger.debug("Using BlobSyncer for %s", source_path)
        return blob_syncer

    def cleanup_cache(self) -> None:
        """Clean up the repository cache."""
        if self.cache_dir.exists():
            logger.info("Cleaning up cache directory: %s", self.cache_dir)
            shutil.rmtree(self.cache_dir)
            logger.info("Successfully cleaned cache directory")
