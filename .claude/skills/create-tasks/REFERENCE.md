# Reference — create-tasks skill

## Decomposition guide

Map spec artifacts to implementation atom categories. Each category produces a distinct type of task.

### Category 1: Data models & schemas

Source: `contracts/*.md` (schemas, enums, required/optional fields)

Atoms:
- Pydantic/dataclass models matching contract schemas
- Enum types for constrained values
- Validation helpers

Task pattern: "Implement {schema-name} model per contracts/{file}.md"

### Category 2: Pure helpers & generators

Source: `contracts/*.md` (naming rules, grammars), `tech-stack/README.md`

Atoms:
- Name/path generators (e.g. folder basename builders)
- Argv/command builders (flag injection, dedup)
- Serialization helpers
- Encoding/format utilities

Task pattern: "Build {thing} generator per contracts/{file}.md"

### Category 3: Infrastructure modules

Source: `decisions/*.md` (workspace, layout), `contracts/layout.md`

Atoms:
- Directory creation / ensure functions
- Migration logic (move files between layouts)
- Retention / pruning (cap enforcement)
- Config extensions

Task pattern: "Create {module} module per decisions/{file}.md"

### Category 4: Core behavior

Source: `architecture/README.md`, `decisions/*.md`, `tech-stack/README.md`

Atoms:
- New runners, processors, or I/O handlers
- Streaming implementations
- Metadata writers

Task pattern: "Implement {behavior} per architecture/README.md"

### Category 5: Caller updates

Source: `architecture/README.md` (call sites), `ui/README.md`, existing code

Atoms:
- Update existing functions to use new modules (e.g. write_scan_result → results/)
- Update screens to read from new paths
- Wire new modules into pipeline/orchestrator

Task pattern: "Update {caller} to use {new-module}"

### Category 6: UX & copy

Source: `ui/README.md`, `interaction/README.md`

Atoms:
- Screen text/copy updates
- New UI elements or bindings (if any)
- Help text changes

Task pattern: "Update {screen} copy to reflect {change}"

## Checklist → task mapping

Use `checklists/requirements.md` as a cross-check. Each checklist item should map to at least one task. If a checklist item has no corresponding task, either:
1. Add a task for it, or
2. Verify it's covered by an existing task's scope

## Dependency heuristics

Common dependency patterns:

```
models/schemas ──→ helpers ──→ infrastructure ──→ core behavior ──→ integration
                                    │
                                    └──→ caller updates ──→ UX/copy
```

- Schema tasks block everything that produces or consumes that schema
- Helper tasks block the core behavior that uses them
- Infrastructure tasks (workspace, dirs) block caller updates that need the new layout
- Core behavior tasks block the integration/wiring task
- Caller updates block UX/copy tasks

## Exclusion rules

Do NOT create tasks for:
- Items explicitly marked "not v1", "deferred", or "out of scope" in decisions/
- Items in `notes/open-questions.md` under "Deferred watchlist"
- Separate test suites beyond what testing/README.md mandates
- CI/CD pipeline changes unless explicitly required
- Documentation files (the spec IS the documentation)

## Task description template

```
{What to implement — 2-3 sentences}

Per {spec-file-reference}:
- {Key requirement 1}
- {Key requirement 2}
- {Key requirement 3}

Tests: {What unit tests to write — specific function/behavior to verify}
```
