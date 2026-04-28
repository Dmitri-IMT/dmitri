---
name: get-issue
description: >-
  Extract full issue context including description, acceptance criteria, linked PRs, and related ADRs.
  Parse issue body for requirements, detect ADR references, and show dependencies.
  Use when starting work on an issue, asking "what's in this issue?", needing full context before implementation,
  or when an issue number is mentioned in conversation.
compatibility: Requires GitHub CLI (gh) and git; designed for GitHub.com repositories
metadata:
  author: github-cli-skills
  source: skills/github-cli/get-issue.md
---

# Issue Context Extractor

Extract comprehensive context from a GitHub issue including description, acceptance criteria,
linked ADRs, related PRs, blockers, and component classification.

## When to Use

- Starting work on a GitHub issue
- User asks "what's in this issue?" "let's work on this issue"
- Issue number referenced in conversation
- Need to understand requirements before implementation
- Setting up context for a feature branch

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Prerequisites

- GitHub CLI (`gh`) must be installed and authenticated
- Issue number or URL must be provided or detectable from context
- Current directory should be a git repository (for ADR lookups)

## Outline

### 1. Determine Issue Number

If `$ARGUMENTS` contains an issue number or URL, extract it.
Supported formats:
- `123` (issue number only)
- `https://github.com/owner/repo/issues/123` (full URL)
- `#123` (with hash prefix)

If no issue can be determined, prompt: "Please provide an issue number or URL (e.g., `123` or `https://github.com/owner/repo/issues/123`)".

### 2. Fetch Issue Details

Run the following command to get comprehensive issue data:

```bash
gh issue view <ISSUE_NUMBER> --json title,body,labels,state,assignees,number,createdAt,updatedAt,url
```

Parse the JSON output to extract:
- **title**: Issue title
- **body**: Full issue description (markdown)
- **labels**: Array of label objects
- **state**: OPEN or CLOSED
- **assignees**: Array of assigned users
- **number**: Issue number
- **createdAt**: Creation timestamp
- **updatedAt**: Last update timestamp
- **url**: Issue URL

### 3. Parse Acceptance Criteria

Search the issue body for acceptance criteria using these patterns:

**Pattern 1: Explicit section**
```
### Acceptance Criteria
- [ ] First requirement
- [ ] Second requirement
- [ ] Third requirement
```

**Pattern 2: Checklist anywhere in body**
```
- [ ] Requirement text
- [x] Completed requirement
```

**Pattern 3: Requirements section**
```
## Requirements
- Requirement 1
- Requirement 2
```

Extract all matching criteria into a checklist. If no criteria found, use the first paragraph of the body as the requirement summary.

### 4. Detect and Fetch ADR References

Search the issue body for ADR references using regex pattern: `ADR-(\d+)` or `adr-(\d+)` (case-insensitive).

For each detected ADR:

1. Look for file `docs/adr/ADR-<NUMBER>.md` in repository root
2. If file exists, read it and extract the first 3-5 lines (title and summary)
3. Store ADR number, title, and brief summary

Example extraction from issue body:
```
"This relates to ADR-003 (backend stack) and ADR-008 (frontend stack)."
```

Result:
```
- ADR-003: Backend Stack (FastAPI + PostgreSQL + SQLModel)
- ADR-008: Frontend Stack (React + TypeScript + Vite)
```

### 5. Find Related PRs

Search for PRs that reference this issue:

```bash
gh pr list --search "relates:PR_NUMBER #<ISSUE_NUMBER>" --state all --json number,title,state,url
```

Alternative: Search PR body/title for issue number:

```bash
gh pr list --search "<ISSUE_NUMBER>" --state all --limit 20 --json number,title,state,url
```

Filter results to keep only PRs that:
- Explicitly mention the issue number (e.g., "fixes #123", "closes #123", "relates to #123")
- Are in feature branches that logically belong to this work

Store: PR number, title, state (OPEN/MERGED/CLOSED), URL

### 6. Extract Blockers and Dependencies

Search issue body and comments for blocker patterns:

- `blocked by #<issue>` or `blocked on #<issue>`
- `depends on #<issue>` or `depends upon #<issue>`
- `waiting for #<issue>`
- `prerequisite: #<issue>`

Also search for text markers:
- "⛔ Blocked"
- "🚫 Cannot proceed"
- "⏳ Waiting for"

For each blocker/dependency found:
1. Extract the referenced issue number
2. Fetch that issue's title and state
3. Mark as blocker or dependency

Store as list with issue number, title, and status.

### 7. Classify Component

Determine which component(s) this issue belongs to based on:

**Primary signals** (from labels):
- Label `backend` → Backend API
- Label `frontend` → Frontend
- Label `hardware-agent` → Hardware Agent
- Label `infra` → Infrastructure & CI
- Label `docs` → Documentation

**Secondary signals** (from issue body keywords):
- Contains `backend`, `FastAPI`, `PostgreSQL`, `endpoint` → Backend API
- Contains `React`, `frontend`, `TypeScript`, `component`, `UI` → Frontend
- Contains `Raspberry Pi`, `Nmap`, `scanning`, `hardware-agent` → Hardware Agent
- Contains `deploy`, `Docker`, `CI/CD`, `workflow` → Infrastructure & CI
- Contains `documentation`, `ADR`, `README` → Documentation

Store component as primary classification with confidence level (HIGH/MEDIUM/LOW).

### 8. Generate Structured Output

Produce a markdown summary with the following structure:

```markdown
# Issue #<NUMBER>: <TITLE>

## Status
- **State**: OPEN | CLOSED
- **Assigned**: @username1, @username2 | Unassigned
- **Labels**: [label-1][label-2][label-3]
- **Component**: Backend API | Frontend | Hardware Agent | Infrastructure & CI | Documentation
- **Created**: <date> | **Updated**: <date>

## Description
<First 2-3 lines of issue body>

## Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3
- [ ] ...

[If no explicit criteria found]: 
```
### Full Context
<First paragraph or entire body if short>
```

## Related Architecture

ADRs relevant to this issue:

- **[ADR-003](docs/adr/ADR-003.md)** — Backend Stack: FastAPI + PostgreSQL + SQLModel
- **[ADR-008](docs/adr/ADR-008.md)** — Frontend Stack: React + TypeScript + Vite

[If no ADRs found]: No ADRs directly referenced in this issue.

## Related Pull Requests

| PR | Title | State |
|----|-------|-------|
| [#45](https://github.com/...) | Implement scan results dashboard | MERGED |
| [#52](https://github.com/...) | Add device filtering | OPEN |

[If no related PRs]: No related pull requests found yet.

## Blockers & Dependencies

⛔ **Blocked by**: #89 (Database migrations framework)  
⏳ **Depends on**: #75 (API authentication layer)

[If no blockers]: No blockers or dependencies identified.

## Next Steps

1. **Review acceptance criteria** above
2. **Check linked ADRs** for architectural context
3. **Review related PRs** for ongoing work
4. **Resolve blockers** if any before starting implementation
5. Create a feature branch when ready to start work

## Quick Links

- [View on GitHub](https://github.com/owner/repo/issues/123)
- [Related PRs](#related-pull-requests)
- [Acceptance Criteria](#acceptance-criteria)
```

### 9. Enrich with Component Info

If component is determined, append a brief component description:

```markdown
## Component Overview: Backend API

The Backend API (FastAPI + PostgreSQL) is responsible for:
- Receiving and validating scan payloads from the hardware agent
- Persisting results in PostgreSQL
- Exposing REST endpoints for the frontend
- Authentication and authorization
- Job queue management for background processing

See [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) section 2.2 for details.
```

### 10. Present to User

Output the structured summary. Highlight:
- Any **blockers** (user should resolve before starting)
- **Acceptance criteria** (clear deliverables)
- **Related ADRs** (architectural context)
- **Related PRs** (ongoing related work to avoid duplication)

## Integration with Project

- **ADR detection**: Uses regex to find ADR references; reads from `docs/adr/` directory
- **Component classification**: References labels and keywords against known component names
- **Architecture context**: Links to `docs/architecture/ARCHITECTURE.md` for component descriptions
- **Scope validation**: May reference project scope rule if issue scope is ambiguous

## Example Usage

```text
User: "What's in issue #42?"

Skill: [Fetches issue 42, finds ADR-003 reference, detects 2 blockers, links 3 related PRs]

Output:
# Issue #42: Implement device inventory filtering

## Status
- **State**: OPEN
- **Assigned**: @alice
- **Component**: Frontend
- **Created**: Apr 15 | **Updated**: Apr 21

## Acceptance Criteria
- [ ] Add filter input to device list
- [ ] Filter by device type (router, printer, etc.)
- [ ] Filter by subnet
- [ ] Persist filter preferences to localStorage

## Related Architecture
- **ADR-008** — Frontend Stack: React + TypeScript + Vite

## Related Pull Requests
| PR | Title | State |
|----|-------|-------|
| #39 | Device list component | MERGED |
| #41 | API device endpoint | OPEN |

## Blockers
⛔ **Blocked by**: #38 (Backend device type enumeration endpoint)

[Continue with next steps and links...]
```

## Limitations

- Requires authenticated `gh` CLI
- ADR detection is pattern-based (may miss references with different formatting)
- Blocker detection relies on standard GitHub patterns (custom formats may be missed)
- Component classification is heuristic-based (edge cases may need manual verification)
- May not detect all related PRs if they don't explicitly mention the issue

## Troubleshooting

- **"Issue not found"**: Verify issue number is correct and `gh` has repository access
- **No ADRs found**: Ensure ADRs exist and are named `ADR-<NUMBER>.md` in `docs/adr/`
- **Missing related PRs**: Related PRs may use different naming; check manually if needed
- **Character encoding**: Ensure terminal supports UTF-8 for emoji and special characters

## Best Practices

1. Always review acceptance criteria before starting work
2. Check for blockers — resolve them first if possible
3. Read linked ADRs to understand architectural context
4. Review related PRs to avoid duplicate work
5. Use this output to create your feature branch and commit messages
