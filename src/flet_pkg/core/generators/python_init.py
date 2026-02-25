"""Generator for the Python __init__.py file.

Produces the package's ``__init__.py`` with all public exports
and ``__all__`` definition.
"""

from __future__ import annotations

from flet_pkg.core.generators.base import CodeGenerator
from flet_pkg.core.models import GenerationPlan
from flet_pkg.core.parser import camel_to_snake


class PythonInitGenerator(CodeGenerator):
    """Generates __init__.py with exports and __all__."""

    def generate(self, plan: GenerationPlan) -> dict[str, str]:
        lines: list[str] = []
        all_exports: list[str] = []

        control_snake = plan.control_name_snake or camel_to_snake(plan.control_name)

        # Module docstring
        desc = plan.description or f"{plan.control_name} integration for Flet applications."
        lines.append(f'"""')
        lines.append(f"{plan.package_name} - {desc}")
        lines.append('"""')
        lines.append("")

        # Main control import
        lines.append(
            f"from {plan.package_name}.{control_snake} import {plan.control_name}"
        )
        all_exports.append(plan.control_name)

        # Sub-module imports
        for sub in plan.sub_modules:
            lines.append(
                f"from {plan.package_name}.{sub.module_name} import {sub.class_name}"
            )
            all_exports.append(sub.class_name)

        # Types imports (always include error event class)
        type_names: list[str] = []
        for enum in plan.enums:
            type_names.append(enum.python_name)
        for event in plan.events:
            type_names.append(event.event_class_name)
        for stub in plan.stub_data_classes:
            type_names.append(stub.python_name)
        # Error event is always generated
        type_names.append(plan.error_event_class or f"{plan.control_name}ErrorEvent")
        type_names = sorted(set(type_names))

        lines.append(f"from {plan.package_name}.types import (")
        for name in type_names:
            lines.append(f"    {name},")
        lines.append(")")
        all_exports.extend(type_names)

        lines.append("")

        # __all__
        lines.append("__all__ = [")

        # Group: Main service
        lines.append("    # Main service")
        lines.append(f'    "{plan.control_name}",')

        # Group: Sub-modules
        if plan.sub_modules:
            lines.append("    # Sub-modules")
            for sub in plan.sub_modules:
                lines.append(f'    "{sub.class_name}",')

        # Group: Types and events
        lines.append("    # Types and events")
        for name in sorted(set(all_exports)):
            if name != plan.control_name and name not in [
                s.class_name for s in plan.sub_modules
            ]:
                lines.append(f'    "{name}",')

        lines.append("]")
        lines.append("")

        return {"__init__.py": "\n".join(lines)}
