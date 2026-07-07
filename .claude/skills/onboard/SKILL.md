---
name: onboard
description: >-
  Provide onboarding-friendly status overview for team members unfamiliar with the project.
  Show recent activity, open issues by component, PR review queue, blockers, and quick component guide.
  Use when a new team member joins, asking "what should I know about this project?",
  joining a standup, or needing quick situational awareness. Manual invocation via /onboard.
compatibility: Requires the linear-server MCP connection (issues live in Linear), plus GitHub CLI (gh) and git for PRs/commits
metadata:
  author: github-cli-skills
  source: skills/github-cli/onboard.md
---

# Team Context Aggregator

Provide a comprehensive, onboarding-friendly overview of the project's current status.
Show recent activity, open issues by component, PR review queue, blockers, and component guide.

## When to Use

- New team member joins or onboarding
- Asking "what should I know about this project?"
- Joining a standup or sprint planning
- Need quick situational awareness without deep knowledge of codebase
- Regular team status updates
- Manual invocation: `/gh-team-context-aggregator`

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).
User may optionally provide a time window (e.g., "last 14 days", "last week") or filter by component.

## Prerequisites

- Linear MCP tools (`mcp__linear-server__*`) for issues; load via ToolSearch if deferred:
  `list_issues`, `list_milestones`, `get_project`
- GitHub CLI (`gh`) authenticated + git repository, for PRs and commits (those stay on GitHub)
- Documentation should be available: `docs/architecture/ARCHITECTURE.md`, `docs/roadmap/`, component READMEs

## Outline

### 1. Determine Time Window

Parse `$ARGUMENTS` to extract time window preference:
- "last 7 days" (default)
- "last 14 days"
- "last 30 days"
- "this week"
- "this month"

Convert to date range for filtering.
Default to **last 7 days** if not specified.

### 2. Fetch Repository Information

Get basic repository info:

```bash
gh repo view --json description,nameWithOwner,url,isPrivate
```

Extract:
- Repository name
- Description
- URL
- Visibility

### 3. Fetch Recent Activity

Fetch recent PRs and commits:

```bash
# Merged PRs in time window
gh pr list --state merged --limit 50 --json number,title,mergedAt,author,labels \
  --jq '.[] | select(.mergedAt > "<START_DATE>") | .'

# Open PRs
gh pr list --state open --limit 50 --json number,title,createdAt,author,labels,reviewRequests

# Recent commits
git log --since="<TIME_WINDOW>" --oneline --all | head -20
```

Parse to extract:
- **Merged PRs**: Count and samples
- **Open PRs**: Count, authors, review status
- **Recent commits**: Count, sample messages

### 4. Fetch Open Issues (Linear)

Issues live in Linear (team **Dmitri**, project **Dmitri**). Fetch open work with
`mcp__linear-server__list_issues` (team `Dmitri`, states Backlog/Todo/In Progress/In Review).
Exclude closed `Migrated` issues — they are imported GitHub history.

For each issue, determine component from labels:

| Label | Component |
|-------|-----------|
| `layer:backend` \| `epic:backend` | Backend API |
| `layer:frontend` \| `epic:frontend` | Frontend |
| `layer:pi` \| `epic:agent` | Pi Agent / Scanner |
| `layer:auth` | Auth |
| `type:ops` | Ops / Infrastructure |
| `type:adr` \| `type:documentation` | Documentation |
| (no layer label) | Uncategorized |

Group by epic (parent issue) when present — the epics ARE the delivery phases — then sort
by Linear priority, then created date. Note the milestone (e.g. **MVP — Control**) and its
target date via `list_milestones`.

### 5. Identify Blockers and Dependencies

Blockers are real Linear relations, not text patterns: `list_issues` results include
relations; for suspicious cases use `get_issue` with `includeRelations: true`. Report each
open issue that is blocked, what blocks it, and the blocker's state. Also scan PR
descriptions (`gh pr list`) for "waiting" language.

### 6. Analyze PR Review Queue

Get PRs waiting for review:

```bash
gh pr list --state open --json number,title,author,reviewRequests,createdAt,labels
```

Identify:
- PRs with pending review requests
- Age of PR (how long waiting)
- Reviewer assignment

### 7. Fetch Component Information

Read or summarize components from documentation:

```
# Read from ARCHITECTURE.md or extract manually:
```

Extract component descriptions:
- **Hardware Agent (Raspberry Pi 4 + Python + Nmap)**: Executes network scans, normalizes results, sends to backend
- **Backend API (FastAPI + PostgreSQL)**: Validates, persists, and serves scan data
- **Frontend (React + Vite)**: Web UI for viewing results and managing scans
- **Database (PostgreSQL)**: Stores scans, devices, ports, services, findings
- **Infrastructure (Docker, CI/CD)**: Deployment, container management, GitHub Actions pipelines

### 8. Build Recent Contributors List

Get who's been active recently:

```bash
git log --since="<TIME_WINDOW>" --format="%an" | sort | uniq -c | sort -rn
```

Top 3-5 contributors in time window.

### 9. Generate Onboarding-Friendly Report

Produce a comprehensive markdown report optimized for readability and quick scanning:

```markdown
# Vulnerability Scanner Project — Team Status Brief

## 👋 Welcome to the Team!

This brief gives you a quick overview of the project status, ongoing work, and key components.
More detailed information is available in the links at the bottom.

---

## 📊 Quick Status

**Repository**: Dmitri-IMT/vulnerability-scanner-device  
**Latest Activity**: Last 7 days  
**Team Size**: Active contributors this week: N people  

| Metric | Count |
|--------|-------|
| 📖 Merged PRs | 3 |
| 🔄 Open PRs | 7 (4 in review, 3 in progress) |
| ❌ Blocked PRs | 1 (#89 waiting on issue #45) |
| 📋 Open Issues | 24 |
| ⏳ Stalled Issues (30+ days) | 2 |

---

## 🎯 What This Project Does

This is an embedded network vulnerability scanning device for a university lab.
- **Hardware**: Raspberry Pi 4 runs Nmap scans on lab networks
- **Backend**: FastAPI server stores and processes scan results
- **Frontend**: React web UI shows network devices, vulnerabilities, and scan history
- **Goal**: Help network administrators find and fix security issues on lab equipment

**Scope**: University robotics lab deployment (not production enterprise, not campus-wide)  
**Users**: ~10 operators/viewers in lab  
**Scan Rate**: 1-2 scans per day typical

---

## 🔨 Component Overview

### Hardware Agent (Raspberry Pi + Nmap)
**What it does**: Runs network scanning and vulnerability detection  
**Tech**: Python, Nmap, NSE scripts  
**Recent changes**: 2 PRs this week — scanning accuracy improvements  
**Status**: ✅ Stable

**Read more**: [hardware-agent/README.md](hardware-agent/README.md)

### Backend API (FastAPI + PostgreSQL)
**What it does**: Receives scans, validates data, stores results, serves API  
**Tech**: FastAPI, PostgreSQL, SQLModel ORM  
**Recent changes**: 3 PRs — new endpoints, database optimizations  
**Status**: 🔄 Active development

**Blockers**: Waiting on authentication framework (issue #45)

**Read more**: [backend/README.md](backend/README.md), [ADR-003 Backend Stack](docs/adr/ADR-003.md)

### Frontend (React + TypeScript + Vite)
**What it does**: Web dashboard for viewing scans and managing devices  
**Tech**: React, TypeScript, Vite, TanStack Query  
**Recent changes**: 1 PR — UI improvements  
**Status**: ✅ Stable

**Read more**: [frontend/README.md](frontend/README.md), [ADR-008 Frontend Stack](docs/adr/ADR-008.md)

### Database (PostgreSQL)
**What it does**: Central data store for scans, devices, ports, services, vulnerabilities  
**Tech**: PostgreSQL, SQLModel, Alembic migrations  
**Recent changes**: 1 PR — new findings schema  
**Status**: ✅ Stable

**Read more**: [ADR-009 Database Stack](docs/adr/ADR-009.md)

### Infrastructure & CI (Docker, GitHub Actions)
**What it does**: Container orchestration, deployment automation, code quality checks  
**Tech**: Docker, Docker Compose, GitHub Actions  
**Recent changes**: None this week  
**Status**: ✅ Stable

**Read more**: [infra/README.md](infra/README.md), [ADR-007 Deployment](docs/adr/ADR-007.md)

---

## 📋 Open Issues by Component

### Backend API (8 issues)

- 🔴 **[#45] Authentication Framework** — Priority: CRITICAL
  - Assigned: @alice
  - Age: 12 days
  - *Blocks: Other backend work*

- 🟡 **[#87] Add device filtering endpoint** — Priority: HIGH
  - Assigned: @bob
  - Age: 3 days
  - Depends on: #45

- 🟢 **[#92] Optimize scan query performance** — Priority: MEDIUM
  - Unassigned
  - Age: 1 day

- [... 5 more backend issues, sorted by priority ...]

### Frontend (4 issues)

- 🟡 **[#81] Dark mode support** — Priority: MEDIUM
  - Assigned: @carol
  - Age: 5 days

- [... 3 more frontend issues ...]

### Hardware Agent (3 issues)

- 🟢 **[#95] Add additional NSE script categories** — Priority: LOW
  - Unassigned
  - Age: 2 days

- [... 2 more hardware issues ...]

### Infrastructure & CI (2 issues)

- 🟢 **[#98] Add Docker image size optimization** — Priority: LOW
  - Unassigned
  - Age: 1 day

- [... 1 more infra issue ...]

### Documentation (3 issues)

- 🟡 **[#89] Update deployment guide** — Priority: MEDIUM
  - Assigned: @dave
  - Age: 8 days

- [... 2 more doc issues ...]

### Uncategorized (4 issues)

- [List issues without clear labels]

---

## 🚫 Current Blockers

| Blocker | Impact | Status |
|---------|--------|--------|
| **#45: Authentication Framework** | Blocks ~5 backend PRs | @alice assigned, started |
| **#89: Deployment guide update** | Blocks release planning | @dave working on it |

**How to help**: Check if you can unblock any of these!

---

## 🔄 PR Review Queue

| PR | Author | Status | Age | Reviewers |
|----|--------|--------|-----|-----------|
| [#102] Add device inventory | @bob | Waiting for review | 2 days | Needs reviewer |
| [#101] Database optimization | @alice | Approved, ready to merge | 1 day | Ready to go! |
| [#100] UI improvements | @carol | Feedback given | 3 days | Awaiting updates |

**Action**: Review #102 if you have capacity — 2 days waiting!

---

## 👥 Recent Contributors

**Last 7 days**:
1. Alice (@alice) — 8 commits
2. Bob (@bob) — 5 commits
3. Carol (@carol) — 3 commits

**Welcome to**: Anyone new joining the team!

---

## 🎓 Onboarding Checklist

**Your first steps**:

- [ ] Read [README.md](README.md) for project overview
- [ ] Review [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) for system design
- [ ] Pick a [good first issue](#suggested-issues-for-new-contributors) to work on
- [ ] Set up local dev environment: `make dev` or see [DEV-SETUP.md](docs/DEV-SETUP.md)
- [ ] Ask questions in team chat or create GitHub discussion

**Suggested issues for new contributors** (good first issues):

1. [DMI-92] Optimize scan query performance — Backend, good learning opportunity
2. [DMI-98] Docker image size optimization — Ops, self-contained task
3. [DMI-105] Update hardware agent logging — Pi Agent, well-defined scope

---

## 📚 Key Documentation

Start here:
- **[README.md](README.md)** — Project overview (start here!)
- **[ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)** — System design and components
- **[DEV-SETUP.md](docs/DEV-SETUP.md)** — Local development setup
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — How to contribute

Deep dives by component:
- [Backend Stack (ADR-003)](docs/adr/ADR-003.md) — Technology decisions
- [Frontend Stack (ADR-008)](docs/adr/ADR-008.md) — React + TypeScript choices
- [Database Stack (ADR-009)](docs/adr/ADR-009.md) — PostgreSQL + ORM
- [Deployment (ADR-007)](docs/adr/ADR-007.md) — Docker + CI/CD

---

## 🛠️ Common Tasks

**Want to...**

- **Start a new feature?** Create a Linear issue via the `create-issue` skill (human-validated
  product brief) → branch from Linear's suggested branch name → open PR with "Fixes DMI-NN"
  
- **Review a PR?** Check review queue above → use `gh pr view` or GitHub UI
  - Use [pr-checklist](CONTRIBUTING.md) if exists
  
- **Deploy changes?** Requires PR approval + passing CI
  - See [deployment docs](infra/README.md)
  
- **Run tests?** `make test` or `pytest backend/tests/`
  - See [DEV-SETUP.md](docs/DEV-SETUP.md)

---

## 📞 Getting Help

- **Questions?** Check [GitHub Discussions](https://github.com/Dmitri-IMT/vulnerability-scanner-device/discussions) or ask team
- **Found a bug?** Create a Linear issue (`create-issue` skill) with steps to reproduce
- **Want to contribute?** See [CONTRIBUTING.md](CONTRIBUTING.md)
- **Onboarding help?** Ask @alice (team lead) or whoever greeted you

---

## 📅 Next Milestones

- **Sprint end** (April 28): Complete backend authentication (DMI-45)
- **Beta v1** (May 15): All core features complete, ready for lab testing
- **v1 Release** (June 1): Deploy to university lab

---

## 🔗 Quick Links

| Link | Purpose |
|------|---------|
| [GitHub Repo](https://github.com/Dmitri-IMT/vulnerability-scanner-device) | Source code |
| [Linear — project Dmitri](https://linear.app/dmitri-imt/project/dmitri-9494f422b1a8) | Work queue (issues, epics, milestones) |
| [GitHub PRs](https://github.com/Dmitri-IMT/vulnerability-scanner-device/pulls) | Code reviews |
| [GitHub Discussions](https://github.com/Dmitri-IMT/vulnerability-scanner-device/discussions) | Questions & ideas |

---

**Last updated**: Today  
**Status**: All systems operational ✅

---

*Generated by gh-team-context-aggregator skill*
```

### 10. Customize by User Role (Optional)

If user indicates they're a specific role, tailor output:

- **Frontend developer**: Emphasize frontend issues, skip hardware details
- **Backend developer**: Emphasize backend issues, show API/database status
- **DevOps/Infra**: Show CI/CD queue, deployment status, infrastructure issues
- **Tech lead**: Show blockers, team metrics, release timeline
- **Manager**: High-level status, team capacity, timeline

Add a note at top: "Customized for: Frontend Developer" and adjust content accordingly.

## Integration with Project

- **Component descriptions**: Source from `docs/architecture/ARCHITECTURE.md` sections 2.1–2.6
- **Issue labels**: Linear taxonomy — `layer:pi`, `layer:backend`, `layer:frontend`,
  `layer:auth`, `type:ops`, `type:decision`, `agentic` (legacy `epic:*` on `Migrated` only)
- **Recent activity**: issues via Linear MCP; PRs/commits via `gh` CLI and git
- **Contributing guide**: Link to [CONTRIBUTING.md](CONTRIBUTING.md)
- **Setup guide**: Link to [docs/DEV-SETUP.md](docs/DEV-SETUP.md)
- **Architecture docs**: Link to ADRs and main ARCHITECTURE.md

## Example Usage

```text
User: "I just joined the team, can you give me a quick overview?"

Skill: [Fetches repo info, recent PRs, open issues, blockers, component info]

Output:
# Vulnerability Scanner Project — Team Status Brief

## Quick Status
- 3 merged PRs last week
- 7 open PRs (4 in review)
- 24 open issues
- 1 blocker (DMI-45 — authentication framework)

## Component Overview
[5 components with current status and recent activity]

## Open Issues by Component
[Issues grouped by backend/frontend/hardware/infra/docs with priorities]

## PR Review Queue
- #102 waiting 2 days for review

## Onboarding Checklist
[First steps for new contributor]

[Continues with key docs, common tasks, quick links...]

User reads this and knows:
- What the project does
- Who's working on what
- What they should work on first
- Where to find help
```

## Limitations

- Requires Linear issues and GitHub PRs to be properly labeled
- Requires documentation files to exist and be readable
- Assumes standard GitHub conventions
- May not reflect real-time status (GitHub API has some caching)
- Component priority may not match team's actual current priorities

## Troubleshooting

- **"Issues list is too long"**: Filter by label or time window
- **"No labels on issues"**: Ask team to use consistent labels (backend, frontend, etc.)
- **"Missing documentation"**: Ensure README.md and ARCHITECTURE.md exist
- **"Outdated information"**: Add timestamp, regenerate frequently

## Best Practices

1. Run this daily/weekly to keep team updated
2. Update issue labels consistently so filtering works well
3. Keep README.md and ARCHITECTURE.md current
4. Review blockers regularly — unblock stuck items
5. Share output in team channels for visibility
