---
name: architecture-adr-sync
description: >-
  Detect drift between docs/architecture/ARCHITECTURE.md, docs/adr/ADR-*.md,
  and the actual codebase. Present conflicts to the user, ask which source is
  authoritative, and patch the documents accordingly. Use when architecture docs
  may be stale, after significant code changes, or when the user mentions ADR
  sync, architecture drift, or doc consistency.
---

# Architecture / ADR Sync

## Purpose

Keep `docs/architecture/ARCHITECTURE.md`, the individual `docs/adr/ADR-*.md`
decision records, and (optionally) `docs/DEV-SETUP.md` consistent with the
actual codebase. This is a **targeted** check — not a blind full-repo scan.

## Scope

| Document | Role |
|---|---|
| `docs/architecture/ARCHITECTURE.md` | Consolidated architecture view (components, stack, versions, interfaces, deployment) |
| `docs/adr/ADR-*.md` | Individual decision records; each owns one decision |
| `docs/DEV-SETUP.md` | Developer environment assumptions (optional — include only when environment facts drift) |

This skill does **not** touch `.specify/` artifacts (spec.md, plan.md, tasks.md).
Use `speckit-analyze` for those.

## User Input

```text
$ARGUMENTS
```

Consider user input before proceeding. If the user names a specific topic
(e.g. "check database versions"), narrow the scan to that topic only.

## Execution Steps

### 1. Identify check topics

Each topic is a factual claim that can be verified against code or config files.
Select topics relevant to recent changes (or all if the user asks for a full sync).

| Topic | Doc sections to read | Code/config hotspots to inspect |
|---|---|---|
| **Pinned versions** | ARCHITECTURE.md §5 (Tech Stack table) | `backend/pyproject.toml`, `frontend/package.json`, `hardware-agent/pyproject.toml`, `infra/docker-compose*.yml` |
| **Component boundaries** | ARCHITECTURE.md §2, §3 (Components, Diagram) | Top-level directories: `backend/`, `frontend/`, `hardware-agent/`, `infra/` |
| **API routes & interfaces** | ARCHITECTURE.md §6 (Component Interfaces) | `backend/src/api/main.py`, `backend/src/api/routers/` |
| **Database & ORM** | ARCHITECTURE.md §2.6, ADR-009 | `backend/src/api/models/`, `backend/src/api/db/`, Alembic `migrations/` |
| **Security model** | ARCHITECTURE.md §6.1-6.2, ADR-005 | Auth middleware, CORS config, env vars |
| **Deployment** | ARCHITECTURE.md §4, ADR-007 | `infra/docker-compose*.yml`, Dockerfiles, nginx config |
| **Frontend stack** | ARCHITECTURE.md §2.3 §5, ADR-008 | `frontend/package.json`, `frontend/vite.config.*`, `frontend/tsconfig.json` |
| **Scanning tools** | ARCHITECTURE.md §2.1, ADR-002, ADR-006 | `hardware-agent/` scripts/configs |
| **Dev environment** | `docs/DEV-SETUP.md` | Root `.env.example`, Docker prerequisites |

### 2. Load documents

Read the architecture doc and relevant ADRs. Do **not** dump their full content
into output — extract only the factual claims (versions, ports, component names,
tool names, config values) you will compare.

### 3. Inspect code hotspots

For each selected topic, read only the specific files listed above. Extract the
corresponding facts from code (dependency versions from lock/config files,
route definitions, model class names, Dockerfile base images, etc.).

If a hotspot file does not exist yet, record it as **"not implemented"** —
this is not necessarily a conflict (the project may be pre-implementation).

### 4. Compare and classify

For each fact, classify as:

| Status | Meaning |
|---|---|
| **MATCH** | Doc and code agree |
| **DRIFT** | Doc states X, code shows Y — one side is outdated |
| **DOC-ONLY** | Doc describes something not yet in code (may be intentional if pre-implementation) |
| **CODE-ONLY** | Code has something not reflected in any doc |
| **MISSING-ADR** | A significant decision exists in code with no corresponding ADR |

### 5. Present conflict report

Output a Markdown table:

```
## Architecture–Code Drift Report

| # | Topic | Document | Claim | Code reality | Status | Severity |
|---|-------|----------|-------|-------------|--------|----------|
| 1 | DB version | ARCHITECTURE.md §2.6 | PostgreSQL 15.x | Supabase dashboard shows 16.1 | DRIFT | MEDIUM |
| 2 | FastAPI version | ARCHITECTURE.md §5 | 0.135.2 | pyproject.toml: 0.136.0 | DRIFT | LOW |
```

Severity guide:
- **HIGH** — component boundary, security model, or API contract mismatch
- **MEDIUM** — version pin or deployment topology mismatch
- **LOW** — cosmetic or non-functional drift (wording, minor version patch)

Omit MATCH rows to keep the report concise.

### 6. Ask the user for resolution

For each DRIFT or MISSING-ADR item, ask the user which source is authoritative.
Use the AskQuestion tool when available; otherwise present a numbered list and
ask the user to reply.

Resolution options per conflict:

- **"Code is correct"** → update the document(s) to match code
- **"Doc is correct"** → flag a code change needed (do NOT change code in this skill; add a recommendation)
- **"Both wrong"** → ask the user for the correct value, then update docs
- **"Needs new ADR"** → draft an ADR stub for the user to complete
- **"Skip"** → leave as-is, note it was acknowledged

For DOC-ONLY items in a pre-implementation project, default to **Skip** unless
the user says otherwise.

### 7. Apply document patches

After receiving answers:

1. Edit only the documents the user authorized.
2. Keep edits minimal — change the specific value, sentence, or table row.
   Do not rewrite surrounding paragraphs or reformat unrelated sections.
3. If a new ADR is needed, create it following the existing naming convention
   (`docs/adr/ADR-NNN-<slug>.md`) with status "Proposed" and a TODO body
   for the user to fill in.
4. Do **not** change application code. If the user chose "Doc is correct",
   add a `### Recommendations` section at the end of the report listing the
   code changes needed.

### 8. Summary

After applying patches, output:

```
## Sync Summary

- Documents updated: <list>
- Recommendations (code changes): <list or "none">
- Skipped: <count>
- New ADRs drafted: <list or "none">
```

## Constraints

- Never perform a blind full-repo scan — always scope by topic.
- Never reformat or restructure documents beyond the specific conflict fix.
- Never change application code (source files under `backend/`, `frontend/`,
  `hardware-agent/`, etc.) — doc patches only; code changes go into recommendations.
- If no drift is found, say so and exit early. Do not pad the report.
- Respect the user's resolution choices exactly — do not override or "improve" them.
