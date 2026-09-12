# Remediation — execution checklist

**The work is specified in [`TRUTH.md`](TRUTH.md).**
Every behaviour required by the audit is a business rule or an acceptance criterion there, plus a
`Docs drift` section and a `Known items` section for what is deliberately deferred.
[`AUDIT.md`](AUDIT.md) is the evidence; this file is only the order of operations.

| | |
|---|---|
| **Owner** | Guilherme Ronca (all remediation) |
| **Vehicle** | Spec `045-ot-agent-hardening` on branch `feat/dmi-157-harden-active-ot-scans` |
| **Gate** | Review completes before TASKS.md is written |
| **Audited** | PR #137 (8 commits), plus `6e19062` and `79c559d` pushed directly to `main` |
| **Branch from** | **`main` (`f68397c`), not `audit/nspi-137`.** This worktree predates `6e19062`, so findings 16 and 17 do not exist here — `runner.py` still has ADR-010's correct pairing and `-sV` is still in `discovery_arguments()`. A fix written on this branch is a no-op that regresses on merge |

## Decisions this implements

| # | Decision |
|---|---|
| 1 | The Alembic repair lands **inside 045**, not as a standalone hotfix |
| 2 | Guilherme does all remediation work |
| 3 | The outstanding review **finishes first**; TASKS.md is written from the complete picture |
| 4 | Guilherme accepts ADR-019 |
| 5 | The test suite fails without a database, with **no opt-out** |
| 6 | 045 absorbs **all** documentation work |
| 7 | 045 absorbs 042's OT persistence, **redesigned** |
| 8 | Review items gate only if they could add or change a task |
| 9 | ADR-019 moves to Accepted now |
| 10 | Claude runs the non-interactive review; Guilherme runs `/nuke` and `/security-review` |
| 11 | Two tables (`industrial_services`, `modbus_units`), JSON beneath, `findings.modbus_unit_id` |
| 12 | `modbus_validations` deferred until the write depth is built |
| 13 | Reads expose status + keyed digest; no raw values, no aggregate statistics |
| 14 | 045's ARCHITECTURE.md supersedes 042 §7 |

**Accepted consequence of decision 1:** `main` cannot migrate until 045 lands, so the
database-backed backend suite is unavailable to the whole team until then. Tell them — do not let
them discover it as a phantom backend bug.

## 1 — Settle the record

- [ ] Amend `AUDIT.md` finding 2: 042's Task 10 is `PENDING`, Task 12 `IN PROGRESS`. The defect is
      a contract published ahead of its implementation, not an oversight.
- [ ] Close the generated-types finding — regeneration produced a byte-identical file.
- [ ] Withdraw the raw-value sensitivity question; `042/TRUTH.md:82-83` already decided it.
      Replace it with the finding that survives: an unkeyed digest over a small value space is
      reversible.
- [ ] ADR-019 → **Accepted (2026-09-12)**.
- [ ] Add the process-data clause to ADR-019: values minimised at capture, not persisted by
      default, and any change-detection digest keyed so it cannot be brute-forced.

## 2 — Finish the review (gating)

Nothing is written into TASKS.md until this closes. New findings append to `AUDIT.md` and become
rules in TRUTH.md.

**Claude runs:**

- [x] Frontend gate, frontend review, TUI sweep, test-quality sweep — dropped as
      TASKS.md gates (045 does not change frontend screens; TUI is in DESIGN.md).

**Guilherme runs:**

- [x] `/nuke` — base `8688597`, head `8fb1c8c`. Verdict FIX BEFORE PUSH on dual
      Alembic heads (AUDIT blocker 1). Do not rewrite `down_revision`; 045 uses
      merge revision `20260912_20`.
- [x] `/security-review` on that range. One medium: Rich markup in scan view
      (AUDIT finding 6). Already in TRUTH.md.

**Logged, not gating** — already carried in TRUTH.md under `Known items`:
`/ponytail-review` over the diff; the two unreproduced suspicions.

## 3 — Specify

- [ ] `/feature-planning` against the completed TRUTH.md → `ARCHITECTURE.md` and `DESIGN.md`
      through the architecture agent. Do not hand-write them; the file/naming table is that
      agent's job, and skipping this gate is how PR #137 happened.
- [ ] Add a superseded-by banner to `specs/042-nspi-modbus-ot/ARCHITECTURE.md` §7.

## 4 — Task and build

- [ ] **Cut the branch from `main`, not from this worktree.** See the header. Keep
      `audit/nspi-137` as-is for `/nuke`, which still needs base `8688597`.
- [x] `/create-tasks` on the approved specs.
- [ ] **Ordering constraint:** the Alembic merge revision first, then the no-database failure.
      Until the first lands nobody can run the suite; until the second lands a green run still
      proves nothing. The second must not land before the first, or the suite fails for everyone
      with no escape hatch.
- [ ] `/feature-orchestrator` for the remainder.

## 5 — Close out

- [ ] Create the issue for the write-validation depth. None exists. It is the parent for the
      deferred storage and the removed contract fields.
- [ ] Update **DMI-142** with the redesign; close it when persistence lands.
- [ ] `/docs-sync` after merge, for drift this work itself introduces.
- [ ] Resume `specs/042-nspi-modbus-ot` for its web read surface (Task 12).
- [ ] Tell the team `main` can migrate again.

## Process finding, unaddressed by any task

Two unreviewed pushes by the same author in four days — PR #137 with an empty body and no
reviewer, then 479 lines direct to `main`. Both times the defect was in the scan lifecycle rather
than in the new feature code. This plan fixes the code. It does not fix that.
