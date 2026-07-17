# ARCHITECTURE — {Feature title}

## System context

Where this fits in the agent pipeline: discovery → port scan → NSE/deep inspection →
normalization (`ScanPayload`) → TUI / persistence. Name the modules touched under
`hardware-agent/src/agent/`.

## Data model / contracts

{Config constants, `ScanPayload` / pydantic field changes, nmap flag sets, exit codes.}

## New files and naming (mandatory)

| Layer | Path | Notes |
|-------|------|-------|
| Config | `hardware-agent/src/agent/config.py` | constants / scan_mode Literal |
| Discovery | `hardware-agent/src/agent/discovery/…` | scan logic |
| Normalize | `hardware-agent/src/agent/normalize/contracts.py` | payload shape |
| Scan runner | `hardware-agent/src/agent/scanner/runner.py` (`ScanRunner`) | thread new params (CLAUDE.md rule) |
| TUI screen | `hardware-agent/src/agent/tui/screens/scan_progress.py` (`ScanProgressScreen`) | thread new params |

> Include every call site a new orchestrator/runner parameter passes through — at minimum
> `ScanRunner` and `ScanProgressScreen` (CLAUDE.md integration rule).

## Constraints

- No new infrastructure by agents — flag `HUMAN_INFRA_REQUIRED` if the feature needs new
  hardware, a daemon, or external tooling.
- Reuse the existing nmap runner / merge helpers; do not invent parallel scan paths.

## Testing expectations

- Unit tests under `hardware-agent/tests/unit/` for new constants / helpers.
- Mirror the nearest existing test (e.g. `test_scan_mode_scripts.py`).
