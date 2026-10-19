---
name: feature-orchestrator
description: >-
  Drives an approved feature spec through TASKS.md and a sequential coder, tester, reviewer
  loop. Use only after the required specs have human approval or when asked to start execution.
---

# Feature Orchestrator

Act as project manager. Do not implement application code, run gates as the reviewer, commit,
or open pull requests. Use the custom Codex agents defined in `.codex/agents/` and spawn each
only when its step is reached. Keep all tasks sequential: one coder at a time. After each role
finishes, capture its result and file handoff, then close or release that worker with the native
client's supported thread-lifecycle action before spawning the next role. Apply this to coder,
tester, reviewer, structural-re-evaluation, and closeout roles. If the client exposes no thread
closure action, use separate sequential sessions so completed workers do not remain open against
the configured thread cap; do not assume an unavailable close tool or skip a required role.

## Prerequisites

Require human-approved `TRUTH.md` and `ARCHITECTURE.md`, plus `DESIGN.md` for changed UI, in
the feature directory. If a required spec is not approved, stop at the spec approval gate.
Before creating tasks, confirm branch, HEAD, worktree changes, and scope. Preserve all existing
work. Read `.claude/docs/index.md` as the canonical code-map.

## Task ledger

Create or update `TASKS.md` using the `create-tasks` skill. Each task must name exact target
files, test files, verifiable success criteria, dependencies, status, and review rejection count.
Every task must be testable. Do not mark a task complete without reviewer `[APPROVE]`.

## Sequential task loop

For each unblocked task, in dependency order:

1. Spawn `agent-developer` with the spec paths and that task only. It implements all criteria
   and reports changed files.
2. Spawn the layer-appropriate test agent (`test-engineer` for hardware-agent/backend;
   `frontend-test-engineer` for frontend) with the task, coder handoff, and allowed paths.
3. Spawn the matching reviewer (`code-reviewer` or `frontend-code-reviewer`). The reviewer
   runs the scoped layer gates and is the only authority for approval. Require first line
   `[APPROVE]` or `[REJECT]`.
4. On `[APPROVE]`, mark complete and move to the next task. On `[REJECT]`, increment the
   rejection count and spawn a fresh coder with the complete feedback; never resume the old
   coder. Re-run testing if the rejection changes behavior or tests. If the same reason recurs
   on the second rejection, revisit the architectural decision before another implementation.

Never run two task coders in parallel. After the fourth rejection on one task, set
`BLOCKED_STRUCTURAL`, spawn `architecture-agent` to write `STRUCTURAL_REEVAL.md`, capture its
handoff, and close or release it before spawning the relevant design agent for the same
re-evaluation. Revise the specs and task ledger, then stop for human approval. Only after approval
reset the rejection count and start a fresh coder.

Do not use model names in prompts as a substitute for selection. Use the configured models in
`.codex/agents/*.toml`; when a task needs a higher reviewer effort, select it through the real
spawn configuration if supported, otherwise run that role in a separate session. Never silently
substitute a model.

## Closeout

After all tasks are approved, spawn `docs-sync-agent` once for the whole feature diff and have it
run the `docs-sync` skill using its configured agent profile. It owns
`.claude/docs/`, makes only clear factual patches to `docs/`, and reports contested drift.
Then summarize completed tasks, gates, limitations, and any docs drift. Leave commits and PRs
to the user.
