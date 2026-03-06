"""Base class for code generators."""

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

    @staticmethod
    def _format_docstring(doc: str, indent: str = "    ") -> list[str]:
        """Format a docstring preserving multi-line structure.

        Args:
            doc: Raw docstring text.
            indent: Indentation prefix for each line.

        Returns:
            List of formatted docstring lines, or empty list if *doc* is empty.
        """
        if not doc:
            return []
        doc_lines = doc.split("\n")
        if len(doc_lines) == 1:
            return [f'{indent}"""{doc}"""']
        result = [f'{indent}"""{doc_lines[0]}']
        for dl in doc_lines[1:]:
            result.append(f"{indent}{dl}" if dl.strip() else "")
        result.append(f'{indent}"""')
        return result

    @staticmethod
    def _py_default(dart_default: str | None) -> str:
        """Convert a Dart default value to a Python literal.

        Args:
            dart_default: Dart default value string (e.g. ``"true"``, ``"0.5"``).

        Returns:
            Equivalent Python literal string (e.g. ``"True"``, ``"0.5"``).
        """
        if not dart_default:
            return "None"
        _DART_TO_PYTHON = {
            "true": "True",
            "false": "False",
            "null": "None",
        }
        if dart_default in _DART_TO_PYTHON:
            return _DART_TO_PYTHON[dart_default]

        # Numeric literals pass through (must check BEFORE "." check
        # since decimals like "0.0" contain dots)
        try:
            float(dart_default)
            return dart_default
        except ValueError:
            pass

        # Dart constructor calls: `const SomeClass()`, `SomeClass()`
        if "(" in dart_default:
            return "None"

        # Dart enum references: `SomeEnum.value` (not numeric decimals)
        if "." in dart_default:
            return "None"

        # Dart const collections: `const []`, `const {}`
        if dart_default.startswith("const "):
            return "None"

        # String literals: keep as-is if they look like Python strings
        if (dart_default.startswith('"') and dart_default.endswith('"')) or (
            dart_default.startswith("'") and dart_default.endswith("'")
        ):
            return dart_default

        # Unknown complex expression → None
        return "None"
