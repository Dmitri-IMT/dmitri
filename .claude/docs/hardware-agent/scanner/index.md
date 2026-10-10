# hardware-agent / scanner

The scan engine, split into single-responsibility modules. `runner.py` owns the worker thread and
drives the whole pipeline; the rest are the pieces it composes. Source lives at
`hardware-agent/src/agent/scanner/`.

* [runner](./runner.md) — `ScanRunner`: cancellation/deadline control and the pipeline body that drives discovery → ports → deep inspection → NSPi OT inspection → normalize.
* [stages](./stages.md) — Threaded Nmap stages, serial bounded OT inspection, retry/circuit-breaker policy, and `HostInfo`→`HostPayload` normalization.
* [nmap](./nmap.md) — NmapRunner / LoggedNmapRunner — execute Nmap, log argv and failed stderr, parse XML, and retain per-run artifacts.
* [models](./models.md) — The in-memory scan dataclasses: `HostInfo`, `PortInfo`, `ServiceInfo`, `ScriptResult`.
* [errors](./errors.md) — The scan exception hierarchy that encodes the contingency policy (fatal / unit / transient / cancelled / budget / circuit-breaker).
* [progress](./progress.md) — `ScanEvent` stream, the `ScanReporter` protocol, and the `ProgressMapper` that turns events into a monotonic 0–100% for the UI.
* [live progress](./live-progress.md) — maps scan events to compact, throttled snapshots for the remote daemon.
* [workspace](./workspace.md) — The on-disk `results/` + `logs/` layout: result serialization, run-folder logging, and pruning.
