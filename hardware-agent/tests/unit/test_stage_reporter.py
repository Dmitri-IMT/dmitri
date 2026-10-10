from __future__ import annotations

import xml.etree.ElementTree as ET

from agent.config import AgentSettings
from agent.scanner.models import HostInfo, PortInfo
from agent.scanner.nmap import NmapRunner
from agent.scanner.progress import ScanEvent
from agent.scanner.stages import run_deep_inspection_stage, run_port_stage


class _FakeReporter:
    def __init__(self) -> None:
        self.events: list[ScanEvent] = []

    def emit(self, event: ScanEvent) -> None:
        self.events.append(event)


def _add_host(parent: ET.Element, ip: str, ports: list[int]) -> None:
    host = ET.SubElement(parent, "host")
    status = ET.SubElement(host, "status")
    status.set("state", "up")
    address = ET.SubElement(host, "address")
    address.set("addr", ip)
    address.set("addrtype", "ipv4")
    ports_elem = ET.SubElement(host, "ports")
    for p in ports:
        port = ET.SubElement(ports_elem, "port")
        port.set("protocol", "tcp")
        port.set("portid", str(p))
        state = ET.SubElement(port, "state")
        state.set("state", "open")
        service = ET.SubElement(port, "service")
        service.set("name", "unknown")


def _make_runner(host_ports: dict[str, list[int]]) -> NmapRunner:
    runner = NmapRunner.__new__(NmapRunner)
    runner.nmap_path = "nmap"

    def _run_xml(arguments: list[str], timeout: float | None = None) -> ET.Element:
        root = ET.Element("nmaprun")
        for ip, ports in host_ports.items():
            if ip in arguments:
                _add_host(root, ip, ports)
        return root

    runner.run_xml = _run_xml  # type: ignore[assignment]
    return runner


def _hosts(ips: list[str]) -> list[HostInfo]:
    return [HostInfo(ip=ip, hostname=ip) for ip in ips]


def _kinds(events: list[ScanEvent], kind: str) -> list[ScanEvent]:
    return [event for event in events if event.kind == kind]


class TestRunPortStageReporter:
    def _run(self) -> tuple[list[ScanEvent], list[HostInfo]]:
        host_ports = {
            "10.0.0.1": [22, 80],
            "10.0.0.2": [80],
            "10.0.0.3": [22, 443, 8080],
            "10.0.0.4": [],
            "10.0.0.5": [22],
        }
        runner = _make_runner(host_ports)
        settings = AgentSettings(
            scan_mode="standard",
            host_batch_size=2,
            max_workers=2,
        )
        hosts = _hosts(list(host_ports))
        reporter = _FakeReporter()
        run_port_stage(runner, settings, hosts, reporter=reporter)
        return reporter.events, hosts

    def test_single_started_event(self) -> None:
        events, _ = self._run()
        assert len(_kinds(events, "port_stage_started")) == 1

    def test_first_event_is_started(self) -> None:
        events, _ = self._run()
        assert events[0].kind == "port_stage_started"

    def test_one_batch_event_per_batch(self) -> None:
        events, _ = self._run()
        batch_events = _kinds(events, "port_batch_done")
        assert len(batch_events) == 3

    def test_batches_total_is_constant(self) -> None:
        events, _ = self._run()
        batch_events = _kinds(events, "port_batch_done")
        assert {event.batches_total for event in batch_events} == {3}

    def test_running_batches_done_count(self) -> None:
        events, _ = self._run()
        batch_events = _kinds(events, "port_batch_done")
        assert sorted(event.batches_done for event in batch_events) == [1, 2, 3]

    def test_single_done_event_last(self) -> None:
        events, _ = self._run()
        done_events = _kinds(events, "port_stage_done")
        assert len(done_events) == 1
        assert events[-1].kind == "port_stage_done"

    def test_ports_open_equals_summed_open_ports(self) -> None:
        events, hosts = self._run()
        done_events = _kinds(events, "port_stage_done")
        expected = sum(len(host.ports) for host in hosts)
        assert done_events[0].ports_open == expected
        assert done_events[0].ports_open == 7

    def test_runs_without_reporter(self) -> None:
        host_ports = {"10.0.0.1": [22], "10.0.0.2": [80]}
        runner = _make_runner(host_ports)
        settings = AgentSettings(
            scan_mode="standard",
            host_batch_size=1,
            max_workers=2,
        )
        hosts = _hosts(list(host_ports))
        run_port_stage(runner, settings, hosts)
        assert sum(len(host.ports) for host in hosts) == 2


class TestRunDeepInspectionStageReporter:
    def _eligible_hosts(self) -> list[HostInfo]:
        return [
            HostInfo(ip="10.0.0.1", hostname="10.0.0.1", ports=[PortInfo(port=22)]),
            HostInfo(
                ip="10.0.0.2",
                hostname="10.0.0.2",
                ports=[PortInfo(port=80), PortInfo(port=443)],
            ),
            HostInfo(ip="10.0.0.3", hostname="10.0.0.3", ports=[PortInfo(port=22)]),
            HostInfo(ip="10.0.0.4", hostname="10.0.0.4", ports=[]),
        ]

    def _run(self) -> list[ScanEvent]:
        hosts = self._eligible_hosts()
        runner = _make_runner(
            {host.ip: [port.port for port in host.ports] for host in hosts}
        )
        settings = AgentSettings(scan_mode="standard", max_workers=2)
        reporter = _FakeReporter()
        run_deep_inspection_stage(runner, settings, hosts, reporter=reporter)
        return reporter.events

    def test_single_started_event_with_eligible_total(self) -> None:
        events = self._run()
        started = _kinds(events, "deep_stage_started")
        assert len(started) == 1
        assert started[0].hosts_total == 3

    def test_one_inspected_event_per_eligible_host(self) -> None:
        events = self._run()
        assert len(_kinds(events, "host_inspected")) == 3

    def test_running_hosts_done_count(self) -> None:
        events = self._run()
        inspected = _kinds(events, "host_inspected")
        assert sorted(event.hosts_done for event in inspected) == [1, 2, 3]

    def test_inspected_hosts_total_is_constant(self) -> None:
        events = self._run()
        inspected = _kinds(events, "host_inspected")
        assert {event.hosts_total for event in inspected} == {3}

    def test_inspected_events_carry_ip(self) -> None:
        events = self._run()
        inspected = _kinds(events, "host_inspected")
        assert {event.ip for event in inspected} == {
            "10.0.0.1",
            "10.0.0.2",
            "10.0.0.3",
        }

    def test_empty_eligible_emits_started_only(self) -> None:
        hosts = [
            HostInfo(ip="10.0.0.1", hostname="10.0.0.1", ports=[]),
            HostInfo(ip="10.0.0.2", hostname="10.0.0.2", ports=[]),
        ]
        runner = _make_runner({})
        settings = AgentSettings(scan_mode="standard", max_workers=2)
        reporter = _FakeReporter()
        run_deep_inspection_stage(runner, settings, hosts, reporter=reporter)
        started = _kinds(reporter.events, "deep_stage_started")
        assert len(started) == 1
        assert started[0].hosts_total == 0
        assert _kinds(reporter.events, "host_inspected") == []

    def test_runs_without_reporter(self) -> None:
        hosts = self._eligible_hosts()
        runner = _make_runner(
            {host.ip: [port.port for port in host.ports] for host in hosts}
        )
        settings = AgentSettings(scan_mode="standard", max_workers=2)
        run_deep_inspection_stage(runner, settings, hosts)
        assert all(isinstance(host, HostInfo) for host in hosts)
