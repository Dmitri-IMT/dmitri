from __future__ import annotations

from agent.config import AgentSettings
from agent.scanner.stages import nmap_arguments_summary


class TestNmapArgumentsSummary:
    def test_extensive_uses_top_ports_no_port_stage_script(self) -> None:
        summary = nmap_arguments_summary(AgentSettings(scan_mode="extensive"))
        assert "ports=-sV -O --top-ports 10000 -Pn -T4" in summary

    def test_max_uses_all_ports_min_rate(self) -> None:
        summary = nmap_arguments_summary(AgentSettings(scan_mode="max"))
        assert "ports=-sV -O -p- --min-rate 1000 -Pn -T4" in summary

    def test_quick_port_stage_unchanged(self) -> None:
        summary = nmap_arguments_summary(AgentSettings(scan_mode="quick"))
        assert "ports=-sV -O --script vulners -Pn -T4" in summary

    def test_standard_port_stage_unchanged(self) -> None:
        summary = nmap_arguments_summary(AgentSettings(scan_mode="standard"))
        assert "ports=-sV -O --script " in summary
        assert "-Pn -T4" in summary

    def test_nspi_port_stage_describes_both_passes(self) -> None:
        summary = nmap_arguments_summary(AgentSettings(scan_mode="nspi"))
        assert "pass1:-Pn -T4" in summary
        assert "pass2:-Pn -T2 -n -p 502,4840,44818,445,139,3389,5985 -sV" in summary
        port_summary = summary.split("ports=", 1)[1].split("; deep_inspection=", 1)[0]
        assert "--script" not in port_summary
        assert (
            "deep_inspection=-sV --version-intensity 5 -O "
            "--script-timeout 60s --host-timeout 300s"
        ) in summary
