"""Recursive dataclass-to-JSON-safe dict converter."""

from __future__ import annotations

import dataclasses
from enum import Enum
from pathlib import Path


def to_dict(obj: object) -> object:
    """Recursively convert dataclass/Path/Enum/tuple to JSON-safe dict."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_dict(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, tuple):
        return [to_dict(item) for item in obj]
    if isinstance(obj, list):
        return [to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj
