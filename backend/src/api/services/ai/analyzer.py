from __future__ import annotations

from api.services.ai.provider import AIProvider
from api.services.ai.schemas import ScanAIAnalysis, ScanAIContext
from api.services.ai.validation import validate_scan_analysis


def generate_scan_analysis(
    provider: AIProvider,
    context: ScanAIContext,
) -> ScanAIAnalysis:
    analysis = provider.analyze_scan(context)
    validate_scan_analysis(context, analysis)
    return analysis
