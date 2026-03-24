# ADR-002: Scanning Tools Selection

## Context

The proposed system aims to perform network discovery, identification of open ports, running services, and potential vulnerabilities within local networks, focusing on small and medium-sized businesses.

Due to the constraints of embedded hardware environments (such as Raspberry Pi), including limitations in CPU, memory, and storage, it is necessary to select tools that are efficient, lightweight, and capable of providing meaningful security insights.

Additionally, the solution must be modular, allowing future expansion without compromising system performance.

---

## Context

The proposed system is not limited to network scanning, but aims to perform **comprehensive vulnerability discovery and analysis** across devices connected to local networks, with a focus on small and medium-sized environments.

Vulnerability scanning is a multi-domain activity and cannot be addressed by a single type of tool. Different components of an IT environment require distinct approaches, including:

- **Network scanners**, which identify active hosts, open ports, exposed services, and misconfigurations in network infrastructure;
- **Web application scanners**, which detect vulnerabilities such as SQL injection, cross-site scripting (XSS), and broken authentication mechanisms;
- **Database scanners**, which assess weaknesses in database configurations, access controls, and patch levels;
- **Cloud and container scanners**, which evaluate misconfigurations and vulnerabilities in modern infrastructure environments;
- **Code analysis tools (SAST/DAST)**, which identify vulnerabilities during development and runtime.

Within this context, the proposed solution focuses primarily on **network-based vulnerability discovery**, serving as the foundation for identifying exposed services and potential entry points. From this foundation, specialized scanning modules can be applied depending on the detected services (e.g., web, database, SMB).

The system is designed as a **modular vulnerability scanning platform**, where each stage builds upon the previous one:

1. Network discovery (hosts and topology)
2. Port discovery (attack surface identification)
3. Service and version detection
4. Targeted vulnerability analysis (based on detected services)

Due to the constraints of embedded hardware environments (such as Raspberry Pi), including limited CPU, memory, and storage, the selection of tools must balance:

- Resource efficiency
- Detection coverage
- Ease of integration
- Output standardization for processing and reporting

Therefore, the goal is not to replicate full-scale enterprise vulnerability scanners (such as Nessus or Qualys), but to design a **lightweight, extensible, and efficient vulnerability scanning solution** that provides meaningful security insights within constrained environments.

---

## Evaluated Tools

### Nmap

A widely used open-source tool for network exploration and security auditing.

#### Capabilities

- Host discovery (`-sn`)
- Port scanning:
  - SYN Scan (`-sS`)
  - TCP Connect (`-sT`)
  - UDP Scan (`-sU`)
- Service/version detection (`-sV`)
- OS detection (`-O`)

#### Advantages

- Low resource usage
- Highly flexible
- Cross-platform
- Easy integration with scripts

#### Disadvantages

- Requires networking knowledge
- Advanced features may be complex

---

### Nmap Scripting Engine (NSE)

An extension of Nmap that allows execution of scripts for vulnerability detection and enumeration.

#### Categories

- `default`
- `safe`
- `vuln`
- `auth`
- `discovery`

#### Relevant Scripts

- `vulners`
- `vulscan`
- `http-enum`
- `ssh-auth-methods`
- `smb-vuln*`

#### Advantages

- Extends Nmap capabilities significantly
- Enables vulnerability detection without heavy tools

---

### CrackMapExec

A tool focused on post-exploitation and enumeration in Windows/SMB environments.

#### Capabilities

- User and group enumeration
- Credential validation
- Remote command execution
- Share and permission analysis

#### Advantages

- Lightweight compared to Metasploit
- Highly effective in corporate environments

#### Disadvantages

- Does not perform network discovery
- Requires credentials or context

---

### Nikto

A web vulnerability scanner.

#### Capabilities

- Detection of insecure configurations
- Identification of known web server vulnerabilities

#### Advantages

- Lightweight
- Easy to integrate

#### Disadvantages

- Limited to web services

---

### testssl.sh

A tool for SSL/TLS security analysis.

#### Capabilities

- Protocol analysis
- Detection of weak ciphers
- Identification of insecure configurations

---

### sqlmap

Scan databases. An automated SQL injection detection and exploitation tool.

#### Capabilities

- Detects SQL injection vulnerabilities
- Identifies database types
- Extracts database information

#### Disadvantages

- Limited to web applications
- Can be intrusive

---

### masscan

A high-performance port scanner.

#### Advantages

- Extremely fast
- Suitable for large-scale scanning

#### Disadvantages

- Does not detect services
- Does not identify vulnerabilities

---

### Metasploit

A full exploitation framework.

#### Disadvantages

- High resource consumption
- Complex setup
- Not suitable for embedded environments

---

### OpenVAS / Greenbone

A comprehensive vulnerability scanner.

#### Disadvantages

- Very resource-intensive
- Complex setup
- High CPU and memory usage

---

## Scoring Rubric

| Tool            | Resource Usage | Detection Coverage | Integration | Output Parsing | Use Case Fit | Final Score |
|----------------|---------------|--------------------|-------------|----------------|--------------|-------------|
| Nmap           | 9             | 9                  | 10          | 9              | 10           | 9.5         |
| Nmap NSE       | 8             | 10                 | 9           | 9              | 10           | 9.5         |
| CrackMapExec   | 8             | 7                  | 8           | 7              | 8            | 7.6         |
| Nikto          | 7             | 7                  | 8           | 7              | 7            | 7.2         |
| testssl.sh     | 7             | 7                  | 8           | 7              | 7            | 7.2         |
| sqlmap         | 7             | 8                  | 6           | 7              | 7            | 7.0         |
| masscan        | 10            | 5                  | 7           | 7              | 6            | 7.0         |
| Metasploit     | 3             | 10                 | 6           | 6              | 4            | 5.8         |
| OpenVAS        | 2             | 10                 | 5           | 6              | 3            | 5.2         |

---

## Decision

The selected toolset for the embedded system consists of:

- **Nmap** as the core network scanning engine
- **Nmap NSE** for vulnerability detection
- **CrackMapExec** for SMB/Windows environment analysis
- **Nikto** and **testssl.sh** for web service analysis
- **sqlmap** for future expansion in web vulnerability analysis

---

## Justification

Nmap was selected as the core scanning tool due to its efficiency, flexibility, and low resource consumption, making it ideal for embedded environments.

The Nmap Scripting Engine (NSE) significantly enhances its capabilities by enabling automated vulnerability detection without requiring heavy external tools.

More comprehensive solutions such as OpenVAS and Metasploit were excluded from the core architecture due to their high resource consumption and complexity, which make them unsuitable for embedded hardware.

Complementary tools such as CrackMapExec, Nikto, and testssl.sh were included to provide specialized analysis capabilities in specific contexts, such as SMB environments and web services.

This combination ensures a balance between performance, detection coverage, and feasibility within constrained environments.

---

## Consequences

- Low resource consumption on embedded devices
- High flexibility and modularity
- Good coverage of network and vulnerability detection
- Easy integration with backend systems
- Scalable architecture for future enhancements