<p align="center"><img src="https://github.com/user-attachments/assets/06ef3010-78b7-4007-b5f7-40cf0201cf3a" width="500" height="500" alt="Flet PKG"></p>

**CLI tool that scaffolds Flet extension packages from Flutter packages, with auto-generated Python controls, Dart bridge code, type mappings, and event handlers.**

![Python](https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white)
![Flet](https://img.shields.io/badge/flet-0.80.0+-00B4D8?logo=flet)
[![Main](https://github.com/brunobrown/flet-pkg/actions/workflows/main.yml/badge.svg?branch=main)](https://github.com/brunobrown/flet-pkg/actions/workflows/main.yml)
[![Dev](https://github.com/brunobrown/flet-pkg/actions/workflows/dev.yml/badge.svg?branch=dev)](https://github.com/brunobrown/flet-pkg/actions/workflows/dev.yml)
![Docs](https://img.shields.io/badge/https%3A%2F%2Fimg.shields.io%2Fbadge%2Fdocs-mkdocs-blue?label=docs)
![Coverage](https://img.shields.io/badge/coverage-95%25-orange)
![License](https://img.shields.io/badge/license-MIT-yellow)

---

> **Important: this tool does not perform miracles.** 🙏😂
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
    - [Output Options](#output-options)
- [Verbose Mode & Coverage Score](#verbose-mode--coverage-score)
- [AI Refinement](#ai-refinement)
  - [Free (Ollama - Local)](#free-ollama---local)
    - [Ollama Model Requirements](#ollama-model-requirements)
  - [Cloud Providers](#cloud-providers)
  - [How AI Refinement Works](#how-ai-refinement-works)
- [MCP Server](#mcp-server)
  - [Installation](#mcp-installation)
  - [Claude Desktop Configuration](#claude-desktop-configuration)
  - [Available Tools](#available-tools)
  - [Resources & Prompts](#resources--prompts)
- [Generated Project Structure](#generated-project-structure)
- [Name Conflict Detection](#name-conflict-detection)
- [Generation Pipeline](#generation-pipeline)
- [Coverage](#coverage)
- [Examples](#examples)
- [Development](#development)
- [Learn more](#learn-more)
- [Flet Community](#flet-community)
- [Support](#support)
- [Contributing](#contributing)

---

## Buy Me a Coffee

If you find this project useful, please consider supporting its development:

<a href="https://www.buymeacoffee.com/brunobrown">
<img src="https://www.buymeacoffee.com/assets/img/guidelines/download-assets-sm-1.svg" width="200" alt="Buy Me a Coffee">
</a>

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

To enable the **MCP server** (optional — for AI agent integrations):

```bash
# Using UV
uv add flet-pkg[mcp]

# Using pip
pip install flet-pkg[mcp]
```

**Requirements:** Python 3.10+

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

# Verbose mode — detailed output + coverage breakdown table
flet-pkg create -t service -f shared_preferences -v
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

![flet_pkg](https://github.com/user-attachments/assets/dea17fa6-496e-4666-9127-c159e2954797)

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
  --version    Show version and exit.
  --help       Show this message and exit.

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
| `--ai-model` | TEXT | _(per provider)_ | Override the default model. Defaults: `ollama`=`qwen2.5-coder:14b`, `anthropic`=`claude-sonnet-4-6`, `openai`=`gpt-4.1-mini`, `google`=`gemini-2.5-flash`. See [Ollama Model Requirements](#ollama-model-requirements) for RAM sizing. |

#### Output Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--verbose` | `-v` | BOOL | `False` | Show detailed analysis output and coverage breakdown table. Without this flag, only a one-line coverage score is shown. |

---

## Verbose Mode & Coverage Score

After code generation, flet-pkg runs a **deterministic gap analysis** that compares the Dart API against the generated Python code. A **coverage score** is always displayed:

```
  Coverage: 95.4% (41/43 features mapped)
```

### Verbose Mode (`-v`)

Pass `--verbose` or `-v` to see detailed output at every pipeline step:

```bash
# Score only (default)
flet-pkg create -t service -f shared_preferences --no-ai-refine

# Full verbose output with breakdown table
flet-pkg create -t service -f shared_preferences --no-ai-refine -v

# Verbose + AI refinement details
flet-pkg create -t service -f shared_preferences --ai-refine -v
```

In verbose mode you'll see:

- **Parse details** — every class and enum discovered in the Dart source
- **Analyze details** — each method, sub-module, event, and property mapped
- **Generate details** — file breakdown (Python vs Dart) with filenames
- **AI details** _(when `--ai-refine`)_ — gap report, architect suggestions, editor edits, validation results
- **Coverage breakdown table** — per-category Rich table:

```
            Coverage Breakdown
┌────────────────┬──────────┬─────────┬─────────────────┐
│ Category       │ Dart API │  Mapped │ Coverage        │
├────────────────┼──────────┼─────────┼─────────────────┤
│ Methods        │       25 │      24 │ ████████░░ 96%  │
│ Events         │        5 │       5 │ ██████████ 100% │
│ Enums          │        8 │       7 │ ███████░░░ 88%  │
├────────────────┼──────────┼─────────┼─────────────────┤
│ Total          │       38 │      36 │ █████████░ 95%  │
└────────────────┴──────────┴─────────┴─────────────────┘
```

---

## AI Refinement

The AI refinement is an **optional** post-generation step that uses an LLM to detect coverage gaps and auto-improve the generated code. It uses the **Architect/Editor pattern** (inspired by [Aider's research](https://aider.chat/2024/09/26/architect.html)) which separates reasoning from editing for better results.

### Free (Ollama - Local)

No API key needed. Runs entirely on your machine:

```bash
# 1. Install Ollama (https://ollama.com)
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Pull the default coding model (see RAM requirements below)
ollama pull qwen2.5-coder:14b

# 3. Install the AI dependency
uv add flet-pkg[ai]    # or: pip install flet-pkg[ai]

# 4. Create with AI refinement (Ollama is the default provider)
flet-pkg create -f shimmer --ai-refine
```

#### Ollama Model Requirements

Choose the model size based on your available RAM. Larger models produce better results but require more memory:

| Model | Size | Min RAM | GPU | Notes |
|-------|------|---------|-----|-------|
| `qwen2.5-coder:7b` | ~4.5 GB | 8 GB | Optional | Fast, but may fail on complex structured output |
| `qwen2.5-coder:14b` | ~9 GB | 16 GB | Optional | **Default — best balance of quality and speed** |
| `qwen2.5-coder:32b` | ~19 GB | 32 GB | Recommended | Best quality, but slow without dedicated GPU |

> **Warning:** Running a model that exceeds your available RAM will cause severe system slowdown or freeze. If you have **no dedicated GPU** (NVIDIA/AMD), the model runs entirely on CPU+RAM. For machines with 24 GB RAM or less, use the **14b** model (default).
>
> To override the model: `flet-pkg create --ai-refine --ai-model qwen2.5-coder:7b`

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

## MCP Server

flet-pkg includes an **MCP (Model Context Protocol) server** that exposes its scaffolding and code generation capabilities to AI agents like Claude Desktop, Cursor, and VS Code Copilot. This complements the CLI by allowing AI assistants to create Flet extensions programmatically.

### MCP Installation

```bash
# Install with MCP support
uv add flet-pkg[mcp]    # or: pip install flet-pkg[mcp]

# Verify it works
flet-pkg-mcp
```

### Claude Desktop Configuration

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "flet-pkg": {
      "command": "flet-pkg-mcp"
    }
  }
}
```

Or use `uvx` (no install needed):

```json
{
  "mcpServers": {
    "flet-pkg": {
      "command": "uvx",
      "args": ["--from", "flet-pkg[mcp]", "flet-pkg-mcp"]
    }
  }
}
```

### Available Tools

| Tool | Description | Network |
|------|-------------|---------|
| `tool_derive_names` | Derive project/package/control names from a Flutter package name | No |
| `tool_map_dart_type` | Convert a Dart type to its Python/Flet equivalent | No |
| `tool_fetch_metadata` | Get pub.dev package metadata (version, description, homepage) | Yes (cached) |
| `tool_detect_extension_type` | Auto-detect whether a package is a service or ui_control | Yes (cached) |
| `tool_scaffold` | Create a project skeleton from a template | No |
| `tool_run_pipeline` | Full pipeline: download, parse, analyze, generate, write | Yes (cached) |
| `tool_analyze_gaps` | Deterministic coverage gap analysis (no LLM) | Yes (cached) |

### Resources & Prompts

**Resources:**

| URI | Description |
|-----|-------------|
| `flet-pkg://type-map` | Full Dart-to-Python type mapping table |
| `flet-pkg://templates` | Available template names (service, ui_control) |

**Prompts:**

| Prompt | Description |
|--------|-------------|
| `scaffold_service` | Step-by-step guide to scaffold a service extension |
| `scaffold_ui_control` | Step-by-step guide to scaffold a UI control extension |
| `analyze_package` | Guide to analyze coverage without scaffolding |

### Example Prompts

With the MCP server configured, use natural language in Claude Code or Claude Desktop:

```
> Use the flet-pkg tool to analyze the Flutter package "onesignal_flutter" and tell me
  the extension type and coverage.
```

```
> Use the flet-pkg tool to analyze the Flutter package "rive" and tell me the extension
  type and coverage.
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
| `shared_preferences` | Service | 100.0% |
| `url_launcher` | UI Control | 100.0% |
| `local_auth` | Service | 100.0% |
| `geolocator` | Service | 100.0% |
| `share_plus` | Service | 100.0% |
| `image_picker` | Service | 100.0% |
| `onesignal_flutter` | Service | 97.6% |

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

### Verbose output with coverage breakdown

```bash
flet-pkg create -t service -f battery_plus -v
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

## Learn more
* [Documentation](https://brunobrown.github.io/flet-pkg)

## Flet Community

Join the community to contribute or get help:

* [Discussions](https://github.com/flet-dev/flet/discussions)
* [Discord](https://discord.gg/dzWXP8SHG8)
* [X (Twitter)](https://twitter.com/fletdev)
* [Bluesky](https://bsky.app/profile/fletdev.bsky.social)
* [Email us](mailto:hello@flet.dev)

## Support

If you like this project, please give it a [GitHub star](https://github.com/brunobrown/flet-pkg) ⭐

---

## Contributing

Contributions and feedback are welcome!

1. Fork the repository
2. Create a feature branch
3. Submit a pull request with detailed explanation

For feedback, [open an issue](https://github.com/brunobrown/flet-pkg/issues) with your suggestions.

---
## Try flet-pkg today and turn any Flutter package into a Flet extension in seconds!

<p align="center"><img src="https://github.com/user-attachments/assets/431aa05f-5fbc-4daa-9689-b9723583e25a" width="50%"></p>
<p align="center"><a href="https://www.bible.com/bible/116/PRO.16.NLT"> Commit your work to the LORD, and your plans will succeed. Proverbs 16:3</a></p>
