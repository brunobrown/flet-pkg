from flet_pkg.core.type_map import (
    get_flet_dart_getter,
    map_dart_type,
    map_dart_type_flet,
    map_return_type,
)


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


class TestMapDartTypeFlet:
    def test_alignment(self):
        assert map_dart_type_flet("Alignment") == "ft.Alignment"

    def test_alignment_geometry(self):
        assert map_dart_type_flet("AlignmentGeometry") == "ft.Alignment"

    def test_nullable_alignment(self):
        assert map_dart_type_flet("Alignment?") == "ft.Alignment | None"

    def test_box_fit(self):
        assert map_dart_type_flet("BoxFit") == "ft.BoxFit"

    def test_rect(self):
        assert map_dart_type_flet("Rect") == "ft.Rect"

    def test_color(self):
        assert map_dart_type_flet("Color") == "ft.Color"

    def test_double(self):
        assert map_dart_type_flet("double") == "ft.Number"

    def test_num(self):
        assert map_dart_type_flet("num") == "ft.Number"

    def test_widget(self):
        assert map_dart_type_flet("Widget") == "ft.Control"

    def test_key_returns_none(self):
        assert map_dart_type_flet("Key") is None

    def test_nullable_key_returns_none(self):
        assert map_dart_type_flet("Key?") is None

    def test_string_fallback(self):
        assert map_dart_type_flet("String") == "str"

    def test_bool_fallback(self):
        assert map_dart_type_flet("bool") == "bool"

    def test_int_fallback(self):
        assert map_dart_type_flet("int") == "int"

    def test_list_widget(self):
        assert map_dart_type_flet("List<Widget>") == "list[ft.Control]"

    def test_list_string(self):
        assert map_dart_type_flet("List<String>") == "list[str]"

    def test_future_alignment(self):
        assert map_dart_type_flet("Future<Alignment>") == "ft.Alignment"

    def test_unknown_type_passthrough(self):
        assert map_dart_type_flet("CustomThing") == "CustomThing"

    def test_fit_maps_to_box_fit(self):
        assert map_dart_type_flet("Fit") == "ft.BoxFit"

    def test_nullable_fit(self):
        assert map_dart_type_flet("Fit?") == "ft.BoxFit | None"

    def test_empty(self):
        assert map_dart_type_flet("") == "Any"


class TestGetFletDartGetter:
    def test_alignment(self):
        result = get_flet_dart_getter("ft.Alignment", "alignment")
        assert result == 'control.getAlignment("alignment")'

    def test_box_fit(self):
        result = get_flet_dart_getter("ft.BoxFit", "fit")
        assert result == 'control.getBoxFit("fit")'

    def test_rect(self):
        result = get_flet_dart_getter("ft.Rect", "rect")
        assert result == 'control.getRect("rect")'

    def test_number(self):
        result = get_flet_dart_getter("ft.Number", "size")
        assert result == 'control.getDouble("size")'

    def test_control(self):
        result = get_flet_dart_getter("ft.Control", "child")
        assert result == 'buildWidget("child")'

    def test_bool(self):
        result = get_flet_dart_getter("bool", "enabled")
        assert result == 'control.getBool("enabled", false)!'

    def test_str(self):
        result = get_flet_dart_getter("str", "name")
        assert result == 'control.getString("name")'

    def test_nullable_type_strips_none(self):
        result = get_flet_dart_getter("ft.Alignment | None", "alignment")
        assert result == 'control.getAlignment("alignment")'

    def test_list_control(self):
        result = get_flet_dart_getter("list[ft.Control]", "children")
        assert result == 'buildWidgets("children")'

    def test_unknown_fallback(self):
        result = get_flet_dart_getter("SomeCustomType", "custom")
        assert result == 'control.getString("custom")'


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
