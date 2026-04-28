---
name: openapi-contract-sync
description: >-
  Verify that FastAPI route definitions match the generated OpenAPI schema and
  that documented API contracts in ARCHITECTURE.md stay in sync. Use when the
  user mentions OpenAPI drift, API contract check, route coverage, or schema
  sync. No-ops gracefully if the backend has no real routes yet.
---

# OpenAPI Contract Sync

## Purpose

Ensure three sources of truth about the API stay consistent:

1. **FastAPI route code** — the actual `@app.get/post/…` decorators and
   Pydantic models in `backend/src/api/`.
2. **Generated OpenAPI schema** — produced by `app.openapi()` at runtime.
3. **Architecture docs** — route list and interface descriptions in
   `docs/architecture/ARCHITECTURE.md` §6 (Component Interfaces).

## User Input

```text
$ARGUMENTS
```

Consider user input before proceeding. If the user names a specific route or
schema (e.g. "check POST /scans"), narrow the check to that route only.

## Pre-flight: Readiness Gate

Before running the full workflow, verify the backend is ready:

1. Check that `backend/src/api/main.py` exists and contains a `FastAPI()` app
   instance.
2. Check that at least **3 non-health routes** are registered (routes beyond
   `GET /` and `GET /docs` and `GET /redoc` and `GET /openapi.json`).

**If the gate fails** (fewer than 3 real routes), output the following and stop:

```
## OpenAPI Contract Sync — Not Applicable Yet

The backend currently has fewer than 3 non-infrastructure routes.
This skill becomes useful once the API surface grows beyond stubs.

Current routes detected:
- <list whatever exists>

No action taken. Re-run after more endpoints are implemented.
```

Do **not** treat this as an error — it is expected in early development.

## Execution Steps (when gate passes)

### 1. Extract routes from code

Scan `backend/src/api/main.py` and all files under `backend/src/api/routers/`
for route registrations (`@app.get`, `@app.post`, `@router.get`, etc.).

For each route, record:
- HTTP method + path
- Summary / operation ID
- Request body model (if any)
- Response model (if any)
- Auth dependencies (if any)

### 2. Generate the OpenAPI schema

Run:

```bash
cd backend && python -c "from api.main import app; import json; print(json.dumps(app.openapi(), indent=2))"
```

If `uv` is the project runner:

```bash
cd backend && uv run python -c "from api.main import app; import json; print(json.dumps(app.openapi(), indent=2))"
```

If the import fails, report the error and stop — the app factory is broken.

Parse the JSON output to extract `paths`, `components/schemas`, and `info`.

### 3. Compare code routes vs OpenAPI output

For each route found in step 1, verify it appears in the OpenAPI paths with
matching method, path parameters, request body schema, and response schema.

Flag:
- **UNDOCUMENTED** — route in code but missing from OpenAPI (rare with FastAPI,
  but possible if `include_in_schema=False` or decorator issues)
- **PHANTOM** — route in OpenAPI but not found in code (should not happen;
  indicates stale import or leftover)
- **SCHEMA MISMATCH** — route exists in both but request/response models differ

### 4. Compare OpenAPI output vs ARCHITECTURE.md

Read `docs/architecture/ARCHITECTURE.md` §6 (Component Interfaces).
Extract the documented routes and their descriptions.

Flag:
- **DOC DRIFT** — route exists in OpenAPI but ARCHITECTURE.md lists different
  method, path, or description
- **DOC MISSING** — route in OpenAPI not mentioned in ARCHITECTURE.md
- **DOC STALE** — route in ARCHITECTURE.md no longer in OpenAPI

### 5. Present drift report

```
## API Contract Drift Report

| # | Route | Source | Issue | Severity |
|---|-------|--------|-------|----------|
| 1 | POST /scans | ARCHITECTURE.md §6.1 | Response code says 202, code returns 200 | MEDIUM |
| 2 | GET /devices | OpenAPI | Not documented in ARCHITECTURE.md | LOW |
```

Severity:
- **HIGH** — auth or security-related route mismatch
- **MEDIUM** — response model, status code, or path parameter mismatch
- **LOW** — missing doc entry for a non-critical route, or wording difference

### 6. Ask the user for resolution

For each drift item, use AskQuestion (or a numbered list) with options:

- **"Code is correct"** — update ARCHITECTURE.md to match
- **"Doc is correct"** — recommend code changes (do not apply them)
- **"Both wrong"** — ask for the intended contract, then update docs
- **"Skip"** — acknowledge and move on

### 7. Apply patches

- Edit only `docs/architecture/ARCHITECTURE.md` (and ADRs if relevant).
- Keep edits minimal — update the specific route entry or table row.
- Never modify Python source files — code changes go into a Recommendations
  section.

### 8. Summary

```
## Contract Sync Summary

- Routes checked: <count>
- Drift items found: <count>
- Documents updated: <list or "none">
- Recommendations (code changes): <list or "none">
- Skipped: <count>
```

## Constraints

- Never modify application code — doc patches only; code fixes go into recommendations.
- Never bypass the readiness gate — if the backend is too early, no-op cleanly.
- Never dump the full OpenAPI JSON into the report — summarize only the diffs.
- If no drift is found, say so and exit early.
