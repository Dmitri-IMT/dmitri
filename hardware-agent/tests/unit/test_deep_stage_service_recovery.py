from __future__ import annotations

from agent.config import AgentSettings
from agent.scanner.errors import BudgetExceeded, UnitScanError
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo
from agent.scanner.stages import run_deep_inspection_stage


class _Reporter:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:
        self.events.append(event)


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
    reporter = _Reporter()

    monkeypatch.setattr(
        "agent.scanner.stages.run_nse_vulnerability_scan",
        lambda *args, **kwargs: None,
    )

    incomplete = run_deep_inspection_stage(
        runner,
        AgentSettings(scan_mode="nspi"),
        [host],
        reporter=reporter,
    )

    assert runner.calls == 1
    assert incomplete == 1
    assert host.deep_inspection_outcome == "partial"
    assert host.deep_inspection_reason == "nse_timeout"
    assert host.deep_inspection_evidence_source == "service_recovery"
    assert host.ports[0].service.name == "modbus"
    assert host.ports[0].service.banner == "Modbus TCP 1.0"
    done = next(event for event in reporter.events if event.kind == "deep_stage_done")
    assert done.units_skipped == 0
    assert done.units_total == 1


def test_deep_stage_recovers_after_unit_scan_error(monkeypatch) -> None:
    host = _host()
    runner = _Runner()

    def fail_nse(*args, **kwargs):
        raise UnitScanError("nse failed")

    monkeypatch.setattr("agent.scanner.stages.run_nse_vulnerability_scan", fail_nse)

    incomplete = run_deep_inspection_stage(
        runner,
        AgentSettings(scan_mode="standard"),
        [host],
    )

    assert runner.calls == 1
    assert incomplete == 1
    assert host.deep_inspection_outcome == "partial"
    assert host.deep_inspection_reason == "nse_failed"
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


def test_deep_stage_continues_when_recovery_probe_fails(monkeypatch) -> None:
    first = _host()
    second = _host()
    second.ip = "192.168.10.31"
    runner = _Runner()

    monkeypatch.setattr(
        "agent.scanner.stages.run_nse_vulnerability_scan",
        lambda *args, **kwargs: (_ for _ in ()).throw(BudgetExceeded()),
    )

    def fail_recovery(*args, **kwargs):
        raise UnitScanError("recovery failed")

    monkeypatch.setattr("agent.scanner.stages.detect_services", fail_recovery)

    skipped = run_deep_inspection_stage(
        runner,
        AgentSettings(scan_mode="nspi", unit_failure_threshold=1.0),
        [first, second],
    )

    assert skipped == 2
    assert first.ports[0].service.name == "modbus-tcp"
    assert second.ports[0].service.name == "modbus-tcp"
