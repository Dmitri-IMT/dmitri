import psutil
import ipaddress
import subprocess
import platform
import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
import re


def get_network_info():
    
    local_ip = get_local_ip()
    interfaces = psutil.net_if_addrs()
    for interface in interfaces:

        for addr in interfaces[interface]:

            if addr.family.name == "AF_INET":

                if addr.address == local_ip:

                    ip = addr.address
                    netmask = addr.netmask

                    network = ipaddress.IPv4Network(
                        f"{ip}/{netmask}",
                        strict=False
                    )

                    return {
                        "ip": ip,
                        "netmask": netmask,
                        "network": str(network)
                    }

    raise Exception("Active network interface not found")


def get_local_ip():

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    return ip


def ping_host(ip):

    system = platform.system()
    if system == "Windows":
        command = ["ping", "-n", "1", "-w", "1000", ip]
    else:
        command = ["ping", "-c", "1", "-W", "1", ip]

    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return result.returncode == 0


def ping_sweep(network, local_ip):

    print(f"[+] Starting Ping Sweep on {network}")

    net = ipaddress.IPv4Network(network, strict=False)
    live_hosts = []
    ips = [str(ip) for ip in net.hosts() if str(ip) != local_ip]

    MAX_THREADS = 50

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        future_to_ip = {
            executor.submit(ping_host, ip): ip for ip in ips
        }

        for future in as_completed(future_to_ip):

            ip = future_to_ip[future]

            try:

                if future.result():

                    print(f"[LIVE] {ip}")

                    live_hosts.append(ip)

            except Exception as e:

                print(f"Error scanning {ip}: {e}")

    return live_hosts


def nmap_discovery(network, local_ip):

    print(f"[+] Running Nmap Host Discovery on {network}")

    try:

        result = subprocess.run(
            [r"C:\Program Files (x86)\Nmap\nmap.exe", "-sn","-T3", network],
            capture_output=True,
            text=True
        )

        hosts = []

        for line in result.stdout.split("\n"):

            if "Nmap scan report for" in line:

                match = re.search(r"\d+\.\d+\.\d+\.\d+", line)

                if match:

                    ip = match.group()

                    # remove seu próprio host
                    if ip != local_ip:
                        hosts.append(ip)

        return list(set(hosts))

    except Exception as e:

        print("Error running nmap:", e)

        return []


def merge_results(ping_hosts, nmap_hosts):

    combined = set(ping_hosts) | set(nmap_hosts)

    hosts = []

    for ip in sorted(combined):

        host = {
            "ip": ip,
            "hostname": "",
            "state": "up",
            "open_ports": []
        }

        hosts.append(host)

    return hosts


def save_results(network_info, hosts):

    data = {
        "network": network_info["network"],
        "local_ip": network_info["ip"],
        "netmask": network_info["netmask"],
        "hosts": hosts
    }

    with open("network_scan.json", "w") as f:

        json.dump(data, f, indent=4)

    print("\n[+] Results saved to network_scan.json")


def run():

    print("[*] Detecting network information...")

    net_info = get_network_info()

    print(f"Local IP: {net_info['ip']}")
    print(f"Network: {net_info['network']}")

    ping_hosts = ping_sweep(net_info["network"], net_info["ip"])

    nmap_hosts = nmap_discovery(net_info["network"], net_info["ip"])

    hosts = merge_results(ping_hosts, nmap_hosts)

    save_results(net_info, hosts)


if __name__ == "__main__":
    run()