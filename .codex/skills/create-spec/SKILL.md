---
name: create-spec
description: >-
  Scaffolds a new versioned feature spec under specs/NNN-feature-slug with the
  canonical folder tree (ui, architecture, contracts, open-questions, etc.).
  Gathers missing context by asking targeted questions when the user’s prompt
  is thin. Use when the user invokes /create-spec, says "create spec" (with
  optional topic), asks to start a new feature spec, or match specs/001-agent-tui
  structure.
user-invocable: true
argument-hint: "Short idea or feature name (optional)"
disable-model-invocation: true
---

# Create spec (`/create-spec`)

## Triggers

Treat any of these as invoking this skill:

- **`/create-spec`** … optional trailing text
- **“create spec”** / **“create a spec”** … optional topic or pasted issue body
- Explicit request to **scaffold** a new **`specs/NNN-…`** folder matching existing specs

**Initial idea** = everything after the command phrase, or the whole message if the user only pasted requirements.

## When context is enough

If the user provides a **rich** description (e.g. full issue: use case, journey, acceptance criteria), **do not** block on Q&A before scaffolding. In the **same turn**:

1. Derive slug + number, scaffold the full tree (see [REFERENCE.md](REFERENCE.md)).
2. Populate **`notes/requirements.md`** (or split if they asked) with their content, structured.
3. Add **`contracts/`** or other sub-docs **only when** the user gave stable facts worth pinning.
4. Seed **`open-questions/to-define.md`** with **ill-defined / ambiguous** gaps only. For **product or UX choices** (even if undecided), add or draft a **`decisions/`** file with **Status: proposed** instead of listing the choice as an “open question.”

## When context is thin

If **two or more** of these are missing or vague, **ask in one reply** (numbered list, keep it short) before or immediately after a **minimal** scaffold—your choice, but **do not** leave `to-define.md` empty when you already know what is unknown:

1. **Working title** or feature name (for README H1)
2. **Goal** — one paragraph: problem + who benefits
3. **Primary surface** — TUI, CLI, API, hardware, etc.
4. **v1 scope** vs **out of scope** (even rough bullets)
5. **Acceptance** — how we know it’s done (testable hints OK)
6. **Contracts** — any known flags, paths, JSON fields, env vars (or “none yet”)

After answers (same or next turn): scaffold or expand, and move resolved facts into **`notes/requirements.md`** / **`contracts/`**; keep **specification gaps** in **`open-questions/to-define.md`** and **choices** in **`decisions/`**.

## Workflow (do in order)

1. **Short name** — Derive `feature-slug` (kebab-case, lowercase, digits OK). From user text or from their answer to Q1.
2. **Next number** — Under `specs/`, dirs matching `^\d{3}-`; `N = max + 1` (or `1` if none). Folder: `specs/NNN-{feature-slug}/`.
3. **Scaffold** — Create the **full subtree** in [REFERENCE.md](REFERENCE.md#canonical-folder-tree). Every subfolder gets a minimal `README.md`; root gets `README.md` + `decisions/record-template.md` (copy from `specs/001-agent-tui/decisions/record-template.md` if present, else REFERENCE template).
4. **`open-questions/to-define.md`** — **Ill-defined** items only (skeleton OK). **Product/engineering choices** → **`decisions/`** (proposed DR if not yet accepted), not `open-questions`.
5. **Root README** — Feature title, one-line goal, **folder map** (include **`open-questions/`**), **suggested workflow**, **Existing artifacts** (link what you created).
6. **Handoff** — Use the **follow-up block** in [REFERENCE.md](REFERENCE.md#post-scaffold-prompts-for-the-user). If you asked questions and are waiting on answers, end with what you still need.

## Rules

- **Match prior specs** — Same layout as `specs/001-agent-tui/`; adapt `ui/` / `interaction/` for non-UI features like `002-agent-logs`.
- **No drive-by code** — Do not change application code unless the user explicitly asks in the same message.
- **Gitignore** — If `specs/` is ignored, mention once that tracking may need `.gitignore` adjustment.

## Depth

Templates: [REFERENCE.md](REFERENCE.md).
