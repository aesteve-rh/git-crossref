"""Tests for the schema module."""

import json
from unittest.mock import mock_open, patch

import pytest
import yaml

from git_crossref.exceptions import InvalidConfigurationError, ValidationError
from git_crossref.schema import (
    get_schema,
    get_schema_path,
    validate_config_data,
    validate_config_file,
)


class TestGetSchema:
    """Test the get_schema function."""

    def test_get_schema_from_file(self, temp_dir):
        """Test loading schema from file."""
        schema_file = temp_dir / "gitsyncfiles-schema.json"
        test_schema = {"type": "object", "properties": {"test": {"type": "string"}}}
        schema_file.write_text(json.dumps(test_schema))

        with patch("git_crossref.schema.get_schema_path") as mock_get_path:
            mock_get_path.return_value = schema_file
            schema = get_schema()
            assert schema == test_schema

    def test_get_schema_embedded(self):
        """Test loading embedded schema when file doesn't exist."""
        with patch("git_crossref.schema.get_schema_path") as mock_get_path:
            mock_get_path.return_value = None
            schema = get_schema()
            assert isinstance(schema, dict)
            assert "type" in schema
            assert schema["type"] == "object"

    def test_get_schema_file_invalid_json(self, temp_dir):
        """Test handling invalid JSON in schema file."""
        schema_file = temp_dir / "gitsyncfiles-schema.json"
        schema_file.write_text("invalid json {")

        with patch("git_crossref.schema.get_schema_path") as mock_get_path:
            mock_get_path.return_value = schema_file
            # Should fall back to embedded schema
            schema = get_schema()
            assert isinstance(schema, dict)
            assert schema["type"] == "object"


class TestGetSchemaPath:
    """Test the get_schema_path function."""

    def test_get_schema_path_exists(self, temp_dir):
        """Test when schema file exists."""
        schema_file = temp_dir / "gitsyncfiles-schema.json"
        schema_file.write_text("{}")

        with patch("git_crossref.config.get_git_root") as mock_get_root:
            mock_get_root.return_value = temp_dir
            path = get_schema_path()
            assert path == schema_file

    def test_get_schema_path_not_exists(self, temp_dir):
        """Test when schema file doesn't exist."""
        with patch("git_crossref.config.get_git_root") as mock_get_root:
            mock_get_root.return_value = temp_dir
            path = get_schema_path()
            assert path is None


class TestValidateConfigData:
    """Test the validate_config_data function."""

    def test_validate_valid_config(self):
        """Test validation of valid config data."""
        valid_config = {
            "remotes": {
                "origin": {"url": "https://github.com/example/repo.git", "version": "main"}
            },
            "files": {"origin": [{"source": "file.py", "destination": "dest/file.py"}]},
        }

        # Should not raise exception
        result = validate_config_data(valid_config)
        assert result == valid_config

    def test_validate_invalid_config_structure(self):
        """Test validation with invalid structure."""
        invalid_config = {"remotes": "not an object", "files": []}

        with pytest.raises(ValidationError):
            validate_config_data(invalid_config)

    def test_validate_missing_required_fields(self):
        """Test validation with missing required fields."""
        invalid_config = {
            "remotes": {
                "origin": {
                    # Missing required 'url' field
                    "version": "main"
                }
            },
            "files": {},
        }

        with pytest.raises(ValidationError):
            validate_config_data(invalid_config)

    def test_validate_invalid_remote_reference(self):
        """Test validation with invalid remote reference in files."""
        invalid_config = {
            "remotes": {"origin": {"url": "https://github.com/example/repo.git"}},
            "files": {
                "nonexistent": [  # References non-existent remote
                    {"source": "file.py", "destination": "dest/file.py"}
                ]
            },
        }

        with pytest.raises(ValidationError):
            validate_config_data(invalid_config)

    def test_validate_duplicate_destinations(self):
        """Test validation with duplicate destination paths."""
        invalid_config = {
            "remotes": {"origin": {"url": "https://github.com/example/repo.git"}},
            "files": {
                "origin": [
                    {"source": "file1.py", "destination": "dest/file.py"},
                    {"source": "file2.py", "destination": "dest/file.py"},  # Duplicate destination
                ]
            },
        }

        with pytest.raises(ValidationError):
            validate_config_data(invalid_config)

    def test_validate_config_with_optional_fields(self):
        """Test validation with all optional fields."""
        valid_config = {
            "remotes": {
                "origin": {
                    "url": "https://github.com/example/repo.git",
                    "base_path": "src",
                    "version": "develop",
                }
            },
            "files": {
                "origin": [
                    {
                        "source": "file.py",
                        "destination": "dest/file.py",
                        "hash": "abc123def456",
                        "ignore_changes": True,
                    }
                ]
            },
        }

        # Should not raise exception
        result = validate_config_data(valid_config)
        assert result == valid_config


class TestValidateConfigFile:
    """Test the validate_config_file function."""

    def test_validate_config_file_success(self, temp_dir):
        """Test successful validation of config file."""
        config_data = {
            "remotes": {"origin": {"url": "https://github.com/example/repo.git"}},
            "files": {"origin": [{"source": "file.py", "destination": "dest/file.py"}]},
        }

        config_file = temp_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Should not raise exception
        result = validate_config_file(str(config_file))
        assert result == config_data

    def test_validate_config_file_not_found(self):
        """Test validation with non-existent file."""
        with pytest.raises(InvalidConfigurationError):
            validate_config_file("nonexistent.yaml")

    def test_validate_config_file_invalid_yaml(self, temp_dir):
        """Test validation with invalid YAML file."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("invalid: yaml: content: [")

        with pytest.raises(InvalidConfigurationError):
            validate_config_file(str(config_file))

    def test_validate_config_file_schema_error(self, temp_dir):
        """Test validation with schema validation error."""
        invalid_config = {"remotes": "not an object", "files": []}

        config_file = temp_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(invalid_config, f)

        with pytest.raises(ValidationError):
            validate_config_file(str(config_file))

    def test_validate_config_file_permission_error(self, temp_dir):
        """Test validation with file permission error."""
        config_file = temp_dir / "config.yaml"
        config_file.write_text("test: content")

        with patch("builtins.open", mock_open()) as mock_file:
            mock_file.side_effect = PermissionError("Permission denied")

            with pytest.raises(InvalidConfigurationError):
                validate_config_file(str(config_file))


class TestSchemaValidationDetails:
    """Test specific schema validation rules."""

    def test_url_format_validation(self):
        """Test URL format validation."""
        valid_urls = [
            "https://github.com/user/repo.git",
            "git@github.com:user/repo.git",
            "https://gitlab.com/user/repo.git",
            "ssh://git@example.com/user/repo.git",
        ]

        for url in valid_urls:
            config = {
                "remotes": {"origin": {"url": url}},
                "files": {"origin": [{"source": "file.py", "destination": "dest/file.py"}]},
            }
            # Should not raise exception
            validate_config_data(config)

    def test_source_destination_patterns(self):
        """Test source and destination path patterns."""
        valid_patterns = [
            ("file.py", "dest/file.py"),
            ("dir/", "target/"),
            ("../config.yaml", "config/settings.yaml"),
            ("templates/", "project-templates/"),
        ]

        for source, dest in valid_patterns:
            config = {
                "remotes": {"origin": {"url": "https://github.com/user/repo.git"}},
                "files": {"origin": [{"source": source, "destination": dest}]},
            }
            # Should not raise exception
            validate_config_data(config)

    def test_version_patterns(self):
        """Test version/hash patterns."""
        valid_versions = ["main", "develop", "v1.0.0", "abc123def456", "feature/new-feature"]

        for version in valid_versions:
            config = {
                "remotes": {
                    "origin": {"url": "https://github.com/user/repo.git", "version": version}
                },
                "files": {"origin": [{"source": "file.py", "destination": "dest/file.py"}]},
            }
            # Should not raise exception
            validate_config_data(config)
