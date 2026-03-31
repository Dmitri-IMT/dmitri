# ADR-004: Scan Methodology and Vulnerability Detection Workflow

## Context

The system aims to perform **end-to-end vulnerability scanning** within local networks using an embedded device.

To achieve this, it is necessary to define what a "scan" represents in the system, including:

- Inputs (targets, scope, configuration)
- Processing stages (pipeline)
- Outputs (structured findings)
- How vulnerabilities are identified and correlated

Unlike simple network scanners, this system must transform raw scan data into **actionable security findings**, combining network discovery, service identification, and vulnerability intelligence.

---

## Definition of a Scan

A **scan** is defined as a structured process that:

1. Receives a target (single IP, host list, or subnet)
2. Executes multiple scanning stages
3. Correlates collected data
4. Produces a set of **findings**

---

## Scan Pipeline Stages

The scanning workflow is divided into modular stages:

### 1. Host Discovery

Objective:
Identify active devices in the network.

Techniques:
- ICMP (ping sweep)
- ARP requests
- Nmap (`-sn`)

Output:
List of active hosts (IPs)

---

### 2. Port Enumeration

Objective:
Identify exposed ports (attack surface).

Techniques:
- TCP SYN scan (`-sS`)
- Fast scan (`-F`)
- Full scan (`-p-`)

Tradeoffs:

| Mode        | Speed | Coverage | Use Case |
|------------|------|----------|----------|
| -F         | High | Low      | Quick scan |
| -p-        | Low  | Full     | Deep scan |
| Custom     | Medium | Medium | Targeted scan |

Output:
List of open ports per host

---

### 3. Service & Version Detection

Objective:
Identify services running on open ports.

Techniques:
- Nmap `-sV`
- Banner grabbing

Tradeoffs:

| Mode              | Accuracy | Speed |
|-------------------|----------|------|
| --version-light   | Medium   | Fast |
| -sV (default)     | High     | Medium |
| --version-all     | Very High| Slow |

Output:
- Service name
- Product
- Version (if available)

---

### 4. Vulnerability Identification

Objective:
Map detected services to known vulnerabilities.

Techniques:

- Nmap NSE scripts (`-sC`, `--script vuln`)
- CVE lookup (external databases)
- Service fingerprint correlation

Examples:
- MySQL → check CVEs
- SMB → check known exploits
- HTTP → run Nikto

Output:
List of vulnerabilities per service

---

## Nmap Scan Modes and Tradeoffs

| Mode | Description | Use Case |
|------|------------|----------|
| -T4 | Faster execution | Default scanning |
| -F | Top ports only | Quick scan |
| -p- | All ports | Deep scan |
| -sV | Service detection | Required for vuln mapping |
| -sC | Default scripts | Basic enumeration |
| -A | Aggressive scan | High detail, high cost |

Decision:
- Use **-T4 + -F** for initial scans
- Use **-sV** for service detection
- Use **NSE selectively**, not `-A`, to reduce resource usage

---

## Vulnerability Data Correlation

Vulnerabilities are not directly discovered in all cases. They are derived by:

### 1. NSE Output Parsing

Extract:

CVE ID
Description
Severity (if available)
### 2. CVE Correlation

Process:

Identify service + version
Query vulnerability databases (future feature)

Sources:

NVD (National Vulnerability Database)
CVE
Vulners API

## 3. Heuristic Mapping

Examples of heuristic correlations:

- Open SMB + no authentication → Potential misconfiguration
- HTTP + outdated version → Likely vulnerable

---

## Scan Scheduling Strategy

Two main modes are defined:

### 1. On-Demand Scan
- Triggered manually
- Used for testing or investigation

### 2. Periodic Scan
- Scheduled execution (e.g., daily)
- Detects new devices and vulnerabilities

---

## Scan Scope

Supported targets:

- Single host (e.g., 192.168.1.10)
- Multiple hosts
- Subnet (e.g., 192.168.1.0/24)

---

## Definition of a Finding

A finding represents a security-relevant issue identified during scanning.


{
  "host": "192.168.15.10",
  "hostname": "",
  "port": 3306,
  "protocol": "tcp",
  "service": "mysql",
  "product": "MySQL",
  "version": "8.x",
  "vulnerability": {
    "cve_id": "CVE-XXXX-XXXX",
    "name": "Example vulnerability",
    "description": "Description of the issue",
    "severity": "high",
    "cvss_score": 8.5
  },
  "source": "nmap_nse",
  "timestamp": "2026-03-31T18:00:00Z"
}

## Decision

### The system will implement a multi-stage scanning pipeline composed of:

- Host discovery
- Port enumeration
- Service detection
- Vulnerability correlation

Each stage feeds the next and progressively enriches the dataset.

## Justification

This pipeline-based approach:

- Ensures modularity and scalability
- Reduces unnecessary processing
- Enables targeted scanning (only scan what matters)
- Aligns with industry-standard vulnerability scanning workflows


## Consequences
- Efficient use of embedded resources
- Clear separation of responsibilities per module
- Easy integration with backend and reporting systems
- Enables future expansion (web, cloud, database scanning)

## Scan Pipeline
[ INPUT ]
   |
   |  (IP / Subnet)
   v
+----------------------+
|   Host Discovery     |
| (Ping / ARP / Nmap)  |
+----------------------+
           |
           v
+----------------------+
|   Port Enumeration   |
| (Fast / Full Scan)   |
+----------------------+
           |
           v
+----------------------+
| Service Detection    |
| (Nmap -sV)           |
+----------------------+
           |
           v
+----------------------+
| Vulnerability        |
| Identification       |
| (NSE / CVE / Tools)  |
+----------------------+
           |
           v
+----------------------+
| Findings Generation  |
| (JSON Structured)    |
+----------------------+
           |
           v
        [ OUTPUT ]