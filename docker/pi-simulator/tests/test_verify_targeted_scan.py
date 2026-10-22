"""Behavior tests for the persisted targeted-lab scan verifier."""

from __future__ import annotations

import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "verify_targeted_scan", ROOT / "docker/pi-simulator/verify_targeted_scan.py"
)
assert SPEC and SPEC.loader
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


def _observation(ip: str, port: int, tool: str, rule: str) -> dict:
    source = "nmap_nse"
    method = "configuration_observation"
    if tool == "vulners":
        source = "nmap_vulners"
        method = "version_correlation"
        rule = "catalog:nmap-vulners"
    elif tool in verifier.EXPECTED_UNITS:
        source = "targeted_service_assessment"
        method = "specific_check"
    result = "inconclusive" if tool == "nikto" else "positive"
    if tool == "nikto":
        rule = "targeted:nikto-unsupported"
    return {
        "ip": ip,
        "port": port,
        "source": source,
        "source_script": tool,
        "method": method,
        "result": result,
        "rule_id": rule,
        "condition_key": "CVE-2021-9999" if tool == "vulners" else rule,
    }


def complete_scan() -> dict:
    observations = []
    for tool, (ip, port, marker) in verifier.TARGETED_RULES.items():
        observations.append(
            _observation(ip, port, tool, marker or f"targeted:{tool}:confirmed")
        )
    observations.extend(
        _observation(ip, None if rule.startswith("nse:smb") else port, "nmap_nse", rule)
        for ip, port, rule in verifier.NSE_RULES
    )
    observations.append(_observation("172.31.13.2", 80, "vulners", ""))
    hosts = []
    for ip, ports in verifier.TARGETS.items():
        hosts.append(
            {
                "ip": ip,
                "ports": [
                    {"port": port, "protocol": "tcp", "state": "open"}
                    for port in sorted(ports)
                ],
            }
        )
    return {
        "scan_id": "lab-scan-id",
        "status": "completed",
        "scan_mode": "extensive",
        "subnet": "172.31.13.0/29",
        "hosts": hosts,
        "targeted_coverage": [
            {"tool": tool, "completed": count, "failed": 0, "timed_out": 0, "skipped": 0, "gaps": []}
            for tool, count in verifier.EXPECTED_UNITS.items()
        ],
        "findings": [
            {
                "host_ip": observation["ip"],
                "port": observation["port"],
                "source_script": observation["source_script"],
                "source": observation["source"],
                "severity": "medium",
                "title": observation["rule_id"],
                "evidence": observation["rule_id"] + " native evidence",
                "evidence_observations": [observation],
            }
            for observation in observations
        ],
    }


class TargetedScanVerifierTests(unittest.TestCase):
    def test_one_complete_scan_with_targeted_and_nse_evidence_passes(self) -> None:
        self.assertEqual(verifier.validate_scan(complete_scan()), [])

    def test_report_uses_api_finding_host_ip(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            verifier.print_report(complete_scan(), [])
        self.assertIn("172.31.13.2:80", output.getvalue())
        self.assertNotIn("?:80", output.getvalue())

    def test_allows_extra_completed_units_from_auxiliary_discovered_hosts(self) -> None:
        scan = complete_scan()
        scan["targeted_coverage"][0]["completed"] += 1
        self.assertEqual(verifier.validate_scan(scan), [])

    def test_rejects_missing_targeted_unit_finding_and_nse_correlation(self) -> None:
        scan = complete_scan()
        scan["targeted_coverage"][0]["completed"] = 1
        scan["targeted_coverage"][1]["failed"] = 1
        scan["findings"] = [
            finding
            for finding in scan["findings"]
            if not any(
                marker in finding["evidence_observations"][0].get("rule_id", "")
                for marker in ("WEB-SECRET-ENV-001", "catalog:nmap-vulners")
            )
        ]

        errors = verifier.validate_scan(scan)

        self.assertTrue(any("ffuf completed 1/2" in error for error in errors))
        self.assertTrue(any("nikto has 1 failed" in error for error in errors))
        self.assertTrue(any("ffuf has no persisted positive evidence" in error for error in errors))
        self.assertTrue(any("vulners has no positive" in error for error in errors))

    def test_rejects_wrong_scan_mode_and_unexpected_endpoint(self) -> None:
        scan = complete_scan()
        scan["scan_mode"] = "nspi"
        scan["hosts"].pop()

        errors = verifier.validate_scan(scan)

        self.assertTrue(any("expected 'extensive'" in error for error in errors))
        self.assertTrue(any("172.31.13.6 is missing" in error for error in errors))
