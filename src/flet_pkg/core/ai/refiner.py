"""AI refinement orchestrator.

Coordinates the four-step pipeline:
1. Gap Report (deterministic)
2. Architect (LLM — reasons about improvements)
3. Editor (LLM — produces search/replace edits)
4. Validator (deterministic — syntax check + retry loop)
"""

from __future__ import annotations

import asyncio
import difflib
from pathlib import Path
from typing import Any

from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table as RichGrid
from rich.text import Text

from flet_pkg.core.ai.agent import (
    ArchitectDeps,
    EditorDeps,
    apply_edits,
    build_architect_agent,
    build_editor_agent,
    validate_python_syntax,
)
from flet_pkg.core.ai.config import AIConfig
from flet_pkg.core.ai.gap_analyzer import GapAnalyzer
from flet_pkg.core.ai.models import RefinementResult
from flet_pkg.core.ai.provider import create_model
from flet_pkg.core.models import DartPackageAPI, GenerationPlan

MAX_RETRIES = 2


class AIRefiner:
    """Orchestrates AI-powered code refinement.

    Uses the Architect/Editor pattern:
    - Architect reasons about WHAT to fix (structured plan)
    - Editor produces HOW to fix it (search/replace edits)
    - Validator checks syntax and retries on failure
    """

    def __init__(self, config: AIConfig):
        """Initialise the refiner with an AI configuration.

        Args:
            config: Provider and model settings for the LLM.
        """
        self.config = config
        self._model: Any = None

    def _get_model(self) -> Any:
        """Lazily create and return the pydantic-ai model instance."""
        if self._model is None:
            self._model = create_model(self.config)
        return self._model

    def refine(
        self,
        api: DartPackageAPI,
        plan: GenerationPlan,
        generated_files: dict[str, str],
        extension_type: str,
        package_path: Path | None = None,
        verbose: bool = False,
    ) -> RefinementResult:
        """Run the full AI refinement pipeline.

        Args:
            api: Parsed Dart package API.
            plan: Generation plan from the analyzer.
            generated_files: Dict of filename → content from generators.
            extension_type: "service" or "ui_control".
            package_path: Path to the downloaded Flutter package source.
            verbose: If True, print detailed progress at each step.

        Returns:
            RefinementResult with gap report, edits applied, and validation status.
        """
        return asyncio.run(
            self._refine_async(api, plan, generated_files, extension_type, package_path, verbose)
        )

    async def _refine_async(
        self,
        api: DartPackageAPI,
        plan: GenerationPlan,
        generated_files: dict[str, str],
        extension_type: str,
        package_path: Path | None = None,
        verbose: bool = False,
    ) -> RefinementResult:
        """Async implementation of the refinement pipeline."""
        from flet_pkg.ui.console import console

        # Step 1: Gap Report (deterministic — no LLM)
        gap_analyzer = GapAnalyzer()
        gap_report = gap_analyzer.analyze(api, plan, extension_type)

        if verbose:
            console.print(
                f"    [cyan]├─ Gap Report:[/cyan] {len(gap_report.gaps)} gaps, "
                f"{gap_report.feasible_gaps} feasible, "
                f"{gap_report.coverage_pct:.1f}%"
            )
            for gap in gap_report.gaps:
                if gap.feasible:
                    console.print(f"    [dim]│    {gap.kind.value}: {gap.dart_name}[/dim]")
                else:
                    console.print(
                        f"    [dim]│    {gap.kind.value}: {gap.dart_name}"
                        f" [yellow]\\[infeasible][/yellow][/dim]"
                    )

        if gap_report.feasible_gaps == 0:
            return RefinementResult(
                gap_report=gap_report,
                overall_assessment="No feasible gaps found — code is already well-covered.",
                validation_passed=True,
            )

        model = self._get_model()

        # Collect Dart source snippets for context
        dart_sources: dict[str, str] = {}
        if package_path and package_path.exists():
            for dart_file in package_path.rglob("*.dart"):
                try:
                    relative = str(dart_file.relative_to(package_path))
                    dart_sources[relative] = dart_file.read_text(encoding="utf-8")
                except Exception:
                    pass

        # Step 2: Architect (LLM — reason about gaps)
        architect_agent = build_architect_agent(model)
        architect_deps = ArchitectDeps(
            gap_report=gap_report,
            dart_sources=dart_sources,
            generated_files=generated_files,
        )

        architect_prompt = (
            f"Analyze the gap report for the '{plan.flutter_package}' Flutter package "
            f"({extension_type} extension). There are {gap_report.feasible_gaps} feasible gaps "
            f"out of {len(gap_report.gaps)} total. "
            f"Use the tools to inspect the gaps and generated files, then produce "
            f"an improvement plan."
        )

        if verbose:
            spinner = _tree_spinner("Architect analyzing gaps...")
            with Live(spinner, console=console, refresh_per_second=10, transient=True):
                architect_result = await architect_agent.run(architect_prompt, deps=architect_deps)
        else:
            architect_result = await architect_agent.run(architect_prompt, deps=architect_deps)
        architect_plan = architect_result.output

        # Track token usage
        total_input_tokens = 0
        total_output_tokens = 0
        arch_usage = architect_result.usage()
        total_input_tokens += arch_usage.request_tokens or 0
        total_output_tokens += arch_usage.response_tokens or 0

        if verbose:
            n = len(architect_plan.suggestions)
            console.print(f"    [cyan]├─ Architect:[/cyan] {n} suggestion(s)")
            for s in architect_plan.suggestions:
                console.print(
                    f"    [dim]│    [/dim][bold]\\[P{s.priority}][/bold] "
                    f"[dim]{s.target_file}: {s.description}[/dim]"
                )

        if not architect_plan.suggestions:
            return RefinementResult(
                gap_report=gap_report,
                architect_plan=architect_plan,
                overall_assessment="Architect found no actionable improvements.",
                validation_passed=True,
            )

        # Step 3 + 4: Editor (LLM) + Validator (retry loop)
        editor_agent = build_editor_agent(model)
        current_files = dict(generated_files)
        total_applied = 0
        total_failed = 0
        validation_passed = False
        all_diffs: list[tuple[str, str]] = []

        for attempt in range(1 + MAX_RETRIES):
            editor_deps = EditorDeps(
                architect_plan=architect_plan,
                file_contents=current_files,
                feedback="" if attempt == 0 else "Previous attempt had errors. Fix and retry.",
            )

            suggestions_text = "\n".join(
                f"- [{s.priority}] {s.target_file}: {s.description}"
                for s in architect_plan.suggestions
            )

            editor_prompt = (
                f"Apply these improvements to the generated files:\n\n{suggestions_text}\n\n"
                f"Use the tools to read file contents, then produce search/replace edits."
            )
            if editor_deps.feedback:
                editor_prompt += f"\n\nFeedback from previous attempt: {editor_deps.feedback}"

            if verbose:
                with Live(
                    _tree_spinner(f"Editor applying improvements (attempt {attempt + 1})..."),
                    console=console,
                    refresh_per_second=10,
                    transient=True,
                ):
                    editor_result = await editor_agent.run(editor_prompt, deps=editor_deps)
            else:
                editor_result = await editor_agent.run(editor_prompt, deps=editor_deps)

            # Track editor token usage
            ed_usage = editor_result.usage()
            total_input_tokens += ed_usage.request_tokens or 0
            total_output_tokens += ed_usage.response_tokens or 0

            # Snapshot before applying edits
            before_files = dict(current_files)

            # Apply edits
            modified_files, applied, failed = apply_edits(editor_result.output.edits, current_files)
            total_applied += applied
            total_failed += failed

            # Generate unified diffs for modified files
            attempt_diffs = _compute_diffs(before_files, modified_files)
            all_diffs.extend(attempt_diffs)

            if verbose:
                console.print(
                    f"    [cyan]├─ Editor[/cyan] (attempt {attempt + 1}): "
                    f"{applied} applied, {failed} failed"
                )
                # Show colored diffs
                for filename, diff_text in attempt_diffs:
                    for line in diff_text.splitlines():
                        colored = _colorize_diff_line(line)
                        console.print(f"    [dim]│[/dim]    {colored}")

            # Validate
            errors = validate_python_syntax(modified_files)
            if not errors:
                current_files = modified_files
                validation_passed = True
                if verbose:
                    console.print("    [cyan]├─ Validation:[/cyan] [green]passed ✓[/green]")
                break

            if verbose:
                console.print(
                    f"    [cyan]├─ Validation:[/cyan] [red]FAILED ✗[/red] ({len(errors)} error(s))"
                )
                for err in errors[:5]:
                    console.print(f"    [dim]│    {err}[/dim]")

            # Feed errors back for retry
            editor_deps.feedback = "Validation errors:\n" + "\n".join(errors)

        # Detect pending suggestions (not applied by Editor)
        files_with_diffs = {fname for fname, _ in all_diffs}
        pending = [s for s in architect_plan.suggestions if s.target_file not in files_with_diffs]

        if verbose and pending:
            console.print("    [cyan]├─ Pending suggestions (not applied):[/cyan]")
            for s in pending:
                console.print(
                    f"    [dim]│[/dim]    [bold]\\[P{s.priority}][/bold] "
                    f"[dim]{s.target_file}: {s.description}[/dim]"
                )

        # Update generated_files in-place with refined content
        if validation_passed:
            generated_files.update(current_files)

        if verbose:

            def _fmt_tokens(n: int) -> str:
                return f"{n / 1000:.1f}K" if n >= 1000 else str(n)

            total = total_input_tokens + total_output_tokens
            console.print(
                f"    [cyan]└─ Tokens:[/cyan] input {_fmt_tokens(total_input_tokens)}, "
                f"output {_fmt_tokens(total_output_tokens)} "
                f"[dim](total {_fmt_tokens(total)})[/dim]"
            )

        return RefinementResult(
            gap_report=gap_report,
            architect_plan=architect_plan,
            edits_applied=total_applied,
            edits_failed=total_failed,
            validation_passed=validation_passed,
            overall_assessment=(
                f"Applied {total_applied} edits ({total_failed} failed). "
                f"Validation: {'passed' if validation_passed else 'FAILED'}."
            ),
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            file_diffs=all_diffs,
            pending_suggestions=pending,
        )


def _compute_diffs(before: dict[str, str], after: dict[str, str]) -> list[tuple[str, str]]:
    """Compute unified diffs for files that changed."""
    diffs: list[tuple[str, str]] = []
    for filename in after:
        old = before.get(filename, "")
        new = after[filename]
        if old == new:
            continue
        diff_lines = list(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new.splitlines(keepends=True),
                fromfile=f"a/{filename}",
                tofile=f"b/{filename}",
            )
        )
        if diff_lines:
            diffs.append((filename, "".join(diff_lines)))
    return diffs


def _tree_spinner(label: str) -> RichGrid:
    """Create a Rich renderable with the spinner aligned to the tree prefix."""
    spinner = Spinner("dots")
    t = RichGrid.grid(padding=0)
    t.add_row(Text("    ├─ ", style="cyan"), spinner, Text(f" {label}", style="cyan"))
    return t


def _colorize_diff_line(line: str) -> str:
    """Apply Rich markup to a single diff line."""
    if line.startswith("+++") or line.startswith("---"):
        return f"[bold]{line}[/bold]"
    if line.startswith("@@"):
        return f"[cyan]{line}[/cyan]"
    if line.startswith("+"):
        return f"[green]{line}[/green]"
    if line.startswith("-"):
        return f"[red]{line}[/red]"
    return line
