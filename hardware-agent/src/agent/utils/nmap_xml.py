"""XML parsing helpers for Nmap and NSE output."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from agent.scanner.models import PortInfo, ScriptResult, ServiceInfo


def parse_ports(host_element: ET.Element) -> list[PortInfo]:
    """Parse port/service/script data from a host XML node."""

    ports_node = host_element.find("ports")
    if ports_node is None:
        return []

    ports: list[PortInfo] = []
    for port_element in ports_node.findall("port"):
        state_node = port_element.find("state")
        if state_node is None:
            continue

        state = state_node.get("state", "unknown")
        if state not in {"open", "filtered"}:
            continue

        service_node = port_element.find("service")
        service = ServiceInfo(
            name=(service_node.get("name", "") if service_node is not None else ""),
            product=(
                service_node.get("product", "") if service_node is not None else ""
            ),
            version=(
                service_node.get("version", "") if service_node is not None else ""
            ),
            extra_info=(
                service_node.get("extrainfo", "") if service_node is not None else ""
            ),
            cpes=(
                [cpe.text for cpe in service_node.findall("cpe") if cpe.text]
                if service_node is not None
                else []
            ),
        )
        scripts = [
            parse_script(script_element)
            for script_element in port_element.findall("script")
        ]
        ports.append(
            PortInfo(
                port=int(port_element.get("portid", "0")),
                protocol=port_element.get("protocol", "tcp"),
                state=state,
                service=service,
                scripts=scripts,
            )
        )
    return ports


def extract_ipv4(host_element: ET.Element) -> str | None:
    """Return the IPv4 address from an Nmap host XML node."""

    for address_node in host_element.findall("address"):
        if address_node.get("addrtype") == "ipv4":
            return address_node.get("addr")
    return None


def parse_host_scripts(host_element: ET.Element) -> list[ScriptResult]:
    """Parse hostscript output from a host XML node."""

    hostscript = host_element.find("hostscript")
    if hostscript is None:
        return []
    return [
        parse_script(script_element, is_host_script=True)
        for script_element in hostscript.findall("script")
    ]


def parse_script(
    script_element: ET.Element,
    *,
    is_host_script: bool = False,
) -> ScriptResult:
    """Parse a `<script>` XML node into a structured result."""

    data = parse_nse_node(script_element) if list(script_element) else None

    return ScriptResult(
        script_id=script_element.get("id", "unknown-script"),
        output=script_element.get("output", "").strip(),
        data=data,
        is_host_script=is_host_script,
    )


def parse_nse_node(node: ET.Element) -> Any:
    """Recursively parse NSE structured XML into Python objects."""

    if node.tag == "elem":
        return (node.text or "").strip()

    keyed_values: dict[str, Any] = {}
    positional_values: list[Any] = []

    for child in node:
        value = parse_nse_node(child)
        key = child.get("key")
        if key is None:
            positional_values.append(value)
            continue

        existing = keyed_values.get(key)
        if existing is None:
            keyed_values[key] = value
        elif isinstance(existing, list):
            existing.append(value)
        else:
            keyed_values[key] = [existing, value]

    if keyed_values and positional_values:
        keyed_values["items"] = positional_values
        return keyed_values
    if keyed_values:
        return keyed_values
    return positional_values
