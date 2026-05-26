"""Tests for the Dart source parser."""

from flet_pkg.core.parser import _parse_class_methods


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
