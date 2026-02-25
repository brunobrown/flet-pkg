# flet-pkg

CLI tool to scaffold Flet extension packages.

Generates complete, ready-to-develop Flet extensions with Python + Flutter/Dart code, following Flet 0.80.x+ patterns.

## Installation

Choose your preferred package manager:

```bash
# Using UV (Recommended)
uv add flet-pkg

# Using pip
pip install flet-pkg

# Using Poetry
poetry add flet-pkg
```

---

## Buy Me a Coffee

If you find this project useful, please consider supporting its development:

<a href="https://www.buymeacoffee.com/brunobrown">
<img src="https://www.buymeacoffee.com/assets/img/guidelines/download-assets-sm-1.svg" width="200" alt="Buy Me a Coffee">
</a>

---

## Usage

### Interactive mode

```bash
flet-pkg create
```

Walks you through creating a new extension with prompts for extension type, Flutter package name, and other details.

### Non-interactive mode

```bash
flet-pkg create --type service --flutter-package onesignal_flutter --output .
```

### Extension types

- **Service** — Non-visual extension (`ft.Service`), e.g. push notifications, analytics
- **UI Control** — Visual widget (`ft.LayoutControl`), e.g. maps, charts, custom widgets

### Generated project structure

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

## Commands

| Command | Description |
|---------|-------------|
| `flet-pkg create` | Create a new Flet extension package |
| `flet-pkg --version` | Show version |
| `flet-pkg --help` | Show help |

## License

MIT

---

<p align="center"><img src="https://github.com/user-attachments/assets/431aa05f-5fbc-4daa-9689-b9723583e25a" width="50%"></p>
<p align="center"><a href="https://www.bible.com/bible/116/PRO.16.NLT"> Commit your work to the LORD, and your plans will succeed. Proverbs 16:3</a></p>

