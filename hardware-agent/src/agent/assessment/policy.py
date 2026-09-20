"""Frozen local policy for attack-surface and machine-profile assessment."""

from __future__ import annotations

from typing import Literal, get_args

LOCAL_ASSESSMENT_POLICY_VERSION = "2026-09-15.2"

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
ExposureRole = Literal[
    "administration",
    "data_store",
    "file_sharing",
    "remote_access",
    "proxy",
    "api",
    "device_control",
    "discovery",
    "media",
    "general_service",
    "unknown",
]
ExposureAttention = Literal["informational", "review", "priority"]
AssessmentConfidence = Literal["unknown", "low", "medium", "high"]
ExposureConfidence = Literal["low", "medium", "high"]
EvidenceKind = Literal[
    "manufacturer",
    "hostname",
    "operating_system",
    "service",
    "version",
    "banner",
    "certificate",
    "protocol",
    "port",
    "cpe",
    "industrial",
    "web_path",
]

MACHINE_TYPES: tuple[str, ...] = get_args(MachineType)
EXPOSURE_ROLES: tuple[str, ...] = get_args(ExposureRole)
EXPOSURE_ATTENTIONS: tuple[str, ...] = get_args(ExposureAttention)
ASSESSMENT_CONFIDENCES: tuple[str, ...] = get_args(AssessmentConfidence)
EXPOSURE_CONFIDENCES: tuple[str, ...] = get_args(ExposureConfidence)
EVIDENCE_KINDS: tuple[str, ...] = get_args(EvidenceKind)

MAX_EVIDENCE_SOURCE_CHARS = 80
MAX_EVIDENCE_VALUE_CHARS = 160
MAX_ASSESSMENT_TEXT_CHARS = 160
MAX_REASON_CHARS = 240
MAX_EVIDENCE_ITEMS = 12
MAX_CONFLICTS = 5
MAX_LIMITATIONS = 5

SIGNAL_WEIGHTS = {
    "protocol": 3,
    "industrial": 3,
    "product": 2,
    "cpe": 2,
    "operating_system": 2,
    "manufacturer": 1,
    "hostname": 1,
    "service": 1,
    "port": 1,
}

MACHINE_SIGNAL_RULES: dict[MachineType, dict[str, tuple[int | str, ...]]] = {
    "camera": {
        "service": (554, 8554, "rtsp", "onvif"),
        "vendor": (
            "hikvision",
            "dahua",
            "axis communications",
            "reolink",
            "amcrest",
        ),
    },
    "printer": {
        "service": (631, 9100, "ipp", "jetdirect", "printer"),
        "vendor": (
            "brother",
            "canon",
            "epson",
            "lexmark",
            "xerox",
            "kyocera",
            "ricoh",
        ),
    },
    "storage": {
        "service": (2049, 548, 3260, "nfs", "afp", "iscsi"),
        "vendor": ("synology", "qnap", "buffalo", "western digital"),
    },
    "router": {
        "service": (53, 80, 443, 8080, 1900, "domain", "upnp"),
        "vendor": (
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
    },
    "tv": {
        "service": (8008, 8009, 7000, "airplay", "dial"),
        "vendor": ("roku", "vizio", "sony visual", "lg electronics"),
    },
    "phone": {
        "service": (),
        "vendor": ("apple", "oneplus", "xiaomi", "motorola"),
    },
    "sensor": {
        "service": (1883, 5683, "mqtt", "coap"),
        "vendor": ("espressif", "tuya", "shelly", "sonoff"),
    },
    "computer": {
        "service": (
            22,
            445,
            3389,
            5900,
            "ssh",
            "microsoft-ds",
            "ms-wbt-server",
            "vnc",
        ),
        "vendor": (),
    },
    "unknown": {"service": (), "vendor": ()},
}

OS_DEVICE_TYPE_RULES: dict[str, MachineType] = {
    "router": "router",
    "firewall": "router",
    "wap": "router",
    "general purpose": "computer",
    "workstation": "computer",
    "server": "computer",
    "webcam": "camera",
    "camera": "camera",
    "storage-misc": "storage",
    "nas": "storage",
    "printer": "printer",
    "media device": "tv",
    "phone": "phone",
    "sensor": "sensor",
}

PRODUCT_TYPE_TOKENS: dict[MachineType, tuple[str, ...]] = {
    machine_type: tuple(
        str(value)
        for value in (*rules["service"], *rules["vendor"])
        if isinstance(value, str)
    )
    for machine_type, rules in MACHINE_SIGNAL_RULES.items()
}
PRODUCT_TYPE_TOKENS.update(
    {
        "camera": (*PRODUCT_TYPE_TOKENS["camera"], "camera"),
        "printer": (*PRODUCT_TYPE_TOKENS["printer"], "printer"),
        "router": (*PRODUCT_TYPE_TOKENS["router"], "router"),
        "storage": (*PRODUCT_TYPE_TOKENS["storage"], "nas"),
        "tv": (*PRODUCT_TYPE_TOKENS["tv"], "television", "smart tv"),
        "phone": (*PRODUCT_TYPE_TOKENS["phone"], "phone"),
        "sensor": (*PRODUCT_TYPE_TOKENS["sensor"], "sensor"),
    }
)

AMBIGUOUS_VENDOR_NAMES = ("samsung", "lg", "sony", "apple", "amazon")

EXPOSURE_ROLE_TOKENS: dict[ExposureRole, tuple[str, ...]] = {
    "administration": ("management", "webadmin", "admin console", "routeros"),
    "api": ("openapi", "swagger", "api documentation"),
    "data_store": (
        "mysql",
        "postgresql",
        "mongodb",
        "redis",
        "memcached",
        "elasticsearch",
        "cassandra",
        "oracle-tns",
        "ms-sql-s",
        "influxdb",
        "couchdb",
    ),
    "file_sharing": (
        "microsoft-ds",
        "netbios-ssn",
        "smb",
        "samba",
        "nfs",
        "afp",
        "iscsi",
        "ftp",
    ),
    "remote_access": ("ssh", "telnet", "ms-wbt-server", "rdp", "vnc", "winrm"),
    "proxy": ("http-proxy", "socks", "squid"),
    "device_control": ("modbus", "mqtt", "coap", "bacnet", "s7comm", "ethernet/ip"),
    "discovery": ("mdns", "ssdp", "upnp"),
    "media": ("rtsp", "airplay", "dlna", "dial"),
    "general_service": (),
    "unknown": (),
}

EXPOSURE_ROLE_PORTS: dict[ExposureRole, tuple[int, ...]] = {
    "administration": (),
    "api": (),
    "data_store": (1433, 1521, 27017, 3306, 5432, 6379, 9042, 9200, 11211),
    "file_sharing": (21, 139, 445, 548, 2049, 3260),
    "remote_access": (22, 23, 3389, 5900, 5985, 5986),
    "proxy": (1080, 3128),
    "device_control": (502, 1883, 5683, 47808),
    "discovery": (1900, 5353),
    "media": (554, 7000, 8008, 8009, 8554),
    "general_service": (),
    "unknown": (),
}

REVIEW_ROLES = frozenset(
    {
        "administration",
        "api",
        "data_store",
        "file_sharing",
        "remote_access",
        "proxy",
        "device_control",
        "unknown",
    }
)
PRIORITY_CLEARTEXT_TOKENS = frozenset(
    {"telnet", "modbus", "mqtt", "coap", "bacnet", "s7comm", "ethernet/ip"}
)
