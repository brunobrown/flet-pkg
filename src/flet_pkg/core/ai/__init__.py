"""AI-powered refinement for generated Flet extension code.

This optional module uses the Architect/Editor pattern (inspired by Aider)
to analyze coverage gaps and apply LLM-driven improvements to generated code.

Requires: ``uv add flet-pkg[ai]`` (pydantic-ai).
"""

from __future__ import annotations

from flet_pkg.core.ai.config import AIConfig
from flet_pkg.core.ai.models import GapReport, RefinementResult

__all__ = ["AIConfig", "GapReport", "RefinementResult"]
