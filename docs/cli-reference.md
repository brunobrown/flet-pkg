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
| `--type` | `-t` | `TEXT` | *(interactive)* | Extension type: `service` or `ui_control` |
| `--flutter-package` | `-f` | `TEXT` | *(interactive)* | Flutter package name from pub.dev |
| `--output` | `-o` | `PATH` | Current dir | Output directory |

### Interactive mode

When options are omitted, `flet-pkg` prompts you interactively using Rich:

```bash
flet-pkg create
```

### Non-interactive mode

Pass all required options via flags:

```bash
flet-pkg create --type service --flutter-package onesignal_flutter --output .
```

### Examples

Create a service extension:

```bash
flet-pkg create -t service -f onesignal_flutter
```

Create a UI control extension in a specific directory:

```bash
flet-pkg create -t ui_control -f flutter_map -o ~/projects
```

### Validation rules

| Field | Rule |
|-------|------|
| Flutter package | Lowercase, underscores, starts with letter (`[a-z][a-z0-9_]*`) |
| Project name | Lowercase, hyphens, starts with letter (`[a-z][a-z0-9-]*`) |
| Package name | Valid Python identifier (`[a-z][a-z0-9_]*`) |
| Control class name | PascalCase (`[A-Z][a-zA-Z0-9]*`) |
