from __future__ import annotations


class ScanError(Exception):
    pass


class FatalScanError(ScanError):
    pass


class UnitScanError(ScanError):
    pass


class TransientScanError(ScanError):
    pass


class BudgetExceeded(ScanError):
    pass


class CircuitBreakerError(BudgetExceeded):
    pass
