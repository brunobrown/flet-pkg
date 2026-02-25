from flet_pkg.core.models import (
    DartClass,
    DartEnum,
    DartMethod,
    DartPackageAPI,
    DartParam,
    EventPlan,
    GenerationPlan,
    MethodPlan,
    ParamPlan,
)


class TestDartParam:
    def test_defaults(self):
        p = DartParam(name="foo")
        assert p.name == "foo"
        assert p.dart_type == "dynamic"
        assert p.required is False
        assert p.named is False
        assert p.default is None

    def test_full(self):
        p = DartParam(name="bar", dart_type="String", required=True, named=True, default='"hello"')
        assert p.dart_type == "String"
        assert p.required is True
        assert p.default == '"hello"'


class TestDartMethod:
    def test_defaults(self):
        m = DartMethod(name="doSomething")
        assert m.return_type == "void"
        assert m.params == []
        assert m.is_async is False

    def test_with_params(self):
        m = DartMethod(
            name="login",
            return_type="Future<void>",
            params=[DartParam(name="id", dart_type="String", required=True)],
            is_async=True,
        )
        assert m.is_async is True
        assert len(m.params) == 1


class TestDartEnum:
    def test_basic(self):
        e = DartEnum(name="LogLevel", values=["debug", "info", "error"])
        assert len(e.values) == 3
        assert e.name == "LogLevel"


class TestDartClass:
    def test_basic(self):
        cls = DartClass(
            name="MyService",
            methods=[DartMethod(name="start")],
            source_file="src/my_service.dart",
        )
        assert cls.name == "MyService"
        assert len(cls.methods) == 1
        assert cls.source_file == "src/my_service.dart"


class TestDartPackageAPI:
    def test_empty(self):
        api = DartPackageAPI()
        assert api.classes == []
        assert api.enums == []

    def test_with_data(self):
        api = DartPackageAPI(
            classes=[DartClass(name="Foo")],
            enums=[DartEnum(name="Bar", values=["a", "b"])],
        )
        assert len(api.classes) == 1
        assert len(api.enums) == 1


class TestParamPlan:
    def test_auto_dart_name(self):
        p = ParamPlan(python_name="user_id")
        assert p.dart_name == "user_id"

    def test_explicit_dart_name(self):
        p = ParamPlan(python_name="user_id", dart_name="userId")
        assert p.dart_name == "userId"


class TestMethodPlan:
    def test_auto_dart_method_name(self):
        m = MethodPlan(python_name="do_thing")
        assert m.dart_method_name == "do_thing"


class TestEventPlan:
    def test_auto_dart_event_name(self):
        e = EventPlan(python_attr_name="on_click", event_class_name="ClickEvent")
        assert e.dart_event_name == "click"


class TestGenerationPlan:
    def test_defaults(self):
        plan = GenerationPlan(control_name="MyControl", package_name="my_pkg")
        assert plan.base_class == "ft.Service"
        assert plan.properties == []
        assert plan.main_methods == []
        assert plan.events == []
        assert plan.sub_modules == []
        assert plan.enums == []
