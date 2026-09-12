"""Safe display of untrusted device text for Rich markup."""

from __future__ import annotations

import re

from rich.markup import escape

_ELLIPSIS = "…"
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

LIMIT_IDENTIFICATION = 48
LIMIT_OBJECT_KEY = 24
LIMIT_OBJECT_VALUE = 48
LIMIT_RANGE_LABEL = 48
LIMIT_UNIT_ERROR = 80
LIMIT_PORT_TEXT = 64
LIMIT_HOST_TEXT = 64
LIMIT_MAPPING_SOURCE = 32
MAX_OBJECTS_SHOWN = 8
MAX_CPES_SHOWN = 8


class ShortenTracker:
    """Counts device values shortened for the scan-view notice."""

    def __init__(self) -> None:
        self.count = 0


def safe(
    value: object,
    limit: int | None = None,
    *,
    tracker: ShortenTracker | None = None,
) -> str:
    """Escape Rich markup and bound untrusted device text for display."""
    text = _CONTROL_CHARS.sub("·", "" if value is None else str(value))
    if limit is not None and len(text) > limit:
        if limit <= len(_ELLIPSIS):
            text = _ELLIPSIS[:limit]
        else:
            text = text[: limit - len(_ELLIPSIS)] + _ELLIPSIS
        if tracker is not None:
            tracker.count += 1
    return escape(text)
