# flet-pkg

CLI tool to scaffold Flet extension packages.

Generates complete, ready-to-develop Flet extensions with Python + Flutter/Dart code, following **Flet 0.80.x+** patterns.

## Features

- **Interactive & non-interactive modes** — guided prompts or full CLI flags
- **Two extension types** — Service (non-visual) and UI Control (visual widget)
- **Complete project scaffolding** — Python package, Flutter package, tests, docs, examples
- **Smart name derivation** — automatically derives project, package, and class names from the Flutter package name
- **Flet 0.80.x+ patterns** — uses `@ft.control`, `ft.Service`, `ft.LayoutControl`, `invoke_method`, and `EventHandler`

## Quick install

```bash
pip install flet-pkg
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install flet-pkg
```

## Quick start

```bash
flet-pkg create
```

This walks you through creating a new Flet extension with interactive prompts.

For non-interactive usage:

```bash
flet-pkg create --type service --flutter-package onesignal_flutter --output .
```

## Generated project structure

```
flet-onesignal/
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── LICENSE
├── mkdocs.yml
├── docs/
├── tests/
├── examples/
│   └── flet_onesignal_example/
└── src/
    ├── flet_onesignal/        # Python package
    │   ├── __init__.py
    │   ├── onesignal.py       # @ft.control + ft.Service
    │   └── types.py
    └── flutter/
        └── flet_onesignal/    # Flutter package
            ├── pubspec.yaml
            └── lib/
                └── src/
                    ├── extension.dart
                    └── onesignal_service.dart
```

## License

MIT
