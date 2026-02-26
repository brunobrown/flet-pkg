"""Generator for the Dart FletService file.

Produces the Dart service (or widget) implementation that handles
method dispatch from Python, event listener setup, and real SDK calls.
"""

from __future__ import annotations

from flet_pkg.core.generators.base import CodeGenerator
from flet_pkg.core.models import GenerationPlan, MethodPlan, SubModulePlan
from flet_pkg.core.parser import camel_to_snake


class DartServiceGenerator(CodeGenerator):
    """Generates the Dart FletService/FletWidget file."""

    def generate(self, plan: GenerationPlan) -> dict[str, str]:
        control_snake = plan.control_name_snake or camel_to_snake(plan.control_name)
        service_type = "Service" if plan.base_class == "ft.Service" else "Widget"
        filename = f"{control_snake}_{service_type.lower()}.dart"

        # UI controls use StatefulWidget + LayoutControl pattern
        if service_type == "Widget":
            return {filename: self._generate_ui_control(plan, control_snake)}

        # Service path — unchanged
        class_name = f"{plan.control_name}{service_type}"
        lines: list[str] = []

        # Imports
        lines.append("import 'dart:convert';")
        lines.append("import 'package:flet/flet.dart';")
        lines.append("import 'package:flutter/foundation.dart';")
        if plan.dart_import:
            lines.append(f"import '{plan.dart_import}';")
        lines.append("")

        # Class
        dart_base = f"Flet{service_type}"
        lines.append(f"/// {plan.control_name} {service_type.lower()} implementation for Flet.")
        lines.append("///")
        lines.append(
            f"/// This {service_type.lower()} handles all communication between the Python SDK"
        )
        lines.append(f"/// and the {plan.flutter_package} Flutter SDK.")
        lines.append(f"class {class_name} extends {dart_base} {{")
        lines.append(f"  {class_name}({{required super.control}});")
        lines.append("")
        lines.append("  bool _initialized = false;")
        lines.append("  bool _listenersSetup = false;")
        lines.append("")

        # init()
        lines.append("  @override")
        lines.append("  void init() {")
        lines.append("    super.init();")
        lines.append("    control.addInvokeMethodListener(_onInvokeMethod);")
        lines.append(f"    _initialize{plan.control_name}();")
        lines.append("  }")
        lines.append("")

        # update()
        lines.append("  @override")
        lines.append("  void update() {")
        lines.append("    super.update();")
        lines.append(f"    _initialize{plan.control_name}();")
        lines.append("  }")
        lines.append("")

        # dispose()
        lines.append("  @override")
        lines.append("  void dispose() {")
        lines.append("    control.removeInvokeMethodListener(_onInvokeMethod);")
        lines.append("    super.dispose();")
        lines.append("  }")
        lines.append("")

        # _initialize method with property reading
        self._render_initialize(lines, plan, class_name)

        # _setupListeners with real event listeners
        self._render_setup_listeners(lines, plan, class_name)

        # Enum parser helpers (if plan uses enums in methods)
        self._render_enum_helpers(lines, plan)

        # _onInvokeMethod with switch dispatch
        self._render_invoke_method(lines, plan)

        # Method implementations with real SDK calls
        all_methods = list(plan.main_methods)
        for sub in plan.sub_modules:
            all_methods.extend(sub.methods)

        for method in all_methods:
            sub_module = self._find_sub_module_for_method(method, plan)
            lines.extend(self._render_dart_method(method, plan, sub_module))
            lines.append("")

        # _handleError
        self._render_handle_error(lines, plan, class_name)

        lines.append("}")
        lines.append("")

        return {filename: "\n".join(lines)}

    # ------------------------------------------------------------------
    # UI Control: StatefulWidget + LayoutControl
    # ------------------------------------------------------------------

    def _generate_ui_control(self, plan: GenerationPlan, control_snake: str) -> str:
        """Generate a StatefulWidget Dart file for UI control extensions.

        Produces a ``StatefulWidget`` whose ``build()`` reads properties
        using typed getters (``getAlignment``, ``getBoxFit``, etc.) and
        wraps the SDK widget in a ``LayoutControl``.
        """
        widget_class = f"{plan.control_name}Widget"
        state_class = f"_{plan.control_name}WidgetState"
        sdk_class = plan.dart_main_class or plan.control_name
        lines: list[str] = []

        # Imports
        lines.append("import 'package:flet/flet.dart';")
        lines.append("import 'package:flutter/widgets.dart';")
        if plan.dart_import:
            lines.append(f"import '{plan.dart_import}';")
        lines.append("")

        # StatefulWidget class
        lines.append(f"/// {plan.control_name} widget implementation for Flet.")
        lines.append("///")
        lines.append(f"/// Wraps the {plan.flutter_package} Flutter widget in a LayoutControl.")
        lines.append(f"class {widget_class} extends StatefulWidget {{")
        lines.append("  final Control control;")
        lines.append(f"  const {widget_class}({{super.key, required this.control}});")
        lines.append("")
        lines.append("  @override")
        lines.append(f"  State<{widget_class}> createState() => {state_class}();")
        lines.append("}")
        lines.append("")

        # State class
        lines.append(f"class {state_class} extends State<{widget_class}> {{")

        # build()
        lines.append("  @override")
        lines.append("  Widget build(BuildContext context) {")
        lines.append("    try {")

        # Read properties using typed getters
        if plan.properties:
            for prop in plan.properties:
                dart_var = _to_camel_case(prop.python_name)
                if prop.dart_getter:
                    # Use the pre-computed typed getter from the analyzer
                    getter_expr = prop.dart_getter.replace("control.", "widget.control.")
                    # buildWidget/buildWidgets don't need widget. prefix
                    if getter_expr.startswith("buildWidget"):
                        getter_expr = prop.dart_getter
                    lines.append(f"      final {dart_var} = {getter_expr};")
                else:
                    # Fallback to getString
                    lines.append(
                        f'      final {dart_var} = widget.control.getString("{prop.python_name}");'
                    )
            lines.append("")

        # Build SDK widget constructor args
        lines.append("      return LayoutControl(")
        lines.append("        control: widget.control,")
        lines.append(f"        child: {sdk_class}(")
        for prop in plan.properties:
            dart_var = _to_camel_case(prop.python_name)
            # Use the original Dart param name for the constructor
            dart_param = prop.dart_name or prop.python_name
            lines.append(f"          {dart_param}: {dart_var},")
        lines.append("        ),")
        lines.append("      );")

        # Error handling
        lines.append("    } catch (error, stackTrace) {")
        lines.append("      _handleError(error, stackTrace);")
        lines.append("      return const SizedBox.shrink();")
        lines.append("    }")
        lines.append("  }")
        lines.append("")

        # _handleError
        lines.append("  void _handleError(Object error, StackTrace stackTrace) {")
        lines.append(f'    debugPrint("{widget_class} ERROR: $error");')
        lines.append('    widget.control.triggerEvent("error", {')
        lines.append('      "message": error.toString(),')
        lines.append('      "stack_trace": stackTrace.toString(),')
        lines.append("    });")
        lines.append("  }")

        lines.append("}")
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Initialize method
    # ------------------------------------------------------------------

    def _render_initialize(self, lines: list[str], plan: GenerationPlan, class_name: str) -> None:
        main_class = plan.dart_main_class or plan.control_name

        lines.append(f"  /// Initialize the {plan.control_name} SDK.")
        lines.append(f"  void _initialize{plan.control_name}() {{")
        lines.append("    if (_initialized) return;")
        lines.append("")
        lines.append("    try {")

        if plan.properties:
            # Read properties from control
            for prop in plan.properties:
                dart_var = _to_camel_case(prop.python_name)
                if prop.python_type in ("str", "str | None"):
                    lines.append(
                        f'      final {dart_var} = control.getString("{prop.python_name}");'
                    )
                elif prop.python_type == "bool":
                    lines.append(
                        f'      final {dart_var} = control.getBool("{prop.python_name}", false)!;'
                    )
                elif prop.python_type in ("int", "int | None"):
                    lines.append(f'      final {dart_var} = control.getInt("{prop.python_name}");')
                else:
                    lines.append(
                        f'      final {dart_var} = control.getString("{prop.python_name}");'
                    )
            lines.append("")

            # Apply pre-init setter properties BEFORE initialize()
            pre_init_props = [p for p in plan.properties if p.dart_pre_init_call]
            if pre_init_props:
                lines.append("      // Pre-init configuration")
                for prop in pre_init_props:
                    dart_var = _to_camel_case(prop.python_name)
                    call = prop.dart_pre_init_call.replace("{var}", dart_var)
                    lines.append(f"      {call}")
                lines.append("")

            # Find the init property (app_id, api_key, id, key, or first string property)
            init_prop = None
            for prop in plan.properties:
                if prop.python_name in ("app_id", "api_key", "id", "key"):
                    init_prop = prop
                    break
            if not init_prop:
                # First string property that is NOT a pre-init setter
                for prop in plan.properties:
                    if prop.python_type in ("str", "str | None") and not prop.dart_pre_init_call:
                        init_prop = prop
                        break

            if init_prop:
                var = _to_camel_case(init_prop.python_name)
                lines.append(f"      if ({var} != null && {var}.isNotEmpty) {{")
                lines.append(f"        {main_class}.initialize({var});")
                lines.append("      }")
        else:
            lines.append(f"      // Initialize {plan.control_name} SDK")
            lines.append(f"      // {main_class}.initialize(...);")

        lines.append("")
        lines.append("      _initialized = true;")
        lines.append("      _setupListeners();")
        lines.append("    } catch (error, stackTrace) {")
        lines.append(f'      _handleError("_initialize{plan.control_name}", error, stackTrace);')
        lines.append("    }")
        lines.append("  }")
        lines.append("")

    # ------------------------------------------------------------------
    # Setup listeners with real event registrations
    # ------------------------------------------------------------------

    def _render_setup_listeners(
        self, lines: list[str], plan: GenerationPlan, class_name: str
    ) -> None:
        lines.append("  /// Setup all event listeners.")
        lines.append("  void _setupListeners() {")
        lines.append("    if (_listenersSetup) return;")
        lines.append("    _listenersSetup = true;")

        if plan.events:
            lines.append("")
            for event in plan.events:
                accessor = event.dart_sdk_accessor or plan.dart_main_class
                listener_method = event.dart_listener_method
                event_name = event.dart_event_name

                if not listener_method:
                    continue

                # Generate real listener registration
                lines.append(f"    // {event.python_attr_name}")
                lines.append(f"    {accessor}.{listener_method}((event) {{")
                lines.append("      try {")
                lines.append(f'        control.triggerEvent("{event_name}", {{')

                # Generate event data extraction based on fields
                for field_name, field_type in event.fields:
                    camel = _to_camel_case(field_name)
                    if field_name == "data":
                        lines.append(f'          "{field_name}": event.toString(),')
                    elif field_name == "value":
                        # Simple value callback (e.g., bool for permission)
                        lines.append(f'          "{field_name}": event,')
                    elif field_type == "dict":
                        # Complex object → serialize via jsonRepresentation
                        lines.append(
                            f'          "{field_name}": '
                            f"jsonDecode(event.{camel}.jsonRepresentation()),"
                        )
                    elif field_type in ("str", "str | None"):
                        lines.append(f'          "{field_name}": event.{camel},')
                    elif field_type in ("bool", "bool | None", "int", "int | None", "float"):
                        lines.append(f'          "{field_name}": event.{camel},')
                    else:
                        lines.append(f'          "{field_name}": event.{camel}?.toString(),')

                lines.append("        });")
                lines.append("      } catch (error, stackTrace) {")
                lines.append(f'        _handleError("{event_name}_listener", error, stackTrace);')
                lines.append("      }")
                lines.append("    });")
                lines.append("")

        lines.append(f'    debugPrint("{class_name}._setupListeners: ready");')
        lines.append("  }")
        lines.append("")

    # ------------------------------------------------------------------
    # Enum parser helpers
    # ------------------------------------------------------------------

    def _render_enum_helpers(self, lines: list[str], plan: GenerationPlan) -> None:
        """Render helper methods to parse enum string values."""
        for enum in plan.enums:
            dart_name = enum.python_name
            lines.append(f"  {dart_name} _parse{dart_name}(String value) {{")
            lines.append("    return switch (value.toLowerCase()) {")
            for val_name, val_value in enum.values:
                lines.append(f'      "{val_value}" => {dart_name}.{val_name},')
            # Default fallback
            if enum.values:
                default_val = enum.values[0][0]
                lines.append(f"      _ => {dart_name}.{default_val},")
            lines.append("    };")
            lines.append("  }")
            lines.append("")

    # ------------------------------------------------------------------
    # _onInvokeMethod dispatch
    # ------------------------------------------------------------------

    def _render_invoke_method(self, lines: list[str], plan: GenerationPlan) -> None:
        lines.append("  /// Handle method invocations from Python.")
        lines.append("  Future<dynamic> _onInvokeMethod(String methodName, dynamic args) async {")
        lines.append("    try {")
        lines.append("      Map<String, dynamic> arguments = {};")
        lines.append("      if (args != null && args is Map) {")
        lines.append("        arguments = Map<String, dynamic>.from(args);")
        lines.append("      }")
        lines.append("")
        lines.append("      return switch (methodName) {")

        # Main methods
        if plan.main_methods:
            lines.append("        // Main methods")
            for method in plan.main_methods:
                dart_name = method.dart_method_name
                impl_name = _to_dart_method_name(dart_name)
                if method.params:
                    lines.append(f'        "{dart_name}" => await {impl_name}(arguments),')
                else:
                    lines.append(f'        "{dart_name}" => await {impl_name}(),')

        # Sub-module methods
        for sub in plan.sub_modules:
            label = sub.module_name.replace("_", " ").title()
            lines.append(f"        // {label} methods")
            for method in sub.methods:
                dart_name = method.dart_method_name
                impl_name = _to_dart_method_name(dart_name)
                if method.params:
                    lines.append(f'        "{dart_name}" => await {impl_name}(arguments),')
                else:
                    lines.append(f'        "{dart_name}" => await {impl_name}(),')

        lines.append(
            f'        _ => throw Exception("Unknown {plan.control_name} method: $methodName"),'
        )
        lines.append("      };")
        lines.append("    } catch (error, stackTrace) {")
        lines.append("      _handleError(methodName, error, stackTrace);")
        lines.append("      return null;")
        lines.append("    }")
        lines.append("  }")
        lines.append("")

    # ------------------------------------------------------------------
    # Individual method implementations with real SDK calls
    # ------------------------------------------------------------------

    def _render_dart_method(
        self,
        method: MethodPlan,
        plan: GenerationPlan,
        sub_module: SubModulePlan | None,
    ) -> list[str]:
        """Render a single Dart method with a real SDK call."""
        lines: list[str] = []
        impl_name = _to_dart_method_name(method.dart_method_name)

        # Determine SDK call path
        if sub_module and sub_module.dart_sdk_accessor:
            sdk_accessor = sub_module.dart_sdk_accessor
        else:
            sdk_accessor = plan.dart_main_class or plan.control_name

        # Original Dart method name for the SDK call
        original_name = method.dart_original_name or method.python_name
        dart_return = method.return_type

        if method.params:
            lines.append(f"  Future<String?> {impl_name}(Map<String, dynamic> args) async {{")
            # Extract arguments using python_name as key (matches what Python sends)
            for p in method.params:
                dart_type = _dart_cast_type(p.dart_type)
                lines.append(f'    final {p.dart_name} = args["{p.python_name}"] as {dart_type};')

            # Build null check condition for required params
            required_params = [p for p in method.params if not p.is_optional]

            # Build SDK call arguments (use "name: name" for named params)
            sdk_arg_parts = []
            for p in method.params:
                if p.is_optional:
                    continue
                if p.is_named:
                    sdk_arg_parts.append(f"{p.dart_name}: {p.dart_name}")
                else:
                    sdk_arg_parts.append(p.dart_name)
            sdk_args = ", ".join(sdk_arg_parts)

            if required_params:
                checks = " && ".join(f"{p.dart_name} != null" for p in required_params)
                lines.append(f"    if ({checks}) {{")

                # Determine return handling
                if dart_return == "None":
                    lines.append(f"      await {sdk_accessor}.{original_name}({sdk_args});")
                    lines.append("    }")
                    lines.append("    return null;")
                elif "bool" in dart_return.lower():
                    lines.append(
                        f"      final result = await {sdk_accessor}.{original_name}({sdk_args});"
                    )
                    lines.append("      return result.toString();")
                    lines.append("    }")
                    lines.append("    return null;")
                else:
                    lines.append(
                        f"      final result = await {sdk_accessor}.{original_name}({sdk_args});"
                    )
                    lines.append("      return result?.toString();")
                    lines.append("    }")
                    lines.append("    return null;")
            else:
                # All params are optional - call directly
                if dart_return == "None":
                    lines.append(f"    await {sdk_accessor}.{original_name}({sdk_args});")
                    lines.append("    return null;")
                else:
                    lines.append(
                        f"    final result = await {sdk_accessor}.{original_name}({sdk_args});"
                    )
                    lines.append("    return result?.toString();")
        else:
            # No params
            lines.append(f"  Future<String?> {impl_name}() async {{")

            # Getters use property access (no parens), methods use call syntax
            call = (
                f"{sdk_accessor}.{original_name}"
                if method.is_getter
                else f"{sdk_accessor}.{original_name}()"
            )

            if dart_return == "None":
                lines.append(f"    await {call};")
                lines.append("    return null;")
            elif "bool" in dart_return.lower():
                lines.append(f"    final result = await {call};")
                lines.append("    return result.toString();")
            elif dart_return in ("str", "str | None"):
                lines.append(f"    return await {call};")
            elif dart_return.startswith("dict") or dart_return.startswith("list"):
                lines.append(f"    final result = await {call};")
                lines.append("    return jsonEncode(result);")
            else:
                lines.append(f"    final result = await {call};")
                lines.append("    return result?.toString();")

        lines.append("  }")
        return lines

    # ------------------------------------------------------------------
    # Error handler
    # ------------------------------------------------------------------

    def _render_handle_error(self, lines: list[str], plan: GenerationPlan, class_name: str) -> None:
        lines.append("  /// Handle and report errors.")
        lines.append("  void _handleError(String method, Object error, StackTrace stackTrace) {")
        lines.append(f'    debugPrint("{class_name} ERROR in $method: $error");')
        lines.append("    FlutterError.reportError(FlutterErrorDetails(")
        lines.append("      exception: error,")
        lines.append("      stack: stackTrace,")
        lines.append(f"      library: '{plan.package_name}',")
        ctx_desc = f"while executing {plan.control_name} method"
        lines.append(f"      context: ErrorDescription('{ctx_desc} \"$method\"'),")
        lines.append("    ));")
        lines.append('    control.triggerEvent("error", {')
        lines.append('      "method": method,')
        lines.append('      "message": error.toString(),')
        lines.append('      "stack_trace": stackTrace.toString(),')
        lines.append("    });")
        lines.append("  }")
        lines.append("")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_sub_module_for_method(
        self, method: MethodPlan, plan: GenerationPlan
    ) -> SubModulePlan | None:
        """Find the sub-module that contains a method."""
        for sub in plan.sub_modules:
            if method in sub.methods:
                return sub
        return None


def _to_dart_method_name(snake_name: str) -> str:
    """Convert a snake_case dart method name to a _camelCase Dart function name."""
    parts = snake_name.split("_")
    return "_" + parts[0] + "".join(p.capitalize() for p in parts[1:])


def _to_camel_case(snake_name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = snake_name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _dart_cast_type(dart_type: str) -> str:
    """Return a safe Dart cast type for argument extraction."""
    dart_type = dart_type.strip().rstrip("?")
    if dart_type in ("String", "bool", "int", "double"):
        return f"{dart_type}?"
    if dart_type.startswith("Map"):
        return "Map<String, dynamic>?"
    if dart_type.startswith("List"):
        return "List?"
    return "dynamic"
