# feature-planning — reference

Canonical copies of every template live in **`specs/_templates/`**. Copy from there when
scaffolding; the skeletons below are the same shapes inlined for quick reference.

## Numbering

1. List directories in `specs/` whose names match `^\d{3}-` (ignore `_templates/`).
2. Parse the leading three digits; `next = max(digits) + 1` (or `1` if none).
3. Format folder: `f"{next:03d}-{feature-slug}"`.
4. If that exact folder already exists, fix the slug first; only append `-2`, `-3` as a last
   resort.

## Flat doc set (per feature)

| File | Owner | Required? |
|------|-------|-----------|
| `TRUTH.md` | feature-planning | always |
| `ARCHITECTURE.md` | architecture-agent | always |
| `DESIGN.md` | tui-design-agent (Textual) / frontend-design-agent (React web) | only when UI screens change |
| `INTEGRATION.md` | architecture-agent | only for a real cross-layer contract (rare here) |
| `TASKS.md` | feature-orchestrator | written in Phase 2, not now |
| `STRUCTURAL_REEVAL.md` | orchestrator | only on 4th rejection |

## TRUTH.md

```markdown
# TRUTH — {Feature title}

## Narrative

{Problem, who it's for, why now. Plain domain language.}

## Business rules

- {Rule 1}
- {Rule 2}

## User stories

1. As a {role}, I want {capability}, so that {benefit}.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| {name} | {state} | {action} | {observable outcome} |

## Out of scope (v1)

- {Explicitly excluded}

## Related specs

- Implementation: `ARCHITECTURE.md`{, `DESIGN.md` if UI}
```

`TRUTH.md` is **not** implementation detail — no file paths, no nmap flags, no code, no config
constants. Domain language and verifiable behaviour only.

## ARCHITECTURE.md

```markdown
# ARCHITECTURE — {Feature title}

## System context

Where this fits in the agent pipeline: discovery → port scan → NSE/deep inspection →
normalization (`ScanPayload`) → TUI / persistence. Name the modules touched under
`hardware-agent/src/agent/`.

## Data model / contracts

{Config constants, `ScanPayload` / pydantic field changes, nmap flag sets, exit codes.}

## New files and naming (mandatory)

| Layer | Path | Notes |
|-------|------|-------|
| Config | `hardware-agent/src/agent/config.py` | constants / scan_mode Literal |
| Discovery | `hardware-agent/src/agent/discovery/…` | scan logic |
| Normalize | `hardware-agent/src/agent/normalize/contracts.py` | payload shape |
| Scan runner | `hardware-agent/src/agent/scanner/runner.py` (`ScanRunner`) | thread new params (CLAUDE.md rule) |
| TUI screen | `hardware-agent/src/agent/tui/screens/scan_progress.py` (`ScanProgressScreen`) | thread new params |

## Constraints

- No new infrastructure by agents — flag `HUMAN_INFRA_REQUIRED` if a feature needs hardware,
  a daemon, or new external tooling.
- Reuse existing nmap runner / merge helpers; do not invent parallel scan paths.

## Testing expectations

- Unit tests under `hardware-agent/tests/unit/` for new constants / helpers.
- Follow the nearest existing test (e.g. `test_scan_mode_scripts.py`) for patterns.
```

The naming table **must** include every call site a new orchestrator/runner parameter passes
through — at minimum `ScanRunner` and `ScanProgressScreen` per the CLAUDE.md integration rule.

## DESIGN.md (Textual screens only)

```markdown
# DESIGN — {Screen / flow}

## Screen flow

{Which screen pushes which; entry and dismiss results.}

## Visual mockup

ASCII / box-drawing render of each new or changed screen — the visual frontend design.
Label widgets with their `#id`. Follow each mockup with a short prose explanation of the
layout regions, where focus starts, and how the render differs per state.

\`\`\`text
┌─ {title} ──────────────────────────────┐
│ {header / status line}                  │
│                                         │
│ > {option / row}            #{id}       │
│   {option / row}                        │
│                                         │
│ {footer: key bindings}                  │
└─────────────────────────────────────────┘
\`\`\`

## Layout

{Widgets top-to-bottom: header, OptionList / table, footer bindings.}

## Key bindings

| Key | Action |
|-----|--------|
| ↑/↓ | move selection |
| enter | confirm |
| esc | back / dismiss(None) |

## Copy

Exact strings for titles, option labels, status lines.

## States

| State | Behavior |
|-------|----------|
| Loading | {spinner / placeholder} |
| Empty | {message} |
| Error | {message + recovery} |

## Widget ids

- `#{id}` per interactive widget, for tests.
```

## Decision records

Settled product/engineering choices go in `decisions/` as `DR-XXXX-*.md` (proposed | accepted |
superseded). Specification gaps that block implementation go in `open-questions/to-define.md`.
Both folders are optional in the flat layout — create them lazily when there is content.

## Post-scaffold handoff (reply to the user)

After writing the specs, reply with:

```
Specs ready: specs/NNN-feature-slug/
- TRUTH.md
- ARCHITECTURE.md
{- DESIGN.md}

Approve the architecture, design, and file/naming conventions, then:
- /refine-specs   to stress-test before execution, or
- /feature-orchestrator   to generate TASKS.md and start the build.
```
