"""Local attack-surface and machine-profile assessment."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .analyzer import AssessmentResult, assess_hosts

__all__ = ["AssessmentResult", "assess_hosts"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import analyzer

        return getattr(analyzer, name)
    raise AttributeError(name)
