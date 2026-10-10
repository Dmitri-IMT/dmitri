# Scan report design references

Research consulted on 2026-09-29 while improving Dmitri's explained scan PDF. These references
inform information hierarchy and caveats; the report uses Dmitri's own scan data and language.

## Patterns used

- **Separate executive summary from details.** Rapid7's InsightVM executive report groups an
  environment overview, vulnerabilities, and remediation into readable sections with visuals.
  Dmitri applies this as a plain-language summary followed by prioritized findings and a separate
  technical PDF. [Rapid7 Executive Summary Report](https://docs.rapid7.com/insightvm/executive-report/)
- **Show severity distributions and asset context.** Microsoft Defender's vulnerable-device report
  uses severity and device charts to make the scope of exposure understandable. Dmitri uses
  directly labelled bars for finding records by severity and affected devices, without implying
  changes over time from a single scan. [Microsoft vulnerable devices report](https://learn.microsoft.com/en-us/defender-vulnerability-management/tvm-vulnerable-devices-report)
- **Keep remediation actionable.** Qualys separates summary and detail views for vulnerability
  prioritization. Dmitri provides an ordered plan, device/service explanations and individual
  validation, correction and verification steps, followed by the full finding register.
  [Qualys VMDR Prioritization Report](https://docs.qualys.com/en/vmdr/latest/mergedProjects/prioritize_your_vulnerabilities/threat/read_prioritization_report.htm)
- **Keep quick and detailed reading paths distinct.** Tenable distinguishes dashboard exports from
  detailed PDF reports; Dmitri keeps its explained and technical downloads as separate variants.
  [Tenable dashboard export](https://docs.tenable.com/vulnerability-management/Content/Dashboards/ExportADashboard.htm)

## Interpretation rules

- Finding records are scan observations and may not equal a count of unique vulnerabilities.
- CVSS describes technical severity; it is not a measure of the whole network's risk. FIRST
  explicitly warns against using CVSS Base alone to assess risk.
- A scan is a snapshot of responsive devices. No finding in one scan does not prove that a network
  is secure or that an intrusion never occurred.
- Charts use labelled counts and zero-based proportional bars. Historical trend charts need
  comparable scans and are excluded from a single-scan report.

Sources: [FIRST CVSS v4.0 User Guide](https://www.first.org/cvss/user-guide), especially “CVSS Base
Score Measures Severity, not Risk”; market product documentation linked above. Pages consulted
2026-09-29; where a page does not state a publication date, the consultation date is recorded.

## Educational expansion — 2026-10-06

The explained PDF now includes all devices, count charts for severity/devices/evidence/service
functions, a conditional incident diagram, service-specific explanations and a plain-language
glossary. Records are grouped by device, endpoint and evidence basis; the complete register
preserves every record. No CVE correlation or service identification is promoted to demonstrated
exploitation. Advisory effect labels use explicit terms from already stored descriptions.

Primary sources consulted for concrete interpretation limits and remediation guidance:

- [Nmap service detection](https://nmap.org/book/vscan.html): treat product and version detection as
  evidence to validate, rather than a guarantee of the exact installed package.
- [Debian security FAQ](https://www.debian.org/security/faq): account for security fixes backported
  into distribution packages; compare complete package revisions and vendor guidance.
- [Microsoft SMBv1 guidance](https://learn.microsoft.com/en-us/windows-server/storage/file-server/troubleshoot/detect-enable-and-disable-smbv1-v2-v3): review dependencies before disabling the legacy protocol and verify the resulting configuration.
- [OpenSSH security notices](https://www.openssh.org/security.html): CVE-2023-38408 concerns
  ssh-agent and agent-forwarding prerequisites, not any responding SSH server.
- [NVD CVE-2011-2523](https://nvd.nist.gov/vuln/detail/CVE-2011-2523): the vsftpd issue concerns a
  maliciously modified distribution; a version banner does not establish package provenance.
- [CISA StopRansomware guide](https://www.cisa.gov/stopransomware/ransomware-guide): apply controlled
  network separation and protect backups; verify restoration and normal operation after changes.
