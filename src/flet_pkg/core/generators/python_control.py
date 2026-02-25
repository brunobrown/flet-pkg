"""Generator for the main Python control file.

Produces the primary control class (e.g., ``onesignal.py``) following
the Flet 0.80.x+ extension pattern with ``@ft.control()``, sub-module
properties, event handlers, and async methods.
"""

from __future__ import annotations

from flet_pkg.core.generators.base import CodeGenerator
from flet_pkg.core.models import GenerationPlan, MethodPlan
from flet_pkg.core.parser import camel_to_snake


class PythonControlGenerator(CodeGenerator):
    """Generates the main Python control file."""

    def generate(self, plan: GenerationPlan) -> dict[str, str]:
        control_snake = plan.control_name_snake or camel_to_snake(plan.control_name)
        filename = f"{control_snake}.py"
        lines: list[str] = []

        # Module docstring
        lines.append(f'"""')
        lines.append(f"{plan.control_name} Service for {plan.package_name}.")
        if plan.description:
            lines.append(f"\n{plan.description}")
        lines.append('"""')

        # Imports
        lines.append("")
        lines.append("from dataclasses import field")
        lines.append("from typing import Any, Optional")
        lines.append("")
        lines.append("import flet as ft")
        lines.append("")

        # Sub-module imports
        for sub in plan.sub_modules:
            lines.append(
                f"from {plan.package_name}.{sub.module_name} import {sub.class_name}"
            )

        # Type imports
        type_imports: list[str] = []
        for event in plan.events:
            type_imports.append(event.event_class_name)
        # Add error event
        type_imports.append(plan.error_event_class or f"{plan.control_name}ErrorEvent")
        for enum in plan.enums:
            type_imports.append(enum.python_name)
        if type_imports:
            lines.append(f"from {plan.package_name}.types import (")
            for imp in sorted(set(type_imports)):
                lines.append(f"    {imp},")
            lines.append(")")

        lines.append("")
        lines.append("")

        # Class definition
        lines.append(f'@ft.control("{plan.control_name}")')
        lines.append(f"class {plan.control_name}({plan.base_class}):")
        lines.append('    """')
        lines.append(f"    {plan.control_name} integration for Flet applications.")
        lines.append("")
        lines.append("    Example:")
        lines.append("        ```python")
        lines.append("        import flet as ft")
        lines.append(f"        import {plan.package_name} as pkg")
        lines.append("")
        lines.append("        async def main(page: ft.Page):")

        if plan.base_class == "ft.Service":
            if plan.properties:
                prop_examples = []
                for prop in plan.properties[:2]:
                    if prop.python_type in ("str", "str | None"):
                        prop_examples.append(f'{prop.python_name}="..."')
                    elif prop.python_type == "bool":
                        prop_examples.append(f"{prop.python_name}=True")
                props_str = ", ".join(prop_examples) if prop_examples else ""
                lines.append(f"            svc = pkg.{plan.control_name}({props_str})")
            else:
                lines.append(f"            svc = pkg.{plan.control_name}()")
            lines.append("            page.services.append(svc)")
        else:
            lines.append(f"            widget = pkg.{plan.control_name}()")
            lines.append("            page.add(widget)")

        lines.append("")
        lines.append("        ft.run(main)")
        lines.append("        ```")
        lines.append('    """')
        lines.append("")

        # Properties (dataclass fields sent to Flutter)
        for prop in plan.properties:
            default = prop.default_value
            lines.append(f"    {prop.python_name}: {prop.python_type} = {default}")
            if prop.docstring:
                lines.append(f'    """{prop.docstring}"""')
            lines.append("")

        # Event handlers
        for event in plan.events:
            attr = event.python_attr_name
            evt_cls = event.event_class_name
            lines.append(f"    {attr}: Optional[ft.EventHandler[{evt_cls}]] = None")
            desc = event.dart_event_name.replace("_", " ")
            lines.append(f'    """Called when {desc} occurs."""')
            lines.append("")

        # Error event handler
        error_cls = plan.error_event_class or f"{plan.control_name}ErrorEvent"
        lines.append(
            f"    on_error: Optional[ft.EventHandler[{error_cls}]] = None"
        )
        lines.append('    """Called when an error occurs in the SDK."""')
        lines.append("")

        # Sub-module private fields
        for sub in plan.sub_modules:
            lines.append(
                f"    _{sub.module_name}: {sub.class_name} = field("
                f'default=None, init=False, metadata={{"skip": True}})'
            )
        if plan.sub_modules:
            lines.append("")

        # init() method
        if plan.sub_modules:
            lines.append("    def init(self):")
            lines.append('        """Initialize the service and sub-modules."""')
            lines.append("        super().init()")
            for sub in plan.sub_modules:
                lines.append(
                    f"        self._{sub.module_name} = {sub.class_name}(self)"
                )
            lines.append("")

        # Sub-module properties
        for sub in plan.sub_modules:
            lines.append("    @property")
            lines.append(f"    def {sub.module_name}(self) -> {sub.class_name}:")
            mod_title = sub.module_name.replace("_", " ").title()
            lines.append(f'        """Access the {mod_title} namespace."""')
            lines.append(f"        if self._{sub.module_name} is None:")
            lines.append(
                f"            self._{sub.module_name} = {sub.class_name}(self)"
            )
            lines.append(f"        return self._{sub.module_name}")
            lines.append("")

        # Main methods
        for method in plan.main_methods:
            lines.extend(self._render_method(method, plan))
            lines.append("")

        # _is_supported_platform
        lines.append("    def _is_supported_platform(self) -> bool:")
        lines.append(
            f'        """Check if the current platform supports {plan.control_name}."""'
        )
        lines.append("        if not self.page:")
        lines.append("            return False")
        lines.append("        return self.page.platform in (")
        lines.append("            ft.PagePlatform.ANDROID,")
        lines.append("            ft.PagePlatform.IOS,")
        lines.append("        )")
        lines.append("")

        # _invoke_method override with platform validation
        lines.append("    async def _invoke_method(")
        lines.append("        self,")
        lines.append("        method_name: str,")
        lines.append("        arguments: Optional[dict[str, Any]] = None,")
        lines.append("        timeout: Optional[float] = None,")
        lines.append("    ) -> Any:")
        lines.append('        """Internal method for invoking Flutter methods."""')
        lines.append("        if not self._is_supported_platform():")
        lines.append("            platform_name = self.page.platform.value if self.page else 'unknown'")
        lines.append("            raise ft.FletUnsupportedPlatformException(")
        lines.append(
            f'                f"{plan.control_name} is only supported on Android and iOS. "'
        )
        lines.append(
            "                f\"Current platform: {platform_name}. \""
        )
        lines.append(
            "                f\"Method '{method_name}' cannot be executed.\""
        )
        lines.append("            )")
        lines.append("        effective_timeout = timeout if timeout is not None else 25.0")
        lines.append("        return await super()._invoke_method(")
        lines.append("            method_name=method_name,")
        lines.append("            arguments=arguments or {},")
        lines.append("            timeout=effective_timeout,")
        lines.append("        )")
        lines.append("")

        return {filename: "\n".join(lines)}

    def _render_method(self, method: MethodPlan, plan: GenerationPlan) -> list[str]:
        """Render a single async method."""
        lines: list[str] = []

        # Build signature
        sig_parts = ["self"]
        for p in method.params:
            type_hint = p.python_type
            if p.is_optional:
                if "None" not in type_hint:
                    type_hint = f"{type_hint} | None"
                default = self._py_default(p.default)
                sig_parts.append(f"{p.python_name}: {type_hint} = {default}")
            else:
                sig_parts.append(f"{p.python_name}: {type_hint}")

        # All methods are async because they call _invoke_method
        sig = ", ".join(sig_parts)
        lines.append(
            f"    async def {method.python_name}({sig}) -> {method.return_type}:"
        )

        # Docstring
        if method.docstring:
            lines.append('        """')
            lines.append(f"        {method.docstring}")
            if method.params:
                lines.append("")
                lines.append("        Args:")
                for p in method.params:
                    lines.append(f"            {p.python_name}: {p.dart_name} parameter.")
            lines.append('        """')
        else:
            doc = method.python_name.replace("_", " ").capitalize()
            lines.append(f'        """{doc}."""')

        # Build arguments dict using python_name as key (matches Dart side)
        args_dict: dict[str, str] = {}
        for p in method.params:
            args_dict[p.python_name] = p.python_name

        if args_dict:
            args_str = ", ".join(f'"{k}": {v}' for k, v in args_dict.items())
            invoke_args = f"{{{args_str}}}"
        else:
            invoke_args = ""

        # Method body
        if method.return_type == "None":
            if invoke_args:
                lines.append(
                    f"        await self._invoke_method("
                    f'"{method.dart_method_name}", {invoke_args})'
                )
            else:
                lines.append(
                    f'        await self._invoke_method("{method.dart_method_name}")'
                )
        elif "bool" in method.return_type.lower():
            if invoke_args:
                lines.append(
                    f"        result = await self._invoke_method("
                    f'"{method.dart_method_name}", {invoke_args})'
                )
            else:
                lines.append(
                    f"        result = await self._invoke_method("
                    f'"{method.dart_method_name}")'
                )
            lines.append('        return result == "true"')
        else:
            if invoke_args:
                lines.append(
                    f"        return await self._invoke_method("
                    f'"{method.dart_method_name}", {invoke_args})'
                )
            else:
                lines.append(
                    f'        return await self._invoke_method("{method.dart_method_name}")'
                )

        return lines
