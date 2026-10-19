from __future__ import annotations

from typing import Protocol, runtime_checkable

from api.schemas.ai import (
    ProviderScanAIAnalysis,
    ProviderScanAIChildAnalysis,
)
from api.services.ai.context import ScanAIContext


@runtime_checkable
class ScanAnalysisProvider(Protocol):
    def analyze_scan(
        self, context: ScanAIContext, *, language: str = "en"
    ) -> ProviderScanAIAnalysis: ...

    def repair_analysis(
        self,
        context: ScanAIContext,
        violation_codes: tuple[str, ...],
        *,
        language: str = "en",
    ) -> ProviderScanAIAnalysis: ...


@runtime_checkable
class BoundedScanAnalysisProvider(ScanAnalysisProvider, Protocol):
    def analyze_chunk(
        self, context: ScanAIContext, *, language: str = "en"
    ) -> ProviderScanAIChildAnalysis: ...

    def repair_chunk(
        self,
        context: ScanAIContext,
        violation_codes: tuple[str, ...],
        *,
        language: str = "en",
    ) -> ProviderScanAIChildAnalysis: ...

    def synthesize_scan(
        self,
        context: ScanAIContext,
        child_results: list[dict[str, object]],
        failed_refs: tuple[str, ...],
        *,
        language: str = "en",
    ) -> ProviderScanAIAnalysis: ...


def supports_bounded_scan_analysis(provider: object) -> bool:
    return isinstance(provider, BoundedScanAnalysisProvider)
