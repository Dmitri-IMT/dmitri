---
name: create-issue
description: >-
  Create a new GitHub issue with the gh CLI, assigned to a collaborator, with the right labels,
  and a structured body (description, acceptance criteria, ADR references, blockers) that the
  get-issue skill can later parse. Use when the user says "create an issue", "open a ticket",
  "file a bug", "make a GitHub issue for X", or wants to hand work off to a following agent.
compatibility: Requires GitHub CLI (gh) authenticated with the `repo` scope; designed for GitHub.com repositories
metadata:
  author: github-cli-skills
  source: skills/github-cli/create-issue.md
---

# Issue Creator

Create a well-structured GitHub issue via `gh` so the next agent picking it up with the
`get-issue` skill gets full, parseable context: a clear description, an acceptance-criteria
checklist, ADR references, blockers, and component labels.

## When to Use

- User says "create an issue", "open a ticket", "file a bug", "make a GitHub issue for X"
- User wants to capture follow-up work or hand a task to a following agent
- A problem surfaced during work that should be tracked rather than fixed now

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). Treat it as the raw
problem statement — the title and body are derived from it.

## Prerequisites

- GitHub CLI (`gh`) installed and authenticated with the `repo` scope
- Current directory is the target git repository (`Dmitri-IMT/dmitri`)

## Defaults for this repo

- **Default assignee**: `rontho14` (override per-issue if the user names someone else).
  Other collaborators: `RafaelBertani`, `Chambs`, `ferrenha`, `giuliano-rt`.
- **Project board**: NOT handled by this skill. The current `gh` token lacks the
  `read:project` / `project` scope. If the user wants the issue on a board, tell them to run
  `gh auth refresh -s project,read:project` and add it manually (or via `gh project item-add`).

## Available labels

Apply labels from these groups (only those that fit — do not over-label):

| Group | Labels |
|-------|--------|
| Epic / component | `epic:backend`, `epic:frontend`, `epic:agent`, `epic:architecture`, `epic:research`, `epic:polishing` |
| Type | `bug`, `type:adr`, `type:documentation`, `type:test` |
| Priority | `priority:critical`, `priority:high`, `priority:medium`, `priority:low` |
| Size | `size:S` (2-4h), `size:M` (4-8h), `size:L` (8-16h) |
| Status | `status:blocked`, `status:needs-grooming` |

If unsure which labels exist, refresh the list:

```bash
gh label list --limit 50
```

## Outline

### 1. Derive the title

From `$ARGUMENTS`, write a concise, imperative title (≤ ~70 chars), e.g.
"Fix scan duration showing 0s for cancelled scans". If the input is too vague to title,
ask the user one clarifying question before proceeding.

### 2. Classify component, type, priority, size

Map the problem to labels:

- **Component** (pick the primary `epic:*`): keywords like `FastAPI`/`endpoint`/`PostgreSQL`
  → `epic:backend`; `React`/`UI`/`TypeScript` → `epic:frontend`; `Nmap`/`scan`/`Textual`/`TUI`/
  `hardware-agent` → `epic:agent`; `ADR`/`ARCHITECTURE.md`/`docs` → `epic:architecture`.
- **Type**: a defect → `bug`; a new ADR → `type:adr`; docs work → `type:documentation`;
  test-only work → `type:test`.
- **Priority / size**: infer from the user's urgency and scope; if genuinely unclear, ask
  or default to `priority:medium` and add `status:needs-grooming`.

State the chosen labels to the user before creating.

### 3. Build the issue body

Use this exact template so the `get-issue` skill can parse it. Fill every section; omit a
section only if truly not applicable.

```markdown
## Description

<2-4 sentence problem statement: what is wrong / needed and why it matters.>

## Acceptance Criteria

- [ ] <First concrete, verifiable requirement>
- [ ] <Second requirement>
- [ ] <Tests added/updated and passing (uv run pytest)>

## Context for the implementer

<Pointers the next agent needs: affected files, call paths, the CLAUDE.md integration rule
if a new parameter must be threaded through ScanRunner/ScanProgressScreen, repro steps for
bugs, etc.>

## Related Architecture

<ADR references in the form ADR-NNN, e.g. "Relates to ADR-006 (scan duration)." If none,
write: "No ADRs directly referenced.">

## Blockers & Dependencies

<Use parseable patterns: "Blocked by #NN", "Depends on #NN". If none, write:
"No blockers or dependencies identified.">
```

The acceptance criteria MUST be a `- [ ]` checklist — `get-issue` extracts these directly.
Use `ADR-NNN` and `Blocked by #NN` / `Depends on #NN` literal patterns so detection works.

### 4. Confirm assignee

Default to `rontho14`. If the user named a different person, use that collaborator instead.
Validate the handle is one of the known collaborators; if not, ask.

### 5. Create the issue

Write the body to a temp file (avoids shell-escaping issues with multi-line markdown), then:

```bash
gh issue create \
  --title "<TITLE>" \
  --body-file "<TEMP_BODY_FILE>" \
  --assignee "<ASSIGNEE>" \
  --label "<label1>" --label "<label2>" --label "<label3>"
```

Notes:
- Pass each label with its own `--label` flag (or a single comma-separated `--label` value).
- If a `--label` is rejected as nonexistent, run `gh label list` and correct it; do not
  invent labels or create new ones unless the user asks.
- Do NOT add `--project`; this skill intentionally skips the project board (see Defaults).

### 6. Report result

After creation, `gh issue create` prints the new issue URL. Report to the user:

```markdown
✅ Created issue #<N>: <TITLE>
- Assignee: @<assignee>
- Labels: <label1>, <label2>, <label3>
- URL: <url>

Next: an agent can run `get-issue <N>` to pull full context and start work.
```

## Example

```text
User: "Create an issue: the TUI scan progress bar freezes at 90% on large subnets.
       High priority, assign to giuliano-rt."

Skill:
- Title: "Fix TUI scan progress bar freezing at 90% on large subnets"
- Labels: epic:agent, bug, priority:high
- Assignee: giuliano-rt
- Body: Description + Acceptance Criteria checklist + implementer context + ADR/blockers
- Runs: gh issue create --title ... --body-file ... --assignee giuliano-rt
        --label epic:agent --label bug --label priority:high

Output:
✅ Created issue #91: Fix TUI scan progress bar freezing at 90% on large subnets
- Assignee: @giuliano-rt
- Labels: epic:agent, bug, priority:high
- URL: https://github.com/Dmitri-IMT/dmitri/issues/91
```

## Limitations

- Requires authenticated `gh` CLI with `repo` scope.
- Does not add issues to a project board (missing `project` scope) — handled manually.
- Label/priority/size classification is heuristic; confirm with the user when ambiguous.

## Troubleshooting

- **"could not add label: 'X' not found"**: run `gh label list` and use an existing label.
- **"could not assign user"**: handle must be a repo collaborator; check spelling.
- **Multi-line body mangled**: always use `--body-file` with a temp file, not inline `--body`.
- **Auth errors**: run `gh auth status`; re-authenticate with `gh auth login` if needed.
