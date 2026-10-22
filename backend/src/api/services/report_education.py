"""Evidence-grounded teaching material for explained reports, without AI calls."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from api.schemas.ai import AILanguage, ScanAIAnalysis
from api.schemas.read import FindingRead, ScanDetailResponse
from api.schemas.reports import ReportEducation
from api.services.report_education_copy import guide, text
from api.services.scan_evidence import (
    is_cve_correlation,
    summarize_finding_evidence,
)

SEVERITIES = ("critical", "high", "medium", "low")


def device_identity(*, address: str, hostname: str, machine_type: str | None,
                    os_name: str | None, profile: dict[str, Any] | None,
                    language: AILanguage) -> dict[str, Any]:
    """Describe the scanner's identity evidence without inventing a model."""
    profile = profile or {}
    label = text("identity_type_" + (machine_type or "unknown"), language)
    if machine_type in {"computer", "phone"} and os_name:
        for system in ("Windows", "Linux", "iOS", "Android", "macOS"):
            if system.casefold() in os_name.casefold():
                label += " " + system
                break
    manufacturer = profile.get("manufacturer")
    model = profile.get("model")
    if model:
        label = str(model)
        if manufacturer and str(manufacturer).casefold() not in label.casefold():
            label = f"{manufacturer} {label}"
    if hostname and hostname != address:
        label = f"{hostname} ({label})"
    return {
        "display_name": label,
        "manufacturer": manufacturer,
        "model": model,
        "identity_confidence": profile.get("confidence", "unknown"),
        "identity_evidence": [item["value"] for item in profile.get("evidence", [])],
        "identity_conflicts": profile.get("conflicts", []),
    }


def _basis(finding: FindingRead) -> str:
    if is_cve_correlation(finding.cve_id, finding.source):
        return "correlation"
    if finding.source == "nmap_nse" and not finding.cve_id:
        return "observation"
    return "other"


def service_family(service: str | None) -> str:
    """Use the observed service name, never infer a service from its port alone."""
    name = (service or "").casefold()
    if name in {"ssh"}:
        return "ssh"
    if name in {"telnet", "exec", "login", "shell", "bindshell", "rsh", "rlogin"}:
        return "legacy_remote"
    if name in {"ftp", "ftp-data", "ftps"}:
        return "ftp"
    if name in {"mysql", "postgresql", "mongodb", "redis", "ms-sql-s", "oracle"}:
        return "database"
    if name in {"smb", "microsoft-ds", "netbios-ssn", "nfs"}:
        return "sharing"
    if name in {"domain", "dns"}:
        return "dns"
    if name in {"http", "https", "http-alt", "ssl/http", "ajp13"}:
        return "web"
    if name in {"vnc", "ms-wbt-server", "rdp", "x11"}:
        return "desktop"
    if ("modbus" in name or "opcua" in name or "opc ua" in name
            or name in {"s7", "s7comm", "ethernet-ip"}):
        return "industrial"
    return "other_service"


def _group_key(
    finding: FindingRead,
) -> tuple[str, str, int | None, str | None, str, str, str | None, bool]:
    address = str(finding.host_ip) if finding.host_ip else ""
    if finding.source_script == "smb-protocols" and "smbv1" in (
        finding.title + " " + finding.evidence
    ).casefold():
        category = "smb_v1"
    elif finding.source_script == "ssh-auth-methods" and "password" in (
        finding.title + " " + finding.evidence
    ).casefold():
        category = "ssh_password"
    elif _basis(finding) == "correlation":
        category = "cve_" + service_family(finding.service)
    else:
        # Different observations must not become one assumed vulnerability.
        category = "observed_" + str(finding.finding_id)
    return (
        address,
        category,
        finding.port,
        finding.protocol,
        finding.detection_method,
        finding.evidence_status,
        finding.confidence,
        finding.evidence_truncated,
    )


def _severity_counts(findings: list[FindingRead]) -> dict[str, int]:
    counts = Counter(finding.severity for finding in findings)
    return {key: counts[key] for key in SEVERITIES}


def _maximum_severity(findings: list[FindingRead]) -> str | None:
    counts = _severity_counts(findings)
    return next((key for key in SEVERITIES if counts[key]), None)


def finding_semantic_limit(
    method: str, status: str, confidence: str | None, language: AILanguage,
    *, evidence_truncated: bool = False, has_observations: bool = False,
) -> str | None:
    """Explain why a record cannot be read as a demonstrated target condition."""
    if status == "supported" and method == "version_correlation":
        return text("limit_version_correlation", language)
    if (
        status == "supported"
        and method == "specific_check"
        and confidence == "confirmed"
        and has_observations
    ):
        return text("limit_specific_check", language)
    if (
        status == "supported"
        and method == "configuration_observation"
        and confidence == "confirmed"
        and has_observations
        and not evidence_truncated
    ):
        return None
    if status == "textual_reference" or method == "textual_reference":
        key = "limit_textual_reference"
    elif status == "conflicting":
        key = "limit_conflicting"
    elif status == "inconclusive":
        key = "limit_inconclusive"
    elif status == "unknown" or method == "unknown":
        key = "limit_unknown"
    else:
        key = "limit_unvalidated"
    return text(key, language, method=text("method_" + method, language),
                status=text("status_" + status, language))


def industrial_protocol_summary(hosts: list[Any]) -> dict[str, dict[str, int]]:
    summary = {
        protocol: {"service_count": 0, "confirmed_services": 0,
                   "suspected_services": 0, "mapping_completed": 0,
                   "mapping_limited": 0, "mapping_not_attempted": 0,
                   "anonymous_read_verified": 0}
        for protocol in ("modbus_tcp", "opcua_tcp")
    }
    for host in hosts:
        for service in host.industrial_services:
            counts = summary[service.protocol]
            counts["service_count"] += 1
            counts["confirmed_services" if service.confidence == "confirmed"
                   else "suspected_services"] += 1
            if service.protocol == "opcua_tcp":
                observation = service.observation
                mapping = observation.mapping if observation else None
                if mapping and mapping.phase.status == "completed":
                    counts["mapping_completed"] += 1
                elif mapping:
                    counts["mapping_limited"] += 1
                else:
                    counts["mapping_not_attempted"] += 1
                if (mapping and mapping.application_value_read_succeeded is True
                        and mapping.value_good_count > 0):
                    counts["anonymous_read_verified"] += 1
            else:
                if service.mapping_source in {
                    None, "service_granularity", "discovery_only",
                }:
                    counts["mapping_not_attempted"] += 1
                elif any(unit.status == "responding" for unit in service.units):
                    counts["mapping_completed"] += 1
                else:
                    counts["mapping_limited"] += 1
    return summary


def report_data_boundary(detail: ScanDetailResponse) -> ScanDetailResponse:
    """Return report data with OPC UA banner and observation fields removed per host."""
    safe_hosts = []
    for host in detail.hosts:
        opcua_ports = {
            service.port for service in host.industrial_services
            if service.protocol == "opcua_tcp"
        }
        safe_hosts.append(host.model_copy(update={
            "ports": [
                port.model_copy(update={"service": "opcua", "version": None})
                if port.protocol == "tcp" and port.port in opcua_ports else port
                for port in host.ports
            ],
            "industrial_services": [
                service.model_copy(update={"observation": None})
                if service.protocol == "opcua_tcp" else service
                for service in host.industrial_services
            ],
        }))
    return detail.model_copy(update={"hosts": safe_hosts})


def _advisory_effects(description: str, language: AILanguage) -> list[str]:
    """Label explicit advisory terms as general effects, not target conclusions."""
    value = description.casefold()
    effects = []
    terms = {
        "code_execution": (
            "arbitrary code", "execute code", "code execution", "execute arbitrary",
        ),
        "denial_of_service": ("denial of service", "denial-of-service"),
        "information_disclosure": (
            "information disclosure", "sensitive information", "disclose information",
        ),
        "privilege_escalation": ("privilege escalation", "escalate privileges"),
        "authentication_bypass": ("authentication bypass", "bypass authentication"),
        "web_injection": ("sql injection", "cross-site scripting"),
    }
    for key, phrases in terms.items():
        if any(phrase in value for phrase in phrases):
            effects.append(text(key, language))
    return effects


def build_report_education(
    detail: ScanDetailResponse,
    language: AILanguage,
    *,
    advisories: dict[str, dict[str, Any]] | None = None,
    enrichment: dict[str, int] | None = None,
    analysis: ScanAIAnalysis | None = None,
) -> ReportEducation:
    industrial_protocols = industrial_protocol_summary(detail.hosts)
    detail = report_data_boundary(detail)
    advisories = advisories or {}
    explanations = {item.finding_id: item for item in analysis.important_findings} \
        if analysis else {}
    host_findings: dict[str, list[FindingRead]] = defaultdict(list)
    for finding in detail.findings:
        address = str(finding.host_ip) if finding.host_ip else ""
        host_findings[address].append(finding)
    hosts = {str(host.ip): host for host in detail.hosts}
    opcua_ports = {
        (str(host.ip), service.port)
        for host in detail.hosts
        for service in host.industrial_services
        if service.protocol == "opcua_tcp"
    }
    observations = Counter(_basis(finding) for finding in detail.findings)
    groups: dict[
        tuple[str, str, int | None, str | None, str, str, str | None, bool],
        list[FindingRead],
    ] = defaultdict(list)
    for finding in detail.findings:
        groups[_group_key(finding)].append(finding)
    issue_groups = []
    group_by_finding: dict[str, str] = {}
    for index, (key, findings) in enumerate(groups.items(), start=1):
        (
            address, category, port, protocol, detection_method,
            evidence_status, confidence, evidence_truncated,
        ) = key
        host = hosts.get(address)
        observed_port = next(
            (
                item for item in host.ports
                if item.port == port and item.protocol == protocol
            ),
            None,
        ) if host else None
        family = (
            category.removeprefix("cve_")
            if category.startswith("cve_")
            else category if category in {"smb_v1", "ssh_password"}
            else "other_service"
        )
        semantic_supported = all(
            finding.detection_method == "configuration_observation"
            and finding.evidence_status == "supported"
            and finding.confidence == "confirmed"
            and bool(finding.evidence_observations)
            and not finding.evidence_truncated
            for finding in findings
        )
        if category in {"smb_v1", "ssh_password"} and not semantic_supported:
            family = service_family(findings[0].service)
        profile = guide(family, language)
        group_id = f"G{index:02d}"
        basis = _basis(findings[0])
        cves = sorted({item.cve_id for item in findings if item.cve_id})
        issue_groups.append({
            "id": group_id,
            "address": address or None,
            "hostname": host.hostname if host else findings[0].host_hostname,
            "category": category,
            "family": family,
            "basis": basis,
            "detection_method": detection_method,
            "evidence_status": evidence_status,
            "confidence": confidence,
            "evidence_truncated": evidence_truncated,
            "evidence_observations": [
                observation.model_dump(mode="json")
                for item in findings
                for observation in item.evidence_observations
            ],
            "title": profile["name"],
            "port": port,
            "protocol": protocol,
            "service": ("opcua" if (address, port) in opcua_ports
                        else findings[0].service),
            "version": (
                None if (address, port) in opcua_ports
                else observed_port.version if observed_port else None
            ),
            "finding_count": len(findings),
            "severity": _maximum_severity(findings),
            "severity_counts": _severity_counts(findings),
            "cves": cves,
            "purpose": profile["purpose"],
            "meaning": profile["meaning"],
            "impact": profile["impact"],
            "conditions": text("reachability", language),
            "uncertainty": (
                finding_semantic_limit(
                    detection_method, evidence_status, confidence, language,
                    evidence_truncated=evidence_truncated,
                    has_observations=bool(findings[0].evidence_observations),
                )
                or (text("correlation_limit", language)
                    if basis == "correlation" else profile["uncertainty"])
            ),
            "steps": profile["steps"],
            "verify": profile["verify"],
            "recorded_observations": [
                {"title": item.title, "description": item.description,
                 "evidence": item.evidence, "recommendation": item.recommendation}
                for item in findings if _basis(item) != "correlation"
            ],
            "advisory_notes": [
                {"cve_id": code, **_known_advisory_note(code, language)}
                for code in cves
                if code in {"CVE-2011-2523", "CVE-2023-38408"}
            ],
        })
        for item in findings:
            group_by_finding[str(item.finding_id)] = group_id
    # A dangerous-looking service remains a service observation, even if the
    # scanner did not emit a finding. Never manufacture a CVE or a login result.
    for host in detail.hosts:
        for port in host.ports:
            if port.state != "open":
                continue
            family = service_family(port.service)
            shell = port.service.casefold() == "bindshell"
            review = any(
                str(item.ip) == str(host.ip) and item.port == port.port
                and item.protocol == port.protocol
                and item.attention in {"review", "priority"}
                for item in detail.exposures
            )
            already_explained = any(
                group["address"] == str(host.ip) and (
                    (group["port"] == port.port
                     and group["protocol"] == port.protocol)
                    or (group["family"] == "smb_v1"
                        and family == "sharing" and port.service.casefold()
                        in {"smb", "microsoft-ds", "netbios-ssn"})
                )
                for group in issue_groups
            )
            if (not shell and not review) or (already_explained and not shell):
                continue
            family = "shell" if shell else family
            profile = guide(family, language)
            issue_groups.append({
                "id": f"G{len(issue_groups) + 1:02d}",
                "address": str(host.ip), "hostname": host.hostname,
                "category": "service_shell" if shell else "service_review",
                "family": family,
                "basis": "service", "title": profile["name"],
                "detection_method": "unknown",
                "evidence_status": "unknown",
                "confidence": None,
                "evidence_truncated": False,
                "evidence_observations": [],
                "port": port.port, "protocol": port.protocol,
                "service": port.service,
                "version": (None if (str(host.ip), port.port) in opcua_ports
                            else port.version),
                "finding_count": 0, "severity": None, "severity_counts": {},
                "cves": [], "purpose": profile["purpose"],
                "meaning": profile["meaning"], "impact": profile["impact"],
                "conditions": text("reachability", language),
                "uncertainty": profile["uncertainty"],
                "steps": profile["steps"], "verify": profile["verify"],
                "recorded_observations": [], "advisory_notes": [],
            })
    issue_groups.sort(key=lambda group: (
        0 if group["family"] == "shell" else 1,
        SEVERITIES.index(group["severity"])
        if group["severity"] in SEVERITIES else len(SEVERITIES),
        group["address"] or "", group["port"] or 0,
    ))
    devices = []
    for host in detail.hosts:
        address = str(host.ip)
        findings = host_findings[address]
        ports = [port for port in host.ports if port.state == "open"]
        exposures = [item for item in detail.exposures if str(item.ip) == address]
        host_groups = [group["id"] for group in issue_groups
                       if group["address"] == address]
        checks = [unit for unit in detail.coverage if str(unit.ip) == address]
        device = {
            "address": address, "hostname": host.hostname,
            **device_identity(
                address=address, hostname=host.hostname,
                machine_type=host.machine_type,
                os_name=host.operating_system.name if host.operating_system else None,
                profile=(host.device_profile.model_dump()
                         if host.device_profile else None),
                language=language,
            ),
            "machine_type": text("type_" + (host.machine_type or "unknown"), language),
            "os": host.operating_system.name if host.operating_system else None,
            "finding_count": len(findings),
            "correlation_count": sum(
                _basis(item) == "correlation" for item in findings
            ),
            "observation_count": sum(
                _basis(item) == "observation" for item in findings
            ),
            "severity_counts": _severity_counts(findings),
            "severity": _maximum_severity(findings),
            "open_ports": len(ports), "groups": host_groups,
            "review_exposures": sum(item.attention in {"review", "priority"}
                                    for item in exposures),
            "checks_completed": sum(unit.outcome == "completed" for unit in checks),
            "checks_incomplete": sum(unit.outcome != "completed" for unit in checks),
            "status": "review" if findings or host_groups or any(
                item.attention in {"review", "priority"} for item in exposures
            ) else "no_alerts",
            "services": [
                {"port": port.port, "protocol": port.protocol,
                 "service": port.service,
                 "version": (None if (address, port.port) in opcua_ports
                             else port.version),
                 "family": service_family(port.service),
                 "purpose": guide(service_family(port.service), language)["purpose"],
                 "finding_count": sum(item.port == port.port
                                      and item.protocol == port.protocol
                                      for item in findings)}
                for port in sorted(ports, key=lambda item: (item.port, item.protocol))
            ],
            "note": text(
                "device_with_alerts" if findings else "device_no_alerts", language
            ),
            "unreadable_fields": host.unreadable_fields,
        }
        devices.append(device)
    devices.sort(key=lambda item: (
        SEVERITIES.index(item["severity"])
        if item["severity"] in SEVERITIES else len(SEVERITIES),
        -item["finding_count"], item["address"],
    ))
    appendix = []
    for finding in sorted(detail.findings, key=lambda item: (
        SEVERITIES.index(item.severity), str(item.host_ip or ""),
        item.port or 0, item.cve_id or "", item.title,
    )):
        advisory = advisories.get(finding.cve_id or "", {})
        explanation = explanations.get(finding.finding_id)
        effects = _advisory_effects(advisory.get("description", ""), language)
        appendix.append({
            "finding_id": str(finding.finding_id),
            "group": group_by_finding[str(finding.finding_id)],
            "address": str(finding.host_ip) if finding.host_ip else None,
            "port": finding.port, "protocol": finding.protocol,
            "title": finding.cve_id or finding.title,
            "severity": finding.severity, "basis": _basis(finding),
            "detection_method": finding.detection_method,
            "evidence_status": finding.evidence_status,
            "confidence": finding.confidence,
            "evidence_truncated": finding.evidence_truncated,
            "semantic_limit": finding_semantic_limit(
                finding.detection_method, finding.evidence_status,
                finding.confidence, language,
                evidence_truncated=finding.evidence_truncated,
                has_observations=bool(finding.evidence_observations),
            ),
            "evidence_observations": [
                observation.model_dump(mode="json")
                for observation in finding.evidence_observations
            ],
            "description": finding.description,
            "recommendation": explanation.recommendation if explanation
            else finding.recommendation,
            "evidence": finding.evidence,
            "plain_language_explanation": explanation.plain_language_explanation
            if explanation else None,
            "why_it_matters": explanation.why_it_matters if explanation else None,
            "uncertainty": explanation.uncertainty if explanation else None,
            "advisory_effects": effects,
            "advisory_description": advisory.get("description"),
            "advisory_fetched_at": advisory.get("fetched_at"),
            "reference": (
                "https://nvd.nist.gov/vuln/detail/" + finding.cve_id
                if finding.cve_id else None
            ),
        })
    service_counts = Counter(port["family"] for device in devices
                             for port in device["services"])
    return {
        "version": "4", "devices": devices, "issue_groups": issue_groups,
        "severity_counts": _severity_counts(detail.findings),
        "evidence_counts": {key: observations[key]
                            for key in ("observation", "correlation", "other")},
        "evidence_summary": (
            detail.evidence_summary.model_dump(mode="json")
            if detail.evidence_summary is not None
            else summarize_finding_evidence(detail.findings, scope="scan")
        ),
        "finding_observations": [
            observation.model_dump(mode="json")
            for observation in detail.finding_observations
        ],
        "finding_observations_truncated": detail.finding_observations_truncated,
        "service_counts": dict(service_counts),
        "industrial_protocols": industrial_protocols,
        "affected_hosts": sum(item["finding_count"] > 0 for item in devices),
        "hosts_without_findings": sum(item["finding_count"] == 0 for item in devices),
        "unassigned_findings": len(host_findings[""]),
        "evidence_completeness": detail.evidence_completeness,
        "checks_completed": sum(
            unit.outcome == "completed" for unit in detail.coverage
        ),
        "checks_incomplete": sum(
            unit.outcome != "completed" for unit in detail.coverage
        ),
        "coverage_recorded": bool(detail.coverage),
        "enrichment": enrichment or {"pending": 0, "failed": 0},
        "appendix": appendix,
        "sources": _sources(),
    }


def _known_advisory_note(code: str, language: AILanguage) -> dict[str, str]:
    key = "advisory_vsftpd" if code == "CVE-2011-2523" else "advisory_agent"
    return {"explanation": text(key, language), "url": (
        "https://nvd.nist.gov/vuln/detail/CVE-2011-2523"
        if key == "advisory_vsftpd" else "https://www.openssh.org/security.html"
    )}


def _sources() -> list[dict[str, str]]:
    return [
        {"title": "FIRST - CVSS User Guide", "url": "https://www.first.org/cvss/v4.0/user-guide"},
        {"title": "Microsoft - SMBv1", "url": "https://learn.microsoft.com/en-us/windows-server/storage/file-server/troubleshoot/detect-enable-and-disable-smbv1-v2-v3"},
        {"title": "OpenSSH - Security", "url": "https://www.openssh.org/security.html"},
        {"title": "Debian - Security FAQ", "url": "https://www.debian.org/security/faq"},
        {"title": "CISA - StopRansomware Guide", "url": "https://www.cisa.gov/stopransomware/ransomware-guide"},
        {"title": "Nmap - Service detection", "url": "https://nmap.org/book/vscan.html"},
    ]
