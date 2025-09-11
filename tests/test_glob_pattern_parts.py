"""Tests for GlobPatternParts dataclass."""

import pytest

from git_crossref.blob_syncer import GlobPatternParts


class TestGlobPatternParts:
    """Test the GlobPatternParts dataclass."""

    def test_init_with_pattern(self):
        """Test initialization with a valid pattern."""
        parts = GlobPatternParts(base_path="src/utils", pattern="*.py")
        assert parts.base_path == "src/utils"
        assert parts.pattern == "*.py"

    def test_init_without_pattern(self):
        """Test initialization without a pattern."""
        parts = GlobPatternParts(base_path="", pattern=None)
        assert parts.base_path == ""
        assert parts.pattern is None

    def test_is_valid_with_pattern(self):
        """Test is_valid returns True when pattern is not None."""
        parts = GlobPatternParts(base_path="src", pattern="*.py")
        assert parts.is_valid is True

    def test_is_valid_without_pattern(self):
        """Test is_valid returns False when pattern is None."""
        parts = GlobPatternParts(base_path="", pattern=None)
        assert parts.is_valid is False

    def test_has_wildcards_with_asterisk(self):
        """Test has_wildcards returns True for patterns with asterisk."""
        parts = GlobPatternParts(base_path="src", pattern="*.py")
        assert parts.has_wildcards is True

    def test_has_wildcards_with_question_mark(self):
        """Test has_wildcards returns True for patterns with question mark."""
        parts = GlobPatternParts(base_path="logs", pattern="log?.txt")
        assert parts.has_wildcards is True

    def test_has_wildcards_with_both_wildcards(self):
        """Test has_wildcards returns True for patterns with both wildcards."""
        parts = GlobPatternParts(base_path="", pattern="test*.?xt")
        assert parts.has_wildcards is True

    def test_has_wildcards_without_wildcards(self):
        """Test has_wildcards returns False for patterns without wildcards."""
        parts = GlobPatternParts(base_path="src", pattern="config.yaml")
        assert parts.has_wildcards is False

    def test_has_wildcards_with_none_pattern(self):
        """Test has_wildcards returns False when pattern is None."""
        parts = GlobPatternParts(base_path="", pattern=None)
        assert parts.has_wildcards is False

    @pytest.mark.parametrize(
        "base_path,pattern,expected_valid,expected_wildcards",
        [
            ("src/utils", "*.py", True, True),
            ("", "*.txt", True, True),
            ("docs", "**/*.md", True, True),
            ("scripts", "build*", True, True),
            ("logs", "log?.txt", True, True),
            ("config", "settings.yaml", True, False),
            ("", None, False, False),
            ("some/path", None, False, False),
        ],
    )
    def test_properties_parametrized(self, base_path, pattern, expected_valid, expected_wildcards):
        """Test all properties with various input combinations."""
        parts = GlobPatternParts(base_path=base_path, pattern=pattern)

        assert parts.base_path == base_path
        assert parts.pattern == pattern
        assert parts.is_valid == expected_valid
        assert parts.has_wildcards == expected_wildcards

    def test_string_representation(self):
        """Test string representation of GlobPatternParts."""
        parts = GlobPatternParts(base_path="src/utils", pattern="*.py")
        str_repr = str(parts)

        assert "GlobPatternParts" in str_repr
        assert "base_path='src/utils'" in str_repr
        assert "pattern='*.py'" in str_repr

    def test_equality(self):
        """Test equality comparison between GlobPatternParts instances."""
        parts1 = GlobPatternParts(base_path="src", pattern="*.py")
        parts2 = GlobPatternParts(base_path="src", pattern="*.py")
        parts3 = GlobPatternParts(base_path="lib", pattern="*.py")

        assert parts1 == parts2
        assert parts1 != parts3

    def test_complex_paths(self):
        """Test with complex path structures."""
        test_cases = [
            # (base_path, pattern, description)
            ("", "*.py", "Root level glob"),
            ("src", "**/*.py", "Recursive glob"),
            ("tests/unit/config", "test_*.py", "Specific directory with prefix glob"),
            ("assets/images/thumbnails", "thumb_*.{jpg,png}", "Complex glob with braces"),
        ]

        for base_path, pattern, description in test_cases:
            parts = GlobPatternParts(base_path=base_path, pattern=pattern)

            assert parts.base_path == base_path, f"Base path failed for: {description}"
            assert parts.pattern == pattern, f"Pattern failed for: {description}"
            assert parts.is_valid is True, f"Validity failed for: {description}"
            assert parts.has_wildcards is True, f"Wildcards failed for: {description}"
