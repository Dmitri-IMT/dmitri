"""Unit tests for the scan error taxonomy and package re-exports."""

from __future__ import annotations

import pytest
from agent.scanner import (
    BudgetExceeded,
    CircuitBreakerError,
    FatalScanError,
    ScanError,
    TransientScanError,
    UnitScanError,
)
from agent.tui.scanner import ScanCancelled


class TestScanErrorSubclasses:
    def test_fatal_subclasses_scan_error(self) -> None:
        assert issubclass(FatalScanError, ScanError)
        assert issubclass(FatalScanError, Exception)

    def test_unit_subclasses_scan_error(self) -> None:
        assert issubclass(UnitScanError, ScanError)
        assert issubclass(UnitScanError, Exception)

    def test_transient_subclasses_scan_error(self) -> None:
        assert issubclass(TransientScanError, ScanError)
        assert issubclass(TransientScanError, Exception)

    def test_budget_subclasses_scan_error(self) -> None:
        assert issubclass(BudgetExceeded, ScanError)
        assert issubclass(BudgetExceeded, Exception)


class TestCircuitBreaker:
    def test_subclasses_budget_exceeded(self) -> None:
        assert issubclass(CircuitBreakerError, BudgetExceeded)
        assert issubclass(CircuitBreakerError, ScanError)

    def test_caught_as_budget_exceeded(self) -> None:
        with pytest.raises(BudgetExceeded):
            raise CircuitBreakerError()


class TestScanCancelled:
    def test_subclasses_scan_error(self) -> None:
        assert issubclass(ScanCancelled, ScanError)

    def test_caught_as_scan_error(self) -> None:
        with pytest.raises(ScanError):
            raise ScanCancelled()


class TestPackageReexports:
    def test_taxonomy_importable_from_package(self) -> None:
        import agent.scanner as scanner

        for cls in (
            ScanError,
            FatalScanError,
            UnitScanError,
            TransientScanError,
            BudgetExceeded,
            CircuitBreakerError,
        ):
            assert getattr(scanner, cls.__name__) is cls

    def test_nmap_execution_error_not_reexported(self) -> None:
        import agent.scanner as scanner

        assert not hasattr(scanner, "NmapExecutionError")
