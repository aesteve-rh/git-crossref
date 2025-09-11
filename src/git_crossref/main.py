"""Main CLI interface for git-crossref."""

import sys

import click

from . import __version__
from .config import get_config, get_config_path
from .exceptions import (
    ConfigurationError,
    ConfigurationNotFoundError,
    GitSyncError,
    ValidationError,
)
from .logger import configure_logging, logger
from .schema import get_schema_path, validate_config_file
from .status import SyncStatus
from .sync import GitSyncOrchestrator, format_sync_results


def version_callback(ctx, param, value):
    """Callback to handle --version option."""
    if value:
        click.echo(__version__)
        ctx.exit()


SAMPLE_CONFIG = """remotes:
  upstream:
    url: "https://github.com/example/source-repo.git"
    base_path: "src/library"
    version: "main"  # All files from this remote default to 'main'

  another-source:
    url: "https://github.com/example/another-repo.git"
    base_path: "scripts"
    version: "v1.2.3"  # All files from this remote default to 'v1.2.3'

files:
  upstream:
    # Single file sync
    - source: "utils.py"
      destination: "libs/utils.py"
      # No hash provided, so it uses 'main' from upstream

    # File with specific commit
    - source: "config.yaml"
      destination: "config/defaults.yaml"
      hash: "abc123"  # Overrides 'main' with a specific commit

    # Directory tree sync
    - source: "templates/"
      destination: "project-templates/"
      # Syncs entire templates directory

    # Glob pattern sync (files matching a pattern)
    - source: "util/*.py"
      destination: "libs/python-utils/"
      # Syncs all Python files from util directory

    # File with text transformations
    - source: "config.template.py"
      destination: "config/settings.py"
      transform:
        - "s/DEBUG = True/DEBUG = False/g"
        - "s/localhost/production.example.com/g"
        - "s/__VERSION__/1.0.0/"

  another-source:
    # Script file
    - source: "deploy.sh"
      destination: "scripts/deploy.sh"
      # No hash provided, so it uses 'v1.2.3' from another-source

"""


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--version",
    is_flag=True,
    help="Show version and exit",
    is_eager=True,
    expose_value=False,
    callback=version_callback,
)
@click.help_option("-h")
@click.pass_context
def cli(ctx, verbose):
    """A Git plugin for syncing specific files from multiple repositories."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    # Configure logging based on verbose flag
    configure_logging(verbose=verbose)


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Force sync even if local files have changes")
@click.option("--remote", "-r", help="Sync only files from this remote")
@click.option(
    "--dry-run", "-n", is_flag=True, help="Show what would be synced without making changes"
)
@click.option("--stage", "-s", is_flag=True, help="Stage all synced files for commit after sync")
@click.argument("files", nargs=-1)
@click.pass_context
def sync(ctx, force, remote, dry_run, stage, files):
    """Sync files from remote repositories.

        If FILES are specified, only sync files matching those patterns.
    Otherwise, sync all configured files.

    Use --stage to automatically stage all synced files for commit.
    """
    verbose = ctx.obj.get("verbose", False)

    try:
        config = get_config()
        orchestrator = GitSyncOrchestrator(config)

        if dry_run:
            logger.info("DRY RUN: Showing what would be synced (no changes will be made)")
            # For dry-run, we check status instead of syncing
            if files:
                results = orchestrator.check_files(list(files))
            else:
                results = orchestrator.check_all(remote_filter=remote)
        else:
            if files:
                results = orchestrator.sync_files(list(files), force=force)
            else:
                results = orchestrator.sync_all(force=force, remote_filter=remote)

        output = format_sync_results(results, verbose=verbose, dry_run=dry_run)
        click.echo(output)

        # Stage files if requested and not in dry-run mode
        if stage and not dry_run:
            orchestrator.git_manager.stage_files(results)

        # Exit with error code if there were any errors
        errors = [
            r
            for r in results
            if r.status in (SyncStatus.ERROR, SyncStatus.LOCAL_CHANGES, SyncStatus.NEEDS_UPDATE)
        ]
        if errors and not force:
            sys.exit(1)

    except ConfigurationNotFoundError as e:
        logger.error("Configuration not found: %s", e.config_path)
        click.echo("Run 'git-crossref init' to create a configuration file.")
        sys.exit(1)
    except ConfigurationError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)
    except GitSyncError as e:
        logger.error("Sync error: %s", e)
        if e.details:
            for key, value in e.details.items():
                logger.error("  %s: %s", key, value)
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option("--remote", "-r", help="Check only files from this remote")
@click.argument("files", nargs=-1)
@click.pass_context
def check(ctx, remote, files):
    """Check the status of configured files without syncing.

    If FILES are specified, only check files matching those patterns.
    Otherwise, check all configured files.
    """
    verbose = ctx.obj.get("verbose", False)

    try:
        config = get_config()
        orchestrator = GitSyncOrchestrator(config)

        if files:
            results = orchestrator.check_files(list(files))
        else:
            results = orchestrator.check_all(remote_filter=remote)

        output = format_sync_results(results, verbose=verbose, dry_run=False)
        click.echo(output)

        # Exit with error code if there were any issues that need attention
        issues = [r for r in results if r.status not in (SyncStatus.SUCCESS, SyncStatus.SKIPPED)]
        if issues:
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx):
    """Show the status of all configured files."""
    verbose = ctx.obj.get("verbose", False)

    try:
        config = get_config()
        orchestrator = GitSyncOrchestrator(config)

        results = orchestrator.check_all()
        output = format_sync_results(results, verbose=verbose, dry_run=False)
        click.echo(output)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--clone", is_flag=True, help="Clone all remote repositories after checking/creating config"
)
@click.pass_context
def init(ctx, clone):
    """Initialize a new .gitcrossref configuration file."""
    configure_logging(verbose=ctx.obj.get("verbose", False))
    config_path = get_config_path()

    if config_path.exists():
        logger.warning("Configuration file already exists: %s", config_path)
    else:
        try:
            # Ensure we're creating in repository root, not .git directory
            config_path.parent.mkdir(exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(SAMPLE_CONFIG)

            logger.info("Created configuration file: %s", config_path)
            click.echo("Edit this file to configure your remotes and files.")
            click.echo(
                "Tip: Add this file to version control to share sync configuration with your team."
            )
        except PermissionError as e:
            logger.error("Permission denied creating configuration file: %s", e)
            sys.exit(1)
        except OSError as e:
            logger.error("Failed to create configuration file: %s", e)
            sys.exit(1)

    # Optionally clone repositories (works regardless of whether config was created or existed)
    if clone:
        try:
            logger.info("Cloning remote repositories...")
            config = get_config()
            orchestrator = GitSyncOrchestrator(config)

            # Initialize all repositories (this will clone them)
            for remote_name, remote in config.remotes.items():
                logger.info("Initializing repository: %s", remote_name)
                repo = orchestrator.git_manager.get_repository(remote_name, remote)
                # Access the repo property to trigger actual cloning
                _ = repo.repo

            logger.info("All remote repositories cloned successfully")
        except Exception as e:
            logger.error("Failed to clone repositories: %s", e)
            click.echo("You can clone them later using 'git-crossref clone' command.")


@cli.command()
@click.option("--remote", "-r", help="Clone only this specific remote")
@click.pass_context
def clone(ctx, remote):
    """Clone remote repositories for caching."""
    verbose = ctx.obj.get("verbose", False)
    configure_logging(verbose=verbose)

    try:
        config = get_config()
        orchestrator = GitSyncOrchestrator(config)

        if remote:
            if remote not in config.remotes:
                logger.error("Remote '%s' not found in configuration", remote)
                sys.exit(1)

            logger.info("Cloning remote repository: %s", remote)
            repo = orchestrator.git_manager.get_repository(remote, config.remotes[remote])
            # Access the repo property to trigger actual cloning
            _ = repo.repo
            logger.info("Successfully cloned %s", remote)
        else:
            logger.info("Cloning all remote repositories...")
            for remote_name, remote_config in config.remotes.items():
                logger.info("Cloning repository: %s", remote_name)
                repo = orchestrator.git_manager.get_repository(remote_name, remote_config)
                # Access the repo property to trigger actual cloning
                _ = repo.repo

            logger.info("All remote repositories cloned successfully")

    except ConfigurationNotFoundError as e:
        logger.error("Configuration not found: %s", e.config_path)
        click.echo("Run 'git-crossref init' to create a configuration file.")
        sys.exit(1)
    except Exception as e:
        logger.error("Failed to clone repositories: %s", e)
        sys.exit(1)


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate the configuration file with detailed schema checking."""
    try:
        # First validate schema
        config_path = get_config_path()
        validate_config_file(str(config_path))

        # Then load the config (this also validates)
        config = get_config()

        logger.info("Configuration file is valid")
        logger.info("Schema validation passed for %s", config_path)

        schema_path = get_schema_path()
        if schema_path:
            logger.info("Using schema: %s", schema_path)
        else:
            logger.info("Using embedded schema")

        verbose = ctx.obj.get("verbose", False)
        if verbose:
            click.echo("\n[SCHEMA] Configuration Summary:")
            click.echo(f"  Configuration file: {config_path}")
            click.echo(f"  Remotes: {len(config.remotes)}")
            click.echo(f"  Total sync rules: {sum(len(files) for files in config.files.values())}")

            click.echo("\n[REMOTES] Repository configurations:")
            for name, remote in config.remotes.items():
                click.echo(f"  ✓ {name}:")
                click.echo(f"    URL: {remote.url}")
                if remote.base_path:
                    click.echo(f"    Base path: {remote.base_path}")
                click.echo(f"    Default version: {remote.version}")

            click.echo("\n[FILES] Sync rules by remote:")
            for remote_name, file_list in config.files.items():
                click.echo(f"  ✓ {remote_name} ({len(file_list)} rules):")
                for file_sync in file_list:
                    version = file_sync.hash or config.remotes[remote_name].version
                    click.echo(
                        f"    {file_sync.sync_type}: {file_sync.source} -> "
                        f"{file_sync.destination} ({version})"
                    )
                    if file_sync.ignore_changes:
                        click.echo("      Ignores local changes")

    except ConfigurationNotFoundError as e:
        logger.error("Configuration file not found: %s", e.config_path)
        click.echo("Run 'git-crossref init' to create a configuration file.")
        sys.exit(1)
    except ValidationError as e:
        logger.error("Schema validation failed: %s", e)
        sys.exit(1)
    except ConfigurationError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        sys.exit(1)


@cli.command()
@click.pass_context
def clean(ctx):
    """Clean up cached repositories."""
    configure_logging(verbose=ctx.obj.get("verbose", False))
    try:
        config = get_config()
        orchestrator = GitSyncOrchestrator(config)
        orchestrator.cleanup()

    except Exception as e:
        logger.error("Failed to clean cache: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    cli()
