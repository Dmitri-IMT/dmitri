---
type: Module
title: scanner/errors — scan exception hierarchy
description: The scan exception hierarchy that encodes the contingency policy — fatal, unit, transient, cancelled, budget, and circuit-breaker failures.
resource: hardware-agent/src/agent/scanner/errors.py
tags: [hardware-agent, scanner, errors, contingency]
timestamp: 2026-09-12T21:23:47Z
---

# scanner/errors — scan exception hierarchy

## Purpose

`errors.py` defines the exception taxonomy that encodes the ADR-010 contingency policy. Where a
failure lands in this hierarchy decides whether the pipeline retries the unit, skips it, trips the
breaker, or aborts — and how [`ScanRunner`](/hardware-agent/scanner/runner.md) tags the partial
result's `terminated_by`.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `ScanError` | Base class for all scan failures. | `errors.py:4` |
| `FatalScanError` | Unrecoverable (e.g. Nmap binary missing) — aborts the run. | `errors.py:8` |
| `UnitScanError` | A single batch/host failed after retries — the unit is skipped. | `errors.py:12` |
| `TransientScanError` | A retryable blip (name-resolution/connection reset) — retried by the stage. | `errors.py:16` |
| `ScanCancelled` | Raised when the cancel event is set — maps to `user_cancel`. | `errors.py:20` |
| `BudgetExceeded` | A timeout/deadline was hit — maps to `timeout`. | `errors.py:24` |
| `CircuitBreakerError` | Subclass of `BudgetExceeded`; too many units failed — aborts the stage, maps to `error`. | `errors.py:28` |
| `UnsupportedScanDepth` | Subclass of `FatalScanError`; refuses an unavailable NSPi depth before active scan work. | `errors.py:32` |

## How it connects

- **Raised by** — [nmap](/hardware-agent/scanner/nmap.md) (`run_xml` classification) and
  [stages](/hardware-agent/scanner/stages.md) (retry wrapper + circuit breaker).
- **Caught by** — [`ScanRunner._run()`](/hardware-agent/scanner/runner.md)'s `except` ladder, which
  translates each class into a completed/partial/failed outcome.
- Re-exported from `scanner/__init__.py` alongside `NmapRunner`.

## Notes / gotchas

- `CircuitBreakerError` **is-a** `BudgetExceeded`, so ordering matters: the runner catches
  `BudgetExceeded` and then `isinstance`-checks for the breaker to pick `error` vs `timeout`.

# Citations

[1] [ADR-010 — scan contingency policy](../../../../docs/adr/ADR-010-scan-contingency-policy.md)
