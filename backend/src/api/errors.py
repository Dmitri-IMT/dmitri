from __future__ import annotations

from collections.abc import Sequence

from fastapi import HTTPException

DEFAULT_CODES_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    410: "gone",
}

# The first `loc` segment names where the error came from, not a field. The contract's
# published example (`hosts[0].ip`) drops it.
_LOCATION_PREFIXES = frozenset({"body", "query", "path", "header", "cookie"})


class ApiError(HTTPException):
    def __init__(self, status_code: int, detail: str, *, code: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def error_envelope(
    code: str, message: str, details: dict | None = None
) -> dict[str, dict]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def field_path(loc: Sequence[str | int]) -> str:
    segments = list(loc)
    if segments and segments[0] in _LOCATION_PREFIXES:
        segments = segments[1:]
    out = ""
    for segment in segments:
        if isinstance(segment, int):
            out += f"[{segment}]"
        else:
            out += f".{segment}" if out else str(segment)
    return out
