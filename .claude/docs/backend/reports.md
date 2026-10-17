---
type: Module
title: Backend explained and technical scan reports
description: Localized educational PDF reports with a clickable, page-numbered contents list, complete device inventory, evidence-aware explanations, vector charts, remediation checks and the full finding register.
resource: backend/src/api/services/reports.py
tags: [backend, reports, pdf, scans, evidence, accessibility]
timestamp: 2026-10-06T00:00:00Z
---

# Backend explained and technical scan reports

## Purpose

`reports.py` assembles completed, organization-scoped scan reports. The explained report teaches
the reader how to interpret findings and act on them; the technical report preserves the scan,
risk and optional AI data. The educational explanations work without an AI provider and cover
English, Brazilian Portuguese and Russian.

## Key classes / functions

| Name | Responsibility | Source |
|------|----------------|--------|
| `build_scan_report()` | Gates on a completed scan, loads the requested language's optional AI analysis and assembles either report variant. | `backend/src/api/services/reports.py:24` |
| `_educational_evidence()` | Batch reads relevant CVE cache entries and counts unfinished/failed enrichment jobs for this scan; performs no external advisory requests or writes. | `backend/src/api/services/reports.py:71` |
| `build_report_education()` | Includes every host, groups findings by device/endpoint/evidence basis, adds service-review explanations and preserves every finding in an indexed register. | `backend/src/api/services/report_education.py:100` |
| `service_family()` | Classifies an observed service name without guessing from its port. | `backend/src/api/services/report_education.py:24` |
| `text()` / `guide()` | Localized terminology, practical explanations, conditional impacts and validation/correction/verification steps by service family. | `backend/src/api/services/report_education_copy.py:307`, `:311` |
| `append_education()` | Builds teaching chapters, full inventories, issue groups, a conditional incident diagram, action plan, glossary, finding register and source links. Retains optional AI recommendations. | `backend/src/api/services/report_education_pdf.py:141` |
| `EvidenceBars` / `AttackPath` | Vector count charts and a conditional incident chain; large charts split while retaining their original common scale. | `backend/src/api/services/report_education_pdf.py:39`, `:98` |
| `ScanReportDocTemplate` | Stable chapter/device/group bookmarks for the PDF outline and its multi-pass, page-numbered clickable contents list. | `backend/src/api/services/report_pdf.py:176` |

## How it connects

The report routes in [routers](/backend/routers.md) authorize the reader, call `build_scan_report`,
and pass the resulting `ScanReportResponse` to `render_scan_report_pdf`. The assembly reads
[scan/risk projections](/backend/services.md) and [optional AI analysis](/backend/ai.md).
Explained `sections` is a single typed `ExplainedReportSections` payload: education, scan metadata,
summary, actions and limitations. AI explanations enrich the full finding register. There is no
parallel executive-summary document or nested `education` blob. The cover derives counts and
host charts from that same inventory and register; `append_education` is the only body renderer.
Technical `sections` is `TechnicalReportSections`, with scan/risk/optional AI models, and downloads
as JSON. The response validates the payload and content type against `kind`. Download URLs are
unchanged; the OpenAPI contract and generated frontend types describe both payloads.

## Notes / gotchas

- Device headings and charts use a readable scan-derived name plus the IP. Type and
  OS are estimates; identity confidence, supporting observations and conflicts are
  printed in each device card. An exact model is shown only when present in the
  stored device profile; a network-adapter vendor alone does not identify a model.
- The cover separates the brand from a short report title. The contents use a single
  column with an independent, right-aligned page-number style so multi-digit page
  numbers cannot inherit the subitem indentation. This scan fits on one contents page;
  longer reports can still split instead of reducing text below the readable sizes.
- A `nmap_vulners`/`nvd` CVE association stays a correlation even if its risk snapshot uses
  `confidence=confirmed`. A published advisory does not establish target applicability.
- SMBv1 and SSH password-method observations have specific explanations. Additional review
  services and a `bindshell` identification remain service observations with zero new findings,
  no invented CVE and no inferred severity.
- Zero-alert devices remain visible. They are favourable observations within the checks performed,
  with explicit coverage, reachability and identity limits; none is certified safe.
- Advisory effect labels use explicit terms from locally stored English descriptions and identify
  the advisory's general consequence, not a demonstrated consequence on the scanned machine.
  Missing or unclassified descriptions remain explicit. Links support individual validation.
- The vsftpd backdoor and OpenSSH ssh-agent examples include their specific prerequisites;
  neither is inferred from a product name or banner alone.
- Long observations remain escaped, splittable paragraphs. Inventory and register tables repeat
  their headers, including device identity on continued inventory pages. Unicode fonts are embedded.
- Tests cover all languages, long escaped evidence, zero-alert hosts, unassigned records,
  grouping boundaries, service-only reviews, local-cache enrichment scope and chart pagination.
