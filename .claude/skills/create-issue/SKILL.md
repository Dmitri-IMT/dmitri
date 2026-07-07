---
name: create-issue
description: >-
  Create a new Linear issue (team Dmitri) via the Linear MCP, written to the agentic
  product-brief template and human-validated BEFORE creation — this skill is the pipeline
  gate: no issue exists until the vision is decided and the user approves. Use when the user
  says "create an issue", "open a ticket", "file a bug", "make an issue for X", or wants to
  hand work off to an agent or teammate.
compatibility: Requires the linear-server MCP connection; GitHub is no longer used for issues.
metadata:
  author: dmitri
  source: docs/roadmap/linear-setup-plan.md (Phase 1/3)
---

# Issue Creator (Linear) — the pipeline gate

Create a Linear issue that is a **finished product brief**: vision decided, feasibility
settled, scope fenced, tests defined. The coder who picks it up never thinks about the
product — they Just Build. Because agents are always human-handled, validation happens in
this conversation *before* the issue is created; the created issue carries a Validation
stamp as the record.

**Never reference the spec (`specs/NNN-slug/`) or TASKS.md inside the issue.** Those are
developer/orchestrator pipeline artifacts created at build time, not issue content.

## When to Use

- User says "create an issue", "open a ticket", "file a bug", "make an issue for X"
- User wants to capture follow-up work or hand a task to an agent/teammate
- A decision just closed and its "to validate after" items in an epic description can now
  become real sub-issues

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). Treat it as the raw
problem statement — the title and brief are derived from it.

## Prerequisites

- Linear MCP tools available (`mcp__linear-server__*`); load via ToolSearch if deferred:
  `save_issue`, `get_issue`, `list_issues`, `list_issue_labels`, `list_users`
- Workspace: `dmitri-imt` · Team: **Dmitri (DMI)** · Project: **Dmitri**
- Current milestone: **MVP — Control** (target 2026-08-15) — apply unless the work is
  clearly outside it

## Defaults for this workspace

- **Default assignee**: Guilherme Ronca (`me`). Ask if the user names someone else and
  verify with `list_users`.
- **Parent epic**: MVP work belongs under one of the delivery-phase epics (parent issues).
  Find them with `list_issues` filtered to project Dmitri, or ask the user which epic.
- **Blocked-by relations**: set real `blockedBy` relations, not prose.

## Available labels

Apply only what fits — do not over-label. Refresh with `list_issue_labels` (team Dmitri)
if unsure.

| Group | Labels |
|-------|--------|
| Layer | `layer:pi`, `layer:backend`, `layer:frontend`, `layer:auth` |
| Kind | `agentic` (every coding issue), `type:ops`, `type:decision`, `Bug`, `type:adr`, `type:documentation` |
| Priority | `priority:critical`, `priority:high`, `priority:medium`, `priority:low` (or Linear's native priority field — prefer the native field) |
| Size | `size:S` (2-4h), `size:M` (4-8h), `size:L` (8-16h) |

`Migrated` is reserved for imported GitHub history — never apply it to new issues.

## Outline

### 1. Classify: coding issue or not?

- **Coding issue** → agentic template below, label `agentic` + one `layer:*`.
- **Ops / decision / review work** → label `type:ops` or `type:decision`; simpler free-form
  body (context, checklist, decision record or runbook link). Skip the template but NOT the
  validation gate (step 4).

### 2. Check the size

A coding issue is right-sized when one concise TRUTH/ARCHITECTURE/DESIGN spec *could* cover
it. If the request spans multiple contracts, screens, or unrelated behaviors, propose a
split (possibly a parent epic + sub-issues) before writing anything.

### 3. Draft the brief

Title: concise, imperative, ≤ ~70 chars. Body for coding issues — this exact structure:

```markdown
## Vision
<What we aim to build and why — the product decision, already made. 2–4
sentences. Link the owning repo docs (roadmap/ADR/architecture) for depth —
never copy their content here.>

## Use cases
- As <who>, I <do what>, so that <outcome>

## Expected
- <observable behavior/result bullets — what exists when this is done>

## NOT expected
- <explicit non-goals: adjacent behavior deliberately not built, edge cases
  deliberately not handled, things a coder might be tempted to add>

## Test cases
- Given <state>, when <action>, then <verifiable result>
- <cover the happy path, the main failure path, and each Expected bullet>
- `uv run pytest` and `uv run ruff check` pass on the touched scope

## Implementation notes (optional)
- Likely files/areas: <paths>
- Hard constraints: <e.g. the CLAUDE.md ScanRunner call-site rule, contract
  files that must not change>

## Validation
- Approved by @<name> on <date>

## Agent workflow
- Branch from Linear's suggested branch name; PR body includes "Fixes DMI-NN"
- Do not expand scope beyond this issue; follow-ups become new issues
- Blocked-by relations are real gates — do not start early
```

### 4. THE GATE — validate with the human (mandatory, never skip)

Present to the user, compactly: title, the full draft brief, labels, assignee, parent epic,
milestone, blocked-by list. Then explicitly confirm:

1. **Vision decided?** Nothing in this issue is still an open product question. If any
   "Expected" bullet is actually undecided, STOP — the item goes into the parent epic's
   description as "to validate after <decision>", not into an issue.
2. **Expected / NOT expected agreed?** The scope fence is where coders drift; make the user
   read it.
3. **Blockers named?** Every real gate is a `blockedBy` relation.

Only on explicit approval ("go", "approved", "yes") fill the Validation line with the
user's name and today's date, then create. If the user hesitates or edits, revise and
re-confirm. **An issue without a Validation stamp should not exist.**

### 5. Create the issue

Use `mcp__linear-server__save_issue` (no `id` — creation): `team: "Dmitri"`,
`project: "Dmitri"`, `title`, `description` (the brief), `assignee`, `labels`, `milestone`,
`parentId` (epic), `priority`, `blockedBy` (issue identifiers). Content goes as real
markdown with literal newlines.

### 6. Report result

```markdown
✅ Created DMI-<N>: <TITLE>
- Epic: <parent> · Milestone: <milestone>
- Assignee: <name> · Labels: <labels>
- Blocked by: <DMI-XX, …> | none
- Validated by @<name> on <date>
- URL: <url>

Next: an agent can run `get-issue DMI-<N>` to pull full context and start work.
```

## Example

```text
User: "Create an issue: the TUI scan progress bar freezes at 90% on large subnets.
       High priority."

Skill:
- Classifies: coding issue (layer:pi, agentic, Bug), right-sized.
- Drafts brief: Vision (fix the freeze; links roadmap/tests docs), use case,
  Expected (bar reaches 100% / partial-cancel works), NOT expected (no progress
  redesign), test cases, notes (scanner.py, ScanProgressScreen).
- Presents draft → user tweaks a NOT-expected bullet → user says "approved".
- Stamps: Approved by @Guilherme Ronca on 2026-07-04. Creates via save_issue.

Output: ✅ Created DMI-51: Fix TUI scan progress bar freezing at 90% on large subnets
```

## Limitations

- Requires the Linear MCP connection (`linear-server`).
- Cannot delete issues or create Linear issue *templates* — template parity is maintained by
  this skill's body structure matching the team template "Agentic coding issue".
- Label/priority/size classification is heuristic; the gate conversation is where it gets
  corrected.

## Troubleshooting

- **Label rejected**: run `list_issue_labels` for team Dmitri and use an existing one; do
  not invent labels without the user asking.
- **Assignee not found**: run `list_users` and confirm the name with the user.
- **Escaped `\n` in the created body**: pass real newlines in `description`, never literal
  escape sequences.
