from __future__ import annotations

import pytest
from agent.config import AgentSettings, deep_stage_scripts
from agent.scanner.stages import nmap_arguments_summary


class TestNmapArgumentsSummary:
    def test_extensive_uses_top_ports_no_port_stage_script(self) -> None:
        summary = nmap_arguments_summary(AgentSettings(scan_mode="extensive"))
        assert "ports=-Pn -n -T4 -O --top-ports 10000" in summary

    def test_max_uses_all_ports_min_rate(self) -> None:
        summary = nmap_arguments_summary(AgentSettings(scan_mode="max"))
        assert "ports=-Pn -n -T4 -O -p- --min-rate 1000" in summary

    def test_quick_port_stage_is_enumeration_only(self) -> None:
        summary = nmap_arguments_summary(AgentSettings(scan_mode="quick"))
        assert "ports=-Pn -n -T4 -O" in summary

    def test_standard_port_stage_is_enumeration_only(self) -> None:
        summary = nmap_arguments_summary(AgentSettings(scan_mode="standard"))
        port_summary = summary.split("ports=", 1)[1].split("; deep_inspection=", 1)[0]
        assert "-sV" not in port_summary
        assert "--script" not in port_summary

    def test_nspi_port_stage_describes_both_passes(self) -> None:
        summary = nmap_arguments_summary(AgentSettings(scan_mode="nspi"))
        assert "pass1:-Pn -T4" in summary
        assert "pass2:-Pn -T2 -n -p 502,4840,44818,445,139,3389,5985" in summary
        port_summary = summary.split("ports=", 1)[1].split("; deep_inspection=", 1)[0]
        assert "--script" not in port_summary
        assert (
            "deep_inspection=-Pn -n -T4 -sV --version-intensity 7 -O "
            "--script-timeout 60s --host-timeout 300s"
        ) in summary


@pytest.mark.parametrize("scan_mode", ("quick", "standard", "extensive", "max"))
def test_regular_summary_has_one_enrichment_authority(scan_mode: str) -> None:
    summary = nmap_arguments_summary(AgentSettings(scan_mode=scan_mode))
    port_summary, deep_summary = summary.split("; deep_inspection=", maxsplit=1)

    assert "-sV" not in port_summary
    assert "--script" not in port_summary
    assert deep_summary.count("-sV") == 1
    assert f"scripts={','.join(deep_stage_scripts(scan_mode))}" in deep_summary


def test_summary_honors_intensity_above_preservation_floor() -> None:
    summary = nmap_arguments_summary(
        AgentSettings(scan_mode="standard", version_intensity=9)
    )
    assert "deep_inspection=-Pn -n -T4 -sV --version-intensity 9" in summary
