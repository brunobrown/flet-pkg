"""
Data models for Dart API parsing and code generation planning.

This module defines two layers of models:
- **Dart API models** (DartParam, DartMethod, etc.): Represent the parsed Dart source code.
- **Generation plan models** (ParamPlan, MethodPlan, etc.):
  Represent the Python/Dart code to generate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Dart API Models (output of parser)
# ---------------------------------------------------------------------------


@dataclass
class DartParam:
    """A parameter from a Dart method signature."""

    name: str
    dart_type: str = "dynamic"
    required: bool = False
    named: bool = False
    default: str | None = None


@dataclass
class DartMethod:
    """A method from a Dart class."""

    name: str
    return_type: str = "void"
    params: list[DartParam] = field(default_factory=list)
    docstring: str = ""
    is_static: bool = False
    is_getter: bool = False
    is_setter: bool = False
    is_async: bool = False


@dataclass
class DartEnum:
    """A Dart enum declaration."""

    name: str
    values: list[str] = field(default_factory=list)
    docstring: str = ""


@dataclass
class DartClass:
    """A parsed Dart class with its methods, properties, and metadata."""

    name: str
    methods: list[DartMethod] = field(default_factory=list)
    docstring: str = ""
    parent_class: str = ""
    source_file: str = ""


@dataclass
class DartPackageAPI:
    """Container for the entire parsed Dart package API."""

    classes: list[DartClass] = field(default_factory=list)
    enums: list[DartEnum] = field(default_factory=list)
    helper_classes: list[DartClass] = field(default_factory=list)
    typedefs: dict[str, str] = field(default_factory=dict)
    reexported_types: dict[str, str] = field(default_factory=dict)
    """Mapping of type name → source package for re-exported public API types."""


# ---------------------------------------------------------------------------
# Generation Plan Models (output of analyzer, input to generators)
# ---------------------------------------------------------------------------


@dataclass
class ParamPlan:
    """Plan for a single method parameter."""

    python_name: str
    python_type: str = "Any"
    dart_name: str = ""
    dart_type: str = "dynamic"
    is_optional: bool = False
    default: str | None = None

    def __post_init__(self):
        if not self.dart_name:
            self.dart_name = self.python_name


@dataclass
class MethodPlan:
    """Plan for generating a single Python async method."""

    python_name: str
    dart_method_name: str = ""
    params: list[ParamPlan] = field(default_factory=list)
    return_type: str = "None"
    docstring: str = ""
    is_async: bool = True
    dart_original_name: str = ""
    dart_class_name: str = ""

    def __post_init__(self):
        if not self.dart_method_name:
            self.dart_method_name = self.python_name
        if not self.dart_original_name:
            self.dart_original_name = self.python_name


@dataclass
class PropertyPlan:
    """Plan for a control property (dataclass field)."""

    python_name: str
    python_type: str = "str"
    default_value: str = '""'
    docstring: str = ""
    dart_pre_init_call: str = ""
    """Optional Dart code template for pre-init setter call.

    Use ``{var}`` placeholder for the variable name.
    Example: ``"OneSignal.Debug.setLogLevel(OSLogLevel.values[{var}]);"``
    """


@dataclass
class EventPlan:
    """Plan for an event handler attribute."""

    python_attr_name: str
    event_class_name: str
    dart_event_name: str = ""
    fields: list[tuple[str, str]] = field(default_factory=list)
    dart_listener_method: str = ""
    dart_sdk_accessor: str = ""

    def __post_init__(self):
        if not self.dart_event_name:
            self.dart_event_name = self.python_attr_name.removeprefix("on_")


@dataclass
class EnumPlan:
    """Plan for generating a Python Enum class."""

    python_name: str
    values: list[tuple[str, str]] = field(default_factory=list)
    docstring: str = ""


@dataclass
class SubModulePlan:
    """Plan for a sub-module file (e.g., user.py, notifications.py)."""

    module_name: str
    class_name: str
    dart_prefix: str = ""
    methods: list[MethodPlan] = field(default_factory=list)
    docstring: str = ""
    dart_class_name: str = ""
    dart_sdk_accessor: str = ""


@dataclass
class GenerationPlan:
    """Complete plan for code generation. Fed to generators."""

    control_name: str
    package_name: str
    base_class: str = "ft.Service"
    description: str = ""
    flutter_package: str = ""
    properties: list[PropertyPlan] = field(default_factory=list)
    main_methods: list[MethodPlan] = field(default_factory=list)
    events: list[EventPlan] = field(default_factory=list)
    sub_modules: list[SubModulePlan] = field(default_factory=list)
    enums: list[EnumPlan] = field(default_factory=list)
    dart_import: str = ""
    dart_listeners: list[dict[str, str]] = field(default_factory=list)
    dart_main_class: str = ""
    control_name_snake: str = ""
    error_event_class: str = ""
    """Name of the error event class (e.g. ``OSErrorEvent``)."""
