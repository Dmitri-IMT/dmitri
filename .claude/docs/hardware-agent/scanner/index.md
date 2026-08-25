# hardware-agent / scanner

The scan engine, split into single-responsibility modules. `runner.py` owns the worker thread and
drives the whole pipeline; the rest are the pieces it composes. Source lives at
`hardware-agent/src/agent/scanner/`.

* [runner](./runner.md) — `ScanRunner`: the worker thread, cancellation, deadline guards, and the `_run()` pipeline body that drives discovery → ports → deep inspection → normalize.
* [stages](./stages.md) — The threaded port and deep-inspection stages, with per-unit retry, circuit breaker, and the `HostInfo`→`HostPayload` builder.
* [nmap](./nmap.md) — NmapRunner / LoggedNmapRunner — execute Nmap, log argv and failed stderr, parse XML, and retain per-run artifacts.
* [models](./models.md) — The in-memory scan dataclasses: `HostInfo`, `PortInfo`, `ServiceInfo`, `ScriptResult`.
* [errors](./errors.md) — The scan exception hierarchy that encodes the contingency policy (fatal / unit / transient / cancelled / budget / circuit-breaker).
* [progress](./progress.md) — `ScanEvent` stream, the `ScanReporter` protocol, and the `ProgressMapper` that turns events into a monotonic 0–100% for the UI.
* [workspace](./workspace.md) — The on-disk `results/` + `logs/` layout: result serialization, run-folder logging, and pruning.
