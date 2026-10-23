from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy import func, text
from sqlmodel import Session, select

from api.core.config import get_settings
from api.db.session import get_engine
from api.models.identity import Org, User
from api.models.persistence import (
    FindingRecord,
    HostRecord,
    ScanHostRecord,
    ScanRecord,
    utc_now,
)
from api.services import mcp_auth, read

logger = logging.getLogger("uvicorn.error.mcp")


def bounded_result(value: dict) -> dict:
    truncated = []
    remaining = 96000

    def bound(item, path):
        nonlocal remaining
        if remaining <= 0:
            if len(truncated) < 100:
                truncated.append(path)
            return None
        remaining -= 32
        if isinstance(item, str):
            raw = item.encode("utf-8")
            limit = max(0, min(8192, remaining))
            remaining -= min(len(raw), limit)
            if len(raw) > limit:
                truncated.append(path)
                return raw[:limit].decode("utf-8", errors="ignore")
            return item
        if isinstance(item, list):
            if len(item) > 100:
                truncated.append(path)
            return [
                bound(child, f"{path}[{index}]")
                for index, child in enumerate(item[:100])
            ]
        if isinstance(item, dict):
            return {key: bound(child, f"{path}.{key}") for key, child in item.items()}
        return item

    data = bound(value, "data")
    return {
        "data": data, "truncated": bool(truncated),
        "truncated_fields": truncated[:100],
    }


def page_result(data: list, total: int, page: int, per_page: int) -> dict:
    return {
        "items": data, "total": total, "page": page, "per_page": per_page,
        "next_page": page + 1 if page * per_page < total else None,
    }


def owned_scan(session: Session, scan_id: UUID, org_id: UUID) -> ScanRecord:
    scan = session.exec(select(ScanRecord).where(
        ScanRecord.scan_id == scan_id, ScanRecord.org_id == org_id,
    )).first()
    if scan is None:
        raise ToolError("Scan not found.")
    return scan


def source(path: str) -> str:
    return get_settings().app_base_url.rstrip("/") + path


def scan_summary(session: Session, scan: ScanRecord) -> dict:
    coverage = read.parse_coverage(scan.coverage_json)
    return {
        "scan_id": str(scan.scan_id), "timestamp": scan.timestamp.isoformat(),
        "scan_mode": scan.scan_mode, "subnet": scan.subnet, "status": scan.status,
        "agent_id": str(scan.agent_id) if scan.agent_id else None,
        "coverage": [unit.model_dump(mode="json") for unit in coverage],
        "targeted_coverage": [
            unit.model_dump(mode="json")
            for unit in read.parse_targeted_coverage(scan.metadata_json)
        ],
        "evidence_completeness": read.evidence_completeness(
            scan.metadata_json, coverage
        ),
        "finding_observations": scan.finding_observations_json,
        "finding_observations_truncated": scan.finding_observations_truncated,
        "assessment_policy_version": scan.assessment_policy_version,
        "host_count": session.exec(
            select(func.count()).select_from(ScanHostRecord)
            .where(ScanHostRecord.scan_id == scan.scan_id)
        ).one(),
        "finding_count": session.exec(
            select(func.count()).select_from(FindingRecord)
            .where(FindingRecord.scan_id == scan.scan_id)
        ).one(),
        "source_url": source(f"/scans/{scan.scan_id}"),
    }


def execute_read(tool: str, args: dict, access_token: str) -> dict:
    identity = mcp_auth.load_access_token(access_token)
    if identity is None:
        raise ToolError("Your connection expired or was disconnected. Sign in again.")
    with Session(get_engine()) as session:
        session.execute(text("SET LOCAL statement_timeout = '10000'"))
        connection = mcp_auth.active_connection(
            session, UUID(identity.claims["connection_id"])
        )
        if connection is None:
            raise ToolError("Your connection is no longer valid.")
        org_id = connection.org_id
        if (
            connection.last_used_at is None
            or connection.last_used_at < utc_now() - timedelta(minutes=1)
        ):
            connection.last_used_at = utc_now()
            session.add(connection)
            session.commit()
            session.execute(text("SET LOCAL statement_timeout = '10000'"))
        logger.info(
            "mcp_read tool=%s user_id=%s org_id=%s",
            tool, connection.user_id, org_id,
        )
        if tool == "get_account_context":
            user = session.get(User, connection.user_id)
            org = session.get(Org, org_id)
            result = {
                "email": user.email, "organization": org.name,
                "scope": mcp_auth.SCOPE,
            }
        elif tool == "list_scans":
            values = {key: value for key, value in args.items() if value is not None}
            data = read.list_scans(session, org_id=org_id, **values)
            result = page_result([{
                **item.model_dump(mode="json"),
                "source_url": source(f"/scans/{item.scan_id}"),
            } for item in data.data], data.total, args["page"], args["per_page"])
        elif tool == "get_scan":
            result = scan_summary(
                session, owned_scan(session, args["scan_id"], org_id)
            )
        elif tool in {"list_scan_machines", "get_scan_machine"}:
            scan = owned_scan(session, args["scan_id"], org_id)
            statement = select(ScanHostRecord).where(
                ScanHostRecord.scan_id == scan.scan_id
            )
            page = args["page"]
            per_page = args["per_page"]
            offset = (page - 1) * per_page
            if tool == "list_scan_machines":
                total = session.exec(
                    select(func.count()).select_from(statement.subquery())
                ).one()
                rows = session.exec(statement.order_by(ScanHostRecord.id).offset(
                    (args["page"] - 1) * args["per_page"]
                ).limit(args["per_page"])).all()
                result = page_result([{
                    "machine_id": str(row.host_id), "ip": row.ip,
                    "hostname": row.hostname,
                    "vendor": row.vendor, "machine_type": row.machine_type,
                    "scan_id": str(scan.scan_id),
                    "scan_timestamp": scan.timestamp.isoformat(),
                } for row in rows], total, args["page"], args["per_page"])
            else:
                row = session.exec(statement.where(
                    ScanHostRecord.host_id == args["machine_id"]
                )).first()
                if row is None:
                    raise ToolError("Machine not found in this scan.")
                machine = read._to_scan_host_view(
                    session, row,
                    assessment_available=scan.assessment_policy_version is not None,
                ).model_dump(mode="json")
                section = args["section"]
                if section == "identity":
                    result = {
                        key: value for key, value in machine.items()
                        if key not in {"ports", "industrial_services"}
                    }
                elif section == "ports":
                    items = machine["ports"]
                    result = page_result(
                        items[offset:offset + per_page],
                        len(items), page, per_page,
                    )
                else:
                    services = machine["industrial_services"]
                    if args["port"] is not None:
                        services = [
                            service for service in services
                            if service["port"] == args["port"]
                        ]
                    if args["unit_id"] is not None:
                        for service in services:
                            service["units"] = [
                                unit for unit in service["units"]
                                if unit["unit_id"] == args["unit_id"]
                            ]
                    result = page_result(
                        services[offset:offset + per_page],
                        len(services), page, per_page,
                    )
                result.update({
                    "scan_id": str(scan.scan_id), "machine_id": str(row.host_id),
                    "scan_timestamp": scan.timestamp.isoformat(),
                    "source_url": source(f"/scans/{scan.scan_id}"),
                })
        elif tool == "list_machines":
            data = read.list_hosts(session, org_id=org_id, **args)
            result = page_result(
                [item.model_dump(mode="json") for item in data.data],
                data.total, args["page"], args["per_page"],
            )
            result["inventory"] = (
                "Latest observation per machine; use a scan for historical data."
            )
        elif tool == "get_machine":
            machine = session.exec(select(HostRecord).where(
                HostRecord.id == args["machine_id"], HostRecord.org_id == org_id,
            )).first()
            if machine is None:
                raise ToolError("Machine not found.")
            result = read._to_host_summary(machine).model_dump(mode="json")
            result.update({
                "source_url": source(f"/network/{machine.id}"),
                "inventory": "Latest observation; get_scan_machine is historical.",
            })
        elif tool == "list_findings":
            data = read.list_findings(session, org_id=org_id, **args)
            result = page_result([{
                key: value for key, value in finding.model_dump(mode="json").items()
                if key not in {"evidence", "evidence_observations"}
            } for finding in data.data], data.total, args["page"], args["per_page"])
            result["evidence_summary"] = data.evidence_summary.model_dump(mode="json")
        elif tool == "get_finding":
            finding = read.get_finding_detail(
                session, args["finding_id"], org_id=org_id
            )
            if finding is None:
                raise ToolError("Finding not found.")
            result = finding.model_dump(mode="json")
            evidence = result["evidence"]
            offset = args["evidence_offset"]
            result["evidence"] = evidence[offset:offset + 4000]
            result["next_evidence_offset"] = (
                offset + 4000 if offset + 4000 < len(evidence) else None
            )
            observations = result["evidence_observations"]
            page = args["observations_page"]
            result["evidence_observations"] = observations[(page - 1) * 25:page * 25]
            result["next_observations_page"] = (
                page + 1 if page * 25 < len(observations) else None
            )
            result["source_url"] = source(f"/scans/{finding.scan_id}")
        else:
            raise ToolError("Unknown read tool.")
        return bounded_result(result)
