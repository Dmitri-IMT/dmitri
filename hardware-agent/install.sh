#!/usr/bin/env bash
# Install Python dependencies with uv. Does NOT install nmap — see docs/DEV-SETUP.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is required. Install: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

uv sync "$@"

if ! command -v nmap >/dev/null 2>&1; then
  echo "warning: nmap not found on PATH. Install nmap before running scans (see ../docs/DEV-SETUP.md from this directory)." >&2
fi

echo "ok: dependencies synced under ${ROOT}/.venv (use: uv run ... from this directory)"
