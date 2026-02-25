# Architecture

How `flet-pkg` works internally.

## Overview

```
CLI (Typer) → Prompts (Rich) → Validators → Scaffolder (Jinja2) → Output
```

## Module structure

```
src/flet_pkg/
├── __init__.py          # Version and app name
├── __main__.py          # python -m flet_pkg support
├── main.py              # Typer app, version callback
├── commands/
│   └── create.py        # Create command logic
├── core/
│   ├── parser.py        # Dart API parser
│   ├── prompts.py       # Rich interactive prompts
│   ├── scaffolder.py    # Jinja2 template engine
│   └── validators.py    # Name validation + derivation
├── ui/
│   ├── console.py       # Rich console instance
│   ├── panels.py        # Header, info, error panels
│   └── tree.py          # Project tree display
└── templates/
    ├── service/         # Service extension template
    └── ui_control/      # UI Control extension template
```

## Key components

### Typer CLI (`main.py`)

The entry point registers the `create` command and a `--version` callback. Uses `rich_markup_mode="rich"` for styled help text.

### Create command (`commands/create.py`)

Orchestrates the creation flow:

1. Determines extension type (from flag or interactive prompt)
2. Collects Flutter package name, project name, package name, control class name
3. Calls `derive_names()` to auto-suggest names
4. Builds a context dict and passes it to `Scaffolder`
5. Displays the generated project tree

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
