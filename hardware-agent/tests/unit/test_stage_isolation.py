from __future__ import annotations

import threading
from xml.etree.ElementTree import Element

from agent.config import AgentSettings, subprocess_timeout_for
from agent.scanner.errors import BudgetExceeded, TransientScanError, UnitScanError
from agent.scanner.models import (
    HostInfo,
    PortInfo,
    PortScanResult,
    ScriptResult,
    StageCoverage,
)
from agent.scanner.progress import STAGE_WEIGHTS, ScanEvent, target_pct
from agent.scanner.stages import (
    build_metadata,
    run_deep_inspection_stage,
    run_port_stage,
)


class _FakeReporter:
    def __init__(self) -> None:
        self.events: list[ScanEvent] = []

    def emit(self, event: ScanEvent) -> None:
        self.events.append(event)


class _DummyRunner:
    def __init__(self) -> None:
        self.nmap_path = "nmap"

    def run_xml(self, arguments, timeout=None):
        return Element("nmaprun")


def test_port_batch_missing_host_result_is_isolated_and_reported(monkeypatch) -> None:
    hosts = [
        HostInfo(ip="10.0.0.1", hostname="first"),
        HostInfo(ip="10.0.0.2", hostname="second"),
    ]
    monkeypatch.setattr(
        "agent.scanner.stages.scan_ports_batch",
        lambda *args, **kwargs: {
            "10.0.0.2": PortScanResult(ports=[PortInfo(port=443)])
        },
    )
    reporter = _FakeReporter()

    skipped = run_port_stage(
        _DummyRunner(),
        AgentSettings(scan_mode="standard", host_batch_size=2, max_workers=1),
        hosts,
        reporter=reporter,
    )

    assert skipped == 1
    assert hosts[0].stage_coverage == [
        StageCoverage("ports", "failed", "nmap_ports", "port_no_result")
    ]
    assert hosts[1].stage_coverage == [
        StageCoverage("ports", "completed", "nmap_ports")
    ]
    assert [port.port for port in hosts[1].ports] == [443]
    assert [event.ip for event in reporter.events if event.kind == "unit_failed"] == [
        "10.0.0.1"
    ]


def _kinds(events: list[ScanEvent], kind: str) -> list[ScanEvent]:
    return [event for event in events if event.kind == kind]


def _eligible_hosts() -> list[HostInfo]:
    return [
        HostInfo(ip="10.0.0.1", hostname="10.0.0.1", ports=[PortInfo(port=22)]),
        HostInfo(ip="10.0.0.2", hostname="10.0.0.2", ports=[PortInfo(port=80)]),
        HostInfo(ip="10.0.0.3", hostname="10.0.0.3", ports=[PortInfo(port=443)]),
    ]


def _make_nse_fake(failures: dict[str, Exception], captured: list | None = None):
    def fake(runner, ip, ports, *, version_intensity, scripts, min_cvss, timeout=None):
        if captured is not None:
            captured.append(timeout)
        exc = failures.get(ip)
        if exc is not None:
            raise exc
        return HostInfo(
            ip=ip,
            hostname=ip,
            ports=ports,
            host_scripts=[ScriptResult(script_id="vulners", is_host_script=True)],
        )

    return fake


def _make_ports_fake(
    failures: dict[str, Exception],
    ports_by_ip: dict[str, list[PortInfo]],
    captured: list | None = None,
):
    def fake(runner, ips, scan_mode, timeout=None):
        if captured is not None:
            captured.append(timeout)
        for ip in ips:
            exc = failures.get(ip)
            if exc is not None:
                raise exc
        return {ip: PortScanResult(ports=ports_by_ip.get(ip, [])) for ip in ips}

    return fake


def _make_nse_counting_fake(transient_until: dict[str, int], calls: dict[str, int]):
    def fake(runner, ip, ports, *, version_intensity, scripts, min_cvss, timeout=None):
        calls[ip] = calls.get(ip, 0) + 1
        if calls[ip] <= transient_until.get(ip, 0):
            raise TransientScanError("flaky")
        return HostInfo(
            ip=ip,
            hostname=ip,
            ports=ports,
            host_scripts=[ScriptResult(script_id="vulners", is_host_script=True)],
        )

    return fake


def _run_deep_with_fake(
    monkeypatch,
    hosts: list[HostInfo],
    fake,
    settings: AgentSettings | None = None,
) -> list[ScanEvent]:
    monkeypatch.setattr("agent.scanner.stages.run_nse_vulnerability_scan", fake)
    settings = settings or AgentSettings(scan_mode="standard", max_workers=1)
    reporter = _FakeReporter()
    run_deep_inspection_stage(_DummyRunner(), settings, hosts, reporter=reporter)
    return reporter.events


def _run_deep(
    monkeypatch,
    hosts: list[HostInfo],
    failures: dict[str, Exception],
    captured: list | None = None,
    settings: AgentSettings | None = None,
    cancel_event: threading.Event | None = None,
) -> list[ScanEvent]:
    monkeypatch.setattr(
        "agent.scanner.stages.run_nse_vulnerability_scan",
        _make_nse_fake(failures, captured),
    )
    settings = settings or AgentSettings(scan_mode="standard", max_workers=2)
    reporter = _FakeReporter()
    run_deep_inspection_stage(
        _DummyRunner(),
        settings,
        hosts,
        reporter=reporter,
        cancel_event=cancel_event,
    )
    return reporter.events


def _run_ports(
    monkeypatch,
    hosts: list[HostInfo],
    failures: dict[str, Exception],
    ports_by_ip: dict[str, list[PortInfo]],
    captured: list | None = None,
    settings: AgentSettings | None = None,
    cancel_event: threading.Event | None = None,
) -> list[ScanEvent]:
    monkeypatch.setattr(
        "agent.scanner.stages.scan_ports_batch",
        _make_ports_fake(failures, ports_by_ip, captured),
    )
    settings = settings or AgentSettings(
        scan_mode="standard", max_workers=2, host_batch_size=2
    )
    reporter = _FakeReporter()
    run_port_stage(
        _DummyRunner(),
        settings,
        hosts,
        reporter=reporter,
        cancel_event=cancel_event,
    )
    return reporter.events


class TestDeepStageUnitFailureIsolated:
    def test_stage_does_not_raise(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        _run_deep(monkeypatch, hosts, {"10.0.0.2": UnitScanError("boom")})

    def test_succeeding_hosts_keep_merged_data(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        _run_deep(monkeypatch, hosts, {"10.0.0.2": UnitScanError("boom")})
        by_ip = {host.ip: host for host in hosts}
        assert by_ip["10.0.0.1"].host_scripts != []
        assert by_ip["10.0.0.3"].host_scripts != []

    def test_failing_host_skipped(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        _run_deep(monkeypatch, hosts, {"10.0.0.2": UnitScanError("boom")})
        by_ip = {host.ip: host for host in hosts}
        assert by_ip["10.0.0.2"].host_scripts == []

    def test_unit_failed_event_carries_ip(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        events = _run_deep(monkeypatch, hosts, {"10.0.0.2": UnitScanError("boom")})
        failed = _kinds(events, "unit_failed")
        assert [event.ip for event in failed] == ["10.0.0.2"]

    def test_deep_stage_done_skip_accounting(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        events = _run_deep(monkeypatch, hosts, {"10.0.0.2": UnitScanError("boom")})
        done = _kinds(events, "deep_stage_done")
        assert len(done) == 1
        assert done[0].units_skipped == 1
        assert done[0].units_total == 3

    def test_no_result_counts_as_skipped_without_erasing_ports(
        self, monkeypatch
    ) -> None:
        hosts = _eligible_hosts()

        def no_result(runner, ip, ports, **kwargs):
            del runner, ports, kwargs
            if ip == "10.0.0.2":
                return None
            return HostInfo(ip=ip, hostname=ip)

        monkeypatch.setattr(
            "agent.scanner.stages.run_nse_vulnerability_scan",
            no_result,
        )
        reporter = _FakeReporter()

        skipped = run_deep_inspection_stage(
            _DummyRunner(),
            AgentSettings(scan_mode="standard", max_workers=1),
            hosts,
            reporter=reporter,
        )

        assert skipped == 1
        assert [port.port for port in hosts[1].ports] == [80]
        assert [event.ip for event in _kinds(reporter.events, "unit_failed")] == [
            "10.0.0.2"
        ]


class TestDeepStageTimeoutSkip:
    def test_timeout_event_carries_ip(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        events = _run_deep(monkeypatch, hosts, {"10.0.0.2": BudgetExceeded("slow")})
        timed_out = _kinds(events, "unit_timed_out")
        assert [event.ip for event in timed_out] == ["10.0.0.2"]

    def test_stage_continues_and_counts_skip(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        events = _run_deep(monkeypatch, hosts, {"10.0.0.2": BudgetExceeded("slow")})
        by_ip = {host.ip: host for host in hosts}
        assert by_ip["10.0.0.1"].host_scripts != []
        assert by_ip["10.0.0.3"].host_scripts != []
        done = _kinds(events, "deep_stage_done")
        assert done[0].units_skipped == 1


class TestPortStageUnitFailureIsolated:
    def _hosts(self) -> list[HostInfo]:
        return [
            HostInfo(ip="10.0.0.1", hostname="10.0.0.1"),
            HostInfo(ip="10.0.0.2", hostname="10.0.0.2"),
            HostInfo(ip="10.0.0.3", hostname="10.0.0.3"),
            HostInfo(ip="10.0.0.4", hostname="10.0.0.4"),
        ]

    def _run(self, monkeypatch) -> tuple[list[ScanEvent], list[HostInfo]]:
        hosts = self._hosts()
        ports_by_ip = {
            "10.0.0.3": [PortInfo(port=22)],
            "10.0.0.4": [PortInfo(port=80), PortInfo(port=443)],
        }
        events = _run_ports(
            monkeypatch,
            hosts,
            {"10.0.0.1": UnitScanError("boom")},
            ports_by_ip,
        )
        return events, hosts

    def test_stage_does_not_raise(self, monkeypatch) -> None:
        self._run(monkeypatch)

    def test_other_batches_keep_ports(self, monkeypatch) -> None:
        _, hosts = self._run(monkeypatch)
        by_ip = {host.ip: host for host in hosts}
        assert len(by_ip["10.0.0.3"].ports) == 1
        assert len(by_ip["10.0.0.4"].ports) == 2

    def test_failed_batch_ports_untouched(self, monkeypatch) -> None:
        _, hosts = self._run(monkeypatch)
        by_ip = {host.ip: host for host in hosts}
        assert by_ip["10.0.0.1"].ports == []
        assert by_ip["10.0.0.2"].ports == []

    def test_skip_event_per_failed_ip(self, monkeypatch) -> None:
        events, _ = self._run(monkeypatch)
        failed = _kinds(events, "unit_failed")
        assert sorted(event.ip for event in failed) == ["10.0.0.1", "10.0.0.2"]

    def test_port_stage_done_skip_accounting(self, monkeypatch) -> None:
        events, _ = self._run(monkeypatch)
        done = _kinds(events, "port_stage_done")
        assert len(done) == 1
        assert done[0].units_skipped == 2
        assert done[0].units_total == 4

    def test_port_stage_count_excludes_filtered_ports(self, monkeypatch) -> None:
        hosts = self._hosts()[:1]
        events = _run_ports(
            monkeypatch,
            hosts,
            {},
            {"10.0.0.1": [PortInfo(port=80), PortInfo(port=81, state="filtered")]},
        )

        done = _kinds(events, "port_stage_done")
        assert done[0].ports_open == 1
        assert done[0].message == "1 open ports found"
        assert len(hosts[0].ports) == 2

    def test_budget_exceeded_batch_emits_timeout(self, monkeypatch) -> None:
        hosts = self._hosts()
        events = _run_ports(
            monkeypatch,
            hosts,
            {"10.0.0.1": BudgetExceeded("slow")},
            {"10.0.0.3": [PortInfo(port=22)]},
        )
        timed_out = _kinds(events, "unit_timed_out")
        assert sorted(event.ip for event in timed_out) == ["10.0.0.1", "10.0.0.2"]
        by_ip = {host.ip: host for host in hosts}
        assert len(by_ip["10.0.0.3"].ports) == 1

    def test_nmap_host_timeout_keeps_evidence_and_counts_skip(
        self, monkeypatch
    ) -> None:
        hosts = self._hosts()

        def _partial_batch(runner, ips, scan_mode, timeout=None):
            del runner, scan_mode, timeout
            return {
                ip: PortScanResult(
                    ports=[PortInfo(port=502)] if ip == "10.0.0.2" else [],
                    skipped=ip == "10.0.0.2",
                )
                for ip in ips
            }

        monkeypatch.setattr(
            "agent.scanner.stages.scan_ports_batch",
            _partial_batch,
        )
        reporter = _FakeReporter()

        skipped = run_port_stage(
            _DummyRunner(),
            AgentSettings(
                scan_mode="nspi",
                max_workers=1,
                host_batch_size=4,
            ),
            hosts,
            reporter=reporter,
        )

        assert skipped == 1
        assert [port.port for port in hosts[1].ports] == [502]
        timed_out = _kinds(reporter.events, "unit_timed_out")
        assert [event.ip for event in timed_out] == ["10.0.0.2"]


class TestCancelStopsReadingFutures:
    def test_deep_stage_processes_no_hosts_when_preset(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        cancel_event = threading.Event()
        cancel_event.set()
        events = _run_deep(monkeypatch, hosts, {}, cancel_event=cancel_event)
        inspected = _kinds(events, "host_inspected")
        assert len(inspected) == 0
        assert len(inspected) < len(hosts)

    def test_deep_stage_does_not_raise_when_cancelled(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        cancel_event = threading.Event()
        cancel_event.set()
        _run_deep(monkeypatch, hosts, {}, cancel_event=cancel_event)

    def test_port_stage_processes_no_batches_when_preset(self, monkeypatch) -> None:
        hosts = [
            HostInfo(ip="10.0.0.1", hostname="10.0.0.1"),
            HostInfo(ip="10.0.0.2", hostname="10.0.0.2"),
            HostInfo(ip="10.0.0.3", hostname="10.0.0.3"),
            HostInfo(ip="10.0.0.4", hostname="10.0.0.4"),
        ]
        cancel_event = threading.Event()
        cancel_event.set()
        events = _run_ports(
            monkeypatch,
            hosts,
            {},
            {ip.ip: [PortInfo(port=22)] for ip in hosts},
            cancel_event=cancel_event,
        )
        assert len(_kinds(events, "port_batch_done")) == 0


class TestTimeoutWiring:
    def test_port_stage_passes_resolved_timeout(self, monkeypatch) -> None:
        hosts = [
            HostInfo(ip="10.0.0.1", hostname="10.0.0.1"),
            HostInfo(ip="10.0.0.2", hostname="10.0.0.2"),
        ]
        captured: list = []
        settings = AgentSettings(
            scan_mode="extensive", max_workers=2, host_batch_size=1
        )
        _run_ports(monkeypatch, hosts, {}, {}, captured=captured, settings=settings)
        expected = subprocess_timeout_for("extensive", "ports")
        assert captured
        assert all(value == expected for value in captured)

    def test_deep_stage_passes_resolved_timeout(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        captured: list = []
        settings = AgentSettings(scan_mode="extensive", max_workers=2)
        _run_deep(monkeypatch, hosts, {}, captured=captured, settings=settings)
        expected = subprocess_timeout_for("extensive", "nse")
        assert captured
        assert all(value == expected for value in captured)


class TestBuildMetadataTerminatedBy:
    def _settings(self) -> AgentSettings:
        return AgentSettings(scan_mode="standard")

    def test_terminated_by_stored(self) -> None:
        metadata = build_metadata(
            runner=_DummyRunner(),
            settings=self._settings(),
            network_info=None,
            elapsed_seconds=1.0,
            hosts_discovered=3,
            findings_count=2,
            terminated_by="user_cancel",
        )
        assert metadata["terminated_by"] == "user_cancel"

    def test_terminated_by_absent_when_omitted(self) -> None:
        metadata = build_metadata(
            runner=_DummyRunner(),
            settings=self._settings(),
            network_info=None,
            elapsed_seconds=1.0,
            hosts_discovered=3,
            findings_count=2,
        )
        assert "terminated_by" not in metadata


class TestTargetPctNewKinds:
    def test_skip_kinds_return_none(self) -> None:
        weights = STAGE_WEIGHTS["standard"]
        assert target_pct(ScanEvent(kind="unit_failed"), weights) is None
        assert target_pct(ScanEvent(kind="unit_timed_out"), weights) is None

    def test_deep_stage_done_is_d_plus_p_plus_i(self) -> None:
        weights = STAGE_WEIGHTS["standard"]
        expected = float(
            weights.discovery + weights.port_scan + weights.deep_inspection
        )
        assert target_pct(ScanEvent(kind="deep_stage_done"), weights) == expected


class TestTransientRetry:
    def test_transient_then_success_keeps_data(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        calls: dict[str, int] = {}
        fake = _make_nse_counting_fake({"10.0.0.1": 1}, calls)
        events = _run_deep_with_fake(monkeypatch, hosts, fake)
        assert calls["10.0.0.1"] == 2
        by_ip = {host.ip: host for host in hosts}
        assert by_ip["10.0.0.1"].host_scripts != []
        assert _kinds(events, "unit_failed") == []

    def test_retry_count_honors_setting(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        calls: dict[str, int] = {}
        fake = _make_nse_counting_fake({"10.0.0.1": 2}, calls)
        settings = AgentSettings(
            scan_mode="standard", max_workers=1, transient_retries=2
        )
        _run_deep_with_fake(monkeypatch, hosts, fake, settings=settings)
        assert calls["10.0.0.1"] == 3
        by_ip = {host.ip: host for host in hosts}
        assert by_ip["10.0.0.1"].host_scripts != []

    def test_persistent_transient_demoted_to_failure(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        calls: dict[str, int] = {}
        fake = _make_nse_counting_fake({"10.0.0.1": 99}, calls)
        events = _run_deep_with_fake(monkeypatch, hosts, fake)
        assert calls["10.0.0.1"] == 2
        by_ip = {host.ip: host for host in hosts}
        assert by_ip["10.0.0.1"].host_scripts == []
        assert by_ip["10.0.0.2"].host_scripts != []
        assert [event.ip for event in _kinds(events, "unit_failed")] == ["10.0.0.1"]
        done = _kinds(events, "deep_stage_done")
        assert done[0].units_skipped == 1

    def test_budget_exceeded_not_retried(self, monkeypatch) -> None:
        hosts = _eligible_hosts()
        calls: dict[str, int] = {}

        def fake(
            runner, ip, ports, *, version_intensity, scripts, min_cvss, timeout=None
        ):
            calls[ip] = calls.get(ip, 0) + 1
            if ip == "10.0.0.1":
                raise BudgetExceeded("slow")
            return HostInfo(
                ip=ip,
                hostname=ip,
                ports=ports,
                host_scripts=[ScriptResult(script_id="vulners", is_host_script=True)],
            )

        events = _run_deep_with_fake(monkeypatch, hosts, fake)
        assert calls["10.0.0.1"] == 1
        assert [event.ip for event in _kinds(events, "unit_timed_out")] == ["10.0.0.1"]
        assert _kinds(events, "unit_failed") == []
