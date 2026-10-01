#!/usr/bin/env bash
# Bootstrap Dmitri dev environment (hardware-agent + backend + frontend + local Supabase
# when available).
# Usage: ./install.sh [--agent-only] [--skip-verify] [--hooks]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ONLY=0
SKIP_VERIFY=0
INSTALL_HOOKS=0
INFRA_OK=0
FRONTEND_OK=0
TARGETED_TOOLS_OK=0

# Read the project id and port from config.toml rather than hardcoding them, so this
# keeps working if either is changed there. Same parse as database.sh.
SUPABASE_CONFIG="${REPO_ROOT}/supabase/config.toml"
SUPABASE_PROJECT="dmitri"
SUPABASE_DB_PORT="54322"
if [[ -f "$SUPABASE_CONFIG" ]]; then
  SUPABASE_PROJECT="$(awk -F'"' '/^project_id/ {print $2; exit}' "$SUPABASE_CONFIG")"
  SUPABASE_DB_PORT="$(awk '/^\[db\]/{f=1;next} /^\[/{f=0} f && /^port[[:space:]]*=/{print $3; exit}' "$SUPABASE_CONFIG")"
fi
SUPABASE_DB_CONTAINER="supabase_db_${SUPABASE_PROJECT}"
LOCAL_DB_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:${SUPABASE_DB_PORT}/postgres"
TEST_DB_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:${SUPABASE_DB_PORT}/dmitri_test"

info() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
note() { printf 'note: %s\n' "$*"; }

usage() {
  cat <<'EOF'
Usage: ./install.sh [OPTIONS]

Bootstrap Dmitri: uv + nmap, Python deps (with dev extras), backend/.env,
frontend npm deps + frontend/.env, and local Supabase/migrations when Docker +
Supabase CLI are available (Docker Desktop is started for you if installed).

Options:
  --agent-only    Skip backend infra and frontend; Pi-friendly
  --skip-verify   Skip post-install pytest / vitest smoke checks
  --hooks         Install pre-commit pre-push hooks
  -h, --help      Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent-only) AGENT_ONLY=1 ;;
    --skip-verify) SKIP_VERIFY=1 ;;
    --hooks) INSTALL_HOOKS=1 ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    info "uv already installed ($(uv --version))"
    return 0
  fi

  info "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh

  for bindir in "${HOME}/.local/bin" "${HOME}/.cargo/bin"; do
    if [[ -d "$bindir" ]]; then
      export PATH="$bindir:$PATH"
    fi
  done

  if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv install finished but uv is not on PATH. Restart your shell and re-run ./install.sh" >&2
    exit 1
  fi
  info "uv installed ($(uv --version))"
}

USER_BIN_DIR="${HOME}/.local/bin"

ensure_user_bin_on_path() {
  mkdir -p "$USER_BIN_DIR"
  if [[ ":${PATH}:" != *":${USER_BIN_DIR}:"* ]]; then
    export PATH="${USER_BIN_DIR}:${PATH}"
  fi

  local profile=""
  case "$(basename "${SHELL:-}")" in
    zsh) profile="${HOME}/.zprofile" ;;
    bash)
      if [[ -f "${HOME}/.bash_profile" ]]; then
        profile="${HOME}/.bash_profile"
      else
        profile="${HOME}/.bashrc"
      fi
      ;;
  esac

  if [[ -z "$profile" ]]; then
    note "Add ${USER_BIN_DIR} to your PATH to run dmitri from anywhere"
    return 0
  fi

  if [[ -f "$profile" ]] && grep -q '\.local/bin' "$profile" 2>/dev/null; then
    return 0
  fi

  {
    printf '\n# Added by Dmitri install.sh\n'
    printf 'export PATH="$HOME/.local/bin:$PATH"\n'
  } >>"$profile"
  info "Added ~/.local/bin to PATH in ${profile}"
  note "Restart your terminal or run: source ${profile}"
}

install_dmitri_cli() {
  local agent_dir="${REPO_ROOT}/hardware-agent"
  local wrapper="${USER_BIN_DIR}/dmitri"

  ensure_user_bin_on_path

  cat >"$wrapper" <<EOF
#!/usr/bin/env bash
# Dmitri TUI launcher — installed by ${REPO_ROOT}/install.sh
set -euo pipefail
exec uv run --directory "${agent_dir}" dmitri "\$@"
EOF
  chmod +x "$wrapper"
  info "Installed dmitri launcher at ${wrapper}"
}

ensure_nmap() {
  if command -v nmap >/dev/null 2>&1; then
    info "nmap already installed ($(nmap --version | head -n1))"
    return 0
  fi

  info "Installing nmap..."
  case "$(uname -s)" in
    Darwin)
      if ! command -v brew >/dev/null 2>&1; then
        echo "error: Homebrew is required to auto-install nmap on macOS. Install from https://brew.sh then re-run." >&2
        exit 1
      fi
      brew install nmap
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y nmap
      elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y nmap
      else
        warn "Could not auto-install nmap on this Linux distro."
        note "Install nmap manually — see docs/DEV-SETUP.md"
        return 0
      fi
      ;;
    *)
      warn "Unsupported OS for automatic nmap install."
      note "Install nmap manually — see docs/DEV-SETUP.md"
      return 0
      ;;
  esac

  if command -v nmap >/dev/null 2>&1; then
    info "nmap installed ($(nmap --version | head -n1))"
  else
    warn "nmap still not on PATH after install attempt."
  fi
}

sync_python_deps() {
  info "Syncing hardware-agent dependencies (with dev extras)..."
  (cd "${REPO_ROOT}/hardware-agent" && uv sync --extra dev)

  if [[ "$AGENT_ONLY" -eq 0 ]]; then
    info "Syncing backend dependencies (with dev extras)..."
    (cd "${REPO_ROOT}/backend" && uv sync --extra dev)
  fi
}

provision_targeted_tools() {
  # The external targeted tools are required for complete scans on the Pi.
  if [[ "$AGENT_ONLY" -eq 0 ]]; then
    return 0
  fi
  if [[ "$(uname -s)" != "Linux" ]]; then
    note "Targeted-tool provisioning is supported on Raspberry Pi Linux only; use the Pi provisioner on armhf/arm64."
    return 0
  fi

  local arch
  if command -v dpkg >/dev/null 2>&1; then
    arch="$(dpkg --print-architecture)"
  else
    arch="$(uname -m)"
  fi
  case "$arch" in
    armhf | arm64 | armv6l | armv7l | aarch64) ;;
    *) note "Targeted-tool provisioning is supported on Raspberry Pi armhf/arm64 only; skipping on ${arch}."; return 0 ;;
  esac

  local provisioner="${REPO_ROOT}/hardware-agent/scripts/provision-targeted-tools.sh"
  if [[ ! -x "$provisioner" ]]; then
    echo "error: Targeted-tool provisioner is missing or not executable: ${provisioner}" >&2
    exit 1
  fi

  info "Provisioning pinned service-targeted tools (Raspberry Pi Linux)..."
  if [[ "${EUID}" -eq 0 ]]; then
    "$provisioner" || { echo "error: Targeted-tool provisioning failed" >&2; exit 1; }
  elif ! command -v sudo >/dev/null 2>&1; then
    echo "error: Targeted-tool provisioning needs sudo: ${provisioner}" >&2
    exit 1
  else
    sudo "$provisioner" || { echo "error: Targeted-tool provisioning failed" >&2; exit 1; }
  fi
  TARGETED_TOOLS_OK=1
}

seed_backend_env() {
  if [[ "$AGENT_ONLY" -eq 1 ]]; then
    return 0
  fi

  local env_file="${REPO_ROOT}/backend/.env"
  local example="${REPO_ROOT}/backend/.env.example"
  if [[ -f "$env_file" ]]; then
    note "backend/.env already exists — not overwriting"
    return 0
  fi
  if [[ ! -f "$example" ]]; then
    warn "backend/.env.example missing — skipping .env seed"
    return 0
  fi
  cp -n "$example" "$env_file"
  info "Created backend/.env from backend/.env.example"
}

ensure_node() {
  if ! command -v node >/dev/null 2>&1; then
    warn "Node.js not found — skipping frontend setup."
    cat <<'EOF'

Install Node 22.x, then re-run ./install.sh:
  nvm:     nvm install 22 && nvm use 22
  macOS:   brew install node@22
  Linux:   https://nodejs.org/en/download/package-manager

EOF
    return 1
  fi

  # frontend/package.json pins engines.node to 22.x. npm does not enforce it by
  # default, so a mismatch is a warning here rather than a hard stop.
  local major
  major="$(node -p 'process.versions.node.split(".")[0]')"
  if [[ "$major" != "22" ]]; then
    warn "Node $(node --version) found; frontend/package.json pins engines.node to 22.x."
    note "Continuing anyway — switch with: nvm use 22"
  else
    info "node $(node --version)"
  fi
}

setup_frontend() {
  if [[ "$AGENT_ONLY" -eq 1 ]]; then
    return 0
  fi

  ensure_node || return 0

  info "Installing frontend dependencies..."
  (cd "${REPO_ROOT}/frontend" && npm install)

  local env_file="${REPO_ROOT}/frontend/.env"
  local example="${REPO_ROOT}/frontend/.env.example"
  if [[ -f "$env_file" ]]; then
    note "frontend/.env already exists — not overwriting"
  elif [[ ! -f "$example" ]]; then
    warn "frontend/.env.example missing — skipping .env seed"
  else
    cp -n "$example" "$env_file"
    info "Created frontend/.env from frontend/.env.example"
  fi

  FRONTEND_OK=1
}

# Docker being installed but idle is the normal state on a dev machine, so start it
# rather than treating it as missing. Mirrors the wait loop in database.sh.
start_docker_daemon() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    return 1
  fi

  info "Docker is installed but not running — starting it..."
  case "$(uname -s)" in
    Darwin) open -a Docker >/dev/null 2>&1 || return 1 ;;
    Linux)
      if command -v systemctl >/dev/null 2>&1; then
        sudo systemctl start docker || return 1
      else
        warn "No systemctl — start the Docker daemon yourself and re-run."
        return 1
      fi
      ;;
    *) return 1 ;;
  esac

  for _ in $(seq 1 90); do
    if docker info >/dev/null 2>&1; then
      info "Docker is up."
      return 0
    fi
    sleep 2
  done

  warn "Docker did not come up within 180s."
  return 1
}

print_docker_instructions() {
  warn "Docker is not running or not installed — skipping Supabase and migrations."
  cat <<'EOF'

Install Docker, then re-run ./install.sh (without --agent-only):
  macOS:   https://docs.docker.com/desktop/setup/install/mac-install/
  Linux:   https://docs.docker.com/engine/install/

EOF
}

print_supabase_instructions() {
  warn "Supabase CLI not found — skipping local Postgres setup."
  cat <<'EOF'

Install the Supabase CLI, then re-run ./install.sh:
  macOS:   brew install supabase/tap/supabase
  Linux:   https://supabase.com/docs/guides/local-development/cli/getting-started
  Windows: scoop install supabase  (or see Supabase docs)

EOF
}

psql_exec() {
  docker exec "$SUPABASE_DB_CONTAINER" psql -U postgres "$@"
}

# `supabase start` returning does not mean Postgres accepts connections yet — without
# this the first psql call below can lose the race.
wait_for_postgres() {
  for _ in $(seq 1 30); do
    if docker exec "$SUPABASE_DB_CONTAINER" pg_isready -U postgres -q; then
      return 0
    fi
    sleep 1
  done
  warn "Postgres in ${SUPABASE_DB_CONTAINER} never became ready."
  return 1
}

recreate_dmitri_test_db() {
  info "Recreating database dmitri_test for isolated backend tests..."
  psql_exec -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'dmitri_test' AND pid <> pg_backend_pid();" \
    >/dev/null 2>&1 || true
  psql_exec -c "DROP DATABASE IF EXISTS dmitri_test;"
  psql_exec -c "CREATE DATABASE dmitri_test;"
}

dmitri_runtime_role_exists() {
  psql_exec -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'dmitri_runtime'" 2>/dev/null || true
}

alembic_on_postgres() {
  (
    cd "${REPO_ROOT}/backend"
    export DATABASE_URL_DIRECT="$LOCAL_DB_URL"
    uv run alembic "$@"
  )
}

prepare_backend_test_database() {
  recreate_dmitri_test_db
  if [[ "$(dmitri_runtime_role_exists)" == "1" ]]; then
    note "dmitri_runtime role present — resetting postgres schema before backend tests"
    alembic_on_postgres downgrade base
  fi
}

finalize_postgres_for_api() {
  info "Applying Alembic migrations on postgres for local API (DATABASE_URL_DIRECT in shell only)..."
  alembic_on_postgres upgrade head
  info "Local Postgres ready at 127.0.0.1:${SUPABASE_DB_PORT}"
}

setup_backend_infra() {
  if [[ "$AGENT_ONLY" -eq 1 ]]; then
    return 0
  fi

  if ! start_docker_daemon; then
    print_docker_instructions
    return 0
  fi

  if ! command -v supabase >/dev/null 2>&1; then
    print_supabase_instructions
    return 0
  fi

  info "Starting local Supabase stack..."
  # `supabase start` refuses to run if the CLI still thinks the stack is up while a
  # container has actually exited. A stop first clears that stale bookkeeping; without
  # --no-backup it leaves the data volume intact.
  if ! docker ps --format '{{.Names}}' | grep -qx "$SUPABASE_DB_CONTAINER"; then
    (cd "$REPO_ROOT" && supabase stop >/dev/null 2>&1) || true
  fi
  (cd "$REPO_ROOT" && supabase start)

  if ! docker ps --format '{{.Names}}' | grep -qx "$SUPABASE_DB_CONTAINER"; then
    warn "Expected container ${SUPABASE_DB_CONTAINER} not running after supabase start."
    return 0
  fi

  wait_for_postgres || return 0

  recreate_dmitri_test_db

  INFRA_OK=1
}

install_hooks() {
  if [[ "$INSTALL_HOOKS" -eq 0 ]]; then
    return 0
  fi
  info "Installing pre-commit hooks..."
  uv tool install pre-commit
  (cd "$REPO_ROOT" && pre-commit install --hook-type pre-push)
}

with_backend_env_hidden() {
  local env_file="${REPO_ROOT}/backend/.env"
  local env_backup=""
  if [[ -f "$env_file" ]]; then
    env_backup="$(mktemp "${TMPDIR:-/tmp}/dmitri-backend-env.XXXXXX")"
    mv "$env_file" "$env_backup"
  fi
  (
    cd "${REPO_ROOT}/backend"
    "$@"
  )
  local status=$?
  if [[ -n "$env_backup" ]]; then
    mv "$env_backup" "$env_file"
  fi
  return "$status"
}

run_verify() {
  if [[ "$SKIP_VERIFY" -eq 1 ]]; then
    note "Skipping verification (--skip-verify)"
    return 0
  fi

  info "Running hardware-agent tests..."
  (cd "${REPO_ROOT}/hardware-agent" && uv run pytest -q)

  if [[ "$AGENT_ONLY" -eq 1 ]]; then
    return 0
  fi

  info "Running backend tests..."
  if [[ "$INFRA_OK" -eq 1 ]]; then
    prepare_backend_test_database
    note "Temporarily hiding backend/.env so settings tests match CI (no dotenv file)"
    with_backend_env_hidden env \
      DATABASE_URL_TEST="$TEST_DB_URL" \
      uv run pytest -q
  else
    note "Running backend tests without DATABASE_URL_TEST (DB-touching tests will skip)"
    with_backend_env_hidden uv run pytest -q
  fi

  if [[ "$FRONTEND_OK" -eq 1 ]]; then
    info "Running frontend tests..."
    (cd "${REPO_ROOT}/frontend" && npm test)
  fi
}

print_next_steps() {
  cat <<EOF

Install complete.

Next steps:
  TUI:     dmitri
           cd hardware-agent && uv run dmitri
  Tests:   cd hardware-agent && uv run pytest
           cd backend && uv run pytest
EOF

  if [[ "$AGENT_ONLY" -eq 0 ]]; then
    cat <<EOF
  API:     cd backend && uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
  Worker:  cd backend && uv run python -m api.worker_main
  Health:  curl http://127.0.0.1:8000/api/v1/health
EOF
  fi

  if [[ "$FRONTEND_OK" -eq 1 ]]; then
    cat <<EOF
  Web:     cd frontend && npm run dev   (http://localhost:5173)
  CORS:    set CORS_ALLOWED_ORIGINS=http://localhost:5173 in backend/.env before using Web
  Links:   set APP_BASE_URL=http://localhost:5173 in backend/.env for local auth links
EOF
  elif [[ "$AGENT_ONLY" -eq 0 ]]; then
    cat <<EOF

Frontend was not set up (Node.js missing).
Install Node 22.x, then: cd frontend && npm install && cp .env.example .env
EOF
  fi

  if [[ "$AGENT_ONLY" -eq 0 && "$INFRA_OK" -eq 0 ]]; then
    cat <<EOF

Backend infra was not configured (Docker/Supabase missing).
Finish setup manually — see backend/README.md and docs/cloud/supabase/SETUP.md
EOF
  fi

  if [[ "$AGENT_ONLY" -eq 1 ]]; then
    if [[ "$TARGETED_TOOLS_OK" -eq 1 ]]; then
      note "Targeted service tools: provisioned and verified."
    fi
  fi

  if [[ "$INSTALL_HOOKS" -eq 0 ]]; then
    note "Optional: ./install.sh --hooks  (pre-commit pre-push)"
  fi

  note "Docs: docs/DEV-SETUP.md, backend/README.md"
  note "Optional Cursor MCP: copy .env.example to .env and set GITHUB_PAT"
}

main() {
  cd "$REPO_ROOT"
  info "Dmitri install (repo: ${REPO_ROOT})"
  ensure_uv
  ensure_nmap
  sync_python_deps
  provision_targeted_tools
  install_dmitri_cli
  seed_backend_env
  setup_frontend
  setup_backend_infra
  install_hooks
  run_verify
  if [[ "$AGENT_ONLY" -eq 0 && "$INFRA_OK" -eq 1 ]]; then
    finalize_postgres_for_api
  fi
  print_next_steps
}

main
