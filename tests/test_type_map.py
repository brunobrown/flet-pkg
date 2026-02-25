from flet_pkg.core.type_map import map_dart_type, map_return_type


class TestMapDartType:
    def test_string(self):
        assert map_dart_type("String") == "str"

    def test_bool(self):
        assert map_dart_type("bool") == "bool"

    def test_int(self):
        assert map_dart_type("int") == "int"

    def test_double(self):
        assert map_dart_type("double") == "float"

    def test_num(self):
        assert map_dart_type("num") == "float"

    def test_void(self):
        assert map_dart_type("void") == "None"

    def test_dynamic(self):
        assert map_dart_type("dynamic") == "Any"

    def test_object(self):
        assert map_dart_type("Object") == "Any"

    def test_color(self):
        assert map_dart_type("Color") == "str"

    def test_nullable_string(self):
        assert map_dart_type("String?") == "str | None"

    def test_nullable_bool(self):
        assert map_dart_type("bool?") == "bool | None"

    def test_nullable_int(self):
        assert map_dart_type("int?") == "int | None"

    def test_list_string(self):
        assert map_dart_type("List<String>") == "list[str]"

    def test_list_int(self):
        assert map_dart_type("List<int>") == "list[int]"

    def test_map_string_dynamic(self):
        assert map_dart_type("Map<String, dynamic>") == "dict[str, Any]"

    def test_map_string_string(self):
        assert map_dart_type("Map<String, String>") == "dict[str, str]"

    def test_set(self):
        assert map_dart_type("Set<String>") == "set[str]"

    def test_future_void(self):
        assert map_dart_type("Future<void>") == "None"

    def test_future_string(self):
        assert map_dart_type("Future<String>") == "str"

    def test_future_bool(self):
        assert map_dart_type("Future<bool>") == "bool"

    def test_nested_generic(self):
        assert map_dart_type("Map<String, List<int>>") == "dict[str, list[int]]"

    def test_empty(self):
        assert map_dart_type("") == "Any"

    def test_unknown_type(self):
        assert map_dart_type("CustomWidget") == "CustomWidget"

    def test_function_type(self):
        assert map_dart_type("Function") == "Any"

    def test_iterable(self):
        assert map_dart_type("Iterable<String>") == "list[str]"


class TestMapReturnType:
    def test_void(self):
        py_type, is_async = map_return_type("void")
        assert py_type == "None"
        assert is_async is False

    def test_future_void(self):
        py_type, is_async = map_return_type("Future<void>")
        assert py_type == "None"
        assert is_async is True

    def test_future_string(self):
        py_type, is_async = map_return_type("Future<String>")
        assert py_type == "str"
        assert is_async is True

    def test_future_bool(self):
        py_type, is_async = map_return_type("Future<bool>")
        assert py_type == "bool"
        assert is_async is True

    def test_bare_future(self):
        py_type, is_async = map_return_type("Future")
        assert py_type == "None"
        assert is_async is True

    def test_string(self):
        py_type, is_async = map_return_type("String")
        assert py_type == "str"
        assert is_async is False

    def test_empty(self):
        py_type, is_async = map_return_type("")
        assert py_type == "None"
        assert is_async is False
