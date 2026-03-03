"""Generator for the Python __init__.py file.

Produces the package's ``__init__.py`` with all public exports
and ``__all__`` definition.
"""

from __future__ import annotations

from flet_pkg.core.generators.base import CodeGenerator
from flet_pkg.core.models import GenerationPlan, SubControlPlan
from flet_pkg.core.parser import camel_to_snake


class PythonInitGenerator(CodeGenerator):
    """Generates __init__.py with exports and __all__."""

    def generate(self, plan: GenerationPlan) -> dict[str, str]:
        lines: list[str] = []
        all_exports: list[str] = []

        control_snake = plan.control_name_snake or camel_to_snake(plan.control_name)

        # Module docstring
        desc = plan.description or f"{plan.control_name} integration for Flet applications."
        lines.append('"""')
        lines.append(f"{plan.package_name} - {desc}")
        lines.append('"""')
        lines.append("")

        # Main control import
        lines.append(f"from {plan.package_name}.{control_snake} import {plan.control_name}")
        all_exports.append(plan.control_name)

        # Sub-control imports (from the same control module)
        for sub in self._flatten_sub_controls(plan.sub_controls):
            lines.append(f"from {plan.package_name}.{control_snake} import {sub.control_name}")
            all_exports.append(sub.control_name)

        # Sibling widget imports (from separate modules)
        for sibling in plan.sibling_widgets:
            sib_snake = sibling.control_name_snake or camel_to_snake(sibling.control_name)
            lines.append(f"from {plan.package_name}.{sib_snake} import {sibling.control_name}")
            all_exports.append(sibling.control_name)

        # Sub-module imports
        for sub in plan.sub_modules:
            lines.append(f"from {plan.package_name}.{sub.module_name} import {sub.class_name}")
            all_exports.append(sub.class_name)

        # Types imports (always include error event class)
        type_names: list[str] = []
        for enum in plan.enums:
            type_names.append(enum.python_name)
        for event in plan.events:
            type_names.append(event.event_class_name)
        for stub in plan.stub_data_classes:
            type_names.append(stub.python_name)
        # Sub-control event types
        for sub in self._flatten_sub_controls(plan.sub_controls):
            for event in sub.events:
                type_names.append(event.event_class_name)
        # Sibling event types
        for sibling in plan.sibling_widgets:
            for event in sibling.events:
                type_names.append(event.event_class_name)
        # Error event is always generated
        type_names.append(plan.error_event_class or f"{plan.control_name}ErrorEvent")
        type_names = sorted(set(type_names))

        lines.append(f"from {plan.package_name}.types import (")
        for name in type_names:
            lines.append(f"    {name},")
        lines.append(")")
        all_exports.extend(type_names)

        # Console imports (conditional)
        if plan.include_console:
            lines.append(f"from {plan.package_name}.console import DebugConsole, setup_logging")
            all_exports.extend(["DebugConsole", "setup_logging"])

        lines.append("")

        # __all__
        lines.append("__all__ = [")

        # Group: Main control/service
        kind = "service" if plan.base_class == "ft.Service" else "control"
        lines.append(f"    # Main {kind}")
        lines.append(f'    "{plan.control_name}",')

        # Group: Sub-controls
        flat_subs = self._flatten_sub_controls(plan.sub_controls)
        if flat_subs:
            lines.append("    # Sub-controls")
            for sub in flat_subs:
                lines.append(f'    "{sub.control_name}",')

        # Group: Sibling widgets
        if plan.sibling_widgets:
            lines.append("    # Sibling widgets")
            for sibling in plan.sibling_widgets:
                lines.append(f'    "{sibling.control_name}",')

        # Group: Sub-modules
        if plan.sub_modules:
            lines.append("    # Sub-modules")
            for sub in plan.sub_modules:
                lines.append(f'    "{sub.class_name}",')

        # Group: Debug console
        if plan.include_console:
            lines.append("    # Debug console")
            lines.append('    "DebugConsole",')
            lines.append('    "setup_logging",')

        # Group: Types and events
        sub_control_names = {s.control_name for s in flat_subs}
        sibling_names = {s.control_name for s in plan.sibling_widgets}
        sub_module_names = {s.class_name for s in plan.sub_modules}
        console_names = {"DebugConsole", "setup_logging"} if plan.include_console else set()
        already_listed = (
            {plan.control_name}
            | sub_control_names
            | sibling_names
            | sub_module_names
            | console_names
        )
        lines.append("    # Types and events")
        for name in sorted(set(all_exports)):
            if name not in already_listed:
                lines.append(f'    "{name}",')

        lines.append("]")
        lines.append("")

        return {"__init__.py": "\n".join(lines)}

    @staticmethod
    def _flatten_sub_controls(sub_controls: list[SubControlPlan]) -> list[SubControlPlan]:
        """Flatten a recursive sub-control tree (leaves first, deduplicated)."""
        result: list[SubControlPlan] = []
        seen: set[str] = set()
        for sc in sub_controls:
            for nested in PythonInitGenerator._flatten_sub_controls(sc.sub_controls):
                if nested.control_name not in seen:
                    result.append(nested)
                    seen.add(nested.control_name)
            if sc.control_name not in seen:
                result.append(sc)
                seen.add(sc.control_name)
        return result
