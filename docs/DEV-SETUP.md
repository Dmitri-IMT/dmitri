# Development setup — **hardware-agent** & **Dmitri** (TUI)

This guide covers **only** the `**hardware-agent`** Python package and the **Textual TUI** (`dmitri` / `dmitri start`).

**Not in scope right now:** Docker Compose, **backend** API, and **frontend** web app. You do not need Node.js, `npm`, or backend `.env` / `docker compose` to work on Dmitri. Those directories remain in the repo for later; when this changes, extend this doc or add a separate full-stack guide.

---

## Prerequisites

- **Git**
- **Python 3.11+** (matches `requires-python` in `hardware-agent/pyproject.toml`)
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** — required for syncing dependencies (supported path; `pip` is an unsupported escape hatch per product specs)
- **Nmap** — install on the host yourself (the repo does **not** install it via `install.sh`). It must be available for **real** scans when you run the TUI. Verify with `nmap --version`. Automated **tests** mock nmap; CI does not install it — see `[specs/001-agent-tui/tech-stack/testing-tooling.md](../specs/001-agent-tui/tech-stack/testing-tooling.md)`.

### Nmap (local runs)

- **Windows**: [Nmap download](https://nmap.org/download.html) or a package manager (e.g. Chocolatey: `choco install nmap`).
- **macOS**: `brew install nmap` or the upstream installer.
- **Debian / Ubuntu**: `sudo apt install nmap`
- **Fedora**: `sudo dnf install nmap`

---

## Install dependencies (**uv**)

From the **repository root**:

```bash
./hardware-agent/install.sh
```

Or from `**hardware-agent/**`:

```bash
cd hardware-agent
chmod +x install.sh   # Unix, if needed
./install.sh
```

The script runs `**uv sync**` in `hardware-agent/`. It does **not** install Nmap; if `nmap` is missing from `PATH`, the script prints a warning — install Nmap using the section above.

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
pre-commit install --hook-type pre-commit --hook-type pre-push
```

Or with uv: `uv tool install pre-commit` then run the same `pre-commit install --hook-type pre-commit --hook-type pre-push`.

The pre-push hook runs the repo lint hooks plus the full pytest suite before `git push`
(including pushes triggered from the VS Code Git UI).

Do not commit real secrets. For hardware-agent–only work, hooks may still touch other trees if configured globally — adjust or skip as needed.

---

## Spec pointers

- CLI contract: `[specs/001-agent-tui/contracts/cli.md](../specs/001-agent-tui/contracts/cli.md)`
- Tech stack (uv, lockfile, CI intent): `[specs/001-agent-tui/tech-stack/](../specs/001-agent-tui/tech-stack/)`

