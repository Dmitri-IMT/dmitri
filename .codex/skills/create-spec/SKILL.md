---
name: create-spec
description: >-
  Scaffold a new versioned feature spec under specs/NNN-feature-slug with the
  same folder layout as existing features (ui, architecture, contracts, etc.).
  Use when the user invokes /create-spec, asks to create a spec folder, start a
  new feature spec, or match specs/001-agent-tui structure for a new idea.
user-invocable: true
argument-hint: "Short idea or feature name (initial prompt)"
---

# Create spec (`/create-spec`)

## Inputs

Treat **everything the user typed after `/create-spec`** (or the skill invocation) as the **initial idea**. If empty, ask once for a one-paragraph description before scaffolding.

## Workflow (do in order)

1. **Short name** — Derive a `feature-slug` (kebab-case, lowercase, digits allowed; no spaces). Prefer 2–5 meaningful tokens from the idea (e.g. `agent-nmap-logs`, `backend-auth`).
2. **Next number** — Under repo root `specs/`, find existing dirs matching `^\d{3}-`. Let `N` be one plus the highest numeric prefix (e.g. if `001-…` and `002-…` exist → `003`). Pad to three digits → `NNN`. Final folder: `specs/NNN-{feature-slug}/`.
3. **Scaffold** — Create that folder and **the full subtree** listed in [REFERENCE.md](REFERENCE.md#canonical-folder-tree). Every subfolder gets a minimal `README.md`; root gets `README.md` + `decisions/record-template.md` (copy from `specs/001-agent-tui/decisions/record-template.md` if present, else use [REFERENCE.md](REFERENCE.md#decision-record-template)).
4. **Root README** — Must include: feature title, one-line goal from the user’s idea, **folder map table** (same columns as `specs/001-agent-tui/README.md`), **suggested workflow** (notes → decisions → contracts/architecture), and **“Existing artifacts”** listing only what you created (link placeholders OK).
5. **Handoff** — Do **not** fill long specs in the same turn unless the user asks. After files exist, **prompt the user** using the **follow-up block** in [REFERENCE.md](REFERENCE.md#post-scaffold-prompts-for-the-user).

## Rules

- **Match prior specs** — Mirror `specs/001-agent-tui/` layout and README tone; adapt folder blurbs only when the feature is obviously non-UI (then say “optional / N/A” in `ui/README.md` like `002-agent-logs`).
- **No drive-by code** — Do not change application code unless the user explicitly asks in the same message.
- **Gitignore** — If `specs/` is ignored by git, mention once that commits may need `.gitignore` adjustment if they want the tree tracked.

## Depth

Templates and copy-paste snippets: [REFERENCE.md](REFERENCE.md).
