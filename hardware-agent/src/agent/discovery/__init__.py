"""Discovery stages used by the hardware-agent scan pipeline."""

from .network_discovery import discover_hosts
from .port_discovery import scan_ports_batch, scan_udp_ports_batch
from .service_detection import detect_services
from .vulnerability_detection import run_targeted_nse_scan

__all__ = [
    "discover_hosts",
    "scan_ports_batch",
    "scan_udp_ports_batch",
    "detect_services",
    "run_targeted_nse_scan",
]
