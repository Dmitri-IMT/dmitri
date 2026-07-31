---
name: create-tasks
description: >-
  Phase 2 of the document-driven pipeline. Reads the human-approved flat Peirce specs
  in specs/NNN-feature-slug/ (TRUTH.md, ARCHITECTURE.md, DESIGN.md, optional
  INTEGRATION.md) and writes TASKS.md — small, testable tasks in the canonical
  orchestrator shape (Description / Dependencies / Target Files / Success Criteria /
  Status / Review Rejections), plus a dependency graph and status table. Use when the
  user says /create-tasks, "taskify this spec", "break this spec into tasks", or
  "write TASKS.md".
user-invocable: true
argument-hint: "Path to spec directory (e.g. specs/005-extensive-scan)"
---

# Create tasks from spec (`/create-tasks`)

Phase 2 of the Dmitri document-driven pipeline. You read the **human-approved flat
Peirce specs** and write **`TASKS.md` as a file** in the spec directory. You do **not**
implement application code and you do **not** create harness tasks — `TASKS.md` is the
ledger the **`feature-orchestrator`** drives.

## Pipeline position

```
/feature-planning  → flat specs written → [human approval gate]
/refine-specs      → optional grilling before approval
/create-tasks      → writes specs/NNN-…/TASKS.md   ← you are here
/feature-orchestrator → runs the per-task Coder → Tester → Reviewer loop on TASKS.md
```

`feature-orchestrator`'s Phase 2 expects a `TASKS.md` in the spec dir. This skill writes
it. (If `/create-tasks` is skipped, the orchestrator writes the same shape inline.)

## Inputs

The argument is a **path to a spec directory** (e.g. `specs/005-extensive-scan`). If
empty, pick the most recent `specs/NNN-…` by numeric prefix. If ambiguous, ask which
spec to taskify.

## Workflow

### 1. Read the approved specs (do all reads before analysis)

Read the flat docs in this order. Pass through whatever exists — `DESIGN.md` and
`INTEGRATION.md` are optional.

1. `TRUTH.md` — narrative, business rules, user stories, **verifiable acceptance
   criteria** (Given/When/Then), out-of-scope
2. `ARCHITECTURE.md` — pipeline fit, data/contract changes, and the **mandatory
   "New files and naming" table** (the source of every task's `Target Files`)
3. `DESIGN.md` — Textual screen flow, layout, key bindings, copy, widget ids (only when
   screens change)
4. `INTEGRATION.md` — only when a real cross-layer contract exists (rare here)
5. `decisions/DR-*.md` — accepted decisions; `open-questions/to-define.md` — unresolved
   gaps (both optional, present only when they have content)

Old folder-tree specs (`specs/000`–`004`) are not migrated; if you are handed one, fall
back to its `README.md` / `contracts/` / `architecture/README.md`, but still emit the
new `TASKS.md` file shape below.

### 2. Identify implementation atoms

Extract **implementation atoms** — the smallest units of work that:
- Produce a testable artifact (function, module, screen, behavior change)
- Have a clear "done" definition derivable from the acceptance criteria or the naming table
- Map to one or more rows in the `ARCHITECTURE.md` naming table (or `DESIGN.md` widgets)

Use the [decomposition guide](REFERENCE.md#decomposition-guide) to categorize atoms, and
cross-check that **every acceptance-criteria scenario in `TRUTH.md` maps to at least one
task**.

### 3. Merge every atom that cannot carry its own test

**This step runs before ordering, and it is the one that protects the token budget.** Splitting
finely is cheap to write and expensive to execute: every task costs a full
coder → tester → reviewer cycle regardless of how little it changes. A task that edits
`package.json`, adds a four-line typed wrapper, or renames a constant burns three agent
invocations to land a diff no test can meaningfully assert.

Apply the **test viability check** to every atom from step 2:

> Can a reviewer verify this task by reading a test that would **fail** if the task were done
> wrong — a test this task itself delivers?

- **Yes** → it stands alone as a task.
- **No** → it is **not a task**. Merge it into the neighbour whose tests already cover it —
  normally its only consumer, or the task that first renders/calls it.

Atoms that almost never survive the check on their own:

| Atom | Merge into |
|---|---|
| Dependency adds/removes, `package.json`/`pyproject.toml` edits, lockfiles | The first task that uses the dependency |
| Token/theme/CSS layers, fonts, config constants with no branching | The first component or module that consumes them |
| Thin typed wrappers over an HTTP client or ORM (no logic beyond the URL and the type) | The hook, service, or screen that calls them — where they get exercised end-to-end |
| Test fixtures, MSW/mock handlers, shared test renderers | The first suite that consumes them |
| Copy-only or token-only presentational components | The page whose test asserts their rendered output |
| Doc write-backs, `<tbd>` replacements, and "run the gate" steps | The last implementation task in the feature |
| A module and its sole caller, when the caller is what makes it observable | One task |

Two rules that keep the merge honest:

- **A merge changes no scope.** Every path in the `ARCHITECTURE.md` naming table is still
  built and every acceptance criterion is still gated — the work moves, it does not vanish.
  Record what moved in an **`Absorbed:`** line on the receiving task, naming the atom and why
  it could not carry a test. That line is how a reviewer confirms nothing was quietly dropped.
- **Never merge to dodge a test that should exist.** If an atom has real branching, a rule, a
  boundary, or an error path, it *can* carry a test and it stays its own task. The check asks
  whether a meaningful test is *possible*, not whether writing one is inconvenient.

The signal that you have split too finely: a task whose `Target Files` contains no
`*.test.*` path and whose `Success Criteria` are all greps and build commands.

### 4. Order and group

Split scope finely **within the limits of step 3**, in this default order:

```
config/constants → discovery/pipeline → normalization (ScanPayload) → TUI screens → tests
```

- **Foundations first**: config constants, pure helpers, schema/`ScanPayload` changes
- **Core behavior next**: runners, two-pass scans, normalization
- **Integration / callers last**: wiring new modules into existing call sites
- **Group into parallel tracks** when atoms share no dependencies (e.g. "Config &
  Pipeline" vs "TUI Screens"), as in `specs/004-nspi-scan-mode/TASKS.md`

### 5. Write TASKS.md

Write **`specs/NNN-feature-slug/TASKS.md`** by copying `specs/_templates/TASKS.md` and
filling it in. Each task uses the canonical orchestrator shape:

```markdown
## Task N: {Task name}
- **Description**: {what to implement; reference the governing spec file}
- **Absorbed**: {atoms merged in per step 3 and why — omit the line when nothing was merged}
- **Dependencies**: {task numbers, or —}
- **Target Files**: [{exact paths from the ARCHITECTURE.md naming table / DESIGN.md}]
- **Tests**: {the test file(s) this task delivers and what they prove}
- **Success Criteria**: {verifiable goals the reviewer can check}
- **Status**: PENDING
- **Review Rejections**: 0
```

`Absorbed` and `Tests` are additive — the orchestrator reads `Status` and `Review Rejections`
and ignores the rest, so adding them breaks nothing.

Then add the **dependency graph** and the **status table** (see the template). Header
line: `{N} tasks. **Unblocked now: #…**`.

- Every `Target Files` path must come from the `ARCHITECTURE.md` naming table or
  `DESIGN.md` — do not invent paths.
- Every task starts `Status: PENDING` and `Review Rejections: 0` — the orchestrator owns
  these fields from here on; don't pre-fill statuses.

### 6. Name the layer's test and review agents when the feature is not Python

`agent-developer` codes every layer and needs no note. The **test and review** agents do:
`test-engineer` writes **pytest under `hardware-agent/tests/`** and `code-reviewer` gates on
**`uv run pytest` + `uv run ruff check`**, neither of which exists in `frontend/`. When the feature's blast radius is not the Python layers, say so at
the top of `TASKS.md`, name the agents to spawn instead, and state the gate command:

| Blast radius | Test agent | Review agent | Gate |
|---|---|---|---|
| `hardware-agent/`, `backend/` | `test-engineer` | `code-reviewer` | `uv run pytest` + `uv run ruff check` |
| `frontend/` | `frontend-test-engineer` | `frontend-code-reviewer` | `npm run lint && npm run format:check && npm run typecheck && npm run test && npm run build` |

### 7. Honor the CLAUDE.md integration rule

When any task adds a parameter to `ScanOrchestrator` / `ScanRunner`, you **must** add
explicit task(s) (or `Target Files` entries) threading it through
`hardware-agent/src/agent/scanner/runner.py` (`ScanRunner`) **and**
`hardware-agent/src/agent/tui/screens/scan_progress.py` (`ScanProgressScreen`). TUI scans
bypass `ScanOrchestrator.run()`, so a parameter that isn't threaded reaches no TUI scan.

### 8. Report

Print the path you wrote and a short summary: total task count, parallel tracks, which tasks
are **unblocked now**, and — when step 3 merged anything — what was absorbed and into what.
Then tell the operator the next step is **`/feature-orchestrator`**.

## Rules

- **Write a file, not harness tasks** — output is `TASKS.md`; do not call `TaskCreate` /
  `TaskUpdate`.
- **Reference spec files** in each `Description` (e.g. "per ARCHITECTURE.md naming table").
- **Verifiable `Success Criteria`** in every task — the reviewer gates on them.
- **One task per testable unit** — don't combine unrelated changes, and don't split a unit
  that cannot be tested on its own (step 3).
- **Every task delivers at least one test file**, named in `Tests`. A task with no test file
  in its `Target Files` is a merge candidate, not a task. The only exception is a task whose
  spec genuinely defines no testable artifact anywhere in the feature — say so explicitly and
  justify it, because it means the reviewer has nothing but greps to gate on.
- **Never create tasks for out-of-scope items** marked "out of scope (v1)", "deferred", or
  "not v1" in `TRUTH.md` / `decisions/`, or anything in `open-questions/`.
- **Don't overwrite a TASKS.md the orchestrator is already driving** — if one exists with
  non-`PENDING` statuses or `Review Rejections > 0`, stop and confirm before regenerating.
- **Aim for 6–12 tasks; hard cap ~15.** If decomposition yields more, merge related atoms —
  step 3 usually removes the overflow on its own. Under-splitting is recoverable (the coder
  does more in one pass); over-splitting is not, because every extra task is three agent
  invocations spent whether or not it earned them.

## Depth

Decomposition categories, criteria→task mapping, dependency heuristics, and the task-body
template: [REFERENCE.md](REFERENCE.md). Canonical file shapes live in `specs/_templates/`.
