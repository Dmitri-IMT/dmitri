---
name: gh-change-summary
description: >-
  Analyze PR changes and generate natural language summary by component.
  Parse diffs to extract breaking changes, documentation gaps, and security-relevant modifications.
  Use when discussing code changes, asking "what changed?", "summarize this PR", or reviewing PRs
  across multiple components (backend, frontend, hardware-agent, contracts, docs).
compatibility: Requires GitHub CLI (gh) and git; designed for GitHub.com repositories
metadata:
  author: github-cli-skills
  source: skills/github-cli/gh-change-summary.md
---

# PR Change Summary

Analyze pull request changes and generate a natural language summary organized by component.
This skill categorizes file changes, identifies breaking changes, highlights documentation gaps,
and flags security-relevant modifications.

## When to Use

- User views a PR or discusses code changes
- User asks "what changed?", "summarize this PR", or "what should I review?"
- PR contains changes across multiple components
- Need quick onboarding context before PR review
- Preparing for code review discussion

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Prerequisites

- GitHub CLI (`gh`) must be installed and authenticated
- Current directory must be a git repository
- PR number or URL must be provided or detectable from context

## Outline

### 1. Determine PR Number

If `$ARGUMENTS` contains a PR number or URL, extract it.
Otherwise, attempt to detect from the current branch context:

```bash
# Get current branch name
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

# Try to find PR associated with current branch
gh pr list --head "$BRANCH" --json number --limit 1 --jq '.[0].number' 2>/dev/null
```

If no PR can be determined, prompt the user: "Please provide a PR number or URL (e.g., `123` or `https://github.com/owner/repo/pull/123`)".

### 2. Fetch PR Details

Run the following command to get PR metadata and file list:

```bash
gh pr view <PR_NUMBER> --json body,title,files,commits --jq '.'
```

Parse the JSON output to extract:
- **title**: PR title
- **body**: PR description
- **files**: List of changed files with path and changeType
- **commits**: Commit count and messages

### 3. Categorize Files by Component

For each file in the PR, categorize by component based on file path:

| Component | Path Pattern | Example |
|-----------|--------------|---------|
| **Backend API** | `backend/src/**`, `backend/requirements.txt`, `backend/Dockerfile` | `backend/src/api/routes/scan.py` |
| **Frontend** | `frontend/src/**`, `frontend/package.json`, `frontend/vite.config.ts` | `frontend/src/components/Dashboard.tsx` |
| **Hardware Agent** | `hardware-agent/src/**`, `hardware-agent/requirements.txt` | `hardware-agent/src/scanning/nmap_runner.py` |
| **Contracts & Schemas** | `contracts/**` | `contracts/api-spec.openapi.json`, `contracts/schemas/scan_result.schema.json` |
| **Infrastructure & CI** | `infra/`, `.github/workflows/`, `docker-compose.yml` | `infra/docker-compose.yml`, `.github/workflows/ci.yml` |
| **Documentation & ADR** | `docs/adr/**`, `docs/architecture/**`, `*.md` (root or docs/) | `docs/adr/ADR-003.md`, `README.md` |

Store categorized files as a map:
```
{
  "backend": [list of files],
  "frontend": [list of files],
  "hardware-agent": [list of files],
  "contracts": [list of files],
  "infra": [list of files],
  "docs": [list of files]
}
```

### 4. Identify Breaking Changes

Scan for breaking changes by pattern:

- **Schema changes** (`contracts/schemas/` or `contracts/api-spec.openapi.json`): Flag any additions or removals
- **Database migrations** (`backend/src/migrations/` or Alembic patterns): Flag as potentially breaking
- **API endpoint changes** (`backend/src/api/routes/`): Check if endpoint paths or parameters modified
- **Environment variables**: Changes to `.env`, `env.example`, or deployment configs
- **Configuration changes**: `docker-compose.yml`, `.github/workflows/`

For each breaking change, extract the specific line diff and mark as **BREAKING**.

### 5. Flag Documentation Gaps

Check if code changes have corresponding documentation updates:

- **Backend API changes** → Check if `contracts/api-spec.openapi.json` updated
- **Architecture changes** → Check if `docs/adr/ADR-*.md` referenced or updated
- **Hardware agent changes** → Check if `hardware-agent/README.md` updated
- **Deployment changes** → Check if `infra/README.md` or ADR-007 referenced
- **Database changes** → Check if ADR-009 or data model docs updated

For each code change **without** corresponding doc update, flag as **DOCS NEEDED**.

### 6. Identify Security-Relevant Changes

Flag security-relevant modifications:

- Changes to `backend/src/` files containing "auth", "security", "password", "token", "credential"
- Changes to cryptographic or validation logic
- Changes to scanning scripts in `hardware-agent/src/scanning/`
- Changes to vulnerability detection or filtering logic
- Changes to `infra/` deployment or TLS configuration

Mark these as **SECURITY RELEVANCE**.

### 7. Generate Summary Report

Produce a markdown summary with the following structure:

```markdown
# PR #<NUMBER>: <TITLE>

## Summary
<First 2-3 sentences from PR body, or description of changes>

## Files Changed
- **Total files**: X
- **Additions**: +Y lines
- **Deletions**: -Z lines

## Changes by Component

### Backend API (N files changed)
- `backend/src/api/routes/scan.py` (+45, -12) — Update scan endpoint parameters
- `backend/src/models/device.py` (+10, -5) — Add device properties
[... more files ...]

### Frontend (N files)
[...]

### Hardware Agent (N files)
[...]

### Contracts & Schemas (N files)
[...]

### Infrastructure & CI (N files)
[...]

### Documentation (N files)
[...]

## Breaking Changes ⚠️

If breaking changes detected:

- **Schema change**: `contracts/api-spec.openapi.json` — New required field `scan_type` in POST /scans
- **Database migration**: `backend/src/migrations/` — Removed `legacy_port_id` column from ports table
- **API change**: Endpoint `/api/v1/scan/{id}` parameters modified

## Documentation Gaps 📋

Files with code changes but missing doc updates:

- ✗ `backend/src/api/routes/` changed → `contracts/api-spec.openapi.json` **NOT updated**
- ✗ `hardware-agent/src/scanning/` changed → `hardware-agent/README.md` **NOT updated**
- ✓ `docs/adr/ADR-003.md` updated ✓ matches backend changes

## Security Review 🔒

High-attention items:

- `backend/src/auth/` — Authentication logic changed (5 files)
- `hardware-agent/src/scanning/` — Vulnerability detection logic changed

## Risk Assessment

| Category | Level | Notes |
|----------|-------|-------|
| **Backward Compatibility** | [HIGH/MEDIUM/LOW] | [Breaking changes present / Minor changes / No impact] |
| **Documentation Sync** | [HIGH/MEDIUM/LOW] | [X docs need update / All docs in sync] |
| **Security Impact** | [HIGH/MEDIUM/LOW] | [Auth/crypto changes / Data validation / No security impact] |
| **Scope Alignment** | [OK/WARNING] | [Fits v1 lab scope / Approaching v2 scope expansion] |

## Reviewer Checklist

- [ ] All breaking changes have accompanying migration docs
- [ ] API changes reflected in `contracts/api-spec.openapi.json`
- [ ] ADR references updated if architectural decision affected
- [ ] Security-relevant code changes reviewed carefully
- [ ] Documentation reflects new code behavior
- [ ] No scope creep beyond v1 lab deployment assumptions
```

### 8. Present and Validate

Output the markdown report to the user. If multiple components are affected:

1. Highlight components with the most changes (sorted by file count)
2. Emphasize any **BREAKING** or **SECURITY** flags
3. Suggest which files to review first based on risk

If breaking changes exist, recommend updating PR description with migration guidance.

## Integration with Project

- **Component boundaries**: Reference `docs/architecture/ARCHITECTURE.md` sections 2.1–2.6 for component responsibilities
- **Schema validation**: Cross-reference changes against `contracts/api-spec.openapi.json` and schema files
- **ADR compliance**: If PR touches multiple components, check related ADRs (ADR-003 for backend, ADR-008 for frontend, etc.)
- **Project scope**: Flag if changes suggest scope expansion beyond v1 lab assumptions (see `.cursor/rules/project-scope.mdc`)

## Example Usage

```text
User: "Can you summarize PR #42?"

Skill: [Fetches PR 42, analyzes 8 file changes across backend, frontend, and contracts]

Output: [Detailed markdown report showing component breakdown, breaking schema change, documentation gap, and risk assessment]

User: "Should I be worried about anything?"

Skill: "Yes — PR 42 has a breaking schema change to scan_result.schema.json (new required field) 
and updates backend authentication logic. Make sure contracts and auth changes are both reviewed carefully.
Also, hardware-agent README is out of sync with the scanning logic updates."
```

## Limitations

- Requires authenticated `gh` CLI
- May not detect all security-relevant patterns (code review still needed)
- Component categorization is pattern-based (edge cases in mixed files)
- Cannot determine intent of changes (only reports what changed)

## Troubleshooting

- **"PR not found"**: Verify PR number is correct and `gh` has access to repository
- **No files detected**: PR may have been closed or deleted; try with explicit PR number
- **Character encoding issues**: Ensure terminal supports UTF-8
