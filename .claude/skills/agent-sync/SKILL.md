---
name: agent-sync
description: >-
  Keep project `.cursor/` and `.claude/` trees in sync when the user names a
  source of truth and optional paths. If direction or scope is missing, ask
  before copying. Use for Cursor ↔ Claude Code parity, agent-sync requests, or
  mirroring skills/rules/agents/MCP config. Never bulk-read all skills just to
  compare; work one named pair (or one basename) at a time.
---

# Agent sync (`.cursor` ↔ `.claude`)

## Purpose

Reconcile **this repo’s** Cursor config (`.cursor/`) with Claude Code config (`.claude/`) so matching files stay **byte-for-byte equal** when the user wants them to. Default action is **copy from source of truth to the other tree** (not merge-by-section unless the user asks).

## When to use

- User mentions **agent-sync**, **sync .cursor and .claude**, **mirror skills**, or **one editor’s copy is wrong**.
- After editing a skill, rule, agent, `mcp.json`, or `CLAUDE.md` in one tree and the other should match.

## Mandatory: source of truth and scope

If the user has **not** clearly stated:

1. **Direction** — which tree wins for this run (`cursor → claude` or `claude → cursor`), and  
2. **Scope** — a **specific** skill name, rule file, agent file, `mcp.json`, or `CLAUDE.md`, *or* explicit “sync **all** mirrored files”,  

then **stop and ask** (use AskQuestion when available, otherwise plain questions). Do **not** assume `.cursor` or `.claude` is authoritative.

Example prompts:

- “Should **`.cursor` → `.claude`** or **`.claude` → `.cursor`** be the copy direction for this sync?”
- “Which single item should we sync first (skill name, `mcp.json`, `CLAUDE.md`, or a rules/agents filename)?”

## Mirrored paths (this codebase)

| Artifact | Cursor path | Claude path |
|----------|-------------|-------------|
| Skill | `.cursor/skills/<name>/SKILL.md` | `.claude/skills/<name>/SKILL.md` |
| Rule | `.cursor/rules/*.mdc` | `.claude/rules/*.mdc` |
| Agent | `.cursor/agents/*.md` | `.claude/agents/*.md` |
| MCP | `.cursor/mcp.json` | `.claude/mcp.json` |
| Claude project instructions | `.cursor/CLAUDE.md` (optional) | `.claude/CLAUDE.md` |

Skill directory name `<name>` must match on both sides (e.g. `architecture-adr-sync`).

If the user wants **parity** for `CLAUDE.md` and only one root has the file, **create** the missing path on the destination using the source file after they confirm direction.

## Efficiency — do not read everything

- **Do not** open every `SKILL.md` under both `skills/` folders to diff the whole set “just in case.”
- **Do** work **one pair at a time**: read **only** the source and destination files needed for the **current** basename or skill name (e.g. one `SKILL.md` pair, or one rules file pair).
- For a **full sync** request: you may **list** directory entry names (cheap) to find matching basenames, then for **each** match, read **only that pair**, apply copy from SoT, then proceed — still **never** load unrelated skill bodies in bulk before you need them.

## Execution steps

1. Read `$ARGUMENTS` and the latest user message for **direction** and **target** (skill name, `mcp.json`, `CLAUDE.md`, or a specific rules/agents filename).
2. If either is missing → **ask**; do not pick a default direction.
3. Resolve paths using the table above; verify the source file exists before copying.
4. Copy **source → destination** so files match (overwrite destination). Preserve YAML frontmatter and line endings where possible.
5. Summarize in one short paragraph: direction, which paths were updated, and anything skipped (e.g. missing counterpart).

## Repo note (git)

In this project, **`.claude`** and **`.cursor/`** are **gitignored**. Syncing still keeps **local** Cursor vs Claude Code trees aligned; it does **not** commit to git unless the user changes ignore rules or copies content into tracked docs.

## User input

```text
$ARGUMENTS
```

Honor explicit direction and file/skill names from arguments first; otherwise fall back to asking.
