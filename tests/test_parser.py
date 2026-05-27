"""Tests for the Dart source parser."""

from flet_pkg.core.parser import (
    _is_example_app_file,
    _parse_class_methods,
    parse_dart_package_api,
)


class TestExampleAppFiltering:
    """Demo/example app files shipped in lib/ must not yield control candidates."""

    def test_detects_main_entrypoint(self):
        assert _is_example_app_file("void main() {\n  runApp(const MyApp());\n}")
        assert _is_example_app_file("Future<void> main() async {\n  runApp(App());\n}")

    def test_ignores_library_file(self):
        lib = "class Shimmer extends StatefulWidget {\n  const Shimmer({super.key});\n}"
        assert not _is_example_app_file(lib)

    def test_ignores_indented_main_method(self):
        # A method named `main` inside a class is not a top-level entrypoint.
        klass = "class Foo {\n  void main() {}\n}"
        assert not _is_example_app_file(klass)

    def test_skips_example_widgets_in_lib(self, tmp_path):
        lib = tmp_path / "lib"
        lib.mkdir()
        (lib / "shimmer.dart").write_text(
            "library shimmer;\n"
            "import 'package:flutter/material.dart';\n"
            "class Shimmer extends StatefulWidget {\n"
            "  const Shimmer({super.key, required this.child});\n"
            "  final Widget child;\n"
            "  @override\n"
            "  State<Shimmer> createState() => _ShimmerState();\n"
            "}\n"
        )
        (lib / "main.dart").write_text(
            "import 'package:flutter/material.dart';\n"
            "void main() {\n  runApp(const MyApp());\n}\n"
            "class MyApp extends StatelessWidget {\n"
            "  const MyApp({super.key});\n"
            "}\n"
            "class MyHomePage extends StatefulWidget {\n"
            "  const MyHomePage({super.key, required this.title});\n"
            "  final String title;\n"
            "  @override\n"
            "  State<MyHomePage> createState() => _MyHomePageState();\n"
            "}\n"
        )
        api = parse_dart_package_api(tmp_path, include_widgets=True)
        names = {c.name for c in api.classes}
        assert "Shimmer" in names
        assert "MyApp" not in names
        assert "MyHomePage" not in names


class TestAnnotationFiltering:
    """Methods annotated as test-only / non-public must be skipped.

    The annotations are indented inside a class body and the method signature
    sits on the next (also indented) line — the regex must consume that
    indentation, otherwise the annotation is dropped from the match and the
    method leaks into the generated bridge (breaking `flutter analyze`).
    """

    def test_skips_indented_visible_for_testing(self):
        src = """
class FlutterSecureStorage {
  /// Writes a value.
  Future<void> write({required String key, required String? value}) async {}

  /// Initializes mock values for testing.
  @visibleForTesting
  static void setMockInitialValues(Map<String, String> values) {}
}
"""
        names = {m.name for m in _parse_class_methods(src)}
        assert "write" in names
        assert "setMockInitialValues" not in names

    def test_skips_indented_protected(self):
        src = """
class Foo {
  @protected
  void internalOnly() {}

  Future<String?> publicApi() async {}
}
"""
        names = {m.name for m in _parse_class_methods(src)}
        assert "publicApi" in names
        assert "internalOnly" not in names

    def test_skips_deprecated_with_message(self):
        src = """
class Foo {
  @Deprecated('Use bar instead')
  void oldThing() {}

  void bar() {}
}
"""
        names = {m.name for m in _parse_class_methods(src)}
        assert "bar" in names
        assert "oldThing" not in names


class TestParamParsing:
    """Constructor/method parameter parsing edge cases."""

    def test_param_with_multiline_deprecated_annotation_and_default(self):
        """A param annotated with a multi-line @Deprecated and a default must
        parse its name/type/default correctly (regression: the name was parsed
        as the keyword `false`, emitting an invalid `false:` Dart arg)."""
        src = """
class Geolocator {
  static Future<Position> getCurrentPosition({
    LocationSettings? locationSettings,
    @Deprecated(
        "use settings parameter with AndroidSettings, AppleSettings")
    bool forceAndroidLocationManager = false,
  }) async {}
}
"""
        methods = _parse_class_methods(src)
        params = {p.name: p for m in methods for p in m.params}
        assert "false" not in params
        assert "forceAndroidLocationManager" in params
        p = params["forceAndroidLocationManager"]
        assert p.dart_type == "bool"
        assert p.default == "false"
