from __future__ import annotations

from typing import Literal, Sequence, get_args

MachineType = Literal[
    "router",
    "computer",
    "camera",
    "storage",
    "tv",
    "phone",
    "printer",
    "sensor",
    "unknown",
]

MACHINE_TYPES: tuple[str, ...] = get_args(MachineType)

_VENDOR_SIGNALS: dict[MachineType, tuple[str, ...]] = {
    "camera": ("hikvision", "dahua", "axis communications", "reolink", "amcrest"),
    "router": (
        "mikrotik",
        "tp-link",
        "netgear",
        "d-link",
        "zyxel",
        "technicolor",
        "sagemcom",
        "arris",
        "ubiquiti",
        "cisco",
        "asustek",
    ),
    "printer": ("brother", "canon", "epson", "lexmark", "xerox", "kyocera", "ricoh"),
    "storage": ("synology", "qnap", "buffalo", "western digital"),
    "tv": ("roku", "vizio", "sony visual", "lg electronics"),
    "phone": ("apple", "oneplus", "xiaomi", "motorola"),
    "sensor": ("espressif", "tuya", "shelly", "sonoff"),
}


def classify_machine_type(
    vendor: str, services: Sequence[tuple[int, str]]
) -> MachineType:
    ports = {port for port, _ in services}
    names = [name.lower() for _, name in services]

    def has(*signals: int | str) -> bool:
        return any(
            signal in ports
            if isinstance(signal, int)
            else any(signal in name for name in names)
            for signal in signals
        )

    if has(554, "rtsp", "onvif", 8554):
        return "camera"
    if has(631, "ipp", 9100, "jetdirect", "printer"):
        return "printer"
    if has(2049, "nfs", 548, "afp", 3260, "iscsi"):
        return "storage"
    if (has(53, "domain") and has(80, 443, 8080)) or (
        has(1900, "upnp") and has(53, "domain")
    ):
        return "router"
    if has(8008, 8009, 7000, "airplay", "dial"):
        return "tv"
    if has(1883, "mqtt", 5683, "coap"):
        return "sensor"
    if has(22, "ssh", 445, "microsoft-ds", 3389, "ms-wbt-server", 5900, "vnc"):
        return "computer"

    lowered = vendor.lower()
    for machine_type, vendors in _VENDOR_SIGNALS.items():
        if any(name in lowered for name in vendors):
            return machine_type
    return "unknown"
