"""
Dart source code parser.

Parses Dart package source files to extract classes, methods, enums,
and their metadata into structured ``DartPackageAPI`` models.
"""

from __future__ import annotations

import keyword
import re
from pathlib import Path
from typing import Any

from flet_pkg.core.models import (
    DartClass,
    DartEnum,
    DartMethod,
    DartPackageAPI,
    DartParam,
)

UI_METHODS = {
    "build",
    "create",
    "initState",
    "dispose",
    "debugFillProperties",
    "didChangeDependencies",
    "didUpdateWidget",
    "setState",
    "toString",
    "noSuchMethod",
    "lifecycleInit",
    "MethodChannel",
    "jsonRepresentation",
    "convertToJsonString",
    "if",
    "if_",
    "that",
    "and_",
    "createState",
    "fromJson",
    "toJson",
    "toJsonString",
    "jsonEncode",
    "instance",
    "callback",
    "refuseInCallingOnInvitationReceived",
}

LIFECYCLE_METHODS = {
    "onLoad",
    "onMount",
    "onRemove",
    "onChildrenChanged",
    "onGameResize",
    "update",
    "render",
    "dispose",
    "renderDebugMode",
    "renderTree",
    "updateTree",
}

# Classes whose name ENDS with these suffixes are skipped as main API classes.
UI_CLASS_SUFFIXES = (
    "Widget",
    "Control",
    "Delegate",
    "Manager",
    "View",
    "Page",
    "Overlay",
    "Config",
    "Protocol",
    "Private",
    "Impl",
    "Guard",
    "Foreground",
    "Background",
    "Internal",
    "Instance",
    "Plugins",
    "ServiceAPIPrivateImpl",
)

# Classes ending with these are parsed into helper_classes (not skipped entirely).
# Used for event field extraction and type resolution.
HELPER_CLASS_SUFFIXES = (
    "Event",
    "Data",
    "Result",
    "State",
    "ChangedState",
    "ClickResult",
    "Button",
    "Layout",
)

# Parent classes that indicate a data/serialization class (not an API).
# Classes extending these are treated as helper classes.
DATA_MODEL_BASES = (
    "JSONStringRepresentable",
    "Serializable",
    "JsonModel",
)


def camel_to_snake(name: str) -> str:
    """Convert ``CamelCase`` or ``camelCase`` to ``snake_case``.

    Handles consecutive uppercase letters (acronyms) properly:
    ``JWT`` -> ``jwt``, ``loginWithJWT`` -> ``login_with_jwt``,
    ``ABCDef`` -> ``abc_def``.
    """
    # Handle consecutive uppercase (acronyms): ABCDef -> ABC_Def
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    # Handle transitions from lowercase/digit to uppercase: camelCase -> camel_Case
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


def _should_skip_class(class_name: str, docstring: str = "", parent_class: str = "") -> bool:
    """Check if a class should be skipped entirely (not parsed at all)."""
    return (
        class_name.startswith("_")
        or class_name.endswith(UI_CLASS_SUFFIXES)
        or "nodoc" in docstring.lower()
        or "internal" in docstring.lower()
    )


def _is_helper_class(class_name: str, parent_class: str = "") -> bool:
    """Check if a class is a helper/data class.

    These are parsed into helper_classes for event field extraction.
    Detected by suffix (Event, Data, Result, State, etc.) or by extending
    known serialization base classes.
    """
    if class_name.endswith(HELPER_CLASS_SUFFIXES):
        return True
    if parent_class in DATA_MODEL_BASES:
        return True
    return False


def _should_skip_method(method_name: str, docstring: str = "") -> bool:
    return (
        method_name in UI_METHODS
        or method_name in LIFECYCLE_METHODS
        or method_name.startswith("_")
        or method_name.startswith("on")
        or "nodoc" in docstring.lower()
        or not method_name.isidentifier()
        or method_name[0].isupper()
    )


def _is_inside_comment(text: str, pos: int) -> bool:
    """Check if *pos* falls inside a ``//`` or ``///`` comment."""
    line_start = text.rfind("\n", 0, pos) + 1
    line_prefix = text[line_start:pos]
    return "//" in line_prefix


def _is_callback_param(param: DartParam) -> bool:
    """Check if a parameter is a callback/function type."""
    t = param.dart_type
    return "Function" in t or "Callback" in t or "void " in t


def _is_remove_listener_method(name: str) -> bool:
    """Check if a method is a remove*Listener/Observer/Handler."""
    return bool(re.match(r"remove\w+(Listener|Observer|Handler)$", name))


def _clean_docstring(match: re.Match) -> str:
    doc = match.group(1) or match.group(2) or ""
    doc = re.sub(r"///+", "", doc)
    doc = re.sub(r"/\*\*|\*/", "", doc)
    return doc.strip().replace("\n", " ").replace("  ", " ")


def _extract_code_block(content: str) -> str | None:
    """Extract text inside a ``{ ... }`` block, handling comments and strings.

    ``content`` must start with the opening ``{``.  Returns the text
    between the braces (exclusive) or ``None`` if the block is never closed.
    """
    brace_count = 1
    i = 1
    length = len(content)
    while i < length:
        c = content[i]

        # Skip single-line comments  ( // ... \n )
        if c == "/" and i + 1 < length and content[i + 1] == "/":
            i = content.find("\n", i)
            if i == -1:
                break
            i += 1
            continue

        # Skip multi-line comments  ( /* ... */ )
        if c == "/" and i + 1 < length and content[i + 1] == "*":
            i = content.find("*/", i + 2)
            if i == -1:
                break
            i += 2
            continue

        # Skip string literals (single-quoted, double-quoted, triple-quoted)
        if c in ("'", '"'):
            # Check for triple-quote
            if i + 2 < length and content[i + 1] == c and content[i + 2] == c:
                end = content.find(c * 3, i + 3)
                if end == -1:
                    break
                i = end + 3
                continue
            # Single-quoted string: advance past escaped chars
            i += 1
            while i < length and content[i] != c:
                if content[i] == "\\":
                    i += 1  # skip escaped char
                i += 1
            i += 1  # skip closing quote
            continue

        if c == "{":
            brace_count += 1
        elif c == "}":
            brace_count -= 1
            if brace_count == 0:
                return content[1:i]
        i += 1
    return None


def _split_params(param_str: str) -> list[str]:
    params: list[str] = []
    current: list[str] = []
    paren_level = 0
    angle_level = 0
    for char in param_str:
        if char == "," and paren_level == 0 and angle_level == 0:
            params.append("".join(current).strip())
            current = []
        else:
            if char == "(":
                paren_level += 1
            elif char == ")":
                paren_level -= 1
            elif char == "<":
                angle_level += 1
            elif char == ">":
                angle_level -= 1
            current.append(char)
    if current:
        params.append("".join(current).strip())
    return params


def _parse_param(param_str: str, is_named_section: bool) -> DartParam | None:
    """Parse a single parameter string into a DartParam."""
    param_str = param_str.strip()
    if not param_str:
        return None

    required = False
    if param_str.startswith("required "):
        required = True
        param_str = param_str[len("required ") :].strip()

    # Extract default value
    default = None
    default_match = re.match(r"^(.+?)\s*=\s*(.+)$", param_str)
    if default_match:
        param_str = default_match.group(1).strip()
        default = default_match.group(2).strip()

    # Remove annotations like @Deprecated
    param_str = re.sub(r"@\w+(\([^)]*\))?\s*", "", param_str).strip()

    parts = param_str.split()
    if len(parts) < 2:
        # No type annotation, just a name
        name = parts[0] if parts else ""
        if not name or not name.isidentifier():
            return None
        return DartParam(
            name=name,
            dart_type="dynamic",
            required=required and not default,
            named=is_named_section,
            default=default,
        )

    dart_type = " ".join(parts[:-1])
    name = parts[-1]

    if not name.isidentifier():
        return None

    return DartParam(
        name=name,
        dart_type=dart_type,
        required=required and not default,
        named=is_named_section,
        default=default,
    )


def _parse_params_string(params_raw: str) -> list[DartParam]:
    """Parse a full Dart parameter list string into DartParam objects."""
    params_raw = params_raw.strip()
    if not params_raw:
        return []

    result: list[DartParam] = []

    # Detect named params section: { ... }
    # and positional params section: [ ... ]
    is_named = False
    is_optional = False
    clean = []
    for char in params_raw:
        if char == "{":
            is_named = True
            continue
        if char == "}":
            is_named = False
            continue
        if char == "[":
            is_optional = True
            continue
        if char == "]":
            is_optional = False
            continue
        clean.append((char, is_named, is_optional))

    # Rebuild with markers
    segments: list[tuple[str, bool]] = []
    current_chars: list[str] = []
    current_named = False
    for char, named, _opt in clean:
        if not current_chars:
            current_named = named
        if char == "," and _count_depth(current_chars) == 0:
            segments.append(("".join(current_chars).strip(), current_named))
            current_chars = []
            current_named = named
        else:
            current_chars.append(char)
    if current_chars:
        segments.append(("".join(current_chars).strip(), current_named))

    for seg, named in segments:
        param = _parse_param(seg, named)
        if param:
            result.append(param)

    return result


def _count_depth(chars: list[str]) -> int:
    depth = 0
    for c in chars:
        if c in "(<":
            depth += 1
        elif c in ")>":
            depth -= 1
    return depth


# ---------------------------------------------------------------------------
# Typedef parsing
# ---------------------------------------------------------------------------

# Matches: typedef void TypedefName(ParamType param);
# Also:    typedef void TypedefName(ParamType param, ...)
_TYPEDEF_RE = re.compile(
    r"typedef\s+\w+\s+(\w+)\s*\(([^)]*)\)\s*;",
)


def _parse_typedefs(content: str) -> dict[str, str]:
    """Extract typedef declarations and map typedef name to first param type.

    Returns a dict mapping typedef name -> first parameter type.
    For example: ``OnNotificationClickListener`` -> ``OSNotificationClickEvent``
    """
    typedefs: dict[str, str] = {}
    for match in _TYPEDEF_RE.finditer(content):
        typedef_name = match.group(1)
        params_str = match.group(2).strip()
        if not params_str:
            continue
        # Get the first parameter's type
        first_param = params_str.split(",")[0].strip()
        parts = first_param.split()
        if len(parts) >= 2:
            # "ParamType paramName" → extract ParamType
            param_type = parts[0]
            typedefs[typedef_name] = param_type
        elif len(parts) == 1 and parts[0][0].isupper():
            # Just a type name without param name
            typedefs[typedef_name] = parts[0]
    return typedefs


# ---------------------------------------------------------------------------
# Enum parsing
# ---------------------------------------------------------------------------

_ENUM_RE = re.compile(
    r"(?:///[^\n]*\n|/\*\*.*?\*/\s*)?"
    r"enum\s+(\w+)\s*\{([^}]*)\}",
    re.DOTALL,
)


def _parse_enums(content: str) -> list[DartEnum]:
    """Extract enum declarations from Dart source."""
    enums: list[DartEnum] = []
    for match in _ENUM_RE.finditer(content):
        name = match.group(1)
        body = match.group(2)

        # Extract docstring before enum
        doc_match = re.search(
            r"(///[^\n]*(?:\n///[^\n]*)*|/\*\*.*?\*/)\s*$",
            content[: match.start()],
            re.DOTALL,
        )
        docstring = _clean_docstring(doc_match) if doc_match else ""

        # Parse values: strip comments and annotations
        values = []
        for line in body.split(","):
            val = line.strip()
            val = re.sub(r"//.*$", "", val).strip()
            val = re.sub(r";.*$", "", val).strip()
            # Skip constructor-like entries (e.g. `value(1)`)
            val = re.sub(r"\(.*\)$", "", val).strip()
            if val and val.isidentifier() and not val.startswith("_"):
                values.append(val)

        if values:
            enums.append(DartEnum(name=name, values=values, docstring=docstring))

    return enums


# ---------------------------------------------------------------------------
# Class method parsing (shared between main and helper classes)
# ---------------------------------------------------------------------------


def _parse_class_methods(
    class_block: str, skip_filter: bool = True
) -> list[DartMethod]:
    """Parse methods from a class body block."""
    methods: list[DartMethod] = []
    seen: set[str] = set()

    # Parse methods with parentheses: `Type name(params)` or `Type get/set name(params)`
    method_matches = re.finditer(
        r"(?:@[^\n]*\n)*"
        r"(static\s+)?"
        r"(Future<.*?>|Future|void|String|bool|int|double|dynamic|"
        r"Map<.*?>|List<.*?>|Set<.*?>|\w+(?:\?)?)\s+"
        r"(get\s+|set\s+)?(\w+)"
        r"\s*\(([^)]*)\)",
        class_block,
    )

    for m in method_matches:
        # Skip matches that fall inside a comment line
        if _is_inside_comment(class_block, m.start()):
            continue

        is_static = m.group(1) is not None
        return_type = m.group(2)
        accessor = m.group(3)
        is_getter = accessor is not None and accessor.strip() == "get"
        is_setter = accessor is not None and accessor.strip() == "set"
        method_name = m.group(4)
        params_raw = m.group(5)

        is_async = return_type.startswith("Future")

        method_doc_match = re.search(
            r"(///[^\n]*(?:\n\s*///[^\n]*)*|/\*\*.*?\*/)\s*$",
            class_block[: m.start()],
            re.DOTALL,
        )
        method_doc = _clean_docstring(method_doc_match) if method_doc_match else ""

        if method_name in seen:
            continue
        if skip_filter and _should_skip_method(method_name, method_doc):
            continue
        seen.add(method_name)

        safe_name = method_name
        if keyword.iskeyword(method_name):
            safe_name = method_name + "_"

        parsed_params = _parse_params_string(params_raw)

        methods.append(
            DartMethod(
                name=safe_name,
                return_type=return_type if not is_setter else "void",
                params=parsed_params,
                docstring=method_doc,
                is_static=is_static,
                is_getter=is_getter,
                is_setter=is_setter,
                is_async=is_async,
            )
        )

    # Parse bare getters without parentheses: `Type get name { ... }` or `Type get name =>`
    getter_matches = re.finditer(
        r"(?:@[^\n]*\n)*"
        r"(static\s+)?"
        r"(Future<.*?>|String|bool|int|double|dynamic|Map<.*?>|List<.*?>|\w+\??)\s+"
        r"get\s+(\w+)\s*(?:\{|=>)",
        class_block,
    )
    for m in getter_matches:
        if _is_inside_comment(class_block, m.start()):
            continue

        is_static = m.group(1) is not None
        return_type = m.group(2)
        getter_name = m.group(3)

        if getter_name in seen:
            continue

        method_doc_match = re.search(
            r"(///[^\n]*(?:\n\s*///[^\n]*)*|/\*\*.*?\*/)\s*$",
            class_block[: m.start()],
            re.DOTALL,
        )
        method_doc = _clean_docstring(method_doc_match) if method_doc_match else ""

        if skip_filter and _should_skip_method(getter_name, method_doc):
            continue
        seen.add(getter_name)

        methods.append(
            DartMethod(
                name=getter_name,
                return_type=return_type,
                params=[],
                docstring=method_doc,
                is_static=is_static,
                is_getter=True,
                is_async=return_type.startswith("Future"),
            )
        )

    # Parse instance fields (only for helper/data classes — skip_filter=False).
    # Matches: `late? Type? fieldName;` or `Type? fieldName = default;`
    if not skip_filter:
        field_matches = re.finditer(
            r"(?:///[^\n]*\n\s*)*"
            r"(late\s+)?"
            r"((?:final\s+)?)"
            r"(String|bool|int|double|Map<[^>]*>|List<[^>]*>|[A-Z]\w*)"
            r"(\??)[ \t]+"
            r"(\w+)"
            r"\s*(?:=[^;]*)?;",
            class_block,
        )
        for m in field_matches:
            if _is_inside_comment(class_block, m.start()):
                continue
            field_type = m.group(3) + (m.group(4) or "")
            field_name = m.group(5)
            if field_name in seen or field_name.startswith("_"):
                continue
            seen.add(field_name)

            # Extract docstring for the field
            field_doc_match = re.search(
                r"(///[^\n]*(?:\n\s*///[^\n]*)*)\s*$",
                class_block[: m.start()],
            )
            field_doc = _clean_docstring(field_doc_match) if field_doc_match else ""

            methods.append(
                DartMethod(
                    name=field_name,
                    return_type=field_type,
                    params=[],
                    docstring=field_doc,
                    is_getter=True,
                    is_async=False,
                )
            )

    if skip_filter:
        methods = [
            m for m in methods if not _should_skip_method(m.name, m.docstring or "")
        ]

    return methods


# ---------------------------------------------------------------------------
# Main parse functions
# ---------------------------------------------------------------------------


def parse_dart_package_api(package_path: Path, strict: bool = False) -> DartPackageAPI:
    """Parse a Dart package and return a structured DartPackageAPI.

    Args:
        package_path: Path to the extracted Flutter package root.
        strict: If True, only include classes with 2+ public methods.

    Returns:
        DartPackageAPI with parsed classes, enums, helper classes, and typedefs.
    """
    lib_dir = package_path / "lib"
    if not lib_dir.exists():
        raise FileNotFoundError(f"Directory {lib_dir} does not exist.")

    all_classes: list[DartClass] = []
    all_enums: list[DartEnum] = []
    all_helpers: list[DartClass] = []
    all_typedefs: dict[str, str] = {}

    for dart_file in lib_dir.rglob("*.dart"):
        content = dart_file.read_text(encoding="utf-8")
        relative_path = str(dart_file.relative_to(lib_dir))

        # Parse typedefs
        all_typedefs.update(_parse_typedefs(content))

        # Parse enums
        all_enums.extend(_parse_enums(content))

        # Parse classes
        class_matches = re.finditer(
            r"(?:@[^\n]*\n)*"
            r"(?:abstract\s+)?class\s+(\w+)"
            r"(?:\s+extends\s+(\w+))?"
            r"(?:\s+with\s+[\w\s,]+)?"
            r"(?:\s+implements\s+[\w\s,]+)?"
            r"\s*\{",
            content,
        )

        for match in class_matches:
            class_name = match.group(1)
            parent_class = match.group(2) or ""

            doc_match = re.search(
                r"(///.*?$|/\*\*(.*?)\*/)",
                content[: match.start()],
                re.DOTALL | re.MULTILINE,
            )
            class_doc = _clean_docstring(doc_match) if doc_match else ""

            class_block = _extract_code_block(content[match.end() - 1 :])
            if not class_block:
                continue

            # Helper classes (Event, Data, Result, State, etc.) or data model classes
            if _is_helper_class(class_name, parent_class):
                helper_methods = _parse_class_methods(class_block, skip_filter=False)
                all_helpers.append(
                    DartClass(
                        name=class_name,
                        methods=helper_methods,
                        docstring=class_doc,
                        parent_class=parent_class,
                        source_file=relative_path,
                    )
                )
                continue

            if _should_skip_class(class_name, class_doc, parent_class):
                continue

            methods = _parse_class_methods(class_block, skip_filter=True)

            if strict and len(methods) < 2:
                continue

            if methods:
                all_classes.append(
                    DartClass(
                        name=class_name,
                        methods=methods,
                        docstring=class_doc,
                        parent_class=parent_class,
                        source_file=relative_path,
                    )
                )

    return DartPackageAPI(
        classes=all_classes,
        enums=all_enums,
        helper_classes=all_helpers,
        typedefs=all_typedefs,
    )


# ---------------------------------------------------------------------------
# Legacy compatibility
# ---------------------------------------------------------------------------


def parse_dart_package(package_path: Path, strict: bool = False) -> dict[str, Any]:
    """Parse a Dart package into a dict (legacy format).

    This function is kept for backward compatibility with existing tests.
    New code should use ``parse_dart_package_api()`` instead.
    """
    api = parse_dart_package_api(package_path, strict=strict)
    result: dict[str, Any] = {}
    for cls in api.classes:
        methods_list: list[dict[str, Any]] = []
        for method in cls.methods:
            params = []
            for p in method.params:
                param_str = (
                    f"{p.dart_type} {p.name}" if p.dart_type != "dynamic" else p.name
                )
                params.append(param_str)
            methods_list.append(
                {
                    "name": method.name,
                    "return_type": method.return_type,
                    "params": params,
                    "docstring": method.docstring,
                    "is_getter": method.is_getter,
                    "is_setter": method.is_setter,
                }
            )
        result[cls.name] = {
            "methods": methods_list,
            "docstring": cls.docstring,
            "source_file": cls.source_file,
        }
    return result


def dart_api_to_template_context(api_info: dict[str, Any]) -> dict[str, Any]:
    """Convert parsed API info to template context (legacy adapter)."""
    methods = []
    for class_name, class_info in api_info.items():
        for method in class_info["methods"]:
            python_params = []
            dart_args = {}
            for p in method["params"]:
                parts = p.strip().split()
                param_name = parts[-1] if parts else p
                python_params.append(param_name)
                dart_args[param_name] = param_name

            methods.append(
                {
                    "name": camel_to_snake(method["name"]),
                    "dart_name": method["name"],
                    "python_params": python_params,
                    "dart_args": dart_args,
                    "docstring": method.get("docstring", ""),
                    "is_getter": method.get("is_getter", False),
                    "is_setter": method.get("is_setter", False),
                    "source_class": class_name,
                }
            )
    return {"parsed_methods": methods}
