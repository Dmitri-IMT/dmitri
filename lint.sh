#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Black =="
python -m black --check "${ROOT}/hardware-agent" || BLACK_FAIL=1
BLACK_FAIL="${BLACK_FAIL:-0}"

echo "== Ruff =="
if ! python -m ruff check "${ROOT}/hardware-agent"; then
  echo "Ruff failed — attempting auto-fix..."
  python -m ruff check --fix "${ROOT}/hardware-agent"
  python -m ruff check "${ROOT}/hardware-agent"
fi

if [[ "$BLACK_FAIL" -ne 0 ]]; then
  echo ""
  echo "Lint failed (Black)."
  exit 1
fi

echo "Lint passed."