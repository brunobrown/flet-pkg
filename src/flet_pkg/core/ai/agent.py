"""Architect and Editor agents using pydantic-ai.

Two-agent pattern:
- **Architect**: Reasons about gaps, produces improvement plan (structured output)
- **Editor**: Produces precise search/replace edits (structured output)

All pydantic-ai imports are lazy — this module can be imported but will only
work when pydantic-ai is installed.
"""

from dataclasses import dataclass, field
from typing import Any

from flet_pkg.core.ai.models import (
    ArchitectPlan,
    EditorResult,
    FileEdit,
    GapReport,
)
from flet_pkg.core.ai.prompts import ARCHITECT_SYSTEM_PROMPT, EDITOR_SYSTEM_PROMPT

# ---------------------------------------------------------------------------
# Dependency containers (passed to agents at run time)
# ---------------------------------------------------------------------------


@dataclass
class ArchitectDeps:
    """Dependencies available to the Architect agent via tools."""

    gap_report: GapReport
    dart_sources: dict[str, str] = field(default_factory=dict)
    generated_files: dict[str, str] = field(default_factory=dict)


@dataclass
class EditorDeps:
    """Dependencies available to the Editor agent via tools."""

    architect_plan: ArchitectPlan
    file_contents: dict[str, str] = field(default_factory=dict)
    feedback: str = ""


# ---------------------------------------------------------------------------
# Agent builders (lazy — only call when pydantic-ai is installed)
# ---------------------------------------------------------------------------


def build_architect_agent(model: Any) -> Any:
    """Build the Architect agent with tools for gap inspection.

    Args:
        model: A pydantic-ai model instance.

    Returns:
        A pydantic-ai Agent configured for the Architect role.
    """
    from pydantic_ai import Agent, RunContext  # ty: ignore[unresolved-import]

    agent = Agent(
        model,
        deps_type=ArchitectDeps,
        output_type=ArchitectPlan,
        system_prompt=ARCHITECT_SYSTEM_PROMPT,
    )

    @agent.tool
    def get_gap_report(ctx: RunContext[ArchitectDeps]) -> str:
        """Get the full gap report as a formatted summary."""
        report = ctx.deps.gap_report
        lines = [report.summary(), "", "Gaps:"]
        for i, gap in enumerate(report.gaps):
            feasible = "feasible" if gap.feasible else "INFEASIBLE"
            lines.append(
                f"  [{i}] {gap.kind.value}: {gap.dart_name} "
                f"(type={gap.dart_type}, class={gap.dart_class}) "
                f"[{feasible}] — {gap.reason}"
            )
        return "\n".join(lines)

    @agent.tool
    def get_dart_source_snippet(ctx: RunContext[ArchitectDeps], class_name: str) -> str:
        """Get Dart source code for a specific class (first 200 lines)."""
        for filename, content in ctx.deps.dart_sources.items():
            if class_name in content:
                lines = content.split("\n")[:200]
                return f"// {filename}\n" + "\n".join(lines)
        return f"No Dart source found containing class '{class_name}'"

    @agent.tool
    def get_generated_file_summary(ctx: RunContext[ArchitectDeps]) -> str:
        """Get a summary of all generated files (names and line counts)."""
        lines = ["Generated files:"]
        for filename, content in ctx.deps.generated_files.items():
            n_lines = content.count("\n") + 1
            lines.append(f"  {filename}: {n_lines} lines")
        return "\n".join(lines)

    return agent


def build_editor_agent(model: Any) -> Any:
    """Build the Editor agent with tools for file inspection.

    Args:
        model: A pydantic-ai model instance.

    Returns:
        A pydantic-ai Agent configured for the Editor role.
    """
    from pydantic_ai import Agent, RunContext  # ty: ignore[unresolved-import]

    agent = Agent(
        model,
        deps_type=EditorDeps,
        output_type=EditorResult,
        system_prompt=EDITOR_SYSTEM_PROMPT,
    )

    @agent.tool
    def get_file_content(ctx: RunContext[EditorDeps], filename: str) -> str:
        """Get the full content of a generated file."""
        content = ctx.deps.file_contents.get(filename)
        if content is None:
            available = ", ".join(ctx.deps.file_contents.keys())
            return f"File '{filename}' not found. Available: {available}"
        return content

    @agent.tool
    def list_files(ctx: RunContext[EditorDeps]) -> str:
        """List all available generated files."""
        return "\n".join(ctx.deps.file_contents.keys())

    return agent


# ---------------------------------------------------------------------------
# Edit application + validation
# ---------------------------------------------------------------------------


def apply_edits(
    edits: list[FileEdit],
    files: dict[str, str],
) -> tuple[dict[str, str], int, int]:
    """Apply search/replace edits to file contents.

    Args:
        edits: List of FileEdit objects with search/replace strings.
        files: Dict mapping filename to file content.

    Returns:
        Tuple of (modified_files, applied_count, failed_count).
    """
    modified = dict(files)
    applied = 0
    failed = 0

    for edit in edits:
        if edit.filename not in modified:
            failed += 1
            continue

        content = modified[edit.filename]
        if edit.search not in content:
            failed += 1
            continue

        modified[edit.filename] = content.replace(edit.search, edit.replace, 1)
        applied += 1

    return modified, applied, failed


def validate_python_syntax(files: dict[str, str]) -> list[str]:
    """Validate Python files for syntax errors.

    Args:
        files: Dict mapping filename to file content.

    Returns:
        List of error messages (empty if all valid).
    """
    errors: list[str] = []
    for filename, content in files.items():
        if not filename.endswith(".py"):
            continue
        try:
            compile(content, filename, "exec")
        except SyntaxError as e:
            errors.append(f"{filename}:{e.lineno}: {e.msg}")
    return errors
