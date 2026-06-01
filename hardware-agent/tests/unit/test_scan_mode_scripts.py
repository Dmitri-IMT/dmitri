"""Unit tests for central mode→scripts helpers and deep-stage script scoping."""

from __future__ import annotations

from agent.config import (
    EXTENSIVE_NSE_SCRIPTS,
    STANDARD_NSE_SCRIPTS,
    deep_stage_scripts,
    min_cvss_for_mode,
    port_stage_scripts,
)

STANDARD_SCRIPT_CSV = (
    "vulners,smb-protocols,smb2-security-mode,"
    "ssh-auth-methods,http-title,http-server-header"
)


class TestPortStageScripts:
    def test_quick_returns_vulners_only(self) -> None:
        assert port_stage_scripts("quick") == "vulners"

    def test_standard_returns_contract_csv(self) -> None:
        assert port_stage_scripts("standard") == STANDARD_SCRIPT_CSV


class TestDeepStageScripts:
    def test_quick_returns_vulners_only(self) -> None:
        assert deep_stage_scripts("quick") == ("vulners",)

    def test_standard_returns_six_tuple(self) -> None:
        result = deep_stage_scripts("standard")
        assert result == STANDARD_NSE_SCRIPTS
        assert len(result) == 6

    def test_max_returns_extensive_set(self) -> None:
        assert deep_stage_scripts("max") == EXTENSIVE_NSE_SCRIPTS


class TestExtensiveScripts:
    def test_extensive_deep_returns_extensive_set(self) -> None:
        result = deep_stage_scripts("extensive")
        assert result == EXTENSIVE_NSE_SCRIPTS
        assert len(result) == 11

    def test_extensive_excludes_snmp_info(self) -> None:
        assert "snmp-info" not in EXTENSIVE_NSE_SCRIPTS

    def test_extensive_is_superset_of_standard(self) -> None:
        assert set(STANDARD_NSE_SCRIPTS).issubset(set(EXTENSIVE_NSE_SCRIPTS))
        added = set(EXTENSIVE_NSE_SCRIPTS) - set(STANDARD_NSE_SCRIPTS)
        assert added == {
            "ssl-cert",
            "ssl-enum-ciphers",
            "http-methods",
            "ftp-anon",
            "banner",
        }


class TestMinCvssForMode:
    def test_extensive_lowers_to_three(self) -> None:
        assert min_cvss_for_mode("extensive") == 3.0

    def test_max_lowers_to_one(self) -> None:
        assert min_cvss_for_mode("max") == 1.0

    def test_other_modes_stay_at_five(self) -> None:
        for mode in ("quick", "standard", "nspi"):
            assert min_cvss_for_mode(mode) == 5.0
