# CLI Reference

## Global options

```bash
flet-pkg --version    # Show version and exit
flet-pkg --help       # Show help
```

## `flet-pkg create`

Create a new Flet extension package.

```bash
flet-pkg create [OPTIONS]
```

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--type` | `-t` | `TEXT` | *(interactive)* | Extension type: `auto`, `service` or `ui_control` |
| `--flutter-package` | `-f` | `TEXT` | *(interactive)* | Flutter package name from pub.dev |
| `--output` | `-o` | `PATH` | Current dir | Output directory |
| `--analyze/--no-analyze` | | `BOOL` | `True` | Analyze Flutter package and generate rich code |
| `--local-package` | `-l` | `PATH` | | Path to a local Flutter package (skip download) |

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

### Validation rules

| Field | Rule |
|-------|------|
| Flutter package | Lowercase, underscores, starts with letter (`[a-z][a-z0-9_]*`) |
| Project name | Lowercase, hyphens, starts with letter (`[a-z][a-z0-9-]*`) |
| Package name | Valid Python identifier (`[a-z][a-z0-9_]*`) |
| Control class name | PascalCase (`[A-Z][a-zA-Z0-9]*`) |
