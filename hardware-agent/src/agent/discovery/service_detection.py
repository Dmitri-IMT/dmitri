import json
import subprocess
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

NMAP_PATH = r"C:\Program Files (x86)\Nmap\nmap.exe"

MAX_THREADS = 10


def detect_services(ip, ports):

    if not ports:
        return []

    port_string = ",".join(map(str, ports))

    print(f"[+] Detecting services on {ip} ({port_string})")

    try:

        result = subprocess.run(
            [
                NMAP_PATH,
                "-sV",
                "--version-intensity", "5",
                "--script=banner",
                "-p", port_string,
                "-T4",
                "-Pn",
                "-oX", "-",
                ip
            ],
            capture_output=True,
            text=True
        )
        print(result.stdout)

        if not result.stdout.strip():
            print(f"[!] Empty Nmap result for {ip}")
            return []

        root = ET.fromstring(result.stdout)

       
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]

        services = []

        for host in root.findall("host"):

            ports_node = host.find("ports")

            if ports_node is None:
                continue

            for port in ports_node.findall("port"):

                state = port.find("state").get("state")

                if state != "open":
                    continue

                port_id = int(port.get("portid"))

                service = port.find("service")

                service_name = service.get("name", "") if service is not None else ""
                product = service.get("product", "") if service is not None else ""
                version = service.get("version", "") if service is not None else ""

                services.append({
                    "port": port_id,
                    "service": service_name,
                    "product": product,
                    "version": version
                })

        return services

    except Exception as e:

        print(f"Error scanning {ip}: {e}")

        return []

def main():

    print("[*] Loading network_scan.json")

    with open("network_scan.json", "r") as f:
        data = json.load(f)

    hosts = data["hosts"]

    futures = {}

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        for host in hosts:

            ip = host["ip"]
            ports = host["open_ports"]

            future = executor.submit(detect_services, ip, ports)

            futures[future] = host

        for future in as_completed(futures):

            host = futures[future]

            services = future.result()

            host["services"] = services

            print(f"[SERVICES] {host['ip']} -> {len(services)} detected")

    with open("network_scan.json", "w") as f:

        json.dump(data, f, indent=4)

    print("\n[+] Service detection completed")


if __name__ == "__main__":
    main()