---
name: commit
description: Separate staged/unstaged changes into logical commits grouped by phase. Use when user says /commit, "commit these changes", or "separate into commits".
---

# Commit

Split all pending changes into logical, dependency-ordered commits with short messages.

## Workflow

1. Run `git status` and `git diff --name-only HEAD` to see all changed files
2. Group files into phases by analyzing what each change does:
   - **New modules/libraries** — foundation code and their tests come first
   - **Backend changes** — modifications to existing core logic
   - **Integration wiring** — connecting new code into existing pipelines
   - **TUI/UI changes** — frontend, screens, user-facing updates and their tests
   - **Config/infra** — settings, CI, linting, dependencies
   - **Chore** — cleanup, deletions, renames unrelated to the feature
3. Unstage everything with `git reset HEAD` if needed
4. For each phase in dependency order:
   - Stage only the files for that phase
   - Commit with a short message (under 60 chars)
5. Show `git log --oneline` of the new commits when done

## Commit message rules

- One line only, no body
- Use conventional prefix: `feat:`, `fix:`, `test:`, `refactor:`, `chore:`, `docs:`
- Describe WHAT changed, not WHY
- No co-author lines, no explanations
- Examples:
  - `feat: add workspace module and tests`
  - `fix: pass workspace_root through TUI scan path`
  - `chore: remove unused codex skill`
  - `test: add integration tests for scan flow`

## Grouping principles

- A new file and its test file belong in the same commit
- Modified test files go with the source changes they test
- If a test file covers multiple source changes, put it with the last phase it depends on
- Prefer more granular commits over fewer large ones
- Never mix feature code with unrelated cleanup
