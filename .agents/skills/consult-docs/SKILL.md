---
name: consult-docs
description: >-
  Select and read Dmitri knowledge-base docs under docs/ without loading the entire KB. Opens
  the routing index at docs/README.md, then reads at most two relevant files. Use when planning,
  scaffolding features, refining specs, auditing, or when unsure which docs/ file applies.
---

# Consult project docs

The knowledge base lives at **`docs/`**. **Do not read every file.**

## Workflow

1. Open **`docs/README.md`** (the routing index).
2. Identify the task domain from the index tables (architecture, scan methodology, security,
   NSE/vuln pipeline, UI, deployment, database…).
3. Read **only one** file from the matching row, unless the task clearly spans two domains
   (maximum **two** docs total).
4. Apply the global conventions from the README's Global conventions section.

## When invoked from the pipeline

- **`refine-specs`**: the index + docs that contradict or clarify spec terminology or ADRs.
- **Orchestration subagents**: only the docs cited in `ARCHITECTURE.md` / `DESIGN.md` or the
  task prompt — use this skill if the path is unclear.

Do not duplicate doc content into chat; cite paths and apply conventions.
