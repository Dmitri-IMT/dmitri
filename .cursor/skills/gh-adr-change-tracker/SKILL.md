---
name: gh-adr-change-tracker
description: >-
  Validate that code changes align with documented architecture decisions (ADRs).
  Map PR file changes to affected ADRs, compare diffs against requirements, and flag violations.
  Use when PR touches architectural components, user asks "does this match our architecture?",
  or when ADR content needs sync after code changes. Integrates with existing architecture-adr-sync skill.
compatibility: Requires GitHub CLI (gh) and git; designed for GitHub.com repositories with ADRs in docs/adr/
metadata:
  author: github-cli-skills
  source: skills/github-cli/gh-adr-change-tracker.md
---

# ADR Change Tracker

Validate that pull request changes align with documented Architecture Decision Records (ADRs).
Map file changes to affected ADRs, compare diffs against architectural requirements, and flag violations.

## When to Use

- PR touches files referenced in ADRs (e.g., backend API changes when ADR-003 defines stack)
- User asks "does this match our architecture?" or "is this compliant with our ADRs?"
- Need to validate architectural decisions before merging
- ADR content needs sync after code changes
- Setting up code review with architectural validation

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Prerequisites

- GitHub CLI (`gh`) must be installed and authenticated
- PR number must be provided or detectable from current branch
- Current directory must be a git repository with ADRs in `docs/adr/` directory
- ADRs should follow naming convention: `ADR-<NUMBER>.md` (e.g., `ADR-003.md`)

## File-to-ADR Mapping Reference

This is the core mapping used to determine which ADRs are affected by file changes:

| ADR | Title | Key File Patterns |
|-----|-------|-------------------|
| **ADR-001** | Hardware Selection | `hardware-agent/`, `*.md` (hardware context) |
| **ADR-002** | Scanning Tools Selection | `hardware-agent/src/scanning/`, `contracts/schemas/scan*` |
| **ADR-003** | Backend Stack | `backend/src/`, `backend/requirements.txt`, `contracts/api-spec.openapi.json` |
| **ADR-004** | Scan Methodology | `hardware-agent/src/scanning/`, `hardware-agent/src/nse_scripts/` |
| **ADR-005** | Security Model | `backend/src/auth/`, `backend/src/security/`, `infra/` (TLS), crypto code |
| **ADR-006** | Additional Tools | `backend/src/`, `backend/requirements.txt`, dependency additions |
| **ADR-007** | Deployment Architecture | `infra/`, `docker-compose.yml`, `.github/workflows/`, deployment docs |
| **ADR-008** | Frontend Stack | `frontend/src/`, `frontend/package.json`, `frontend/vite.config.ts` |
| **ADR-009** | Database Stack | `backend/src/migrations/`, `backend/src/models/`, database schema changes |

## Outline

### 1. Determine PR Number

If `$ARGUMENTS` contains a PR number or URL, extract it.
Supported formats:
- `123` (PR number)
- `https://github.com/owner/repo/pull/123` (full URL)
- `#123` (with hash)

If no PR found, prompt: "Please provide a PR number or URL (e.g., `123` or `https://github.com/owner/repo/pull/123`)".

### 2. Fetch PR Details

Run the following command:

```bash
gh pr view <PR_NUMBER> --json body,files,commits,title --jq '.'
```

Parse JSON to extract:
- **title**: PR title
- **body**: PR description (where users might reference ADRs)
- **files**: Array of changed files with paths
- **commits**: Commit messages (may contain ADR references)

### 3. Search for Explicit ADR References

Search PR description and commit messages for ADR references using regex: `ADR-(\d+)` or `adr-(\d+)` (case-insensitive).

Store all mentioned ADR numbers in a set (e.g., `{3, 5, 8}` from "implements ADR-003 and ADR-005; also frontend per ADR-008").

### 4. Map File Changes to ADRs

For each file in the PR's file list, determine affected ADRs using the mapping:

```
For file "backend/src/api/routes/scan.py":
  - Matches "backend/src/" → affects ADR-003 (Backend Stack)
  - Matches "backend/src/" → affects ADR-006 (Additional Tools, if new dependencies)
  - May affect ADR-005 if auth-related

For file "contracts/api-spec.openapi.json":
  - Matches "contracts/api-spec.openapi.json" → affects ADR-003 (Backend Stack)

For file "hardware-agent/src/scanning/nmap_runner.py":
  - Matches "hardware-agent/src/scanning/" → affects ADR-002, ADR-004

For file ".github/workflows/ci.yml":
  - Matches ".github/workflows/" → affects ADR-007 (Deployment Architecture)
```

Store mapping as: `{adr_number: [list of files triggering it]}`.

### 5. Read Affected ADRs

For each ADR determined to be affected (from explicit mentions + file mapping):

1. Look for file `docs/adr/ADR-<NUMBER>.md`
2. If found, read the entire file
3. Extract key sections:
   - Title (usually in first heading)
   - Problem statement
   - Decision
   - Consequences/Details
   - Any constraints or requirements

Store ADR content for later validation.

### 6. Generate Compliance Checks

For each affected ADR, create validation checks based on the ADR content:

**ADR-003 (Backend Stack)**:
- Check: `backend/src/api/routes/` changes → `contracts/api-spec.openapi.json` must be updated
- Check: No forbidden dependencies added (should use FastAPI, Pydantic, SQLModel per decision)
- Check: Database changes use SQLModel ORM pattern

**ADR-004 (Scan Methodology)**:
- Check: NSE script changes → documented with script purpose and category
- Check: Vulnerability detection logic changes → validated with test scans

**ADR-005 (Security Model)**:
- Check: Auth changes → reviewed and documented in ARCHITECTURE.md
- Check: Credential handling → no hardcoded secrets in code
- Check: TLS/encryption changes documented in infra/

**ADR-007 (Deployment Architecture)**:
- Check: Docker/compose changes → validated with deployment docs
- Check: Workflow changes → CI pipeline still validates schemas and lints

**ADR-008 (Frontend Stack)**:
- Check: Component changes → use React + TypeScript pattern
- Check: No new CSS framework (should use project's existing styling)

**ADR-009 (Database Stack)**:
- Check: Migration files → follow Alembic naming convention
- Check: Schema changes → documented in ADR or migration comment

### 7. Run Compliance Checks

For each check, determine if it **PASSES**, **WARNS**, or **FAILS**:

**PASS**: Requirement met, no issues.
**WARN**: Potential issue or best practice deviation, but not blocking. Example: "API change without OpenAPI update detected, but PR body mentions it will be updated in follow-up."
**FAIL**: Clear violation. Example: "Backend route added but OpenAPI spec not updated."

Logic for each check:

```
check: "API change without OpenAPI update"
  - Does PR contain "backend/src/api/routes/" changes? YES
  - Does PR contain "contracts/api-spec.openapi.json" changes? NO
  - Does PR description mention "OpenAPI will be updated"? NO
  → Result: FAIL
```

### 8. Generate Validation Report

Produce a markdown report with the following structure:

```markdown
# ADR Compliance Check — PR #<NUMBER>

## PR Summary
- **Title**: <PR title>
- **Changed Files**: N total
- **Affected ADRs**: [list of ADR numbers] (ADR-003, ADR-005, ADR-008)

## Explicit ADR References in PR
- PR description mentions: ADR-003 ✓
- Commit messages mention: ADR-005 ✓
- **Status**: PR author aware of architectural decisions

[If no references]: No explicit ADR references found in PR description or commits. [WARN]

## File-to-ADR Mapping

| File | Impact | ADR(s) | Risk |
|------|--------|--------|------|
| `backend/src/api/routes/scan.py` | API endpoint changed | ADR-003 | MEDIUM |
| `contracts/api-spec.openapi.json` | OpenAPI spec updated | ADR-003 | LOW |
| `hardware-agent/src/scanning/` | Scanning logic modified | ADR-002, ADR-004 | HIGH |
| `.github/workflows/ci.yml` | CI pipeline modified | ADR-007 | MEDIUM |

## Compliance Checks

### ADR-003: Backend Stack (FastAPI + PostgreSQL + SQLModel)

**Status**: ⚠️ WARN

- ✓ PASS: Uses FastAPI for new endpoint
- ✓ PASS: Uses SQLModel for database interaction
- ✗ FAIL: API endpoint added but `contracts/api-spec.openapi.json` NOT updated
  - **Issue**: Route `/api/v1/scan/{id}/results` added, but spec unchanged
  - **Action**: Update OpenAPI spec or update PR to include spec changes
- ⚠️ WARN: New dependency `numpy` added without justification in PR body
  - **Suggestion**: Explain why numpy is needed in comment

### ADR-004: Scan Methodology (Nmap + NSE Scripts)

**Status**: ✓ PASS

- ✓ PASS: Scanning logic uses approved NSE scripts (default, vuln, discovery)
- ✓ PASS: Changes properly scoped to detection logic
- ⓘ INFO: New NSE script filter added (research cost tracking); aligns with methodology

### ADR-005: Security Model

**Status**: ✓ PASS

- ✓ PASS: Authentication changes follow role-based access pattern
- ✓ PASS: No hardcoded credentials detected in code
- ✓ PASS: TLS config changes match ADR-007 deployment architecture

### ADR-007: Deployment Architecture

**Status**: ⚠️ WARN

- ✓ PASS: Docker Compose changes validated
- ⚠️ WARN: GitHub Actions workflow modified but no updated workflow docs
  - **Action**: Update `.github/workflows/ci.yml` description or workflow README

### ADR-008: Frontend Stack (React + TypeScript + Vite)

**Status**: ✓ PASS

- ✓ PASS: React components use TypeScript
- ✓ PASS: Vite build config unchanged
- ✓ PASS: Component patterns follow project conventions

### ADR-009: Database Stack (PostgreSQL + SQLModel + Alembic)

**Status**: ✗ FAIL

- ✗ FAIL: New migration file `20260421_add_device_table.py` doesn't follow Alembic naming convention
  - **Expected**: `<rev_id>_add_device_table.py` (with revision hash)
  - **Actual**: `20260421_add_device_table.py` (with date)
  - **Action**: Regenerate migration with Alembic to get correct revision ID

## Summary & Recommendations

| Category | Status | Issue Count |
|----------|--------|-------------|
| **Backend Stack** | ⚠️ WARN | 2 issues (1 FAIL, 1 WARN) |
| **Scanning** | ✓ PASS | 0 issues |
| **Security** | ✓ PASS | 0 issues |
| **Deployment** | ⚠️ WARN | 1 issue (docs) |
| **Frontend** | ✓ PASS | 0 issues |
| **Database** | ✗ FAIL | 1 issue (naming) |

### 🔴 Required Actions (Blocking)

1. **Update `contracts/api-spec.openapi.json`** with new `/api/v1/scan/{id}/results` endpoint
2. **Fix migration file naming** — regenerate with Alembic to get correct revision hash

### 🟡 Recommended Actions (Non-blocking)

1. Explain numpy dependency in PR comment
2. Document GitHub Actions workflow changes in README

### ✓ Approved

- Scanning logic changes align with ADR-004
- Security changes align with ADR-005

## Next Steps

1. **Address blocking issues** (FAIL) above
2. **Consider recommended actions** (WARN) for better documentation
3. **Request re-review** after changes
4. If changes require new architectural decision, create ADR follow-up

## Quick Links

- [View PR on GitHub](<PR_URL>)
- [ADR-003: Backend Stack](docs/adr/ADR-003.md)
- [ADR-009: Database Stack](docs/adr/ADR-009.md)
- [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
```

### 9. Identify New ADR Candidates

If PR introduces significant architectural decisions not covered by existing ADRs, flag:

```markdown
### 🆕 Potential New ADR

This PR introduces **research cost tracking** to vulnerability scanning results.
This is a new architectural decision beyond the current scan methodology (ADR-004).

**Suggestion**: Consider creating **ADR-010: Research Cost Metadata** to document:
- Why research costs are tracked
- How they're stored and transmitted
- Impact on performance and data model

Create new ADR before merging large architectural changes.
```

### 10. Validate Against Project Scope

Check if PR changes suggest scope expansion beyond v1 lab assumptions:

```markdown
### Scope Alert

PR modifies deployment to support **multiple simultaneous scan sites**. This implies:
- Network authentication across multiple locations
- Centralized reporting infrastructure
- Possible infrastructure cost scaling

This goes beyond the current **v1 lab scope** (single NSPi lab, ≤10 operators, 1-2 scans/day).

**Decision needed**: Is this a v1 requirement or v2 roadmap item?
See `.cursor/rules/project-scope.mdc` for scope constraints.
```

## Integration with Project

- **ADR Location**: `docs/adr/ADR-*.md` files
- **Architecture Reference**: `docs/architecture/ARCHITECTURE.md` sections 2.1–2.6
- **Related Skills**: Integrates with `architecture-adr-sync` skill for post-merge sync
- **Project Scope**: References `.cursor/rules/project-scope.mdc` for v1/v2 boundary checks

## Example Usage

```text
User: "Can you check if this PR matches our architecture?"

Skill: [Fetches PR, detects changes to backend API, database, and frontend]

Output:
# ADR Compliance Check — PR #123

## Affected ADRs
- ADR-003 (Backend Stack)
- ADR-009 (Database Stack)
- ADR-008 (Frontend Stack)

## Compliance Summary

### ADR-003: ⚠️ WARN
- ✗ FAIL: API endpoint added but OpenAPI spec not updated
- ⚠️ WARN: New dependency added without explanation

### ADR-008: ✓ PASS
- All components follow React + TypeScript conventions

### ADR-009: ✗ FAIL
- Migration file doesn't follow Alembic naming convention

## Blocking Issues
1. Update OpenAPI spec with new endpoint
2. Regenerate migration with correct naming

[Continue with recommendations and next steps...]
```

## Limitations

- Requires ADRs to exist in `docs/adr/` directory
- Mapping is pattern-based (may miss complex cross-cutting concerns)
- Compliance checks are heuristic (cannot detect all architectural violations)
- Requires human judgment for nuanced architectural decisions
- May produce false positives if file naming conventions vary

## Troubleshooting

- **"PR not found"**: Verify PR number and `gh` access
- **"ADRs not found"**: Ensure ADRs exist as `ADR-<NUMBER>.md` in `docs/adr/`
- **File mapping too broad**: May over-flag related files; review each WARN/FAIL manually
- **Missing validation checks**: Add new checks for project-specific patterns
