---
name: create-tasks
description: >-
  Converts human-approved feature specs into a small sequential TASKS.md ledger with testable
  tasks, exact target files, dependencies, and acceptance criteria. Use before orchestration.
---

# Create Tasks

Read the approved `TRUTH.md`, `ARCHITECTURE.md`, and `DESIGN.md` when present. Do not implement
code or overwrite a ledger already in progress. Use `.claude/docs/index.md` to verify code
locations, and [`REFERENCE.md`](REFERENCE.md) for decomposition and the task shape.

Create tasks from testable implementation units. Every acceptance scenario maps to at least one
task. Merge atoms that cannot carry a meaningful test into the task that makes them observable;
record merged work as `Absorbed:` so scope remains visible. Do not merge work that has meaningful
branching or behavior just to avoid testing. Include exact paths from the architecture naming
table and identify the tests each task adds or changes. Keep task order sequential and encode
dependencies. Prefer 6–12 tasks, with a hard cap near 15.

Use the checked-in [`TASKS.template.md`](TASKS.template.md). Each task must contain Description,
Dependencies, Target Files, Tests, Success Criteria, `Status: PENDING`, and
`Review Rejections: 0`. Name frontend or Python test/review roles according to target files.
Account for all integration call paths, including `ScanRunner` and `ScanProgressScreen` when
adding a scan parameter. Finish with a dependency graph and status table.

Report the path written, task count, parallel tracks if any, unblocked tasks, and the next step:
the per-task build loop.
