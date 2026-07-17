# TRUTH — Headless agent entrypoint (DMI-51)

Domain language and verifiable behaviour only. No file paths, no nmap flags, no code.

## Narrative

The production Pi runs a headless daemon, not the TUI. Today the scan pipeline is only
reachable through a screen: an operator opens the TUI, picks a mode and subnet, and the
TUI's runner drives discovery, port scanning, deep inspection, and normalization, then
writes the result JSON. The future daemon must run that exact pipeline on command — but
there is currently no way to invoke it without rendering a screen.

This feature makes the pipeline callable without a screen: an agent entrypoint that takes
a scan mode and a subnet, runs the **same** runner and stages a TUI-initiated scan runs,
and writes JSON identical in shape. It is the foundation the daemon will be built on —
command handling, transport, and service management come later and are explicitly out of
scope. It also gives developers a faster iteration loop: run a scan from the command line
without the TUI.

An older, environment-driven headless path existed and has been discontinued as dead code.
This feature does not resurrect it; the new entrypoint shares the TUI's live pipeline —
one pipeline, two front doors.

## Business rules

- A headless run takes exactly two inputs — scan mode and subnet — and executes the same
  scan pipeline a TUI-initiated scan executes: same stages, same ordering, same budgets,
  same contingency behaviour.
- The headless run's saved result JSON is identical in shape to a TUI-initiated scan's:
  same schema, same fields, same terminal-state vocabulary. Only run-specific values
  (timestamps, discovered hosts, identifiers) differ.
- The TUI's behaviour is unchanged: same screens, same flow, same outputs. An operator
  cannot tell this feature exists from inside the TUI.
- Both paths share one pipeline implementation — no forked or duplicated scan logic. A
  future fix to the pipeline must automatically apply to both front doors.
- When a stage fails mid-run, the headless run applies the same partial/fatal semantics
  as the TUI runner: the same stage conditions produce a partial or fatal result, and the
  saved result records the same terminal state either way. A headless-only persistence
  failure is the exception: if a completed or partial payload cannot be written, the
  headless outcome is fatal with no result JSON, while the payload remains available to
  the programmatic caller.
- The headless run is invocable programmatically (by the future daemon) and from the
  command line (by a developer), and reports its outcome — completed, partial, or fatal —
  in a machine-readable way in both cases.
- Invalid inputs (unknown mode, malformed subnet) are rejected with a clear error before
  any scanning starts.

## User stories

1. As the future Pi daemon, I invoke the pipeline programmatically with a mode and subnet
   and get the normalized result back, so command handling can be built on top later.
2. As a developer, I run a scan from the CLI without the TUI, so iteration on the
   pipeline is faster.
3. As the operator of the eventual product, I trust that a scan triggered remotely
   produces exactly what a scan triggered at the device produces, because both run the
   same pipeline.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Same shape | the same mode + subnet | a scan runs headless and a scan runs via the TUI | both produce contract-valid result JSON with the same structure |
| Programmatic result | the entrypoint invoked programmatically with mode + subnet | the scan completes | the caller receives the normalized result and the result JSON is written |
| Failure semantics match | a scan that hits a stage failure | it runs headless | the partial/fatal outcome and recorded terminal state match what the TUI runner produces for the same failure |
| Result persistence failure | a completed or partial payload | the headless result write fails | the outcome is fatal, no result JSON exists, and the programmatic caller still receives the payload |
| TUI untouched | the TUI | any screen-driven scan runs | behaviour, flow, and outputs are identical to before this change |
| One pipeline | the pipeline code | headless and TUI paths are compared | both call the same runner/stages implementation — no duplicated scan logic |
| Input validation | an unknown mode or malformed subnet | a headless run is attempted | it fails fast with a clear error and no scan starts |
| Suites green | the touched scope | `uv run pytest` and `uv run ruff check` run | both pass |

## Out of scope (v1)

- No WebSocket client, no backend upload, no daemonization/systemd/reconnect logic
  (later issues; the command channel is ADR-011's concern).
- No TUI removal and no TUI feature changes.
- No new scan modes, and no new config surface beyond what invoking headlessly requires.
- No resurrection of the discontinued environment-driven headless path.
- No progress UI for the headless run beyond what invoking it requires.

## Related specs

- Issue: Linear DMI-51 (approved 2026-07-04); direction: `docs/roadmap/PI.md` § Pi runtime,
  `docs/adr/ADR-011-pi-command-channel.md` (future transport, out of scope here).
- **Pending sibling: `specs/011-nspi-port-stage-fix/` (unimplemented, same branch)** — it
  edits the same runner modules (cancel guard, error-class relocation, log retention).
  This spec must not conflict with it; where both touch the same seam, 011's decisions
  (e.g. the shared cancellation error living in the scanner layer) are assumed.
- Failure semantics source: `specs/010-scan-pipeline-resilience/`, `docs/adr/ADR-010-scan-contingency-policy.md`.
- Machine-readable outcome / exit-code contract: `docs/adr/ADR-012-headless-exit-code-contract.md`.
- Legacy headless path discontinued: `specs/006-scan-duration-fix/` (issue #68 context).
- Implementation: `ARCHITECTURE.md`
- Execution ledger: `POOP.md` (written during orchestration)
