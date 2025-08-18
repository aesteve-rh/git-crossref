"""Tests for the sync module."""

from unittest.mock import Mock, patch

import pytest

from git_crossref.config import FileSync
from git_crossref.sync import (
    FileSyncer,
    GitSyncOrchestrator,
    SyncResult,
    SyncStatus,
    format_sync_results,
)


class TestSyncStatus:
    """Test the SyncStatus enum."""

    def test_sync_status_values(self):
        """Test SyncStatus enum values."""
        assert SyncStatus.SUCCESS == "success"
        assert SyncStatus.SKIPPED == "skipped"
        assert SyncStatus.ERROR == "error"
        assert SyncStatus.LOCAL_CHANGES == "local_changes"
        assert SyncStatus.NOT_FOUND == "not_found"

    def test_from_text_direct_match(self):
        """Test SyncStatus.from_text with direct enum values."""
        assert SyncStatus.from_text("success") == SyncStatus.SUCCESS
        assert SyncStatus.from_text("error") == SyncStatus.ERROR
        assert SyncStatus.from_text("local_changes") == SyncStatus.LOCAL_CHANGES

    def test_from_text_keyword_matching(self):
        """Test SyncStatus.from_text with keyword matching."""
        assert SyncStatus.from_text("File synced successfully") == SyncStatus.SUCCESS
        assert SyncStatus.from_text("Already up to date") == SyncStatus.SKIPPED
        assert SyncStatus.from_text("Sync failed with error") == SyncStatus.ERROR
        assert SyncStatus.from_text("File has local changes") == SyncStatus.LOCAL_CHANGES
        assert SyncStatus.from_text("File not found") == SyncStatus.NOT_FOUND

    def test_from_text_case_insensitive(self):
        """Test SyncStatus.from_text is case insensitive."""
        assert SyncStatus.from_text("SUCCESS") == SyncStatus.SUCCESS
        assert SyncStatus.from_text("File SYNCED Successfully") == SyncStatus.SUCCESS
        assert SyncStatus.from_text("NOT FOUND") == SyncStatus.NOT_FOUND

    def test_from_text_invalid(self):
        """Test SyncStatus.from_text with invalid text."""
        with pytest.raises(ValueError):
            SyncStatus.from_text("unknown status")

    def test_is_success(self):
        """Test is_success property."""
        assert SyncStatus.SUCCESS.is_success is True
        assert SyncStatus.SKIPPED.is_success is False
        assert SyncStatus.ERROR.is_success is False

    def test_is_error(self):
        """Test is_error property."""
        assert SyncStatus.ERROR.is_error is True
        assert SyncStatus.LOCAL_CHANGES.is_error is True
        assert SyncStatus.NOT_FOUND.is_error is True
        assert SyncStatus.SUCCESS.is_error is False
        assert SyncStatus.SKIPPED.is_error is False

    def test_is_actionable(self):
        """Test is_actionable property."""
        assert SyncStatus.LOCAL_CHANGES.is_actionable is True
        assert SyncStatus.SUCCESS.is_actionable is False
        assert SyncStatus.ERROR.is_actionable is False

    def test_to_colored_string(self):
        """Test to_colored_string method."""
        # Test that it returns strings with ANSI codes
        success_str = SyncStatus.SUCCESS.to_colored_string()
        assert "[OK] SUCCESS" in success_str
        assert "\033[92m" in success_str  # Green color

        error_str = SyncStatus.ERROR.to_colored_string()
        assert "[ERROR] ERROR" in error_str
        assert "\033[91m" in error_str  # Red color

        skip_str = SyncStatus.SKIPPED.to_colored_string()
        assert "[SKIP] SKIPPED" in skip_str
        assert "\033[93m" in skip_str  # Yellow color


class TestSyncResult:
    """Test the SyncResult dataclass."""

    def test_sync_result_creation(self):
        """Test SyncResult creation."""
        file_sync = FileSync(source="file.py", destination="dest/file.py")
        result = SyncResult(
            file_sync=file_sync,
            remote_name="origin",
            status=SyncStatus.SUCCESS,
            message="File synced",
            local_hash="abc123",
            remote_hash="def456",
            files_processed=1,
        )

        assert result.file_sync == file_sync
        assert result.remote_name == "origin"
        assert result.status == SyncStatus.SUCCESS
        assert result.message == "File synced"
        assert result.local_hash == "abc123"
        assert result.remote_hash == "def456"
        assert result.objects_synced == 1

    def test_sync_result_defaults(self):
        """Test SyncResult with default values."""
        file_sync = FileSync(source="file.py", destination="dest/file.py")
        result = SyncResult(
            file_sync=file_sync,
            remote_name="origin",
            status=SyncStatus.SUCCESS,
            message="File synced",
        )

        assert result.local_hash is None
        assert result.remote_hash is None
        assert result.objects_synced == 1


class TestFileSyncer:
    """Test the FileSyncer class."""

    @pytest.fixture
    def file_syncer(self, sample_config):
        """Create a FileSyncer instance for testing."""
        mock_git_manager = Mock()
        return FileSyncer(sample_config, mock_git_manager)

    def test_file_syncer_init(self, file_syncer, sample_config):
        """Test FileSyncer initialization."""
        assert file_syncer.config == sample_config
        assert file_syncer.git_manager is not None

    @patch("git_crossref.sync.get_git_root")
    def test_sync_file_remote_not_found(self, mock_get_git_root, file_syncer, temp_dir):
        """Test sync_file with remote not in configuration."""
        mock_get_git_root.return_value = temp_dir
        file_sync = FileSync(source="file.py", destination="dest/file.py")

        result = file_syncer.sync_file("nonexistent", file_sync)
        assert result.status == SyncStatus.ERROR
        assert "not found in configuration" in result.message

    @patch("git_crossref.sync.get_git_root")
    def test_check_file_remote_not_found(self, mock_get_git_root, file_syncer, temp_dir):
        """Test check_file with remote not in configuration."""
        mock_get_git_root.return_value = temp_dir
        file_sync = FileSync(source="file.py", destination="dest/file.py")

        result = file_syncer.check_file("nonexistent", file_sync)
        assert result.status == SyncStatus.ERROR
        assert "not found in configuration" in result.message


class TestGitSyncOrchestrator:
    """Test the GitSyncOrchestrator class."""

    @pytest.fixture
    def orchestrator(self, sample_config):
        """Create a GitSyncOrchestrator instance for testing."""
        with patch("git_crossref.sync.GitSyncManager") as mock_manager:
            with patch("git_crossref.sync.FileSyncer") as mock_syncer:
                return GitSyncOrchestrator(sample_config)

    def test_orchestrator_init(self, orchestrator, sample_config):
        """Test GitSyncOrchestrator initialization."""
        assert orchestrator.config == sample_config

    def test_sync_all_no_filter(self, orchestrator):
        """Test sync_all without remote filter."""
        mock_result = SyncResult(
            file_sync=FileSync("file.py", "dest.py"),
            remote_name="origin",
            status=SyncStatus.SUCCESS,
            message="Synced",
        )
        orchestrator.syncer.sync_file.return_value = mock_result

        results = orchestrator.sync_all()
        # Should call sync_file for each file in config
        assert len(results) == 3  # 2 from upstream + 1 from fork
        assert all(r.status == SyncStatus.SUCCESS for r in results)

    def test_sync_all_with_filter(self, orchestrator):
        """Test sync_all with remote filter."""
        mock_result = SyncResult(
            file_sync=FileSync("file.py", "dest.py"),
            remote_name="upstream",
            status=SyncStatus.SUCCESS,
            message="Synced",
        )
        orchestrator.syncer.sync_file.return_value = mock_result

        results = orchestrator.sync_all(remote_filter="upstream")
        # Should only sync files from upstream remote
        assert len(results) == 2  # Only upstream files
        assert all(r.status == SyncStatus.SUCCESS for r in results)

    def test_sync_files_pattern_matching(self, orchestrator):
        """Test sync_files with pattern matching."""
        mock_result = SyncResult(
            file_sync=FileSync("utils.py", "lib/utils.py"),
            remote_name="upstream",
            status=SyncStatus.SUCCESS,
            message="Synced",
        )
        orchestrator.syncer.sync_file.return_value = mock_result

        results = orchestrator.sync_files(["utils"])
        # Should match files containing "utils"
        assert len(results) == 1
        assert results[0].status == SyncStatus.SUCCESS

    def test_check_all(self, orchestrator):
        """Test check_all method."""
        mock_result = SyncResult(
            file_sync=FileSync("file.py", "dest.py"),
            remote_name="origin",
            status=SyncStatus.SUCCESS,
            message="Up to date",
        )
        orchestrator.syncer.check_file.return_value = mock_result

        results = orchestrator.check_all()
        assert len(results) == 3
        assert all(r.status == SyncStatus.SUCCESS for r in results)

    def test_cleanup(self, orchestrator):
        """Test cleanup method."""
        orchestrator.cleanup()
        orchestrator.git_manager.cleanup_cache.assert_called_once()


class TestFormatSyncResults:
    """Test the format_sync_results function."""

    def test_format_empty_results(self):
        """Test formatting empty results."""
        output = format_sync_results([])
        assert "No files to sync" in output

    def test_format_success_results(self):
        """Test formatting successful results."""
        results = [
            SyncResult(
                file_sync=FileSync("file1.py", "dest1.py"),
                remote_name="origin",
                status=SyncStatus.SUCCESS,
                message="Synced successfully",
            ),
            SyncResult(
                file_sync=FileSync("file2.py", "dest2.py"),
                remote_name="origin",
                status=SyncStatus.SUCCESS,
                message="Already up to date",
            ),
        ]

        output = format_sync_results(results)
        assert "[OK] SUCCESS" in output
        assert "origin:file1.py -> dest1.py" in output
        assert "origin:file2.py -> dest2.py" in output
        assert "2 files" in output

    def test_format_mixed_results(self):
        """Test formatting mixed status results."""
        results = [
            SyncResult(
                file_sync=FileSync("good.py", "dest1.py"),
                remote_name="origin",
                status=SyncStatus.SUCCESS,
                message="Synced",
            ),
            SyncResult(
                file_sync=FileSync("bad.py", "dest2.py"),
                remote_name="origin",
                status=SyncStatus.ERROR,
                message="Failed",
            ),
            SyncResult(
                file_sync=FileSync("skip.py", "dest3.py"),
                remote_name="origin",
                status=SyncStatus.SKIPPED,
                message="Skipped",
            ),
        ]

        output = format_sync_results(results)
        assert "[OK] SUCCESS" in output
        assert "[ERROR] ERROR" in output
        assert "[SKIP] SKIPPED" in output

    def test_format_verbose_output(self):
        """Test formatting with verbose flag."""
        results = [
            SyncResult(
                file_sync=FileSync("file.py", "dest.py"),
                remote_name="origin",
                status=SyncStatus.SUCCESS,
                message="Synced",
                local_hash="abc123",
                remote_hash="def456",
            )
        ]

        output = format_sync_results(results, verbose=True)
        assert "abc123" in output
        assert "def456" in output
        assert "local:" in output
        assert "remote:" in output

    def test_format_dry_run_output(self):
        """Test formatting with dry-run flag."""
        results = [
            SyncResult(
                file_sync=FileSync("file.py", "dest.py"),
                remote_name="origin",
                status=SyncStatus.SUCCESS,
                message="Would sync",
            ),
            SyncResult(
                file_sync=FileSync("changed.py", "dest2.py"),
                remote_name="origin",
                status=SyncStatus.LOCAL_CHANGES,
                message="Has local changes",
            ),
        ]

        output = format_sync_results(results, dry_run=True)
        assert "would sync" in output
        assert "would skip (local changes)" in output
