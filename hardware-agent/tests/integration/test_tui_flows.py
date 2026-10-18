"""Integration tests for TUI flows using Textual pilot testing."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from agent.normalize.contracts import (
    DeviceProfilePayload,
    ExposurePayload,
    FindingPayload,
    HostPayload,
    OperatingSystemDetection,
    PortPayload,
    ScanPayload,
)
from agent.paths import DmitriConfig, save_config
from agent.scanner.scan_lock import ScanLease
from agent.tui.app import DmitriApp
from agent.tui.screens.device_detail import DeviceDetailScreen
from agent.tui.screens.home import HomeScreen
from agent.tui.screens.past_scans import PastScansScreen
from agent.tui.screens.scan_progress import ScanProgressScreen
from agent.tui.screens.scan_view import ScanViewScreen
from agent.tui.screens.settings import SettingsScreen
from agent.tui.screens.setup import SetupScreen
from textual.widgets import OptionList, Static


def _make_config(tmp_path: Path) -> tuple[Path, Path]:
    """Create a temp config and workspace dir, return (config_path, workspace_dir)."""
    config_dir = tmp_path / "config"
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir(parents=True)
    (workspace_dir / "results").mkdir(exist_ok=True)
    (workspace_dir / "logs").mkdir(exist_ok=True)
    config_path = config_dir / "config.toml"
    save_config(DmitriConfig(results_dir=str(workspace_dir)), config_path)
    return config_path, workspace_dir


def _make_payload(subnet: str = "192.168.1.0/24") -> ScanPayload:
    return ScanPayload(
        scan_id=uuid4(),
        timestamp=datetime(2026, 5, 3, 14, 30, 0, tzinfo=timezone.utc),
        subnet=subnet,
        scan_mode="quick",
        hosts=[
            HostPayload(
                ip="192.168.1.1",
                hostname="router.local",
                vendor="Netgear",
                operating_system=OperatingSystemDetection(
                    name="Linux 5.10 - 5.15",
                    accuracy=98,
                ),
                machine_type="router",
                device_profile=DeviceProfilePayload(
                    manufacturer="Netgear",
                    confidence="medium",
                    limitations=["Exact product model unavailable."],
                ),
                ports=[
                    PortPayload(
                        port=22,
                        protocol="tcp",
                        state="open",
                        service="ssh",
                        version="OpenSSH 8.9",
                    ),
                ],
            ),
        ],
        findings=[
            FindingPayload(
                ip="192.168.1.1",
                port=22,
                protocol="tcp",
                service="ssh",
                severity="high",
                cve_id="CVE-2023-12345",
                cvss_score=8.5,
                title="Weak SSH key exchange",
                description="Server uses deprecated key exchange algorithm",
                recommendation="Update SSH config",
                evidence="diffie-hellman-group1-sha1",
            ),
        ],
        assessment_policy_version="2026-09-15.1",
        exposures=[
            ExposurePayload(
                ip="192.168.1.1",
                port=22,
                protocol="tcp",
                observed_service="ssh",
                observed_version="OpenSSH 8.9",
                role="remote_access",
                attention="review",
                confidence="high",
                reason="A remote-access service is reachable.",
            )
        ],
        metadata={"hosts_discovered": 1, "findings_count": 1},
    )


def _make_multi_host_payload() -> ScanPayload:
    payload = _make_payload()
    payload.hosts.append(
        HostPayload(
            ip="192.168.1.2",
            hostname="camera.local",
            vendor="Acme",
            machine_type="camera",
            device_profile=DeviceProfilePayload(
                manufacturer="Acme",
                product_family="Camera family",
                confidence="high",
            ),
            ports=[
                PortPayload(
                    port=80,
                    protocol="tcp",
                    state="open",
                    service="http",
                )
            ],
        )
    )
    payload.exposures.append(
        ExposurePayload(
            ip="192.168.1.2",
            port=80,
            protocol="tcp",
            observed_service="http",
            role="administration",
            attention="priority",
            confidence="high",
            reason="An administrative interface is reachable without TLS.",
        )
    )
    return payload


@pytest.mark.asyncio
async def test_first_run_shows_setup(tmp_path):
    """Journey E: no config → S0 shown."""
    with patch("agent.tui.app.load_config", return_value=None):
        async with DmitriApp().run_test() as pilot:
            assert isinstance(pilot.app.screen, SetupScreen)


@pytest.mark.asyncio
async def test_existing_config_shows_home(tmp_path):
    """With config present, app shows Home."""
    config_path, results_dir = _make_config(tmp_path)
    config = DmitriConfig(results_dir=str(results_dir))
    with patch("agent.tui.app.load_config", return_value=config):
        async with DmitriApp().run_test() as pilot:
            assert isinstance(pilot.app.screen, HomeScreen)


@pytest.mark.asyncio
async def test_settings_roundtrip(tmp_path):
    """Journey D: Ctrl+T opens Settings."""
    config_path, results_dir = _make_config(tmp_path)
    config = DmitriConfig(results_dir=str(results_dir))
    with patch("agent.tui.app.load_config", return_value=config):
        async with DmitriApp().run_test() as pilot:
            assert isinstance(pilot.app.screen, HomeScreen)
            await pilot.press("ctrl+t")
            assert isinstance(pilot.app.screen, SettingsScreen)
            await pilot.press("escape")
            assert isinstance(pilot.app.screen, HomeScreen)


@pytest.mark.asyncio
async def test_past_scans_empty_state(tmp_path):
    """S6 with empty results dir shows message."""
    config_path, results_dir = _make_config(tmp_path)
    config = DmitriConfig(results_dir=str(results_dir))
    with (
        patch("agent.tui.app.load_config", return_value=config),
        patch(
            "agent.tui.screens.past_scans.load_config",
            return_value=config,
        ),
    ):
        async with DmitriApp().run_test() as pilot:
            assert isinstance(pilot.app.screen, HomeScreen)
            await pilot.press("j", "j")
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(pilot.app.screen, PastScansScreen)
            empty = pilot.app.screen.query_one("#past-scans-empty")
            assert empty.display is True


@pytest.mark.asyncio
async def test_past_scans_with_files(tmp_path):
    """A saved scan opens summary, detail, and returns with selection intact."""
    config_path, workspace_dir = _make_config(tmp_path)
    config = DmitriConfig(results_dir=str(workspace_dir))

    payload = _make_multi_host_payload()
    scan_file = workspace_dir / "results" / "2026-05-03T14-30-00_192-168-1-0_24.json"
    scan_file.write_text(
        json.dumps(payload.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )

    with (
        patch("agent.tui.app.load_config", return_value=config),
        patch(
            "agent.tui.screens.past_scans.load_config",
            return_value=config,
        ),
    ):
        async with DmitriApp().run_test() as pilot:
            await pilot.press("j", "j")
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(pilot.app.screen, PastScansScreen)
            empty = pilot.app.screen.query_one("#past-scans-empty")
            assert empty.display is False
            pilot.app.screen.query_one("#past-scans-list").highlighted = 0
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(pilot.app.screen, ScanViewScreen)
            summary = pilot.app.screen
            assert summary.query_one("#scan-view-container") is not None
            devices = summary.query_one("#scan-device-list", OptionList)
            assert devices.highlighted == 0
            await pilot.press("down")
            assert devices.highlighted == 1
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(pilot.app.screen, DeviceDetailScreen)
            detail = pilot.app.screen
            assert str(detail._host.ip) == "192.168.1.2"
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen is summary
            assert devices.highlighted == 1
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(pilot.app.screen, PastScansScreen)
            assert (
                pilot.app.screen.query_one("#past-scans-list", OptionList).highlighted
                == 0
            )


@pytest.mark.asyncio
async def test_completed_scan_payload_shows_operating_system(tmp_path):
    """A fresh result uses the same summary/detail/back flow without HTTP."""
    config_path, results_dir = _make_config(tmp_path)
    config = DmitriConfig(results_dir=str(results_dir))
    payload = _make_multi_host_payload()

    def unexpected_http(*args, **kwargs):
        raise AssertionError("the local TUI must not make an HTTP request")

    with (
        patch("agent.tui.app.load_config", return_value=config),
        patch("agent.tui.screens.home.load_config", return_value=config),
        patch("httpx.Client.request", side_effect=unexpected_http) as request,
    ):
        async with DmitriApp().run_test() as pilot:
            await pilot.pause()
            home = pilot.app.screen
            assert isinstance(home, HomeScreen)
            home._on_scan_complete((payload, True))
            await pilot.pause()
            assert isinstance(pilot.app.screen, ScanViewScreen)
            summary = pilot.app.screen
            assert summary.query_one("#scan-result-header") is not None
            assert summary.query_one("#scan-category-summary") is not None
            devices = summary.query_one("#scan-device-list", OptionList)
            assert devices.highlighted == 0
            await pilot.press("j")
            assert devices.highlighted == 1
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(pilot.app.screen, DeviceDetailScreen)
            detail = pilot.app.screen
            assert str(detail._host.ip) == "192.168.1.2"
            for widget_id in (
                "#device-detail-header",
                "#device-profile",
                "#device-inventory",
                "#device-exposures",
                "#device-findings",
            ):
                assert detail.query_one(widget_id) is not None
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen is summary
            assert devices.highlighted == 1
            await pilot.press("escape")
            await pilot.pause()
            assert pilot.app.screen is home
            request.assert_not_called()


@pytest.mark.asyncio
async def test_home_summary_counts_duplicate_raw_ports_once(tmp_path):
    """Fresh-scan summary uses canonical endpoint identity for its open count."""
    config = DmitriConfig(results_dir=str(tmp_path))
    payload = _make_payload()
    payload.hosts[0].ports.append(payload.hosts[0].ports[0].model_copy(deep=True))

    with (
        patch("agent.tui.app.load_config", return_value=config),
        patch("agent.tui.screens.home.load_config", return_value=config),
        patch("agent.tui.screens.home.write_scan_result", return_value=None),
    ):
        async with DmitriApp().run_test() as pilot:
            await pilot.pause()
            home = pilot.app.screen
            assert isinstance(home, HomeScreen)
            home._on_scan_complete((payload, False))
            await pilot.pause()

            summary = str(home.query_one("#summary-band", Static).render())
            assert "Ports open: 1" in summary


@pytest.mark.asyncio
async def test_home_transfers_lease_through_progress_and_result_persistence(
    tmp_path, monkeypatch
):
    config = DmitriConfig(results_dir=str(tmp_path))
    payload = _make_payload()
    lease = ScanLease(None, None)
    runner_args = []
    persist_while_active = []

    def record_runner_start(runner):
        runner_args.append(runner.scan_lease)

    def persist_result(*args):
        persist_while_active.append(lease.active)
        return tmp_path / "saved.json"

    monkeypatch.setattr("agent.tui.screens.home.acquire_scan_lease", lambda: lease)
    monkeypatch.setattr("agent.tui.screens.home.load_config", lambda: config)
    monkeypatch.setattr("agent.tui.screens.home.write_scan_result", persist_result)
    monkeypatch.setattr(
        "agent.tui.screens.scan_progress.ScanRunner.start", record_runner_start
    )
    with patch("agent.tui.app.load_config", return_value=config):
        async with DmitriApp().run_test() as pilot:
            await pilot.pause()
            home = pilot.app.screen
            assert isinstance(home, HomeScreen)
            home._on_network_result((payload.subnet, "quick", None))
            await pilot.pause()
            progress = pilot.app.screen
            assert isinstance(progress, ScanProgressScreen)
            assert progress.scan_lease is lease
            assert runner_args == [lease]
            assert lease.active

            progress.dismiss((payload, False))
            await pilot.pause()

            assert pilot.app.screen is home
            assert persist_while_active == [True]
            assert not lease.active


@pytest.mark.asyncio
async def test_home_summary_counts_endpoint_identity_across_hosts_protocols_and_states(
    tmp_path,
):
    config = DmitriConfig(results_dir=str(tmp_path))
    payload = _make_payload()
    first = payload.hosts[0]
    first.ports.extend(
        [
            first.ports[0].model_copy(deep=True),
            PortPayload(port=443, protocol="tcp", state="closed", service="https"),
        ]
    )
    second = HostPayload(
        ip="192.168.1.2",
        hostname="second.local",
        vendor="Unknown",
        ports=[
            PortPayload(port=22, protocol="tcp", state="open", service="ssh"),
            PortPayload(port=22, protocol="udp", state="open", service="unknown"),
            PortPayload(port=53, protocol="udp", state="filtered", service="domain"),
        ],
    )
    payload.hosts.extend([second, second.model_copy(deep=True)])

    with (
        patch("agent.tui.app.load_config", return_value=config),
        patch("agent.tui.screens.home.load_config", return_value=config),
        patch("agent.tui.screens.home.write_scan_result", return_value=None),
    ):
        async with DmitriApp().run_test() as pilot:
            await pilot.pause()
            home = pilot.app.screen
            assert isinstance(home, HomeScreen)
            home._on_scan_complete((payload, False))
            await pilot.pause()

            summary = str(home.query_one("#summary-band", Static).render())
            assert "Ports open: 3" in summary


@pytest.mark.asyncio
async def test_ctrl_q_exits(tmp_path):
    """Journey G1: Ctrl+Q exits cleanly."""
    config = DmitriConfig(results_dir=str(tmp_path))
    with patch("agent.tui.app.load_config", return_value=config):
        async with DmitriApp().run_test() as pilot:
            assert isinstance(pilot.app.screen, HomeScreen)
            await pilot.press("ctrl+q")


def test_cli_unknown_command():
    """Exit code 2 for unknown subcommand."""
    import sys

    from agent.cli import main

    with patch.object(sys, "argv", ["dmitri", "nonsense"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2


def test_cli_nmap_missing():
    """Exit code 20 when nmap is not found."""
    import sys

    from agent.cli import main

    with (
        patch.object(sys, "argv", ["dmitri", "start"]),
        patch("agent.cli._check_nmap", return_value=False),
    ):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 20
