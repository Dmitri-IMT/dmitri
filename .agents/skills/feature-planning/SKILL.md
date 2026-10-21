---
name: feature-planning
description: >-
  Creates approved, testable feature specs in specs/. Use when the user asks to plan or specify
  a feature. It writes TRUTH.md and delegates architecture and relevant design docs, then stops
  for human approval without implementing application code.
---

# Feature Planning

Phase 1 of Dmitri's document-driven pipeline. Write specs, then stop for human approval.
Do not implement application code or create `TASKS.md`.

1. Use the feature request and consult `consult-docs` (`docs/README.md` plus at most two
   relevant docs). Check `.claude/docs/index.md` for the canonical code map.
2. Pick the next `NNN-feature-slug` based on numeric spec directories.
3. Write `TRUTH.md` with domain narrative, business rules, user stories, verifiable
   Given/When/Then criteria, and explicit out-of-scope items. Keep code paths out of TRUTH.
4. Spawn `architecture-agent` to produce `ARCHITECTURE.md` and `INTEGRATION.md` only for a
   real cross-layer contract. Require exact existing/new paths, contracts, and test expectations.
   This repository is multi-layer; do not apply the old single-layer assumption. Capture its
   handoff and close or release the worker through the native client's supported thread-lifecycle
   action before spawning another role. If no close action is exposed, use a separate sequential
   session so the completed worker does not remain open against the thread cap; do not assume an
   unavailable close tool or skip a required role.
5. If UI changes, spawn `frontend-design-agent` for React or the available design role for
   Textual only after closing or releasing the architecture worker; include mockups, states, copy,
   accessibility, and exact paths. Apply the same lifecycle to any other planning role.
6. Pass file paths and criteria to child agents, not large pasted documents. Verify every
   named path against the code-map and source.
7. Summarize the files and ask the user to approve `TRUTH.md`, `ARCHITECTURE.md`, `DESIGN.md`
   (if present), and file/naming conventions. Stop. The next step after approval is
   `create-tasks` or `feature-orchestrator`.

Use the linked [`REFERENCE.md`](REFERENCE.md) for the canonical flat spec shapes and numbering.
