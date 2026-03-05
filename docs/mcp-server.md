# MCP Server

flet-pkg includes a [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that exposes scaffolding and code generation capabilities to AI agents like Claude.

## Installation

The MCP server is included with flet-pkg. You also need the `mcp` dependency:

```bash
uv add flet-pkg[mcp]
```

## Running standalone

```bash
flet-pkg-mcp
```

This starts the server using stdio transport (the standard for MCP).

## Configuration

### Claude Code

Add to your project's `.mcp.json` or `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "flet-pkg": {
      "command": "uv",
      "args": ["run", "--from", "flet-pkg[mcp]", "flet-pkg-mcp"]
    }
  }
}
```

### Claude Desktop

Add to your Claude Desktop configuration file:

=== "macOS"

    `~/Library/Application Support/Claude/claude_desktop_config.json`

=== "Windows"

    `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "flet-pkg": {
      "command": "uv",
      "args": ["run", "--from", "flet-pkg[mcp]", "flet-pkg-mcp"]
    }
  }
}
```

## Tools

The server exposes 7 tools:

### `tool_derive_names`

Derive project/package/control names from a Flutter package name.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `flutter_package` | `str` | Flutter package name (e.g. `onesignal_flutter`) |

**Returns:** `project_name`, `package_name`, `control_name`, `control_name_snake`

### `tool_map_dart_type`

Convert a Dart type string to its Python/Flet equivalent.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `dart_type` | `str` | | Dart type to convert |
| `flet_aware` | `bool` | `False` | Use native Flet types for UI controls |

### `tool_fetch_metadata`

Get pub.dev package metadata (version, description, homepage).

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `flutter_package` | `str` | Flutter package name |

### `tool_detect_extension_type`

Auto-detect whether a Flutter package should be a `service` or `ui_control` extension.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `flutter_package` | `str` | Flutter package name |

**Returns:** `extension_type` (`"service"` or `"ui_control"`)

### `tool_scaffold`

Create a project skeleton from a template. Does **not** generate code — use `tool_run_pipeline` after this.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `template_name` | `str` | | `service` or `ui_control` |
| `flutter_package` | `str` | | Flutter package name |
| `project_name` | `str` | | Project directory name |
| `package_name` | `str` | | Python package name |
| `control_name` | `str` | | PascalCase control class name |
| `description` | `str` | `""` | Package description |
| `author` | `str` | `""` | Author name |
| `output_dir` | `str` | `"."` | Output directory path |
| `include_console` | `bool` | `True` | Include debug console module |

### `tool_run_pipeline`

Run the full generation pipeline: download → parse → analyze → generate → write.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `flutter_package` | `str` | | Flutter package name |
| `control_name` | `str` | | PascalCase control class name |
| `extension_type` | `str` | | `service` or `ui_control` |
| `project_dir` | `str` | | Path to scaffolded project |
| `package_name` | `str` | | Python package name |
| `description` | `str` | `""` | Package description |
| `control_name_snake` | `str` | `""` | Snake-case control name |
| `include_console` | `bool` | `True` | Include debug console module |
| `local_package_path` | `str \| None` | `None` | Local Flutter package path |

### `tool_analyze_gaps`

Analyze coverage gaps between a Flutter package and its generated code. Purely deterministic — no LLM required.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `flutter_package` | `str` | Flutter package name |
| `extension_type` | `str` | `service` or `ui_control` |

**Returns:** `coverage_pct`, `total_dart_api`, `total_generated`, `feasible_gaps`, and a list of `gaps`.

## Resources

### `flet-pkg://type-map`

Full Dart-to-Python type mapping table, including standard mappings, Flet-aware mappings, and skipped types.

### `flet-pkg://templates`

List of available template names and their paths.

## Prompts

### `scaffold_service`

Step-by-step guide to scaffold a Flet service extension. Takes `flutter_package` as input.

### `scaffold_ui_control`

Step-by-step guide to scaffold a Flet UI control extension. Takes `flutter_package` as input.

### `analyze_package`

Guide to analyze a Flutter package's coverage without scaffolding. Takes `flutter_package` and `extension_type`.

## Example prompts

With the MCP server configured, you can use natural language prompts in Claude Code or Claude Desktop:

### Analyze a service package

```
> Use the flet-pkg tool to analyze the Flutter package "onesignal_flutter" and tell me
  the extension type and coverage.
```

Claude will call:

1. `tool_detect_extension_type("onesignal_flutter")` → `service`
2. `tool_analyze_gaps("onesignal_flutter", "service")` → Coverage 95.4%

### Analyze a UI control package

```
> Use the flet-pkg tool to analyze the Flutter package "rive" and tell me the extension
  type and coverage.
```

Claude will call:

1. `tool_detect_extension_type("rive")` → `ui_control`
2. `tool_analyze_gaps("rive", "ui_control")` → Coverage report

### Scaffold a full project

```
> Use flet-pkg to scaffold a service extension for shared_preferences.
```

Claude will call:

1. `tool_derive_names("shared_preferences")`
2. `tool_fetch_metadata("shared_preferences")`
3. `tool_scaffold(template_name="service", ...)`
4. `tool_run_pipeline(extension_type="service", ...)`
