"""
Dart source code parser.

Parses Dart package source files to extract classes, methods, enums,
and their metadata into structured ``DartPackageAPI`` models.
"""

from __future__ import annotations

import keyword
import re
from pathlib import Path

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
    "Plugin",
    "ServiceAPIPrivateImpl",
    "Utils",
    "Painter",
    "Positioned",
)

# Parent classes that indicate a platform implementation (not a public API).
# Classes extending these are skipped entirely.
PLATFORM_IMPL_BASES = (
    "Platform",
    "PlatformInterface",
    "MethodChannelPlatform",
)

# Parent classes that indicate internal rendering/painting implementations.
_INTERNAL_PARENT_BASES = (
    "CustomPainter",
    "BoxBorder",
    "BoxDecoration",
    "Decoration",
    "ShapeBorder",
)

# Parent classes that indicate a Flutter widget (not a service API).
WIDGET_BASES = (
    "StatelessWidget",
    "StatefulWidget",
    "InheritedWidget",
    "RenderObjectWidget",
    "LeafRenderObjectWidget",
    "SingleChildRenderObjectWidget",
    "MultiChildRenderObjectWidget",
)

# Dart types that are Flutter-internal and should NOT become Flet properties.
_WIDGET_INTERNAL_TYPES = {
    "Key",
    "Widget",
    "BuildContext",
    "GlobalKey",
    "ValueKey",
    "ObjectKey",
    "UniqueKey",
    "PageStorageKey",
    "LocalKey",
    "Animation",
    "AnimationController",
    "TickerProvider",
    "ScrollController",
    "FocusNode",
    "TextEditingController",
}

# Classes ending with these are parsed into helper_classes (not skipped entirely).
# Used for event field extraction, type resolution, and config data classes.
HELPER_CLASS_SUFFIXES = (
    "Event",
    "Data",
    "Result",
    "State",
    "ChangedState",
    "ClickResult",
    "Button",
    "Layout",
    "Configuration",
    "Config",
    "Options",
    "Params",
    "Info",
    "Style",
    "Position",
    "Gradient",
    "Animation",
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
        or _is_platform_impl(parent_class)
        or parent_class in WIDGET_BASES
        or parent_class in _INTERNAL_PARENT_BASES
    )


def _is_platform_impl(parent_class: str) -> bool:
    """Check if a parent class indicates a platform implementation."""
    if not parent_class:
        return False
    # Direct match or ends with a known platform base suffix
    return parent_class.endswith(PLATFORM_IMPL_BASES)


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


def _should_skip_method(
    method_name: str,
    docstring: str = "",
    return_type: str = "",
) -> bool:
    return (
        method_name in UI_METHODS
        or method_name in LIFECYCLE_METHODS
        or method_name.startswith("_")
        # Skip on* methods UNLESS they are Stream getters (event sources)
        or (method_name.startswith("on") and not return_type.startswith("Stream"))
        or "nodoc" in docstring.lower()
        or not method_name.isidentifier()
        or method_name[0].isupper()
    )


def _is_inside_comment(text: str, pos: int) -> bool:
    """Check if *pos* falls inside a ``//`` or ``///`` comment."""
    line_start = text.rfind("\n", 0, pos) + 1
    line_prefix = text[line_start:pos]
    return "//" in line_prefix


def _is_inside_string(text: str, pos: int) -> bool:
    """Check if *pos* falls inside a string literal (single or double quoted)."""
    # Scan from the last newline to pos, counting unescaped quotes
    line_start = text.rfind("\n", 0, pos) + 1
    line = text[line_start:pos]
    in_single = False
    in_double = False
    i = 0
    while i < len(line):
        c = line[i]
        if c == "\\" and (in_single or in_double):
            i += 2
            continue
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        i += 1
    return in_single or in_double


def _extract_balanced_parens(text: str, open_pos: int) -> str | None:
    """Extract content between balanced parentheses starting at *open_pos*.

    ``text[open_pos]`` must be ``(``.  Returns the text between the outer
    parens (exclusive) or ``None`` if unbalanced.
    """
    if open_pos >= len(text) or text[open_pos] != "(":
        return None
    depth = 1
    i = open_pos + 1
    length = len(text)
    while i < length:
        c = text[i]
        # Skip string literals (single and double quotes)
        if c in ("'", '"'):
            quote = c
            i += 1
            while i < length and text[i] != quote:
                if text[i] == "\\":
                    i += 1  # skip escaped char
                i += 1
            i += 1  # skip closing quote
            continue
        # Skip line comments
        if c == "/" and i + 1 < length and text[i + 1] == "/":
            i = text.find("\n", i)
            if i == -1:
                break
            i += 1
            continue
        # Skip block comments
        if c == "/" and i + 1 < length and text[i + 1] == "*":
            i = text.find("*/", i + 2)
            if i == -1:
                break
            i += 2
            continue
        # Track nesting for all bracket types
        if c in "(<[":
            depth += 1
        elif c in ")>]":
            depth -= 1
            if depth == 0:
                return text[open_pos + 1 : i]
        i += 1
    return None


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
    # Track nesting depth so that brackets inside default values (e.g.,
    # `const <T>[...]` or `{key: value}`) don't corrupt section markers.
    is_named = False
    is_optional = False
    nesting = 0  # depth inside (), <>, or [] within defaults
    clean = []
    for char in params_raw:
        if nesting == 0:
            if char == "{":
                is_named = True
                # Retroactively mark trailing whitespace as named
                # so that spaces between `,` and `{` don't misclassify
                # the next parameter as positional.
                i = len(clean) - 1
                while i >= 0 and clean[i][0].isspace():
                    clean[i] = (clean[i][0], True, clean[i][2])
                    i -= 1
                continue
            if char == "}":
                is_named = False
                continue
            if char == "[" and not is_named:
                is_optional = True
                continue
            if char == "]" and is_optional and not is_named:
                is_optional = False
                continue
        # Track nesting for all bracket types inside defaults
        if char in "(<[":
            nesting += 1
        elif char in ")>]":
            nesting -= 1
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
        if c in "(<[":
            depth += 1
        elif c in ")>]":
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

        # Parse values: strip doc comments (/// lines) before splitting
        cleaned_body = re.sub(r"[ \t]*///[^\n]*", "", body)
        values = []
        for line in cleaned_body.split(","):
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
# Widget constructor parameter parsing
# ---------------------------------------------------------------------------


def _parse_constructor_params(class_name: str, class_block: str) -> list[DartParam]:
    """Extract constructor parameters from a Dart widget class.

    Builds a field-type map from ``final Type fieldName;`` declarations,
    then finds the primary constructor and resolves ``this.fieldName``
    references to their declared types.

    Skips Flutter-internal types (Widget, Key, etc.) that cannot be
    serialized as Flet control properties.
    """
    # Step 1: Build field type map from `final Type fieldName;` declarations
    field_types: dict[str, str] = {}
    field_docs: dict[str, str] = {}
    for m in re.finditer(
        r"((?:///[^\n]*\n\s*)*)"
        r"(?:late\s+)?(?:final\s+)?"
        r"([\w]+(?:<[^;]*?>)?(?:\?)?)\s+"
        r"(\w+)\s*(?:=[^;]*)?;",
        class_block,
    ):
        doc_lines = m.group(1).strip()
        raw_type = m.group(2).strip()
        field_name = m.group(3)
        if not field_name.startswith("_"):
            field_types[field_name] = raw_type
            if doc_lines:
                field_docs[field_name] = (
                    re.sub(r"///+\s*", "", doc_lines).strip().replace("\n", " ")
                )

    # Step 2: Find the primary constructor
    ctor_re = re.compile(
        r"(?:const\s+)?" + re.escape(class_name) + r"\s*\(",
    )
    ctor_match = ctor_re.search(class_block)
    if not ctor_match:
        return []

    params_raw = _extract_balanced_parens(class_block, ctor_match.end() - 1)
    if params_raw is None:
        return []

    # Strip all comments (// and ///) and template tags ({@...})
    params_raw = re.sub(r"//[^\n]*", "", params_raw)
    params_raw = re.sub(r"\{@\w+[^}]*\}", "", params_raw)

    # Step 3: Parse constructor params (handling this. references)
    result: list[DartParam] = []
    is_named = False

    # Split respecting nesting
    segments: list[tuple[str, bool]] = []
    current: list[str] = []
    depth = 0
    for char in params_raw:
        if depth == 0:
            if char == "{":
                is_named = True
                continue
            if char == "}":
                is_named = False
                continue
        if char in "(<[":
            depth += 1
        elif char in ")>]":
            depth -= 1
        if char == "," and depth == 0:
            segments.append(("".join(current).strip(), is_named))
            current = []
        else:
            current.append(char)
    if current:
        segments.append(("".join(current).strip(), is_named))

    for seg, named in segments:
        seg = seg.strip()
        if not seg:
            continue
        # Strip annotations
        seg = re.sub(r"@\w+(\([^)]*\))?\s*", "", seg).strip()

        required = False
        if seg.startswith("required "):
            required = True
            seg = seg[len("required ") :].strip()

        # Extract default value
        default = None
        # Match default respecting nesting
        eq_depth = 0
        eq_pos = -1
        for i, c in enumerate(seg):
            if c in "(<[":
                eq_depth += 1
            elif c in ")>]":
                eq_depth -= 1
            elif c == "=" and eq_depth == 0:
                eq_pos = i
                break
        if eq_pos >= 0:
            default = seg[eq_pos + 1 :].strip()
            seg = seg[:eq_pos].strip()

        # Handle `this.fieldName` syntax
        this_match = re.match(r"this\.(\w+)$", seg)
        if this_match:
            field_name = this_match.group(1)
            dart_type = field_types.get(field_name, "dynamic")
        else:
            # Explicit type: `Type fieldName`
            parts = seg.split()
            if len(parts) >= 2:
                dart_type = " ".join(parts[:-1])
                field_name = parts[-1]
            elif len(parts) == 1:
                field_name = parts[0]
                dart_type = field_types.get(field_name, "dynamic")
            else:
                continue

        if not field_name.isidentifier():
            continue

        # Skip Flutter-internal types
        base_type = re.sub(r"[?<].*", "", dart_type).strip()
        if base_type in _WIDGET_INTERNAL_TYPES:
            continue

        result.append(
            DartParam(
                name=field_name,
                dart_type=dart_type,
                required=required and default is None,
                named=named,
                default=default,
            )
        )

    return result


# ---------------------------------------------------------------------------
# Class method parsing (shared between main and helper classes)
# ---------------------------------------------------------------------------


def _parse_class_methods(class_block: str, skip_filter: bool = True) -> list[DartMethod]:
    """Parse methods from a class body block."""
    methods: list[DartMethod] = []
    seen: set[str] = set()

    # Parse methods with parentheses: `Type name(params)` or `Type get/set name(params)`
    # Match up to the opening paren, then use balanced extraction for params.
    method_sig_re = re.compile(
        r"(?:@[^\n]*\n)*"
        r"(static\s+)?"
        r"(Future<.*?>|Future|void|String|bool|int|double|dynamic|"
        r"Map<.*?>|List<.*?>|Set<.*?>|\w+(?:\?)?)\s+"
        r"(get\s+|set\s+)?(\w+)"
        r"\s*\(",
    )
    method_matches = method_sig_re.finditer(class_block)

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

        # Extract balanced parameter text from opening paren
        open_pos = m.end() - 1  # position of the '('
        params_raw = _extract_balanced_parens(class_block, open_pos)
        if params_raw is None:
            continue

        is_async = return_type.startswith("Future")

        method_doc_match = re.search(
            r"(///[^\n]*(?:\n\s*///[^\n]*)*|/\*\*.*?\*/)\s*$",
            class_block[: m.start()],
            re.DOTALL,
        )
        method_doc = _clean_docstring(method_doc_match) if method_doc_match else ""

        if method_name in seen:
            continue
        if skip_filter and _should_skip_method(method_name, method_doc, return_type):
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
        r"(Future<.*?>|Stream<.*?>|String|bool|int|double|dynamic|Map<.*?>|List<.*?>|\w+\??)\s+"
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

        if skip_filter and _should_skip_method(getter_name, method_doc, return_type):
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
            m for m in methods if not _should_skip_method(m.name, m.docstring or "", m.return_type)
        ]

    return methods


# ---------------------------------------------------------------------------
# Re-export parsing
# ---------------------------------------------------------------------------


def _parse_reexports(lib_dir: Path) -> dict[str, str]:
    """Parse barrel files to find re-exported public API type names.

    Scans top-level ``export`` directives in ``lib/*.dart`` for
    ``show`` clauses and returns a mapping of symbol name → source package.
    """
    reexports: dict[str, str] = {}
    # Only check top-level dart files in lib/ (barrel files)
    for dart_file in lib_dir.glob("*.dart"):
        content = dart_file.read_text(encoding="utf-8")
        for m in re.finditer(
            r"export\s+['\"]package:([^'\"]+)['\"]"
            r"\s+show\s+([^;]+);",
            content,
        ):
            package_path_str = m.group(1)
            symbols = [s.strip() for s in m.group(2).split(",")]
            package_name = package_path_str.split("/")[0]
            for sym in symbols:
                if sym and sym[0].isupper():
                    reexports[sym] = package_name
    return reexports


# ---------------------------------------------------------------------------
# Top-level function parsing
# ---------------------------------------------------------------------------


def _parse_top_level_functions(
    content: str,
    source_file: str = "",
) -> list[DartMethod]:
    """Parse top-level functions (not inside any class) from Dart source.

    Finds function declarations at the top level of the file and extracts
    their signatures.  Skips private functions (starting with ``_``),
    ``main()``, and functions inside class bodies.
    """
    # Skip files that are clearly internal implementation
    if source_file:
        stem = source_file.rsplit("/", maxsplit=1)[-1].replace(".dart", "")
        if any(stem.endswith(s) for s in ("_conversion", "_internal", "_stub", "_test")):
            return []
    # First, find the spans of all class/enum bodies so we can exclude them
    class_spans: list[tuple[int, int]] = []
    for m in re.finditer(
        r"(?:abstract\s+)?(?:class|enum|mixin|extension)\s+\w+[^{]*\{",
        content,
    ):
        block = _extract_code_block(content[m.end() - 1 :])
        if block is not None:
            class_spans.append((m.start(), m.end() + len(block)))

    def _is_inside_class(pos: int) -> bool:
        return any(start <= pos < end for start, end in class_spans)

    # Match top-level function declarations
    func_re = re.compile(
        r"(?:@[^\n]*\n)*"
        r"(static\s+)?"
        r"(Future<.*?>|Future|void|String|bool|int|double|dynamic|"
        r"Map<.*?>|List<.*?>|Set<.*?>|\w+(?:\?)?)\s+"
        r"(\w+)"
        r"\s*\(",
    )

    functions: list[DartMethod] = []
    seen: set[str] = set()

    # Known valid Dart return types (lowercase) — catches false positives
    # from matches inside string literals.
    _VALID_RETURN_TYPES = {
        "void",
        "int",
        "double",
        "bool",
        "dynamic",
        "num",
        "var",
    }

    for m in func_re.finditer(content):
        if _is_inside_class(m.start()):
            continue
        if _is_inside_comment(content, m.start()):
            continue
        if _is_inside_string(content, m.start()):
            continue

        # Check for @Deprecated or @visibleForTesting annotations
        annotation_text = m.group(0)
        if re.search(r"@[Dd]eprecated|@visibleForTesting", annotation_text):
            continue

        return_type = m.group(2)
        func_name = m.group(3)

        # Skip private, main, and non-identifier names
        if func_name.startswith("_") or func_name == "main":
            continue
        if not func_name.isidentifier() or func_name[0].isupper():
            continue
        if func_name in seen:
            continue
        # Skip known non-function patterns (import, export, etc.)
        if return_type in ("import", "export", "part", "library", "typedef"):
            continue
        # Validate return type: must be a known type or start with uppercase
        if (
            return_type not in _VALID_RETURN_TYPES
            and not return_type[0].isupper()
            and not return_type.startswith("Future")
            and not return_type.startswith("Stream")
            and not return_type.startswith("Map")
            and not return_type.startswith("List")
            and not return_type.startswith("Set")
        ):
            continue

        # Extract balanced params
        open_pos = m.end() - 1
        params_raw = _extract_balanced_parens(content, open_pos)
        if params_raw is None:
            continue

        # Docstring
        doc_match = re.search(
            r"(///[^\n]*(?:\n\s*///[^\n]*)*|/\*\*.*?\*/)\s*$",
            content[: m.start()],
            re.DOTALL,
        )
        func_doc = _clean_docstring(doc_match) if doc_match else ""

        if _should_skip_method(func_name, func_doc):
            continue

        seen.add(func_name)
        parsed_params = _parse_params_string(params_raw)
        is_async = return_type.startswith("Future")

        functions.append(
            DartMethod(
                name=func_name,
                return_type=return_type,
                params=parsed_params,
                docstring=func_doc,
                is_static=False,
                is_getter=False,
                is_setter=False,
                is_async=is_async,
            )
        )

    return functions


# ---------------------------------------------------------------------------
# Main parse functions
# ---------------------------------------------------------------------------


def parse_dart_package_api(
    package_path: Path,
    strict: bool = False,
    include_widgets: bool = False,
) -> DartPackageAPI:
    """Parse a Dart package and return a structured DartPackageAPI.

    Args:
        package_path: Path to the extracted Flutter package root.
        strict: If True, only include classes with 2+ public methods.
        include_widgets: If True, include widget classes and extract their
            constructor parameters. Used for ``ui_control`` extensions where
            widget constructor params become Flet control properties.

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
    all_top_level_functions: list[DartMethod] = []

    for dart_file in lib_dir.rglob("*.dart"):
        content = dart_file.read_text(encoding="utf-8")
        relative_path = str(dart_file.relative_to(lib_dir))

        # Parse typedefs
        all_typedefs.update(_parse_typedefs(content))

        # Parse enums
        all_enums.extend(_parse_enums(content))

        # Parse top-level functions (not inside any class)
        all_top_level_functions.extend(_parse_top_level_functions(content, relative_path))

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

            # Check for @Deprecated annotation on the class
            annotation_text = match.group(0)
            if re.search(r"@[Dd]eprecated", annotation_text):
                continue

            doc_match = re.search(
                r"(///.*?$|/\*\*(.*?)\*/)",
                content[: match.start()],
                re.DOTALL | re.MULTILINE,
            )
            class_doc = _clean_docstring(doc_match) if doc_match else ""

            class_block = _extract_code_block(content[match.end() - 1 :])
            if not class_block:
                continue

            # Skip private, deprecated, internal, and platform impl classes early
            if (
                class_name.startswith("_")
                or "nodoc" in class_doc.lower()
                or "internal" in class_doc.lower()
                or _is_platform_impl(parent_class)
                or parent_class in _INTERNAL_PARENT_BASES
            ):
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

            # Widget classes: include when building ui_control extensions
            is_widget = parent_class in WIDGET_BASES
            if is_widget and include_widgets:
                # Skip widgets with internal-looking suffixes
                if class_name.endswith(UI_CLASS_SUFFIXES):
                    continue
                ctor_params = _parse_constructor_params(class_name, class_block)
                if ctor_params:
                    all_classes.append(
                        DartClass(
                            name=class_name,
                            methods=[],
                            constructor_params=ctor_params,
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

    # Parse re-exported types from barrel files
    reexported = _parse_reexports(lib_dir)

    return DartPackageAPI(
        classes=all_classes,
        enums=all_enums,
        helper_classes=all_helpers,
        typedefs=all_typedefs,
        reexported_types=reexported,
        top_level_functions=all_top_level_functions,
    )
