import json
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

NMAP_PATH = r"C:\Program Files (x86)\Nmap\nmap.exe"

MAX_THREADS = 5


def load_scan():

    with open("network_scan.json", "r") as f:
        return json.load(f)


def save_scan(data):

    with open("network_scan.json", "w") as f:
        json.dump(data, f, indent=4)


def scan_ports(ip):

    print(f"[+] Scanning ports on {ip}")

    try:

        result = subprocess.run(
            [NMAP_PATH, "-p-", "--min-rate", "1000", "-T4", "-Pn", ip],
            capture_output=True,
            text=True
        )

        open_ports = []

        for line in result.stdout.split("\n"):

            match = re.match(r"(\d+)/tcp\s+open", line)

            if match:

                port = int(match.group(1))
                open_ports.append(port)

        print(f"[OPEN PORTS] {ip}: {open_ports}")

        return ip, open_ports

    except Exception as e:

        print(f"Error scanning {ip}: {e}")
        return ip, []


def run():

    print("[*] Loading hosts from network_scan.json")

    data = load_scan()

    hosts = [host["ip"] for host in data["hosts"]]

    results = {}

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        futures = {executor.submit(scan_ports, ip): ip for ip in hosts}

        for future in as_completed(futures):

            ip, ports = future.result()

            results[ip] = ports

    for host in data["hosts"]:

        ip = host["ip"]

        if ip in results:

            host["open_ports"] = results[ip]

    save_scan(data)

    print("\n[+] Port scan finished and saved")


if __name__ == "__main__":
    run()