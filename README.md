# git-crossref

A Git-based vendoring tool that lets you selectively sync specific files and directories from multiple remote repositories into your project. Think of it as a lightweight alternative to Git submodules, giving you fine-grained control over what gets included and when it gets updated.

## Why Use git-crossref?

Perfect for scenarios where you need to:

- Vendor specific files: pull only the files you need, not entire repositories
- Keep dependencies current: easily update to specific commits, tags, or branches
- Multiple sources: combine files from different repositories into your project
- Fast synchronization: hash-based change detection means only modified files are updated
- Team coordination: version-controlled configuration ensures everyone syncs the same files
- Safe updates: local change detection prevents accidental overwrites
- File transformations: apply text transformations during sync (e.g., import path updates)

## vs. Other Tools

| Tool | git-crossref | Git Submodules | npm/pip packages |
|------|-------------|----------------|------------------|
| **Granularity** | Individual files/dirs | Entire repositories | Entire packages |
| **Updates** | On-demand, per file | Manual submodule update | Version-based |
| **Transformations** | ✅ Built-in | ❌ Manual | ❌ Post-install scripts |
| **Multi-source** | ✅ Multiple remotes | ✅ Multiple submodules | ✅ Multiple registries |
| **Local changes** | ✅ Protected | ⚠️ Conflicts | ❌ Overwritten |
| **Performance** | ⚡ Hash-based | 🐌 Full checkout | ⚡ Registry-based |

Perfect for when you need more control than submodules but don't want full package overhead.

## Installation

You can install git-crossref using pip:

    pip install git-crossref

Alternatively, clone the repository and install manually:

    git clone https://github.com/yourusername/git-crossref.git
    cd git-crossref
    pip install .

## Quick Start

1. Initialize a configuration file:
   ```bash
   git-crossref init
   ```

2. Edit `.gitcrossref` to configure your remotes and files

3. Sync files:
   ```bash
   git-crossref sync
   ```

## Configuration

The tool uses a YAML configuration file located at `.gitcrossref` in your repository root. Here's an example:

```yaml
remotes:
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
    
    # Glob pattern with exclusions
    - source: "scripts/*.py"
      destination: "tools/"
      include_subdirs: true
      exclude:
        - "*_test.py"       # Skip test files
        - "*.tmp"           # Skip temporary files

  another-source:
    # Script file
    - source: "deploy.sh"
      destination: "scripts/deploy.sh"
      # No hash provided, so it uses 'v1.2.3' from another-source
```

### Configuration Options

**Remotes:**

- `url`: Git URL of the remote repository
- `base_path`: Optional base path within the repository  
- `version`: Default branch/tag/commit for files from this remote

**Files:**

- `source`: Path to file or directory in the remote repository (relative to `base_path`)
- `destination`: Local path where content should be copied
- `hash`: Optional specific commit hash (overrides `version`)
- `ignore_changes`: If true, overwrites local files without checking for changes
- `include_subdirs`: If true, include subdirectories when copying directories objects
- `exclude`: List of glob patterns to exclude from syncing (applies to directories and glob patterns)
- `transform`: List of sed-like text transformations to apply during sync

**Git Object Types:**

- **Blob (file)**: `source: "utils.py"` - single file and/or glob patterns
- **Tree (directory)**: `source: "templates/"` - entire directory (note trailing slash)

## File Exclusion Patterns

When syncing directories or glob patterns, you can exclude specific files using the `exclude` option.
This is particularly useful for filtering out temporary files, test files, or other unwanted content.

### Basic Exclusion Syntax

```yaml
files:
  upstream:
    # Directory sync with exclusions
    - source: "src/"
      destination: "vendor/src/"
      exclude:
        - "*.tmp"           # Exclude all .tmp files
        - "test_*"          # Exclude files starting with "test_"
        - "__pycache__/*"   # Exclude everything in __pycache__ directories
    
    # Glob pattern with exclusions
    - source: "scripts/*.py"
      destination: "tools/"
      include_subdirs: true
      exclude:
        - "*_test.py"       # Exclude test files
        - "*.pyc"           # Exclude compiled Python files
```

### Exclusion Pattern Types

**Exact filename matching:**
```yaml
exclude:
  - "config.py"           # Excludes exactly "config.py"
  - "Dockerfile"          # Excludes exactly "Dockerfile"
  - ".gitignore"          # Excludes exactly ".gitignore"
```

**Wildcard patterns:**
```yaml
exclude:
  - "**/node_modules/**"  # Any node_modules directory anywhere
  - "*.log"               # All files ending with .log
  - "temp*"               # All files starting with "temp"
  - "*_backup.*"          # All backup files with any extension
  - "*.min.js"            # All minified JavaScript files
```

### Pattern Matching Rules

The exclusion patterns use Unix shell-style wildcards via Python's `fnmatch`:

- `*` matches any sequence of characters (except path separators)
- `?` matches any single character
- `[seq]` matches any character in seq (e.g., `[abc]` matches 'a', 'b', or 'c')
- `[!seq]` matches any character not in seq
- `**` matches across directory boundaries when used with `/`

## Commands

### Sync files
```bash
# Sync all configured files
git-crossref sync

# Sync only files from a specific remote
git-crossref sync --remote upstream

# Force sync (override local changes)
git-crossref sync --force

# Sync specific files by pattern
git-crossref sync libs/
```

### Check status
```bash
# Check status of all files
git-crossref status

# Check specific files
git-crossref check libs/utils.py

# Verbose output with hash information
git-crossref status --verbose
```

### Configuration management
```bash
# Initialize new configuration
git-crossref init

# Validate configuration
git-crossref validate

# Clean up cached repositories
git-crossref clean
```

## How it Works

git-crossref provides efficient, reliable vendoring through a Git-native approach:

1. **Smart caching**: bare clone remote repositories once and reuses them for all operations
2. **Precise targeting**: Extracts only the specific files/directories you need
3. **Hash-based detection**: Compares Git blob hashes to detect changes reliably
4. **Safe operations**: Checks for local modifications before overwriting files

This approach is both fast and reliable compared to timestamp-based synchronization tools.

## Use Cases

### Common Scenarios

**📁 Shared Configuration Files**
```yaml
# Sync common CI/build configs across projects
remotes:
  shared-configs:
    url: "https://github.com/company/shared-configs.git"
    version: "main"
files:
  shared-configs:
    - source: ".github/workflows/"
      destination: ".github/workflows/"
    - source: "Makefile"
      destination: "Makefile"
```

**🔧 Utility Libraries** 
```yaml
# Cherry-pick utility functions from larger codebases
remotes:
  utils:
    url: "https://github.com/company/utils.git"
    base_path: "src"
files:
  utils:
    - source: "database/helpers.py"
      destination: "lib/db_helpers.py"
    - source: "validation/*.py"
      destination: "lib/validators/"
```

**📦 Dependency Vendoring**
```yaml
# Vendor specific versions of dependencies
remotes:
  vendor:
    url: "https://github.com/external/library.git"
    version: "v2.1.0"  # Pin to specific version
files:
  vendor:
    - source: "src/core/"
      destination: "vendor/library/"
      ignore_changes: true  # Don't warn about local modifications
```

## Technical Details

### Implementation

For those interested in the technical implementation:

- **Bare repository caching**: Remote repositories are cloned to `.git/crossref-cache/` as bare repositories (Git objects only, no working directory)
- **Hash-based comparison**: Uses `git hash-object` to compare local and remote file blob hashes for reliable change detection
- **Git status integration**: Leverages `git status` to detect uncommitted local changes before sync operations

### Architecture

The tool is built around several key components:

- **Configuration layer**: YAML-based configuration with JSON schema validation
- **Git operations**: Efficient Git object manipulation using GitPython
- **Sync engines**: Specialized classes for different content types (files, directories, patterns)
- **Status tracking**: Rich status enumeration with success/failure categorization
- **Error handling**: Comprehensive exception system with actionable error messages

## Contributing

Contributions are welcome! Please see [README.developers.md](README.developers.md) for detailed development setup, code quality guidelines, and contribution workflow.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
