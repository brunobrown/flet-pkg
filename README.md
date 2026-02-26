# Flet PKG

CLI tool to scaffold Flet extension packages.

Generates complete, ready-to-develop Flet extensions with Python + Flutter/Dart code, following Flet 0.80.x+ patterns.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flet](https://img.shields.io/badge/Flet-0.80.0+-00B4D8?style=for-the-badge&logo=flutter&logoColor=white)
![CI-MAIN](https://img.shields.io/badge/ci|main-passing-brightgreen?style=for-the-badge)
![CI-DEV](https://img.shields.io/badge/ci|dev-passing-brightgreen?style=for-the-badge)
![Docs](https://img.shields.io/badge/https%3A%2F%2Fimg.shields.io%2Fbadge%2Fdocs-mkdocs-blue?style=for-the-badge&label=Docs)
![Downloads](https://img.shields.io/badge/https%3A%2F%2Fstatic.pepy.tech%2Fpersonalized-badge%2Fflet-onesignal%3Fperiod%3Dmonthly%26units%3DINTERNATIONAL_SYSTEM%26left_color%3DGREY%26right_color%3DBLUE%26left_text%3Ddownloads%252Fmonth?style=for-the-badge&label=Downloads%2FMonth)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

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
flet-pkg create --type auto --flutter-package onesignal_flutter --output .
```

### Extension types

| Option | Description |
|--------|-------------|
| **Auto-detect** (default) | Downloads the Flutter package and detects the type automatically |
| **Service** | Non-visual extension (`ft.Service`), e.g. push notifications, analytics |
| **UI Control** | Visual widget (`ft.LayoutControl`), e.g. maps, charts, custom widgets |

### Name conflict detection

After you choose the extension name, `flet-pkg` checks **PyPI**, **GitHub**, and the **Flet SDK monorepo** for existing packages with the same name. If matches are found, you'll see a warning with links and a confirmation prompt before continuing.

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

