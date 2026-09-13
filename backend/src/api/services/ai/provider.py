from __future__ import annotations

from typing import Protocol

from api.services.ai.schemas import ScanAIAnalysis, ScanAIContext


class AIProvider(Protocol):
    def analyze_scan(self, context: ScanAIContext) -> ScanAIAnalysis: ...


class AIProviderError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable
