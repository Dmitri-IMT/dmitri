---
name: get-issue
description: >-
  Extract full context from a Linear issue (DMI-NN): the product brief (vision, use cases,
  expected/not-expected, test cases), validation status, blockers, related ADRs, and linked
  PRs. Use when starting work on an issue, asking "what's in this issue?", needing full
  context before implementation, or when a DMI-NN identifier is mentioned in conversation.
compatibility: Requires the linear-server MCP connection; git repo for ADR lookups; gh CLI only for PR fallback.
metadata:
  author: dmitri
  source: docs/roadmap/linear-setup-plan.md (Phase 1)
---

# Issue Context Extractor (Linear)

Pull comprehensive context from a Linear issue so an agent can start building with zero
product thinking: the brief, the validation stamp, blockers, ADR context, and related PRs.

## When to Use

- Starting work on an issue ("let's work on DMI-43")
- User asks "what's in this issue?"
- A DMI-NN identifier appears in conversation
- Need to understand requirements before implementation

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Prerequisites

- Linear MCP tools (`mcp__linear-server__*`); load via ToolSearch if deferred:
  `get_issue`, `list_comments`, `list_issues`
- Git repository checkout (for ADR lookups under `docs/adr/`)

## Outline

### 1. Determine the issue

Accept: `DMI-43`, `43`, or a Linear URL (`https://linear.app/dmitri-imt/issue/DMI-43/...`).
Bare numbers are DMI-<N>. If nothing is determinable, ask for the identifier.

### 2. Fetch

`mcp__linear-server__get_issue` with `id: "DMI-<N>"` and `includeRelations: true`. Also
fetch `list_comments` for the issue — decisions and scope changes often live there.

Extract: title, description (the brief), state, assignee, labels, priority, project,
milestone, parent (epic), sub-issues, relations (blocked-by / blocks / related),
attachments (the GitHub integration attaches linked PRs here), `gitBranchName`, timestamps,
URL.

### 3. Parse the brief

Agentic issues (label `agentic`) follow the product-brief template — extract each section:

- **Vision** — the decided product intent + repo doc links
- **Use cases**
- **Expected** — the deliverables checklist
- **NOT expected** — the scope fence; surface this prominently, it is what keeps the build
  surgical
- **Test cases** — these become the verification plan
- **Implementation notes** — files/constraints
- **Validation** — the `Approved by @<name> on <date>` stamp
- **Agent workflow** — branch/PR rules

**If the Validation line is missing or unfilled on an `agentic` issue, STOP and flag it:
the issue was born outside the create-issue gate and must be validated by the user before
any work starts.**

Legacy issues (label `Migrated`) are read-only history in their original GitHub format —
parse best-effort (checklists, `## Description`, etc.) and say so.

### 4. Detect and fetch ADR references

Regex `ADR-(\d+)` (case-insensitive) over description + comments. For each hit, read
`docs/adr/ADR-<NNN>-*.md` and extract title + status line. Also follow any linked roadmap
docs (`docs/roadmap/*.md`) named in the Vision section — read only the sections the issue
points at.

### 5. Blockers and related work

- **Relations**: report blocked-by (with each blocker's state — an open blocker means do
  not start), blocks, related, parent epic, sub-issues.
- **PRs**: check the issue's attachments first (GitHub integration). Fallback:
  `gh pr list --search "DMI-<N>" --state all --json number,title,state,url`.

### 6. Present to user

```markdown
# DMI-<N>: <TITLE>

## Status
- **State**: <state> · **Assignee**: <name> · **Priority**: <p>
- **Epic**: <parent> · **Milestone**: <milestone>
- **Labels**: <labels>
- **Validation**: ✅ Approved by @<name> on <date> | ⚠️ NOT VALIDATED — stop
- **Branch**: `<gitBranchName>`

## Vision
<verbatim>

## Expected / NOT expected
<both lists verbatim — the fence matters as much as the goal>

## Test cases
<verbatim>

## Related architecture
- **ADR-NNN** — <title>: <one-line summary>
[or] No ADRs referenced.

## Blockers & related
⛔ Blocked by: DMI-XX (<state>) …
🔗 Related / PRs: …
[or] No blockers; no linked PRs.

## Next steps
1. Resolve/confirm blockers
2. Branch from `<gitBranchName>`
3. Build to Expected, fenced by NOT expected; verify with the test cases
4. PR body includes "Fixes DMI-<N>"
```

Highlight open blockers and a missing validation stamp above everything else.

## Limitations

- Requires the Linear MCP connection.
- ADR detection is pattern-based; unusual formatting may be missed.
- PR linkage depends on the Linear↔GitHub integration; the `gh` fallback needs the CLI
  authenticated.
- `Migrated` issues predate the template — extraction is best-effort.

## Troubleshooting

- **Issue not found**: confirm the DMI-NN identifier; try `list_issues` with a title query.
- **No ADR files found**: ADRs live at `docs/adr/ADR-<NNN>-<slug>.md`.
- **No PRs shown**: check the issue's attachments in Linear; the integration may not be
  connected yet (linear-setup-plan Phase 6).
