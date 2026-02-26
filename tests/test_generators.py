import pytest

from flet_pkg.core.generators import (
    DartServiceGenerator,
    PythonControlGenerator,
    PythonInitGenerator,
    PythonSubModuleGenerator,
    PythonTypesGenerator,
)
from flet_pkg.core.models import (
    EnumPlan,
    EventPlan,
    GenerationPlan,
    MethodPlan,
    ParamPlan,
    PropertyPlan,
    SubModulePlan,
)


@pytest.fixture
def sample_plan():
    """A full GenerationPlan for testing generators."""
    return GenerationPlan(
        control_name="OneSignal",
        package_name="flet_onesignal",
        base_class="ft.Service",
        description="OneSignal integration for Flet.",
        flutter_package="onesignal_flutter",
        dart_import="package:onesignal_flutter/onesignal_flutter.dart",
        properties=[
            PropertyPlan(
                python_name="app_id", python_type="str", default_value='""', docstring="App ID."
            ),
        ],
        main_methods=[
            MethodPlan(
                python_name="login",
                dart_method_name="login",
                params=[
                    ParamPlan(python_name="external_id", python_type="str", dart_name="external_id")
                ],
                return_type="None",
                is_async=True,
                docstring="Login with external ID.",
            ),
            MethodPlan(
                python_name="logout",
                dart_method_name="logout",
                return_type="None",
                is_async=True,
            ),
        ],
        events=[
            EventPlan(
                python_attr_name="on_click",
                event_class_name="OneSignalClickEvent",
                dart_event_name="click",
                fields=[("data", "dict")],
            ),
        ],
        sub_modules=[
            SubModulePlan(
                module_name="user",
                class_name="OneSignalUser",
                dart_prefix="user",
                methods=[
                    MethodPlan(
                        python_name="add_tag",
                        dart_method_name="user_add_tag",
                        params=[
                            ParamPlan(python_name="key", python_type="str", dart_name="key"),
                            ParamPlan(python_name="value", python_type="str", dart_name="value"),
                        ],
                        return_type="None",
                        is_async=True,
                    ),
                    MethodPlan(
                        python_name="get_tags",
                        dart_method_name="user_get_tags",
                        return_type="dict[str, str]",
                        is_async=True,
                    ),
                ],
                docstring="User management.",
            ),
        ],
        enums=[
            EnumPlan(
                python_name="OSLogLevel",
                values=[("NONE", "none"), ("DEBUG", "debug"), ("INFO", "info")],
                docstring="Log levels.",
            ),
        ],
        dart_listeners=[
            {"event_name": "click", "python_attr": "on_click"},
        ],
    )


class TestPythonControlGenerator:
    def test_generates_file(self, sample_plan):
        gen = PythonControlGenerator()
        files = gen.generate(sample_plan)
        assert "one_signal.py" in files

    def test_contains_class_definition(self, sample_plan):
        gen = PythonControlGenerator()
        files = gen.generate(sample_plan)
        content = files["one_signal.py"]
        assert '@ft.control("OneSignal")' in content
        assert "class OneSignal(ft.Service):" in content

    def test_contains_imports(self, sample_plan):
        gen = PythonControlGenerator()
        files = gen.generate(sample_plan)
        content = files["one_signal.py"]
        assert "import flet as ft" in content
        assert "from flet_onesignal.user import OneSignalUser" in content

    def test_contains_properties(self, sample_plan):
        gen = PythonControlGenerator()
        files = gen.generate(sample_plan)
        content = files["one_signal.py"]
        assert 'app_id: str = ""' in content

    def test_contains_events(self, sample_plan):
        gen = PythonControlGenerator()
        files = gen.generate(sample_plan)
        content = files["one_signal.py"]
        assert "on_click: Optional[ft.EventHandler[OneSignalClickEvent]]" in content

    def test_contains_methods(self, sample_plan):
        gen = PythonControlGenerator()
        files = gen.generate(sample_plan)
        content = files["one_signal.py"]
        assert "async def login(self, external_id: str)" in content
        assert "async def logout(self)" in content

    def test_contains_submodule_property(self, sample_plan):
        gen = PythonControlGenerator()
        files = gen.generate(sample_plan)
        content = files["one_signal.py"]
        assert "def user(self) -> OneSignalUser:" in content

    def test_contains_invoke_method(self, sample_plan):
        gen = PythonControlGenerator()
        files = gen.generate(sample_plan)
        content = files["one_signal.py"]
        assert "_invoke_method" in content


class TestPythonSubModuleGenerator:
    def test_generates_files(self, sample_plan):
        gen = PythonSubModuleGenerator()
        files = gen.generate(sample_plan)
        assert "user.py" in files

    def test_contains_class(self, sample_plan):
        gen = PythonSubModuleGenerator()
        files = gen.generate(sample_plan)
        content = files["user.py"]
        assert "class OneSignalUser:" in content

    def test_contains_methods(self, sample_plan):
        gen = PythonSubModuleGenerator()
        files = gen.generate(sample_plan)
        content = files["user.py"]
        assert "async def add_tag(self, key: str, value: str)" in content
        assert '"user_add_tag"' in content

    def test_contains_type_checking(self, sample_plan):
        gen = PythonSubModuleGenerator()
        files = gen.generate(sample_plan)
        content = files["user.py"]
        assert "TYPE_CHECKING" in content


class TestPythonTypesGenerator:
    def test_generates_types_file(self, sample_plan):
        gen = PythonTypesGenerator()
        files = gen.generate(sample_plan)
        assert "types.py" in files

    def test_contains_enum(self, sample_plan):
        gen = PythonTypesGenerator()
        files = gen.generate(sample_plan)
        content = files["types.py"]
        assert "class OSLogLevel(Enum):" in content
        assert 'NONE = "none"' in content

    def test_contains_event_class(self, sample_plan):
        gen = PythonTypesGenerator()
        files = gen.generate(sample_plan)
        content = files["types.py"]
        assert "class OneSignalClickEvent(ft.Event" in content

    def test_contains_error_event(self, sample_plan):
        gen = PythonTypesGenerator()
        files = gen.generate(sample_plan)
        content = files["types.py"]
        assert "class OneSignalErrorEvent(ft.Event" in content

    def test_empty_plan_still_generates_error_event(self):
        plan = GenerationPlan(control_name="X", package_name="x")
        gen = PythonTypesGenerator()
        files = gen.generate(plan)
        # types.py is always generated (error event class is always needed)
        assert "types.py" in files
        assert "XErrorEvent" in files["types.py"]


class TestPythonInitGenerator:
    def test_generates_init(self, sample_plan):
        gen = PythonInitGenerator()
        files = gen.generate(sample_plan)
        assert "__init__.py" in files

    def test_contains_main_import(self, sample_plan):
        gen = PythonInitGenerator()
        files = gen.generate(sample_plan)
        content = files["__init__.py"]
        assert "from flet_onesignal.one_signal import OneSignal" in content

    def test_contains_all(self, sample_plan):
        gen = PythonInitGenerator()
        files = gen.generate(sample_plan)
        content = files["__init__.py"]
        assert "__all__" in content
        assert '"OneSignal"' in content


class TestDartServiceGenerator:
    def test_generates_dart_file(self, sample_plan):
        gen = DartServiceGenerator()
        files = gen.generate(sample_plan)
        assert "one_signal_service.dart" in files

    def test_contains_class(self, sample_plan):
        gen = DartServiceGenerator()
        files = gen.generate(sample_plan)
        content = files["one_signal_service.dart"]
        assert "class OneSignalService extends FletService" in content

    def test_contains_switch(self, sample_plan):
        gen = DartServiceGenerator()
        files = gen.generate(sample_plan)
        content = files["one_signal_service.dart"]
        assert '"login"' in content
        assert '"logout"' in content
        assert '"user_add_tag"' in content

    def test_contains_error_handler(self, sample_plan):
        gen = DartServiceGenerator()
        files = gen.generate(sample_plan)
        content = files["one_signal_service.dart"]
        assert "_handleError" in content

    def test_contains_import(self, sample_plan):
        gen = DartServiceGenerator()
        files = gen.generate(sample_plan)
        content = files["one_signal_service.dart"]
        assert "package:onesignal_flutter/onesignal_flutter.dart" in content


class TestDartUIControlGenerator:
    """Tests for StatefulWidget generation for UI controls."""

    @pytest.fixture
    def ui_plan(self):
        return GenerationPlan(
            control_name="Rive",
            package_name="flet_rive",
            base_class="ft.LayoutControl",
            flutter_package="rive",
            dart_import="package:rive/rive.dart",
            dart_main_class="RiveAnimation",
            properties=[
                PropertyPlan(
                    python_name="fit",
                    python_type="ft.BoxFit | None",
                    default_value="None",
                    dart_getter='control.getBoxFit("fit")',
                ),
                PropertyPlan(
                    python_name="alignment",
                    python_type="ft.Alignment | None",
                    default_value="None",
                    dart_getter='control.getAlignment("alignment")',
                ),
                PropertyPlan(
                    python_name="antialiasing",
                    python_type="bool",
                    default_value="True",
                    dart_getter='control.getBool("antialiasing", false)!',
                ),
            ],
            events=[
                EventPlan(
                    python_attr_name="on_init",
                    event_class_name="RiveOnInitEvent",
                    dart_event_name="init",
                ),
            ],
        )

    def test_generates_widget_file(self, ui_plan):
        gen = DartServiceGenerator()
        files = gen.generate(ui_plan)
        assert "rive_widget.dart" in files

    def test_contains_stateful_widget(self, ui_plan):
        gen = DartServiceGenerator()
        files = gen.generate(ui_plan)
        content = files["rive_widget.dart"]
        assert "class RiveWidget extends StatefulWidget" in content

    def test_contains_state_class(self, ui_plan):
        gen = DartServiceGenerator()
        files = gen.generate(ui_plan)
        content = files["rive_widget.dart"]
        assert "class _RiveWidgetState extends State<RiveWidget>" in content

    def test_contains_layout_control(self, ui_plan):
        gen = DartServiceGenerator()
        files = gen.generate(ui_plan)
        content = files["rive_widget.dart"]
        assert "LayoutControl(" in content
        assert "control: widget.control," in content

    def test_contains_sdk_widget(self, ui_plan):
        gen = DartServiceGenerator()
        files = gen.generate(ui_plan)
        content = files["rive_widget.dart"]
        assert "RiveAnimation(" in content

    def test_contains_typed_getters(self, ui_plan):
        gen = DartServiceGenerator()
        files = gen.generate(ui_plan)
        content = files["rive_widget.dart"]
        assert "getBoxFit" in content
        assert "getAlignment" in content
        assert "getBool" in content

    def test_contains_error_handler(self, ui_plan):
        gen = DartServiceGenerator()
        files = gen.generate(ui_plan)
        content = files["rive_widget.dart"]
        assert "_handleError" in content
        assert 'triggerEvent("error"' in content

    def test_contains_flutter_widgets_import(self, ui_plan):
        gen = DartServiceGenerator()
        files = gen.generate(ui_plan)
        content = files["rive_widget.dart"]
        assert "package:flutter/widgets.dart" in content

    def test_no_flet_widget_base_class(self, ui_plan):
        gen = DartServiceGenerator()
        files = gen.generate(ui_plan)
        content = files["rive_widget.dart"]
        assert "FletWidget" not in content

    def test_dart_constructor_uses_camel_case_names(self):
        """Bug 2: Dart constructor args must use camelCase, not snake_case."""
        plan = GenerationPlan(
            control_name="WebView",
            package_name="flet_webview",
            base_class="ft.LayoutControl",
            flutter_package="webview_flutter",
            dart_import="package:webview_flutter/webview_flutter.dart",
            dart_main_class="WebView",
            properties=[
                PropertyPlan(
                    python_name="initial_url",
                    python_type="str | None",
                    default_value="None",
                    dart_name="initialUrl",
                ),
                PropertyPlan(
                    python_name="debugging_enabled",
                    python_type="bool",
                    default_value="False",
                    dart_name="debuggingEnabled",
                    dart_getter='widget.control.getBool("debugging_enabled", false)!',
                ),
            ],
        )
        gen = DartServiceGenerator()
        files = gen.generate(plan)
        content = files["web_view_widget.dart"]
        # Constructor args must use camelCase Dart names
        assert "initialUrl: initialUrl," in content
        assert "debuggingEnabled: debuggingEnabled," in content
        # Must NOT use snake_case
        assert "initial_url:" not in content
        assert "debugging_enabled:" not in content


class TestPythonControlFieldImport:
    """Tests for field(default_factory) import in python_control.py."""

    def test_field_import_for_list_property(self):
        plan = GenerationPlan(
            control_name="MyWidget",
            package_name="flet_my_widget",
            base_class="ft.LayoutControl",
            properties=[
                PropertyPlan(
                    python_name="items",
                    python_type="list[str]",
                    default_value="field(default_factory=list)",
                ),
            ],
        )
        gen = PythonControlGenerator()
        files = gen.generate(plan)
        content = files["my_widget.py"]
        assert "from dataclasses import field" in content

    def test_no_field_import_without_list_or_submodules(self):
        plan = GenerationPlan(
            control_name="MyWidget",
            package_name="flet_my_widget",
            base_class="ft.LayoutControl",
            properties=[
                PropertyPlan(python_name="name", python_type="str", default_value='""'),
            ],
        )
        gen = PythonControlGenerator()
        files = gen.generate(plan)
        content = files["my_widget.py"]
        assert "from dataclasses import field" not in content
