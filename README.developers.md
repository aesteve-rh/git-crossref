# Developer Guide for git-crossref

This guide provides instructions for developers who want to contribute to or publish the `git-crossref` library.

## Table of Contents

- [Development Setup](#development-setup)
- [Testing](#testing)
- [Publishing to PyPI](#publishing-to-pypi)
- [Release Process](#release-process)
- [Development Workflow](#development-workflow)
- [Code Quality](#code-quality)

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

3. Install project and dependencies:

   ```bash
   pip install -e .
   ```

4. Verify the installation:

   ```bash
   git-crossref --help
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

1. Update version in `pyproject.toml`:

   ```toml
   [project]
   name = "git-crossref"
   version = "0.2.0"  # Increment version
   ```

2. Update changelog and document changes in a `CHANGELOG.md` file

3. Run tests and ensure they all pass:

   ```bash
   pytest
   tox
   ```

4. Add new annotated tag, e.g., `vX.Y.Z`

   ```bash
   git tag -a -m "Release X.Y.Z" vX.Y.Z
   ```

5. Push the tag

   ```bash
   git push --tags upstream vX.Y.Z
   ```

6. Create a new release in github for the new tag.

#### 2. Publish on TestPyPI

1. Clean the source tree:

   ```bash
   make clean
   ```

2. Install and update pip, build, and twine if needed

   ```bash
   pip install --upgrade pip build twine
   ```

3. Build the release:

   ```bash
   python -m build
   ```

4. Upload to the package to pypi:

   ```bash
   python -m twine upload dist/*
   ```

   Check the project page to make sure everything looks good:
   https://pypi.org/project/git-crossref/

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
- [ ] Create Git tag: `git tag v0.2.0`
- [ ] Push tag: `git push origin v0.2.0`
- [ ] Upload to production PyPI
- [ ] Create GitHub release with release notes
- [ ] Announce release (if applicable)

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
4. Install the package with development dependencies: `pip install -e .`

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

### Code Standards

- **Python 3.11+**: Use modern Python features
- **Type hints**: All public functions should have type annotations
- **Docstrings**: Use Google-style docstrings for all public functions
- **Error handling**: Use custom exceptions with informative messages
- **Testing**: Maintain >80% test coverage
- **Formatting**: Black for code formatting, isort for import sorting

### Getting Help

- Check existing issues on GitHub
- Create new issues with detailed error messages
- Include Python version, OS, and package versions in bug reports
