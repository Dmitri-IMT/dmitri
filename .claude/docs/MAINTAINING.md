---
type: Maintenance Playbook
title: Maintaining the Dmitri code-map
description: How agents write and keep the .claude/docs OKF code-map current as the code changes.
tags: [okf, maintenance, meta]
timestamp: 2026-07-21T00:00:00Z
---

# Maintaining this code-map

This directory (`.claude/docs/`) is an **Open Knowledge Format (OKF v0.1)** bundle: a tree of
markdown *concept documents*, each with YAML frontmatter, cross-linked with bundle-relative
links, navigated via reserved `index.md` files and change-tracked via reserved `log.md`.

It is a **code map** — it explains what the Dmitri source code *does* and how the modules fit
together. It is **not** the design knowledge base. Product decisions, target-state architecture,
and roadmaps live in the repo's `docs/` tree (ADRs, `docs/architecture/`, `docs/roadmap/`). Link
to those as citations; never copy them here.

You (an LLM agent) own this layer entirely. Humans read it; you write and maintain it. The
[`docs-sync`](/../skills/docs-sync/SKILL.md) skill is the automated maintainer that runs this
playbook after code changes land.

## Bundle rules (OKF v0.1)

- **Bundle root** is `.claude/docs/`. A concept's **ID** is its path from the root minus `.md`
  (e.g. `hardware-agent/scanner/runner.md` → ID `hardware-agent/scanner/runner`).
- **Reserved filenames** (never a concept): `index.md` (directory listing), `log.md` (change
  history). This `MAINTAINING.md` is itself a concept doc.
- Every non-reserved `.md` **must** have parseable YAML frontmatter with a non-empty `type`.
- **Consumers tolerate broken links** — but ours should resolve; fix them when you move a file.

## Frontmatter schema

```yaml
---
type: <required>          # see vocabulary below
title: <human name>
description: <one sentence — reused verbatim in index.md listings>
resource: <primary source path this doc maps>   # e.g. hardware-agent/src/agent/scanner/runner.py
tags: [<cross-cutting labels>]
timestamp: <ISO 8601 — bump on every edit>
---
```

`type` vocabulary (descriptive, not registered): `Package Overview`, `Module`, `Entry Point`,
`Data Contract`, `Domain Glossary`, `Migration`, `Infrastructure`, `Maintenance Playbook`.

## Concept-doc body shape

Every module/file concept doc uses these sections, in order:

1. **Purpose** — one paragraph: what this code is responsible for.
2. **Key classes / functions** — a table: name → what it does, with `path:line` references.
3. **How it connects** — upstream callers and downstream callees, as bundle-relative links.
4. **Notes / gotchas** — seams and caveats (see "Standing facts" below) where relevant.
5. `# Citations` (optional) — links to the governing `docs/adr/ADR-*.md` and `specs/` files.

Keep it accurate over exhaustive. Reference real symbols and line numbers; do not invent APIs.

## Linking

- Between concept docs: **bundle-relative** absolute paths — `[stages](/hardware-agent/scanner/stages.md)`
  (stable when files move) — or `./neighbour.md` for same-directory links.
- To the repo KB / source: normal repo-relative paths — `[ADR-011](../../docs/adr/ADR-011-pi-command-channel.md)`.
- `index.md` entries: `* [Title](./concept.md) — <frontmatter description>`, grouped by section.

## Standing facts to preserve (do NOT "fix" these)

- **Current vs target state.** Only the Pi agent + TUI is in active development. The backend is
  working code but nothing calls it yet (`api/main.py` exposes only `GET /api/v1/health`); the
  agent→backend link, Pi hardware, and frontend do not exist. Flag backend/contract docs as
  **planned / not yet wired**.
- **`device` ↔ `host` rename.** The Pi ingest payload says `devices[]` (frozen by ADR-011);
  everywhere else the term is `host`. `X-Device-Id` identifies the *agent*, not a host.
- **`ScanRunner` orchestration.** There is no `ScanOrchestrator` class; `ScanRunner._run()` is the
  pipeline. CLAUDE.md's "bypass" warning is about the dual front-door design (TUI + headless), not
  a live second code path.
- **Not-wired / legacy code.** `discovery/service_detection.py` is exported but unused; the legacy
  `full` scan mode is being removed in favor of `max`. Describe as such; don't delete.
- **Contract divergence.** OpenAPI `ScanIngestRequest` (`scan_mode`) is out of step with the
  implemented `schemas/scan.py` + example JSON (`target_mode`/`scan_profile`). Note, don't reconcile.

## Ingest workflow (when code changes)

1. Determine the changed source files (a diff — never a blind full-repo scan).
2. For each, open the concept doc whose `resource:` maps it (or its module). Revise Purpose /
   Key classes-functions / How it connects / Notes to match; bump `timestamp`.
3. Add a concept doc for a new module; remove one for a deleted module; fix cross-links either way.
4. Refresh any affected `index.md` listing (descriptions come from frontmatter).
5. Append a dated entry to `log.md` (newest first): `## YYYY-MM-DD` then
   `* **Update**: <what changed>` / `* **Creation**:` / `* **Deletion**:`.

## Lint (periodic health check)

Check for: concept docs whose `resource:` file no longer exists; broken bundle links; source
symbols/line refs that have drifted; modules with no concept doc; `index.md` entries missing their
description. Report and repair.
