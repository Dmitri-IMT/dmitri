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
