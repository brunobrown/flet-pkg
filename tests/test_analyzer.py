import pytest

from flet_pkg.core.analyzer import PackageAnalyzer
from flet_pkg.core.models import (
    DartClass,
    DartEnum,
    DartMethod,
    DartPackageAPI,
    DartParam,
)


@pytest.fixture
def analyzer():
    return PackageAnalyzer()


@pytest.fixture
def sample_api():
    """A realistic DartPackageAPI mirroring a OneSignal-like structure."""
    return DartPackageAPI(
        classes=[
            DartClass(
                name="OneSignal",
                methods=[
                    DartMethod(
                        name="login",
                        return_type="Future<void>",
                        params=[DartParam(name="externalId", dart_type="String", required=True)],
                        is_async=True,
                    ),
                    DartMethod(name="logout", return_type="Future<void>", is_async=True),
                ],
                source_file="src/onesignal.dart",
            ),
            DartClass(
                name="OneSignalUser",
                methods=[
                    DartMethod(
                        name="getOnesignalId",
                        return_type="Future<String?>",
                        is_async=True,
                    ),
                    DartMethod(
                        name="addTagWithKey",
                        return_type="Future<void>",
                        params=[
                            DartParam(name="key", dart_type="String", required=True),
                            DartParam(name="value", dart_type="String", required=True),
                        ],
                        is_async=True,
                    ),
                    DartMethod(
                        name="removeTag",
                        return_type="Future<void>",
                        params=[DartParam(name="key", dart_type="String", required=True)],
                        is_async=True,
                    ),
                ],
                source_file="src/user.dart",
            ),
            DartClass(
                name="OneSignalNotifications",
                methods=[
                    DartMethod(
                        name="requestPermission",
                        return_type="Future<bool>",
                        params=[
                            DartParam(name="fallbackToSettings", dart_type="bool", required=True)
                        ],
                        is_async=True,
                    ),
                    DartMethod(name="clearAll", return_type="Future<void>", is_async=True),
                    DartMethod(
                        name="addClickListener",
                        return_type="void",
                        params=[DartParam(name="callback", dart_type="Function")],
                    ),
                ],
                source_file="src/notifications.dart",
            ),
        ],
        enums=[
            DartEnum(
                name="OSLogLevel",
                values=["none", "fatal", "error", "warn", "info", "debug", "verbose"],
            ),
        ],
    )


class TestNamespaceDetection:
    def test_prefix_detection(self, analyzer, sample_api):
        plan = analyzer.analyze(
            sample_api, "OneSignal", "service", "onesignal_flutter", "flet_onesignal"
        )

        ns_names = [s.module_name for s in plan.sub_modules]
        assert "user" in ns_names
        assert "notifications" in ns_names

    def test_main_class_not_namespace(self, analyzer, sample_api):
        plan = analyzer.analyze(
            sample_api, "OneSignal", "service", "onesignal_flutter", "flet_onesignal"
        )

        ns_names = [s.module_name for s in plan.sub_modules]
        # "OneSignal" itself should NOT become a namespace
        assert "onesignal" not in [n.lower() for n in ns_names]

    def test_main_methods_from_main_class(self, analyzer, sample_api):
        plan = analyzer.analyze(
            sample_api, "OneSignal", "service", "onesignal_flutter", "flet_onesignal"
        )

        main_names = [m.python_name for m in plan.main_methods]
        assert "login" in main_names
        assert "logout" in main_names


class TestEventDetection:
    def test_detects_click_listener(self, analyzer, sample_api):
        plan = analyzer.analyze(
            sample_api, "OneSignal", "service", "onesignal_flutter", "flet_onesignal"
        )

        event_names = [e.python_attr_name for e in plan.events]
        # Event from OneSignalNotifications gets namespace prefix "notification"
        assert "on_notification_click" in event_names

    def test_event_excludes_from_methods(self, analyzer, sample_api):
        plan = analyzer.analyze(
            sample_api, "OneSignal", "service", "onesignal_flutter", "flet_onesignal"
        )

        # Listener methods should NOT appear as regular methods in sub-modules
        for sub in plan.sub_modules:
            method_names = [m.python_name for m in sub.methods]
            assert "add_click_listener" not in method_names


class TestSubModuleMethods:
    def test_user_methods(self, analyzer, sample_api):
        plan = analyzer.analyze(
            sample_api, "OneSignal", "service", "onesignal_flutter", "flet_onesignal"
        )

        user_sub = next(s for s in plan.sub_modules if s.module_name == "user")
        method_names = [m.python_name for m in user_sub.methods]
        assert "get_onesignal_id" in method_names
        assert "add_tag_with_key" in method_names
        assert "remove_tag" in method_names

    def test_dart_prefix(self, analyzer, sample_api):
        plan = analyzer.analyze(
            sample_api, "OneSignal", "service", "onesignal_flutter", "flet_onesignal"
        )

        user_sub = next(s for s in plan.sub_modules if s.module_name == "user")
        login_method = next(m for m in user_sub.methods if m.python_name == "get_onesignal_id")
        assert login_method.dart_method_name == "user_get_onesignal_id"


class TestEnumDetection:
    def test_enums_extracted(self, analyzer, sample_api):
        plan = analyzer.analyze(
            sample_api, "OneSignal", "service", "onesignal_flutter", "flet_onesignal"
        )

        assert len(plan.enums) == 1
        assert plan.enums[0].python_name == "OSLogLevel"
        assert len(plan.enums[0].values) == 7


class TestBaseClass:
    def test_service_type(self, analyzer, sample_api):
        plan = analyzer.analyze(
            sample_api, "OneSignal", "service", "onesignal_flutter", "flet_onesignal"
        )
        assert plan.base_class == "ft.Service"

    def test_ui_control_type(self, analyzer, sample_api):
        plan = analyzer.analyze(
            sample_api, "OneSignal", "ui_control", "onesignal_flutter", "flet_onesignal"
        )
        assert plan.base_class == "ft.LayoutControl"


class TestFallback:
    def test_empty_api(self, analyzer):
        api = DartPackageAPI()
        plan = analyzer.analyze(api, "Empty", "service", "empty_flutter", "flet_empty")
        assert plan.main_methods == []
        assert plan.sub_modules == []
        assert plan.events == []

    def test_single_method_class_no_submodule(self, analyzer):
        """Classes with < 2 methods don't become sub-modules."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyMain",
                    methods=[DartMethod(name="doThing", return_type="void")],
                ),
                DartClass(
                    name="MyMainHelper",
                    methods=[DartMethod(name="help", return_type="void")],
                ),
            ]
        )
        plan = analyzer.analyze(api, "MyMain", "service", "my_main_flutter", "flet_my_main")
        # Helper has only 1 method, should NOT become a sub-module
        assert len(plan.sub_modules) == 0
        # But its methods should be merged into main_methods
        main_names = [m.python_name for m in plan.main_methods]
        assert "do_thing" in main_names
        assert "help" in main_names
