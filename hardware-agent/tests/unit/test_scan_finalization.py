from uuid import uuid4

import pytest
from agent.scanner.finalization import ScanFinalizationCheckpoint, ScanFinalizationStore


def test_checkpoint_survives_restart_and_retains_v1_on_legacy_reconnect(tmp_path):
    store = ScanFinalizationStore(tmp_path / "scan-finalization.json")
    checkpoint = ScanFinalizationCheckpoint(
        command_id=uuid4(),
        scan_id=uuid4(),
        session_id=uuid4(),
        phase="awaiting_ack",
        status="done",
        result_path="results/scan.json",
    )

    store.save(checkpoint)

    restarted_store = ScanFinalizationStore(store.path)
    assert restarted_store.load() == checkpoint
    assert restarted_store.load().protocol == 1


def test_checkpoint_write_failure_preserves_previous_checkpoint(tmp_path, monkeypatch):
    store = ScanFinalizationStore(tmp_path / "scan-finalization.json")
    checkpoint = ScanFinalizationCheckpoint(
        command_id=uuid4(),
        scan_id=uuid4(),
        session_id=uuid4(),
        phase="running",
    )
    store.save(checkpoint)

    def fail_replace(*_args):
        raise OSError("disk full")

    monkeypatch.setattr("agent.scanner.finalization.os.replace", fail_replace)
    with pytest.raises(OSError):
        store.save(
            ScanFinalizationCheckpoint(
                command_id=uuid4(),
                scan_id=uuid4(),
                session_id=uuid4(),
                phase="uploading",
            )
        )

    assert store.load() == checkpoint


def test_corrupt_checkpoint_fails_closed(tmp_path):
    path = tmp_path / "scan-finalization.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError):
        ScanFinalizationStore(path).load()
