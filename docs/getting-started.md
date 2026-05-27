# Getting Started

This guide walks you through creating your first Flet extension package.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv tool install flet-pkg
```

Or with pip:

```bash
pip install flet-pkg
```

## Creating your first extension

### 1. Run the create command

```bash
flet-pkg create
```

You'll be prompted for:

1. **Extension type** — Auto-detect (recommended), Service (non-visual), or UI Control (visual widget)
2. **Flutter package name** — the pub.dev package you're wrapping (e.g. `onesignal_flutter`)
3. **Extension name** — auto-derived, e.g. `flet-onesignal`
4. **Python package name** — auto-derived, e.g. `flet_onesignal`
5. **Control class name** — auto-derived, e.g. `Onesignal`
6. **Description** and **Author**

!!! tip "Auto-detect"
    When you choose **Auto-detect**, `flet-pkg` downloads the Flutter package and inspects the Dart source code to determine whether it contains widgets (UI Control) or only services. This is the recommended option if you're unsure which type to pick.

!!! note "Name conflict detection"
    After you enter the extension name, `flet-pkg` checks **PyPI**, **GitHub**, and the official **Flet SDK monorepo** (`flet-dev/flet`) for existing packages with the same name. If matches are found, links are displayed and you can choose whether to continue.

### 2. Navigate to your project

```bash
cd flet-onesignal
```

### 3. Install dependencies

```bash
uv sync
```

### 4. Run tests

```bash
uv run pytest -v
```

## Name derivation

`flet-pkg` automatically derives names from the Flutter package name:

| Flutter package | Project name | Python package | Class name |
|----------------|-------------|----------------|------------|
| `onesignal_flutter` | `flet-onesignal` | `flet_onesignal` | `Onesignal` |
| `flutter_map` | `flet-map` | `flet_map` | `Map` |
| `google_maps_flutter` | `flet-google-maps` | `flet_google_maps` | `GoogleMaps` |

Common Flutter affixes (`flutter_`, `_flutter`, `_plus`, `_pro`) are stripped automatically.

## What's next

- Edit the Python control file in `src/<package_name>/` to implement your Flet control
- Review and complete the generated Dart service/widget in `src/flutter/<package_name>/lib/src/` (it's a working scaffold)
- Add examples in `examples/`
- Run `flet-pkg --help` for all available options

### Trying out your extension

The example app under `examples/<package_name>_example/` is pre-wired to use your
extension from source. **Build** it to test the control:

```bash
cd examples/<package_name>_example
uv sync
flet build macos    # or: windows | linux | apk | aab | ipa | web
```

!!! warning "Use `flet build`, not `flet run`"

    `flet run` launches Flet's prebuilt client, which only knows the built-in
    controls — a control from a custom extension renders as *"Unknown control"*
    (and a custom service's Dart code never runs). `flet build` compiles a Flutter
    app that includes your extension's Dart code, so it actually works. This is the
    most common point of confusion when starting out.
