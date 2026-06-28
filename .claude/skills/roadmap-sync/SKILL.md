---
name: roadmap-sync
description: >-
  Keep the per-layer roadmap docs in docs/roadmap/ consistent. The product roadmap is split
  across PI.md, BACKEND.md, FRONTEND.md, AI.md, SECURITY.md and a README index — these
  share contracts (API shapes, auth, the Pi command channel), so a change to one usually
  ripples to its neighbours. Use after editing any docs/roadmap/ file, when a roadmap decision
  may contradict an ADR/ARCHITECTURE, or when the user mentions roadmap drift / cross-doc sync.
---

# Roadmap cross-doc sync

The roadmap lives in **`docs/roadmap/`**. These docs are intentionally coupled. After you edit
one, check whether its neighbours need the same change.

## Dependency map

When you change the doc on the left, re-read and consider updating the docs on the right:

| Changed | Re-check |
|---------|----------|
| `PI.md` (command channel, provisioning) | `BACKEND.md` (queue/endpoints), `SECURITY.md` (channel auth), `FRONTEND.md` (trigger UX / online state) |
| `BACKEND.md` (API surface, auth, DTOs, data model, deploy) | `FRONTEND.md` (contract/DTOs, login UX), `PI.md` (command contract), `AI.md` (tool surface), `SECURITY.md` |
| `FRONTEND.md` (screens, auth UX) | `BACKEND.md` (needed endpoints), `SECURITY.md` (auth), `AI.md` (explainer panel) |
| `AI.md` (LLM explainer) | `BACKEND.md` (tools/endpoints), `FRONTEND.md` (panel), `SECURITY.md` (data scope/audit); keep consistent with `../implementation/INTELLIGENCE-IA-ASSESSMENT-ROADMAP.md` |
| `SECURITY.md` (auth, secrets, channel) | **all** roadmap docs reference it — sweep each |
| **any** doc | `README.md` status table + milestone sequencing |

## Workflow

1. Identify which roadmap file(s) you changed.
2. Look up the row(s) above. Open each "re-check" doc and confirm it still agrees. Update where it doesn't.
3. Always re-check `docs/roadmap/README.md`: keep the **status table** and **milestone sequencing** current.
4. **ADR/ARCHITECTURE check:** if your change relies on or contradicts a claim from
   `docs/adr/*` or `docs/architecture/ARCHITECTURE.md`, do **not** silently diverge — mark it
   **⚠️ REVALIDATE** in the roadmap doc and tell the user a real ADR may be needed. (The Pi
   command channel is the live example: it reopens ADR-005's "one-way push" → needs ADR-011.)
5. Report which sibling docs you touched (or confirmed unchanged) so the set stays coherent.

## Conventions used in these docs

- **⚠️ REVALIDATE** — claim inherited from an ADR/ARCHITECTURE that must be checked against code.
- **🔓 OPEN** — decision not yet made; options + recommendation are listed.
- Roadmap docs cover *future direction + open decisions*; they link to ADRs/ARCHITECTURE for
  current-state detail rather than restating it. Don't duplicate the IA roadmap into `AI.md`.
- Keep edits short and surgical; don't rewrite a neighbour just to restate — change only what drifted.
