"""Name validation and derivation utilities.

Provides validators for Flutter package names, Python package names,
project names, and control class names. Also derives a consistent set
of names from a Flutter package name.
"""

import re
from dataclasses import dataclass


@dataclass
class DerivedNames:
    """Set of names derived from a Flutter package name.

    Attributes:
        project_name: Hyphenated project name (e.g. ``flet-onesignal``).
        package_name: Python package name (e.g. ``flet_onesignal``).
        control_name: PascalCase control class name (e.g. ``Onesignal``).
        control_name_snake: Snake-case control name (e.g. ``onesignal``).
    """
    project_name: str
    package_name: str
    control_name: str
    control_name_snake: str


def validate_package_name(name: str) -> str | None:
    """Validate a Python package name. Returns an error message or ``None``."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        return "Must be a valid Python identifier: lowercase, underscores, starts with letter."
    return None


def validate_project_name(name: str) -> str | None:
    """Validate a project name (lowercase + hyphens). Returns an error message or ``None``."""
    if not re.fullmatch(r"[a-z][a-z0-9\-]*", name):
        return "Must be lowercase letters, digits, and hyphens. Starts with letter."
    return None


def validate_flutter_package(name: str) -> str | None:
    """Validate a pub.dev package name. Returns an error message or ``None``."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        return "Must be a valid pub.dev package name: lowercase, underscores, starts with letter."
    return None


def validate_control_name(name: str) -> str | None:
    """Validate a PascalCase control class name. Returns an error message or ``None``."""
    if not re.fullmatch(r"[A-Z][a-zA-Z0-9]*", name):
        return "Must be PascalCase: starts with uppercase letter, alphanumeric."
    return None


def _camel_to_snake(name: str) -> str:
    """Convert a PascalCase or camelCase string to snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _strip_flutter_affixes(name: str) -> str:
    """Remove common Flutter suffixes/prefixes (``_flutter``, ``flutter_``, etc.)."""
    for suffix in ("_flutter", "_plus", "_pro"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    for prefix in ("flutter_",):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _derive_control_name(core: str) -> str:
    """Convert a snake_case core name to PascalCase."""
    parts = core.split("_")
    return "".join(p.capitalize() for p in parts)


def derive_names(flutter_package: str) -> DerivedNames:
    """Derive project, package, and control names from a Flutter package name.

    Args:
        flutter_package: A pub.dev package name (e.g. ``onesignal_flutter``).

    Returns:
        A ``DerivedNames`` instance with all derived names.
    """
    core = _strip_flutter_affixes(flutter_package)
    control_name = _derive_control_name(core)
    return DerivedNames(
        project_name=f"flet-{core.replace('_', '-')}",
        package_name=f"flet_{core}",
        control_name=control_name,
        control_name_snake=_camel_to_snake(control_name).lower(),
    )
