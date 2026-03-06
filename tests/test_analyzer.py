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
                values=[
                    ("none", ""),
                    ("fatal", ""),
                    ("error", ""),
                    ("warn", ""),
                    ("info", ""),
                    ("debug", ""),
                    ("verbose", ""),
                ],
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


class TestEnumLikeSuffixHeuristic:
    """Tests that unknown types with enum-like suffixes map to str, not dict."""

    def test_rive_hit_test_behavior_maps_to_str(self, analyzer):
        """RiveHitTestBehavior (enum from transitive dep) → str | None."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="RiveWidget",
                    constructor_params=[
                        DartParam(name="hitTestBehavior", dart_type="RiveHitTestBehavior"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "Rive", "ui_control", "rive", "flet_rive")
        prop = next(p for p in plan.properties if p.python_name == "hit_test_behavior")
        assert prop.python_type == "str | None"

    def test_custom_mode_enum_maps_to_str(self, analyzer):
        """Types ending in 'Mode' should map to str."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyWidget",
                    constructor_params=[
                        DartParam(name="renderMode", dart_type="CustomRenderMode"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "MyWidget", "ui_control", "my_pkg", "flet_my")
        prop = next(p for p in plan.properties if p.python_name == "render_mode")
        assert prop.python_type == "str | None"

    def test_custom_style_enum_maps_to_str(self, analyzer):
        """Types ending in 'Style' should map to str."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyWidget",
                    constructor_params=[
                        DartParam(name="lineStyle", dart_type="CustomLineStyle"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "MyWidget", "ui_control", "my_pkg", "flet_my")
        prop = next(p for p in plan.properties if p.python_name == "line_style")
        assert prop.python_type == "str | None"

    def test_unknown_class_without_enum_suffix_stays_dict(self, analyzer):
        """Unknown types without enum suffix should still become dict | None."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyWidget",
                    constructor_params=[
                        DartParam(name="options", dart_type="CustomOptions"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "MyWidget", "ui_control", "my_pkg", "flet_my")
        prop = next(p for p in plan.properties if p.python_name == "options")
        assert prop.python_type == "dict | None"


class TestParserFieldRegex:
    """Bug 1: Ensure `return child;` is not matched as a field declaration."""

    def test_widget_child_type_not_return(self, analyzer):
        """Widget? child should map to ft.Control | None, not return | None."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="CameraPreview",
                    parent_class="StatelessWidget",
                    constructor_params=[
                        DartParam(name="child", dart_type="Widget?"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "Camera", "ui_control", "camera", "flet_camera")
        child_props = [p for p in plan.properties if p.python_name == "child"]
        assert len(child_props) == 1
        assert "return" not in child_props[0].python_type
        assert "ft.Control" in child_props[0].python_type


class TestDartNamePreserved:
    """Bug 2: PropertyPlan.dart_name should preserve original camelCase."""

    def test_dart_name_stored(self, analyzer):
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="WebView",
                    parent_class="StatefulWidget",
                    constructor_params=[
                        DartParam(name="initialUrl", dart_type="String?"),
                        DartParam(name="debuggingEnabled", dart_type="bool"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "WebView", "ui_control", "webview_flutter", "flet_webview")
        prop_map = {p.python_name: p for p in plan.properties}
        assert prop_map["initial_url"].dart_name == "initialUrl"
        assert prop_map["debugging_enabled"].dart_name == "debuggingEnabled"


class TestPolicySuffix:
    """Bug 3: AutoMediaPlaybackPolicy should map to str, not dict."""

    def test_policy_suffix_maps_to_str(self, analyzer):
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="WebView",
                    parent_class="StatefulWidget",
                    constructor_params=[
                        DartParam(
                            name="initialMediaPlaybackPolicy",
                            dart_type="AutoMediaPlaybackPolicy",
                        ),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "WebView", "ui_control", "webview_flutter", "flet_webview")
        props = {p.python_name: p for p in plan.properties}
        assert "str" in props["initial_media_playback_policy"].python_type

    def test_strategy_suffix_maps_to_str(self, analyzer):
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="Foo",
                    parent_class="StatefulWidget",
                    constructor_params=[
                        DartParam(name="loadStrategy", dart_type="LoadStrategy"),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "Foo", "ui_control", "foo", "flet_foo")
        props = {p.python_name: p for p in plan.properties}
        assert "str" in props["load_strategy"].python_type


class TestUnknownGenericOuters:
    """Bug 4a: Unknown generic wrappers like Factory[...] → dict | None."""

    def test_factory_wrapper_collapsed(self, analyzer):
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="WebView",
                    parent_class="StatefulWidget",
                    constructor_params=[
                        DartParam(
                            name="gestureRecognizers",
                            dart_type="Set<Factory<OneSequenceGestureRecognizer>>?",
                        ),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "WebView", "ui_control", "webview_flutter", "flet_webview")
        props = {p.python_name: p for p in plan.properties}
        ptype = props["gesture_recognizers"].python_type
        # Factory should NOT appear in the type
        assert "Factory" not in ptype

    def test_undefined_inner_type_sanitized(self, analyzer):
        """Types from barrel (known_types) not actually generated → dict."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="WebView",
                    parent_class="StatefulWidget",
                    constructor_params=[
                        DartParam(
                            name="initialCookies",
                            dart_type="List<WebViewCookie>",
                        ),
                    ],
                ),
            ]
        )
        plan = analyzer.analyze(api, "WebView", "ui_control", "webview_flutter", "flet_webview")
        props = {p.python_name: p for p in plan.properties}
        ptype = props["initial_cookies"].python_type
        # WebViewCookie is not generated as a Python class → should be dict
        assert "WebViewCookie" not in ptype
        assert "list[" in ptype


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


class TestCompoundWidgetDetection:
    """Tests for compound widget (sub-control) detection."""

    def test_typed_sub_widget_detected(self, analyzer):
        """A typed param like ActionPane? should become a SubControlPlan."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="Slidable",
                    constructor_params=[
                        DartParam(name="startActionPane", dart_type="ActionPane?"),
                        DartParam(name="child", dart_type="Widget"),
                    ],
                    parent_class="StatefulWidget",
                ),
            ],
            component_classes=[
                DartClass(
                    name="ActionPane",
                    constructor_params=[
                        DartParam(name="extentRatio", dart_type="double"),
                        DartParam(name="children", dart_type="List<Widget>"),
                    ],
                ),
            ],
        )
        plan = analyzer.analyze(api, "Slidable", "ui_control", "flutter_slidable", "flet_slidable")
        assert len(plan.sub_controls) == 1
        sc = plan.sub_controls[0]
        assert sc.control_name == "ActionPane"
        assert sc.parent_property == "start_action_pane"
        assert sc.is_list is False

    def test_list_sub_widget_detected(self, analyzer):
        """A List<BarItem> param should become a SubControlPlan with is_list=True."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="NavBar",
                    constructor_params=[
                        DartParam(name="items", dart_type="List<BarItem>"),
                    ],
                    parent_class="StatefulWidget",
                ),
            ],
            component_classes=[
                DartClass(
                    name="BarItem",
                    constructor_params=[
                        DartParam(name="title", dart_type="String"),
                    ],
                ),
            ],
        )
        plan = analyzer.analyze(api, "NavBar", "ui_control", "nav_bar", "flet_nav_bar")
        assert len(plan.sub_controls) == 1
        sc = plan.sub_controls[0]
        assert sc.control_name == "BarItem"
        assert sc.is_list is True
        assert sc.parent_property == "items"

    def test_plain_widget_not_sub_control(self, analyzer):
        """A Widget? child should remain ft.Control, not a SubControlPlan."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyWidget",
                    constructor_params=[
                        DartParam(name="child", dart_type="Widget?"),
                        DartParam(name="title", dart_type="String"),
                    ],
                    parent_class="StatefulWidget",
                ),
            ],
        )
        plan = analyzer.analyze(api, "MyWidget", "ui_control", "my_widget", "flet_my_widget")
        assert len(plan.sub_controls) == 0
        # child should map to ft.Control | None, not a sub-control
        child_prop = next((p for p in plan.properties if p.python_name == "child"), None)
        assert child_prop is not None
        assert "ft.Control" in child_prop.python_type

    def test_max_depth_respected(self, analyzer):
        """Nesting deeper than max_depth=3 should not recurse."""
        # Create a 4-level deep chain: A → B → C → D
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="A",
                    constructor_params=[
                        DartParam(name="bChild", dart_type="B?"),
                    ],
                    parent_class="StatefulWidget",
                ),
            ],
            component_classes=[
                DartClass(
                    name="B",
                    constructor_params=[DartParam(name="cChild", dart_type="C?")],
                ),
                DartClass(
                    name="C",
                    constructor_params=[DartParam(name="dChild", dart_type="D?")],
                ),
                DartClass(
                    name="D",
                    constructor_params=[DartParam(name="value", dart_type="int")],
                ),
            ],
        )
        plan = analyzer.analyze(api, "A", "ui_control", "a_pkg", "flet_a")
        # A → B (depth 1) → C (depth 2) → D (depth 3, max)
        assert len(plan.sub_controls) == 1  # B
        b = plan.sub_controls[0]
        assert b.control_name == "B"
        assert len(b.sub_controls) == 1  # C
        c = b.sub_controls[0]
        assert c.control_name == "C"
        assert len(c.sub_controls) == 1  # D
        d = c.sub_controls[0]
        assert d.control_name == "D"
        assert len(d.sub_controls) == 0  # depth 3 = max, no further nesting

    def test_external_type_not_sub_control(self, analyzer):
        """Types not in the same package should NOT become sub-controls."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="MyWidget",
                    constructor_params=[
                        DartParam(name="data", dart_type="ExternalClass?"),
                    ],
                    parent_class="StatefulWidget",
                ),
            ],
            # No component_classes — ExternalClass is from another package
        )
        plan = analyzer.analyze(api, "MyWidget", "ui_control", "my_widget", "flet_my_widget")
        assert len(plan.sub_controls) == 0

    def test_backward_compat_simple_widget(self, analyzer):
        """Simple widget without sub-controls should have no regression."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="CameraPreview",
                    constructor_params=[
                        DartParam(name="child", dart_type="Widget?"),
                        DartParam(name="fit", dart_type="BoxFit?"),
                        DartParam(name="width", dart_type="double"),
                    ],
                    parent_class="StatefulWidget",
                ),
            ],
        )
        plan = analyzer.analyze(api, "CameraPreview", "ui_control", "camera", "flet_camera")
        assert len(plan.sub_controls) == 0
        assert len(plan.properties) > 0
        prop_names = [p.python_name for p in plan.properties]
        assert "fit" in prop_names
        assert "width" in prop_names

    def test_sub_control_property_type_not_sanitized(self, analyzer):
        """Sub-control types should appear as class names, not dict | None."""
        api = DartPackageAPI(
            classes=[
                DartClass(
                    name="Slidable",
                    constructor_params=[
                        DartParam(name="actionPane", dart_type="ActionPane?"),
                        DartParam(name="child", dart_type="Widget"),
                    ],
                    parent_class="StatefulWidget",
                ),
            ],
            component_classes=[
                DartClass(
                    name="ActionPane",
                    constructor_params=[
                        DartParam(name="extentRatio", dart_type="double"),
                    ],
                ),
            ],
        )
        plan = analyzer.analyze(api, "Slidable", "ui_control", "flutter_slidable", "flet_slidable")
        # The property type should be ActionPane | None, not dict | None
        ap_prop = next((p for p in plan.properties if p.python_name == "action_pane"), None)
        assert ap_prop is not None
        assert "ActionPane" in ap_prop.python_type
        assert "dict" not in ap_prop.python_type


# ---------------------------------------------------------------------------
# Multi-widget classification tests
# ---------------------------------------------------------------------------


class TestMultiWidgetClassification:
    """Tests for _classify_multi_widgets and multi-widget processing."""

    def _make_widget(self, name: str, params: list[str]) -> DartClass:
        """Helper to make a DartClass with constructor params."""
        return DartClass(
            name=name,
            constructor_params=[DartParam(name=p, dart_type="double") for p in params],
        )

    def test_single_widget_returns_single(self, analyzer):
        widgets = [self._make_widget("Shimmer", ["color", "size"])]
        strategy, filtered = analyzer._classify_multi_widgets(widgets, "Shimmer")
        assert strategy == "single"
        assert len(filtered) == 1

    def test_family_detection_many_widgets(self, analyzer):
        """≥5 widgets should classify as family."""
        shared = ["color", "size", "duration"]
        widgets = [
            self._make_widget(f"SpinKit{name}", shared + [f"extra_{i}"])
            for i, name in enumerate(["Circle", "HourGlass", "Wave", "Pulse", "Ring"])
        ]
        strategy, filtered = analyzer._classify_multi_widgets(widgets, "SpinKit")
        assert strategy == "family"
        assert len(filtered) == 5

    def test_family_detection_high_overlap(self, analyzer):
        """2-4 widgets with ≥60% overlap should classify as family."""
        widgets = [
            self._make_widget("FooA", ["color", "size", "duration", "extra"]),
            self._make_widget("FooB", ["color", "size", "duration", "other"]),
        ]
        strategy, _ = analyzer._classify_multi_widgets(widgets, "Foo")
        assert strategy == "family"

    def test_sibling_detection_low_overlap(self, analyzer):
        """2-4 widgets with <60% overlap should classify as sibling."""
        widgets = [
            self._make_widget("CircularIndicator", ["percent", "radius", "center"]),
            self._make_widget(
                "LinearIndicator", ["percent", "width", "height", "bar_radius", "fill"]
            ),
        ]
        strategy, _ = analyzer._classify_multi_widgets(widgets, "Indicator")
        assert strategy == "sibling"

    def test_single_fallback_private_only(self, analyzer):
        """All private classes → fallback to single."""
        widgets = [
            self._make_widget("_InternalWidget", ["x"]),
        ]
        strategy, _ = analyzer._classify_multi_widgets(widgets, "Internal")
        assert strategy == "single"


class TestWidgetFamilyProcessing:
    """Tests for _process_widget_family."""

    def _make_widget(self, name: str, params: list[str]) -> DartClass:
        return DartClass(
            name=name,
            constructor_params=[DartParam(name=p, dart_type="double") for p in params],
        )

    def test_family_creates_type_enum(self, analyzer):
        shared = ["color", "size"]
        widgets = [
            self._make_widget(f"SpinKit{v}", shared)
            for v in ["Circle", "HourGlass", "Wave", "Pulse", "Ring"]
        ]
        api = DartPackageAPI(classes=widgets)
        plan = analyzer.analyze(api, "SpinKit", "ui_control", "flutter_spinkit", "flet_spinkit")
        # Should have SpinKitType enum
        enum_names = [e.python_name for e in plan.enums]
        assert "SpinKitType" in enum_names

        # Should have widget_family_variants
        assert len(plan.widget_family_variants) == 5
        variant_values = [v.enum_value for v in plan.widget_family_variants]
        assert "circle" in variant_values
        assert "hour_glass" in variant_values

    def test_family_extracts_shared_properties(self, analyzer):
        widgets = [
            self._make_widget("SpinKitCircle", ["color", "size", "lineWidth"]),
            self._make_widget("SpinKitWave", ["color", "size", "itemCount"]),
        ]
        api = DartPackageAPI(classes=widgets)
        plan = analyzer.analyze(api, "SpinKit", "ui_control", "flutter_spinkit", "flet_spinkit")
        prop_names = [p.python_name for p in plan.properties]
        assert "color" in prop_names
        assert "size" in prop_names
        # "type" should be the first property
        assert prop_names[0] == "type"

    def test_family_has_type_property(self, analyzer):
        widgets = [
            self._make_widget("SpinKitA", ["x"]),
            self._make_widget("SpinKitB", ["x"]),
            self._make_widget("SpinKitC", ["x"]),
            self._make_widget("SpinKitD", ["x"]),
            self._make_widget("SpinKitE", ["x"]),
        ]
        api = DartPackageAPI(classes=widgets)
        plan = analyzer.analyze(api, "SpinKit", "ui_control", "flutter_spinkit", "flet_spinkit")
        # First property should be "type"
        assert plan.properties[0].python_name == "type"
        assert "SpinKitType" in plan.properties[0].python_type


class TestSiblingWidgetProcessing:
    """Tests for _process_sibling_widgets."""

    def _make_widget(self, name: str, params: list[str]) -> DartClass:
        return DartClass(
            name=name,
            constructor_params=[DartParam(name=p, dart_type="double") for p in params],
        )

    def test_sibling_creates_separate_plans(self, analyzer):
        widgets = [
            self._make_widget("CircularPercentIndicator", ["percent", "radius"]),
            self._make_widget("LinearPercentIndicator", ["percent", "width", "height", "extra"]),
        ]
        api = DartPackageAPI(classes=widgets)
        plan = analyzer.analyze(
            api, "PercentIndicator", "ui_control", "percent_indicator", "flet_percent_indicator"
        )
        # Should have sibling_widgets
        assert len(plan.sibling_widgets) >= 1
        sib_names = [s.control_name for s in plan.sibling_widgets]
        # One of the two is the main widget, the other is a sibling
        assert plan.dart_main_class in ("CircularPercentIndicator", "LinearPercentIndicator")
        # The sibling should be the other one
        for sib_name in sib_names:
            assert sib_name != plan.dart_main_class

    def test_sibling_has_own_properties(self, analyzer):
        widgets = [
            self._make_widget("CircularIndicator", ["percent", "radius"]),
            self._make_widget("LinearIndicator", ["percent", "width", "height"]),
        ]
        api = DartPackageAPI(classes=widgets)
        plan = analyzer.analyze(api, "Indicator", "ui_control", "test_indicator", "flet_indicator")
        assert len(plan.sibling_widgets) >= 1
        sibling = plan.sibling_widgets[0]
        assert len(sibling.properties) > 0
