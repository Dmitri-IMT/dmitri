---
type: Maintenance Playbook
title: Maintaining the Dmitri code-map
description: How agents write and keep the .claude/docs OKF code-map current as the code changes.
tags: [okf, maintenance, meta]
timestamp: 2026-08-05T00:00:00Z
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

- **Current vs target state.** Three layers are in active development: the Pi agent + TUI, the
  backend, and the React frontend. The backend serves the read path, auth, `users/me`, the invite
  routes and — since DMI-64 — the full command channel (`POST /agents/{id}/commands`,
  `GET /commands/{id}`, and the WS channel that delivers commands and applies the Pi's status
  frames). Ingest (`POST /api/v1/scans`) is also wired, since DMI-63. Still **not wired**: the
  device side — no Pi daemon posts scan results (DMI-66) and no Pi client dials the WS channel
  either, so both are exercised against signed test requests and fake sockets rather than a real
  Pi. The backend routes exist and are gated; what's missing is the Pi client that calls them.
  Flag that as **planned / not yet wired**; do not describe the backend as a whole that way.
- **`device` ↔ `host` rename, now complete on the wire.** ADR-013 lifted ADR-011's ingest-naming
  freeze, so the ingest payload says `hosts[]` too — on both the agent side
  (`normalize/contracts.py:56`) and the backend (`schemas/scan.py:66`). `host` is the term
  everywhere. Two deliberate survivors: `X-Device-Id`, which identifies the *agent* and not a host,
  and the legacy `PersistedDevice`/`devices`/`device_count` projections in
  `schemas/persistence.py`, which were never renamed. Don't "finish" either.
- **`ScanRunner` orchestration.** There is no `ScanOrchestrator` class; `ScanRunner._run()` is the
  pipeline. CLAUDE.md's "bypass" warning is about the dual front-door design (TUI + headless), not
  a live second code path.
- **Not-wired / legacy code.** `discovery/service_detection.py` is exported but unused; the legacy
  `full` scan mode is being removed in favor of `max`. Describe as such; don't delete.
- **Contract and Python agree — the old divergence is resolved.** OpenAPI `ScanIngestRequest`,
  `schemas/scan.py` and the example JSON all use `scan_mode`; `target_mode`/`scan_profile` are gone.
  DMI-63 went further and adopted the contract's own component names on the Python side
  (`ScanIngestRequest`, `HostPayload`, `PortPayload`, `FindingPayload`), so the two halves can no
  longer drift on naming. This entry used to say the opposite — if you half-remember a warning about
  a `scan_mode` divergence, read [contracts.md](./contracts.md)'s "Resolved divergence" section
  rather than re-opening it.

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
