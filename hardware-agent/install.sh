#!/usr/bin/env bash
# Agent-only install wrapper — delegates to the repo-root installer.
set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/install.sh" --agent-only "$@"
