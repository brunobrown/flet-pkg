# Architecture

How `flet-pkg` works internally.

## Overview

```mermaid
flowchart LR
    A[CLI<br/>Typer] --> B[Prompts<br/>Rich]
    B --> C[Validators]
    C --> D[Registry<br/>Check]
    D --> E[Scaffolder<br/>Jinja2]
    E --> F[Pipeline]
    F --> G{--ai-refine?}
    G -->|yes| H[AI Refine]
    G -->|no| I[Output]
    H --> I[Output]
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
│   │   ├── base.py          # CodeGenerator abstract base
│   │   ├── python_control.py    # Main control file
│   │   ├── python_submodule.py  # Sub-module files
│   │   ├── python_types.py      # types.py (enums, events)
│   │   ├── python_init.py       # __init__.py exports
│   │   └── dart_service.py      # Dart FletService/FletWidget
│   ├── models.py            # DartPackageAPI, GenerationPlan
│   ├── parser.py            # Dart API parser + detect_extension_type()
│   ├── pipeline.py          # GenerationPipeline orchestrator
│   ├── prompts.py           # Rich interactive prompts
│   ├── registry_checker.py  # PyPI, GitHub, Flet SDK name conflict check
│   ├── scaffolder.py        # Jinja2 template engine
│   ├── type_map.py          # Dart → Python type mapping
│   └── validators.py        # Name validation + derivation
├── core/ai/
│   ├── agent.py             # pydantic-ai Architect/Editor agents
│   ├── config.py            # AIConfig + provider detection
│   ├── gap_analyzer.py      # Deterministic coverage gap analyzer
│   ├── models.py            # GapReport, RefinementResult, etc.
│   ├── provider.py          # Model factory for pydantic-ai
│   └── refiner.py           # AIRefiner orchestrator
├── mcp/
│   ├── server.py            # FastMCP server (tools, resources, prompts)
│   └── _serializers.py      # Dataclass → dict helpers
├── ui/
│   ├── console.py           # Rich console instance
│   ├── coverage.py          # Coverage score + breakdown table
│   ├── panels.py            # Header, info, error panels
│   └── tree.py              # Project tree display
└── templates/
    ├── service/             # Service extension template
    └── ui_control/          # UI Control extension template
```

## Data model

Two aggregates flow through the pipeline: the **parser** produces a
`DartPackageAPI` (a faithful view of the Dart source), and the **analyzer**
transforms it into a `GenerationPlan` (what the generators emit). Both live in
[`core/models.py`](api/models.md).

```mermaid
classDiagram
    direction LR

    class DartPackageAPI {
        +list~DartClass~ classes
        +list~DartEnum~ enums
        +list~DartClass~ helper_classes
        +list~DartMethod~ top_level_functions
        +dict reexported_types
    }
    class DartClass {
        +str name
        +str parent_class
        +str source_file
        +list~DartMethod~ methods
        +list~DartParam~ constructor_params
    }
    class DartMethod {
        +str name
        +str return_type
        +bool is_static
        +bool is_getter
        +bool is_async
    }
    class DartParam {
        +str name
        +str dart_type
        +bool required
        +bool named
    }
    class DartEnum {
        +str name
        +list values
    }
    DartPackageAPI o-- DartClass
    DartPackageAPI o-- DartEnum
    DartClass o-- DartMethod
    DartClass o-- DartParam : constructor_params
    DartMethod o-- DartParam

    class GenerationPlan {
        +str control_name
        +str base_class
        +list~PropertyPlan~ properties
        +list~MethodPlan~ main_methods
        +list~EventPlan~ events
        +list~SubModulePlan~ sub_modules
        +list~EnumPlan~ enums
    }
    class MethodPlan {
        +str python_name
        +str return_type
        +bool is_async
        +bool dart_is_async
        +bool is_static
        +list~ParamPlan~ params
    }
    class PropertyPlan {
        +str python_name
        +str python_type
        +str dart_getter
    }
    class EventPlan {
        +str python_attr_name
        +str event_class_name
    }
    class SubModulePlan {
        +str module_name
        +str class_name
        +list~MethodPlan~ methods
    }
    GenerationPlan o-- PropertyPlan
    GenerationPlan o-- MethodPlan
    GenerationPlan o-- EventPlan
    GenerationPlan o-- SubModulePlan
    MethodPlan o-- ParamPlan
    SubModulePlan o-- MethodPlan

    DartPackageAPI ..> GenerationPlan : PackageAnalyzer.analyze()
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
7. Optionally runs AI refinement if `--ai-refine` is set
8. Displays coverage score and the generated project tree

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

### Generation Pipeline (`core/pipeline.py`)

Orchestrates the full code generation flow:

1. **Download** — fetches the Flutter package from pub.dev (or uses a local path)
2. **Parse** — extracts `DartPackageAPI` from Dart source files
3. **Analyze** — produces a `GenerationPlan` (methods, events, enums, properties, sub-modules)
4. **Generate** — runs 5 generators to produce Python + Dart files
5. **Write** — writes generated files to the project directory, overwriting template stubs
6. **Gap analysis** — computes coverage percentage
7. **AI refine** (optional) — runs the Architect/Editor pattern for improvements

```mermaid
flowchart TD
    DL[Download<br/>pub.dev or local] --> PA[Parse<br/>DartPackageAPI]
    PA --> AN[Analyze<br/>GenerationPlan]
    AN --> GEN[Generate<br/>5 generators]
    GEN --> WR[Write files<br/>overwrite stubs]
    WR --> GAP[Gap analysis<br/>coverage percent]
    GAP --> REF{--ai-refine?}
    REF -->|yes| AI[AI Refine<br/>Architect/Editor]
    REF -->|no| OUT[Project ready]
    AI --> OUT

    PA -. produces .-> APIOBJ[(DartPackageAPI)]
    AN -. produces .-> PLANOBJ[(GenerationPlan)]
    APIOBJ -. consumed by .-> AN
    PLANOBJ -. consumed by .-> GEN
```

### Generators (`core/generators/`)

Five specialized generators produce different parts of the output:

| Generator | Output |
|-----------|--------|
| `PythonControlGenerator` | Main control file (e.g. `onesignal.py`) |
| `PythonSubModuleGenerator` | Sub-module files (e.g. `user.py`, `notifications.py`) |
| `PythonTypesGenerator` | `types.py` with enums and event dataclasses |
| `PythonInitGenerator` | `__init__.py` with exports |
| `DartServiceGenerator` | Dart service/widget files + `extension.dart` |

### AI Refinement (`core/ai/`)

Optional LLM-powered code improvement using the **Architect/Editor** pattern:

1. **Gap Analyzer** (`gap_analyzer.py`) — deterministic comparison of `DartPackageAPI` vs `GenerationPlan` to find coverage gaps
2. **Architect** agent — LLM reasons about WHAT to improve based on the gap report
3. **Editor** agent — LLM produces search/replace edits (HOW to fix)
4. **Validator** — checks syntax of edited files and retries on failure

```mermaid
flowchart LR
    GA[Gap Analyzer<br/>DartPackageAPI vs GenerationPlan] --> R[(Gap report)]
    R --> AR[Architect agent<br/>WHAT to improve]
    AR --> ED[Editor agent<br/>search/replace edits]
    ED --> V{Validator<br/>syntax OK?}
    V -->|no, retry| ED
    V -->|yes| DONE[Refined files]
```

Supports multiple providers: Ollama (local, free), Anthropic, OpenAI, Google.

### Coverage

The gap analyzer computes a coverage score:

```
coverage = generated_items / total_dart_api_items × 100
```

Categories tracked: Methods, Events, Enums, Properties.

### MCP Server (`mcp/server.py`)

Exposes flet-pkg capabilities to AI agents via the [Model Context Protocol](https://modelcontextprotocol.io/):

- **7 tools**: derive_names, map_dart_type, fetch_metadata, detect_extension_type, scaffold, run_pipeline, analyze_gaps
- **2 resources**: type-map, templates
- **3 prompts**: scaffold_service, scaffold_ui_control, analyze_package

See the [MCP Server documentation](mcp-server.md) for configuration details.

### Templates

Templates live under `src/flet_pkg/templates/`. Each template type has:

- `template.yaml` — template metadata
- A directory tree with `{{variable}}` placeholders in names
- `.jinja` suffix on files that need rendering

Variable substitution happens both in **file/directory names** and in **file contents** (for `.jinja` files).
