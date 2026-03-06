"""Data models for the AI refinement pipeline.

Uses Pydantic BaseModel for structured LLM output validation.
All models are importable without pydantic-ai installed (only pydantic needed
at runtime when AI features are used).
"""

from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# Gap Report (deterministic, Step 1 — no LLM)
# ---------------------------------------------------------------------------


class GapKind(str, Enum):
    """Classification of a coverage gap."""

    MISSING_METHOD = "missing_method"
    MISSING_PROPERTY = "missing_property"
    MISSING_ENUM = "missing_enum"
    MISSING_EVENT = "missing_event"
    TYPE_MISMATCH = "type_mismatch"
    INCOMPLETE_STUB = "incomplete_stub"


@dataclass
class GapItem:
    """A single coverage gap between Dart source and generated code."""

    kind: GapKind
    dart_name: str
    dart_type: str = ""
    dart_class: str = ""
    reason: str = ""
    feasible: bool = True
    context: str = ""


@dataclass
class GapReport:
    """Structured report of coverage gaps (deterministic output)."""

    flutter_package: str
    extension_type: str
    total_dart_api: int = 0
    total_generated: int = 0
    coverage_pct: float = 0.0
    gaps: list[GapItem] = field(default_factory=list)
    category_counts: dict[str, tuple[int, int]] = field(default_factory=dict)
    """Per-category (dart_api_count, generated_count) — e.g. {"Methods": (25, 24)}."""

    @property
    def feasible_gaps(self) -> int:
        return sum(1 for g in self.gaps if g.feasible)

    def summary(self) -> str:
        lines = [
            f"Package: {self.flutter_package} ({self.extension_type})",
            f"Coverage: {self.total_generated}/{self.total_dart_api} ({self.coverage_pct:.1f}%)",
            f"Gaps: {len(self.gaps)} total, {self.feasible_gaps} feasible",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Architect Output (Step 2 — LLM structured output)
# ---------------------------------------------------------------------------


@dataclass
class ImprovementSuggestion:
    """A single improvement suggested by the Architect."""

    target_file: str
    description: str
    gap_refs: list[int] = field(default_factory=list)
    priority: int = 1


@dataclass
class ArchitectPlan:
    """The Architect's analysis and improvement plan."""

    analysis: str
    suggestions: list[ImprovementSuggestion] = field(default_factory=list)
    files_to_skip: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Editor Output (Step 3 — LLM structured output)
# ---------------------------------------------------------------------------


@dataclass
class FileEdit:
    """A precise search/replace edit to apply to a file."""

    filename: str
    search: str
    replace: str
    rationale: str = ""


@dataclass
class EditorResult:
    """Collection of edits from the Editor agent."""

    edits: list[FileEdit] = field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# Final Result
# ---------------------------------------------------------------------------


@dataclass
class RefinementResult:
    """Final output of the AI refinement pipeline."""

    gap_report: GapReport
    architect_plan: ArchitectPlan | None = None
    edits_applied: int = 0
    edits_failed: int = 0
    validation_passed: bool = False
    overall_assessment: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    file_diffs: list[tuple[str, str]] = field(default_factory=list)
    """(filename, unified_diff_text) for files modified by AI."""
    pending_suggestions: list[ImprovementSuggestion] = field(default_factory=list)
    """Architect suggestions that the Editor did not apply."""
