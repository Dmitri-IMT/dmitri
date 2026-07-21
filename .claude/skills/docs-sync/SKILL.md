---
name: docs-sync
description: >-
  Update both the .claude/docs OKF code-map and the human docs/ knowledge base after code
  changes land. Owns .claude/docs fully; for docs/ it delegates to architecture-adr-sync /
  roadmap-sync / openapi-contract-sync and only patches unambiguous factual drift. Run once at the
  end of the feature-orchestrator pipeline, or manually via /docs-sync when code has moved and the
  docs may be stale.
---

# docs-sync

Keep the two documentation layers current with the code, scoped to what changed.

| Layer | Ownership | Action |
|-------|-----------|--------|
| `.claude/docs/` (OKF code-map) | **fully owned** | Always update to match changed source. |
| `docs/` (human KB) | curated, partly target-state | Delegate + patch only unambiguous factual drift; report the rest. |

The `.claude/docs/` conventions (frontmatter, body shape, linking, standing facts) live in
[`.claude/docs/MAINTAINING.md`](../../docs/MAINTAINING.md) — read it first; this skill *executes*
that playbook. Never scan the whole repo blindly — always scope by the changed files.

## Input / scope

- **Orchestrator mode:** run once when all tasks are `COMPLETED`, over the whole feature's diff
  (`git diff --name-only` vs the base branch).
- **Manual mode (`/docs-sync`):** `$ARGUMENTS` if given, else `git diff --name-only` vs `main`.

If nothing under `hardware-agent/`, `backend/`, `contracts/`, `supabase/`, or infra changed, say so
and exit early.

## Steps

1. **List changed source files** (the scope above). Group them by component.
2. **Update `.claude/docs/` (always).** For each changed file, open the concept doc whose
   `resource:` maps it (or its module — e.g. a change in `scanner/nmap.py` → `hardware-agent/scanner/nmap.md`).
   Revise Purpose / Key classes-functions / How it connects / Notes to match; bump `timestamp`; fix
   any now-stale cross-links and `path:line` refs. Add a doc for a new module, remove one for a deleted
   module (and update the parent `index.md`). Refresh affected `index.md` listings from frontmatter
   `description`s. Append a dated entry to `.claude/docs/log.md` (newest first).
3. **Update `docs/` (narrow + delegating).** Where a change touches an area an existing skill owns,
   invoke that skill instead of hand-editing:
   - architecture / ADRs → `architecture-adr-sync`
   - `docs/roadmap/*` → `roadmap-sync`
   - contracts ↔ routes → `openapi-contract-sync`
   Outside those, patch only **low-risk factual drift** (a renamed symbol, a moved path, a changed
   default). Leave decisions and target-state claims alone.
4. **Report contested items.** Anything you did not edit because it needs a human call goes into the
   run's report to the operator (orchestrator mode: also append a "Docs drift" list to the feature's
   `POOP.md`).

## Modes

- **Orchestrator mode — autonomous, non-interactive.** Update `.claude/docs` freely; apply only
  unambiguous `docs/` patches; never call `AskUserQuestion`; never block the pipeline. Everything
  uncertain is reported, not applied.
- **Manual mode (`/docs-sync`)** — broader. For contested `docs/` edits you may use
  `AskUserQuestion` (which source is authoritative?), mirroring `architecture-adr-sync`'s flow.

## Constraints

- **Never modify application code** — docs only.
- Never reformat a `docs/` file beyond the specific fix; keep edits minimal.
- Never auto-rewrite `.claude/docs/pipeline.md` (dev process, not code) or a `docs/adr/` decision.
- Preserve the "standing facts" in `MAINTAINING.md` — do not "correct" the device↔host rename, the
  ScanRunner orchestration note, the not-wired backend, or the contract divergence.
- If a delegated skill is unavailable, fall back to a reported recommendation rather than a blind edit.
