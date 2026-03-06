# Changelog

## [0.1.1] - 2026-03-05

### Added

- **CLI tool** (`flet-pkg create`) with interactive and non-interactive modes for scaffolding Flet extension packages.
- **Auto-detect extension type** — downloads the Flutter package and inspects Dart source to determine `service` or `ui_control` automatically.
- **Deterministic generation pipeline** — download, parse, analyze, generate, write — produces Python controls, Dart bridge code, type mappings, enum definitions, and event handlers from any Flutter package on pub.dev.
- **Service extensions** (`ft.Service`) with async method invocation via `invoke_method`.
- **UI Control extensions** (`ft.LayoutControl`) with constructor-to-property mapping.
- **Sub-module grouping** — related Dart classes (e.g. `OneSignalUser`, `OneSignalNotifications`) become separate Python modules.
- **Compound widget detection** — typed sub-widget constructor params become `ft.Control` sub-classes.
- **Stream event detection** — `Stream<T> get onXxx` patterns become Python `ft.EventHandler` attributes.
- **Platform interface resolution** — downloads `*_platform_interface` packages to fill stub enum values and data class fields.
- **Type mapping** — comprehensive Dart-to-Python/Flet type mapping (`core/type_map.py`) including Flutter enums, generics, and nullable types.
- **Name conflict detection** — checks PyPI, GitHub, and Flet SDK monorepo before creating a package.
- **Verbose mode** (`-v`) with deterministic coverage score and Rich breakdown table per category (Methods, Events, Enums, Properties).
- **Debug console module** — optional `console.py` with `DebugConsole` widget and `setup_logging()` for development.
- **AI refinement** (optional, `flet-pkg[ai]`) — post-generation LLM-powered code improvement using the Architect/Editor pattern:
  - Deterministic gap analysis comparing Dart API vs generated Python code.
  - Architect agent reasons about how to fix each gap.
  - Editor agent produces precise search/replace code edits.
  - Validator checks Python syntax with retry loop.
  - Supports Ollama (free, local), Anthropic, OpenAI, and Google providers.
  - Diff review, spinners, and coverage comparison output.
- **MCP Server** (optional, `flet-pkg[mcp]`) — Model Context Protocol server exposing scaffolding and code generation tools to AI agents (Claude Desktop, Cursor, VS Code Copilot).
- **Documentation** — MkDocs Material site with API Reference (mkdocstrings), architecture guide, CLI reference, and MCP server docs.
- **Generated project structure** includes `pyproject.toml`, `README.md`, `mkdocs.yml`, tests, examples, and docs scaffolding.
- **Template engine** — Jinja2 templates for both `service` and `ui_control` types with `include_console` conditionals.
- **Python reserved word sanitization** — module names and method names that collide with Python keywords (e.g. `async`, `await`) are automatically renamed.
- **Dart control-flow filtering** — false method matches from `catch`/`finally`/`then` patterns are excluded from generation.
- **Test suite** — 383 tests covering models, type map, downloader, analyzer, generators, pipeline, scaffolder, CLI, validators, and coverage.
- **CI/CD** — GitHub Actions workflows for `dev` and `main` branches with ruff, ty, pytest, and mkdocs build.
