"""MCP server for flet-pkg.

Exposes scaffolding and code generation capabilities to AI agents
via the Model Context Protocol (tools, resources, prompts).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession

from flet_pkg.core.downloader import PubDevDownloader
from flet_pkg.core.scaffolder import TEMPLATE_DIR
from flet_pkg.core.type_map import (
    _FLET_TYPE_MAP,
    _TYPE_MAP,
    map_dart_type,
    map_dart_type_flet,
)
from flet_pkg.core.validators import derive_names, validate_flutter_package
from flet_pkg.mcp._serializers import to_dict

# ---------------------------------------------------------------------------
# Lifespan — share a single PubDevDownloader instance across tools
# ---------------------------------------------------------------------------


@dataclass
class AppContext:
    downloader: PubDevDownloader


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Provide a shared ``PubDevDownloader`` instance for the server lifetime."""
    yield AppContext(downloader=PubDevDownloader())


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="flet-pkg",
    instructions=("Scaffold and analyze Flet extension packages from Flutter packages on pub.dev."),
    lifespan=app_lifespan,
)

# Type alias for tool context
ToolContext = Context[ServerSession, AppContext]


def _get_downloader(ctx: ToolContext) -> PubDevDownloader:
    """Extract the shared downloader from the MCP tool context."""
    return ctx.request_context.lifespan_context.downloader


# ---------------------------------------------------------------------------
# Tool 1: derive_names
# ---------------------------------------------------------------------------


@mcp.tool()
def tool_derive_names(flutter_package: str) -> dict:
    """Derive project/package/control names from a Flutter package name.

    Args:
        flutter_package: A pub.dev package name (e.g. ``onesignal_flutter``).

    Returns:
        Dict with ``project_name``, ``package_name``, ``control_name``,
        and ``control_name_snake``.
    """
    error = validate_flutter_package(flutter_package)
    if error:
        raise ValueError(f"Invalid flutter_package '{flutter_package}': {error}")
    names = derive_names(flutter_package)
    return to_dict(names)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tool 2: map_dart_type
# ---------------------------------------------------------------------------


@mcp.tool()
def tool_map_dart_type(dart_type: str, flet_aware: bool = False) -> dict:
    """Convert a Dart type string to its Python/Flet equivalent.

    Args:
        dart_type: Dart type string (e.g. ``"List<String>"``, ``"bool?"``).
        flet_aware: Use native Flet types (``ft.Alignment``, ``ft.Color``, etc.)
            for UI control extensions.

    Returns:
        Dict with ``dart_type``, ``python_type``, and ``skipped`` flag.
    """
    if flet_aware:
        result = map_dart_type_flet(dart_type)
        skipped = result is None
        return {
            "dart_type": dart_type,
            "python_type": result if result is not None else "SKIPPED",
            "skipped": skipped,
        }
    return {
        "dart_type": dart_type,
        "python_type": map_dart_type(dart_type),
        "skipped": False,
    }


# ---------------------------------------------------------------------------
# Tool 3: fetch_metadata
# ---------------------------------------------------------------------------


@mcp.tool()
def tool_fetch_metadata(flutter_package: str, ctx: ToolContext) -> dict:
    """Get pub.dev package metadata (version, description, homepage).

    Args:
        flutter_package: A pub.dev package name.
        ctx: MCP tool context for dependency injection.

    Returns:
        Dict with package metadata fields.
    """
    downloader = _get_downloader(ctx)
    metadata = downloader.fetch_metadata(flutter_package)
    return to_dict(metadata)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tool 4: detect_extension_type
# ---------------------------------------------------------------------------


@mcp.tool()
def tool_detect_extension_type(flutter_package: str, ctx: ToolContext) -> dict:
    """Auto-detect whether a Flutter package should be a service or ui_control extension.

    Downloads the package (cached) and scans for widget classes.

    Args:
        flutter_package: A pub.dev package name.
        ctx: MCP tool context for dependency injection.

    Returns:
        Dict with ``flutter_package`` and ``extension_type``.
    """
    from flet_pkg.core.parser import detect_extension_type

    downloader = _get_downloader(ctx)
    package_path = downloader.download(flutter_package)
    ext_type = detect_extension_type(package_path)
    return {"flutter_package": flutter_package, "extension_type": ext_type}


# ---------------------------------------------------------------------------
# Tool 5: scaffold
# ---------------------------------------------------------------------------


@mcp.tool()
def tool_scaffold(
    template_name: str,
    flutter_package: str,
    project_name: str,
    package_name: str,
    control_name: str,
    description: str = "",
    author: str = "",
    output_dir: str = ".",
    include_console: bool = True,
) -> dict:
    """Create a project skeleton from a template (service or ui_control).

    Does NOT generate code — only scaffolds the directory structure with
    template stubs. Use run_pipeline after this to fill in the generated code.
    """
    from flet_pkg.core.scaffolder import Scaffolder
    from flet_pkg.core.validators import _camel_to_snake

    context = {
        "project_name": project_name,
        "package_name": package_name,
        "control_name": control_name,
        "control_name_snake": _camel_to_snake(control_name).lower(),
        "flutter_package": flutter_package,
        "description": description,
        "author": author,
        "include_console": include_console,
    }

    out = Path(output_dir).resolve()
    scaffolder = Scaffolder(template_name, context, out)
    project_dir = scaffolder.generate()

    files = sorted(str(p.relative_to(project_dir)) for p in project_dir.rglob("*") if p.is_file())
    return {"project_dir": str(project_dir), "files": files}


# ---------------------------------------------------------------------------
# Tool 6: run_pipeline
# ---------------------------------------------------------------------------


@mcp.tool()
def tool_run_pipeline(
    flutter_package: str,
    control_name: str,
    extension_type: str,
    project_dir: str,
    package_name: str,
    description: str = "",
    control_name_snake: str = "",
    include_console: bool = True,
    local_package_path: str | None = None,
) -> dict:
    """Run the full generation pipeline: download → parse → analyze → generate → write.

    Overwrites template stubs in project_dir with auto-generated code.
    Set local_package_path to use a local Flutter package instead of downloading.
    """
    from flet_pkg.core.pipeline import GenerationPipeline

    pipeline = GenerationPipeline()
    result = pipeline.run(
        flutter_package=flutter_package,
        control_name=control_name,
        extension_type=extension_type,
        project_dir=Path(project_dir),
        package_name=package_name,
        description=description,
        local_package=Path(local_package_path) if local_package_path else None,
        control_name_snake=control_name_snake,
        include_console=include_console,
    )

    plan = result.plan
    return {
        "project_dir": str(result.project_dir),
        "files_generated": result.files_generated,
        "warnings": result.warnings,
        "plan_summary": {
            "control_name": plan.control_name,
            "base_class": plan.base_class,
            "n_methods": len(plan.main_methods),
            "n_events": len(plan.events),
            "n_enums": len(plan.enums),
            "n_sub_modules": len(plan.sub_modules),
            "n_sub_controls": len(plan.sub_controls),
            "n_properties": len(plan.properties),
        },
    }


# ---------------------------------------------------------------------------
# Tool 7: analyze_gaps
# ---------------------------------------------------------------------------


@mcp.tool()
def tool_analyze_gaps(
    flutter_package: str,
    extension_type: str,
    ctx: ToolContext,
) -> dict:
    """Analyze coverage gaps between a Flutter package and its generated code.

    Downloads the package, parses, analyzes, and runs deterministic gap analysis.
    No LLM is used — purely structural comparison.
    """
    from flet_pkg.core.ai.gap_analyzer import GapAnalyzer
    from flet_pkg.core.analyzer import PackageAnalyzer
    from flet_pkg.core.parser import parse_dart_package_api

    downloader = _get_downloader(ctx)
    package_path = downloader.download(flutter_package)

    api = parse_dart_package_api(
        package_path,
        include_widgets=(extension_type == "ui_control"),
    )

    analyzer = PackageAnalyzer()
    names = derive_names(flutter_package)
    plan = analyzer.analyze(
        api,
        control_name=names.control_name,
        extension_type=extension_type,
        flutter_package=flutter_package,
        package_name=names.package_name,
    )

    gap_analyzer = GapAnalyzer()
    report = gap_analyzer.analyze(api, plan, extension_type)

    return {
        "flutter_package": flutter_package,
        "extension_type": extension_type,
        "coverage_pct": round(report.coverage_pct, 1),
        "total_dart_api": report.total_dart_api,
        "total_generated": report.total_generated,
        "feasible_gaps": report.feasible_gaps,
        "gaps": [to_dict(g) for g in report.gaps],
    }


# ---------------------------------------------------------------------------
# Resource 1: type-map
# ---------------------------------------------------------------------------


@mcp.resource("flet-pkg://type-map")
def resource_type_map() -> dict:
    """Full Dart-to-Python type mapping table.

    Includes standard mappings, Flet-aware mappings, and skipped types.
    """
    flet_map = {}
    skipped = []
    for dart_type, python_type in _FLET_TYPE_MAP.items():
        if python_type is None:
            skipped.append(dart_type)
        else:
            flet_map[dart_type] = python_type

    return {
        "standard": dict(_TYPE_MAP),
        "flet_aware": flet_map,
        "skipped": skipped,
    }


# ---------------------------------------------------------------------------
# Resource 2: templates
# ---------------------------------------------------------------------------


@mcp.resource("flet-pkg://templates")
def resource_templates() -> dict:
    """Available template names and their paths."""
    templates = sorted(d.name for d in TEMPLATE_DIR.iterdir() if d.is_dir())
    return {"templates": templates}


# ---------------------------------------------------------------------------
# Prompt 1: scaffold_service
# ---------------------------------------------------------------------------


@mcp.prompt()
def scaffold_service(flutter_package: str) -> str:
    """Step-by-step guide to scaffold a Flet service extension."""
    pkg = flutter_package
    return (
        f"Scaffold a Flet **service** extension for `{pkg}`.\n\n"
        "Follow these steps:\n\n"
        f'1. Call `tool_derive_names("{pkg}")` to get naming conventions.\n'
        f'2. Call `tool_fetch_metadata("{pkg}")` to get the description.\n'
        f'3. Call `tool_scaffold(template_name="service", ...)` with derived names.\n'
        f'4. Call `tool_run_pipeline(extension_type="service", ...)` to generate.\n'
        f'5. Optionally call `tool_analyze_gaps("{pkg}", "service")` for coverage.\n\n'
        "Report the generated files and any warnings."
    )


# ---------------------------------------------------------------------------
# Prompt 2: scaffold_ui_control
# ---------------------------------------------------------------------------


@mcp.prompt()
def scaffold_ui_control(flutter_package: str) -> str:
    """Step-by-step guide to scaffold a Flet UI control extension."""
    pkg = flutter_package
    return (
        f"Scaffold a Flet **UI control** extension for `{pkg}`.\n\n"
        "Follow these steps:\n\n"
        f'1. Call `tool_derive_names("{pkg}")` to get naming conventions.\n'
        f'2. Call `tool_fetch_metadata("{pkg}")` to get the description.\n'
        f'3. Call `tool_scaffold(template_name="ui_control", ...)` with derived names.\n'
        f'4. Call `tool_run_pipeline(extension_type="ui_control", ...)` to generate.\n'
        f'5. Optionally call `tool_analyze_gaps("{pkg}", "ui_control")` for coverage.\n\n'
        "Report the generated files and any warnings."
    )


# ---------------------------------------------------------------------------
# Prompt 3: analyze_package
# ---------------------------------------------------------------------------


@mcp.prompt()
def analyze_package(flutter_package: str, extension_type: str = "service") -> str:
    """Guide to analyze a Flutter package's coverage without scaffolding."""
    pkg = flutter_package
    ext = extension_type
    return (
        f"Analyze the Flutter package `{pkg}` as a `{ext}` extension.\n\n"
        "Follow these steps:\n\n"
        f'1. Call `tool_fetch_metadata("{pkg}")` to get package info.\n'
        f'2. Call `tool_detect_extension_type("{pkg}")` to verify the type.\n'
        f'3. Call `tool_analyze_gaps("{pkg}", "{ext}")` for coverage.\n\n'
        "Report:\n"
        "- Coverage percentage\n"
        "- Number of feasible gaps\n"
        "- List of gaps with their kind, Dart name, and reason."
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the flet-pkg MCP server (stdio transport)."""
    mcp.run()
