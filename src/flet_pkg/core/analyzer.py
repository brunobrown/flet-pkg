"""
Package analyzer for Dart-to-Python code generation.

Analyzes a ``DartPackageAPI`` and produces a ``GenerationPlan`` that
drives the code generators: detects namespaces, events, properties,
and maps types.
"""

from __future__ import annotations

import re

from flet_pkg.core.models import (
    DartClass,
    DartMethod,
    DartPackageAPI,
    EnumPlan,
    EventPlan,
    GenerationPlan,
    MethodPlan,
    ParamPlan,
    PropertyPlan,
    StubDataClass,
    SubModulePlan,
)
from flet_pkg.core.parser import camel_to_snake, parse_dart_package_api
from flet_pkg.core.type_map import (
    get_flet_dart_getter,
    map_dart_type,
    map_dart_type_flet,
    map_return_type,
)


class PackageAnalyzer:
    """Analyzes a parsed Dart API and produces a generation plan.

    The analyzer detects:
    - **Namespaces**: Groups of related methods (e.g., User, Notifications)
      that become separate Python sub-module files.
    - **Events**: Listener/Observer methods that become ``ft.EventHandler`` attrs.
    - **Properties**: Constructor params and getters that become dataclass fields.
    - **Enums**: Dart enums that become Python ``Enum`` classes.

    Args:
        min_namespace_methods: Minimum methods to justify a separate sub-module.
    """

    def __init__(self, min_namespace_methods: int = 2):
        self.min_namespace_methods = min_namespace_methods
        self._known_types: frozenset[str] = frozenset()

    def analyze(
        self,
        api: DartPackageAPI,
        control_name: str,
        extension_type: str,
        flutter_package: str = "",
        package_name: str = "",
        description: str = "",
    ) -> GenerationPlan:
        """Analyze a Dart API and produce a GenerationPlan."""
        base_class = "ft.Service" if extension_type == "service" else "ft.LayoutControl"
        control_name_lower = control_name.lower()

        # Build set of known type names for type sanitization.
        # Includes re-exported types AND locally parsed enum names and
        # helper class names so they are not replaced with `dict | None`.
        known = set(api.reexported_types.keys())
        known.update(e.name for e in api.enums)
        known.update(h.name for h in api.helper_classes)
        self._known_types = frozenset(known)

        # Detect the main SDK class (the one matching the control name)
        dart_main_class = self._detect_main_class(api, control_name)

        plan = GenerationPlan(
            control_name=control_name,
            package_name=package_name,
            base_class=base_class,
            description=description,
            flutter_package=flutter_package,
            dart_import=f"package:{flutter_package}/{flutter_package}.dart",
            dart_main_class=dart_main_class,
        )

        # --- UI control path: widget constructor params → properties ---
        has_widget_classes = any(cls.constructor_params for cls in api.classes)
        if extension_type == "ui_control" and has_widget_classes:
            self._process_widget_classes(api, plan, control_name)
        else:
            # --- Service path: methods → async methods ---
            # Detect namespaces by class name prefix
            namespace_classes: dict[str, list[DartClass]] = {}
            main_classes: list[DartClass] = []

            # Single-class packages: the only class IS the main class, no sub-modules
            if len(api.classes) == 1:
                main_classes = api.classes[:]
            else:
                for cls in api.classes:
                    ns = self._detect_namespace(cls, control_name, control_name_lower)
                    if ns:
                        namespace_classes.setdefault(ns, []).append(cls)
                    else:
                        main_classes.append(cls)

            # Infer properties from initialize() method on main class
            for cls in main_classes:
                self._infer_properties_from_initialize(cls, plan)

            # Infer properties from pre-init setter methods (consent, log level, etc.)
            self._infer_pre_init_properties(api, plan, control_name)

            # Process main classes: extract events, properties, methods
            for cls in main_classes:
                self._process_main_class(cls, plan, dart_main_class, api)

            # Detect sub-object namespaces (e.g., User.pushSubscription → fold into user)
            self._fold_sub_objects(api, namespace_classes, control_name, plan)

            # Process namespace classes into sub-modules
            for ns_name, classes in namespace_classes.items():
                # Extract events from namespace classes (events go to main plan)
                for cls in classes:
                    for method in cls.methods:
                        event = self._detect_event(
                            method, control_name, api, dart_main_class, cls.name
                        )
                        if event and not any(
                            e.python_attr_name == event.python_attr_name for e in plan.events
                        ):
                            plan.events.append(event)

                sub_module = self._build_sub_module(
                    ns_name, classes, control_name, dart_main_class, plan
                )
                if sub_module and len(sub_module.methods) >= self.min_namespace_methods:
                    plan.sub_modules.append(sub_module)
                else:
                    # Not enough methods for a sub-module; merge into main
                    for cls in classes:
                        self._process_main_class(cls, plan, dart_main_class, api)

            # Process top-level functions as main methods
            for func in api.top_level_functions:
                method_plan = self._build_method_plan(func, "", dart_main_class)
                if not any(m.python_name == method_plan.python_name for m in plan.main_methods):
                    plan.main_methods.append(method_plan)

        # Process enums — only keep those that are used or commonly useful
        generated_type_names: set[str] = set()
        for dart_enum in api.enums:
            plan.enums.append(
                EnumPlan(
                    python_name=dart_enum.name,
                    values=[(v, v.lower()) for v in dart_enum.values],
                    docstring=dart_enum.docstring,
                )
            )
            generated_type_names.add(dart_enum.name)

        # Generate stub types for re-exported types from platform_interface
        # that are referenced by methods but not locally defined.
        self._generate_reexported_types(api, plan, generated_type_names)

        # Generate data classes from local helper classes (Configuration,
        # Options, Params, etc.) that are referenced as method parameters.
        self._generate_local_data_classes(api, plan, generated_type_names)

        # Set error event class name with short prefix
        prefix = "OS" if control_name.lower().startswith("one") else control_name
        plan.error_event_class = f"{prefix}ErrorEvent"

        # Build dart_listeners from events
        plan.dart_listeners = [
            {
                "event_name": event.dart_event_name,
                "python_attr": event.python_attr_name,
                "dart_listener_method": event.dart_listener_method,
                "dart_sdk_accessor": event.dart_sdk_accessor,
            }
            for event in plan.events
        ]

        return plan

    def resolve_platform_types(
        self,
        api: DartPackageAPI,
        plan: GenerationPlan,
    ) -> None:
        """Download platform_interface packages and resolve stub types.

        Replaces UNKNOWN-only enum stubs and ``data: dict`` stub data
        classes with real values/fields parsed from the source packages.
        """
        from flet_pkg.core.downloader import PubDevDownloader

        # Collect unique source packages that need resolution
        packages_to_resolve: dict[str, list[str]] = {}
        for type_name, source_pkg in api.reexported_types.items():
            if not source_pkg:
                continue
            packages_to_resolve.setdefault(source_pkg, []).append(type_name)

        if not packages_to_resolve:
            return

        downloader = PubDevDownloader()

        for pkg_name, type_names in packages_to_resolve.items():
            try:
                pkg_path = downloader.download(pkg_name)
            except Exception:
                continue

            try:
                platform_api = parse_dart_package_api(pkg_path)
            except Exception:
                continue

            # Build lookup maps from the platform_interface source
            enum_map: dict[str, list[str]] = {}
            for dart_enum in platform_api.enums:
                enum_map[dart_enum.name] = dart_enum.values

            helper_map: dict[str, list[tuple[str, str]]] = {}
            for helper_cls in platform_api.helper_classes:
                fields = []
                for method in helper_cls.methods:
                    if method.is_getter and not method.params:
                        if method.name == helper_cls.name:
                            continue
                        field_name = camel_to_snake(method.name)
                        field_type = map_dart_type(method.return_type)
                        fields.append((field_name, field_type))
                if fields:
                    helper_map[helper_cls.name] = fields

            # Standard Dart object members to skip when extracting fields
            _OBJECT_MEMBERS = {
                "hashCode",
                "runtimeType",
                "toString",
                "noSuchMethod",
                "operator",
                "hash_code",
                "runtime_type",
            }

            def _clean_fields(raw_fields: list[tuple[str, str]]) -> list[tuple[str, str]]:
                """Filter out Dart object members and sanitize types."""
                cleaned = []
                for fname, ftype in raw_fields:
                    if fname in _OBJECT_MEMBERS:
                        continue
                    # Sanitize unknown types to str | None
                    ftype = _sanitize_python_type(ftype, self._known_types)
                    cleaned.append((fname, ftype))
                return cleaned

            # Also check regular classes for data classes with getters/fields
            for cls in platform_api.classes:
                if cls.name in helper_map:
                    continue
                fields = []
                for method in cls.methods:
                    if method.is_getter and not method.params:
                        if method.name == cls.name:
                            continue
                        field_name = camel_to_snake(method.name)
                        field_type = map_dart_type(method.return_type)
                        fields.append((field_name, field_type))
                if fields:
                    helper_map[cls.name] = fields

            # Clean all fields
            for name in helper_map:
                helper_map[name] = _clean_fields(helper_map[name])

            # Update plan enums with real values
            for enum_plan in plan.enums:
                if enum_plan.python_name in enum_map:
                    real_values = enum_map[enum_plan.python_name]
                    if real_values:
                        enum_plan.values = [(v, v.lower()) for v in real_values]
                        enum_plan.docstring = ""

            # Convert stub data classes to enums when platform_interface
            # reveals they are actually enums (not data classes).
            stubs_to_remove: list[StubDataClass] = []
            for stub in plan.stub_data_classes:
                if stub.python_name in enum_map:
                    real_values = enum_map[stub.python_name]
                    if real_values and not any(
                        e.python_name == stub.python_name for e in plan.enums
                    ):
                        plan.enums.append(
                            EnumPlan(
                                python_name=stub.python_name,
                                values=[(v, v.lower()) for v in real_values],
                            )
                        )
                        stubs_to_remove.append(stub)
                elif stub.python_name in helper_map:
                    real_fields = helper_map[stub.python_name]
                    if real_fields:
                        stub.fields = real_fields
                        stub.docstring = ""
            for stub in stubs_to_remove:
                plan.stub_data_classes.remove(stub)

    # ------------------------------------------------------------------
    # Widget class processing (ui_control path)
    # ------------------------------------------------------------------

    # Dart callback/function types that become event handlers
    _CALLBACK_TYPES = {
        "VoidCallback",
        "GestureTapCallback",
        "GestureLongPressCallback",
    }
    _CALLBACK_PREFIXES = (
        "ValueChanged",
        "ValueSetter",
        "ValueGetter",
        "IndexedWidgetBuilder",
        "WidgetBuilder",
        "NullableIndexedWidgetBuilder",
    )

    # Dart types that cannot be serialized to Flet properties (complex objects).
    # Note: simple Flutter enums (Curve, StackFit, Clip, WrapAlignment, etc.)
    # are handled by the type_map and should NOT be listed here.
    _NON_SERIALIZABLE_TYPES = {
        "LinearGradient",
        "Gradient",
        "MaskFilter",
        "Curves",
        "ScrollPhysics",
        "NeverScrollableScrollPhysics",
        "AlwaysScrollableScrollPhysics",
        "EdgeInsetsGeometry",
        "EdgeInsets",
        "BorderRadius",
        "BorderSide",
        "BoxDecoration",
        "ShapeBorder",
        "BoxBorder",
        "TextStyle",
        # Controller types (complex objects, not properties)
        "AnimationController",
        "ScrollController",
        "TextEditingController",
        # Cursor / hit-test types
        "MouseCursor",
        "SystemMouseCursors",
        "HitTestBehavior",
    }

    def _process_widget_classes(
        self,
        api: DartPackageAPI,
        plan: GenerationPlan,
        control_name: str,
    ) -> None:
        """Process widget classes: extract constructor params as properties.

        For ``ui_control`` extensions, widget constructor parameters become
        Flet control properties. Callback params become event handlers.
        Selects the best-matching widget class (not merging all).
        """
        from flet_pkg.core.generators.base import CodeGenerator

        # Select the best-matching widget class for the control name
        widget_classes = [c for c in api.classes if c.constructor_params]
        if not widget_classes:
            return

        main_widget = self._select_main_widget(widget_classes, control_name)
        plan.dart_main_class = main_widget.name

        # Build helper class lookup for type resolution
        helper_map: dict[str, DartClass] = {h.name: h for h in api.helper_classes}

        # Track referenced helper types that need generation
        referenced_helpers: set[str] = set()

        for param in main_widget.constructor_params:
            # Detect callbacks → event handlers
            base_type = re.sub(r"[?<].*", "", param.dart_type).strip()
            is_callback = (
                base_type in self._CALLBACK_TYPES
                or base_type.startswith(self._CALLBACK_PREFIXES)
                or "Function" in param.dart_type
                or "Callback" in param.dart_type
            )

            # Also detect by name: Flutter convention `onXxx` = callback
            if not is_callback and re.match(r"on[A-Z]", param.name):
                is_callback = True

            if is_callback:
                python_attr = camel_to_snake(param.name)
                if not python_attr.startswith("on_"):
                    python_attr = f"on_{python_attr}"
                event_class = f"{control_name}{param.name[0].upper()}{param.name[1:]}Event"
                if not any(e.python_attr_name == python_attr for e in plan.events):
                    plan.events.append(
                        EventPlan(
                            python_attr_name=python_attr,
                            event_class_name=event_class,
                            dart_event_name=python_attr.removeprefix("on_"),
                            dart_listener_method=param.name,
                        )
                    )
                continue

            # Skip non-serializable Flutter types
            if base_type in self._NON_SERIALIZABLE_TYPES:
                continue
            # Skip any Controller or Painter subtype (complex objects)
            if "Controller" in base_type or base_type.endswith("Painter"):
                continue

            # Check if this type references a package helper class
            if base_type in helper_map:
                referenced_helpers.add(base_type)

            # Check for generic type params (e.g., List<SegmentLinearIndicator>)
            generic_match = re.search(r"<(\w+)>", param.dart_type)
            if generic_match:
                inner_type = generic_match.group(1)
                if inner_type in helper_map:
                    referenced_helpers.add(inner_type)

            # Convert to Python property (Flet-aware for ui_control)
            python_name = camel_to_snake(param.name)
            is_ui = plan.base_class != "ft.Service"

            if is_ui:
                python_type = map_dart_type_flet(param.dart_type)
                # None means "skip this property" (e.g. Key)
                if python_type is None:
                    continue
            else:
                python_type = map_dart_type(param.dart_type)

            python_type = _sanitize_python_type(python_type, self._known_types)

            # Determine default value
            default_value = CodeGenerator._py_default(param.default)

            # Use field(default_factory=list) for list types (before nullable logic)
            if python_type.startswith("list[") and default_value in ("None", '""'):
                default_value = "field(default_factory=list)"

            # In Flet controls, all properties are dataclass fields and need
            # defaults. If default is None, the type must be nullable.
            if default_value == "None" and "None" not in python_type:
                python_type = f"{python_type} | None"

            # Compute Dart getter expression for UI controls
            dart_getter = ""
            if is_ui:
                dart_getter = get_flet_dart_getter(python_type, python_name)

            # Skip duplicate properties
            if any(p.python_name == python_name for p in plan.properties):
                continue

            plan.properties.append(
                PropertyPlan(
                    python_name=python_name,
                    python_type=python_type,
                    default_value=default_value,
                    docstring="",
                    dart_getter=dart_getter,
                )
            )

        # Generate dataclasses for referenced helper types (recursive)
        generated_names = {e.python_name for e in plan.enums}
        generated_names.update(s.python_name for s in plan.stub_data_classes)
        pending = list(referenced_helpers)
        while pending:
            helper_name = pending.pop(0)
            if helper_name in generated_names:
                continue
            if helper_name not in helper_map:
                continue
            helper_cls = helper_map[helper_name]
            fields = []
            for method in helper_cls.methods:
                if method.is_getter and not method.params:
                    if method.name == helper_cls.name:
                        continue
                    field_name = camel_to_snake(method.name)
                    field_type = map_dart_type(method.return_type)
                    field_type = _sanitize_python_type(field_type, self._known_types)
                    fields.append((field_name, field_type))
                    # Check if this field type references another helper
                    raw_base = re.sub(r"[?\s|].*", "", method.return_type).strip()
                    if raw_base in helper_map and raw_base not in generated_names:
                        pending.append(raw_base)
            plan.stub_data_classes.append(
                StubDataClass(
                    python_name=helper_name,
                    fields=fields,
                    docstring=helper_cls.docstring,
                )
            )
            generated_names.add(helper_name)

    # Suffixes that indicate internal/non-user-facing widget classes.
    _INTERNAL_WIDGET_SUFFIXES = (
        "SharedTexture",
        "Renderer",
        "Controller",
        "State",
        "Painter",
        "Delegate",
        "Builder",
    )

    def _select_main_widget(self, widget_classes: list[DartClass], control_name: str) -> DartClass:
        """Select the best-matching widget class for the control name.

        Filters out private Dart classes (``_Foo``) and internal helper
        widgets (e.g. ``SharedTexture``, ``Renderer``, ``Controller``).
        """
        control_lower = control_name.lower()

        # Filter out internal/private widget classes
        filtered = [
            cls
            for cls in widget_classes
            if not cls.name.startswith("_")
            and not any(cls.name.endswith(suffix) for suffix in self._INTERNAL_WIDGET_SUFFIXES)
        ]
        # Fallback to unfiltered if everything got excluded
        if not filtered:
            filtered = widget_classes

        # Priority 1: Exact name match
        for cls in filtered:
            if cls.name.lower() == control_lower:
                return cls
        # Priority 2: Name contains control name
        for cls in filtered:
            if control_lower in cls.name.lower():
                return cls
        # Priority 3: Most constructor params (richest API)
        return max(filtered, key=lambda c: len(c.constructor_params))

    # ------------------------------------------------------------------
    # Main SDK class detection
    # ------------------------------------------------------------------

    def _detect_main_class(self, api: DartPackageAPI, control_name: str) -> str:
        """Detect the main SDK class from the package."""
        control_lower = control_name.lower()
        # Priority 1: Exact match
        for cls in api.classes:
            if cls.name.lower() == control_lower:
                return cls.name
        # Priority 2: Match without "Flutter" suffix
        for cls in api.classes:
            name = cls.name.lower()
            if name == control_lower.replace("flutter", ""):
                return cls.name
        # Priority 3: Shortest class that starts with control name prefix
        candidates = [cls for cls in api.classes if cls.name.lower().startswith(control_lower)]
        if candidates:
            return min(candidates, key=lambda c: len(c.name)).name
        # Fallback: control_name as-is
        return control_name

    # ------------------------------------------------------------------
    # Namespace detection
    # ------------------------------------------------------------------

    def _detect_namespace(
        self, cls: DartClass, control_name: str, control_name_lower: str
    ) -> str | None:
        """Detect if a class belongs to a namespace (sub-module)."""
        cls_lower = cls.name.lower()

        # Skip the main class itself
        if cls_lower == control_name_lower:
            return None

        # Check prefix match: e.g., OneSignalUser -> "user"
        if cls_lower.startswith(control_name_lower):
            suffix = cls.name[len(control_name) :]
            if suffix:
                # Only treat as namespace if suffix starts on a PascalCase
                # boundary (uppercase). "LocalAuthentication" with control
                # "LocalAuth" → suffix "entication" (lowercase) = mid-word split.
                if not suffix[0].isupper():
                    return None
                return camel_to_snake(suffix)

        # Check if the class file suggests a namespace
        if cls.source_file:
            stem = cls.source_file.rsplit("/", maxsplit=1)[-1].replace(".dart", "")
            if stem != control_name_lower and not stem.startswith("_"):
                return stem

        return None

    # ------------------------------------------------------------------
    # SDK accessor computation
    # ------------------------------------------------------------------

    def _compute_sdk_accessor(self, cls_name: str, control_name: str, dart_main_class: str) -> str:
        """Compute the SDK accessor path for a class.

        Examples:
            OneSignalUser with main=OneSignal -> "OneSignal.User"
            OneSignalNotifications -> "OneSignal.Notifications"
        """
        if cls_name == dart_main_class:
            return dart_main_class
        # Strip the control name prefix to get the namespace suffix
        control_len = len(control_name)
        if cls_name.lower().startswith(control_name.lower()) and len(cls_name) > control_len:
            suffix = cls_name[control_len:]
            # Only use suffix if it starts on a PascalCase boundary
            if suffix[0].isupper():
                return f"{dart_main_class}.{suffix}"
        return dart_main_class

    # ------------------------------------------------------------------
    # Property inference from initialize() method
    # ------------------------------------------------------------------

    def _infer_properties_from_initialize(self, cls: DartClass, plan: GenerationPlan) -> None:
        """Infer properties from the main class's initialize() method.

        For example, `OneSignal.initialize(String appId)` produces a
        property `app_id: str`.
        """
        for method in cls.methods:
            if method.name != "initialize":
                continue
            for param in method.params:
                python_name = camel_to_snake(param.name)
                python_type = map_dart_type(param.dart_type)
                if not any(p.python_name == python_name for p in plan.properties):
                    plan.properties.append(
                        PropertyPlan(
                            python_name=python_name,
                            python_type=python_type,
                            default_value=_default_for_type(python_type),
                            docstring=f"The {python_name.replace('_', ' ')} "
                            f"for {plan.control_name}.",
                        )
                    )

    # ------------------------------------------------------------------
    # Sub-object folding (e.g., User.pushSubscription → user module)
    # ------------------------------------------------------------------

    def _fold_sub_objects(
        self,
        api: DartPackageAPI,
        namespace_classes: dict[str, list[DartClass]],
        control_name: str,
        plan: GenerationPlan | None = None,
    ) -> None:
        """Fold sub-object namespaces into their parent namespace.

        Detects when a namespace class (e.g., ``OneSignalPushSubscription``)
        is accessed as a getter on another namespace class (e.g.,
        ``OneSignalUser.pushSubscription``).  When found, the sub-object's
        methods are renamed with a short prefix and merged into the parent.

        Events from folded classes are extracted before listener methods
        are removed, ensuring they appear on the main control.
        """
        # Build class name → namespace mapping
        class_to_ns: dict[str, str] = {}
        for ns, classes in namespace_classes.items():
            for cls in classes:
                class_to_ns[cls.name] = ns

        # Scan for getter methods that return another namespace class
        # (child_ns, parent_ns, getter_name_prefix)
        folds: list[tuple[str, str, str]] = []
        for cls in api.classes:
            parent_ns = class_to_ns.get(cls.name)
            if not parent_ns:
                continue
            for method in cls.methods:
                if not method.is_getter or method.params:
                    continue
                ret_clean = method.return_type.rstrip("?")
                child_ns = class_to_ns.get(ret_clean)
                if child_ns and child_ns != parent_ns:
                    # Derive a short prefix from the getter name
                    # e.g., "pushSubscription" → "push"
                    getter_snake = camel_to_snake(method.name)
                    short_prefix = getter_snake.split("_")[0]
                    folds.append((child_ns, parent_ns, short_prefix))

        # Execute folds: extract events first, then rename and merge
        for child_ns, parent_ns, prefix in folds:
            if child_ns not in namespace_classes or parent_ns not in namespace_classes:
                continue

            # Extract events from child classes BEFORE removing listener methods
            if plan:
                for cls in namespace_classes[child_ns]:
                    for method in cls.methods:
                        event = self._detect_event(
                            method,
                            control_name,
                            api,
                            plan.dart_main_class,
                            cls.name,
                        )
                        if event and not any(
                            e.python_attr_name == event.python_attr_name for e in plan.events
                        ):
                            plan.events.append(event)

            # Find the full getter name for richer naming (e.g., "push_subscription")
            full_getter_snake = ""
            for cls_check in api.classes:
                if class_to_ns.get(cls_check.name) != parent_ns:
                    continue
                for m in cls_check.methods:
                    if m.is_getter and class_to_ns.get(m.return_type.rstrip("?")) == child_ns:
                        full_getter_snake = camel_to_snake(m.name)
                        break

            for cls in namespace_classes[child_ns]:
                # Filter out listener/observer methods before renaming
                cls.methods = [
                    m
                    for m in cls.methods
                    if not re.match(r"add\w*(Listener|Observer|Handler)$", m.name)
                    and not re.match(r"remove\w*(Listener|Observer|Handler)$", m.name)
                ]
                # Rename methods using intelligent prefix strategy
                for method in cls.methods:
                    if method.name.lower().startswith(prefix):
                        continue  # Already has prefix
                    if method.is_getter and not method.params:
                        # Getters use full name: id → GetPushSubscriptionId
                        cap_full = (
                            "".join(w.capitalize() for w in full_getter_snake.split("_"))
                            if full_getter_snake
                            else prefix.capitalize()
                        )
                        method.name = "Get" + cap_full + method.name[0].upper() + method.name[1:]
                    elif method.return_type in ("void", "Future<void>") and not method.params:
                        # Void no-param actions: optIn → OptInPush (verb first)
                        method.name = method.name + prefix[0].upper() + prefix[1:]
                    else:
                        # Default: prefix normally: "foo" → "PushFoo"
                        method.name = prefix.capitalize() + method.name[0].upper() + method.name[1:]
            # Remove the getter method on the parent that returned the child
            for parent_cls in namespace_classes[parent_ns]:
                parent_cls.methods = [
                    m
                    for m in parent_cls.methods
                    if not (m.is_getter and m.return_type.rstrip("?") in class_to_ns)
                ]
            namespace_classes[parent_ns].extend(namespace_classes[child_ns])
            del namespace_classes[child_ns]

    # ------------------------------------------------------------------
    # Pre-init property inference from setter methods
    # ------------------------------------------------------------------

    def _infer_pre_init_properties(
        self,
        api: DartPackageAPI,
        plan: GenerationPlan,
        control_name: str,
    ) -> None:
        """Infer properties from pre-init setter methods.

        Detects patterns like:
        - ``consentRequired(bool)`` → ``require_consent: bool``
        - ``Debug.setLogLevel(OSLogLevel)`` → ``log_level: int``
        - ``Debug.setAlertLevel(OSLogLevel)`` → ``visual_alert_level: int``

        These become control properties read at Dart init time, before
        the SDK ``initialize()`` call.
        """
        enum_names = {e.name for e in api.enums}

        for cls in api.classes:
            for method in cls.methods:
                # Must be void + single non-callback param
                if method.return_type not in ("void", "Future<void>"):
                    continue
                if len(method.params) != 1:
                    continue
                param = method.params[0]
                if "Function" in param.dart_type or "Callback" in param.dart_type:
                    continue

                prop_name: str | None = None
                prop_type: str = ""
                prop_default: str = "None"
                prop_doc: str = ""

                dart_pre_init_call = ""

                # Pattern: consentRequired(bool) → require_consent
                if "consent" in method.name.lower() and "required" in method.name.lower():
                    prop_name = "require_consent"
                    prop_type = "bool"
                    prop_default = "False"
                    prop_doc = "Whether consent is required before initializing."
                    sdk_accessor = self._compute_sdk_accessor(
                        cls.name, control_name, plan.dart_main_class
                    )
                    dart_pre_init_call = f"if ({{var}}) {{ {sdk_accessor}.{method.name}(true); }}"

                # Pattern: setLogLevel(EnumType) → log_level
                elif method.name.startswith("set") and param.dart_type in enum_names:
                    raw_name = method.name[3:]
                    prop_name = camel_to_snake(raw_name)
                    # If method name contains "Alert" or "Visual", prefer
                    # "visual_alert_level" to match common SDK conventions
                    if "alert" in raw_name.lower() and "visual" not in prop_name:
                        prop_name = f"visual_{prop_name}"
                    enum_type = param.dart_type
                    prop_type = f"Optional[{enum_type}]"
                    prop_default = "None"
                    prop_doc = method.docstring or f"The {prop_name.replace('_', ' ')}."
                    sdk_accessor = self._compute_sdk_accessor(
                        cls.name, control_name, plan.dart_main_class
                    )
                    dart_pre_init_call = (
                        f"if ({{var}} != null) {{ "
                        f"{sdk_accessor}.{method.name}"
                        f"({enum_type}.values[{{var}}.value]); }}"
                    )

                if prop_name and not any(p.python_name == prop_name for p in plan.properties):
                    plan.properties.append(
                        PropertyPlan(
                            python_name=prop_name,
                            python_type=prop_type,
                            default_value=prop_default,
                            docstring=prop_doc,
                            dart_pre_init_call=dart_pre_init_call,
                        )
                    )

    # ------------------------------------------------------------------
    # Main class processing
    # ------------------------------------------------------------------

    def _process_main_class(
        self,
        cls: DartClass,
        plan: GenerationPlan,
        dart_main_class: str,
        api: DartPackageAPI | None = None,
    ) -> None:
        """Extract events, properties, and methods from a main class."""
        # Collect property names to skip methods already converted to properties
        prop_methods = set()
        for method in cls.methods:
            if method.name == "initialize":
                prop_methods.add(method.name)
            elif "consent" in method.name.lower() and "required" in method.name.lower():
                prop_methods.add(method.name)

        for method in cls.methods:
            # Skip methods that were converted to properties
            if method.name in prop_methods:
                continue

            # Check if this method is an event listener
            event = self._detect_event(method, plan.control_name, api, dart_main_class, cls.name)
            if event:
                if not any(e.python_attr_name == event.python_attr_name for e in plan.events):
                    plan.events.append(event)
                continue

            # Detect Stream<T> getter as event source (e.g., onBatteryStateChanged)
            stream_event = self._detect_stream_event(method, plan.control_name, api)
            if stream_event:
                if not any(
                    e.python_attr_name == stream_event.python_attr_name for e in plan.events
                ):
                    plan.events.append(stream_event)
                continue

            # Skip remove*Listener/Observer methods
            if self._is_remove_listener_method(method):
                continue

            # Skip methods with callback params (can't serialize over wire)
            if self._has_callback_params(method):
                continue

            # Skip setter methods that were converted to properties
            if self._is_property_setter(method, plan):
                continue

            # Check if this is a synchronous getter -> property
            # Async getters (Future<T>) become methods, not properties,
            # because they require an await call to Flutter.
            if method.is_getter and not method.params and not method.is_async:
                prop = PropertyPlan(
                    python_name=camel_to_snake(method.name),
                    python_type=map_dart_type(method.return_type),
                    default_value=_default_for_type(map_dart_type(method.return_type)),
                    docstring=method.docstring,
                )
                if not any(p.python_name == prop.python_name for p in plan.properties):
                    plan.properties.append(prop)
                continue

            # Regular method
            method_plan = self._build_method_plan(method, "", cls.name)
            if not any(m.python_name == method_plan.python_name for m in plan.main_methods):
                plan.main_methods.append(method_plan)

    # ------------------------------------------------------------------
    # Sub-module building
    # ------------------------------------------------------------------

    def _build_sub_module(
        self,
        ns_name: str,
        classes: list[DartClass],
        control_name: str,
        dart_main_class: str,
        plan: GenerationPlan | None = None,
    ) -> SubModulePlan | None:
        """Build a SubModulePlan from namespace classes."""
        class_name = f"{control_name}{ns_name.replace('_', ' ').title().replace(' ', '')}"
        dart_prefix = ns_name

        methods: list[MethodPlan] = []
        docstrings: list[str] = []
        dart_class_name = ""
        dart_sdk_accessor = ""

        for cls in classes:
            if cls.docstring:
                docstrings.append(cls.docstring)
            if not dart_class_name:
                dart_class_name = cls.name
                dart_sdk_accessor = self._compute_sdk_accessor(
                    cls.name, control_name, dart_main_class
                )
            for method in cls.methods:
                # Skip event listeners (handled at main level)
                if self._is_listener_method(method):
                    continue
                # Skip remove*Listener/Observer methods
                if self._is_remove_listener_method(method):
                    continue
                # Skip methods with callback params
                if self._has_callback_params(method):
                    continue
                # Skip setter methods that were converted to properties
                # (but keep them in namespace sub-modules for runtime use)
                if plan and self._is_property_setter(method, plan, in_namespace=True):
                    pass  # Keep in namespace as method
                method_plan = self._build_method_plan(method, dart_prefix, cls.name)
                if not any(m.python_name == method_plan.python_name for m in methods):
                    methods.append(method_plan)

        if not methods:
            return None

        return SubModulePlan(
            module_name=ns_name,
            class_name=class_name,
            dart_prefix=dart_prefix,
            methods=methods,
            docstring=(
                " ".join(docstrings) if docstrings else f"{control_name} {ns_name} namespace."
            ),
            dart_class_name=dart_class_name,
            dart_sdk_accessor=dart_sdk_accessor,
        )

    # ------------------------------------------------------------------
    # Method building
    # ------------------------------------------------------------------

    def _build_method_plan(
        self,
        method: DartMethod,
        dart_prefix: str,
        dart_class_name: str,
    ) -> MethodPlan:
        """Convert a DartMethod to a MethodPlan."""
        python_name = camel_to_snake(method.name)

        # Invoke key = "{module_name}_{python_method_name}" — no abbreviation
        if dart_prefix:
            dart_method_name = f"{dart_prefix}_{python_name}"
        else:
            dart_method_name = python_name

        # Normalize common naming patterns for Pythonic API
        python_name, dart_method_name = _normalize_method_name(
            python_name,
            dart_method_name,
            method,
            dart_prefix,
        )

        python_return, _dart_is_async = map_return_type(method.return_type)
        # Sanitize return type: replace unknown Dart classes with dict | None
        python_return = _sanitize_python_type(python_return, self._known_types)

        params: list[ParamPlan] = []
        for p in method.params:
            python_type = map_dart_type(p.dart_type)
            # Sanitize: replace unknown Dart classes with dict | None
            python_type = _sanitize_python_type(python_type, self._known_types)
            raw_name = camel_to_snake(p.name) if p.name != p.name.lower() else p.name
            # Normalize param name: strip namespace words, simplify redundant names
            param_name = _normalize_param_name(raw_name)
            params.append(
                ParamPlan(
                    python_name=param_name,
                    python_type=python_type,
                    dart_name=p.name,
                    dart_type=p.dart_type,
                    is_optional=not p.required and p.named,
                    is_named=p.named,
                    default=p.default,
                )
            )

        # ALL methods are forced async because they call _invoke_method
        return MethodPlan(
            python_name=python_name,
            dart_method_name=dart_method_name,
            params=params,
            return_type=python_return,
            docstring=method.docstring,
            is_async=True,
            is_getter=method.is_getter,
            dart_original_name=method.name,
            dart_class_name=dart_class_name,
        )

    # ------------------------------------------------------------------
    # Stream-based event detection
    # ------------------------------------------------------------------

    def _detect_stream_event(
        self,
        method: DartMethod,
        control_name: str,
        api: DartPackageAPI | None,
    ) -> EventPlan | None:
        """Detect Stream<T> methods/getters as event sources.

        Flutter packages commonly expose event sources as either:
        - ``Stream<T> get onXxxChanged`` (getter with "on" prefix)
        - ``Stream<T> getPositionStream(...)`` (method returning Stream)

        These are converted to ``on_xxx`` event handlers on the Python side.
        """
        if not method.return_type.startswith("Stream"):
            return None

        # Accept: getters starting with "on", OR any method returning Stream<T>
        is_on_getter = method.is_getter and method.name.startswith("on")
        is_stream_method = not method.is_getter and "Stream" in method.return_type
        if not is_on_getter and not is_stream_method:
            return None

        # Extract event type from Stream<T>
        stream_match = re.match(r"Stream<(\w+)\??>?", method.return_type)
        event_type_name = stream_match.group(1) if stream_match else "dynamic"

        # Build event name
        if is_on_getter:
            # onBatteryStateChanged → on_battery_state_changed
            python_attr = camel_to_snake(method.name)
        else:
            # getPositionStream → on_position_stream
            # getServiceStatusStream → on_service_status_stream
            snake = camel_to_snake(method.name)
            # Remove get_ prefix and _stream suffix for cleaner names
            clean = snake.removeprefix("get_").removesuffix("_stream")
            python_attr = f"on_{clean}"

        if not python_attr.startswith("on_"):
            python_attr = f"on_{python_attr}"
        dart_event_name = python_attr.removeprefix("on_")

        # Derive event class name
        prefix = "OS" if control_name.lower().startswith("one") else control_name
        event_class_name = f"{prefix}{event_type_name}Event"
        if event_type_name.endswith("Event"):
            event_class_name = f"{prefix}{event_type_name}"

        # Extract fields from helper class if available
        fields: list[tuple[str, str]] = [("value", "str")]
        if api:
            for helper_cls in api.helper_classes:
                if helper_cls.name == event_type_name:
                    fields = self._extract_fields_from_helper(helper_cls, api)
                    break

        return EventPlan(
            python_attr_name=python_attr,
            event_class_name=event_class_name,
            dart_event_name=dart_event_name,
            fields=fields,
            dart_listener_method=method.name,
            dart_sdk_accessor="",
        )

    # ------------------------------------------------------------------
    # Event detection (listener pattern)
    # ------------------------------------------------------------------

    def _detect_event(
        self,
        method: DartMethod,
        control_name: str,
        api: DartPackageAPI | None,
        dart_main_class: str,
        source_class_name: str,
    ) -> EventPlan | None:
        """Detect if a method registers an event listener."""
        name = method.name

        # Patterns: addXxxListener, addXxxObserver, addXxxHandler
        # Also: addListener, addObserver (empty core)
        listener_match = re.match(r"add(\w*?)(Listener|Observer|Handler)$", name)
        if not listener_match:
            return None

        event_core = listener_match.group(1)

        # Build a meaningful event name with namespace prefix
        sdk_accessor = self._compute_sdk_accessor(source_class_name, control_name, dart_main_class)
        # Determine namespace prefix for event naming
        ns_prefix = self._event_namespace_prefix(source_class_name, control_name)

        # If event_core is empty (e.g., addObserver), derive from context
        if not event_core:
            event_core = self._derive_event_core_from_context(
                method, source_class_name, control_name, api
            )
        else:
            # Enrich event_core from typedef name if it provides more info
            # E.g., method "addPermissionObserver" → core "Permission"
            # but typedef "OnNotificationPermissionChangeObserver" → "PermissionChange"
            event_core = self._enrich_event_core(event_core, method, api)

        snake = camel_to_snake(event_core) if event_core else "change"

        # Shorten verbose event names:
        # "foreground_will_display" → "foreground" (will_display is implied)
        snake = _shorten_event_name(snake)

        # Deduplicate: if snake already starts with the namespace prefix,
        # strip it to avoid "on_user_user_change" → "on_user_change".
        if ns_prefix and snake.startswith(ns_prefix + "_"):
            snake = snake[len(ns_prefix) + 1 :]
        elif ns_prefix and snake.startswith(ns_prefix):
            snake = snake[len(ns_prefix) :].lstrip("_") or "change"

        if ns_prefix:
            python_attr = f"on_{ns_prefix}_{snake}"
            dart_event_name = f"{ns_prefix}_{snake}"
        else:
            python_attr = f"on_{snake}"
            dart_event_name = snake

        # Try to extract the event type name from callback parameter
        event_class_name = self._derive_event_class_name(method, control_name, event_core, api)

        # Extract event fields from helper classes if available
        fields = self._extract_event_fields(method, api)

        return EventPlan(
            python_attr_name=python_attr,
            event_class_name=event_class_name,
            dart_event_name=dart_event_name,
            fields=fields,
            dart_listener_method=name,
            dart_sdk_accessor=sdk_accessor,
        )

    def _enrich_event_core(
        self,
        event_core: str,
        method: DartMethod,
        api: DartPackageAPI | None,
    ) -> str:
        """Enrich event_core from typedef/callback type name.

        If the method name gives a short core like "Permission", the typedef
        name ``OnNotificationPermissionChangeObserver`` provides the richer
        "PermissionChange".
        """
        if not api or not method.params:
            return event_core

        cb_type = method.params[0].dart_type
        # Look for On{Prefix}{EventCore}{Extra}(Observer|Listener|Handler) pattern
        # The non-capturing group MUST match (required prefix between On and event_core)
        # This prevents matching OnClickInAppMessageListener with event_core="Click"
        # but DOES match OnNotificationPermissionChangeObserver with event_core="Permission"
        m = re.match(
            r"On[A-Z]\w+?(" + re.escape(event_core) + r"\w*?)"
            r"(Observer|Listener|Handler|Change)$",
            cb_type,
        )
        if m:
            enriched = m.group(1)
            suffix = m.group(2)
            if suffix == "Change" and not enriched.endswith("Change"):
                enriched += "Change"
            if len(enriched) > len(event_core):
                return enriched

        return event_core

    def _derive_event_core_from_context(
        self,
        method: DartMethod,
        source_class_name: str,
        control_name: str,
        api: DartPackageAPI | None,
    ) -> str:
        """Derive event core name when the listener method has no descriptive name.

        For example: ``OneSignalUser.addObserver`` → event core "Change"
        (derived from callback type ``OnUserChangeObserver``).
        """
        # Try to extract from callback parameter typedef name
        if method.params:
            param_type = method.params[0].dart_type
            # Pattern: On{Something}Observer/Listener → extract {Something}
            m = re.match(r"On(\w+?)(Observer|Listener|Handler|Change)$", param_type)
            if m:
                return m.group(1) + (m.group(2) if m.group(2) == "Change" else "")

            # Try typedef resolution
            if api and param_type in api.typedefs:
                resolved_type = api.typedefs[param_type]
                # Look for Change/Changed in the resolved type name
                m2 = re.match(r"\w*?(Change\w*|Changed\w*)$", resolved_type)
                if m2:
                    return m2.group(1)

        # Fallback: derive from class name
        suffix = source_class_name[len(control_name) :]
        if suffix:
            return suffix + "Change"
        return "Change"

    def _event_namespace_prefix(self, source_class_name: str, control_name: str) -> str:
        """Compute a short prefix for event names based on source class.

        OneSignalNotifications -> "notification"
        OneSignalInAppMessages -> "iam"
        OneSignal (main) -> "" (no prefix)
        """
        if source_class_name.lower() == control_name.lower():
            return ""
        suffix = source_class_name[len(control_name) :]
        if not suffix:
            return ""
        snake = camel_to_snake(suffix)
        # Common abbreviations
        abbreviations = {
            "notifications": "notification",
            "in_app_messages": "iam",
            "push_subscription": "push_subscription",
        }
        return abbreviations.get(snake, snake)

    def _derive_event_class_name(
        self,
        method: DartMethod,
        control_name: str,
        event_core: str,
        api: DartPackageAPI | None = None,
    ) -> str:
        """Derive a proper event class name.

        Always returns names ending in ``Event``.  If the Dart SDK uses
        a ``*State``/``*ChangedState`` type for its observer callback, the
        generated Python event class is still named ``*Event`` for
        consistency.
        """
        # Check callback parameter for a type hint
        if method.params:
            cb_type = method.params[0].dart_type

            # Direct match: parameter type already contains "Event"
            type_match = re.search(r"\b([A-Z]\w+Event)\b", cb_type)
            if type_match:
                return type_match.group(1)

            # Resolve typedef to find event type
            if api and cb_type in api.typedefs:
                resolved = api.typedefs[cb_type]
                type_match = re.search(r"\b([A-Z]\w+)\b", resolved)
                if type_match:
                    resolved_name = type_match.group(1)
                    # Normalize *State → *Event
                    return _normalize_event_class_name(resolved_name)

        # Generate name: OS + EventCore + Event
        prefix = "OS" if control_name.lower().startswith("one") else control_name
        return f"{prefix}{event_core}Event"

    def _extract_event_fields(
        self,
        method: DartMethod,
        api: DartPackageAPI | None,
    ) -> list[tuple[str, str]]:
        """Extract typed event fields from the callback's event type class."""
        if not api or not method.params:
            return [("data", "dict")]

        cb_type = method.params[0].dart_type

        # Resolve typedef first
        actual_type = cb_type
        if cb_type in api.typedefs:
            actual_type = api.typedefs[cb_type]

        # For simple/primitive callback types (e.g., bool for permission change)
        if actual_type in ("bool", "bool?"):
            return [("value", "bool")]
        if actual_type in ("String", "String?"):
            return [("value", "str")]
        if actual_type in ("int", "int?"):
            return [("value", "int")]

        # Try to find the event type in helper_classes
        type_match = re.search(r"\b([A-Z]\w+)\b", actual_type)
        if not type_match:
            return [("data", "dict")]

        event_type_name = type_match.group(1)

        # Search helper_classes for matching type
        for helper_cls in api.helper_classes:
            if helper_cls.name == event_type_name:
                return self._extract_fields_from_helper(helper_cls, api)

        return [("data", "dict")]

    def _extract_fields_from_helper(
        self,
        helper_cls: DartClass,
        api: DartPackageAPI,
    ) -> list[tuple[str, str]]:
        """Extract fields from a helper class, following nested types.

        When a helper has a ``current`` field pointing to another helper,
        the nested fields are expanded in-place so the Python event carries
        the leaf-level data directly.
        """
        fields: list[tuple[str, str]] = []

        for m in helper_cls.methods:
            if not m.is_getter or m.params:
                continue
            py_name = camel_to_snake(m.name)
            py_type = map_dart_type(m.return_type)
            dart_type_clean = m.return_type.rstrip("?")

            # If this field points to another helper class, expand it
            nested_cls = None
            for hc in api.helper_classes:
                if hc.name == dart_type_clean:
                    nested_cls = hc
                    break

            if nested_cls and py_name in ("current", "previous"):
                # Expand "current" inline; skip "previous" (redundant)
                if py_name == "current":
                    nested_fields = self._extract_fields_from_helper(nested_cls, api)
                    if nested_fields and nested_fields != [("data", "dict")]:
                        fields.extend(nested_fields)
                continue

            # Simplify complex types to basic Python types
            if (
                py_type
                not in (
                    "str",
                    "int",
                    "float",
                    "bool",
                    "Any",
                    "str | None",
                    "int | None",
                    "float | None",
                    "bool | None",
                )
                and not py_type.startswith("list")
                and not py_type.startswith("dict")
            ):
                py_type = "dict"
            fields.append((py_name, py_type))

        if fields:
            return fields

        return [("data", "dict")]

    # ------------------------------------------------------------------
    # Re-exported type generation
    # ------------------------------------------------------------------

    def _generate_reexported_types(
        self,
        api: DartPackageAPI,
        plan: GenerationPlan,
        generated_type_names: set[str],
    ) -> None:
        """Generate stub types for re-exported types from platform_interface.

        Uses naming heuristics to determine if a re-exported type is an
        enum, a data class, or an exception type, and generates appropriate
        stubs so that generated code can reference them without NameError.
        """
        # Collect all type names referenced in the plan
        referenced = self._collect_referenced_types(plan)

        # Suffixes that indicate enum types
        _ENUM_SUFFIXES = (
            "Type",
            "State",
            "Status",
            "Mode",
            "Level",
            "Source",
            "Device",
            "Permission",
            "Accuracy",
            "Direction",
        )
        # Suffixes that indicate data/params classes
        _DATA_SUFFIXES = (
            "Params",
            "Result",
            "Options",
            "Configuration",
            "Config",
            "Settings",
            "Info",
            "Response",
            "Position",
            "Data",
            "File",
        )
        # Suffixes to skip (widget/callback types not useful on Python side)
        _SKIP_SUFFIXES = ("Builder", "Delegate", "Callback", "Link", "Target")

        for type_name, _source_pkg in api.reexported_types.items():
            if type_name in generated_type_names:
                continue  # Already generated from local source
            if type_name.startswith("_"):
                continue
            if any(type_name.endswith(s) for s in _SKIP_SUFFIXES):
                continue
            # Only generate types that are actually referenced
            if type_name not in referenced and type_name not in self._known_types:
                continue

            if any(type_name.endswith(s) for s in _ENUM_SUFFIXES):
                # Generate as enum with a string value fallback
                plan.enums.append(
                    EnumPlan(
                        python_name=type_name,
                        values=[("UNKNOWN", "unknown")],
                        docstring=(
                            f"{type_name} enum (stub — values should be filled "
                            f"from the {_source_pkg} platform interface)."
                        ),
                    )
                )
                generated_type_names.add(type_name)
            elif any(type_name.endswith(s) for s in _DATA_SUFFIXES):
                # Generate as a stub dataclass in types.py
                plan.stub_data_classes.append(
                    StubDataClass(
                        python_name=type_name,
                        fields=[("data", "dict")],
                        docstring=(
                            f"{type_name} data class (stub — fields should be "
                            f"filled from the {_source_pkg} platform interface)."
                        ),
                    )
                )
                generated_type_names.add(type_name)
            elif type_name in referenced:
                # Fallback: generate as enum stub for any referenced type
                # that didn't match known suffixes (e.g. LocationPermission,
                # ImageSource, XFile). This prevents NameError at runtime.
                plan.enums.append(
                    EnumPlan(
                        python_name=type_name,
                        values=[("UNKNOWN", "unknown")],
                        docstring=(
                            f"{type_name} enum (stub — values should be filled "
                            f"from the {_source_pkg} platform interface)."
                        ),
                    )
                )
                generated_type_names.add(type_name)

    def _generate_local_data_classes(
        self,
        api: DartPackageAPI,
        plan: GenerationPlan,
        generated_type_names: set[str],
    ) -> None:
        """Generate Python dataclasses from local helper classes.

        Detects helper classes (Configuration, Options, Params, etc.)
        that are referenced as method parameter types and generates
        proper Python dataclasses with their parsed fields.
        """
        referenced = self._collect_referenced_types(plan)

        # Data class suffixes (these helper classes have useful fields)
        _DATA_SUFFIXES = (
            "Configuration",
            "Config",
            "Settings",
            "Options",
            "Params",
            "Info",
            "Result",
            "Response",
            "Position",
            "Data",
            "File",
        )
        # Event suffixes should not be generated as data classes
        _SKIP_SUFFIXES = ("Event", "State", "ChangedState")

        for helper_cls in api.helper_classes:
            name = helper_cls.name
            if name in generated_type_names:
                continue
            if name.startswith("_"):
                continue
            if any(name.endswith(s) for s in _SKIP_SUFFIXES):
                continue
            if not any(name.endswith(s) for s in _DATA_SUFFIXES):
                continue
            # Only generate if actually referenced by methods
            if name not in referenced:
                continue

            # Extract fields from the helper class methods (which includes
            # parsed instance fields when skip_filter=False)
            fields: list[tuple[str, str]] = []
            for method in helper_cls.methods:
                if method.is_getter and not method.params:
                    # Skip constructor entries (name matches class name)
                    if method.name == name:
                        continue
                    field_name = camel_to_snake(method.name)
                    field_type = map_dart_type(method.return_type)
                    fields.append((field_name, field_type))

            if not fields:
                fields = [("data", "dict")]

            plan.stub_data_classes.append(
                StubDataClass(
                    python_name=name,
                    fields=fields,
                    docstring=helper_cls.docstring or f"{name} configuration.",
                )
            )
            generated_type_names.add(name)

    def _collect_referenced_types(self, plan: GenerationPlan) -> set[str]:
        """Collect all type names referenced by methods, params, and return types."""
        refs: set[str] = set()
        all_methods = list(plan.main_methods)
        for sub in plan.sub_modules:
            all_methods.extend(sub.methods)
        for method in all_methods:
            # Check return type
            base = method.return_type.split("[")[0].split("|")[0].strip()
            if base and base[0].isupper():
                refs.add(base)
            for p in method.params:
                base = p.python_type.split("[")[0].split("|")[0].strip()
                if base and base[0].isupper():
                    refs.add(base)
                base_dart = p.dart_type.rstrip("?")
                if base_dart and base_dart[0].isupper():
                    refs.add(base_dart)
        return refs

    # ------------------------------------------------------------------
    # Helper checks
    # ------------------------------------------------------------------

    def _is_listener_method(self, method: DartMethod) -> bool:
        """Check if a method is a listener registration."""
        return bool(re.match(r"add\w*(Listener|Observer|Handler)$", method.name))

    def _is_remove_listener_method(self, method: DartMethod) -> bool:
        """Check if a method is a listener removal."""
        return bool(re.match(r"remove\w*(Listener|Observer|Handler)$", method.name))

    def _has_callback_params(self, method: DartMethod) -> bool:
        """Check if any params are callback/function types (not serializable)."""
        for p in method.params:
            t = p.dart_type
            if "Function" in t or "Callback" in t or "void " in t:
                return True
        return False

    def _is_property_setter(
        self, method: DartMethod, plan: GenerationPlan, *, in_namespace: bool = False
    ) -> bool:
        """Check if a setter method was converted to a property.

        When ``in_namespace`` is True, the setter is kept as a method
        (for runtime use from the sub-module) and NOT skipped.
        """
        if in_namespace:
            return False  # Keep setters as methods in sub-modules
        if not method.name.startswith("set") or len(method.params) != 1:
            return False
        raw_name = method.name[3:]
        prop_name = camel_to_snake(raw_name)
        return any(p.python_name == prop_name for p in plan.properties)


def _shorten_event_name(snake: str) -> str:
    """Shorten verbose event names.

    ``foreground_will_display`` → ``foreground``
    (the "will_display"/"did_display" part is implied by the event handler.)
    """
    # Remove trailing lifecycle suffixes that are already implied
    for suffix in ("_will_display", "_did_display", "_will_dismiss", "_did_dismiss"):
        if snake.endswith(suffix) and len(snake) > len(suffix):
            return snake[: -len(suffix)]
    return snake


def _normalize_event_class_name(name: str) -> str:
    """Normalize a Dart type name to a Python event class name.

    Ensures the name ends with ``Event``.  Replaces ``*State``/``*ChangedState``
    suffixes with ``Event``.
    """
    if name.endswith("Event"):
        return name
    if name.endswith("ChangedState"):
        return name[: -len("ChangedState")] + "ChangedEvent"
    if name.endswith("State"):
        return name[: -len("State")] + "Event"
    return name + "Event"


def _normalize_param_name(param_name: str) -> str:
    """Normalize parameter names — keep original Dart names (camel_to_snake).

    Minimal normalization: the direct ``camel_to_snake`` mapping from Dart
    parameter names is usually the best Python name.
    """
    return param_name


def _normalize_method_name(
    python_name: str,
    dart_method_name: str,
    method: DartMethod,
    dart_prefix: str,
) -> tuple[str, str]:
    """Normalize method naming for Pythonic conventions.

    Applies minimal patterns:
    - Bare getter methods (no params, non-void return) → add ``get_`` or ``is_`` prefix
    - Otherwise keep the direct ``camel_to_snake`` mapping from Dart
    """

    def _rebuild_dart_key(new_name: str) -> str:
        if dart_prefix:
            return f"{dart_prefix}_{new_name}"
        return new_name

    # Verb prefixes that already convey meaning — don't add get_/is_ on top
    _VERB_PREFIXES = ("get_", "is_", "are_", "can_", "has_", "should_", "does_", "will_", "was_")

    # Bare getter: no params, non-void return, no existing verb prefix → add "get_" or "is_"
    if (
        method.is_getter
        and not method.params
        and method.return_type not in ("void", "Future<void>")
        and not any(python_name.startswith(vp) for vp in _VERB_PREFIXES)
    ):
        is_bool = method.return_type in ("bool", "bool?", "Future<bool>", "Future<bool?>")
        prefix_word = "is_" if is_bool else "get_"
        python_name = f"{prefix_word}{python_name}"
        dart_method_name = _rebuild_dart_key(python_name)

    return python_name, dart_method_name


# Suffixes that strongly indicate a Dart enum type.  When an unknown type
# ends with one of these, ``_sanitize_python_type`` maps it to ``str``
# (serialised as a string on the wire) instead of ``dict | None``.
# This handles enums from transitive dependencies that the parser never
# downloads (e.g. ``RiveHitTestBehavior`` from ``rive_native``).
_ENUM_LIKE_SUFFIXES = (
    "Behavior",
    "Behaviour",
    "Mode",
    "Style",
    "Kind",
    "Fit",
    "Order",
    "Level",
    "Direction",
    "Action",
    "Axis",
    "Clip",
    "Curve",
    "Cap",
    "Join",
)

# Python types that are valid and should not be replaced
_KNOWN_PYTHON_TYPES = frozenset(
    {
        "str",
        "int",
        "float",
        "bool",
        "bytes",
        "None",
        "Any",
        "list",
        "dict",
        "set",
        "tuple",
        "Optional",
    }
)


def _sanitize_python_type(
    python_type: str,
    known_types: frozenset[str] = frozenset(),
) -> str:
    """Replace unknown Dart class types with ``dict | None``.

    Types like ``LiveActivitySetupOptions`` that pass through the
    type_map unchanged are replaced with a safe fallback, since
    they won't exist in the generated Python code.

    *known_types* contains re-exported type names from the package
    barrel file that should be preserved (e.g. ``BiometricType``).
    """
    # Strip nullable suffix for checking (use proper substring match,
    # not rstrip which removes individual characters).
    is_nullable = python_type.endswith("| None") or python_type.endswith("|None")
    if is_nullable:
        base = re.sub(r"\s*\|\s*None$", "", python_type).strip()
    else:
        base = python_type.strip()

    # Generic types (list[...], dict[...]) — sanitize inner types recursively
    if "[" in python_type:
        bracket_start = python_type.index("[")
        outer = python_type[:bracket_start]
        inner = python_type[bracket_start + 1 : python_type.rindex("]")]
        sanitized_inner = _sanitize_python_type(inner, known_types)
        return f"{outer}[{sanitized_inner}]"

    # Known Python types are fine
    if base.lower() in {t.lower() for t in _KNOWN_PYTHON_TYPES}:
        return python_type

    # Types starting with OS are enum references — keep them
    if base.startswith("OS") or base.startswith("os"):
        return python_type

    # Re-exported public API types — keep them
    if base in known_types:
        return python_type

    # If the type name ends with a common enum suffix, treat as str
    # (enums from transitive deps that weren't downloaded/parsed).
    if base and base[0].isupper() and base.endswith(_ENUM_LIKE_SUFFIXES):
        return "str | None" if is_nullable else "str"

    # If it looks like a Dart class name (UpperCase), replace with dict
    if base and base[0].isupper() and base.isidentifier():
        return "dict | None" if is_nullable else "dict | None"

    return python_type


def _default_for_type(python_type: str) -> str:
    """Return a sensible default value string for a Python type."""
    if python_type == "str":
        return '""'
    if python_type == "bool":
        return "False"
    if python_type == "int":
        return "0"
    if python_type == "float":
        return "0.0"
    if "None" in python_type:
        return "None"
    if python_type.startswith("list"):
        return "field(default_factory=list)"
    if python_type.startswith("dict"):
        return "field(default_factory=dict)"
    return "None"
