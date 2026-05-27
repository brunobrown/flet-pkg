"""Generator for the Dart FletService file.

Produces the Dart service (or widget) implementation that handles
method dispatch from Python, event listener setup, and real SDK calls.
"""

from flet_pkg.core.generators.base import CodeGenerator
from flet_pkg.core.models import (
    GenerationPlan,
    MethodPlan,
    SiblingWidgetPlan,
    SubControlPlan,
    SubModulePlan,
)
from flet_pkg.core.parser import camel_to_snake


class DartServiceGenerator(CodeGenerator):
    """Generates the Dart FletService/FletWidget file."""

    def generate(self, plan: GenerationPlan) -> dict[str, str]:
        """Generate Dart service/widget files and optional extension.dart.

        Args:
            plan: Generation plan produced by the analyzer.

        Returns:
            Mapping of filename to generated Dart source code.
        """
        control_snake = plan.control_name_snake or camel_to_snake(plan.control_name)
        is_service = plan.base_class == "ft.Service"
        service_type = "Service" if is_service else "Widget"
        # UI controls follow the official Flet convention: the widget class is
        # ``{Control}Control`` in ``{snake}_control.dart``, registered via
        # ``Extension.createWidget``. Services use ``{Control}Service``.
        filename = (
            f"{control_snake}_service.dart" if is_service else f"{control_snake}_control.dart"
        )

        # UI controls use StatefulWidget + LayoutControl pattern
        if not is_service:
            files: dict[str, str] = {filename: self._generate_ui_control(plan, control_snake)}

            # Generate sibling control Dart files
            for sibling in plan.sibling_widgets:
                sib_snake = sibling.control_name_snake or camel_to_snake(sibling.control_name)
                sib_file = f"{sib_snake}_control.dart"
                files[sib_file] = self._generate_sibling_widget(sibling, plan)

            # Always (re)generate extension.dart so the exported entry-point
            # matches the generated control/sibling class names.
            files["extension.dart"] = self._generate_extension_dart(plan)

            return files

        # Service path
        class_name = f"{plan.control_name}{service_type}"
        main_class = plan.dart_main_class or plan.control_name

        # Decide whether the SDK class must be instantiated. Instance (non-static)
        # methods are dispatched on an instance; static methods on the class name.
        all_methods = list(plan.main_methods)
        for sub in plan.sub_modules:
            all_methods.extend(sub.methods)
        instance_var = f"_{main_class[0].lower()}{main_class[1:]}" if main_class else "_sdk"
        needs_instance = any(
            self._method_uses_instance(m, self._find_sub_module_for_method(m, plan))
            for m in all_methods
        )

        lines: list[str] = []

        # `dart:convert` is only used for jsonEncode (no-param methods returning
        # dict/list) and jsonDecode (event fields of type "dict"). Import it
        # only when actually used to avoid an `unused_import` warning.
        needs_json = any(
            not m.params and (m.return_type.startswith("dict") or m.return_type.startswith("list"))
            for m in all_methods
        ) or any(ftype == "dict" for ev in plan.events for _fname, ftype in ev.fields)

        # Imports
        if needs_json:
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
        if needs_instance:
            lines.append(f"  final {main_class} {instance_var} = {main_class}();")
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

        # _onInvokeMethod with switch dispatch
        self._render_invoke_method(lines, plan)

        # Method implementations with real SDK calls
        for method in all_methods:
            sub_module = self._find_sub_module_for_method(method, plan)
            lines.extend(self._render_dart_method(method, plan, sub_module, instance_var))
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

        Args:
            plan: Generation plan with widget properties and events.
            control_snake: Snake-case control name for file references.

        Returns:
            Complete Dart source code string.
        """
        widget_class = f"{plan.control_name}Control"
        state_class = f"_{plan.control_name}ControlState"
        sdk_class = plan.dart_main_class or plan.control_name
        lines: list[str] = []

        # Imports
        lines.append("import 'package:flet/flet.dart';")
        # Use material.dart if TextStyle getters need Theme.of(context)
        needs_material = any("Theme.of(context)" in (p.dart_getter or "") for p in plan.properties)
        if needs_material:
            lines.append("import 'package:flutter/material.dart';")
        else:
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
                # The "type" discriminator is read by the family-variant switch
                # below; skip it here to avoid a duplicate local declaration.
                if plan.widget_family_variants and prop.python_name == "type":
                    continue
                dart_var = _to_camel_case(prop.python_name)
                if prop.dart_getter:
                    # Use the pre-computed typed getter from the analyzer.
                    # Getters reference `control.` (incl. buildWidget/buildWidgets);
                    # rewrite to the State's `widget.control.` receiver.
                    if prop.dart_getter.startswith("widget."):
                        getter_expr = prop.dart_getter
                    else:
                        getter_expr = prop.dart_getter.replace("control.", "widget.control.")
                    getter_expr = _coalesce_child_getter(getter_expr, prop.dart_type)
                    lines.append(f"      final {dart_var} = {getter_expr};")
                else:
                    # Fallback to getString
                    lines.append(
                        f'      final {dart_var} = widget.control.getString("{prop.python_name}");'
                    )
            lines.append("")

        # Build SDK widget constructor args
        if plan.widget_family_variants:
            # Family variant: switch on type to select the right SDK widget
            lines.append("      final Widget sdkChild;")
            default_val = plan.widget_family_variants[0].enum_value
            lines.append(f'      final type = widget.control.getString("type") ?? "{default_val}";')
            lines.append("      switch (type) {")
            # Build shared args string (all properties except "type")
            shared_args: list[str] = []
            for prop in plan.properties:
                if prop.python_name == "type":
                    continue
                dart_var = _to_camel_case(prop.python_name)
                dart_param = prop.dart_name or prop.python_name
                shared_args.append(f"{dart_param}: {dart_var}")
            args_str = ", ".join(shared_args)
            for variant in plan.widget_family_variants:
                lines.append(f'        case "{variant.enum_value}":')
                lines.append(f"          sdkChild = {variant.dart_class_name}({args_str});")
                lines.append("          break;")
            # Default case
            default_cls = plan.widget_family_variants[0].dart_class_name
            lines.append("        default:")
            lines.append(f"          sdkChild = {default_cls}({args_str});")
            lines.append("      }")
            lines.append("")
            lines.append("      return LayoutControl(")
            lines.append("        control: widget.control,")
            lines.append("        child: sdkChild,")
            lines.append("      );")
        else:
            lines.append("      return LayoutControl(")
            lines.append("        control: widget.control,")
            lines.append(f"        child: {sdk_class}(")
            for prop in _ctor_arg_order(plan.properties):
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

        # Sub-control StatefulWidgets
        for sub in self._flatten_sub_controls(plan.sub_controls):
            lines.extend(self._render_sub_control_widget(sub, plan))
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Sibling widget generation
    # ------------------------------------------------------------------

    def _generate_sibling_widget(self, sibling: SiblingWidgetPlan, plan: GenerationPlan) -> str:
        """Generate a standalone StatefulWidget Dart file for a sibling widget."""
        widget_class = f"{sibling.control_name}Control"
        state_class = f"_{sibling.control_name}ControlState"
        sdk_class = sibling.dart_class_name
        needs_material = any(
            "Theme.of(context)" in (p.dart_getter or "") for p in sibling.properties
        )
        flutter_import = (
            "import 'package:flutter/material.dart';"
            if needs_material
            else "import 'package:flutter/widgets.dart';"
        )
        lines: list[str] = [
            "import 'package:flet/flet.dart';",
            flutter_import,
        ]

        # Imports
        if plan.dart_import:
            lines.append(f"import '{plan.dart_import}';")
        lines.append("")

        # StatefulWidget
        lines.append(f"/// {sibling.control_name} widget implementation for Flet.")
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
        lines.append("  @override")
        lines.append("  Widget build(BuildContext context) {")
        lines.append("    try {")

        # Read properties
        if sibling.properties:
            for prop in sibling.properties:
                dart_var = _to_camel_case(prop.python_name)
                if prop.dart_getter:
                    getter_expr = prop.dart_getter.replace("control.", "widget.control.")
                    getter_expr = _coalesce_child_getter(getter_expr, prop.dart_type)
                    lines.append(f"      final {dart_var} = {getter_expr};")
                else:
                    lines.append(
                        f'      final {dart_var} = widget.control.getString("{prop.python_name}");'
                    )
            lines.append("")

        # SDK widget constructor
        lines.append("      return LayoutControl(")
        lines.append("        control: widget.control,")
        lines.append(f"        child: {sdk_class}(")
        for prop in _ctor_arg_order(sibling.properties):
            dart_var = _to_camel_case(prop.python_name)
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

    def _generate_extension_dart(self, plan: GenerationPlan) -> str:
        """Generate ``extension.dart`` registering the main + sibling controls.

        Follows the official Flet convention: a ``FletExtension`` subclass that
        maps ``control.type`` to the matching ``{Control}Control`` widget via
        ``createWidget``. Lives at ``lib/src/extension.dart`` and is re-exported
        by ``lib/{package}.dart``.
        """
        control_snake = plan.control_name_snake or camel_to_snake(plan.control_name)
        lines: list[str] = []

        # Imports (relative to lib/src/)
        lines.append("import 'package:flet/flet.dart';")
        lines.append("import 'package:flutter/widgets.dart';")
        lines.append(f"import '{control_snake}_control.dart';")
        for sibling in plan.sibling_widgets:
            sib_snake = sibling.control_name_snake or camel_to_snake(sibling.control_name)
            lines.append(f"import '{sib_snake}_control.dart';")
        lines.append("")

        # FletExtension.createWidget dispatch
        lines.append("class Extension extends FletExtension {")
        lines.append("  @override")
        lines.append("  Widget? createWidget(Key? key, Control control) {")
        lines.append("    switch (control.type) {")
        lines.append(f'      case "{plan.control_name}":')
        lines.append(f"        return {plan.control_name}Control(control: control);")
        for sibling in plan.sibling_widgets:
            lines.append(f'      case "{sibling.control_name}":')
            lines.append(f"        return {sibling.control_name}Control(control: control);")
        lines.append("      default:")
        lines.append("        return null;")
        lines.append("    }")
        lines.append("  }")
        lines.append("}")
        lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Sub-control widget rendering
    # ------------------------------------------------------------------

    def _render_sub_control_widget(self, sub: SubControlPlan, plan: GenerationPlan) -> list[str]:
        """Render a StatefulWidget for a sub-control."""
        widget_class = f"{sub.control_name}Widget"
        state_class = f"_{sub.control_name}WidgetState"
        lines: list[str] = []

        lines.append(f"/// {sub.control_name} sub-control widget for {plan.control_name}.")
        lines.append(f"class {widget_class} extends StatefulWidget {{")
        lines.append("  final Control control;")
        lines.append(f"  const {widget_class}({{super.key, required this.control}});")
        lines.append("")
        lines.append("  @override")
        lines.append(f"  State<{widget_class}> createState() => {state_class}();")
        lines.append("}")
        lines.append("")

        lines.append(f"class {state_class} extends State<{widget_class}> {{")
        lines.append("  @override")
        lines.append("  Widget build(BuildContext context) {")
        lines.append("    try {")

        # Read properties using typed getters
        for prop in sub.properties:
            dart_var = _to_camel_case(prop.python_name)
            if prop.dart_getter:
                if prop.dart_getter.startswith("widget."):
                    getter_expr = prop.dart_getter
                else:
                    getter_expr = prop.dart_getter.replace("control.", "widget.control.")
                getter_expr = _coalesce_child_getter(getter_expr, prop.dart_type)
                lines.append(f"      final {dart_var} = {getter_expr};")
            else:
                lines.append(
                    f'      final {dart_var} = widget.control.getString("{prop.python_name}");'
                )

        if sub.properties:
            lines.append("")

        # Build constructor call
        lines.append(f"      return {sub.dart_class_name}(")
        for prop in _ctor_arg_order(sub.properties):
            dart_var = _to_camel_case(prop.python_name)
            dart_param = prop.dart_name or prop.python_name
            lines.append(f"        {dart_param}: {dart_var},")
        lines.append("      );")
        lines.append("    } catch (error, stackTrace) {")
        lines.append(f'      debugPrint("{sub.dart_class_name} ERROR: $error");')
        lines.append("      return const SizedBox.shrink();")
        lines.append("    }")
        lines.append("  }")
        lines.append("}")
        lines.append("")

        return lines

    @staticmethod
    def _flatten_sub_controls(sub_controls: list[SubControlPlan]) -> list[SubControlPlan]:
        """Flatten a recursive sub-control tree (leaves first, deduplicated)."""
        result: list[SubControlPlan] = []
        seen: set[str] = set()
        for sc in sub_controls:
            for nested in DartServiceGenerator._flatten_sub_controls(sc.sub_controls):
                if nested.control_name not in seen:
                    result.append(nested)
                    seen.add(nested.control_name)
            if sc.control_name not in seen:
                result.append(sc)
                seen.add(sc.control_name)
        return result

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
        instance_var: str = "",
    ) -> list[str]:
        """Render a single Dart method with a real SDK call."""
        lines: list[str] = []
        impl_name = _to_dart_method_name(method.dart_method_name)

        # Determine SDK call path. Instance methods are dispatched on the
        # instantiated SDK object; static methods (and namespaced sub-modules)
        # are dispatched on the class/namespace path.
        if sub_module and sub_module.dart_sdk_accessor:
            sdk_accessor = sub_module.dart_sdk_accessor
        elif not method.is_static and instance_var:
            sdk_accessor = instance_var
        else:
            sdk_accessor = plan.dart_main_class or plan.control_name

        # Original Dart method name for the SDK call
        original_name = method.dart_original_name or method.python_name
        dart_return = method.return_type

        # Only await Future-returning SDK calls. Awaiting a synchronous method
        # or getter raises await_only_futures / use_of_void_result in
        # `flutter analyze`.
        aw = "await " if method.dart_is_async else ""

        if method.params:
            lines.append(f"  Future<String?> {impl_name}(Map<String, dynamic> args) async {{")
            # Extract arguments using python_name as key (matches what Python sends)
            for p in method.params:
                dart_type = _dart_cast_type(p.dart_type)
                var_name = _safe_dart_var(p.dart_name)
                lines.append(f'    final {var_name} = args["{p.python_name}"] as {dart_type};')

            # Build null check condition for required params
            required_params = [p for p in method.params if not p.is_optional]

            # Build SDK call arguments. Named params (required or optional)
            # are forwarded as "name: var"; positional params as "var", in
            # declaration order. Optional values are extracted as nullable
            # from the args map and forwarded directly: a collection-`if`
            # (`if (x != null) name: x`) is NOT valid inside a Dart call
            # argument list, and optional named SDK params are nullable.
            sdk_arg_parts = []
            for p in method.params:
                v = _safe_dart_var(p.dart_name)
                if p.is_named:
                    sdk_arg_parts.append(f"{p.dart_name}: {v}")
                else:
                    sdk_arg_parts.append(v)
            sdk_args = ", ".join(sdk_arg_parts)

            if required_params:
                checks = " && ".join(
                    f"{_safe_dart_var(p.dart_name)} != null" for p in required_params
                )
                lines.append(f"    if ({checks}) {{")

                # Determine return handling
                if dart_return == "None":
                    lines.append(f"      {aw}{sdk_accessor}.{original_name}({sdk_args});")
                    lines.append("    }")
                    lines.append("    return null;")
                elif "bool" in dart_return.lower():
                    lines.append(
                        f"      final result = {aw}{sdk_accessor}.{original_name}({sdk_args});"
                    )
                    lines.append("      return result.toString();")
                    lines.append("    }")
                    lines.append("    return null;")
                else:
                    lines.append(
                        f"      final result = {aw}{sdk_accessor}.{original_name}({sdk_args});"
                    )
                    lines.append("      return result?.toString();")
                    lines.append("    }")
                    lines.append("    return null;")
            else:
                # All params are optional - call directly
                if dart_return == "None":
                    lines.append(f"    {aw}{sdk_accessor}.{original_name}({sdk_args});")
                    lines.append("    return null;")
                else:
                    lines.append(
                        f"    final result = {aw}{sdk_accessor}.{original_name}({sdk_args});"
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
                lines.append(f"    {aw}{call};")
                lines.append("    return null;")
            elif "bool" in dart_return.lower():
                lines.append(f"    final result = {aw}{call};")
                lines.append("    return result.toString();")
            elif dart_return in ("str", "str | None"):
                lines.append(f"    return {aw}{call};")
            elif dart_return.startswith("dict") or dart_return.startswith("list"):
                lines.append(f"    final result = {aw}{call};")
                lines.append("    return jsonEncode(result);")
            else:
                lines.append(f"    final result = {aw}{call};")
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

    @staticmethod
    def _method_uses_instance(method: MethodPlan, sub_module: SubModulePlan | None) -> bool:
        """Whether a method is dispatched on an SDK instance (vs a static path).

        A method needs an instance when it is non-static and not routed through a
        namespaced sub-module accessor (those resolve to a static path).
        """
        if method.is_static:
            return False
        return not (sub_module and sub_module.dart_sdk_accessor)


def _to_dart_method_name(snake_name: str) -> str:
    """Convert a snake_case dart method name to a _camelCase Dart function name."""
    parts = snake_name.split("_")
    return "_" + parts[0] + "".join(p.capitalize() for p in parts[1:])


def _to_camel_case(snake_name: str) -> str:
    """Convert snake_case to camelCase."""
    parts = snake_name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _coalesce_child_getter(getter_expr: str, dart_type: str) -> str:
    """Add a ``?? const SizedBox.shrink()`` fallback to a single-child getter.

    ``Control.buildWidget()`` returns ``Widget?``; passing it to a non-nullable
    SDK constructor parameter raises ``argument_type_not_assignable`` in
    ``flutter analyze``. When the Dart param is nullable (``Widget?``) the value
    is forwarded as-is. List children (``buildWidgets``) already return a
    non-null ``List<Widget>`` and are left untouched.
    """
    if "buildWidget(" in getter_expr and not dart_type.endswith("?"):
        return f"{getter_expr} ?? const SizedBox.shrink()"
    return getter_expr


def _ctor_arg_order(props):
    """Order SDK constructor args so child/children (Widget) params come last.

    Satisfies the Dart `sort_child_properties_last` lint. Stable for all other
    params. Child params are detected by their buildWidget/buildWidgets getter.
    """

    def _is_child(p) -> bool:
        getter = p.dart_getter or ""
        return "buildWidget(" in getter or "buildWidgets(" in getter

    return [p for p in props if not _is_child(p)] + [p for p in props if _is_child(p)]


_DART_RESERVED = frozenset(
    {
        "this",
        "super",
        "class",
        "enum",
        "extends",
        "with",
        "implements",
        "abstract",
        "as",
        "assert",
        "break",
        "case",
        "catch",
        "const",
        "continue",
        "default",
        "do",
        "else",
        "false",
        "final",
        "finally",
        "for",
        "if",
        "in",
        "is",
        "new",
        "null",
        "return",
        "switch",
        "throw",
        "true",
        "try",
        "var",
        "void",
        "while",
        "yield",
    }
)


def _safe_dart_var(name: str) -> str:
    """Escape Dart reserved keywords used as variable names."""
    if name in _DART_RESERVED:
        return f"{name}_"
    return name


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
