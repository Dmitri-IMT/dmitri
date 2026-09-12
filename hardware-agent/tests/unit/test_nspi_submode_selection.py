from __future__ import annotations

from agent.tui.screens.scan_category import ScanCategoryScreen
from agent.tui.screens.scan_mode import _NSPI_OPTIONS


def test_tui_lists_inventory_mapping_and_disabled_active_validation() -> None:
    assert [option.id for option in _NSPI_OPTIONS] == [
        "inventory",
        "read_only_mapping",
        "active_validation",
    ]
    assert _NSPI_OPTIONS[0].disabled is False
    assert _NSPI_OPTIONS[1].disabled is False
    assert _NSPI_OPTIONS[2].disabled is True


def test_nspi_category_returns_top_level_mode_and_selected_submode(monkeypatch) -> None:
    screen = ScanCategoryScreen("192.168.1.0/24")
    captured = []
    monkeypatch.setattr(screen, "dismiss", captured.append)
    screen._category = "nspi"

    screen._on_mode_result("read_only_mapping")

    assert captured == [("192.168.1.0/24", "nspi", "read_only_mapping")]
