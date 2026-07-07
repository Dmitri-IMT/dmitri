"""Integration tests for TUI flows using Textual pilot testing."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from agent.normalize.contracts import (
    DevicePayload,
    FindingPayload,
    PortPayload,
    ScanPayload,
)
from agent.paths import DmitriConfig, save_config
from agent.tui.app import DmitriApp
from agent.tui.screens.home import HomeScreen
from agent.tui.screens.past_scans import PastScansScreen
from agent.tui.screens.settings import SettingsScreen
from agent.tui.screens.setup import SetupScreen


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
        devices=[
            DevicePayload(
                ip="192.168.1.1",
                hostname="router.local",
                vendor="Netgear",
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
        metadata={"hosts_discovered": 1, "findings_count": 1},
    )


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
    """S6 lists scan files from results/ subdirectory."""
    config_path, workspace_dir = _make_config(tmp_path)
    config = DmitriConfig(results_dir=str(workspace_dir))

    payload = _make_payload()
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
