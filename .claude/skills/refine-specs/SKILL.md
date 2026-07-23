---
name: refine-specs
description: >-
  Grilling session that challenges a feature's TRUTH/ARCHITECTURE/DESIGN against the domain
  language in docs/, the ADRs, and the existing hardware-agent code — sharpening terminology
  and scope and updating the spec docs inline as decisions crystallise. Read-only on
  application code. Use between /feature-planning and the human approval gate, or when the
  user asks to grill, refine, or stress-test specs.
disable-model-invocation: true
---

# Refine Specs

Phase 1.5 of the document-driven pipeline. Stress-test a feature's specs before the human
approval gate. You **edit spec docs** inline as decisions resolve, but you are **read-only**
on `hardware-agent/**`.

## When to run

Between `/feature-planning` (specs written) and the approval gate — or whenever the operator
asks to grill, refine, or stress-test specs. Never edit application code; never start
`/feature-orchestrator`.

## How to grill

Interview the operator relentlessly about every aspect of the feature until you reach shared
understanding. Walk down each branch of the design tree, resolving dependencies one-by-one.
For each question, **provide your recommended answer**.

**Ask one question at a time.** Wait for feedback before continuing.

If a question can be answered by exploring the codebase or `docs/`, explore instead of asking.
Use the **`consult-docs`** skill to load knowledge-base docs selectively (max two).

## Read the spec folder

Read everything in `specs/NNN-feature-slug/`:

| File | Role in grilling |
|------|------------------|
| `TRUTH.md` | Narrative, business rules, acceptance criteria — domain language lives here |
| `ARCHITECTURE.md` | Data model, scan pipeline, mandatory paths and naming |
| `DESIGN.md` | Textual screens, key bindings, copy, states (if present) |
| `INTEGRATION.md` | Cross-layer contract (rare in this single-layer repo) |

Canonical shapes: `specs/_templates/`.

## Domain awareness

Also read the stable knowledge base when terms are fuzzy:

- `docs/architecture/ARCHITECTURE.md` — system architecture
- `docs/adr/ADR-*.md` — accepted decisions (scan methodology, security model, tools)
- `docs/implementation/NSE-VULNERABILITY-PIPELINE.md` — NSE/vuln pipeline
- `hardware-agent/src/agent/` — existing code (read-only)

To locate that code without reading it all, use the **`.claude/docs/` code-map** as a router:
start at `.claude/docs/index.md`, follow the component `index.md` to the concept doc for the
modules in question, and jump to source via its `path:line` refs. The code-map maps concept→code
(what exists, how modules connect); the `docs/` KB above holds decisions/design. When a spec's
claim about how something works is in doubt, route through the code-map to the real source and
confirm before challenging.

### Challenge against TRUTH and the ADRs

When the operator or a spec uses a term that conflicts with `TRUTH.md`, the ADRs, or
established code, call it out immediately.

### Sharpen fuzzy language

When vague or overloaded terms appear (e.g. "scan", "deep", "device"), propose a precise
canonical term and which doc should own it (TRUTH vs ARCHITECTURE vs DESIGN).

### Discuss concrete scenarios

Stress-test with specific scenarios — invent edge cases that probe boundaries, failure modes
(nmap missing, timeouts, partial results), and scan-mode interactions.

### Cross-reference with code and ADRs

When the operator states how something works, check whether the code and ADRs agree. Surface
contradictions explicitly.

### Check acceptance criteria

Flag criteria that are ambiguous, untestable, or not observable. Propose rewritten Given/When/Then
rows for `TRUTH.md`.

### Scope smell test

Ask whether the feature still fits the usual shape (a bounded slice of the scan pipeline +
optional TUI screen). If scope balloons, flag it and propose a thinner v1 or a split.

## Update specs inline (do not batch)

- Narrative, business rules, acceptance, out-of-scope → `TRUTH.md`
- Config constants, nmap flags, file paths, payload shape → `ARCHITECTURE.md`
- Screen layout, key bindings, copy, states, widget ids → `DESIGN.md`
- Cross-layer contracts → `INTEGRATION.md`

`TRUTH.md` stays implementation-free — no paths, no flags, no code.

### Offer ADRs sparingly

Only suggest a new `docs/adr/ADR-XXX-*.md` when **all three** hold: hard to reverse,
surprising without context, and a real trade-off with genuine alternatives. Draft only after
operator confirmation.

## Session end

When grilling is complete (or the operator stops), summarize:

1. Spec files updated inline
2. Open questions remaining (→ `open-questions/to-define.md`)
3. ADR candidates, if any
4. Whether specs are ready for the approval gate and `/feature-orchestrator`
