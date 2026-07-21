# Development setup — **hardware-agent** & **Dmitri** (TUI)

This guide covers **only** the `**hardware-agent`** Python package and the **Textual TUI** (`dmitri` / `dmitri start`).

**Deployment context:** o agente **Dmitri** está orientado ao laboratório **NSPi** (robótica industrial na universidade). Equipamentos típicos (CLPs em Ethernet, Pi em Wi‑Fi) e o foco só-TUI estão descritos no [README](../README.md) (secções *Foco atual do desenvolvimento* e *Ambiente de implantação: laboratório NSPi*).

**Not in scope right now:** Docker Compose, the **backend** API, and the **frontend** web app. You do not need Node.js, `npm`, or backend `.env` / `docker compose` to work on Dmitri. The API and frontend will be added later; when that happens, extend this doc or add a separate full-stack guide.

---

## Quick install (recommended)

From the **repo root** after cloning:

```bash
# macOS / Linux / Pi — full dev bootstrap (agent + backend + local Supabase when Docker is available)
./install.sh

# Agent-only (Pi, no Docker)
./install.sh --agent-only

# Skip post-install pytest
./install.sh --skip-verify

# Also install pre-commit pre-push hooks
./install.sh --hooks
```

Windows (PowerShell):

```powershell
.\install.ps1
.\install.ps1 -AgentOnly
.\install.ps1 -SkipVerify
.\install.ps1 -Hooks
```

The root installer auto-installs **uv** and **nmap**, runs `uv sync --extra dev` in both packages (required for `uv run pytest`), seeds `backend/.env` when missing, and — if Docker and the Supabase CLI are present — starts local Postgres and runs Alembic migrations. It also installs a `dmitri` launcher in `~/.local/bin` (and adds that directory to your shell `PATH` on macOS/Linux when missing).

After `./install.sh`, run the TUI from anywhere:

```bash
dmitri
```

`hardware-agent/install.sh` is a thin wrapper that runs `./install.sh --agent-only`.

Manual steps below remain valid if you prefer not to use the scripts.

---

## Prerequisites

- **Git**
- **Python 3.11+** (matches `requires-python` in `hardware-agent/pyproject.toml`)
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — required for syncing dependencies (supported path; `pip` is an unsupported escape hatch per product specs)
- **Nmap** — install on the host yourself. It must be available for **real** scans when you run the TUI. Verify with `nmap --version`. Automated **tests** mock nmap; CI does not install it — see `[specs/001-agent-tui/tech-stack/testing-tooling.md](../specs/001-agent-tui/tech-stack/testing-tooling.md)`.

### Nmap (local runs)

- **Windows**: [Nmap download](https://nmap.org/download.html) or a package manager (e.g. Chocolatey: `choco install nmap`).
- **macOS**: `brew install nmap` or the upstream installer.
- **Debian / Ubuntu**: `sudo apt install nmap`
- **Fedora**: `sudo dnf install nmap`

---

## Install dependencies (**uv**)

From `**hardware-agent/**`:

```bash
cd hardware-agent
uv sync --extra dev
```

This installs runtime and dev dependencies (including **pytest**). Plain `uv sync` omits dev extras and `uv run pytest` will fail. It does **not** install Nmap; if `nmap` is missing from `PATH`, install it using the section above (or use `./install.sh` from the repo root).

**Advanced (unsupported):** `pip install -e .` inside `hardware-agent/` may work in some environments (e.g. air-gapped mirrors), but it is **not** the supported install path — prefer **uv** — `[specs/001-agent-tui/tech-stack/package-and-distribution.md](../specs/001-agent-tui/tech-stack/package-and-distribution.md)`.

### Persisted prefs (TUI)

When saving app config (e.g. under `%LOCALAPPDATA%\Dmitri\`, XDG `~/.config/dmitri/`, etc.), use **write a `*.tmp`next to the real file → flush →`os.replace`/`Path.replace`** so a crash never leaves a half-written config. Details:` [specs/001-agent-tui/tech-stack/persistence-and-io.md](../specs/001-agent-tui/tech-stack/persistence-and-io.md) `(**Atomic save**). Default scan output for **Use default** is under `**…/Dmitri/results`** —` [specs/001-agent-tui/ui/screens.md](../specs/001-agent-tui/ui/screens.md)`.

---

## Run the TUI

From `**hardware-agent/`** (after `uv sync`):

```bash
cd hardware-agent
uv run dmitri
# or
uv run dmitri start
```

The `**dmitri**` console script is declared in `hardware-agent/pyproject.toml` (`[project.scripts]`). If your environment cannot see the script entrypoint, use:

```bash
uv run python -m agent.cli
```

---

## Optional: pre-commit (repo-wide)

If the repository configures **pre-commit** at the root:

```bash
pip install pre-commit
pre-commit install --hook-type pre-push
```

Or with uv: `uv tool install pre-commit` then run the same `pre-commit install --hook-type pre-push`.

The pre-push hook runs the repo lint hooks plus the full pytest suite before `git push`
(including pushes triggered from the VS Code Git UI). Lint checks always run against
`hardware-agent/` even if no files are staged.

Do not commit real secrets. For hardware-agent–only work, hooks may still touch other trees if configured globally — adjust or skip as needed.

---

## Spec pointers

- CLI contract: `[specs/001-agent-tui/contracts/cli.md](../specs/001-agent-tui/contracts/cli.md)`
- Tech stack (uv, lockfile, CI intent): `[specs/001-agent-tui/tech-stack/](../specs/001-agent-tui/tech-stack/)`

