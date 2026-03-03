"""AI refinement orchestrator.

Coordinates the four-step pipeline:
1. Gap Report (deterministic)
2. Architect (LLM — reasons about improvements)
3. Editor (LLM — produces search/replace edits)
4. Validator (deterministic — syntax check + retry loop)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

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
        self.config = config
        self._model: Any = None

    def _get_model(self) -> Any:
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
    ) -> RefinementResult:
        """Run the full AI refinement pipeline.

        Args:
            api: Parsed Dart package API.
            plan: Generation plan from the analyzer.
            generated_files: Dict of filename → content from generators.
            extension_type: "service" or "ui_control".
            package_path: Path to the downloaded Flutter package source.

        Returns:
            RefinementResult with gap report, edits applied, and validation status.
        """
        return asyncio.run(
            self._refine_async(api, plan, generated_files, extension_type, package_path)
        )

    async def _refine_async(
        self,
        api: DartPackageAPI,
        plan: GenerationPlan,
        generated_files: dict[str, str],
        extension_type: str,
        package_path: Path | None = None,
    ) -> RefinementResult:
        """Async implementation of the refinement pipeline."""
        # Step 1: Gap Report (deterministic — no LLM)
        gap_analyzer = GapAnalyzer()
        gap_report = gap_analyzer.analyze(api, plan, extension_type)

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

        architect_result = await architect_agent.run(architect_prompt, deps=architect_deps)
        architect_plan = architect_result.output

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

            editor_result = await editor_agent.run(editor_prompt, deps=editor_deps)

            # Apply edits
            modified_files, applied, failed = apply_edits(editor_result.output.edits, current_files)
            total_applied += applied
            total_failed += failed

            # Validate
            errors = validate_python_syntax(modified_files)
            if not errors:
                current_files = modified_files
                validation_passed = True
                break

            # Feed errors back for retry
            editor_deps.feedback = "Validation errors:\n" + "\n".join(errors)

        # Update generated_files in-place with refined content
        if validation_passed:
            generated_files.update(current_files)

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
        )
