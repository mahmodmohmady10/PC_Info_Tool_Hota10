from __future__ import annotations

from typing import Any
from core.data_models import CollectionResult


def gb(value: Any) -> str | None:
    try:
        number = float(value)
        if number < 0:
            return None
        return f"{number / (1024 ** 3):.2f} GB"
    except (TypeError, ValueError):
        return None


def set_cim_error(result: CollectionResult, error: str | None, source: str = "Windows CIM") -> None:
    if error:
        result.errors.append(error)
