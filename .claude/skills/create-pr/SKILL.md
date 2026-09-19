---
name: create-pr
description: >-
  Create a pull request from the current branch with automatically generated title and description
  based on committed changes. Analyzes git history, changed files, and diffs to create comprehensive PR documentation.
  Use when you've committed work and want to open a PR, asking "create a PR for my changes",
  or after finishing a feature branch. Generates PR title, description, labels, and reviewers intelligently.
compatibility: Requires GitHub CLI (gh) and git; designed for GitHub.com repositories
metadata:
  author: github-cli-skills
  source: skills/github-cli/create-pr.md
---

# Create Pull Request

Automatically create a pull request with comprehensive documentation based on your committed changes.
Analyzes git history, file changes, and diffs to generate intelligent PR titles, descriptions, and metadata.

## When to Use

- After committing work, ready to open a PR
- Asking "create a PR for my changes"
- Finished implementing a feature and want to document changes automatically
- Need to create PR with intelligent title and description from commits
- Want to let agent handle PR creation and description generation

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).
User may optionally provide:
- PR title (e.g., "Add device filtering")
- PR description (e.g., "Implements feature X")
- Target branch (default: `main`)
- Reviewers (e.g., "@rontho14")
- Labels (e.g., "backend,frontend")

If not provided, the skill will auto-generate these from your commits.

## Prerequisites

- GitHub CLI (`gh`) must be installed and authenticated
- Current directory must be a git repository with commits ready to push
- Current branch must have commits not yet on the target branch
- Remote must be set up and point to GitHub
- Branch should not already have an open PR

## Outline

### 1. Verify Git State

Check that we're in a valid state to create a PR:

```bash
# Verify we're in a git repository
git rev-parse --git-dir 2>/dev/null || error "Not in a git repository"

# Get current branch name
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Verify we're not on main/master
if [[ "$CURRENT_BRANCH" == "main" ]] || [[ "$CURRENT_BRANCH" == "master" ]]; then
  error "Cannot create PR from main/master branch. Please switch to a feature branch."
fi

# Get target branch (default: main, fallback to master)
TARGET_BRANCH="${USER_TARGET:-main}"
if ! git rev-parse --verify "$TARGET_BRANCH" >/dev/null 2>&1; then
  TARGET_BRANCH="master"
fi

# Verify there are commits to push
COMMITS=$(git log "$TARGET_BRANCH".."$CURRENT_BRANCH" --oneline)
if [ -z "$COMMITS" ]; then
  error "No commits to push. Make sure your branch has changes relative to $TARGET_BRANCH"
fi
```

### 2. Extract User-Provided Metadata

Parse `$ARGUMENTS` for optional overrides:
- **Title**: Look for quoted text or "title: ..." pattern
- **Description**: Look for description between markers or "description: ..." pattern
- **Target**: Look for "target: branch_name" or default to `main`
- **Reviewers**: Look for "@username" mentions or "reviewers: @user1,@user2"
- **Labels**: Look for "labels: label1,label2" pattern

Store these for optional use in PR creation.

### 3. Analyze Git History

Extract meaningful information from recent commits:

```bash
# Get commit messages on current branch that aren't on target
COMMIT_MESSAGES=$(git log "$TARGET_BRANCH".."$CURRENT_BRANCH" --format="%B" | head -50)

# Get short commit list for reference
COMMIT_LIST=$(git log "$TARGET_BRANCH".."$CURRENT_BRANCH" --oneline)

# Count commits
COMMIT_COUNT=$(git log "$TARGET_BRANCH".."$CURRENT_BRANCH" --oneline | wc -l)
```

Extract from commit messages:
- **Feature description**: Look for first substantive commit message
- **Related issues**: Extract Linear identifiers — `DMI-123`, `fixes DMI-123`, branch names
  like `dmi-123-slug` (issues live in Linear; bare `#123` patterns are legacy GitHub refs)
- **ADR references**: Extract `ADR-NNN` references
- **Breaking changes**: Look for "BREAKING", "breaking change" keywords

### 4. Analyze File Changes

Get comprehensive diff information:

```bash
# Get list of changed files with stats
FILE_CHANGES=$(git diff --stat "$TARGET_BRANCH".."$CURRENT_BRANCH")

# Get total lines changed
DIFF_STATS=$(git diff --numstat "$TARGET_BRANCH".."$CURRENT_BRANCH" | awk '{added+=$1; removed+=$2} END {print added ":" removed}')

# Categorize files by type
CHANGED_FILES=$(git diff --name-only "$TARGET_BRANCH".."$CURRENT_BRANCH")
```

Parse file changes to determine:
- **Component**: Which components affected (backend, frontend, hardware-agent, infra, docs)
- **Change type**: Feature (new files), Bugfix (modified files), Refactor (structure changes), Docs
- **Files summary**: Group files by component

### 4b. Assess Alembic upgrade need

Decide from the PR diff alone whether operators must run `alembic upgrade head` after merge.
Do not ask the user; infer from git.

```bash
MIGRATION_FILES=$(git diff --name-only "$TARGET_BRANCH".."$CURRENT_BRANCH" -- 'backend/alembic/versions/*.py')
```

**Migration required** when any of the following is true:
- A **new** file under `backend/alembic/versions/` (new revision)
- An **edited** existing revision under `backend/alembic/versions/`

**Migration not required** when the diff has no such files — including backend-only PRs that only
touch routers, services, schemas, or tests, or that change SQLAlchemy models without a matching
Alembic revision in this branch.

Set `ALEMBIC_UPGRADE_NEEDED=true` or `false` and keep the list of migration paths for the PR body.

When `ALEMBIC_UPGRADE_NEEDED=true`, the generated description **must** include a **Database**
subsection (see step 6) that names the revision file(s) and says explicitly:

> **Alembic upgrade required** after merge: run `alembic upgrade head` on the target database.
> @rontho14 — please run the migration.

Use a real `@rontho14` mention in the markdown body so GitHub notifies them. `@rontho14` is already
the default reviewer; this callout is for the post-merge migration step, not a substitute for review.

When `ALEMBIC_UPGRADE_NEEDED=false`, add one line under **Database**: `No Alembic upgrade required
for this PR.`

### 5. Generate PR Title

If user didn't provide a title, generate one from commits and files:

**Strategy** (in order of preference):
1. First commit message (if meaningful and <60 chars)
2. Pattern from file changes: "Add X" (for new files), "Fix X" (for bug patterns), "Update X" (for modifications)
3. Component + action: "Backend: Add device filtering", "Frontend: Fix dashboard load"
4. Generic: "Update code on [CURRENT_BRANCH]"

**Title rules**:
- Max 60 characters (GitHub convention)
- Start with action verb: Add, Fix, Update, Refactor, Implement
- Include component if multiple components touched: "Backend: ", "Frontend: "
- No period at end

**Examples**:
```
✓ "Add device filtering endpoint"
✓ "Fix scan results parsing bug"
✓ "Backend: Implement authentication layer"
✓ "Update documentation for v1 release"
✗ "did some work" (too vague)
✗ "Add device filtering endpoint that filters devices by type and subnet (too long)"
```

### 6. Generate PR Description

Create comprehensive PR description with sections:

```markdown
## Summary
<1-3 sentence summary of changes>

## Type of Change
- [ ] New feature (non-breaking change adding functionality)
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] Breaking change (change causing existing functionality to change)
- [ ] Documentation update

## Component(s)
- Backend API
- Frontend
- Hardware Agent
- Infrastructure & CI
- Database
- Documentation

## Changes Made
- Bullet list of key changes
- Extracted from file changes and commits

## Related Issues
Fixes DMI-123 (if detected from branch name or commits — the "Fixes DMI-NN" magic word is
what lets the Linear↔GitHub integration auto-move the issue on merge)
Related to: [ADR-003](docs/adr/ADR-003.md) (if ADR mentioned)

## Testing
How to test these changes:
- Step-by-step instructions
- Or: "See test files added in this PR"

## Database
<If ALEMBIC_UPGRADE_NEEDED: list migration revision file(s), alembic upgrade required, @rontho14 please run the migration>
<Else: No Alembic upgrade required for this PR.>

## Checklist
- [ ] My code follows the project's code style
- [ ] I have updated relevant documentation
- [ ] I have added tests for new functionality (if applicable)
- [ ] All tests pass locally
- [ ] I have reviewed the CONTRIBUTING guidelines
<If ALEMBIC_UPGRADE_NEEDED: - [ ] @rontho14 ran `alembic upgrade head` on the target environment after merge>

## Additional Notes
[Any other context or notes]
```

### 7. Categorize by Change Type

Determine the nature of changes:

**Feature Detection**:
- New files in `backend/src/api/routes/` → Feature (API endpoint)
- New files in `frontend/src/` → Feature (UI component)
- Changes to `contracts/api-spec.openapi.json` → API contract change
- New migration files → Database schema change

**Bugfix Detection**:
- Commits mentioning: "fix", "bug", "issue", "patch"
- Small number of files changed (1-3 typically)
- Few lines added relative to removed

**Refactor Detection**:
- File moves or renames (same content, different path)
- Large number of files changed with similar patterns
- Commits mentioning: "refactor", "reorganize", "cleanup"

**Documentation Detection**:
- Only `.md` files changed
- Changes to `docs/`, `*.md`, `README.md`

### 8. Generate Component List

Categorize changed files:

```
backend/src/api/routes/*.py → Backend API
frontend/src/**/*.tsx → Frontend
hardware-agent/src/** → Hardware Agent
infra/** → Infrastructure & CI
backend/src/migrations/** → Database
docs/** → Documentation
contracts/** → Contracts & Schemas
```

Build checklist of components affected for PR description.

### 9. Extract Issue References

Search the branch name and commit messages for patterns:

- `DMI-123` / branch `dmi-123-slug` (Linear issue reference)
- `fixes DMI-123`, `closes DMI-123` (linking magic words)
- `ADR-001`, `ADR-003` (architecture decision records)
- `v1`, `v2` (version references)

Add these to the PR description's "Related Issues" section as `Fixes DMI-NN` — Linear's
GitHub integration parses this to link the PR and auto-move the issue on merge. If the
branch clearly implements a Linear issue but no identifier was found, ask the user which
DMI-NN it fixes rather than omitting the link.


### 10. Suggest Labels

Add appropriate labels:

**Category labels**:
- `backend`, `frontend`, `hardware-agent`, `infra`, `docs` (based on files changed)

**Type labels**:
- `feature` (new functionality)
- `bugfix` (fixes issue)
- `refactor` (code reorganization)
- `docs` (documentation)
- `chore` (maintenance)

**Status labels**:
- `ready-for-review` (automatic)
- `wip` (if branch name contains "wip" or user specifies)

### 11. Determine Reviewers

Automatically set reviewer for the PR:

```bash
# Always set @rontho14 as reviewer
REVIEWER="rontho14"

# Add additional reviewers based on file changes if desired
# Backend changes → add backend reviewers
# Frontend changes → add frontend reviewers
# etc.

# For now, @rontho14 is the default reviewer for all PRs
```

**Reviewer Strategy**:
- **Primary reviewer**: Always `@rontho14`
- **Optional additional reviewers**: Based on component (if configured)
  - Backend changes: Backend team
  - Frontend changes: Frontend team
  - etc.

### 12. Verify Branch is Pushed

Ensure commits are on remote:

```bash
# Push branch to remote (with user confirmation or auto-push)
REMOTE_BRANCH=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)

if [ -z "$REMOTE_BRANCH" ]; then
  # Branch not pushed yet
  echo "📤 Pushing branch to remote..."
  git push -u origin "$CURRENT_BRANCH"
else
  # Update remote if needed
  git push
fi
```

### 13. Create PR via GitHub CLI

Create the PR with generated or provided metadata:

```bash
gh pr create \
  --title "<GENERATED_TITLE>" \
  --body "<GENERATED_DESCRIPTION>" \
  --base "$TARGET_BRANCH" \
  --head "$CURRENT_BRANCH" \
  --reviewer "rontho14" \
  --label <LABEL_LIST> \
  --draft # Optional: use --draft if WIP detected
```

**Reviewer**: `@rontho14` is always set as the reviewer for code review.

### 14. Display PR Summary

Output success message with PR details:

```markdown
# ✅ Pull Request Created Successfully!

## PR Details

- **Title**: <PR title>
- **Number**: #123
- **URL**: <GitHub PR link>
- **Base**: $TARGET_BRANCH ← $CURRENT_BRANCH
- **Commits**: N changes
- **Files**: M files changed (+X, -Y lines)

## Summary
<PR description excerpt>

## Components
- Backend API
- Frontend
- Database

## Suggested Reviewers
@rontho14

## Labels
- `backend`, `feature`, `ready-for-review`

## Next Steps

1. 👁️ Share PR link with team for review
2. 📝 Address any review comments
3. ✅ Merge when approved

[View PR on GitHub](<PR_URL>)
```

### 14. Handle Errors

If anything goes wrong:

```
Error cases:
- Not on feature branch → "Please switch to a feature branch"
- No commits to push → "No new commits to create PR"
- Branch already has open PR → "PR already exists for this branch"
- Authentication failed → "GitHub CLI not authenticated"
- Remote not found → "Remote 'origin' not configured"
```

## Integration with Project

- **Component mapping**: References your monorepo structure (backend, frontend, hardware-agent, infra, docs)
- **ADR detection**: Finds ADR references in commits
- **Issue linking**: Detects Linear identifiers (DMI-NN) in branch names and commit
  messages; writes "Fixes DMI-NN" so the Linear↔GitHub integration links and auto-moves
  the issue
- **Branch naming**: Respects your feature branch conventions
- **Target branch**: Defaults to `main`, fallback to `master`

## Example Usage

```text
User: "I've committed all my changes, let's open a PR"

Skill: [Analyzes git history, file changes, commits]

Output:
# ✅ Pull Request Created Successfully!

## PR Details
- Title: "Backend: Add device filtering endpoint"
- Number: #45
- URL: https://github.com/Dmitri-IMT/vulnerability-scanner-device/pull/45
- Base: main ← feature/add-device-filtering
- Commits: 3 changes
- Files: 4 files changed (+120, -30 lines)

## Summary
Added filtering capabilities to device list endpoint. Supports filtering by device type, subnet, and status.

## Components
- Backend API
- Contracts & Schemas
- Database

## Suggested Reviewers
@rontho14

## Labels
- backend, feature, ready-for-review

## Next Steps
1. Share PR link with team
2. Address review comments
3. Merge when approved

[View PR on GitHub](https://github.com/...)
```

## Advanced Features

### Auto-detect PR Type

If PR touches multiple components or significant code:
- Show summary of all changes
- Suggest if this should be multiple PRs
- Warn if scope seems large

### Conflict Detection

Before creating PR:
```bash
# Check if PR would have conflicts
git merge-base --is-ancestor "$TARGET_BRANCH" HEAD
```

If conflicts likely, warn user: "This PR may have merge conflicts. Recommend rebasing first."

### Draft PR Option

If branch name contains "wip" or user specifies, create as draft:
```bash
gh pr create ... --draft
```

### Auto-request Review

Optionally auto-request reviews from suggested reviewers (can be disabled).

## Limitations

- Requires commits to be on current branch
- Title generation is heuristic-based (may need manual tweaking)
- Component detection based on file paths (edge cases may exist)
- Issue/ADR detection based on commit message patterns
- Requires branch to be pushed to GitHub first

## Troubleshooting

- **"Not in git repository"**: Run from project root directory
- **"No commits to push"**: Make sure you have commits relative to target branch
- **"Branch not pushed"**: Skill will attempt to push; ensure GitHub access configured
- **"Already has open PR"**: Check if PR already exists before creating
- **"Failed to create PR"**: Check `gh` authentication with `gh auth status`
- **"Title is too long"**: Skill will truncate to 60 chars; review manually if needed

## Best Practices

1. Use descriptive commit messages — they feed PR title and description
2. Commit related changes together — creates logical PR chunks
3. Branch from Linear's suggested branch name (`dmi-NN-slug`) and reference issues in
   commits (`fixes DMI-NN`) — auto-links in both Linear and the PR
4. Keep PRs focused — single feature per PR when possible
5. Review generated PR description — adjust if needed before merge
