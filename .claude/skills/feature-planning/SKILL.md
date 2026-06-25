---
name: feature-planning
description: >-
  Phase 1 of the document-driven pipeline. Creates specs/NNN-feature-slug/, writes
  flat TRUTH.md, and spawns the architecture (and TUI design) agents to write
  ARCHITECTURE.md / DESIGN.md with mandatory file/naming tables and verifiable
  acceptance criteria. Stops at a human approval gate — never implements. Use when
  the user invokes /feature-planning, says "create spec" / "plan feature" / "start a
  spec", or pastes a feature/issue body to begin a new feature.
user-invocable: true
argument-hint: "Short idea or feature name (optional)"
disable-model-invocation: false
---

# Feature Planning (`/feature-planning`)

Phase 1 of the Dmitri document-driven pipeline. You write **specs as files** and then
**stop** for human approval. You do **not** implement application code.

This skill replaces the old `create-spec`. New specs use **flat Peirce docs**
(`TRUTH.md`, `ARCHITECTURE.md`, `DESIGN.md`, optional `INTEGRATION.md`) — not the
folder-tree used by `specs/000`–`004`. Those older specs stay as-is; do not migrate them.

## Triggers

- `/feature-planning` … optional trailing idea
- "create spec" / "plan feature" / "start a spec" … optional topic or pasted issue body
- Request to scaffold a new `specs/NNN-…` feature before implementation

**Initial idea** = everything after the command phrase, or the whole message if the user
only pasted requirements.

## Pipeline position

```
/feature-planning  → specs written → [human approval gate]
/refine-specs      → optional grilling before approval
/feature-orchestrator → TASKS.md + per-task Coder→Tester→Reviewer loop
```

## Phase 1 — steps (do in order)

1. **Context** — Use the user's narrative. If thin, ask the gap questions below (one short
   numbered list, then proceed). Do not block forever on Q&A when the idea is already rich.
2. **Consult docs** — Use the **`consult-docs`** skill (`docs/README.md` routing index, max
   two docs) to load only the relevant knowledge-base files. Do not read all of `docs/`.
3. **Derive slug + number** — `feature-slug` is kebab-case, lowercase, digits OK. Number =
   `max(NNN) + 1` over `specs/` dirs matching `^\d{3}-` (or `001` if none). See
   [REFERENCE.md](REFERENCE.md#numbering).
4. **Create** `specs/NNN-feature-slug/` and write **`TRUTH.md`** from the
   [TRUTH template](REFERENCE.md#truthmd) — narrative, business rules, user stories,
   **verifiable acceptance criteria** (Given/When/Then), out-of-scope. `TRUTH.md` holds
   **domain language and behaviour only** — no file paths, no nmap flags, no code.
5. **Spawn the architecture agent** (`subagent_type: architecture-agent`) to write
   **`ARCHITECTURE.md`** (+ `INTEGRATION.md` only if the feature genuinely crosses a layer
   boundary; this is a single-layer Python app, so usually omit it). It must produce the
   **mandatory New files and naming** table and per-area testing expectations.
6. **Spawn the TUI design agent** (`subagent_type: tui-design-agent`) to write
   **`DESIGN.md`** **only when** the feature adds or changes Textual screens
   (`hardware-agent/src/agent/tui/screens/`). Skip for pure pipeline/config features.
7. **Naming is mandatory** — both agents must list the exact files/paths implementers will
   create or touch under `hardware-agent/src/agent/`.

Pass the agents **paths**, not pasted spec contents.

## Phase 1.5 — human approval gate (HALT)

1. Summarize the specs you created (one short paragraph + the file list).
2. Ask the operator to approve `TRUTH.md`, `ARCHITECTURE.md`, `DESIGN.md`, and the file/naming
   conventions.
3. **HALT.** Do not write `TASKS.md` and do not implement.
4. Tell the operator: run **`/refine-specs`** to stress-test the specs, or **`/feature-orchestrator`**
   when ready to execute.

## When context is thin

If two or more of these are missing or vague, ask once (short numbered list) before or right
after a minimal scaffold:

1. **Working title** / feature name
2. **Goal** — one paragraph: problem + who benefits
3. **Surface** — TUI screen, scan pipeline, CLI, config, normalization
4. **v1 scope** vs out of scope
5. **Acceptance** — how we know it's done (testable hints)
6. **Contracts** — known flags, nmap options, config constants, `ScanPayload` fields, env vars,
   exit codes (or "none yet")

## Rules

- **No application code** — never edit `hardware-agent/**` from this skill. Specs only.
- **Single layer** — collapse to one implementer; omit `INTEGRATION.md` unless a real
  cross-layer contract exists.
- **Honor the CLAUDE.md integration rule** — when the architecture agent names a new
  orchestrator/runner parameter, the naming table must also list `ScanRunner` and
  `ScanProgressScreen` as call sites to thread it through.
- **Match the flat-doc shapes** in [REFERENCE.md](REFERENCE.md) — do not recreate the old
  folder-tree.

## Depth

Templates, numbering algorithm, and doc skeletons: [REFERENCE.md](REFERENCE.md). Canonical
copies live in `specs/_templates/`.
