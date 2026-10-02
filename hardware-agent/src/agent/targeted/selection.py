"""Deterministic target selection from accepted Nmap service evidence."""

from __future__ import annotations

from ipaddress import ip_address
from typing import Iterable, Iterator

from agent.config import TARGETED_MAX_UNITS, TARGETED_MODES
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo
from agent.targeted.models import (
    TargetedGapReason,
    TargetedOutcome,
    TargetedStageSummary,
    TargetedTool,
    TargetedUnit,
)

_WEB_FALLBACKS = {80: "http", 443: "https", 8080: "http", 8443: "https"}
_TLS_FALLBACKS = {443, 465, 636, 853, 989, 990, 993, 995, 5061, 5986, 8443, 9443}
_TLS_SERVICES = {"tls", "https", "imaps", "pop3s", "smtps", "ftps", "ldaps"}
_SMB_SERVICES = {"netbios-ssn", "microsoft-ds", "smb", "samba"}
_INCONCLUSIVE_SERVICES = {"", "unknown", "tcpwrapped"}


def _service_name(port: PortInfo) -> str:
    return port.service.name.strip().casefold()


def _tunnel_name(port: PortInfo) -> str:
    return (port.service.tunnel or "").strip().casefold()


def _has_conclusive_service(port: PortInfo) -> bool:
    return _service_name(port) not in _INCONCLUSIVE_SERVICES


def _is_web(port: PortInfo) -> bool:
    name = _service_name(port)
    if "http" in name:
        return True
    return not _has_conclusive_service(port) and port.port in _WEB_FALLBACKS


def _web_transport(port: PortInfo) -> str:
    name = _service_name(port)
    if _tunnel_name(port) == "ssl" or "https" in name or name.startswith("ssl/"):
        return "https"
    if _has_conclusive_service(port):
        return "http"
    return _WEB_FALLBACKS.get(port.port, "http")


def _is_tls(port: PortInfo) -> bool:
    name = _service_name(port)
    if _tunnel_name(port) == "ssl" or name.startswith("ssl/") or name in _TLS_SERVICES:
        return True
    return not _has_conclusive_service(port) and port.port in _TLS_FALLBACKS


def _is_smb(port: PortInfo) -> bool:
    name = _service_name(port)
    if name in _SMB_SERVICES:
        return True
    return not _has_conclusive_service(port) and port.port in {139, 445}


def _is_ssh(port: PortInfo) -> bool:
    name = _service_name(port)
    return name == "ssh" or (not _has_conclusive_service(port) and port.port == 22)


def _is_cleartext_ftp(port: PortInfo) -> bool:
    name = _service_name(port)
    if _tunnel_name(port) == "ssl" or name in {"ftps", "ssl/ftp"}:
        return False
    return name == "ftp" or (not _has_conclusive_service(port) and port.port == 21)


def _is_cleartext_telnet(port: PortInfo) -> bool:
    if _tunnel_name(port) == "ssl":
        return False
    name = _service_name(port)
    return name == "telnet" or (not _has_conclusive_service(port) and port.port == 23)


def _unit(
    ip: str,
    port: PortInfo,
    tool: TargetedTool,
    transport: str | None = None,
) -> TargetedUnit:
    return TargetedUnit(
        ip=ip,
        port=port.port,
        protocol=port.protocol,
        service=port.service.name.strip(),
        tool=tool,
        transport=transport,
    )


def _preferred_service_name(current: str, candidate: str) -> str:
    names = (current.strip().casefold(), candidate.strip().casefold())
    conclusive = [name for name in names if name not in _INCONCLUSIVE_SERVICES]
    if conclusive:
        return min(conclusive)
    return min(names)


def _preferred_tunnel(current: str | None, candidate: str | None) -> str | None:
    tunnels = {
        value.strip().casefold()
        for value in (current, candidate)
        if value and value.strip()
    }
    if "ssl" in tunnels:
        return "ssl"
    return min(tunnels) if tunnels else None


def _canonical_endpoints(
    hosts: Iterable[HostInfo],
) -> dict[tuple[str, int, str], PortInfo]:
    """Consume hosts once and retain only canonical endpoint evidence.

    The scan already owns the accepted ``HostInfo`` inventory.  This compact map is
    required for exact, order-independent deduplication; it deliberately does not
    retain hosts or build the unbounded eligible-unit list prohibited by the spec.
    """

    endpoints: dict[tuple[str, int, str], PortInfo] = {}
    for host in hosts:
        canonical_ip = str(ip_address(host.ip))
        for port in host.ports:
            if port.state != "open" or port.protocol != "tcp":
                continue
            key = (canonical_ip, port.port, port.protocol)
            current = endpoints.get(key)
            if current is None:
                endpoints[key] = PortInfo(
                    port=port.port,
                    protocol=port.protocol,
                    state="open",
                    service=ServiceInfo(
                        name=_preferred_service_name("", port.service.name),
                        tunnel=_preferred_tunnel(None, port.service.tunnel),
                    ),
                )
                continue
            current.service.name = _preferred_service_name(
                current.service.name, port.service.name
            )
            current.service.tunnel = _preferred_tunnel(
                current.service.tunnel, port.service.tunnel
            )
    return endpoints


def _smb_ports(
    endpoints: dict[tuple[str, int, str], PortInfo],
) -> dict[str, int]:
    selected: dict[str, tuple[int, int]] = {}
    for (ip, _, _), port in endpoints.items():
        if not _is_smb(port):
            continue
        rank = (0 if port.port == 445 else 1 if port.port == 139 else 2, port.port)
        if ip not in selected or rank < selected[ip]:
            selected[ip] = rank
    return {ip: rank[1] for ip, rank in selected.items()}


def _eligible_units(hosts: Iterable[HostInfo]) -> Iterator[TargetedUnit]:
    endpoints = _canonical_endpoints(hosts)
    smb_ports = _smb_ports(endpoints)
    for (ip, _, _), port in endpoints.items():
        if _is_web(port):
            transport = _web_transport(port)
            yield _unit(ip, port, TargetedTool.FFUF, transport)
            yield _unit(ip, port, TargetedTool.NIKTO, transport)
        if _is_tls(port):
            yield _unit(ip, port, TargetedTool.TESTSSL, "tls")
        if smb_ports.get(ip) == port.port:
            yield _unit(ip, port, TargetedTool.ENUM4LINUX)
        if _is_ssh(port):
            yield _unit(ip, port, TargetedTool.SSH_AUDIT)
        if _is_cleartext_ftp(port):
            yield _unit(ip, port, TargetedTool.FTP_CHECK)
        if _is_cleartext_telnet(port):
            yield _unit(ip, port, TargetedTool.TELNET_CHECK)


_TOOL_ORDER = {tool: index for index, tool in enumerate(TargetedTool)}


def _unit_order_key(unit: TargetedUnit) -> tuple[object, int, str, int]:
    return (ip_address(unit.ip), unit.port, unit.protocol, _TOOL_ORDER[unit.tool])


def _keep_best(units: Iterable[TargetedUnit]) -> list[TargetedUnit]:
    kept: list[TargetedUnit] = []
    for unit in units:
        if len(kept) < TARGETED_MAX_UNITS:
            kept.append(unit)
            continue
        worst_index = max(
            range(len(kept)), key=lambda index: _unit_order_key(kept[index])
        )
        if _unit_order_key(unit) < _unit_order_key(kept[worst_index]):
            kept[worst_index] = unit
    kept.sort(key=_unit_order_key)
    return kept


def select_targeted_units(
    hosts: Iterable[HostInfo],
    *,
    scan_mode: str,
    summary: TargetedStageSummary | None = None,
) -> list[TargetedUnit]:
    """Return a capped plan and optionally record bounded plan-limit counters."""

    if scan_mode not in TARGETED_MODES:
        return []

    eligible_by_tool = {tool: 0 for tool in TargetedTool}

    def counted() -> Iterator[TargetedUnit]:
        for unit in _eligible_units(hosts):
            eligible_by_tool[unit.tool] += 1
            yield unit

    selected = _keep_best(counted())
    if summary is not None:
        planned_by_tool = {tool: 0 for tool in TargetedTool}
        for unit in selected:
            planned_by_tool[unit.tool] += 1
        eligible = sum(eligible_by_tool.values())
        omitted = eligible - len(selected)
        summary.eligible += eligible
        summary.planned += len(selected)
        summary.omitted += omitted
        summary.skipped += omitted
        for tool in TargetedTool:
            tool_omitted = eligible_by_tool[tool] - planned_by_tool[tool]
            summary.per_tool[tool][TargetedOutcome.SKIPPED] += tool_omitted
            summary.plan_limit_by_tool[tool] += tool_omitted
            summary.gap_by_tool[tool][TargetedGapReason.PLAN_LIMIT] += tool_omitted
    return selected


def select_omitted_targeted_units(
    hosts: Iterable[HostInfo], selected: list[TargetedUnit]
) -> list[TargetedUnit]:
    selected_ids = {unit.identity for unit in selected}
    return _keep_best(
        unit for unit in _eligible_units(hosts) if unit.identity not in selected_ids
    )
