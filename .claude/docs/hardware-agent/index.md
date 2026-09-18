# hardware-agent

The Python scanning appliance: the Nmap + NSE scan pipeline, its normalization to the shared
JSON contract, and both front doors (Textual TUI + headless CLI). This is the only Dmitri
component in active development. Source lives at `hardware-agent/src/agent/`.

## Overview & entry points

* [Package overview](./overview.md) — What the hardware-agent package is, its scan pipeline, and the three front doors that drive it.
* [Entry points & configuration](./cli.md) — The `dmitri` CLI dispatcher, the headless entrypoint, scan tuning (`config.py`), and persisted user prefs (`paths.py`).

## Scan engine (scanner)

* [scanner package](./scanner/index.md) — The split scan engine: runner, stages, Nmap execution, models, errors, progress, and workspace layout.

## Discovery & normalization

* [discovery](./discovery.md) — Thin per-stage Nmap-argument builders: host discovery, port discovery, service detection, and NSE vulnerability scanning.
* [normalize](./normalize.md) — The Pydantic scan payloads for observations, profiles, exposures and findings, plus the NSE finding extractor.
* [assessment](./assessment.md) — The deterministic, versioned local policy that turns accepted scan evidence into endpoint exposures and conservative device profiles.
* [utils](./utils.md) — Local-network detection/connectivity checks and the Nmap/NSE XML parsers.

## Remote control & upload

* [daemon](./daemon.md) — The long-lived device process that executes one remote scan at a time, uploads it, reports lifecycle status, and logs safe upload outcomes.
* [command-channel](./command-channel.md) — The signed device WebSocket: strict hello/command/status frames, visible connection loss/recovery, and the pinned reconnect ladder.
* [transport](./transport.md) — The device-side ingest client: environment-loaded config, the Ed25519 request envelope, bounded retries, and the typed submission outcome. Wired to the daemon since DMI-66.

## TUI

* [tui](./tui.md) — The Textual application — scan setup/progress plus local inventory, profile, exposure and finding result views.
* [ot](./ot.md) — Modbus inspection: policy, keyed digest, read-only client, inventory, OT stage (`pymodbus`).
