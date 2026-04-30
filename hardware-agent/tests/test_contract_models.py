from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from agent.normalize.contracts import (
    ArtifactPayload,
    DevicePayload,
    FindingPayload,
    PortPayload,
    ScanPayload,
)


def test_scan_payload_accepts_optional_mac_and_enriched_findings() -> None:
    payload = ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        subnet="192.168.0.0/24",
        target_mode="subnet",
        scan_profile="lan",
        devices=[
            DevicePayload(
                ip="192.168.0.20",
                mac=None,
                hostname="192.168.0.20",
                vendor="unknown",
                ports=[
                    PortPayload(
                        port=80,
                        protocol="tcp",
                        state="open",
                        service="http",
                        version="nginx 1.24.0",
                        cpes=["cpe:/a:nginx:nginx:1.24.0"],
                    )
                ],
            )
        ],
        findings=[
            FindingPayload(
                ip="192.168.0.20",
                port=80,
                protocol="tcp",
                service="http",
                source="nmap_vulners",
                source_script="vulners",
                cve_id="CVE-2024-12345",
                cvss_score=9.1,
                severity="critical",
                title="Known CVE detected via vulners: CVE-2024-12345",
                description="A known CVE was correlated to the detected HTTP service.",
                recommendation="Patch the vulnerable software.",
                evidence="vulners correlated the service to CVE-2024-12345.",
                references=["https://vulners.com/cve/CVE-2024-12345"],
            )
        ],
        artifacts=[
            ArtifactPayload(
                kind="nmap_xml",
                path="hardware-agent/artifacts/raw/discovery/discovery.xml",
                stage="discovery",
            )
        ],
        metadata={"elapsed_seconds": 12.5},
    )

    assert payload.devices[0].mac is None
    assert payload.devices[0].ports[0].cpes == ["cpe:/a:nginx:nginx:1.24.0"]
    assert payload.findings[0].cve_id == "CVE-2024-12345"
