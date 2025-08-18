"""Configuration schema validation for git-crossref."""

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from .exceptions import InvalidConfigurationError, ValidationError


def get_schema() -> dict[str, Any]:
    """Load the JSON schema for configuration validation.

    Returns:
        The JSON schema as a dictionary

    Raises:
        RuntimeError: If the schema file cannot be found or loaded
    """
    # Try to find the schema file using get_schema_path
    schema_path = get_schema_path()

    if schema_path is not None:
        try:
            with open(schema_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # Fall back to embedded schema if file is invalid
            pass

    # If no external schema file found, use embedded schema
    return get_embedded_schema()


def get_embedded_schema() -> dict[str, Any]:
    """Get an embedded JSON schema when external file is not available.

    Returns:
        The embedded JSON schema as a dictionary
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Git Sync Files Configuration",
        "type": "object",
        "required": ["remotes", "files"],
        "properties": {
            "remotes": {
                "type": "object",
                "minProperties": 1,
                "patternProperties": {
                    "^[a-zA-Z0-9_-]+$": {
                        "type": "object",
                        "required": ["url"],
                        "properties": {
                            "url": {
                                "type": "string",
                                "minLength": 1,
                                "pattern": "^(https?://|git://|ssh://|git@[^:]+:).+",
                            },
                            "base_path": {
                                "type": "string",
                                "pattern": "^[^/].*$",
                                "description": "Base path within the repository (trailing slashes are normalized)",
                            },
                            "version": {
                                "type": "string",
                                "minLength": 1,
                                "default": "main",
                            },
                        },
                        "additionalProperties": False,
                    }
                },
                "additionalProperties": False,
            },
            "files": {
                "type": "object",
                "minProperties": 1,
                "patternProperties": {
                    "^[a-zA-Z0-9_-]+$": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["source", "destination"],
                            "properties": {
                                "source": {"type": "string", "minLength": 1},
                                "destination": {"type": "string", "minLength": 1},
                                "hash": {
                                    "type": "string",
                                    "minLength": 7,
                                    "pattern": "^[a-fA-F0-9]{7,64}$|^[a-zA-Z0-9_./-]+$",
                                },
                                "ignore_changes": {"type": "boolean", "default": False},
                                "include_subdirs": {"type": "boolean", "default": False},
                                "transform": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "pattern": "^s/.+/.*/[gimx]*$",
                                    },
                                },
                                "exclude": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "minLength": 1,
                                    },
                                },
                            },
                            "additionalProperties": False,
                        },
                    }
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }


def validate_config_data(data: dict[str, Any]) -> dict[str, Any]:
    """Validate configuration data against the JSON schema.

    Args:
        data: The configuration data loaded from YAML

    Returns:
        The validated configuration data (unchanged if valid)

    Raises:
        ValidationError: If the configuration is invalid
    """
    try:
        schema = get_schema()
        jsonschema.validate(data, schema)

        # Additional validation for remote references
        _validate_remote_references(data)

        # Additional validation for duplicate destinations
        _validate_unique_destinations(data)

        return data

    except jsonschema.ValidationError as e:
        # Format the error message to be more user-friendly
        error_path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        raise ValidationError(
            f"Configuration validation failed at '{error_path}': {e.message}"
        ) from e
    except jsonschema.SchemaError as e:
        raise ValidationError(f"Schema definition error: {e.message}") from e


def _validate_remote_references(data: dict[str, Any]) -> None:
    """Validate that all file sync rules reference existing remotes.

    Args:
        data: The configuration data

    Raises:
        ValidationError: If file sync rules reference non-existent remotes
    """
    remote_names = set(data.get("remotes", {}).keys())
    file_remote_names = set(data.get("files", {}).keys())

    missing_remotes = file_remote_names - remote_names
    if missing_remotes:
        raise ValidationError(
            f"File sync rules reference non-existent remotes: {', '.join(sorted(missing_remotes))}"
        )


def _validate_unique_destinations(data: dict[str, Any]) -> None:
    """Validate that all destination paths are unique.

    Args:
        data: The configuration data

    Raises:
        ValidationError: If duplicate destination paths are found
    """
    all_destinations = []

    for _remote_name, file_list in data.get("files", {}).items():
        for file_sync in file_list:
            destination = file_sync.get("destination")
            if destination in all_destinations:
                raise ValidationError(f"Duplicate destination path: '{destination}'")
            all_destinations.append(destination)


def validate_config_file(config_path: str) -> dict[str, Any]:
    """Validate a configuration file against the JSON schema.

    Args:
        config_path: Path to the configuration file

    Returns:
        The validated configuration data

    Raises:
        ValidationError: If the configuration is invalid
        InvalidConfigurationError: If the file format is invalid
    """
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            raise InvalidConfigurationError(f"Configuration file not found: {config_path}")

        with open(config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise InvalidConfigurationError(
                "Configuration file must contain a YAML object", config_path
            )

        return validate_config_data(data)

    except yaml.YAMLError as e:
        raise InvalidConfigurationError(
            f"Invalid YAML in configuration file: {e}", config_path
        ) from e


def get_schema_path() -> Path | None:
    """Get the path to the JSON schema file if it exists.

    Returns:
        Path to the schema file, or None if not found
    """
    possible_paths = [
        Path(__file__).parent.parent.parent / "gitcrossref-schema.json",  # Project root
    ]

    for schema_path in possible_paths:
        if schema_path.exists():
            return schema_path

    return None
