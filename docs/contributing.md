# Contributing

## Development setup

1. Clone the repository:

    ```bash
    git clone https://github.com/brunobrown/flet-pkg.git
    cd flet-pkg
    ```

2. Install dependencies with [uv](https://docs.astral.sh/uv/):

    ```bash
    uv sync --dev
    ```

3. Install docs dependencies (optional):

    ```bash
    uv sync --group docs
    ```

## Running tests

```bash
uv run pytest -v
```

With coverage:

```bash
uv run pytest -v --cov=flet_pkg --cov-report=term-missing
```

## Code quality

Format code:

```bash
uv run ruff format
```

Check linting:

```bash
uv run ruff check
```

Type checking:

```bash
uv run ty check
```

## Documentation

Serve docs locally:

```bash
uv run --group docs mkdocs serve
```

Build docs:

```bash
uv run --group docs mkdocs build --strict
```

## Project structure

See the [Architecture](architecture.md) page for details on how the codebase is organized.

## Pull requests

1. Create a feature branch from `main`
2. Make your changes
3. Ensure all checks pass (ruff format, ruff check, pytest)
4. Bump the version in `pyproject.toml` and `src/flet_pkg/__init__.py`
5. Open a PR against `main`
