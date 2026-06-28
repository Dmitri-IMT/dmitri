# POOP — Technical ledger (append only)

`POOP.md` is the "poop" of the subagents — a joke about subagents constantly producing messy
code. Every coder, test engineer, and reviewer appends one section before returning. The
orchestrator appends only `STRUCTURAL_REEVAL` blocks. Never overwrite prior entries.

Each entry includes:
1. **Order Given** — the exact task scope / prompt.
2. **What, How, and Why** — what was done, how, and why that approach.
3. **Decisions Made** — key technical decisions.
4. **Code Changed / Reviewed** — file paths only, no snippets.

---

## Task 1 — {name} — agent-developer ({YYYY-MM-DD})

### Order Given
{…}

### What, How, and Why
{…}

### Decisions Made
- {…}

### Code Changed
- {path}

---

## Task 1 — {name} — test-engineer ({YYYY-MM-DD})

### Order Given
{…}

### What, How, and Why
{…}

### Decisions Made
- {…}

### Code Changed
- {test path}

---

## Task 1 — {name} — code-reviewer ({YYYY-MM-DD})

### Order Given
{…}

### What, How, and Why
{ran `uv run pytest` + `uv run ruff check`; result …}

### Decisions Made
- {[APPROVE] / [REJECT] rationale}

### Code Reviewed
- {path}
