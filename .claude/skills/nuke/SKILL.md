---
name: nuke
description: >-
  Manual pre-push branch-delta audit only. Invoke when the human explicitly says nuke or /nuke.
  Never use during planning, orchestration, TASKS.md execution, or per-task review. Judges only
  what THIS branch introduced or worsened vs main; outputs SHIP or FIX BEFORE PUSH; reports only
  and never edits code. Not a substitute for the per-task code reviewer or /code-review.
disable-model-invocation: true
---

# Nuke (pre-push audit)

Strict **branch-delta** maintainability check for Dmitri. Run only at the end of a feature,
after implementation and tests are green, **before pushing to `main`**.

**Philosophy:** do not fix what is not broken. Judge only what **this branch introduced or
worsened**. Pre-existing debt is out of scope unless the diff made it harder to reason about.

## When to run

| Run | Do not run |
|-----|------------|
| Human explicitly says `nuke` / `/nuke` | During `/feature-planning`, `/feature-orchestrator`, or per-task review |
| Feature work finished; `uv run pytest` already green | Mid-task or "while implementing" |
| Immediately before push to `main` | To block or replace the `code-reviewer` subagent |

## Scope

1. **Diff first:** `git diff main...HEAD` (operator may override the base).
2. **Changed files only** — plus direct importers only if the diff leaks into a shared path.
3. **No repo-wide refactors**, no "while we're here" cleanups, no redesign of untouched modules.
4. Optional context: `specs/NNN-feature-slug/` (`TRUTH.md`, `ARCHITECTURE.md`) for intent — **not**
   a second spec-compliance gate (that already ran in orchestration).

## Primary questions (delta-only)

For each meaningful change in the diff:

1. Did this branch add **spaghetti** — ad-hoc conditionals or scattered special cases in
   **shared** paths (e.g. `config.py` helpers, the nmap runner, `_merge_ports`, normalization)?
2. Did any **touched** file cross ~1000 lines because of this branch?
3. Did **feature logic leak** across boundaries (scan logic in TUI screens, TUI concerns in the
   discovery layer, pipeline rules in CLI glue)?
4. Did the diff add **unsafe types** (bare `except`, untyped pydantic escapes), or **duplicate
   helpers** where a canonical utility already exists?
5. Did the diff **break the CLAUDE.md integration rule** — a new orchestrator/runner parameter
   that was *not* threaded through `ScanRunner` and `ScanProgressScreen`?

## Project rules (new violations only)

| Area | Check |
|------|--------|
| `hardware-agent/src/agent/` | ruff-clean new lines; typed; named per `ARCHITECTURE.md` |
| Discovery / pipeline | reuse existing nmap runner / merge helpers; no parallel scan paths |
| TUI screens | new screens follow existing `screens/` patterns; no scan logic embedded |
| Tests | new behavior has unit tests under `hardware-agent/tests/` |

Do **not** block on pre-existing violations in untouched lines.

## Explicit non-goals

- No ambitious rewrite; no refactor of unrelated pre-existing code.
- No `TASKS.md` / dual-approve tokens.
- Do **not** run the full suite unless asked — assume tests already passed.
- Do **not** edit application code; produce a report only.

## Output format

Start with exactly one verdict line:

```
SHIP
```

or

```
FIX BEFORE PUSH
```

Then:

### Blockers (max 5)
Issues **introduced by this branch** to fix before push. Each: file path, what changed, why it's
a regression, minimal fix direction (no drive-by refactors).

### Optional (max 3)
Improvements **confined to files already changed** in this branch. Prefix each with `Optional:`.

### Pre-existing debt ignored
One short line if you noticed out-of-scope debt and correctly excluded it.

## Verdict bar

**`SHIP`** when: no new structural regression in the diff; no touched file crossed ~1k lines
without strong organization; no new spaghetti or layer leak; the integration rule holds.

**`FIX BEFORE PUSH`** when any blocker above is present. Do not soften blockers; do not invent
scope creep.

## Relationship to the pipeline

| Piece | Nuke |
|-------|------|
| `feature-orchestrator` | Not wired — orchestrator must not spawn nuke |
| `code-reviewer` subagent | Separate; nuke does not replace it |
| Human workflow | plan → orchestrate → review loop → tests green → **nuke** → **commit** → **create-pr** |
