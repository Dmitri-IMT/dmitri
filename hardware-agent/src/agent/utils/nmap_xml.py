"""XML parsing helpers for Nmap and NSE output."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from agent.scanner.models import (
    MacIdentity,
    OperatingSystemInfo,
    PortInfo,
    ScriptResult,
    ServiceInfo,
)


def _parse_accuracy(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        accuracy = int(value)
    except ValueError:
        return None
    return accuracy if 0 <= accuracy <= 100 else None


def _optional_attribute(element: ET.Element, name: str) -> str | None:
    value = element.get(name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def parse_operating_system(host_element: ET.Element) -> OperatingSystemInfo | None:
    """Parse the strongest supported OS match from an Nmap host XML node."""

    selected_match: ET.Element | None = None
    selected_accuracy = -1
    for match in host_element.findall("os/osmatch"):
        name = (match.get("name") or "").strip()
        accuracy = _parse_accuracy(match.get("accuracy"))
        if not name or accuracy is None or accuracy <= selected_accuracy:
            continue
        selected_match = match
        selected_accuracy = accuracy

    if selected_match is None:
        return None

    selected_class: ET.Element | None = None
    selected_class_accuracy = -1
    classes = selected_match.findall("osclass")
    for os_class in classes:
        accuracy = _parse_accuracy(os_class.get("accuracy"))
        if accuracy is None or accuracy <= selected_class_accuracy:
            continue
        selected_class = os_class
        selected_class_accuracy = accuracy

    cpes = sorted(
        {
            normalized
            for os_class in classes
            for cpe in os_class.findall("cpe")
            if (normalized := (cpe.text or "").strip())
        }
    )
    return OperatingSystemInfo(
        name=(selected_match.get("name") or "").strip(),
        accuracy=selected_accuracy,
        vendor=(
            _optional_attribute(selected_class, "vendor")
            if selected_class is not None
            else None
        ),
        family=(
            _optional_attribute(selected_class, "osfamily")
            if selected_class is not None
            else None
        ),
        generation=(
            _optional_attribute(selected_class, "osgen")
            if selected_class is not None
            else None
        ),
        device_type=(
            _optional_attribute(selected_class, "type")
            if selected_class is not None
            else None
        ),
        cpes=cpes,
    )


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
            tunnel=(
                _optional_attribute(service_node, "tunnel")
                if service_node is not None
                else None
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


def extract_mac_identity(host_element: ET.Element) -> MacIdentity:
    """Return the MAC address and Nmap's vendor label as one observation."""

    for address_node in host_element.findall("address"):
        if address_node.get("addrtype") == "mac":
            return MacIdentity(
                mac=_optional_attribute(address_node, "addr"),
                vendor=_optional_attribute(address_node, "vendor") or "unknown",
            )
    return MacIdentity()


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
