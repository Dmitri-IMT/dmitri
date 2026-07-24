#!/usr/bin/env bash
#
# Bring up the local Postgres that the backend test suite needs, and tidy Docker.
#
#   ./database.sh                clean + set up
#   ./database.sh --test         ... then run the backend suite against it
#   ./database.sh --no-clean     skip the Docker cleanup
#   ./database.sh --deep-clean   also remove unused Supabase images (see below)
#
# Idempotent: safe to re-run. Never deletes Docker volumes, so the local database
# survives. Alembic is the sole schema owner - this script never runs
# `supabase db reset|push|migration`; conftest.py migrates to head itself.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

CONFIG="$ROOT/supabase/config.toml"
DB_NAME="dmitri_test"   # conftest.py aborts unless the database is named exactly this
RUN_TESTS=0
DO_CLEAN=1
DEEP_CLEAN=0

usage() {
  cat <<'USAGE'
Bring up the local Postgres that the backend test suite needs, and tidy Docker.

  ./database.sh                clean + set up
  ./database.sh --test         ... then run the backend suite against it
  ./database.sh --no-clean     skip the Docker cleanup
  ./database.sh --deep-clean   also remove unused Supabase images

By default the cleanup leaves the Supabase CLI's own images alone. `supabase start`
re-pulls its full image set even for services disabled in config.toml (imgproxy,
pooler), so deleting them just means downloading them again on the next start.
--deep-clean removes them anyway, at the cost of that re-pull.

Idempotent, and never deletes Docker volumes - the local database survives.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --test) RUN_TESTS=1 ;;
    --no-clean) DO_CLEAN=0 ;;
    --deep-clean) DEEP_CLEAN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

[[ -f "$CONFIG" ]] || { echo "Not found: $CONFIG" >&2; exit 1; }

# Read these from config.toml rather than hardcoding, so the script keeps working
# if the project id or port is changed there.
PROJECT="$(awk -F'"' '/^project_id/ {print $2; exit}' "$CONFIG")"
PORT="$(awk '/^\[db\]/{f=1;next} /^\[/{f=0} f && /^port[[:space:]]*=/{print $3; exit}' "$CONFIG")"
DB_CONTAINER="supabase_db_${PROJECT}"
DATABASE_URL_TEST="postgresql+psycopg://postgres:postgres@127.0.0.1:${PORT}/${DB_NAME}"

echo "== Docker daemon =="
if ! docker info >/dev/null 2>&1; then
  if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "Starting Docker Desktop..."
    open -a Docker
  else
    echo "Docker daemon is not running - start it and re-run." >&2
    exit 1
  fi
  for _ in $(seq 1 90); do
    docker info >/dev/null 2>&1 && break
    sleep 2
  done
  docker info >/dev/null 2>&1 || { echo "Docker did not come up in 180s." >&2; exit 1; }
fi
echo "Docker is up."

echo ""
echo "== Supabase stack =="
if [[ -n "$(docker ps -q -f "name=^${DB_CONTAINER}$")" ]]; then
  echo "Already running."
else
  # `supabase start` refuses to run if the CLI still thinks the stack is up while
  # a container has actually exited. A stop first clears that stale bookkeeping;
  # without --no-backup it leaves the data volume intact.
  supabase stop >/dev/null 2>&1 || true
  supabase start
fi

echo ""
echo "== Test database =="
for _ in $(seq 1 30); do
  docker exec "$DB_CONTAINER" pg_isready -U postgres -q && break
  sleep 1
done
docker exec "$DB_CONTAINER" pg_isready -U postgres -q \
  || { echo "Postgres in $DB_CONTAINER never became ready." >&2; exit 1; }

if [[ -n "$(docker exec "$DB_CONTAINER" psql -U postgres -tAc \
      "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'")" ]]; then
  echo "Database '${DB_NAME}' already exists."
else
  docker exec "$DB_CONTAINER" psql -U postgres -c "CREATE DATABASE ${DB_NAME}"
  echo "Created database '${DB_NAME}'."
fi

if [[ "$DO_CLEAN" -eq 1 ]]; then
  echo ""
  echo "== Docker cleanup =="
  # Deliberately runs *after* the stack is up, so every image the running stack
  # needs is referenced by a container and therefore protected. Doing this first
  # would delete the whole Supabase image set on a machine whose containers had
  # been removed, forcing a multi-GB re-pull.
  #
  # Only images no container references at all are removed. Volumes are never
  # touched - that would destroy the local database.
  #
  # Supabase's own images are skipped unless --deep-clean: `supabase start` pulls
  # its whole image set even for services disabled in config.toml (imgproxy,
  # pooler), so removing them just triggers a re-download on the next start.
  removed=0
  skipped=0
  supabase_prefix=""
  if [[ "$DEEP_CLEAN" -eq 0 ]]; then
    supabase_prefix="$(docker inspect "$DB_CONTAINER" --format '{{.Config.Image}}' \
      2>/dev/null | sed 's#/[^/]*$#/#')"
  fi

  while read -r image; do
    [[ -z "$image" || "$image" == *"<none>"* ]] && continue
    [[ -n "$(docker ps -aq --filter "ancestor=${image}")" ]] && continue
    if [[ -n "$supabase_prefix" && "$image" == "$supabase_prefix"* ]]; then
      echo "Keeping (Supabase would re-pull it): $image"
      skipped=$((skipped + 1))
      continue
    fi
    echo "Removing unused image: $image"
    docker rmi "$image" >/dev/null && removed=$((removed + 1)) || true
  done < <(docker images --format '{{.Repository}}:{{.Tag}}')

  while read -r id; do
    [[ -z "$id" ]] && continue
    echo "Removing dangling image: $id"
    docker rmi "$id" >/dev/null && removed=$((removed + 1)) || true
  done < <(docker images -f dangling=true -q)

  if [[ "$removed" -eq 0 && "$skipped" -eq 0 ]]; then
    echo "Nothing to remove - every image is in use."
  else
    echo "Removed ${removed} image(s); kept ${skipped} Supabase image(s)."
    [[ "$skipped" -gt 0 ]] && echo "Use --deep-clean to remove those too."
  fi
fi

echo ""
echo "== Ready =="
echo "DATABASE_URL_TEST=${DATABASE_URL_TEST}"

if [[ "$RUN_TESTS" -eq 1 ]]; then
  echo ""
  echo "== Backend suite =="
  cd "$ROOT/backend"
  DATABASE_URL_TEST="$DATABASE_URL_TEST" uv run pytest -q
else
  echo ""
  echo "Run the suite with:"
  echo "  cd backend && DATABASE_URL_TEST=\"${DATABASE_URL_TEST}\" uv run pytest"
  echo "Or re-run this script with --test."
fi
