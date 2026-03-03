"""Generator for the Python types file.

Produces ``types.py`` with enum classes and event dataclasses
that mirror the Dart SDK's types.
"""

from __future__ import annotations

from flet_pkg.core.generators.base import CodeGenerator
from flet_pkg.core.models import GenerationPlan, SubControlPlan
from flet_pkg.core.parser import camel_to_snake


class PythonTypesGenerator(CodeGenerator):
    """Generates types.py with enums and event dataclasses."""

    @staticmethod
    def _optional_type(field_type: str) -> str:
        """Wrap a type in Optional[], avoiding redundant Optional[X | None]."""
        if "| None" in field_type:
            return field_type
        return f"Optional[{field_type}]"

    def generate(self, plan: GenerationPlan) -> dict[str, str]:
        # Always generate types.py — the error event class is always
        # imported by the main control file.

        lines: list[str] = []

        # Module docstring
        lines.append('"""')
        lines.append(f"Types, enums, and dataclasses for {plan.package_name}.")
        lines.append('"""')
        lines.append("")
        lines.append("from __future__ import annotations")
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
                lines.extend(self._format_docstring(enum.docstring, "    "))
            else:
                lines.append(f'    """{enum.python_name} enum."""')
            lines.append("")
            for val_name, val_value, val_doc in enum.values:
                # Convert camelCase to UPPER_SNAKE_CASE (e.g. sdkUnavailable → SDK_UNAVAILABLE)
                py_name = camel_to_snake(val_name).upper()
                lines.append(f'    {py_name} = "{val_value}"')
                if val_doc:
                    lines.append(f'    """{val_doc}"""')
                else:
                    lines.append(f'    """{val_name}."""')
                lines.append("")
            lines.append("")

        # Event dataclasses (deduplicate by class name — multiple events
        # can share the same Stream<T> type, e.g. onMessage and onMessageOpenedApp
        # both use Stream<RemoteMessage>)
        seen_event_classes: set[str] = set()
        for event in plan.events:
            if event.event_class_name in seen_event_classes:
                continue
            seen_event_classes.add(event.event_class_name)
            lines.append("")
            lines.append("@dataclass")
            lines.append(f'class {event.event_class_name}(ft.Event["{plan.control_name}"]):')
            event_desc = event.dart_event_name.replace("_", " ")
            lines.append(f'    """Event fired when {event_desc} occurs."""')
            lines.append("")

            for field_name, field_type in event.fields:
                if field_type == "dict":
                    lines.append(f"    {field_name}: dict | None = None")
                elif field_type == "bool":
                    lines.append(f"    {field_name}: bool = False")
                else:
                    opt = self._optional_type(field_type)
                    lines.append(f"    {field_name}: {opt} = None")
                field_desc = field_name.replace("_", " ").capitalize()
                lines.append(f'    """{field_desc}."""')
                lines.append("")

        # Sibling widget event dataclasses
        for sibling in plan.sibling_widgets:
            for event in sibling.events:
                if event.event_class_name in seen_event_classes:
                    continue
                seen_event_classes.add(event.event_class_name)
                lines.append("")
                lines.append("@dataclass")
                lines.append(f'class {event.event_class_name}(ft.Event["{sibling.control_name}"]):')
                event_desc = event.dart_event_name.replace("_", " ")
                lines.append(f'    """Event fired when {event_desc} occurs."""')
                lines.append("")

                for field_name, field_type in event.fields:
                    if field_type == "dict":
                        lines.append(f"    {field_name}: dict = None")
                    elif field_type == "bool":
                        lines.append(f"    {field_name}: bool = False")
                    else:
                        opt = self._optional_type(field_type)
                        lines.append(f"    {field_name}: {opt} = None")
                    field_desc = field_name.replace("_", " ").capitalize()
                    lines.append(f'    """{field_desc}."""')
                    lines.append("")

        # Sub-control event dataclasses
        for sub in self._flatten_sub_controls(plan.sub_controls):
            for event in sub.events:
                if event.event_class_name in seen_event_classes:
                    continue
                seen_event_classes.add(event.event_class_name)
                lines.append("")
                lines.append("@dataclass")
                lines.append(f'class {event.event_class_name}(ft.Event["{sub.control_name}"]):')
                event_desc = event.dart_event_name.replace("_", " ")
                lines.append(f'    """Event fired when {event_desc} occurs."""')
                lines.append("")

                for field_name, field_type in event.fields:
                    if field_type == "dict":
                        lines.append(f"    {field_name}: dict | None = None")
                    elif field_type == "bool":
                        lines.append(f"    {field_name}: bool = False")
                    else:
                        opt = self._optional_type(field_type)
                        lines.append(f"    {field_name}: {opt} = None")
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
                    lines.append(f"    {field_name}: dict | None = None")
                else:
                    opt = self._optional_type(field_type)
                    lines.append(f"    {field_name}: {opt} = None")
                lines.append("")

        # Error event (always generated)
        lines.append("")
        lines.append("@dataclass")
        error_cls = plan.error_event_class or f"{plan.control_name}ErrorEvent"
        lines.append(f'class {error_cls}(ft.Event["{plan.control_name}"]):')
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

    @staticmethod
    def _flatten_sub_controls(sub_controls: list[SubControlPlan]) -> list[SubControlPlan]:
        """Flatten a recursive sub-control tree (leaves first, deduplicated)."""
        result: list[SubControlPlan] = []
        seen: set[str] = set()
        for sc in sub_controls:
            for nested in PythonTypesGenerator._flatten_sub_controls(sc.sub_controls):
                if nested.control_name not in seen:
                    result.append(nested)
                    seen.add(nested.control_name)
            if sc.control_name not in seen:
                result.append(sc)
                seen.add(sc.control_name)
        return result
