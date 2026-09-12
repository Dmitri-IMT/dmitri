from __future__ import annotations

from agent.config import AgentSettings
from agent.scanner.errors import BudgetExceeded, UnitScanError
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo
from agent.scanner.stages import run_deep_inspection_stage


class _Runner:
    nmap_path = "nmap"
    calls = 0

    def run_xml(self, arguments, *, timeout=None):
        import xml.etree.ElementTree as ET

        self.calls += 1
        return ET.fromstring(
            """
            <nmaprun>
              <host>
                <ports>
                  <port protocol="tcp" portid="502">
                    <state state="open"/>
                    <service name="modbus" product="Modbus TCP" version="1.0"/>
                  </port>
                </ports>
              </host>
            </nmaprun>
            """
        )


def _host() -> HostInfo:
    return HostInfo(
        ip="192.168.10.30",
        hostname="plc-a",
        ports=[
            PortInfo(
                port=502,
                state="open",
                service=ServiceInfo(name="modbus-tcp"),
            )
        ],
    )


def test_deep_stage_recovers_service_evidence_when_nse_returns_none(
    monkeypatch,
) -> None:
    host = _host()
    runner = _Runner()

    monkeypatch.setattr(
        "agent.scanner.stages.run_nse_vulnerability_scan",
        lambda *args, **kwargs: None,
    )

    run_deep_inspection_stage(
        runner,
        AgentSettings(scan_mode="nspi"),
        [host],
    )

    assert runner.calls == 1
    assert host.ports[0].service.name == "modbus"
    assert host.ports[0].service.banner == "Modbus TCP 1.0"


def test_deep_stage_recovers_after_unit_scan_error(monkeypatch) -> None:
    host = _host()
    runner = _Runner()

    def fail_nse(*args, **kwargs):
        raise UnitScanError("nse failed")

    monkeypatch.setattr("agent.scanner.stages.run_nse_vulnerability_scan", fail_nse)

    run_deep_inspection_stage(
        runner,
        AgentSettings(scan_mode="standard"),
        [host],
    )

    assert runner.calls == 1
    assert host.ports[0].service.name == "modbus"


def test_deep_stage_keeps_port_evidence_when_recovery_also_empty(monkeypatch) -> None:
    host = _host()
    original_name = host.ports[0].service.name
    runner = _Runner()

    def empty_recovery(*args, **kwargs):
        return []

    monkeypatch.setattr(
        "agent.scanner.stages.run_nse_vulnerability_scan",
        lambda *args, **kwargs: (_ for _ in ()).throw(BudgetExceeded()),
    )
    monkeypatch.setattr("agent.scanner.stages.detect_services", empty_recovery)

    skipped = run_deep_inspection_stage(
        runner,
        AgentSettings(scan_mode="nspi", unit_failure_threshold=1.0),
        [host],
    )

    assert skipped == 1
    assert host.ports[0].service.name == original_name
