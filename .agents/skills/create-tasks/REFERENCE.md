# Reference — create-tasks skill

Maps the flat Peirce specs (`TRUTH.md`, `ARCHITECTURE.md`, `DESIGN.md`,
`INTEGRATION.md`) to implementation-atom categories and the canonical `TASKS.md` shape.

## Decomposition guide

Each category produces a distinct type of **atom**. The `Target Files` of every task come
from the `ARCHITECTURE.md` **"New files and naming" table** (or `DESIGN.md` widget ids).

> **An atom is not automatically a task.** Categories below are how you *find* the work, not
> how you *package* it. After listing atoms, run SKILL.md step 3's test viability check and
> merge every atom that cannot deliver a test that would fail if the atom were done wrong.
> Category 1 atoms in particular are usually merged, not shipped alone: a constant with no
> branching is verified by whatever consumes it. Category 6 is the extreme case — see its note.

### Category 1: Config & constants

Source: `ARCHITECTURE.md` → "Data model / contracts" + naming-table `Config` row.

Atoms:
- New `config.py` constants (port sets, NSE script tuples, timeouts)
- `scan_mode` Literal extensions and mode-helper branches
  (`port_stage_scripts()` / `deep_stage_scripts()`)

Task pattern: "Add {CONSTANT} to config.py per ARCHITECTURE.md"

### Category 2: Pure helpers & generators

Source: `ARCHITECTURE.md` contracts (naming rules, argv/flag sets, grammars).

Atoms:
- Name/path generators, argv/command builders (flag injection, dedup)
- Serialization / encoding / format utilities
- Merge helpers (e.g. dedup ports by `(port, protocol)`)

Task pattern: "Build {thing} generator per ARCHITECTURE.md"

### Category 3: Core behavior (discovery / pipeline / normalization)

Source: `ARCHITECTURE.md` "System context" + naming-table `Discovery` / `Normalize` rows.

Atoms:
- New runners, scan passes, processors, I/O handlers
- `ScanPayload` / pydantic field changes in `normalize/contracts.py`
- Metadata writers

Task pattern: "Implement {behavior} per ARCHITECTURE.md"

### Category 4: TUI screens

Source: `DESIGN.md` (screen flow, layout, key bindings, copy, widget ids).

Atoms:
- New Textual screens (one task per screen)
- Screen behavior changes (category-aware option lists, new bindings, copy)
- Widget-id additions needed for tests

Task pattern: "Create {Screen} per DESIGN.md" / "Update {Screen} for {change}"

### Category 5: Caller / integration updates

Source: `ARCHITECTURE.md` call sites + the CLAUDE.md integration rule.

Atoms:
- Wire new modules into existing call sites (orchestrator, runner, screens)
- **Thread new orchestrator/runner params through `ScanRunner`
  (`scanner/runner.py`) and `ScanProgressScreen` (`tui/screens/scan_progress.py`)** —
  mandatory whenever a param is added; TUI scans bypass `ScanOrchestrator.run()`

Task pattern: "Wire {caller} to use {new-module}" / "Thread {param} through ScanRunner + ScanProgressScreen"

### Category 6: Tests

Source: `ARCHITECTURE.md` "Testing expectations" + `TRUTH.md` acceptance criteria.

Atoms:
- Unit tests under `hardware-agent/tests/unit/` for new constants / helpers / merges
- Tests asserting behavior for each acceptance-criteria scenario
- Follow the nearest existing test (e.g. `test_scan_mode_scripts.py`) for patterns

Task pattern: "Unit tests for {thing}" — one task per coherent test target.

**Prefer tests inside the task that builds the thing.** A separate test task is worth it only
when the suite is large enough to stand alone (a full rule table, a state matrix) or when it
spans several earlier tasks. Otherwise the test belongs in the implementing task's
`Target Files`, named in its `Tests` field — that is what makes step 3's viability check pass
and what stops thin atoms from becoming their own review cycles.

## Acceptance criteria → task mapping

`TRUTH.md` holds a verifiable acceptance-criteria table (Given/When/Then). Use it as the
cross-check: **every scenario must map to at least one task** (an implementation task, a
test task, or both). If a scenario has no corresponding task, either add one or confirm an
existing task's `Success Criteria` already covers it. The `Success Criteria` you write
should trace back to these scenarios so the code reviewer can gate on them.

## Dependency heuristics

```
config/constants ──→ helpers ──→ core behavior ──→ caller/integration
       │                              │
       └──────────────→ tests        └──→ TUI screens ──→ TUI wiring
```

- Config/constant tasks block everything that reads those constants
- Schema/`ScanPayload` tasks block any code that builds or validates that payload
- Helper tasks block the core behavior that uses them
- Core behavior tasks block the integration/wiring task
- Screen tasks block the screen that pushes them and the wiring task
- A param added to the orchestrator/runner blocks the `ScanRunner` /
  `ScanProgressScreen` threading task (CLAUDE.md rule)

Encode dependencies in each task's `Dependencies` field and in the `## Dependency graph`
block at the bottom of `TASKS.md`.

## Exclusion rules

Do NOT create tasks for:
- Items under `TRUTH.md` "Out of scope (v1)", or marked "deferred" / "not v1" /
  "superseded" in `decisions/`
- Anything in `open-questions/to-define.md` (unresolved — blocks, not work)
- Separate test suites beyond `ARCHITECTURE.md` "Testing expectations"
- CI/CD or infrastructure changes (the architecture agent flags
  `HUMAN_INFRA_REQUIRED` for those — they are human-only)
- Documentation files (the specs ARE the documentation)

## Task body template

Fill the canonical orchestrator shape (matches `specs/_templates/TASKS.md`):

```markdown
## Task N: {imperative verb + what}
- **Description**: {2–3 sentences: what to implement, which spec file governs it}
- **Absorbed**: {atoms merged in per SKILL.md step 3, and why each could not carry a test —
  omit the line entirely when nothing was merged}
- **Dependencies**: {task numbers, or —}
- **Target Files**: [{exact paths from the ARCHITECTURE.md naming table / DESIGN.md}]
- **Tests**: {the test file(s) this task delivers and what they prove}
- **Success Criteria**:
  - {Verifiable goal 1 — what the reviewer checks}
  - {Verifiable goal 2}
  - Tests: {specific function/behavior the unit test must verify}
- **Status**: PENDING
- **Review Rejections**: 0
```

Then close `TASKS.md` with the dependency graph and status table from the template. Leave
`Status: PENDING` and `Review Rejections: 0` untouched — the per-task build loop owns
those fields once the build starts.
