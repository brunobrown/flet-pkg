# Changelog

## [0.2.0] - 2026-05-27

Major quality release: generated extensions are now aligned to **Flet 0.85.x** and
compile far more cleanly. Across a 5-package end-to-end audit, `flutter analyze`
errors on generated extensions dropped ~68% (simple services now compile with zero
errors). The generated Dart remains a reviewable scaffold — advanced cases
(required callbacks, complex SDK config types) are documented TODOs.

### Added

- **Mermaid diagrams** in the docs (enabled via `pymdownx.superfences`): architecture
  overview, generation pipeline, core data-model class diagram, AI-refinement flow, and
  the Python↔Dart communication bridge (in both project docs and generated extensions).
- **Post-creation guidance** — the `create` "Next Steps" panel and generated guides now
  explain testing via `flet build` (not `flet run`, which only knows built-in controls),
  resolving the most common point of confusion (GitHub issue #6).

### Changed

- **Flet 0.85 alignment** — generated Dart uses the canonical `class Extension extends
  FletExtension` with `createWidget`/`createService`; the widget class is `{Control}Control`
  in `lib/src/{snake}_control.dart`; pins bumped to `flet>=0.85.1` / `flet: ^0.85.1`.
- **Example app wiring** — example `pyproject.toml` now uses `[tool.flet.dev_packages]`,
  `[tool.uv.sources]` (editable), and `[tool.flet]` metadata (the non-existent
  `[tool.flet.dependencies]` was removed).
- **Docs updated to Flet 0.85.x** patterns (`@ft.control`, `ft.LayoutControl`,
  `_invoke_method`), correct author URL, and a "trying out your extension" section.

### Fixed — Dart bridge generation (service & UI control)

- UI control widget/file naming aligned to the official convention (`{Control}Control` /
  `{snake}_control.dart`) so the exported `extension.dart` compiles.
- Synchronous SDK calls/getters are no longer `await`ed (`await_only_futures` /
  `use_of_void_result`); stream events dispatch via `.listen(...)` on the SDK instance.
- `buildWidget`/`buildWidgets` are called on `widget.control` (the Control extension
  receiver) instead of as undefined bare calls.
- Non-nullable params are coalesced: child widgets (`?? const SizedBox.shrink()`),
  numeric/string getters (`?? 0.0` / `?? 0` / `?? ""`), enums (`?? <Enum>.values.first`).
- `ft.Color` reads via `getColor("name", context)`; Flutter/package enums read via
  `parseEnum(<Enum>.values, getString(...))`; typed `List`/`Map` args use `.cast<T>()`.
- Static-access on instance members fixed; `@visibleForTesting`/`@protected` and
  example-app (`lib/main.dart`) classes are filtered out of generation.
- Widget-family detection no longer groups unrelated widgets as variants (requires shared
  constructor params); the dialog API and version strings updated to 0.85.
- Parser: params annotated with a multi-line `@Deprecated(...)` and a default no longer
  mis-parse the parameter name.

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
