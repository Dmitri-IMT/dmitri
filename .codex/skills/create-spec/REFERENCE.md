# create-spec — reference

## Canonical folder tree

Create **all** of these under `specs/NNN-feature-slug/`:

| Path | Required files |
|------|----------------|
| (root) | `README.md` |
| `architecture/` | `README.md` |
| `bugs/` | `README.md` (table header; empty or “none yet”) |
| `checklists/` | `README.md` |
| `contracts/` | `README.md` |
| `decisions/` | `README.md`, `record-template.md` |
| `interaction/` | `README.md` |
| `notes/` | `README.md` |
| `plans/` | `README.md` |
| `tech-stack/` | `README.md` |
| `testing/` | `README.md` |
| `ui/` | `README.md` |

## Numbering algorithm

1. List directories in `specs/` whose names match `^[0-9]{3}-`.
2. Parse leading three digits; `next = max(digits) + 1` (if none, use `1`).
3. Format folder: `f"{next:03d}-{feature-slug}"`.
4. If that exact folder already exists, append `-2`, `-3`, … only as last resort; prefer fixing slug collisions first.

## Subfolder README content (minimal)

Each sub-`README.md` should have:

- **H1** title matching the folder purpose (see `001-agent-tui` for tone).
- **What belongs here** — 3–6 bullets.
- **What belongs elsewhere** — 2–4 bullets pointing at sibling folders.
- **Files** — table with “— | *Add files as needed.*” or one placeholder row.

Do **not** invent long `plans/NN-*.md` or `bugs/NNN-*.md` unless the user asks; keep scaffolds thin.

## Root `README.md` skeleton

```markdown
# Feature: {Title} (`NNN-feature-slug`)

{One paragraph: goal + how this spec folder relates to code paths if known, else “implementation TBD under repo.”}

## Folder map

| Folder | Purpose |
|--------|---------|
| [`ui/`](ui/) | … |
| [`interaction/`](interaction/) | … |
| [`architecture/`](architecture/) | … |
| [`tech-stack/`](tech-stack/) | … |
| [`contracts/`](contracts/) | … |
| [`decisions/`](decisions/) | … |
| [`notes/`](notes/) | … |
| [`testing/`](testing/) | … |
| [`checklists/`](checklists/) | … |
| [`bugs/`](bugs/) | … |
| [`plans/`](plans/) | … |

## Suggested workflow

1. …
2. …

## Existing artifacts

- (none beyond this scaffold — add `spec.md` when ready and link here.)
```

Reuse the **same folder purposes** as `specs/001-agent-tui/README.md` unless the feature is non-UI; then adjust `ui/` and `interaction/` blurbs to “optional” or “operator journeys” per `002-agent-logs`.

## Decision record template

If `specs/001-agent-tui/decisions/record-template.md` is missing, use:

```markdown
# DR-XXXX: Short title

**Date**: YYYY-MM-DD  
**Status**: proposed | accepted | superseded

## Context

What problem or question triggered this?

## Decision

What did we choose?

## Consequences

**Positive**: …  
**Negative / follow-ups**: …

## Links

- Related specs: …
- Related code: …
```

## Post-scaffold prompts for the user

After creating the tree, reply with a short confirmation (path + `NNN`) and **ask the user** to continue with structured detail. Use this block (edit out sections that clearly do not apply):

---

**Scaffold ready:** `specs/NNN-feature-slug/`

Next, let’s sharpen the spec. Reply in one message (bullet points OK):

1. **Scope** — What is in v1 vs explicitly out of scope?
2. **Surfaces** — CLI / TUI / API / jobs / hardware: which ones matter?
3. **Contracts** — Any stable inputs/outputs (env vars, files, JSON, exit codes) you already know?
4. **Dependencies** — External tools, services, or repos?
5. **Acceptance** — How will we know “done” (testable checks)?
6. **Risks** — Security, privacy, performance, or compliance concerns?

Optional: say which subfolder you want filled first (`contracts/`, `architecture/`, `plans/`, …) and the agent will draft there.

---

## Optional: slash command hint

If the environment supports slash commands, document for the user:

```text
/create-spec {initial idea in natural language}
```
