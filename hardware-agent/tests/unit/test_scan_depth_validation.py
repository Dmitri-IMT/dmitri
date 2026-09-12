from __future__ import annotations

import pytest
from agent import config
from agent.scanner.errors import UnsupportedScanDepth
from agent.scanner.runner import ScanRunner


class TestValidateNspiDepth:
    def test_inventory_with_nspi_mode_is_allowed(self) -> None:
        config.validate_nspi_depth("nspi", "inventory")

    def test_read_only_mapping_with_nspi_mode_is_allowed(self) -> None:
        config.validate_nspi_depth("nspi", "read_only_mapping")

    def test_active_validation_is_refused(self) -> None:
        with pytest.raises(UnsupportedScanDepth) as exc_info:
            config.validate_nspi_depth("nspi", "active_validation")
        assert exc_info.value.refused_depth == "active_validation"

    def test_submode_with_non_nspi_mode_is_refused(self) -> None:
        with pytest.raises(UnsupportedScanDepth) as exc_info:
            config.validate_nspi_depth("quick", "read_only_mapping")
        assert exc_info.value.refused_depth == "read_only_mapping"

    def test_default_submode_with_non_nspi_mode_is_allowed(self) -> None:
        config.validate_nspi_depth("standard", "inventory")

    def test_unknown_submode_with_nspi_mode_is_refused(self) -> None:
        with pytest.raises(UnsupportedScanDepth) as exc_info:
            config.validate_nspi_depth("nspi", "unknown")  # type: ignore[arg-type]
        assert exc_info.value.refused_depth == "unknown"


class TestScanRunnerConstructor:
    def test_refuses_active_validation_before_state_is_built(self) -> None:
        with pytest.raises(UnsupportedScanDepth):
            ScanRunner(
                subnet="192.168.1.0/24",
                scan_mode="nspi",
                nspi_submode="active_validation",
            )

    def test_refuses_submode_with_non_nspi_mode(self) -> None:
        with pytest.raises(UnsupportedScanDepth):
            ScanRunner(
                subnet="192.168.1.0/24",
                scan_mode="quick",
                nspi_submode="read_only_mapping",
            )
