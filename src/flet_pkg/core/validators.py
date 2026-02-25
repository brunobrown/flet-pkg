import re
from dataclasses import dataclass


@dataclass
class DerivedNames:
    project_name: str
    package_name: str
    control_name: str
    control_name_snake: str


def validate_package_name(name: str) -> str | None:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        return "Must be a valid Python identifier: lowercase, underscores, starts with letter."
    return None


def validate_project_name(name: str) -> str | None:
    if not re.fullmatch(r"[a-z][a-z0-9\-]*", name):
        return "Must be lowercase letters, digits, and hyphens. Starts with letter."
    return None


def validate_flutter_package(name: str) -> str | None:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        return "Must be a valid pub.dev package name: lowercase, underscores, starts with letter."
    return None


def validate_control_name(name: str) -> str | None:
    if not re.fullmatch(r"[A-Z][a-zA-Z0-9]*", name):
        return "Must be PascalCase: starts with uppercase letter, alphanumeric."
    return None


def _camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _strip_flutter_affixes(name: str) -> str:
    for suffix in ("_flutter", "_plus", "_pro"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    for prefix in ("flutter_",):
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _derive_control_name(core: str) -> str:
    parts = core.split("_")
    return "".join(p.capitalize() for p in parts)


def derive_names(flutter_package: str) -> DerivedNames:
    core = _strip_flutter_affixes(flutter_package)
    control_name = _derive_control_name(core)
    return DerivedNames(
        project_name=f"flet-{core.replace('_', '-')}",
        package_name=f"flet_{core}",
        control_name=control_name,
        control_name_snake=_camel_to_snake(control_name).lower(),
    )
