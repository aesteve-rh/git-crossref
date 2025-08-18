# Developer Guide for git-crossref

This guide provides instructions for developers who want to contribute to or publish the `git-crossref` library.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Publishing to PyPI](#publishing-to-pypi)
- [Release Process](#release-process)
- [Development Workflow](#development-workflow)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- `pip` and `setuptools`

### Setting up the Development Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/aesteve-rh/git-crossref.git
   cd git-crossref
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Verify the installation:
   ```bash
   git-crossref --help
   ```

### Project Structure

```
git-crossref/
├── src/
│   └── git_crossref/           # Main package
│       ├── __init__.py
│       ├── main.py            # CLI entry point
│       ├── config.py          # Configuration handling
│       ├── sync.py            # Sync orchestration
│       ├── git_ops.py         # Git operations
│       ├── blob_syncer.py     # File synchronization
│       ├── tree_syncer.py     # Directory synchronization
│       ├── schema.py          # Configuration validation
│       ├── exceptions.py      # Custom exceptions
│       └── logger.py          # Logging configuration
├── tests/                     # Test suite
├── gitcrossref-schema.json    # Configuration schema
├── pyproject.toml            # Project configuration
├── README.md                 # User documentation
└── README.developers.md      # This file
```

### Architecture Details

The tool is built around several key components:

- **Configuration layer**: YAML-based configuration with JSON schema validation
- **Git operations**: Efficient Git object manipulation using GitPython
- **Sync engines**: Specialized classes for different content types (files, directories, patterns)
- **Status tracking**: Rich status enumeration with success/failure categorization
- **Error handling**: Comprehensive exception system with actionable error messages

#### Status System

The `SyncStatus` enum provides flexible status handling for programmatic usage:

```python
from git_crossref.sync import SyncStatus

# String enum - can be compared directly with strings
assert SyncStatus.SUCCESS == "success"

# Parse status from text with keywords
status = SyncStatus.from_text("file synced successfully")  # -> SUCCESS
status = SyncStatus.from_text("local changes detected")    # -> LOCAL_CHANGES

# Utility properties
status.is_success      # -> True/False
status.is_error        # -> True/False  
status.is_actionable   # -> True if fixable with --force

# Visual output
status.to_colored_string()  # -> colored terminal output with prefixes
```

## Testing

### Running Tests

Run the full test suite:
```bash
pytest
```

Run specific test files:
```bash
pytest tests/test_config.py
pytest tests/test_sync.py
```

Run tests with coverage:
```bash
pytest --cov=src/git_crossref --cov-report=html
```

### Test Types

- **Unit tests**: Test individual functions and classes
- **Integration tests**: Test component interactions
- **CLI tests**: Test command-line interface using `click.testing`

### Using Tox

Run tests across multiple Python versions:
```bash
tox
```

Run specific environments:
```bash
tox -e py311
tox -e test-fast
```

## Publishing to PyPI

### Prerequisites for Publishing

1. **PyPI Account**: Create accounts on both:
   - [TestPyPI](https://test.pypi.org/) (for testing)
   - [PyPI](https://pypi.org/) (for production)

2. **API Tokens**: Generate API tokens for both platforms:
   - Go to Account Settings → API tokens
   - Create tokens with appropriate scopes
   - Store them securely

3. **Install Build Tools**:
   ```bash
   pip install build twine
   ```

### Step-by-Step Publishing Process

#### 1. Prepare for Release

1. **Update Version**: Edit `pyproject.toml`:
   ```toml
   [project]
   name = "git-crossref"
   version = "0.2.0"  # Increment version
   ```

2. **Update Changelog**: Document changes in a `CHANGELOG.md` file

3. **Run Tests**: Ensure all tests pass:
   ```bash
   pytest
   tox
   ```

4. **Check Package Metadata**:
   ```bash
   python -m build --sdist --wheel
   twine check dist/*
   ```

#### 2. Test on TestPyPI

1. **Build the Package**:
   ```bash
   # Clean previous builds
   rm -rf dist/ build/ *.egg-info/
   
   # Build source distribution and wheel
   python -m build
   ```

2. **Upload to TestPyPI**:
   ```bash
   twine upload --repository testpypi dist/*
   ```

   When prompted, use:
   - Username: `__token__`
   - Password: Your TestPyPI API token

3. **Test Installation from TestPyPI**:
   ```bash
   # Create a fresh virtual environment
   python -m venv test-env
   source test-env/bin/activate
   
   # Install from TestPyPI
   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ git-crossref
   
   # Test the installation
   git-crossref --help
   ```

#### 3. Publish to Production PyPI

1. **Upload to PyPI**:
   ```bash
   twine upload dist/*
   ```

   Use your production PyPI API token when prompted.

2. **Verify Installation**:
   ```bash
   # Create a fresh virtual environment
   python -m venv verify-env
   source verify-env/bin/activate
   
   # Install from PyPI
   pip install git-crossref
   
   # Test the installation
   git-crossref --help
   ```

### Configuration Files for Automated Publishing

#### `.pypirc` Configuration

Create `~/.pypirc` for easier uploads:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-your-api-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-testpypi-token-here
```

#### Using Environment Variables

Alternatively, use environment variables:

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-your-api-token-here
export TWINE_REPOSITORY=pypi

# Then upload without prompts
twine upload dist/*
```

## Release Process

### Semantic Versioning

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Incompatible API changes
- **MINOR** (0.1.0): Backward-compatible functionality additions
- **PATCH** (0.0.1): Backward-compatible bug fixes

### Release Checklist

- [ ] All tests pass locally and in CI
- [ ] Version number updated in `pyproject.toml`
- [ ] CHANGELOG.md updated with new version
- [ ] Documentation updated if needed
- [ ] Build package and test on TestPyPI
- [ ] Create Git tag: `git tag v0.2.0`
- [ ] Push tag: `git push origin v0.2.0`
- [ ] Upload to production PyPI
- [ ] Create GitHub release with release notes
- [ ] Announce release (if applicable)

### Automated Release with GitHub Actions

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    - name: Build package
      run: python -m build
    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: twine upload dist/*
```

Store your PyPI API token in GitHub Secrets as `PYPI_API_TOKEN`.

## Development Workflow

### Code Style

The project uses:
- **Black** for code formatting
- **Pylint** for linting
- **Type hints** for better code documentation

Format code:
```bash
black src/ tests/
```

Run linting:
```bash
pylint src/git_crossref/
```

### Git Workflow

1. Create feature branches from `main`
2. Make changes and add tests
3. Ensure tests pass and code is formatted
4. Create pull request
5. Review and merge to `main`
6. Tag releases from `main`

### Adding New Features

1. Write tests first (TDD approach)
2. Implement the feature
3. Update documentation
4. Add configuration schema updates if needed
5. Update CHANGELOG.md

## Code Quality

This project uses several tools to maintain high code quality standards.

### Quick Setup for Contributors

If you just want to contribute quickly:

1. Clone the repository
2. Create a virtual environment: `python -m venv ~/.venv/git-crossref`
3. Activate the virtual environment: `source ~/.venv/git-crossref/bin/activate`
4. Install the package with development dependencies: `pip install -e ".[dev]"`

### Code Quality Tools

The project uses the following tools for code quality:

#### Using Tox (Recommended)

```bash
# Linting
tox -e lint          # Run ruff for linting

# Formatting  
tox -e format        # Check code formatting with black and isort
tox -e format-fix    # Auto-fix formatting issues

# Type checking
tox -e typecheck     # Run mypy for type checking

# All checks
tox -e all           # Run all quality checks at once
```

#### Using Makefile

Alternatively, you can use the provided Makefile for common tasks:

```bash
make install-dev     # Install with dev dependencies
make lint           # Run linting
make format         # Check formatting
make format-fix     # Fix formatting issues
make typecheck      # Run type checking
make all           # Run all quality checks
make clean         # Clean build artifacts
```

#### Manual Tool Usage

If you prefer to run tools directly:

```bash
# Linting
ruff check src/ tests/

# Formatting
black --check src/ tests/
isort --check src/ tests/

# Type checking
mypy src/git_crossref/

# Auto-formatting
black src/ tests/
isort src/ tests/
```

### Pre-commit Hooks

Install pre-commit hooks to ensure code quality before commits:

```bash
pip install pre-commit
pre-commit install
```

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.9.1
    hooks:
      - id: black
  - repo: https://github.com/pycqa/pylint
    rev: v3.0.1
    hooks:
      - id: pylint
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

### Code Standards

- **Python 3.11+**: Use modern Python features
- **Type hints**: All public functions should have type annotations
- **Docstrings**: Use Google-style docstrings for all public functions
- **Error handling**: Use custom exceptions with informative messages
- **Testing**: Maintain >80% test coverage
- **Formatting**: Black for code formatting, isort for import sorting

### Continuous Integration

The project should include CI/CD pipelines that:
- Run tests on multiple Python versions
- Check code formatting and linting
- Build and test package installation
- Automatically publish releases

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you've installed the package in development mode (`pip install -e .`)

2. **Test Failures**: 
   - Check if you're in the correct virtual environment
   - Ensure all dependencies are installed
   - Check Git repository state for integration tests

3. **Publishing Errors**:
   - Verify API tokens are correct
   - Check package name availability on PyPI
   - Ensure version number hasn't been used before

4. **Schema Validation**: 
   - Ensure `gitcrossref-schema.json` is included in package data
   - Check JSON schema syntax

### Getting Help

- Check existing issues on GitHub
- Create new issues with detailed error messages
- Include Python version, OS, and package versions in bug reports

## Contributing

We welcome contributions to git-crossref! Here's how to get started:

### Quick Contribution Workflow

1. **Fork the repository** on GitHub
2. **Create a feature branch** from main:
   ```bash
   git checkout -b feature-name
   ```
3. **Make your changes** and add tests
4. **Run quality checks**:
   ```bash
   make all  # or tox -e all
   ```
5. **Commit your changes** with a clear message:
   ```bash
   git commit -am 'Add feature: brief description'
   ```
6. **Push to your fork**:
   ```bash
   git push origin feature-name
   ```
7. **Open a pull request** on GitHub

### Contribution Guidelines

#### Before You Start
- Check existing issues and PRs to avoid duplication
- For major changes, open an issue first to discuss the approach
- Make sure you understand the project's architecture and goals

#### Code Requirements
- **Tests**: Add tests for new functionality (maintain >80% coverage)
- **Documentation**: Update docstrings and README if needed
- **Type hints**: Add type annotations to all new functions
- **Error handling**: Use custom exceptions for error conditions
- **Code style**: Follow existing patterns and run formatting tools

#### Pull Request Process
1. **Clear description**: Explain what the PR does and why
2. **Small focused changes**: Prefer multiple small PRs over large ones
3. **Tests pass**: Ensure all CI checks pass
4. **Schema updates**: Update JSON schema if adding configuration options
5. **Breaking changes**: Clearly document any breaking changes

#### Review Process
- PRs require review from maintainers
- Address feedback promptly and respectfully
- Squash commits if requested before merge
- Maintainers may ask for changes or additional tests

### Types of Contributions Welcome

- 🐛 **Bug fixes**: Fix existing issues or edge cases
- ✨ **New features**: Add functionality that fits the project goals
- 📚 **Documentation**: Improve README, docstrings, or examples
- 🧪 **Tests**: Add test coverage for untested code paths
- 🔧 **Developer experience**: Improve tooling, CI, or development workflow
- 🎨 **Code quality**: Refactoring, performance improvements, type safety

For major changes, please open an issue first to discuss the proposed changes.
