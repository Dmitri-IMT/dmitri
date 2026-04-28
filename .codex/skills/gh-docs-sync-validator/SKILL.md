---
name: gh-docs-sync-validator
description: >-
  Ensure code changes stay consistent with ARCHITECTURE.md and design documentation.
  Validate API endpoints match OpenAPI specs, database changes align with docs, and deployment changes reflect infra docs.
  Use during PR review, asking "are docs in sync with this change?", or when ADR/ARCHITECTURE.md modified.
  Complements the architecture-adr-sync skill with code-focused validation.
compatibility: Requires GitHub CLI (gh), git, and jq; designed for GitHub.com repositories with OpenAPI specs
metadata:
  author: github-cli-skills
  source: skills/github-cli/gh-docs-sync-validator.md
---

# Documentation Sync Validator

Ensure code changes stay consistent with documentation including ARCHITECTURE.md, API specifications,
deployment documentation, and component READMEs.

## When to Use

- PR review context (validating code against documented design)
- User asks "are docs in sync with this change?" or "is this documented?"
- ADR or ARCHITECTURE.md modified
- Need validation that code implementation matches design documents
- Before merging architectural changes

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Prerequisites

- GitHub CLI (`gh`) must be installed and authenticated
- PR number must be provided or detectable from current branch
- Current directory must be a git repository
- JSON parser (`jq`) recommended for parsing OpenAPI specs
- Documentation files should exist: `docs/architecture/ARCHITECTURE.md`, `contracts/api-spec.openapi.json`, etc.

## Outline

### 1. Determine PR Number

Extract PR number from `$ARGUMENTS` (same process as other skills).

Supported formats:
- `123` (PR number)
- `https://github.com/owner/repo/pull/123` (full URL)
- `#123` (with hash)

### 2. Fetch PR Details

Run the following command:

```bash
gh pr view <PR_NUMBER> --json body,files,title,commits --jq '.'
```

Parse JSON to extract:
- **files**: Array of changed files with paths and deletion/addition counts
- **body**: PR description
- **title**: PR title
- **commits**: Commit messages

### 3. Categorize Code Changes by Type

For each file, determine the type of change:

| File Pattern | Change Type | Documentation to Check |
|--------------|-------------|------------------------|
| `backend/src/api/routes/**` | API endpoint change | `contracts/api-spec.openapi.json` |
| `backend/src/models/**` | Data model change | ADR-009, data model docs, schema files |
| `backend/src/migrations/**` | Database migration | ADR-009, migration docs |
| `infra/docker-compose.yml` | Infrastructure change | `infra/README.md`, ADR-007 |
| `.github/workflows/**` | CI/CD change | GitHub Actions docs, `.github/workflows/README.md` |
| `frontend/src/**` | Frontend component change | `frontend/README.md`, component patterns |
| `hardware-agent/src/**` | Hardware agent change | `hardware-agent/README.md`, ADR-002/004 |
| `docs/architecture/ARCHITECTURE.md` | Architecture doc change | Verify consistency with current code |
| `docs/adr/ADR-*.md` | ADR change | Verify ADR reflects actual implementation |
| `*/README.md` | Component README change | Verify matches component implementation |

### 4. Fetch Documentation Files

Read the following documentation files from the repository:

```bash
# Fetch OpenAPI spec
gh api repos/{owner}/{repo}/contents/contracts/api-spec.openapi.json --jq '.content' | base64 -d

# Fetch ARCHITECTURE.md
gh api repos/{owner}/{repo}/contents/docs/architecture/ARCHITECTURE.md --jq '.content' | base64 -d

# Fetch project scope rule (if exists)
gh api repos/{owner}/{repo}/contents/.cursor/rules/project-scope.mdc --jq '.content' | base64 -d (or read locally)
```

Store fetched documentation for comparison.

### 5. Validate API Changes

If PR contains changes to `backend/src/api/routes/`:

**Extraction logic**:
1. Parse PR diff to find new/modified route definitions
2. Look for patterns:
   - `@app.get("/api/v1/...")` → GET endpoint
   - `@app.post("/api/v1/...")` → POST endpoint
   - Route parameters: `{id}`, `{name}`, etc.
   - Request/response models (Pydantic classes)

**Validation checks**:

```
check: "API endpoints documented in OpenAPI"
  - For each route in diff:
    - Extract path: "/api/v1/scan/{id}"
    - Extract method: GET
    - Search OpenAPI spec for matching path + method
    - Result: PASS (found) / FAIL (not found) / WARN (outdated)

check: "Request/response models match OpenAPI schema"
  - For each Pydantic model in route:
    - Extract fields: id, name, status, created_at
    - Search OpenAPI spec for matching schema definition
    - Compare field names, types, required vs optional
    - Result: PASS (match) / WARN (minor differences) / FAIL (major mismatch)

check: "OpenAPI spec describes all current routes"
  - Get all routes in codebase: GET /api/v1/scan, POST /api/v1/scan, etc.
  - Get all paths in OpenAPI spec
  - Check coverage: all routes in spec?
  - Result: PASS (100% documented) / WARN (85-99%) / FAIL (<85%)
```

### 6. Validate Database Changes

If PR contains changes to `backend/src/models/` or `backend/src/migrations/`:

**Extraction logic**:
1. Parse migration files to find schema changes
2. Look for SQLModel patterns: `sa.Column()`, field definitions
3. Check Alembic migration comments

**Validation checks**:

```
check: "Database schema changes documented"
  - For each migration in diff:
    - Extract tables: devices, ports, services
    - Extract columns: id, name, port_number
    - Search ADR-009 for schema documentation
    - Search migration comments for rationale
    - Result: PASS (documented) / WARN (sparse docs) / FAIL (no docs)

check: "Migration follows Alembic conventions"
  - Check migration filename: <rev_id>_<description>.py
  - Check migration has proper up/down functions
  - Check migration references unique constraint (if needed)
  - Result: PASS (follows conventions) / WARN (minor deviation) / FAIL (broken pattern)

check: "No breaking changes to critical tables"
  - Check for column deletions in devices, ports, findings
  - Check for required field additions (may break existing code)
  - Result: PASS (safe) / WARN (may need code updates) / FAIL (breaking)
```

### 7. Validate Deployment Changes

If PR contains changes to `infra/` or `.github/workflows/`:

**Extraction logic**:
1. Parse `docker-compose.yml` for services, environment variables, volumes
2. Parse GitHub Actions workflows for jobs, steps, dependencies

**Validation checks**:

```
check: "Infrastructure changes documented in infra/README.md"
  - For each service change (database, API, worker):
    - Search README for service description
    - Result: PASS (documented) / WARN (outdated) / FAIL (no docs)

check: "Deployment matches ADR-007"
  - Check Docker Compose uses PostgreSQL (per ADR)
  - Check API uses FastAPI (per ADR)
  - Check for correct network setup, port mappings
  - Result: PASS (compliant) / WARN (questionable) / FAIL (violates ADR)

check: "GitHub Actions workflow steps are documented"
  - For each workflow job (validate, lint, frontend-lint):
    - Check .github/workflows/README.md or comments explain purpose
    - Result: PASS (documented) / WARN (self-explanatory) / FAIL (unclear)
```

### 8. Validate Component READMEs

If PR adds or modifies files in component directories:

**Validation checks**:

```
check: "Component README exists and is updated"
  - If PR adds new files to `backend/src/api/routes/`:
    - Verify backend/README.md exists
    - Check if new functionality is mentioned
    - Result: PASS (docs updated) / WARN (README outdated) / FAIL (no README)

check: "README matches implementation"
  - Extract key features/components from README
  - Check if they match actual code
  - Result: PASS (in sync) / WARN (minor differences) / FAIL (seriously out of sync)
```

### 9. Validate ARCHITECTURE.md Consistency

If any architectural component changes or ADRs modified:

**Validation checks**:

```
check: "ARCHITECTURE.md section 2.1 matches hardware-agent code"
  - Read section 2.1 (Pi Agent description)
  - Compare against actual capabilities in hardware-agent/src/
  - Result: PASS (matches) / WARN (minor drift) / FAIL (major drift)

check: "ARCHITECTURE.md data flow diagram accurate"
  - Verify flow: Agent → Backend → Database → Frontend
  - Check if PR changes affect any component in flow
  - Result: PASS (still accurate) / WARN (may need diagram update) / FAIL (diagram outdated)

check: "Component diagram reflects current boundaries"
  - Verify mermaid diagram shows correct component separation
  - Check if PR introduces cross-component coupling
  - Result: PASS (boundaries intact) / WARN (coupling detected) / FAIL (violates separation)
```

### 10. Check Scope Alignment

Reference project scope rule to ensure PR doesn't imply scope expansion:

```
check: "PR changes fit within v1 lab scope"
  - Review `.cursor/rules/project-scope.mdc`
  - Detect scope expansions: "multiple sites", "enterprise scale", "campus-wide"
  - Result: PASS (fits v1 scope) / WARN (approaching v2 boundary) / FAIL (v2 feature for v1)
```

### 11. Generate Validation Report

Produce a markdown report with structure:

```markdown
# Documentation Sync Validation — PR #<NUMBER>

## PR Summary
- **Title**: <PR title>
- **Files Changed**: N total
- **Change Categories**: API, Database, Infrastructure, Docs

## Change Overview

| Category | Files | Status |
|----------|-------|--------|
| API Routes | 3 files | ⚠️ Check needed |
| Database Migrations | 1 file | ✓ OK |
| Infrastructure | 0 files | — N/A |
| Documentation | 2 files | ⚠️ Check needed |

## API Endpoint Validation

### New/Modified Routes

| Endpoint | Method | Model | OpenAPI | Status |
|----------|--------|-------|---------|--------|
| `/api/v1/scan/{id}/results` | GET | ScanResults | ❌ Missing | FAIL |
| `/api/v1/devices` | POST | Device | ✓ Found | PASS |
| `/api/v1/devices/{id}` | PUT | Device | ✓ Found, ⚠️ schema mismatch | WARN |

### Validation Results

✗ **FAIL: 1 endpoint not in OpenAPI**
- **`GET /api/v1/scan/{id}/results`** — New endpoint added but not documented in `contracts/api-spec.openapi.json`
  - **File**: `backend/src/api/routes/scan.py` (lines 42-55)
  - **Model**: Uses `ScanResults` Pydantic model
  - **Action**: Add endpoint + schema to OpenAPI spec

⚠️ **WARN: 1 schema mismatch detected**
- **`PUT /api/v1/devices/{id}`** — OpenAPI schema doesn't match Pydantic model
  - **Pydantic fields**: `id`, `name`, `ip_address`, `device_type`, `status`, `last_seen`
  - **OpenAPI schema**: Missing `last_seen` field, has extra `deprecated` field
  - **Action**: Align OpenAPI schema with actual Pydantic model or update model

✓ **PASS: 1 endpoint properly documented**
- `POST /api/v1/devices` — Matches OpenAPI spec and schema

### API Coverage
- Routes in codebase: 12 total
- Routes in OpenAPI spec: 11 documented
- **Coverage**: 91.7% — **WARN**
  - One endpoint is missing from OpenAPI

## Database Changes

### Migrations

| Migration | Tables | Status |
|-----------|--------|--------|
| `abc1234_add_scan_type_to_scans.py` | scans | ✓ Valid |
| `def5678_create_findings_table.py` | findings | ✓ Valid |

### Validation Results

✓ **PASS: All migrations follow conventions**
- Proper Alembic naming: `<rev_id>_<description>.py`
- Both have up/down functions
- Database changes documented in migration comments

⚠️ **WARN: Breaking change detected**
- **Migration `def5678`**: Adds **required** column `severity` to findings table
  - **Impact**: Existing code reading findings may break if not updated
  - **Suggestion**: Make column nullable initially, then backfill + make required in follow-up
  - **Check**: Is backend code updated to handle new field?

### Schema Documentation

✓ Database changes documented:
- ADR-009 references PostgreSQL + SQLModel pattern
- Migration comments explain purpose of schema changes
- New findings schema aligns with vulnerability tracking goals

## Infrastructure Changes

No infrastructure files modified in this PR.

## Component README Validation

### Files Added/Modified

| Component | File | Status |
|-----------|------|--------|
| Backend | `backend/src/api/routes/scan.py` | ⚠️ Backend README outdated |
| Backend | `backend/src/models/finding.py` | ⚠️ Backend README outdated |

### Validation Results

⚠️ **WARN: Component README needs update**
- **File**: `backend/README.md`
- **Issue**: New scanning results API not mentioned in "Endpoints" section
- **Action**: Add endpoint documentation to backend README

## ARCHITECTURE.md Consistency

### Component Changes

- **Backend API** → Modified (new endpoint)
- **Database** → Modified (new table and column)
- **Other components** → Unchanged

### Validation Results

✓ **PASS: Architecture boundaries intact**
- New endpoint follows existing pattern
- Database changes scoped to database layer
- No cross-component coupling introduced

⚠️ **WARN: Data flow diagram may need update**
- ARCHITECTURE.md Figure X shows scan flow
- New `findings.severity` field changes data model
- **Action**: Update diagram or data model section

## Scope Alignment

✓ **PASS: Changes fit v1 lab scope**
- Scanning improvements are within planned v1 work
- No scope expansion detected (no "multiple sites", "enterprise", etc.)
- Changes maintain lab-only deployment model

## Summary & Actions

| Priority | Issue | File | Action |
|----------|-------|------|--------|
| 🔴 BLOCKING | Missing OpenAPI documentation | `contracts/api-spec.openapi.json` | Add GET /api/v1/scan/{id}/results |
| 🔴 BLOCKING | API schema mismatch | `contracts/api-spec.openapi.json` | Align PUT /api/v1/devices/{id} schema |
| 🟡 RECOMMENDED | Backend README outdated | `backend/README.md` | Document new scanning endpoint |
| 🟡 RECOMMENDED | Breaking database change | `backend/src/migrations/` | Consider nullable approach for new fields |
| 🟡 RECOMMENDED | Architecture diagram outdated | `docs/architecture/ARCHITECTURE.md` | Update data model section |

## Consistency Score

```
Components with documentation: 3/3 (100%)
- ✓ API endpoints: 11/12 documented (91.7%)
- ✓ Database schemas: All documented
- ⚠️ Component README: 1 needs update

Overall Consistency: 85% — GOOD (but needs fixes before merge)
```

## Quick Checklist

- [ ] Add missing OpenAPI endpoint documentation
- [ ] Fix API schema mismatch for PUT /devices/{id}
- [ ] Update backend README with new endpoint
- [ ] Review breaking database change (severity field)
- [ ] Update ARCHITECTURE.md data model section if needed
- [ ] Verify code handles new required fields
- [ ] Re-run validation after changes

## Next Steps

1. **Blocking issues must be resolved** before merge
   - Add OpenAPI endpoint
   - Fix schema mismatch
2. **Recommended issues** should be addressed for documentation quality
3. **Request new validation run** after making changes
4. **Architecture review** may be needed if data model significantly changed

## Related Documentation

- [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) — System architecture and component boundaries
- [ADR-003: Backend Stack](docs/adr/ADR-003.md) — Backend technology decisions
- [ADR-009: Database Stack](docs/adr/ADR-009.md) — Database decisions
- [OpenAPI Spec](contracts/api-spec.openapi.json) — API contract
- [Backend README](backend/README.md) — Backend component overview
```

## Integration with Project

- **OpenAPI Spec**: `contracts/api-spec.openapi.json`
- **Architecture Doc**: `docs/architecture/ARCHITECTURE.md`
- **ADRs**: `docs/adr/ADR-*.md` (especially ADR-003, ADR-007, ADR-009)
- **Component READMEs**: `backend/README.md`, `frontend/README.md`, `hardware-agent/README.md`, `infra/README.md`
- **Scope Rule**: `.cursor/rules/project-scope.mdc`
- **Complements**: Existing `architecture-adr-sync` skill

## Example Usage

```text
User: "Are the docs in sync with this PR?"

Skill: [Fetches PR, analyzes API, database, and README changes]

Output:
# Documentation Sync Validation — PR #88

## Summary
- 3 API endpoints modified
- 1 database migration added
- READMEs need updates

## Issues Found

🔴 BLOCKING
- GET /api/v1/scan/{id}/results NOT in OpenAPI spec

🟡 RECOMMENDED  
- Backend README missing endpoint documentation
- Architecture diagram may need update

## Action Items
1. Add endpoint to OpenAPI
2. Update Backend README
3. Review data model changes

[Continue with detailed validation...]
```

## Limitations

- Requires documentation files to exist and be well-formatted
- OpenAPI spec validation assumes JSON format
- Cannot detect all semantic inconsistencies (requires human review)
- Pattern-based detection may miss edge cases
- Requires component README files to exist

## Troubleshooting

- **"OpenAPI spec not found"**: Verify `contracts/api-spec.openapi.json` exists and is valid JSON
- **"ARCHITECTURE.md not found"**: Ensure docs/architecture/ARCHITECTURE.md exists
- **"Failed to parse schema"**: Check OpenAPI spec is valid OpenAPI 3.x format
- **"Too many warnings"**: Review with team if documentation maintenance is keeping up
