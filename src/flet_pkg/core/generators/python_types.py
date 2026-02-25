"""Generator for the Python types file.

Produces ``types.py`` with enum classes and event dataclasses
that mirror the Dart SDK's types.
"""

from __future__ import annotations

from flet_pkg.core.generators.base import CodeGenerator
from flet_pkg.core.models import GenerationPlan


class PythonTypesGenerator(CodeGenerator):
    """Generates types.py with enums and event dataclasses."""

    def generate(self, plan: GenerationPlan) -> dict[str, str]:
        # Always generate types.py — the error event class is always
        # imported by the main control file.

        lines: list[str] = []

        # Module docstring
        lines.append(f'"""')
        lines.append(f"Types, enums, and dataclasses for {plan.package_name}.")
        lines.append('"""')
        lines.append("")

        # Imports
        lines.append("from dataclasses import dataclass")
        if plan.enums:
            lines.append("from enum import Enum")
        lines.append("from typing import Optional")
        lines.append("")
        lines.append("import flet as ft")
        lines.append("")
        lines.append("")

        # Enums
        for enum in plan.enums:
            lines.append(f"class {enum.python_name}(Enum):")
            if enum.docstring:
                lines.append(f'    """{enum.docstring}"""')
            else:
                lines.append(f'    """{enum.python_name} enum."""')
            lines.append("")
            for val_name, val_value in enum.values:
                lines.append(f'    {val_name.upper()} = "{val_value}"')
                lines.append(f'    """{val_name}."""')
                lines.append("")
            lines.append("")

        # Event dataclasses
        for event in plan.events:
            lines.append("")
            lines.append("@dataclass")
            lines.append(
                f'class {event.event_class_name}(ft.Event["{plan.control_name}"]):'
            )
            event_desc = event.dart_event_name.replace("_", " ")
            lines.append(f'    """Event fired when {event_desc} occurs."""')
            lines.append("")

            for field_name, field_type in event.fields:
                if field_type == "dict":
                    lines.append(f"    {field_name}: dict = None")
                elif field_type == "bool":
                    lines.append(f"    {field_name}: bool = False")
                elif field_type in ("str", "int", "float"):
                    lines.append(f"    {field_name}: Optional[{field_type}] = None")
                else:
                    lines.append(f"    {field_name}: Optional[{field_type}] = None")
                field_desc = field_name.replace("_", " ").capitalize()
                lines.append(f'    """{field_desc}."""')
                lines.append("")

        # Stub data classes (re-exported types from platform_interface)
        for stub in plan.stub_data_classes:
            lines.append("")
            lines.append("@dataclass")
            lines.append(f"class {stub.python_name}:")
            if stub.docstring:
                lines.append(f'    """{stub.docstring}"""')
            else:
                lines.append(f'    """{stub.python_name} data class."""')
            lines.append("")
            for field_name, field_type in stub.fields:
                if field_type == "dict":
                    lines.append(f"    {field_name}: dict = None")
                else:
                    lines.append(f"    {field_name}: Optional[{field_type}] = None")
                lines.append("")

        # Error event (always generated)
        lines.append("")
        lines.append("@dataclass")
        error_cls = plan.error_event_class or f"{plan.control_name}ErrorEvent"
        lines.append(
            f'class {error_cls}(ft.Event["{plan.control_name}"]):'
        )
        lines.append('    """Event fired when an error occurs."""')
        lines.append("")
        lines.append("    method: Optional[str] = None")
        lines.append('    """The method that caused the error."""')
        lines.append("")
        lines.append("    message: Optional[str] = None")
        lines.append('    """The error message."""')
        lines.append("")
        lines.append("    stack_trace: Optional[str] = None")
        lines.append('    """The stack trace, if available."""')
        lines.append("")

        return {"types.py": "\n".join(lines)}
