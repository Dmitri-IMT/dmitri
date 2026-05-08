---
description: When wiring new modules or parameters, trace ALL call paths — especially the TUI ScanRunner path that bypasses ScanOrchestrator.run()
globs: hardware-agent/src/**
alwaysApply: false
---

# Integration: trace all call paths

When wiring a new module into the codebase, trace **every** call path that
reaches the affected code — not just the primary pipeline.

## TUI scan path

The TUI has its own scan runner (`ScanRunner` in `scanner.py`) that **bypasses
`ScanOrchestrator.run()`** and calls discovery functions directly:

```
ScanProgressScreen → ScanRunner → ScanOrchestrator (manual stage calls)
```

Any new parameter added to the orchestrator (e.g. `workspace_root`) **must**
also be threaded through `ScanRunner` and `ScanProgressScreen` so TUI-initiated
scans receive it.

## Checklist before marking integration complete

1. Grep for every constructor and call site of the changed class.
2. Verify each call site passes the new parameter.
3. Pay special attention to the TUI path above — it is the most common source
   of missed wiring.
