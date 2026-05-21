# Installing `aws-get-creds` as a Global Command (`awsc`)

This document describes how to install `aws-get-creds` so that it is available
system-wide as the `awsc` command.

---

## 1. Packaging Configuration

The repository already includes `pyproject.toml` and `aws_get_creds.py` which
together define the `awsc` console script entry point.

### `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "aws-get-creds"
version = "1.0.0"
description = "Fetches temporary AWS credentials and stores them in the global credentials file."
requires-python = ">=3.10"
dependencies = [
    "boto3==1.43.12",
]

[project.scripts]
awsc = "aws_get_creds:main"

[tool.setuptools]
py-modules = ["application", "exceptions", "aws_get_creds"]
```

> **Python ≥ 3.10 is required.** `boto3==1.43.12` dropped Python 3.9 support
> on 2026-04-29 and declares `requires-python = ">=3.10"`.

### `aws_get_creds.py` (entry-point shim)

Python module names cannot contain hyphens, so `aws_get_creds.py` acts as a
thin wrapper around the existing `application.py`.  It also prints the package
version on every invocation:

```python
from importlib.metadata import version, PackageNotFoundError
from application import Application
import sys

def main():
    try:
        v = version("aws-get-creds")
    except PackageNotFoundError:
        v = "unknown"

    print(f"aws-get-creds {v}")

    try:
        app = Application()
        app.run()
    except Exception as err:
        print(f"Error while fetching the credentials:\n\t{err}")
        sys.exit(1)
```

The entry point `awsc = "aws_get_creds:main"` tells pip/pipx to create a
wrapper script named `awsc` that calls `aws_get_creds.main()`.

---

## 2. Global Installation

### 2a. Editable install with `pip` (simplest)

```bash
# From the repository root
pip install -e .
```

`pip` reads `pyproject.toml` (or `setup.py`), installs `boto3`, and creates
the `awsc` wrapper in the active Python environment's `bin/` (or `Scripts/`
on Windows) directory.  Verify with:

```bash
awsc --help   # or just: awsc
which awsc    # Linux/macOS
where awsc    # Windows
```

> **Note:** Use a virtual environment or ensure the environment's `bin/`
> directory is on your `PATH`.

### 2b. Isolated install with `pipx` (recommended for CLI tools)

[pipx](https://pipx.pypa.io) installs each CLI tool into its own isolated
virtual environment while still exposing the command globally.

```bash
# Install pipx if not already present
pip install pipx
pipx ensurepath          # adds ~/.local/bin to PATH (restart shell after)

# Install aws-get-creds directly from GitHub (no local clone needed)
pipx install git+https://github.com/ktyl/aws-get-creds.git

# Or from a local clone
pipx install .
```

`pipx` automatically installs `boto3` and all other dependencies declared in
`pyproject.toml`.  To upgrade later (after new commits are pushed):

```bash
pipx reinstall aws-get-creds
```

---

## 3. Alternative Methods

Use these if you prefer not to rely on the packaging configuration.

### 3a. Symbolic link

```bash
# Linux / macOS — link the existing entry-point script to a directory on PATH
chmod +x /path/to/aws-get-creds/aws-get-creds.py
ln -s /path/to/aws-get-creds/aws-get-creds.py /usr/local/bin/awsc
```

> On Windows you can create a `.cmd` wrapper instead:
> ```bat
> @echo off
> python "C:\path\to\aws-get-creds\aws-get-creds.py" %*
> ```
> Save it as `awsc.cmd` in a folder that is already on your `%PATH%`.

Dependencies still need to be installed manually:

```bash
pip install -r /path/to/aws-get-creds/requirements.txt
```

### 3b. Shell alias (`.bashrc` / `.zshrc`)

Add the following line to `~/.bashrc` or `~/.zshrc`:

```bash
alias awsc='python /path/to/aws-get-creds/aws-get-creds.py'
```

Then reload your shell configuration:

```bash
source ~/.bashrc   # or source ~/.zshrc
```

Dependencies must be installed separately:

```bash
pip install -r /path/to/aws-get-creds/requirements.txt
```

> **Limitation:** Shell aliases are not available in non-interactive shells
> (e.g., cron jobs or scripts run with `sh`). Prefer the symlink or `pipx`
> approach for broader compatibility.

---

## Summary Comparison

| Method | Isolation | Auto-deps | Works in scripts | Effort |
|---|---|---|---|---|
| `pip install -e .` | No (uses active env) | Yes | Yes | Low |
| `pipx install .` | Yes (own venv) | Yes | Yes | Low |
| Symbolic link | No | Manual | Yes | Medium |
| Shell alias | No | Manual | No | Minimal |
