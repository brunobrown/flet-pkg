"""Generator for Python sub-module files.

Produces one file per sub-module (e.g., ``user.py``, ``notifications.py``)
following the composition pattern used in flet-onesignal.
"""

from flet_pkg.core.generators.base import CodeGenerator
from flet_pkg.core.models import GenerationPlan, MethodPlan, SubModulePlan
from flet_pkg.core.parser import camel_to_snake


class PythonSubModuleGenerator(CodeGenerator):
    """Generates Python sub-module files."""

    def generate(self, plan: GenerationPlan) -> dict[str, str]:
        """Generate one Python file per sub-module.

        Args:
            plan: Generation plan produced by the analyzer.

        Returns:
            Mapping of filename to generated source code.
        """
        files: dict[str, str] = {}
        for sub in plan.sub_modules:
            filename = f"{sub.module_name}.py"
            content = self._render_submodule(sub, plan)
            files[filename] = content
        return files

    def _render_submodule(self, sub: SubModulePlan, plan: GenerationPlan) -> str:
        """Render a single sub-module file."""
        lines: list[str] = []
        control_snake = plan.control_name_snake or camel_to_snake(plan.control_name)
        self._enum_names = {e.python_name for e in plan.enums}

        # Module docstring
        mod_title = sub.module_name.replace("_", " ").title()
        lines.append(f'"""\n{plan.control_name} {mod_title} module for {plan.package_name}.\n"""')
        lines.append("")

        # Collect typing imports based on types used in methods
        needs_any = False
        needs_optional = False
        enum_names = {e.python_name for e in plan.enums}
        used_enums: set[str] = set()

        for method in sub.methods:
            all_types = [method.return_type] + [p.python_type for p in method.params]
            for t in all_types:
                if "Any" in t:
                    needs_any = True
                if "Optional" in t:
                    needs_optional = True
                # Check if type references an enum
                for en in enum_names:
                    if en in t:
                        used_enums.add(en)

        typing_imports = ["TYPE_CHECKING"]
        if needs_any:
            typing_imports.append("Any")
        if needs_optional:
            typing_imports.append("Optional")

        lines.append(f"from typing import {', '.join(sorted(typing_imports))}")
        lines.append("")

        # Import enums used by methods
        if used_enums:
            enum_list = ", ".join(sorted(used_enums))
            lines.append(f"from {plan.package_name}.types import {enum_list}")
            lines.append("")

        lines.append("if TYPE_CHECKING:")
        lines.append(f"    from {plan.package_name}.{control_snake} import {plan.control_name}")
        lines.append("")
        lines.append("")

        # Class
        lines.append(f"class {sub.class_name}:")
        lines.append('    """')
        lines.append(
            f"    {plan.control_name} {sub.module_name.replace('_', ' ').title()} namespace."
        )
        lines.append("")
        if sub.docstring:
            lines.append(f"    {sub.docstring}")
        lines.append('    """')
        lines.append("")

        # Constructor
        lines.append(f'    def __init__(self, service: "{plan.control_name}"):')
        lines.append("        self._service = service")
        lines.append("")

        # Methods
        for method in sub.methods:
            lines.extend(self._render_method(method, sub))
            lines.append("")

        return "\n".join(lines)

    def _render_method(self, method: MethodPlan, sub: SubModulePlan) -> list[str]:
        """Render a single async method definition for a sub-module class.

        Args:
            method: Method plan with name, params, and return type.
            sub: Parent sub-module plan for invoke key generation.

        Returns:
            List of source code lines for the method.
        """
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

        # Add timeout for getter-style methods (no params, return value)
        has_timeout = False
        if method.return_type not in ("None",) and not method.params:
            sig_parts.append("timeout: float = 25")
            has_timeout = True

        # All methods are async because they call _invoke_method
        sig = ", ".join(sig_parts)
        lines.append(f"    async def {method.python_name}({sig}) -> {method.return_type}:")

        # Docstring
        if method.docstring:
            lines.append('        """')
            for dl in method.docstring.split("\n"):
                lines.append(f"        {dl}" if dl.strip() else "")
            if method.params:
                lines.append("")
                lines.append("        Args:")
                for p in method.params:
                    if p.docstring:
                        lines.append(f"            {p.python_name}: {p.docstring}")
                    else:
                        lines.append(f"            {p.python_name}: {p.dart_name} parameter.")
            lines.append('        """')
        elif method.params:
            doc = method.python_name.replace("_", " ").capitalize()
            lines.append(f'        """{doc}.')
            lines.append("")
            lines.append("        Args:")
            for p in method.params:
                if p.docstring:
                    lines.append(f"            {p.python_name}: {p.docstring}")
                else:
                    lines.append(f"            {p.python_name}: {p.dart_name} parameter.")
            lines.append('        """')
        else:
            doc = method.python_name.replace("_", " ").capitalize()
            lines.append(f'        """{doc}."""')

        # Build arguments dict using python_name as key (matches Dart dispatch)
        # For enum-typed params, use .value to serialize (with None guard)
        enum_names = getattr(self, "_enum_names", set())
        args_dict: dict[str, str] = {}
        for p in method.params:
            # Check if param type is an enum (strip Optional/nullable)
            base_type = p.python_type.replace("Optional[", "").rstrip("]")
            base_type = base_type.split("|")[0].strip()
            if base_type in enum_names:
                if p.is_optional or "None" in p.python_type:
                    args_dict[p.python_name] = (
                        f"{p.python_name}.value if {p.python_name} is not None else None"
                    )
                else:
                    args_dict[p.python_name] = f"{p.python_name}.value"
            else:
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
                    f"        await self._service._invoke_method("
                    f'"{method.dart_method_name}", {invoke_args})'
                )
            else:
                lines.append(
                    f'        await self._service._invoke_method("{method.dart_method_name}")'
                )
        elif "bool" in method.return_type.lower():
            timeout_arg = ", timeout=timeout" if has_timeout else ""
            if invoke_args:
                lines.append(
                    f"        result = await self._service._invoke_method("
                    f'"{method.dart_method_name}", {invoke_args}{timeout_arg})'
                )
            else:
                lines.append(
                    f"        result = await self._service._invoke_method("
                    f'"{method.dart_method_name}"{timeout_arg})'
                )
            lines.append('        return result == "true"')
        else:
            timeout_arg = ", timeout=timeout" if has_timeout else ""
            if invoke_args:
                lines.append(
                    f"        result = await self._service._invoke_method("
                    f'"{method.dart_method_name}", {invoke_args}{timeout_arg})'
                )
            else:
                lines.append(
                    f"        result = await self._service._invoke_method("
                    f'"{method.dart_method_name}"{timeout_arg})'
                )
            lines.append("        return result")

        return lines
