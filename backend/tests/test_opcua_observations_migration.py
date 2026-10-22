from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from api.models.identity import Org
from api.models.persistence import IndustrialServiceRecord, ScanHostRecord, ScanRecord
from conftest import _alembic_config
from sqlmodel import Session

ROOT = Path(__file__).resolve().parents[1]


def _load_migration():
    path = ROOT / "alembic/versions/20261020_44_opcua_observations.py"
    spec = importlib.util.spec_from_file_location("opcua_observations_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_follows_current_single_head_and_declares_safe_downgrade(
    monkeypatch,
) -> None:
    migration = _load_migration()
    statements: list[str] = []
    dropped_columns: list[str] = []
    monkeypatch.setattr(
        migration.op, "execute", lambda sql: statements.append(str(sql))
    )
    monkeypatch.setattr(
        migration.op,
        "drop_constraint",
        lambda name, table, **kwargs: statements.append(f"drop {name}"),
    )
    monkeypatch.setattr(
        migration.op,
        "create_check_constraint",
        lambda name, table, condition: statements.append(f"create {name}: {condition}"),
    )
    monkeypatch.setattr(
        migration.op, "drop_column", lambda table, name: dropped_columns.append(name)
    )

    migration.downgrade()

    assert migration.revision == "20261020_44"
    assert migration.down_revision == "20261019_43"
    assert any("protocol = 'opcua_tcp'" in statement for statement in statements)
    assert "opcua_observation_json" in dropped_columns
    assert statements[0].index("IF EXISTS") < statements[0].index("RAISE EXCEPTION")


def test_migrated_database_has_nullable_observation_and_protocol_checks(
    migrated_database,
) -> None:
    inspector = sa.inspect(migrated_database)
    columns = {
        column["name"]: column
        for column in inspector.get_columns("industrial_services")
    }
    assert columns["opcua_observation_json"]["nullable"] is True
    checks = {
        check["name"]: check["sqltext"]
        for check in inspector.get_check_constraints("industrial_services")
    }
    assert "opcua_tcp" in checks["ck_industrial_services_protocol"]
    assert (
        "opcua_observation_json"
        in checks["ck_industrial_services_opcua_observation_protocol"]
    )


def test_downgrade_refuses_existing_ua_service(migrated_database) -> None:
    from datetime import datetime, timezone
    from uuid import uuid4

    with Session(migrated_database) as session:
        org = Org(name="OPC UA migration downgrade guard")
        session.add(org)
        session.flush()
        scan_id = uuid4()
        session.add(
            ScanRecord(
                scan_id=scan_id,
                org_id=org.id,
                timestamp=datetime.now(timezone.utc),
                subnet="192.168.1.0/24",
                scan_mode="nspi",
            )
        )
        session.flush()
        scan_host = ScanHostRecord(
            scan_id=scan_id,
            ip="192.168.1.50",
            hostname="ua-host",
            vendor="unknown",
        )
        session.add(scan_host)
        session.flush()
        session.add(
            IndustrialServiceRecord(
                scan_host_id=scan_host.id,
                protocol="opcua_tcp",
                port=4840,
                confidence="confirmed",
                opcua_observation_json={"schema_version": 1},
            )
        )
        session.commit()

    with pytest.raises(Exception, match="Cannot downgrade: OPC UA observations exist"):
        command.downgrade(_alembic_config(), "20261019_43")

    inspector = sa.inspect(migrated_database)
    assert "opcua_observation_json" in {
        column["name"]
        for column in inspector.get_columns("industrial_services")
    }


def test_modbus_rows_survive_downgrade_and_upgrade(migrated_database) -> None:
    from datetime import datetime, timezone
    from uuid import uuid4

    with Session(migrated_database) as session:
        org = Org(name="OPC UA migration Modbus preservation")
        session.add(org)
        session.flush()
        scan_id = uuid4()
        session.add(
            ScanRecord(
                scan_id=scan_id,
                org_id=org.id,
                timestamp=datetime.now(timezone.utc),
                subnet="192.168.1.0/24",
                scan_mode="nspi",
            )
        )
        session.flush()
        scan_host = ScanHostRecord(
            scan_id=scan_id,
            ip="192.168.1.51",
            hostname="modbus-host",
            vendor="unknown",
        )
        session.add(scan_host)
        session.flush()
        session.add(
            IndustrialServiceRecord(
                scan_host_id=scan_host.id,
                protocol="modbus_tcp",
                port=502,
                confidence="confirmed",
                evidence_sources_json=["modbus-discover"],
            )
        )
        session.commit()

    config = _alembic_config()
    command.downgrade(config, "20261019_43")
    with Session(migrated_database) as session:
        evidence_sources = session.exec(
            sa.text(
                "SELECT evidence_sources_json FROM industrial_services "
                "WHERE protocol = 'modbus_tcp'"
            )
        ).one()[0]
        assert evidence_sources == ["modbus-discover"]

    command.upgrade(config, "head")
    assert "opcua_observation_json" in {
        column["name"]
        for column in sa.inspect(migrated_database).get_columns(
            "industrial_services"
        )
    }
