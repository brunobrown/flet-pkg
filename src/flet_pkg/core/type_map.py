"""
Dart-to-Python type mapping.

Converts Dart type annotations to their Python equivalents,
handling nullable types, generics, and common Flutter types.
"""

from __future__ import annotations

import re

# Direct type mappings: Dart type -> Python type
_TYPE_MAP: dict[str, str] = {
    "String": "str",
    "bool": "bool",
    "int": "int",
    "double": "float",
    "num": "float",
    "void": "None",
    "dynamic": "Any",
    "Object": "Any",
    "Color": "str",
    "Duration": "int",
    "DateTime": "str",
    "Uint8List": "bytes",
    "BigInt": "int",
    "Uri": "str",
    "Rect": "dict",
    # Common Flutter enums (mapped to str for Flet serialization)
    "TextDirection": "str",
    "Axis": "str",
    "StackFit": "str",
    "MainAxisAlignment": "str",
    "CrossAxisAlignment": "str",
    "MainAxisSize": "str",
    "VerticalDirection": "str",
    "TextAlign": "str",
    "TextOverflow": "str",
    "FontWeight": "str",
    "FontStyle": "str",
    "TextBaseline": "str",
    "Clip": "str",
    "BoxFit": "str",
    "Alignment": "str",
    "AlignmentGeometry": "str",
    "AlignmentDirectional": "str",
    "BlendMode": "str",
    "FilterQuality": "str",
    "ImageRepeat": "str",
    "Curve": "str",
    "StrokeCap": "str",
    "StrokeJoin": "str",
    "PaintingStyle": "str",
    "TileMode": "str",
    "WrapAlignment": "str",
    "WrapCrossAlignment": "str",
    "HitTestBehavior": "str",
    "DragStartBehavior": "str",
    "ScrollViewKeyboardDismissBehavior": "str",
    "TextInputType": "str",
    "TextInputAction": "str",
    "TextCapitalization": "str",
    "Brightness": "str",
    "TabBarIndicatorSize": "str",
    "FloatingLabelBehavior": "str",
}

# Regex to extract generic type parameters: e.g. List<String> -> ("List", "String")
_GENERIC_RE = re.compile(r"^(\w+)\s*<(.+)>$")

# Regex to detect nullable: e.g. String? -> ("String", True)
_NULLABLE_RE = re.compile(r"^(.+?)\?$")


def map_dart_type(dart_type: str) -> str:
    """Map a Dart type annotation to its Python equivalent.

    Handles nullable types (``String?`` -> ``str | None``), generics
    (``List<String>`` -> ``list[str]``), nested generics
    (``Map<String, List<int>>`` -> ``dict[str, list[int]]``), and
    ``Future<T>`` (unwraps to the inner type).

    Args:
        dart_type: The Dart type string to convert.

    Returns:
        The corresponding Python type string.
    """
    dart_type = dart_type.strip()
    if not dart_type:
        return "Any"

    # Handle nullable
    nullable_match = _NULLABLE_RE.match(dart_type)
    if nullable_match:
        inner = map_dart_type(nullable_match.group(1))
        return f"{inner} | None"

    # Handle generics
    generic_match = _GENERIC_RE.match(dart_type)
    if generic_match:
        outer = generic_match.group(1)
        inner_raw = generic_match.group(2)

        # Future<T> -> unwrap to T
        if outer == "Future":
            return map_dart_type(inner_raw)

        # Split generic params respecting nested angle brackets
        inner_types = _split_generic_params(inner_raw)
        mapped_inner = ", ".join(map_dart_type(t) for t in inner_types)

        if outer == "List":
            return f"list[{mapped_inner}]"
        if outer == "Set":
            return f"set[{mapped_inner}]"
        if outer == "Map":
            return f"dict[{mapped_inner}]"
        if outer == "Iterable":
            return f"list[{mapped_inner}]"

        # Unknown generic: just map the outer
        mapped_outer = _TYPE_MAP.get(outer, outer)
        return f"{mapped_outer}[{mapped_inner}]"

    # Direct lookup
    if dart_type in _TYPE_MAP:
        return _TYPE_MAP[dart_type]

    # Function types
    if "Function" in dart_type:
        return "Any"

    # Unknown type: pass through as-is
    return dart_type


def map_return_type(dart_type: str) -> tuple[str, bool]:
    """Map a Dart return type, detecting if the method is async.

    Args:
        dart_type: The Dart return type string.

    Returns:
        A tuple of (python_type, is_async). ``is_async`` is True
        when the Dart return type is ``Future<T>``.
    """
    dart_type = dart_type.strip()
    if not dart_type:
        return "None", False

    generic_match = _GENERIC_RE.match(dart_type)
    if generic_match and generic_match.group(1) == "Future":
        inner = generic_match.group(2).strip()
        if inner == "void":
            return "None", True
        return map_dart_type(inner), True

    if dart_type == "Future":
        return "None", True

    return map_dart_type(dart_type), False


def _split_generic_params(params_str: str) -> list[str]:
    """Split generic type parameters respecting nested angle brackets.

    ``"String, List<int>"`` -> ``["String", "List<int>"]``
    """
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in params_str:
        if char == "<":
            depth += 1
            current.append(char)
        elif char == ">":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current).strip())
    return parts
