from __future__ import annotations


class ScanError(Exception):
    pass


class FatalScanError(ScanError):
    pass


class UnitScanError(ScanError):
    pass


class TransientScanError(ScanError):
    pass


class ScanCancelled(ScanError):
    pass


class BudgetExceeded(ScanError):
    pass


class CircuitBreakerError(BudgetExceeded):
    pass


class UnsupportedScanDepth(FatalScanError):
    def __init__(self, refused_depth: str) -> None:
        self.refused_depth = refused_depth
        super().__init__(f"Unsupported scan depth: {refused_depth}")
