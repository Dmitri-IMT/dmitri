from __future__ import annotations

from typing import Protocol

from api.services.ai.schemas import ScanAIAnalysis, ScanAIContext


class AIProvider(Protocol):
    """Provider boundary; business logic does not depend on a vendor SDK."""

    def analyze_scan(self, context: ScanAIContext) -> ScanAIAnalysis: ...
