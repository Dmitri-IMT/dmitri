from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

MAX_DEVICE_STRING_CHARS = 128
MAX_IDENTIFICATION_OBJECTS = 16
MAX_IDENTIFICATION_SOURCES = 8
MAX_ADDRESS_RANGES_PER_UNIT = 32

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def bound_text(value: str | None) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    cleaned = _CONTROL_CHARS.sub("", value)
    if len(cleaned) <= MAX_DEVICE_STRING_CHARS:
        return cleaned, False
    return cleaned[:MAX_DEVICE_STRING_CHARS], True


def bound_objects(objects: Mapping[str, Any]) -> tuple[dict[str, str], bool]:
    numeric: list[tuple[int, str, Any]] = []
    other: list[tuple[str, Any]] = []
    for key, raw_value in objects.items():
        try:
            numeric.append((int(key), str(key), raw_value))
        except (TypeError, ValueError):
            other.append((str(key), raw_value))
    numeric.sort(key=lambda item: item[0])
    ordered: list[tuple[str, Any]] = [
        (key, value) for _, key, value in numeric
    ] + other
    truncated = len(ordered) > MAX_IDENTIFICATION_OBJECTS
    selected = ordered[:MAX_IDENTIFICATION_OBJECTS]
    result: dict[str, str] = {}
    for key, raw_value in selected:
        text = str(raw_value) if raw_value is not None else ""
        bounded, cut = bound_text(text)
        if bounded is not None:
            result[key] = bounded
        truncated = truncated or cut
    return result, truncated


def bound_sources(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= MAX_IDENTIFICATION_SOURCES:
            break
    return result
