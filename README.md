<p align="center"><img src="https://github.com/user-attachments/assets/06ef3010-78b7-4007-b5f7-40cf0201cf3a" width="500" height="500" alt="Flet PKG"></p>

<p align="center">
  <strong>CLI tool that scaffolds Flet extension packages from Flutter packages, with auto-generated Python controls, Dart bridge code, type mappings, and event handlers.</strong>
</p>

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flet](https://img.shields.io/badge/Flet-0.80.0+-00B4D8?style=for-the-badge&logo=flutter&logoColor=white)
![CI-MAIN](https://img.shields.io/badge/ci|main-passing-brightgreen?style=for-the-badge)
![CI-DEV](https://img.shields.io/badge/ci|dev-passing-brightgreen?style=for-the-badge)
![Docs](https://img.shields.io/badge/https%3A%2F%2Fimg.shields.io%2Fbadge%2Fdocs-mkdocs-blue?style=for-the-badge&label=Docs)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

---

> **Important: this tool does not do magic.**
>
> Every Flutter package on [pub.dev](https://pub.dev) has its own API surface, configuration requirements, and platform-specific behaviors. Some packages expose simple method calls; others require complex initialization flows, native platform setup (Android manifests, iOS plists, Gradle/CocoaPods configuration), or callback-based architectures that don't map cleanly to Python.
>
> It would be unrealistic to write a code generation algorithm that generalizes perfectly for every possible Flutter package. **flet-pkg** aims to accelerate the process by delivering significantly more than a blank skeleton — it downloads the real Dart source, parses the public API, and auto-generates Python controls, type mappings, enum definitions, event handlers, and Dart bridge code. For service packages, this typically covers ~95% of the API surface.
>
> However, **the developer is still responsible for**:
> - Understanding how the original Flutter/Dart package works
> - Reviewing the generated code for correctness
> - Handling package-specific configurations (native platform setup, initialization flows, etc.)
> - Adjusting or complementing the generated code for edge cases the pipeline could not cover
>
> Think of flet-pkg as a smart starting point, not a finished product.

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [Usage](#usage)
  - [Interactive Mode](#interactive-mode)
  - [Non-Interactive Mode (CI/Scripting)](#non-interactive-mode-ciscripting)
  - [Using a Local Flutter Package](#using-a-local-flutter-package)
- [Extension Types](#extension-types)
- [CLI Reference](#cli-reference)
  - [flet-pkg --help](#flet-pkg---help)
  - [flet-pkg create](#flet-pkg-create)
    - [Package Options](#package-options)
    - [Code Generation Options](#code-generation-options)
    - [AI Refinement Options](#ai-refinement-options)
- [AI Refinement](#ai-refinement)
  - [Free (Ollama - Local)](#free-ollama---local)
  - [Cloud Providers](#cloud-providers)
  - [How AI Refinement Works](#how-ai-refinement-works)
- [Generated Project Structure](#generated-project-structure)
- [Name Conflict Detection](#name-conflict-detection)
- [Generation Pipeline](#generation-pipeline)
- [Coverage](#coverage)
- [Examples](#examples)
- [Development](#development)
- [Support](#support)
- [License](#license)

---

## Installation

```bash
# Using UV (recommended)
uv add flet-pkg

# Using pip
pip install flet-pkg
```

To enable **AI refinement** (optional):

```bash
# Using UV
uv add flet-pkg[ai]

# Using pip
pip install flet-pkg[ai]
```

**Requirements:** Python 3.11+

---

## Quick Start

```bash
# Interactive mode — prompts guide you through every step
flet-pkg create

# One-liner for a service extension
flet-pkg create -t service -f shared_preferences

# One-liner for a UI control extension
flet-pkg create -t ui_control -f shimmer

# Auto-detect type + AI refinement (free, uses Ollama locally)
flet-pkg create -f onesignal_flutter --ai-refine
```

---

## How It Works

flet-pkg automates the tedious parts of creating a Flet extension:

1. **Downloads** the Flutter package source from [pub.dev](https://pub.dev) (or uses a local path)
2. **Parses** the Dart source files to extract the public API (classes, methods, constructors, enums, streams)
3. **Analyzes** the API to produce a generation plan (type mappings, event detection, sub-module grouping)
4. **Generates** Python controls (`ft.Service` / `ft.LayoutControl`), Dart bridge code, type definitions, and `__init__.py` exports
5. **Writes** everything into a ready-to-develop project with `pyproject.toml`, tests, examples, and docs scaffolding

Optionally, an **AI refinement** step can analyze coverage gaps and auto-improve the generated code using LLM-powered edits.

---

## Usage

### Interactive Mode

```bash
flet-pkg create
```

The CLI walks you through each step with prompts:

1. **Extension type** — Auto-detect (recommended), Service, or UI Control
2. **Flutter package name** — The package name from pub.dev (e.g. `onesignal_flutter`)
3. **Extension name** — Your Flet extension project name (e.g. `flet-onesignal`)
4. **Python package name** — The importable package name (e.g. `flet_onesignal`)
5. **Control class name** — The Python class name (e.g. `OneSignal`)
6. **Description** — A short description for `pyproject.toml`
7. **Author** — Your name
8. **Debug console** — Whether to include a debug console module
9. **AI refinement** — Whether to run AI-powered code improvement (only shown if `pydantic-ai` is installed)

### Non-Interactive Mode (CI/Scripting)

Pass all options as flags to skip prompts entirely:

```bash
flet-pkg create \
  --type service \
  --flutter-package shared_preferences \
  --output ./my-extensions
```

For a UI control with AI refinement:

```bash
flet-pkg create \
  --type ui_control \
  --flutter-package shimmer \
  --ai-refine \
  --ai-provider ollama \
  --no-console
```

### Using a Local Flutter Package

If you have the Flutter package source locally (useful for private packages or development):

```bash
flet-pkg create \
  --type service \
  --flutter-package my_package \
  --local-package ./path/to/my_package
```

This skips the pub.dev download and uses your local files directly.

---

## Extension Types

| Type | Base Class | Description | Example Packages |
|------|-----------|-------------|------------------|
| **Auto-detect** | _(detected)_ | Downloads the package and inspects the Dart source to determine the type automatically. Falls back to a manual prompt if detection fails. | Any package |
| **Service** | `ft.Service` | Non-visual extensions that provide platform services — push notifications, storage, sensors, authentication. Methods are exposed as async Python calls via `invoke_method`. | `shared_preferences`, `onesignal_flutter`, `geolocator`, `local_auth`, `battery_plus` |
| **UI Control** | `ft.LayoutControl` | Visual widget extensions that render Flutter widgets on screen. Constructor parameters become Python properties mapped via `_get_control_name` and `_before_build_command`. | `shimmer`, `flutter_rating_bar`, `rive`, `video_player` |

---

## CLI Reference

### `flet-pkg --help` or `flet-pkg create --help`

```
Usage: flet-pkg [OPTIONS] COMMAND [ARGS]...

Options:
  -v, --version    Show version and exit.
  --help           Show this message and exit.

Commands:
  create    Create a new Flet extension package.
```

### flet-pkg create

```
Usage: flet-pkg create [OPTIONS]
```

#### Package Options

| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--type` | `-t` | TEXT | Extension type: `auto` (default), `service`, or `ui_control`. |
| `--flutter-package` | `-f` | TEXT | Flutter package name from [pub.dev](https://pub.dev). |
| `--output` | `-o` | PATH | Output directory for the generated project. Defaults to current directory. |
| `--local-package` | `-l` | PATH | Path to a local Flutter package source. Skips the pub.dev download. |

#### Code Generation Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--analyze / --no-analyze` | BOOL | `analyze` | Analyze the Flutter package and auto-generate Python controls, type mappings, and Dart bridge code. Use `--no-analyze` to generate only the skeleton structure without code analysis. |
| `--console / --no-console` | BOOL | _(prompted)_ | Include a debug console module (`console.py`) for development logging. |

#### AI Refinement Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--ai-refine / --no-ai-refine` | BOOL | _(prompted)_ | Run AI-powered refinement on generated code. Requires `uv add flet-pkg[ai]` or `pip install flet-pkg[ai]`. |
| `--ai-provider` | TEXT | `ollama` | AI provider: `ollama` (local, free), `anthropic` (Claude), `openai` (GPT), or `google` (Gemini). |
| `--ai-model` | TEXT | _(per provider)_ | Override the default model. Defaults: `ollama`=`qwen2.5-coder`, `anthropic`=`claude-sonnet-4-6`, `openai`=`gpt-4.1-mini`, `google`=`gemini-2.5-flash`. |

---

## AI Refinement

The AI refinement is an **optional** post-generation step that uses an LLM to detect coverage gaps and auto-improve the generated code. It uses the **Architect/Editor pattern** (inspired by [Aider's research](https://aider.chat/2024/09/26/architect.html)) which separates reasoning from editing for better results.

### Free (Ollama - Local)

No API key needed. Runs entirely on your machine:

```bash
# 1. Install Ollama (https://ollama.com)
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Pull the default coding model
ollama pull qwen2.5-coder

# 3. Install the AI dependency
uv add flet-pkg[ai]    # or: pip install flet-pkg[ai]

# 4. Create with AI refinement (Ollama is the default provider)
flet-pkg create -f shimmer --ai-refine
```

### Cloud Providers

If you prefer a cloud-hosted LLM, set the appropriate API key:

```bash
# Anthropic (Claude)
export ANTHROPIC_API_KEY=sk-ant-...
flet-pkg create -f shimmer --ai-refine --ai-provider anthropic

# OpenAI (GPT)
export OPENAI_API_KEY=sk-...
flet-pkg create -f shimmer --ai-refine --ai-provider openai

# Google (Gemini)
export GOOGLE_API_KEY=...
flet-pkg create -f shimmer --ai-refine --ai-provider google
```

### How AI Refinement Works

The pipeline runs in 4 steps:

```
Step 1: Gap Report (deterministic, no LLM)
├── Compares the Dart API against the generated code
├── Identifies: missing methods, properties, enums, events, type mismatches
└── Produces a structured GapReport

Step 2: Architect (LLM)
├── Receives the GapReport + Dart source snippets + generated file summaries
├── Reasons about HOW to fix each feasible gap
└── Produces an ArchitectPlan (text descriptions of improvements)

Step 3: Editor (LLM)
├── Receives the ArchitectPlan + actual file contents
├── Produces precise search/replace code edits
└── Returns structured FileEdit objects

Step 4: Validator (deterministic, no LLM)
├── Applies the edits to the generated files
├── Validates Python syntax
├── If errors: feeds back to Editor (max 2 retries)
└── Writes the refined files
```

---

## Generated Project Structure

After running `flet-pkg create`, you get a complete, ready-to-develop project:

```
flet-onesignal/                     # Project root
├── pyproject.toml                  # Hatchling build + Flet metadata
├── README.md                       # Extension documentation
├── CHANGELOG.md
├── LICENSE
├── mkdocs.yml                      # MkDocs Material config
├── docs/                           # Documentation source
│   ├── index.md
│   ├── getting-started.md
│   ├── api-reference.md
│   └── examples.md
├── tests/
│   └── test_flet_onesignal.py      # Pytest test file
├── examples/
│   └── flet_onesignal_example/     # Working example app
│       ├── pyproject.toml
│       └── src/
│           └── main.py             # ft.run(main) example
└── src/
    ├── flet_onesignal/             # Python package
    │   ├── __init__.py             # Public exports
    │   ├── onesignal.py            # Main control (@ft.control + ft.Service)
    │   ├── user.py                 # Sub-module (auto-detected from Dart API)
    │   ├── types.py                # Enums, dataclasses, type definitions
    │   └── console.py              # Debug console (optional)
    └── flutter/
        └── flet_onesignal/         # Flutter package
            ├── pubspec.yaml        # Flutter dependencies
            ├── analysis_options.yaml
            └── lib/
                ├── flet_onesignal.dart
                └── src/
                    ├── extension.dart           # Flet extension entry point
                    └── onesignal_service.dart    # Dart bridge code
```

The files under `src/flet_onesignal/` and `src/flutter/.../lib/src/` are **auto-generated** from the Flutter package analysis. They contain real method mappings, type conversions, and event handlers — not just stubs.

---

## Name Conflict Detection

When you choose an extension name, flet-pkg automatically checks for existing packages across:

- **PyPI** — Python Package Index
- **GitHub** — Public repositories
- **Flet SDK** — Official Flet monorepo packages

If matches are found, you'll see a warning with links and a confirmation prompt before continuing. This helps avoid naming conflicts with existing packages.

---

## Generation Pipeline

The deterministic pipeline (no AI needed) follows these steps:

```
download → parse → analyze → generate → [AI refine] → write
```

| Step | Module | Description |
|------|--------|-------------|
| **Download** | `core/downloader.py` | Fetches the Flutter package from pub.dev. Caches locally at `~/.cache/flet-pkg/`. |
| **Parse** | `core/parser.py` | Parses Dart source files into a structured `DartPackageAPI` (classes, methods, constructors, enums, streams, getters). |
| **Analyze** | `core/analyzer.py` | Produces a `GenerationPlan` with method mappings, type conversions, event detection, sub-module grouping, compound widget detection, and sibling widget detection. |
| **Generate** | `core/generators/` | Five generators produce Python and Dart code: control, sub-modules, types, `__init__.py`, and Dart service/control. |
| **AI Refine** | `core/ai/` | _(Optional)_ Gap analysis + LLM-powered code improvement. |
| **Write** | `core/pipeline.py` | Writes files into the project directory, cleans up template stubs that were replaced by generated files. |

Key analysis features:

- **Stream event detection** — `Stream<T> get onXxx` patterns become Python event handlers
- **Sub-module grouping** — Related methods are grouped into separate Python files (e.g. `user.py`, `notifications.py`)
- **Compound widget detection** — Typed sub-widget constructor params become `ft.Control` sub-classes
- **Platform interface resolution** — Downloads `*_platform_interface` packages to fill stub enum values
- **Type mapping** — Dart types are mapped to Python/Flet equivalents via `core/type_map.py`
- **Internal method filtering** — `toString`, `hashCode`, `setMock*` and other framework methods are excluded

---

## Coverage

The deterministic pipeline (without AI) achieves the following coverage on tested packages:

| Package | Type | Coverage |
|---------|------|----------|
| `onesignal_flutter` | Service | 95.4% |
| `url_launcher` | Service | 95.0% |
| `battery_plus` | Service | 95.0% |
| `local_auth` | Service | 94.9% |
| `share_plus` | Service | 94.6% |

Coverage is measured as the percentage of public Dart API surface (methods, properties, enums, events) that is correctly mapped to Python code.

---

## Examples

### Create a service extension for shared_preferences

```bash
flet-pkg create -t service -f shared_preferences
cd flet-shared-preferences
uv sync
```

### Create a UI control for shimmer with AI refinement

```bash
uv add flet-pkg[ai]    # or: pip install flet-pkg[ai]
ollama pull qwen2.5-coder
flet-pkg create -t ui_control -f shimmer --ai-refine
```

### Create from a local Flutter package

```bash
flet-pkg create -t service -f my_package -l ./my_flutter_package
```

### Non-interactive mode for CI

```bash
flet-pkg create \
  -t auto \
  -f onesignal_flutter \
  -o ./output \
  --no-console \
  --no-ai-refine
```

---

## Development

```bash
# Clone and install
git clone https://github.com/brunobrown/flet-pkg.git
cd flet-pkg
uv sync

# Run tests
uv run pytest tests/ -v

# Lint and format
uv tool run ruff format
uv tool run ruff check
uv tool run ty check

# Run the CLI locally
uv run flet-pkg create
```

---

## Support

- **Documentation:** https://brunobrown.github.io/flet-pkg
- **Issues:** https://github.com/brunobrown/flet-pkg/issues

### Buy Me a Coffee

If you find this project useful, please consider supporting its development:

<a href="https://www.buymeacoffee.com/brunobrown">
<img src="https://www.buymeacoffee.com/assets/img/guidelines/download-assets-sm-1.svg" width="200" alt="Buy Me a Coffee">
</a>

---

## License

MIT

---

<p align="center"><img src="https://github.com/user-attachments/assets/431aa05f-5fbc-4daa-9689-b9723583e25a" width="50%"></p>
<p align="center"><a href="https://www.bible.com/bible/116/PRO.16.NLT"> Commit your work to the LORD, and your plans will succeed. Proverbs 16:3</a></p>
