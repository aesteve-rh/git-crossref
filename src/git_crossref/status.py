"""Sync status enumeration and utilities."""

from enum import StrEnum, auto


class SyncStatus(StrEnum):
    """Status of a file sync operation."""

    SUCCESS = auto()
    SKIPPED = auto()
    ERROR = auto()
    LOCAL_CHANGES = auto()
    NOT_FOUND = auto()
    NEEDS_UPDATE = auto()

    @classmethod
    def from_text(cls, text: str) -> "SyncStatus":
        """Convert text or text containing status keywords into a SyncStatus enum.

        This method allows flexible matching based on keywords found in text:
        - "success", "successful", "synced", "ok" -> SUCCESS
        - "skip", "skipped", "up to date", "unchanged" -> SKIPPED
        - "error", "failed", "failure" -> ERROR
        - "local changes", "modified", "uncommitted" -> LOCAL_CHANGES
        - "not found", "missing", "404" -> NOT_FOUND

        Args:
            text: The text to analyze for status keywords

        Returns:
            SyncStatus enum value

        Raises:
            ValueError: If no status can be determined from the text
        """
        text_lower = text.lower().strip()

        # Direct enum value matches
        try:
            return cls(text_lower.replace(" ", "_"))
        except ValueError:
            pass

        # Keyword-based matching
        success_keywords = ["success", "successful", "synced", "ok", "done", "completed"]
        skip_keywords = ["skip", "skipped", "up to date", "unchanged", "already", "same"]
        error_keywords = ["error", "failed", "failure", "exception", "crash"]
        local_changes_keywords = ["local changes", "modified", "uncommitted", "dirty", "changed"]
        not_found_keywords = ["not found", "missing", "404", "does not exist", "absent"]
        needs_update_keywords = [
            "would be updated",
            "differs from remote",
            "needs update",
            "out of date",
        ]

        # Check for keyword matches
        if any(keyword in text_lower for keyword in success_keywords):
            return cls.SUCCESS
        elif any(keyword in text_lower for keyword in skip_keywords):
            return cls.SKIPPED
        elif any(keyword in text_lower for keyword in error_keywords):
            return cls.ERROR
        elif any(keyword in text_lower for keyword in local_changes_keywords):
            return cls.LOCAL_CHANGES
        elif any(keyword in text_lower for keyword in not_found_keywords):
            return cls.NOT_FOUND
        elif any(keyword in text_lower for keyword in needs_update_keywords):
            return cls.NEEDS_UPDATE

        # If no keywords match, default to ERROR for safety
        raise ValueError(f"Could not determine sync status from text: '{text}'")

    @property
    def is_success(self) -> bool:
        """Check if this status represents a successful operation."""
        return self == self.SUCCESS  # type: ignore[comparison-overlap]

    @property
    def is_error(self) -> bool:
        """Check if this status represents an error condition."""
        return self in (self.ERROR, self.LOCAL_CHANGES, self.NOT_FOUND)  # type: ignore[comparison-overlap]

    @property
    def is_actionable(self) -> bool:
        """Check if this status represents something that could be fixed with --force."""
        return self in (self.LOCAL_CHANGES, self.NEEDS_UPDATE)  # type: ignore[comparison-overlap]

    def to_colored_string(self) -> str:
        """Get a colored string representation using ANSI codes."""
        match self:
            case self.SUCCESS:
                return "\033[92m[OK] SUCCESS\033[0m"  # Green
            case self.SKIPPED:
                return "\033[93m[SKIP] SKIPPED\033[0m"  # Yellow
            case self.ERROR:
                return "\033[91m[ERROR] ERROR\033[0m"  # Red
            case self.LOCAL_CHANGES:
                return "\033[93m[WARN] LOCAL_CHANGES\033[0m"  # Yellow
            case self.NOT_FOUND:
                return "\033[91m[ERROR] NOT_FOUND\033[0m"  # Red
            case self.NEEDS_UPDATE:
                return "\033[93m[UPDATE] NEEDS_UPDATE\033[0m"  # Yellow
            case _:
                return f"[UNKNOWN] {self.value.upper()}"
