"""
Generation pipeline orchestrator.

Coordinates the full flow: download → parse → analyze → generate → write.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from flet_pkg.core.analyzer import PackageAnalyzer
from flet_pkg.core.downloader import PubDevDownloader
from flet_pkg.core.generators import (
    DartServiceGenerator,
    PythonControlGenerator,
    PythonInitGenerator,
    PythonSubModuleGenerator,
    PythonTypesGenerator,
)
from flet_pkg.core.models import DartPackageAPI, GenerationPlan
from flet_pkg.core.parser import parse_dart_package_api
from flet_pkg.ui.console import console

if TYPE_CHECKING:
    from flet_pkg.core.ai.config import AIConfig
    from flet_pkg.core.ai.models import GapReport, RefinementResult


@dataclass
class PipelineResult:
    """Result of a generation pipeline run."""

    project_dir: Path
    plan: GenerationPlan
    files_generated: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage_pct: float = 0.0
    gap_report: GapReport | None = None
    ai_coverage_pct: float | None = None


class GenerationPipeline:
    """Orchestrates the full code generation pipeline.

    Steps:
    1. Download Flutter package from pub.dev (or use local path)
    2. Parse Dart sources into DartPackageAPI
    3. Analyze API to produce GenerationPlan
    4. Run generators to produce Python + Dart files
    5. Write generated files to project directory (overwriting template stubs)
    """

    def __init__(self):
        """Initialise pipeline with default downloader and analyzer."""
        self.downloader = PubDevDownloader()
        self.analyzer = PackageAnalyzer()

    def run(
        self,
        flutter_package: str,
        control_name: str,
        extension_type: str,
        project_dir: Path,
        package_name: str,
        description: str = "",
        local_package: Path | None = None,
        control_name_snake: str = "",
        include_console: bool = True,
        ai_refine: bool = False,
        ai_provider: str | None = None,
        ai_model: str | None = None,
        verbose: bool = False,
    ) -> PipelineResult:
        """Run the full generation pipeline.

        Args:
            flutter_package: Flutter package name (pub.dev).
            control_name: PascalCase control class name.
            extension_type: ``"service"`` or ``"ui_control"``.
            project_dir: Path to the scaffolded project directory.
            package_name: Python package name.
            description: Package description.
            local_package: If set, use this local path instead of downloading.
            control_name_snake: Snake_case name for files (matches template context).
            include_console: Whether to include debug console module (default: True).
            ai_refine: If True, run AI refinement after generation.
            ai_provider: AI provider name (anthropic, openai, google, ollama).
            ai_model: AI model name override.
            verbose: If True, print detailed progress at each step.

        Returns:
            PipelineResult with generated file list and warnings.
        """
        result = PipelineResult(
            project_dir=project_dir,
            plan=GenerationPlan(
                control_name=control_name,
                package_name=package_name,
            ),
        )

        # Step 1: Get package source
        try:
            if local_package:
                package_path = local_package
                console.print(f"  [info]Using local package:[/info] {package_path}")
            else:
                package_path = self.downloader.download(flutter_package)
                console.print(f"  [success]Downloaded {flutter_package}[/success]")
        except Exception as e:
            result.warnings.append(f"Download failed: {e}")
            console.print(f"  [warning]Download failed: {e}[/warning]")
            return result

        # Step 2: Parse
        try:
            api = parse_dart_package_api(
                package_path,
                include_widgets=(extension_type == "ui_control"),
            )
            n_classes = len(api.classes)
            n_enums = len(api.enums)
            n_helpers = len(api.helper_classes)
            n_funcs = len(api.top_level_functions)
            parts = [f"{n_classes} classes", f"{n_enums} enums", f"{n_helpers} helper types"]
            if n_funcs:
                parts.append(f"{n_funcs} top-level functions")
            console.print(f"  [success]Parsed {', '.join(parts)}[/success]")
            if verbose:
                for cls in api.classes:
                    console.print(f"    [dim]class {cls.name}[/dim]")
                for enum in api.enums:
                    console.print(f"    [dim]enum {enum.name}[/dim]")
        except Exception as e:
            result.warnings.append(f"Parse failed: {e}")
            console.print(f"  [warning]Parse failed: {e}[/warning]")
            return result

        if not api.classes and not api.top_level_functions:
            result.warnings.append("No public classes or functions found in package.")
            console.print("  [warning]No public classes or functions found.[/warning]")
            return result

        # Step 3: Analyze
        try:
            plan = self.analyzer.analyze(
                api,
                control_name=control_name,
                extension_type=extension_type,
                flutter_package=flutter_package,
                package_name=package_name,
                description=description,
            )
            # Set control_name_snake from the template context
            plan.control_name_snake = control_name_snake
            plan.include_console = include_console
            result.plan = plan

            # Resolve re-exported types from platform_interface packages
            if api.reexported_types:
                try:
                    self.analyzer.resolve_platform_types(api, plan)
                except Exception as e:
                    result.warnings.append(f"Platform type resolution failed: {e}")

            n_methods = len(plan.main_methods) + sum(len(s.methods) for s in plan.sub_modules)
            console.print(
                f"  [success]Analyzed: {n_methods} methods, "
                f"{len(plan.sub_modules)} sub-modules, "
                f"{len(plan.events)} events[/success]"
            )
            if plan.sub_controls:
                n_sub = len(plan.sub_controls)
                names = ", ".join(sc.control_name for sc in plan.sub_controls)
                console.print(f"  [success]Detected {n_sub} sub-control(s): {names}[/success]")
            if plan.widget_family_variants:
                n_var = len(plan.widget_family_variants)
                console.print(f"  [success]Widget family: {n_var} variants[/success]")
            if plan.sibling_widgets:
                sib_names = ", ".join(s.control_name for s in plan.sibling_widgets)
                console.print(f"  [success]Sibling widgets: {sib_names}[/success]")
            if verbose:
                for m in plan.main_methods:
                    console.print(f"    [dim]method: {m.python_name}()[/dim]")
                for sub in plan.sub_modules:
                    console.print(f"    [dim]sub-module: {sub.module_name}[/dim]")
                    for m in sub.methods:
                        console.print(f"      [dim]{m.python_name}()[/dim]")
                for ev in plan.events:
                    console.print(f"    [dim]event: {ev.python_attr_name}[/dim]")
                for p in getattr(plan, "properties", []):
                    console.print(f"    [dim]property: {p.python_name}[/dim]")
        except Exception as e:
            result.warnings.append(f"Analysis failed: {e}")
            console.print(f"  [warning]Analysis failed: {e}[/warning]")
            return result

        # Step 4: Generate
        generators = [
            PythonControlGenerator(),
            PythonSubModuleGenerator(),
            PythonTypesGenerator(),
            PythonInitGenerator(),
            DartServiceGenerator(),
        ]

        all_files: dict[str, str] = {}
        for gen in generators:
            try:
                files = gen.generate(plan)
                all_files.update(files)
            except Exception as e:
                result.warnings.append(f"Generator {gen.__class__.__name__} failed: {e}")

        if verbose:
            py_files = [f for f in all_files if f.endswith(".py")]
            dart_files = [f for f in all_files if f.endswith(".dart")]
            console.print(
                f"    [dim]{len(py_files)} Python files, {len(dart_files)} Dart files[/dim]"
            )
            for fname in sorted(all_files):
                console.print(f"    [dim]{fname}[/dim]")

        # Step 4.1: Gap Analysis (deterministic — no AI)
        try:
            gap_report = self._run_gap_analysis(api, plan, extension_type)
            result.coverage_pct = gap_report.coverage_pct
            result.gap_report = gap_report
        except Exception as e:
            result.warnings.append(f"Gap analysis failed: {e}")

        # Step 4.5: AI Refinement (optional)
        if ai_refine:
            try:
                from flet_pkg.core.ai.config import AIConfig
                from flet_pkg.core.ai.refiner import AIRefiner

                config = AIConfig.load(provider=ai_provider, model=ai_model)
                if config.is_available():
                    label = "Running AI refinement..."
                    if verbose:
                        label += f" [dim]({config.provider} / {config.model})[/dim]"
                    console.print(f"  [info]{label}[/info]")
                    refiner = AIRefiner(config)
                    ai_result = refiner.refine(
                        api,
                        plan,
                        all_files,
                        extension_type,
                        package_path,
                        verbose=verbose,
                    )
                    if ai_result.edits_applied > 0:
                        console.print(
                            f"  [success]AI refined: {ai_result.edits_applied} edits applied"
                            f"[/success]"
                        )
                    if not ai_result.validation_passed and ai_result.edits_applied > 0:
                        result.warnings.append("AI edits failed validation — using originals")
                    # Estimate post-AI coverage from applied edits
                    if ai_result.validation_passed and ai_result.edits_applied > 0:
                        gap = ai_result.gap_report
                        if gap.total_dart_api > 0:
                            new_mapped = gap.total_generated + ai_result.edits_applied
                            result.ai_coverage_pct = min(
                                new_mapped / gap.total_dart_api * 100, 100.0
                            )
                    # Always write .ai-review.md when AI refinement runs
                    _write_ai_review(project_dir, config, ai_result)
                else:
                    console.print("  [warning]AI skipped: no API key configured[/warning]")
            except ImportError:
                console.print("  [warning]AI skipped: install with uv add flet-pkg[ai][/warning]")
            except Exception as e:
                import logging

                logging.debug("AI refinement error: %s", e, exc_info=True)
                result.warnings.append(_format_ai_error(e))

        # Step 5: Write files (overwriting template stubs)
        python_pkg_dir = project_dir / "src" / package_name
        dart_src_dir = project_dir / "src" / "flutter" / package_name / "lib" / "src"

        dart_lib_dir = project_dir / "src" / "flutter" / package_name / "lib"

        for filename, content in all_files.items():
            if filename == "extension.dart":
                # extension.dart lives at lib/extension.dart (not lib/src/)
                target = dart_lib_dir / filename
            elif filename.endswith(".dart"):
                target = dart_src_dir / filename
            else:
                target = python_pkg_dir / filename

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            result.files_generated.append(str(target.relative_to(project_dir)))

        # Clean up template stubs that were replaced by generated files
        self._cleanup_stubs(project_dir, package_name, all_files, result)

        console.print(f"  [success]Generated {len(result.files_generated)} files[/success]")

        return result

    @staticmethod
    def _run_gap_analysis(
        api: DartPackageAPI,
        plan: GenerationPlan,
        extension_type: str,
    ) -> GapReport:
        """Run deterministic gap analysis (no AI/LLM)."""
        from flet_pkg.core.ai.gap_analyzer import GapAnalyzer

        analyzer = GapAnalyzer()
        return analyzer.analyze(api, plan, extension_type)

    def _cleanup_stubs(
        self,
        project_dir: Path,
        package_name: str,
        generated_files: dict[str, str],
        result: PipelineResult,
    ) -> None:
        """Remove template stub files that conflict with generated files.

        The template creates stub files like ``onesignal.py`` and
        ``onesignal_service.dart``, but the generators may produce files
        with the same purpose under different names. This method removes
        orphaned stubs to prevent import conflicts.
        """
        python_pkg_dir = project_dir / "src" / package_name
        dart_src_dir = project_dir / "src" / "flutter" / package_name / "lib" / "src"

        generated_py = {f for f in generated_files if f.endswith(".py")}
        generated_dart = {f for f in generated_files if f.endswith(".dart")}

        # Check for conflicting Python stubs
        for py_file in python_pkg_dir.glob("*.py"):
            name = py_file.name
            if name in generated_py or name == "__init__.py":
                continue
            # Check if this is a stub with TODO content (from template)
            try:
                content = py_file.read_text(encoding="utf-8")
                if "TODO" in content or "example_method" in content:
                    py_file.unlink()
            except Exception:
                pass

        # Check for conflicting Dart stubs
        # Don't protect extension.dart if we generated our own
        protect_extension = "extension.dart" not in generated_files
        for dart_file in dart_src_dir.glob("*.dart"):
            name = dart_file.name
            if name in generated_dart or (name == "extension.dart" and protect_extension):
                continue
            try:
                content = dart_file.read_text(encoding="utf-8")
                if "TODO" in content or "example_method" in content:
                    dart_file.unlink()
            except Exception:
                pass


def _write_ai_review(
    project_dir: Path,
    config: AIConfig,
    ai_result: RefinementResult,
) -> None:
    """Write .ai-review.md with diffs and pending suggestions."""
    lines: list[str] = []
    lines.append("# AI Review Report\n")

    # Header
    lines.append(f"- **Provider:** {config.provider}")
    lines.append(f"- **Model:** {config.model}")
    lines.append(f"- **Coverage:** {ai_result.gap_report.coverage_pct:.1f}%")
    lines.append(f"- **Edits applied:** {ai_result.edits_applied}")
    lines.append(f"- **Edits failed:** {ai_result.edits_failed}")
    status = "passed" if ai_result.validation_passed else "FAILED"
    lines.append(f"- **Validation:** {status}")
    lines.append("")

    # Diffs section
    if ai_result.file_diffs:
        lines.append("## Diffs\n")
        for filename, diff_text in ai_result.file_diffs:
            lines.append(f"### {filename}\n")
            lines.append("```diff")
            lines.append(diff_text.rstrip())
            lines.append("```\n")
    else:
        lines.append("## Diffs\n")
        lines.append("_No files were modified._\n")

    # Pending suggestions
    if ai_result.pending_suggestions:
        lines.append("## Suggestions (not applied)\n")
        for s in ai_result.pending_suggestions:
            lines.append(f"- **[P{s.priority}] {s.target_file}:** {s.description}")
        lines.append("")

    review_path = project_dir / ".ai-review.md"
    review_path.write_text("\n".join(lines), encoding="utf-8")
    console.print("  [info]Review saved: .ai-review.md[/info]")


def _format_ai_error(exc: Exception) -> str:
    """Format AI provider errors into user-friendly messages."""
    msg = str(exc)
    lower = msg.lower()

    if "insufficient_quota" in msg or "billing" in lower:
        return "AI skipped: API quota exceeded. Check your billing at your provider's dashboard."
    if "401" in msg or "invalid_api_key" in msg or "Unauthorized" in msg:
        return "AI skipped: invalid API key. Verify your API key environment variable is correct."
    if "rate_limit" in msg or "429" in msg:
        return "AI skipped: rate limit reached. Try again later."
    if "timeout" in lower or "timed out" in lower:
        return "AI skipped: request timed out. Try again later."
    if "context length" in lower or "too long" in lower:
        return (
            "AI skipped: input too long for the model's context window. "
            "Try a model with a larger context or reduce the package size."
        )
    if "maximum retries" in lower or "output validation" in lower:
        return (
            "AI skipped: model failed to produce valid structured output. "
            "Try a larger model (e.g. --ai-model qwen2.5-coder:32b) "
            "or use a cloud provider (--ai-provider anthropic)."
        )
    if "500" in msg or "server_error" in lower or "internal server error" in lower:
        return (
            "AI skipped: provider returned a server error (500). "
            "This is a transient issue on the provider's side. Try again later."
        )

    return f"AI refinement failed: {msg}"
