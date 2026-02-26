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


class TestWidgetSelection:
    """Tests for _select_main_widget filtering."""

    def test_filters_private_classes(self, analyzer):
        """Private Dart classes (starting with _) should be filtered."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="_InternalRenderer",
                    constructor_params=[DartParam(name="size", dart_type="double")],
                ),
                DartClass(
                    name="Rive",
                    constructor_params=[
                        DartParam(name="fit", dart_type="BoxFit"),
                        DartParam(name="alignment", dart_type="Alignment"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "Rive", "ui_control", "rive", "flet_rive")
        assert plan.dart_main_class == "Rive"

    def test_filters_internal_suffix_classes(self, analyzer):
        """Classes with internal suffixes (SharedTexture, Renderer, etc.) should be filtered."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="RiveSharedTexture",
                    constructor_params=[
                        DartParam(name="x", dart_type="int"),
                        DartParam(name="y", dart_type="int"),
                        DartParam(name="w", dart_type="int"),
                    ],
                ),
                DartClass(
                    name="RiveRenderer",
                    constructor_params=[DartParam(name="path", dart_type="String")],
                ),
                DartClass(
                    name="RiveAnimation",
                    constructor_params=[
                        DartParam(name="fit", dart_type="BoxFit"),
                        DartParam(name="alignment", dart_type="Alignment"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "Rive", "ui_control", "rive", "flet_rive")
        # Should pick RiveAnimation, not RiveSharedTexture (most params but internal)
        assert plan.dart_main_class == "RiveAnimation"

    def test_fallback_when_all_filtered(self, analyzer):
        """If all classes are internal, fall back to unfiltered selection."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="AlphaRenderer",
                    constructor_params=[DartParam(name="a", dart_type="int")],
                ),
                DartClass(
                    name="BetaController",
                    constructor_params=[
                        DartParam(name="b", dart_type="int"),
                        DartParam(name="c", dart_type="int"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "Gamma", "ui_control", "gamma_pkg", "flet_gamma")
        # Should fallback to BetaController (most params in unfiltered list)
        assert plan.dart_main_class == "BetaController"


class TestFletTypeMapping:
    """Tests for Flet-aware type mapping in ui_control analysis."""

    def test_alignment_becomes_ft_alignment(self, analyzer):
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyWidget",
                    constructor_params=[
                        DartParam(name="alignment", dart_type="Alignment"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "MyWidget", "ui_control", "my_widget", "flet_my_widget")
        prop = next(p for p in plan.properties if p.python_name == "alignment")
        assert prop.python_type == "ft.Alignment | None"
        assert "getAlignment" in prop.dart_getter

    def test_box_fit_becomes_ft_box_fit(self, analyzer):
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyWidget",
                    constructor_params=[
                        DartParam(name="fit", dart_type="BoxFit"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "MyWidget", "ui_control", "my_widget", "flet_my_widget")
        prop = next(p for p in plan.properties if p.python_name == "fit")
        assert prop.python_type == "ft.BoxFit | None"
        assert "getBoxFit" in prop.dart_getter

    def test_key_is_skipped(self, analyzer):
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyWidget",
                    constructor_params=[
                        DartParam(name="key", dart_type="Key?"),
                        DartParam(name="name", dart_type="String"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "MyWidget", "ui_control", "my_widget", "flet_my_widget")
        prop_names = [p.python_name for p in plan.properties]
        assert "key" not in prop_names
        assert "name" in prop_names

    def test_list_gets_default_factory(self, analyzer):
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyWidget",
                    constructor_params=[
                        DartParam(name="items", dart_type="List<String>"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "MyWidget", "ui_control", "my_widget", "flet_my_widget")
        prop = next(p for p in plan.properties if p.python_name == "items")
        assert prop.python_type == "list[str]"
        assert prop.default_value == "field(default_factory=list)"

    def test_service_type_uses_standard_mapping(self, analyzer):
        """Service extensions should still use standard map_dart_type, not Flet types."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyService",
                    constructor_params=[
                        DartParam(name="alignment", dart_type="Alignment"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "MyService", "service", "my_service", "flet_my_service")
        # In service mode, Alignment should map to "str" (standard mapping)
        if plan.properties:
            prop = next((p for p in plan.properties if p.python_name == "alignment"), None)
            if prop:
                assert prop.python_type == "str | None"


class TestControllerTypeFiltering:
    """Tests that Controller/Painter types are filtered from widget properties."""

    def test_controller_type_filtered(self, analyzer):
        """AnimationController params should not become properties."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="RiveWidget",
                    constructor_params=[
                        DartParam(name="fit", dart_type="BoxFit"),
                        DartParam(name="controller", dart_type="AnimationController"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "Rive", "ui_control", "rive", "flet_rive")
        prop_names = [p.python_name for p in plan.properties]
        assert "fit" in prop_names
        assert "controller" not in prop_names

    def test_generic_controller_substring_filtered(self, analyzer):
        """Any type containing 'Controller' should be filtered."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyWidget",
                    constructor_params=[
                        DartParam(name="name", dart_type="String"),
                        DartParam(name="scroll", dart_type="ScrollController"),
                        DartParam(name="riveCtrl", dart_type="RiveAnimationController"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "MyWidget", "ui_control", "my_pkg", "flet_my")
        prop_names = [p.python_name for p in plan.properties]
        assert "name" in prop_names
        assert "scroll" not in prop_names
        assert "rive_ctrl" not in prop_names

    def test_painter_type_filtered(self, analyzer):
        """Types ending in 'Painter' should be filtered."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyWidget",
                    constructor_params=[
                        DartParam(name="enabled", dart_type="bool"),
                        DartParam(name="painter", dart_type="CustomPainter"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "MyWidget", "ui_control", "my_pkg", "flet_my")
        prop_names = [p.python_name for p in plan.properties]
        assert "enabled" in prop_names
        assert "painter" not in prop_names


class TestRiveLikeWidgetParsing:
    """End-to-end test: a rive-like package with FooWidget as main class."""

    def test_selects_rive_widget_not_panel(self, analyzer):
        """RiveWidget should be selected as main widget, not RivePanel."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="RiveWidget",
                    constructor_params=[
                        DartParam(name="fit", dart_type="BoxFit"),
                        DartParam(name="alignment", dart_type="Alignment"),
                        DartParam(name="useSharedTexture", dart_type="bool"),
                        DartParam(name="layoutScaleFactor", dart_type="double"),
                        DartParam(name="controller", dart_type="AnimationController"),
                    ],
                ),
                DartClass(
                    name="RivePanel",
                    constructor_params=[
                        DartParam(name="backgroundColor", dart_type="Color"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "Rive", "ui_control", "rive", "flet_rive")
        assert plan.dart_main_class == "RiveWidget"
        prop_names = [p.python_name for p in plan.properties]
        assert "fit" in prop_names
        assert "alignment" in prop_names
        assert "use_shared_texture" in prop_names
        assert "layout_scale_factor" in prop_names
        # Controller should be filtered
        assert "controller" not in prop_names

    def test_rive_fit_type_maps_to_ft_box_fit(self, analyzer):
        """Fit type (rive-specific) should map to ft.BoxFit."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="RiveWidget",
                    constructor_params=[
                        DartParam(name="fit", dart_type="Fit"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "Rive", "ui_control", "rive", "flet_rive")
        prop = next(p for p in plan.properties if p.python_name == "fit")
        assert prop.python_type == "ft.BoxFit | None"


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
