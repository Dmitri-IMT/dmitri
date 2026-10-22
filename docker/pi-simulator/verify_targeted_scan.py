"""Validate and print one persisted targeted lab scan."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


TARGETS: dict[str, set[int]] = {
    "172.31.13.2": {80, 443},
    "172.31.13.3": {22},
    "172.31.13.4": {21},
    "172.31.13.5": {445},
    "172.31.13.6": {23},
}
EXPECTED_UNITS = {
    "ffuf": 2,
    "nikto": 2,
    "testssl.sh": 1,
    "enum4linux-ng": 1,
    "ssh-audit": 1,
    "ftp-check": 1,
    "telnet-check": 1,
}
TARGETED_RULES = {
    "ffuf": ("172.31.13.2", 80, "WEB-SECRET-ENV-001"),
    "nikto": ("172.31.13.2", 80, "targeted:nikto-unsupported"),
    "testssl.sh": ("172.31.13.2", 443, None),
    "enum4linux-ng": ("172.31.13.5", 445, None),
    "ssh-audit": ("172.31.13.3", 22, None),
    "ftp-check": ("172.31.13.4", 21, None),
    "telnet-check": ("172.31.13.6", 23, None),
}
NSE_RULES = {
    ("172.31.13.2", 80, "nse:http-methods"),
    ("172.31.13.2", 443, "nse:ssl-cert-self-signed"),
    ("172.31.13.2", 443, "nse:ssl-cert-weak-signature"),
    ("172.31.13.2", 443, "nse:ssl-cert-weak-key"),
    ("172.31.13.2", 443, "nse:ssl-enum-ciphers-protocol"),
    ("172.31.13.2", 443, "nse:ssl-enum-ciphers-warning"),
    ("172.31.13.2", 443, "nse:ssl-enum-ciphers-grade"),
    ("172.31.13.3", 22, "nse:ssh-auth-methods"),
    ("172.31.13.4", 21, "nse:ftp-anon"),
    ("172.31.13.5", 445, "nse:smb-protocols"),
    ("172.31.13.5", 445, "nse:smb2-security-mode"),
}


def _finding_observations(finding: dict[str, Any]) -> list[dict[str, Any]]:
    observations = finding.get("evidence_observations", [])
    return [item for item in observations if isinstance(item, dict)]


def validate_scan(scan: dict[str, Any]) -> list[str]:
    """Return acceptance failures for a single API ScanDetailResponse payload."""
    errors: list[str] = []
    if scan.get("status") != "completed":
        errors.append(f"scan status is {scan.get('status')!r}, expected 'completed'")
    if scan.get("scan_mode") != "extensive":
        errors.append(f"scan mode is {scan.get('scan_mode')!r}, expected 'extensive'")
    if scan.get("subnet") != "172.31.13.0/29":
        errors.append(f"scan subnet is {scan.get('subnet')!r}, expected 172.31.13.0/29")

    hosts = {
        str(host.get("ip")): host
        for host in scan.get("hosts", [])
        if isinstance(host, dict)
    }
    for ip, expected_ports in TARGETS.items():
        host = hosts.get(ip)
        if host is None:
            errors.append(f"target {ip} is missing from the scan")
            continue
        found_ports = {
            int(port["port"])
            for port in host.get("ports", [])
            if isinstance(port, dict)
            and port.get("protocol") == "tcp"
            and port.get("state") == "open"
        }
        for port in sorted(expected_ports - found_ports):
            errors.append(f"target {ip} TCP/{port} is not recorded open")

    coverage = {
        row.get("tool"): row
        for row in scan.get("targeted_coverage", [])
        if isinstance(row, dict) and isinstance(row.get("tool"), str)
    }
    for tool, expected in EXPECTED_UNITS.items():
        row = coverage.get(tool)
        if row is None:
            errors.append(f"targeted coverage for {tool} is missing")
            continue
        completed = row.get("completed", 0)
        if completed < expected:
            errors.append(f"{tool} completed {completed}/{expected} minimum planned units")
        for outcome in ("failed", "timed_out", "skipped"):
            if row.get(outcome, 0):
                errors.append(f"{tool} has {row[outcome]} {outcome} unit(s)")
        gaps = row.get("gaps", [])
        if gaps:
            errors.append(f"{tool} reports coverage gaps: {gaps}")

    findings = [item for item in scan.get("findings", []) if isinstance(item, dict)]
    all_observations = [
        observation
        for finding in findings
        for observation in _finding_observations(finding)
    ]
    observations = [item for item in all_observations if item.get("result") == "positive"]
    for tool, (ip, port, rule_marker) in TARGETED_RULES.items():
        expected_result = "inconclusive" if tool == "nikto" else "positive"
        matching = all_observations if tool == "nikto" else observations
        if not any(
            str(item.get("ip")) == ip
            and item.get("port") == port
            and item.get("source_script") == tool
            and item.get("result") == expected_result
            and (rule_marker is None or rule_marker in str(item.get("rule_id", "")))
            for item in matching
        ):
            errors.append(f"{tool} has no persisted {expected_result} evidence for {ip}:{port}")

    for ip, port, rule in NSE_RULES:
        if not any(
            str(item.get("ip")) == ip
            and (
                item.get("port") == port
                or (rule.startswith("nse:smb") and item.get("port") is None)
            )
            and item.get("rule_id") == rule
            and item.get("source") == "nmap_nse"
            for item in observations
        ):
            errors.append(f"NSE rule {rule} has no positive finding for {ip}:{port}")

    if not any(
        item.get("source") == "nmap_vulners"
        and item.get("source_script") == "vulners"
        and item.get("method") == "version_correlation"
        and item.get("result") == "positive"
        and item.get("rule_id") == "catalog:nmap-vulners"
        and str(item.get("condition_key", "")).startswith("CVE-")
        for item in observations
    ):
        errors.append("vulners has no positive CPE/CVE correlation in this scan")
    return errors


def _api_json(base_url: str, path: str, *, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = Request(f"{base_url.rstrip('/')}{path}", data=data, headers=headers)
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def fetch_scan(base_url: str, scan_id: str, email: str, password: str) -> dict[str, Any]:
    login = _api_json(
        base_url,
        "/api/v1/auth/login",
        token="",
        payload={"email": email, "password": password},
    )
    token = login.get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("local API login did not return an access token")
    return _api_json(base_url, f"/api/v1/scans/{scan_id}", token=token)


def print_report(scan: dict[str, Any], errors: list[str]) -> None:
    findings = [item for item in scan.get("findings", []) if isinstance(item, dict)]
    print(f"scan_id={scan.get('scan_id', 'unknown')}")
    print(f"status={scan.get('status', 'unknown')} mode={scan.get('scan_mode', 'unknown')}")
    print(f"findings={len(findings)} hosts={len(scan.get('hosts', []))}")
    print("\nFindings:")
    for finding in findings:
        endpoint = f"{finding.get('host_ip') or '?'}:{finding.get('port') or '?'}"
        cve = f" {finding['cve_id']}" if finding.get("cve_id") else ""
        print(
            f"- {endpoint} [{finding.get('source_script') or finding.get('source') or 'unknown'}] "
            f"{finding.get('severity', 'unknown')}{cve}: {finding.get('title', 'untitled')}"
        )
        evidence = finding.get("evidence")
        if isinstance(evidence, str) and evidence:
            print(f"  evidence: {evidence}")
    if errors:
        print("\nAcceptance failures:")
        for error in errors:
            print(f"- {error}")
        print("result=FAIL")
    else:
        print("result=PASS")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scan_id", help="scan UUID returned by `./simulator.sh lab-scan`")
    parser.add_argument(
        "--api-url", default=os.environ.get("DMITRI_SIM_API_URL", "http://127.0.0.1:8000")
    )
    args = parser.parse_args(argv)
    try:
        email = os.environ["SIM_ADMIN_EMAIL"]
        password = os.environ["SIM_ADMIN_PASSWORD"]
        scan = fetch_scan(args.api_url, args.scan_id, email, password)
    except (KeyError, ValueError, HTTPError, OSError, json.JSONDecodeError) as exc:
        print(f"could not fetch scan: {exc}", file=sys.stderr)
        return 2
    errors = validate_scan(scan)
    print_report(scan, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
