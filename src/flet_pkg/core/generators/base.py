"""Base class for code generators."""

from __future__ import annotations

import textwrap
from abc import ABC, abstractmethod

from flet_pkg.core.models import GenerationPlan


class CodeGenerator(ABC):
    """Abstract base class for code generators.

    Each generator receives a ``GenerationPlan`` and produces a dict
    mapping filenames to their generated content.
    """

    @abstractmethod
    def generate(self, plan: GenerationPlan) -> dict[str, str]:
        """Generate files from the plan.

        Returns:
            Dict mapping relative filename to file content string.
        """

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _indent(text: str, level: int = 1, width: int = 4) -> str:
        """Indent text by the given level."""
        prefix = " " * (level * width)
        return textwrap.indent(text, prefix)

    @staticmethod
    def _docstring(text: str, indent_level: int = 1) -> str:
        """Format a docstring with proper indentation."""
        if not text:
            return ""
        prefix = " " * (indent_level * 4)
        lines = text.strip().split("\n")
        if len(lines) == 1:
            return f'{prefix}"""{lines[0]}"""\n'
        result = [f'{prefix}"""']
        for line in lines:
            result.append(f"{prefix}{line}")
        result.append(f'{prefix}"""\n')
        return "\n".join(result)

    @staticmethod
    def _imports(*modules: str) -> str:
        """Generate sorted import lines."""
        return "\n".join(sorted(f"import {m}" for m in modules))
