# ADR-012: Headless agent outcome → exit-code contract

## Context

[`spec 012`](../../specs/012-headless-agent-entrypoint/) adds a second front door onto the scan
pipeline: a headless entrypoint (`run_headless_scan`) and its `dmitri agent <mode> <subnet>` CLI
wrapper. It is the foundation the [`ADR-011`](ADR-011-pi-command-channel.md) Pi daemon sits on —
the daemon invokes the pipeline on command and must read the run's **outcome** to drive the
command lifecycle (`running → uploading → done | failed`).

Two facts force a decision:

- The daemon (and a CLI script) need the outcome in a **machine-readable** form, and richer than
  "success / failure": a scan that preserved partial work ([`ADR-010`](ADR-010-scan-contingency-policy.md))
  is neither a clean success nor a total failure.
- The `dmitri` binary already has one subcommand (`start`, the TUI) whose contract
  ([`specs/000-agent-tui/contracts/cli.md`](../../specs/000-agent-tui/contracts/cli.md)) used exit
  `1` for any fatal startup error and had no notion of "partial". Introducing a second subcommand
  with its own unrelated codes would leave one binary speaking two exit-code dialects.

This ADR pins the outcome vocabulary, its exit-code mapping, and unifies the whole `dmitri`
binary on that single space.

## Decision

### 1. Outcome vocabulary → exit codes

Every headless run reports exactly one outcome, mapped to a fixed exit code:

| Outcome | Meaning | Exit code | Result JSON written? |
|---------|---------|-----------|----------------------|
| `completed` | scan finished, `partial_result` false | `0` | yes |
| `partial` | partial work preserved (cancel / timeout / circuit-breaker / post-discovery fatal) | `10` | yes |
| `fatal` | no result JSON written (nmap missing, unwritable workspace, pre-discovery fatal, or a completed/partial payload that could not be persisted) | `20` | no |
| *(usage / invalid input)* | unknown mode, malformed subnet, wrong arity — nothing ran | `2` | no |

`2` is not an outcome of a run; it is the POSIX-conventional usage-error code, returned before any
scan starts.

### 2. Outcome derives from the runner's terminal state — no new vocabulary

Normally, `completed` / `partial` / `fatal` are a projection of the existing terminal
classification from [`ADR-010`](ADR-010-scan-contingency-policy.md) (`terminated_by ∈
{completed, user_cancel, timeout, error}` combined with `partial_result`). The exception is a
result-write `OSError`: `fatal` is then an I/O failure layered on an already-classified payload,
not a projection of `terminated_by` / `partial_result`. The payload remains available to the
programmatic caller, but no result JSON or `result_path` exists. No new terminal state, metadata
field, or schema change is introduced.

### 3. Two channels, one contract

- **Programmatic API** (`run_headless_scan`) returns `HeadlessScanResult.outcome`; invalid input
  raises `InvalidScanInput` (the caller maps it to `2`).
- **CLI** (`dmitri agent`) encodes the outcome in the process **exit code** per the table and also
  echoes a machine-readable JSON line (`{"outcome", "result_path", "scan_id"}`) to stdout.

### 4. Unify the whole `dmitri` binary on this space

The same code space applies to every subcommand of the binary, superseding the earlier `start`
codes:

- Fatal startup (nmap missing, unwritable workspace): `1 → 20`.
- Usage error (unknown subcommand, wrong arity): `1 → 2`.
- Normal completion / clean abort: `0` (unchanged).
- Optional OS-level SIGINT: `130` (unchanged — orthogonal signalling convention, not an outcome).

The spec-000 contracts ([`cli.md`](../../specs/000-agent-tui/contracts/cli.md),
[`checklists/requirements.md`](../../specs/000-agent-tui/checklists/requirements.md)) are updated to
these codes; [`BUG-004`](../../specs/000-agent-tui/bugs/004-nmap-missing-not-fatal.md) and
[`plans/01`](../../specs/000-agent-tui/plans/01-cli-entry-and-skeleton.md) keep their exit-`1`
wording as historical records with a superseded-by note.

### 5. Enforced in tests

The mapping is a contract, not a convention: a test asserts the code's `EXIT_CODES`
(`{"completed": 0, "partial": 10, "fatal": 20}`) and `INVALID_INPUT_EXIT` (`2`) equal this ADR's
table, so the two cannot drift silently.

## Rejected alternatives

- **Per-subcommand divergence** — `agent` gets `0/2/10/20`, `start` keeps `1`. Zero edits to the
  existing path, but one binary then reports nmap-missing as `1` under `start` and `20` under
  `agent`; a wart in a tool the daemon and scripts both consume. Rejected in favour of one space.
- **Reuse `1` for everything** — collapses `completed`/`partial`/`fatal` into success-vs-failure,
  so the daemon cannot tell a preserved-partial run from a fatal one by exit code. Defeats the
  reason for the contract.

## Consequences

- The daemon reads run outcome from the CLI exit code (or `HeadlessScanResult.outcome`
  programmatically) without parsing result JSON.
- `partial` is a non-zero exit (`10`): scripts that treat any non-zero as failure will flag partial
  runs. This is intended — a partial run is not a clean success — and is documented at the CLI.
- The exit-code change ripples into two spec-000 contracts and two existing CLI tests
  (`test_cli_nmap_missing` `1→20`, `test_cli_unknown_command` `1→2`); the TUI's on-screen behaviour
  is unchanged (the exit precedes any screen render).

## Out of scope

- Transport, upload, daemonization — [`ADR-011`](ADR-011-pi-command-channel.md) and later issues.
- The optional `130` SIGINT convention — unchanged, not an outcome of this contract.

## References

- [`spec 012`](../../specs/012-headless-agent-entrypoint/ARCHITECTURE.md) — headless entrypoint
- [`ADR-010`](ADR-010-scan-contingency-policy.md) — terminal-state vocabulary used before any
  result-write failure is layered on the outcome
- [`ADR-011`](ADR-011-pi-command-channel.md) — the daemon that consumes this outcome
- [`specs/000-agent-tui/contracts/cli.md`](../../specs/000-agent-tui/contracts/cli.md) — aligned CLI contract
