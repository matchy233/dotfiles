---
name: python
description: Default Python conventions for tooling (uv, ruff, pixi), type annotations, string formatting, project config, and The Zen of Python. Use when writing Python code in any project. Existing project conventions always take priority over these defaults.
---

# Python Project Conventions

These are default conventions. **Always honor existing project conventions first** — if the project already has a style guide, linter config, `Makefile`, `setup.py`, or established patterns, follow those. Apply these defaults only where the project has no existing opinion.

## The Zen of Python

Internalize and follow PEP 20. In particular:

- Explicit is better than implicit — no magic, no hidden state.
- Simple is better than complex — choose the straightforward approach.
- Flat is better than nested — avoid deep nesting; extract early returns.
- Readability counts — code is read far more than written.
- Errors should never pass silently — don't bare `except:`.
- There should be one obvious way to do it — pick one pattern per problem and stay consistent.
- If the implementation is hard to explain, it's a bad idea.

## Type Annotations

Always use `typing` module types, never bare generics:

```python
# Yes
from typing import Dict, List, Optional, Tuple, Set

def process(items: List[str]) -> Dict[str, int]: ...

# No
def process(items: list[str]) -> dict[str, int]: ...
```

## String Formatting

Always use f-strings. Never `%` formatting or `.format()`:

```python
# Yes
msg = f"Found {count} items in {path}"

# No
msg = "Found {} items in {}".format(count, path)
msg = "Found %d items in %s" % (count, path)
```

## Formatter & Linter

Always use **ruff** for formatting and linting. If not already installed, install it:

```bash
uv tool install ruff    # preferred
# or: pip install ruff
```

Configure in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

Run `ruff format` and `ruff check --fix` before committing.

## Package & Python Version Management

Use **uv** as the default package manager and Python version manager:

```bash
uv init                  # new project
uv add <package>         # add dependency
uv run <script.py>       # run with managed env
uv python install 3.12   # install Python version
```

Never use raw `pip install` in projects. Never use `setup.py` — always `pyproject.toml`.

## Scientific / Bioinformatics Projects

When a project needs conda-forge or bioconda packages (bioinformatics tools, R,
compiled libraries), use **pixi** for its environments. Never use conda, mamba
or miniforge.

```bash
pixi init --channel conda-forge --channel bioconda   # creates pixi.toml
pixi add python=3.12 samtools minimap2               # conda packages
pixi add --pypi some-package                         # PyPI packages
pixi run python script.py                            # run inside the environment
```

- Commit `pixi.toml` and `pixi.lock`; the lock file is what makes a run
  reproducible.
- Tools with conflicting requirements go in separate named environments
  (`[feature.<name>]` plus `[environments]`), run with `pixi run -e <name> ...`.
- Pure-Python projects without conda packages keep using uv.

## Project Structure

First decide what the project is.

### Scripting and data analysis: no package

Scientific computing, bioinformatics and other analysis work produces results,
not importable software. Do not organize it as a package (no `src/`, no
package directory, no `[build-system]`).

```
project/
├── pixi.toml / pixi.lock   # or uv, if no conda packages are needed
├── Snakefile               # when the steps form a pipeline
├── scripts/
│   ├── build_templates.py  # one step per script
│   ├── simulate.py
│   └── common.py           # small shared helpers, imported directly
├── config/
└── tests/
```

- Each script does one step and runs on its own: inputs and outputs are
  `argparse` arguments, no hard-coded paths, code under
  `if __name__ == "__main__":`.
- A workflow (Snakemake) calls the scripts and records the run order.
- Tool config (ruff, pytest) goes in `ruff.toml` / `pytest.ini`, or in a
  `pyproject.toml` that holds only `[tool.*]` tables. Tests import scripts via
  pytest's `pythonpath = ["scripts"]`.

### Software meant to be installed or imported: package at the root

Use the flat layout, with the package directory at the project root. Do not
use a `src/` directory.

```
project/
├── pyproject.toml       # project metadata, dependencies, tool config
├── package_name/
│   ├── __init__.py
│   └── ...
├── tests/
│   └── ...
└── .python-version      # pin Python version (managed by uv)
```

## pyproject.toml Template (software projects)

```toml
[project]
name = "project-name"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```
