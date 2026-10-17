"""Unit tests for the authoritative deep-enrichment policy."""

from __future__ import annotations

from agent.config import (
    EXTENSIVE_NSE_SCRIPTS,
    NSPI_NSE_SCRIPTS,
    QUICK_NSE_SCRIPTS,
    STANDARD_NSE_SCRIPTS,
    deep_stage_scripts,
    effective_version_intensity,
    min_cvss_for_mode,
)


class TestDeepStageScripts:
    def test_catalogs_are_unchanged_and_selected_only_for_deep_stage(self) -> None:
        assert QUICK_NSE_SCRIPTS == ("vulners",)
        assert STANDARD_NSE_SCRIPTS == (
            "vulners",
            "smb-protocols",
            "smb2-security-mode",
            "ssh-auth-methods",
            "http-title",
            "http-server-header",
        )
        assert EXTENSIVE_NSE_SCRIPTS == (
            *STANDARD_NSE_SCRIPTS,
            "ssl-cert",
            "ssl-enum-ciphers",
            "http-methods",
            "ftp-anon",
            "banner",
        )
        assert NSPI_NSE_SCRIPTS == (
            "modbus-discover",
            "enip-info",
            "smb-protocols",
            "smb2-security-mode",
            "smb-security-mode",
            "smb-vuln-ms17-010",
            "smb-enum-shares",
            "rdp-enum-encryption",
            "ssh-auth-methods",
            "ssh2-enum-algos",
            "ssl-cert",
            "ssl-enum-ciphers",
            "http-title",
            "vulners",
        )

        assert deep_stage_scripts("quick") == QUICK_NSE_SCRIPTS
        assert deep_stage_scripts("standard") == STANDARD_NSE_SCRIPTS
        assert deep_stage_scripts("extensive") == EXTENSIVE_NSE_SCRIPTS
        assert deep_stage_scripts("max") == EXTENSIVE_NSE_SCRIPTS
        assert deep_stage_scripts("nspi") == NSPI_NSE_SCRIPTS


class TestEffectiveVersionIntensity:
    def test_values_below_former_implicit_depth_are_raised_to_seven(self) -> None:
        assert effective_version_intensity(0) == 7
        assert effective_version_intensity(5) == 7

    def test_values_at_or_above_seven_are_honored(self) -> None:
        assert effective_version_intensity(7) == 7
        assert effective_version_intensity(9) == 9


class TestMinCvssForMode:
    def test_extensive_lowers_to_three(self) -> None:
        assert min_cvss_for_mode("extensive") == 3.0

    def test_max_lowers_to_one(self) -> None:
        assert min_cvss_for_mode("max") == 1.0

    def test_other_modes_stay_at_five(self) -> None:
        for mode in ("quick", "standard", "nspi"):
            assert min_cvss_for_mode(mode) == 5.0
