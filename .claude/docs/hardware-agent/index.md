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
* [normalize](./normalize.md) — Pydantic wire contracts (`ScanPayload`) and the NSE-to-findings extractor.
* [utils](./utils.md) — Local-network detection/connectivity checks and the Nmap/NSE XML parsers.

## Upload

* [transport](./transport.md) — The device-side ingest client: environment-loaded config, the Ed25519 request envelope, bounded retries, and the typed submission outcome. Built, not yet called (DMI-66).

## TUI

* [tui](./tui.md) — The Textual application: app root, screens (setup, home, wizard, progress, view, past scans), and shared widgets.
