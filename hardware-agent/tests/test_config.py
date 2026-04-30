from __future__ import annotations

from agent.config import load_settings


def test_load_settings_disables_raw_artifacts_by_default(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_SAVE_RAW_ARTIFACTS", raising=False)

    settings = load_settings()

    assert settings.save_raw_artifacts is False
