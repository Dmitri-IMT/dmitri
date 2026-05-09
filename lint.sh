#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Black =="
python -m black --check "${ROOT}/hardware-agent" || BLACK_FAIL=1
BLACK_FAIL="${BLACK_FAIL:-0}"

echo "== Ruff =="
python -m ruff check "${ROOT}/hardware-agent" || RUFF_FAIL=1
RUFF_FAIL="${RUFF_FAIL:-0}"

if [[ "$BLACK_FAIL" -ne 0 || "$RUFF_FAIL" -ne 0 ]]; then
  echo ""
  echo "Lint failed."
  exit 1
fi

echo "Lint passed."