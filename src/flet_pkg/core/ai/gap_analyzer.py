"""Deterministic coverage gap analyzer.

Compares ``DartPackageAPI`` (source) against ``GenerationPlan`` (output)
to identify exactly what the pipeline missed and why. Produces a structured
``GapReport`` — no LLM required.
"""

import re

from flet_pkg.core.ai.models import GapItem, GapKind, GapReport
from flet_pkg.core.models import DartPackageAPI, GenerationPlan
from flet_pkg.core.parser import camel_to_snake
from flet_pkg.core.type_map import map_dart_type, map_dart_type_flet

# Internal Dart methods excluded from gap counting.
_INTERNAL_METHOD_NAMES = frozenset(
    {
        "setMockInitialValues",
        "setMockMethodCallHandler",
        "hashCode",
        "getHashCode",
        "runtimeType",
        "toString",
        "noSuchMethod",
        "toJson",
        "fromJson",
        "toMap",
        "fromMap",
        "copyWith",
        "compareTo",
        "toJsonString",
        "fromJsonFunction",
        "getFromJsonFunction",
        "removeDuplicates",
        "addIfNotNull",
        "compute",
        "identical",
        "jsonRepresentation",
        "convertToJsonString",
        "jsonEncode",
    }
)

# Framework constructor params that are never mapped.
_FRAMEWORK_PARAMS = frozenset({"key", "child", "children"})

# Dart types that cannot be serialized to Flet properties.
_NON_SERIALIZABLE_TYPES = frozenset(
    {
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
        "AnimationController",
        "ScrollController",
        "TextEditingController",
        "MouseCursor",
        "SystemMouseCursors",
        "HitTestBehavior",
    }
)

# Callback types that become events (not gaps).
_CALLBACK_TYPES = frozenset(
    {
        "VoidCallback",
        "GestureTapCallback",
        "GestureLongPressCallback",
    }
)
_CALLBACK_PREFIXES = (
    "ValueChanged",
    "ValueSetter",
    "ValueGetter",
    "IndexedWidgetBuilder",
    "WidgetBuilder",
    "NullableIndexedWidgetBuilder",
)

# Regex for add/remove listener/observer/handler patterns.
_LISTENER_RE = re.compile(r"^(add|remove)(.*?)(Listener|Observer|Handler|Subscription)s?$")

# Methods that map to constructor properties (SDK init flow).
_INIT_METHOD_NAMES = frozenset({"initialize", "init", "setup", "configure"})


def _is_listener_method(name: str) -> bool:
    """Return True if *name* is an add/remove listener/observer/handler."""
    return _LISTENER_RE.match(name) is not None


class GapAnalyzer:
    """Deterministic gap analysis between Dart source and generated plan."""

    def analyze(
        self,
        api: DartPackageAPI,
        plan: GenerationPlan,
        extension_type: str,
    ) -> GapReport:
        """Analyze gaps between Dart API surface and generated plan.

        Args:
            api: Parsed Dart package API.
            plan: Generated plan to compare against.
            extension_type: Either ``"service"`` or ``"ui_control"``.

        Returns:
            A ``GapReport`` with coverage stats and missing items.
        """
        if extension_type == "service":
            return self._analyze_service_gaps(api, plan)
        return self._analyze_ui_control_gaps(api, plan)

    def _analyze_service_gaps(
        self,
        api: DartPackageAPI,
        plan: GenerationPlan,
    ) -> GapReport:
        """Analyze gaps for a service (non-visual) package."""
        report = GapReport(
            flutter_package=plan.flutter_package,
            extension_type="service",
        )

        # Per-category counters: [dart_api, generated]
        cat: dict[str, list[int]] = {
            "Methods": [0, 0],
            "Events": [0, 0],
            "Enums": [0, 0],
        }

        # Collect all generated method names (main + sub-modules)
        generated_methods: set[str] = set()
        for m in plan.main_methods:
            generated_methods.add(m.python_name)
        for sub in plan.sub_modules:
            for m in sub.methods:
                generated_methods.add(m.python_name)

        # Collect generated event names
        generated_events: set[str] = set()
        for e in plan.events:
            generated_events.add(e.python_attr_name)

        # Collect generated enum names
        generated_enums: set[str] = set()
        for e in plan.enums:
            generated_enums.add(e.python_name)

        # Collect generated property names
        generated_props: set[str] = set()
        for p in plan.properties:
            generated_props.add(p.python_name)

        # Analyze class methods
        for cls in api.classes:
            for method in cls.methods:
                if method.name in _INTERNAL_METHOD_NAMES:
                    continue

                # Stream getters → events
                if method.is_getter and method.return_type.startswith("Stream"):
                    report.total_dart_api += 1
                    cat["Events"][0] += 1
                    event_name = f"on_{camel_to_snake(method.name)}"
                    if not any(
                        e.python_attr_name == event_name
                        or e.python_attr_name
                        == f"on_{camel_to_snake(method.name).removeprefix('on_')}"
                        for e in plan.events
                    ):
                        report.gaps.append(
                            GapItem(
                                kind=GapKind.MISSING_EVENT,
                                dart_name=method.name,
                                dart_type=method.return_type,
                                dart_class=cls.name,
                                reason="Stream getter not mapped to event handler",
                            )
                        )
                    else:
                        report.total_generated += 1
                        cat["Events"][1] += 1
                    continue

                # add/remove Listener/Observer/Handler → covered by events
                if _is_listener_method(method.name) and generated_events:
                    report.total_dart_api += 1
                    cat["Events"][0] += 1
                    report.total_generated += 1
                    cat["Events"][1] += 1
                    continue

                # Bare getters/setters mapped as properties
                python_name = camel_to_snake(method.name)
                if (method.is_getter or method.is_setter) and python_name in generated_props:
                    report.total_dart_api += 1
                    cat["Methods"][0] += 1
                    report.total_generated += 1
                    cat["Methods"][1] += 1
                    continue

                # Init/setup methods covered by constructor properties
                if method.name in _INIT_METHOD_NAMES and generated_props:
                    report.total_dart_api += 1
                    cat["Methods"][0] += 1
                    report.total_generated += 1
                    cat["Methods"][1] += 1
                    continue

                # Regular methods
                report.total_dart_api += 1
                cat["Methods"][0] += 1
                if python_name in generated_methods:
                    report.total_generated += 1
                    cat["Methods"][1] += 1
                else:
                    report.gaps.append(
                        GapItem(
                            kind=GapKind.MISSING_METHOD,
                            dart_name=method.name,
                            dart_type=method.return_type,
                            dart_class=cls.name,
                            reason="Method not mapped to Python async method",
                            feasible=self._is_method_feasible(method.return_type),
                        )
                    )

        # Top-level functions
        for func in api.top_level_functions:
            report.total_dart_api += 1
            cat["Methods"][0] += 1
            python_name = camel_to_snake(func.name)
            if python_name in generated_methods:
                report.total_generated += 1
                cat["Methods"][1] += 1
            else:
                report.gaps.append(
                    GapItem(
                        kind=GapKind.MISSING_METHOD,
                        dart_name=func.name,
                        dart_type=func.return_type,
                        reason="Top-level function not mapped",
                        feasible=self._is_method_feasible(func.return_type),
                    )
                )

        # Enum gaps
        for dart_enum in api.enums:
            report.total_dart_api += 1
            cat["Enums"][0] += 1
            if dart_enum.name in generated_enums or any(
                e.python_name == dart_enum.name for e in plan.enums
            ):
                report.total_generated += 1
                cat["Enums"][1] += 1
            else:
                report.gaps.append(
                    GapItem(
                        kind=GapKind.MISSING_ENUM,
                        dart_name=dart_enum.name,
                        reason="Dart enum not mapped to Python Enum",
                    )
                )

        # Coverage
        if report.total_dart_api > 0:
            report.coverage_pct = report.total_generated / report.total_dart_api * 100

        # Store per-category counts (only non-empty categories)
        report.category_counts = {k: (v[0], v[1]) for k, v in cat.items() if v[0] > 0}

        return report

    def _analyze_ui_control_gaps(
        self,
        api: DartPackageAPI,
        plan: GenerationPlan,
    ) -> GapReport:
        """Analyze gaps for a UI control (visual widget) package."""
        report = GapReport(
            flutter_package=plan.flutter_package,
            extension_type="ui_control",
        )

        # Per-category counters: [dart_api, generated]
        cat: dict[str, list[int]] = {
            "Properties": [0, 0],
            "Events": [0, 0],
            "Enums": [0, 0],
        }

        # Find the main widget class
        widget_classes = [c for c in api.classes if c.constructor_params]
        main_widget = next(
            (c for c in widget_classes if c.name == plan.dart_main_class),
            widget_classes[0] if widget_classes else None,
        )

        if not main_widget:
            return report

        # Collect generated property/event names
        generated_props: set[str] = {p.python_name for p in plan.properties}
        generated_events: set[str] = {e.python_attr_name for e in plan.events}
        generated_enums: set[str] = {e.python_name for e in plan.enums}

        # Sub-control property names
        sub_control_props: set[str] = set()
        for sc in plan.sub_controls:
            sub_control_props.add(camel_to_snake(sc.dart_class_name))
            for p in sc.properties:
                sub_control_props.add(p.python_name)

        # Analyze constructor params
        for param in main_widget.constructor_params:
            if param.name in _FRAMEWORK_PARAMS:
                continue

            report.total_dart_api += 1
            python_name = camel_to_snake(param.name)

            # Check if mapped as property, event, or sub-control
            is_callback = self._is_callback_type(param.dart_type)

            if is_callback:
                cat["Events"][0] += 1
                event_name = f"on_{python_name.removeprefix('on_')}"
                if event_name in generated_events or python_name in generated_events:
                    report.total_generated += 1
                    cat["Events"][1] += 1
                else:
                    report.gaps.append(
                        GapItem(
                            kind=GapKind.MISSING_EVENT,
                            dart_name=param.name,
                            dart_type=param.dart_type,
                            dart_class=main_widget.name,
                            reason="Callback param not mapped to event handler",
                        )
                    )
            elif python_name in generated_props or python_name in sub_control_props:
                cat["Properties"][0] += 1
                report.total_generated += 1
                cat["Properties"][1] += 1
            else:
                cat["Properties"][0] += 1
                feasible = self._is_property_feasible(param.dart_type)
                report.gaps.append(
                    GapItem(
                        kind=GapKind.MISSING_PROPERTY,
                        dart_name=param.name,
                        dart_type=param.dart_type,
                        dart_class=main_widget.name,
                        reason=self._property_skip_reason(param.dart_type),
                        feasible=feasible,
                    )
                )

        # Enum gaps
        for dart_enum in api.enums:
            report.total_dart_api += 1
            cat["Enums"][0] += 1
            if dart_enum.name in generated_enums or any(
                e.python_name == dart_enum.name for e in plan.enums
            ):
                report.total_generated += 1
                cat["Enums"][1] += 1
            else:
                report.gaps.append(
                    GapItem(
                        kind=GapKind.MISSING_ENUM,
                        dart_name=dart_enum.name,
                        reason="Dart enum not mapped to Python Enum",
                    )
                )

        # Coverage
        if report.total_dart_api > 0:
            report.coverage_pct = report.total_generated / report.total_dart_api * 100

        # Store per-category counts (only non-empty categories)
        report.category_counts = {k: (v[0], v[1]) for k, v in cat.items() if v[0] > 0}

        return report

    # ------------------------------------------------------------------
    # Feasibility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_method_feasible(return_type: str) -> bool:
        """Check if a method with this return type is feasibly mappable."""
        base = return_type.replace("?", "").strip()
        if base.startswith("Future<"):
            base = base[7:-1].strip()
        if base.startswith("Stream<"):
            return True
        mapped = map_dart_type(base)
        return mapped != base or base in ("void", "dynamic")

    @staticmethod
    def _is_callback_type(dart_type: str) -> bool:
        """Check if a Dart type is a callback/function type."""
        base = dart_type.replace("?", "").strip()
        if base in _CALLBACK_TYPES:
            return True
        if any(base.startswith(prefix) for prefix in _CALLBACK_PREFIXES):
            return True
        if "Function" in base or "Callback" in base:
            return True
        return False

    @staticmethod
    def _is_property_feasible(dart_type: str) -> bool:
        """Check if a Dart type can feasibly become a Flet property."""
        base = dart_type.replace("?", "").strip()
        if base in _NON_SERIALIZABLE_TYPES:
            return False
        mapped = map_dart_type_flet(base)
        return mapped is not None

    @staticmethod
    def _property_skip_reason(dart_type: str) -> str:
        """Return human-readable reason why a property was skipped."""
        base = dart_type.replace("?", "").strip()
        if base in _NON_SERIALIZABLE_TYPES:
            return f"Non-serializable type: {base}"
        mapped = map_dart_type_flet(base)
        if mapped is None:
            return f"Type skipped by Flet mapping: {base}"
        return f"Unknown type mapping: {base}"
