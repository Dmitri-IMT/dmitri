"""Static topology checks for the local targeted-scan lab Compose files."""

import json
import ipaddress
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
COMPOSE = "docker/pi-simulator/compose.yaml"
LAB_COMPOSE = "docker/pi-simulator/compose.lab.yaml"
NSPI_COMPOSE = "docker/pi-simulator/compose.nspi.yaml"
AGENT_DOCKERFILE = "docker/pi-simulator/agent.Dockerfile"
TARGET_IPS = {
    "lab-web": "172.31.13.2",
    "lab-ssh": "172.31.13.3",
    "lab-ftp": "172.31.13.4",
    "lab-smb": "172.31.13.5",
    "lab-telnet": "172.31.13.6",
}


def compose_config(*paths: str) -> dict:
    env = os.environ.copy()
    env.update(
        BACKEND_URL="https://example.invalid",
        DEVICE_ID="static-topology-test",
        DEVICE_PRIVATE_KEY="00" * 32,
    )
    if LAB_COMPOSE in paths:
        env["SIMULATOR_APP_SUBNET"] = "172.31.12.0/24"
    result = subprocess.run(
        ["docker", "compose", *[part for path in paths for part in ("-f", path)], "config", "--format", "json"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class TargetedLabTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = compose_config(COMPOSE, LAB_COMPOSE)

    def test_target_network_is_private_and_small(self) -> None:
        targets = self.config["networks"]["targets"]
        self.assertTrue(targets["internal"])
        self.assertEqual(
            targets["ipam"]["config"][0]["subnet"], "172.31.13.0/28"
        )
        scan_range = ipaddress.ip_network(targets["ipam"]["config"][0]["subnet"])
        scan_subnet = ipaddress.ip_network("172.31.13.0/29")
        gateway = ipaddress.ip_address(targets["ipam"]["config"][0]["gateway"])
        self.assertEqual(str(gateway), "172.31.13.14")
        self.assertNotIn(gateway, scan_subnet)
        self.assertTrue(all(ipaddress.ip_address(ip) in scan_subnet for ip in TARGET_IPS.values()))
        app_network = ipaddress.ip_network(
            self.config["networks"]["default"]["ipam"]["config"][0]["subnet"]
        )
        self.assertFalse(scan_range.overlaps(app_network))

    def test_agent_is_dual_homed_and_app_services_are_not_on_target_network(self) -> None:
        services = self.config["services"]
        self.assertIn("Lab seed already present", " ".join(services["seed"]["command"]))
        self.assertIn("/shared/agent.env", " ".join(services["seed"]["command"]))
        self.assertEqual(set(services["agent"]["networks"]), {"default", "targets"})
        agent_target_ip = services["agent"]["networks"]["targets"]["ipv4_address"]
        self.assertEqual(agent_target_ip, "172.31.13.13")
        self.assertNotIn(ipaddress.ip_address(agent_target_ip), ipaddress.ip_network("172.31.13.0/29"))
        for name in ("db", "migrate", "api", "worker", "seed"):
            self.assertEqual(set(services[name]["networks"]), {"default"}, name)

    def test_targets_have_unique_fixed_ips_and_no_published_ports(self) -> None:
        services = self.config["services"]
        self.assertTrue(set(TARGET_IPS).issubset(services))
        observed_ips = set()
        for name, expected_ip in TARGET_IPS.items():
            service = services[name]
            self.assertNotIn("ports", service, name)
            self.assertEqual(set(service["networks"]), {"targets"}, name)
            ip = service["networks"]["targets"]["ipv4_address"]
            self.assertEqual(ip, expected_ip, name)
            self.assertIn(ipaddress.ip_address(ip), ipaddress.ip_network(
                self.config["networks"]["targets"]["ipam"]["config"][0]["subnet"]
            ), name)
            observed_ips.add(ip)
        self.assertEqual(len(observed_ips), len(TARGET_IPS))

    def test_connect_only_compose_has_no_new_target_services_or_lab_network(self) -> None:
        config = compose_config(NSPI_COMPOSE)
        self.assertEqual(set(config["services"]), {"agent", "target"})
        self.assertNotIn("targets", config["networks"])
        new_targets = set(TARGET_IPS) - {"target"}
        self.assertTrue(new_targets.isdisjoint(config["services"]))


class TargetedToolImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dockerfile = (ROOT / AGENT_DOCKERFILE).read_text(encoding="utf-8")

    def test_external_tool_releases_and_sources_are_pinned(self) -> None:
        for pin in (
            "ARG FFUF_VERSION=2.1.0",
            "ARG FFUF_AMD64_SHA256=fc2c82736c14dcbea4daf3d3cf3878c1c4773008ba45c2bc0fceba7d17b40bb5",
            "ARG NIKTO_VERSION=2.6.0",
            "ARG NIKTO_COMMIT=69681e2e4213c15b85a90c53b2169ecb2a88fb01",
            "ARG NIKTO_DB_SHA256=e221b0ab6db1b3dec26a11674a68216fc6ee690b8b20f07056d4e4ae33ed30a2",
            "ARG ENUM4LINUX_VERSION=1.3.10",
            "ARG ENUM4LINUX_COMMIT=f34e7bb3bc2bcd10267a7257fb3658154434ccf4",
            "ARG TESTSSL_VERSION=3.0.8+dfsg-1",
            "ARG NMAP_VULNERS_COMMIT=47c73ec5addcaad04904f233c6f85dfe76c58ed5",
            "ARG NMAP_VULNERS_SHA256=96ab184c1c2da56a184f2a6e156614c9daf9e7d35142ee6c210bd54a1b312cd4",
        ):
            with self.subTest(pin=pin):
                self.assertIn(pin, self.dockerfile)
        self.assertIn("sha256sum --check --status", self.dockerfile)

    def test_installed_tool_commands_and_data_match_targeted_adapters(self) -> None:
        for dependency in (
            "nmap", "testssl.sh=${TESTSSL_VERSION}", "dirb", "smbclient",
            "samba-common-bin", "python3-ldap3", "python3-yaml", "python3-impacket",
        ):
            with self.subTest(dependency=dependency):
                self.assertIn(dependency, self.dockerfile)
        for adapter_path in (
            "/opt/dmitri/tools/nikto-${NIKTO_VERSION}/program/databases/db_tests",
            "/opt/dmitri/tools/enum4linux-ng-${ENUM4LINUX_VERSION}/enum4linux-ng.py",
            "/usr/share/wordlists/dirb/common.txt",
            "/usr/share/dirb/wordlists/common.txt",
        ):
            with self.subTest(adapter_path=adapter_path):
                self.assertIn(adapter_path, self.dockerfile)
        self.assertIn("/usr/local/bin/enum4linux-ng", self.dockerfile)
        self.assertIn("/usr/bin/python3", self.dockerfile)
        self.assertIn("/usr/local/bin/nikto", self.dockerfile)

    def test_local_agent_image_supplies_scan_lock_contract(self) -> None:
        self.assertIn(
            "COPY hardware-agent/packaging/scan-lock-path /usr/lib/dmitri/scan-lock-path",
            self.dockerfile,
        )
        self.assertIn("/var/lib/dmitri/scan.lock", self.dockerfile)

    def test_nmap_vulners_is_pinned_registered_and_resolvable(self) -> None:
        for setup_step in (
            "git clone https://github.com/vulnersCom/nmap-vulners.git /tmp/nmap-vulners",
            "install -m 0644 /tmp/nmap-vulners/vulners.nse /usr/share/nmap/scripts/vulners.nse",
            "nmap --script-updatedb",
            "nmap --script-help vulners",
        ):
            with self.subTest(setup_step=setup_step):
                self.assertIn(setup_step, self.dockerfile)

    def test_lab_start_reconciles_changes_without_volume_deletion(self) -> None:
        script = (ROOT / "simulator.sh").read_text(encoding="utf-8")
        lab_start = script.split("  lab-start)", 1)[1].split("  scan|lab-scan)", 1)[0]
        self.assertIn('"${LAB_COMPOSE[@]}" up -d --build', lab_start)
        self.assertNotIn(" down -v", lab_start)
        self.assertNotIn(" ps -q", lab_start)


if __name__ == "__main__":
    unittest.main()
