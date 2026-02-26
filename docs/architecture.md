# Architecture

How `flet-pkg` works internally.

## Overview

```
CLI (Typer) → Prompts (Rich) → Validators → Registry Check → Scaffolder (Jinja2) → Pipeline → Output
```

## Module structure

```
src/flet_pkg/
├── __init__.py              # Version and app name
├── __main__.py              # python -m flet_pkg support
├── main.py                  # Typer app, version callback
├── commands/
│   └── create.py            # Create command logic
├── core/
│   ├── analyzer.py          # PackageAnalyzer → GenerationPlan
│   ├── downloader.py        # PubDevDownloader (pub.dev cache)
│   ├── generators/          # Code generators (Python + Dart)
│   ├── models.py            # DartPackageAPI, GenerationPlan
│   ├── parser.py            # Dart API parser + detect_extension_type()
│   ├── pipeline.py          # GenerationPipeline orchestrator
│   ├── prompts.py           # Rich interactive prompts (ask, ask_confirm, ask_choice)
│   ├── registry_checker.py  # PyPI, GitHub, Flet SDK name conflict check
│   ├── scaffolder.py        # Jinja2 template engine
│   ├── type_map.py          # Dart → Python type mapping
│   └── validators.py        # Name validation + derivation
├── ui/
│   ├── console.py           # Rich console instance
│   ├── panels.py            # Header, info, error panels
│   └── tree.py              # Project tree display
└── templates/
    ├── service/             # Service extension template
    └── ui_control/          # UI Control extension template
```

## Key components

### Typer CLI (`main.py`)

The entry point registers the `create` command and a `--version` callback. Uses `rich_markup_mode="rich"` for styled help text.

### Create command (`commands/create.py`)

Orchestrates the creation flow:

1. Determines extension type (from flag or interactive prompt). If `auto`, downloads the Flutter package and calls `detect_extension_type()` to resolve it.
2. Collects Flutter package name, project name, package name, control class name
3. Calls `derive_names()` to auto-suggest names
4. Checks PyPI, GitHub, and Flet SDK monorepo for name conflicts via `registry_checker`
5. Builds a context dict and passes it to `Scaffolder`
6. Runs the analysis pipeline (download → parse → analyze → generate)
7. Displays the generated project tree

### Registry checker (`core/registry_checker.py`)

Checks for existing packages with the same name before scaffolding:

- **PyPI** — `GET https://pypi.org/pypi/{name}/json` (200 = exists)
- **Flet SDK** — checks `flet-dev/flet` monorepo at `sdk/python/packages/{name}` via GitHub Contents API
- **GitHub** — searches repositories matching the name (top 3 results)

All checks fail silently on network errors to avoid blocking the flow.

### Validators (`core/validators.py`)

- `validate_flutter_package()` — valid pub.dev name
- `validate_project_name()` — lowercase + hyphens
- `validate_package_name()` — valid Python identifier
- `validate_control_name()` — PascalCase
- `derive_names()` — strips Flutter affixes and derives all names from the Flutter package name

### Scaffolder (`core/scaffolder.py`)

Uses Jinja2 to render templates:

1. Walks the template directory tree
2. Resolves `{{variable}}` placeholders in directory and file names
3. Renders `.jinja` files through Jinja2 with the context dict
4. Copies non-Jinja files as-is

### Templates

Templates live under `src/flet_pkg/templates/`. Each template type has:

- `template.yaml` — template metadata
- A directory tree with `{{variable}}` placeholders in names
- `.jinja` suffix on files that need rendering

Variable substitution happens both in **file/directory names** and in **file contents** (for `.jinja` files).
