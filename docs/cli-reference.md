# CLI Reference

## Global options

```bash
flet-pkg --version      # Show version and exit
flet-pkg --help         # Show help
flet-pkg create --help  # Show help
```

## `flet-pkg create`

Create a new Flet extension package.

```bash
flet-pkg create [OPTIONS]
```

### Package Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--type` | `-t` | `TEXT` | *(interactive)* | Extension type: `auto`, `service` or `ui_control` |
| `--flutter-package` | `-f` | `TEXT` | *(interactive)* | Flutter package name from pub.dev |
| `--output` | `-o` | `PATH` | Current dir | Output directory |
| `--local-package` | `-l` | `PATH` | | Path to a local Flutter package (skip download) |

### Code Generation Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--analyze/--no-analyze` | `BOOL` | `True` | Analyze Flutter package and generate rich code |
| `--console/--no-console` | `BOOL` | *(interactive)* | Include a debug console module for development logging |

### AI Refinement Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--ai-refine/--no-ai-refine` | `BOOL` | *(interactive)* | Run AI-powered refinement on generated code |
| `--ai-provider` | `TEXT` | `ollama` | AI provider: `ollama`, `anthropic`, `openai`, or `google` |
| `--ai-model` | `TEXT` | *(auto)* | Override the default model for the selected provider |

Default models per provider:

| Provider | Default Model |
|----------|--------------|
| `ollama` | `qwen2.5-coder:14b` |
| `anthropic` | `claude-sonnet-4-6` |
| `openai` | `gpt-4.1-mini` |
| `google` | `gemini-2.5-flash` |

### Output Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--verbose` | `-v` | `BOOL` | `False` | Show detailed analysis output and coverage breakdown table |

#### `--type` values

| Value | Description |
|-------|-------------|
| `auto` | Downloads the Flutter package and auto-detects the type (recommended) |
| `service` | Non-visual extension (`ft.Service`) |
| `ui_control` | Visual widget (`ft.LayoutControl`) |

### Interactive mode

When options are omitted, `flet-pkg` prompts you interactively using Rich:

```bash
flet-pkg create
```

The interactive prompt presents three choices for extension type:

```
? Extension type:
  1 - Auto-detect (recommended)
  2 - Service (no visual interface)
  3 - UI Control (visual widget)
```

After you enter the extension name, `flet-pkg` checks **PyPI**, **GitHub**, and the **Flet SDK monorepo** for existing packages. If matches are found, you'll see a warning with links before a confirmation prompt.

If `pydantic-ai` is installed (via `flet-pkg[ai]`), you'll also be prompted for AI refinement options.

### Non-interactive mode

Pass all required options via flags:

```bash
flet-pkg create --type auto --flutter-package onesignal_flutter --output .
```

### Examples

Auto-detect extension type:

```bash
flet-pkg create -t auto -f onesignal_flutter
```

Create a service extension:

```bash
flet-pkg create -t service -f onesignal_flutter
```

Create a UI control extension in a specific directory:

```bash
flet-pkg create -t ui_control -f flutter_map -o ~/projects
```

Use a local Flutter package (skip download):

```bash
flet-pkg create -t auto -f my_package -l ./path/to/my_package
```

With AI refinement (Ollama, local):

```bash
flet-pkg create -f shimmer --ai-refine
```

With AI refinement (Anthropic):

```bash
export ANTHROPIC_API_KEY=sk-...
flet-pkg create -f shimmer --ai-refine --ai-provider anthropic
```

Verbose output with coverage breakdown:

```bash
flet-pkg create -f onesignal_flutter -v
```

### Validation rules

| Field | Rule |
|-------|------|
| Flutter package | Lowercase, underscores, starts with letter (`[a-z][a-z0-9_]*`) |
| Project name | Lowercase, hyphens, starts with letter (`[a-z][a-z0-9-]*`) |
| Package name | Valid Python identifier (`[a-z][a-z0-9_]*`) |
| Control class name | PascalCase (`[A-Z][a-zA-Z0-9]*`) |
