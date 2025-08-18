"""Base repository management with lazy initialization pattern."""

from abc import ABC, abstractmethod
from pathlib import Path

from git import Repo


class BaseRepository(ABC):
    """Base class for repository management with lazy initialization."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self._repo: Repo | None = None

    @property
    def repo(self) -> Repo:
        """Get the git repository instance, initializing if needed."""
        if self._repo is None:
            self._repo = self._initialize_repo()
        # After initialization, _repo should never be None
        assert self._repo is not None
        return self._repo

    @abstractmethod
    def _initialize_repo(self) -> Repo:
        """Initialize the repository. Subclasses must implement this."""
