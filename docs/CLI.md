# `dmitri` CLI reference

> **Executable:** `dmitri` (lowercase). Declared in `hardware-agent/pyproject.toml` as
> `agent.cli:main`. Run from `hardware-agent/` after `uv sync`:
> `uv run dmitri …` or `uv run python -m agent.cli …`.
>
> **Exit-code contract:** [`adr/ADR-012-headless-exit-code-contract.md`](adr/ADR-012-headless-exit-code-contract.md).

## Commands

| Command | Purpose |
|---------|---------|
| `dmitri` | Launch the Textual TUI (same as `start`) |
| `dmitri start` | Launch the Textual TUI |
| `dmitri agent <mode> <subnet>` | Run one headless scan; print JSON result to stdout |

### `dmitri start` / `dmitri` — TUI

```bash
uv run dmitri
uv run dmitri start
```

No scan arguments. Requires **nmap** on PATH (or a common install location). Results directory
comes from setup/settings (see [`DEV-SETUP.md`](DEV-SETUP.md)).

### `dmitri agent <mode> <subnet>` — headless scan

```bash
uv run dmitri agent quick 192.168.1.0/24
uv run dmitri agent nspi 10.0.0.0/24
```

- **`<mode>`** — one of: `quick`, `standard`, `extensive`, `nspi`, `max`
- **`<subnet>`** — IPv4 CIDR (e.g. `192.168.1.0/24`); host addresses without a prefix are rejected

On success, prints one JSON line to **stdout**:

```json
{"outcome": "completed", "result_path": "/path/to/result.json", "scan_id": "…"}
```

Progress messages go to **stderr** (`StderrReporter`). Workspace defaults match the TUI
(`agent.paths.load_config()` or OS default under `Dmitri/results`).

## Exit codes

Shared across all subcommands ([ADR-012](adr/ADR-012-headless-exit-code-contract.md)):

| Code | Meaning |
|------|---------|
| `0` | TUI: normal quit. Agent: scan **completed** (full result JSON written). |
| `2` | Usage error — unknown subcommand, wrong arity, unknown mode, invalid subnet. |
| `10` | Agent only: scan **partial** (partial result JSON written). |
| `20` | Agent **fatal** with no result JSON written — nmap missing, unwritable workspace, pre-discovery failure, or a completed/partial payload that could not be persisted. |
| `130` | Optional: OS-level SIGINT (not a documented user action for the TUI). |

## Examples

```bash
# TUI on dev machine
cd hardware-agent && uv run dmitri

# Headless quick scan (CI / daemon / scripting)
cd hardware-agent && uv run dmitri agent quick 192.168.1.0/24
echo $?   # 0 = completed, 10 = partial, 20 = fatal, 2 = bad input

# Invalid mode → exit 2
uv run dmitri agent bogus 192.168.1.0/24

# Missing nmap → exit 20 (both subcommands)
uv run dmitri agent quick 192.168.1.0/24
uv run dmitri start
```

If a scan completes but its result cannot be written, stdout still reports the outcome and keeps
the in-memory payload's `scan_id` while `result_path` is `null`:

```json
{"outcome": "fatal", "result_path": null, "scan_id": "7f693869-6357-4d94-8743-bd88e942a7c4"}
```

The write error is printed separately to stderr:

```text
Scan completed but the result file could not be written to /path/to/workspace: No space left on device
```

## Related docs

- Dev setup (install, nmap, pre-commit): [`DEV-SETUP.md`](DEV-SETUP.md)
- Pi daemon roadmap (`dmitri agent` on production Pi): [`roadmap/PI.md`](roadmap/PI.md)
- Headless entrypoint spec: [`../specs/012-headless-agent-entrypoint/`](../specs/012-headless-agent-entrypoint/)
