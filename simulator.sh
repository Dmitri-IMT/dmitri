#!/usr/bin/env bash
#
# Start a local "Pi": the real `dmitri agent` daemon in a container, scanning a real
# Samba target and uploading to a local backend.
#
#   ./simulator.sh                        start (no-op if already running)
#   ./simulator.sh scan [mode] [subnet]   enqueue a scan; defaults nspi 172.31.7.0/24
#   ./simulator.sh lab-start              start the isolated targeted lab project
#   ./simulator.sh lab-scan              enqueue one extensive scan of the isolated lab
#   ./simulator.sh lab-verify <scan-id>  verify and print one persisted lab scan
#   ./simulator.sh lab-stop               remove only the targeted lab containers/volumes
#   ./simulator.sh stop                   down -v; nothing survives
#   ./simulator.sh logs [args...]         passthrough to `docker compose logs`
#   ./simulator.sh --nspi [verb]          connect-only against the deployed
#                                         environment; `scan` is refused
#
# There is deliberately no simulator.ps1. install/database/lint each have a PowerShell
# twin; this one does not, because the simulator is a Linux-container harness whose
# Windows path nobody will exercise, and an untested .ps1 implies a promise we are not
# keeping. This script is the registered exception to docs-sync's "every root script is
# a .sh/.ps1 mirror pair; never patch one without the other" rule. A twin is a small
# follow-up if a Windows developer appears.
#
# The API takes port 8000: stop a hand-run backend before starting this.
set -euo pipefail

# Git Bash rewrites container paths such as /verify_targeted_scan.py into Windows
# paths before docker can pass them to the Linux container.
if [[ -n "${MSYSTEM:-}" ]]; then
  export MSYS_NO_PATHCONV=1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

usage() {
  cat <<'USAGE'
Run a containerized Pi against a local backend.

  ./simulator.sh                        start (no-op if already running)
  ./simulator.sh scan [mode] [subnet]   enqueue a scan; defaults nspi 172.31.7.0/24
  ./simulator.sh lab-start              start the isolated targeted lab project
  ./simulator.sh lab-scan               enqueue one extensive scan of 172.31.13.0/29
  ./simulator.sh lab-verify <scan-id>   verify one persisted targeted lab result
  ./simulator.sh lab-stop               remove the targeted lab containers/volumes
  ./simulator.sh stop                   down -v; nothing survives
  ./simulator.sh logs [args...]         passthrough to `docker compose logs`
  ./simulator.sh --nspi [verb]          connect-only against the deployed environment

State is ephemeral: scans accumulate while it runs, and a stop wipes everything. A
start against a running stack changes nothing, so typing it twice cannot destroy a
session's scans - use `stop` then start to reset.

--nspi points the agent at the deployed backend using BACKEND_URL, DEVICE_ID and
DEVICE_PRIVATE_KEY from docker/pi-simulator/.env. It refuses `scan`: the agent runs on
this laptop, so a scan would record a Docker bridge as a customer network in the one
deployed environment there is. Confirm the DEVICE_ID belongs to a throwaway org, never
the pilot org, before connecting.
USAGE
}

NSPI=0
if [[ "${1:-}" == "--nspi" ]]; then
  NSPI=1
  shift
fi

if [[ "$NSPI" -eq 1 ]]; then
  COMPOSE=(docker compose -p dmitri-sim-nspi -f docker/pi-simulator/compose.nspi.yaml)
  LAB_COMPOSE=()
else
  COMPOSE=(docker compose -f docker/pi-simulator/compose.yaml)
  LAB_COMPOSE=(env SIMULATOR_APP_SUBNET=172.31.12.0/24 docker compose --parallel 1 -p dmitri-targeted-lab-demo -f docker/pi-simulator/compose.yaml -f docker/pi-simulator/compose.lab.yaml)
fi

[[ -f docker/pi-simulator/.env ]] \
  || { echo "Not found: docker/pi-simulator/.env - copy .env.example to it." >&2; exit 1; }

case "${1:-start}" in
  start)
    if [[ -n "$("${COMPOSE[@]}" ps -q)" ]]; then
      echo "Already running - leaving it alone. Use './simulator.sh stop' to wipe it."
      exit 0
    fi
    # A cold start begins from an empty volume: seed.sh has no idempotency guard, and
    # `down -v` here clears anything a previous `docker compose stop` left behind.
    "${COMPOSE[@]}" down -v
    "${COMPOSE[@]}" up -d --build
    echo ""
    if [[ "$NSPI" -eq 0 ]]; then
      echo "Up. API on http://localhost:8000, Postgres on 55432."
    else
      echo "Up. Agent connecting to the deployed backend at" \
        "$(grep -m1 '^BACKEND_URL=' docker/pi-simulator/.env | cut -d= -f2-)." \
        "No local API or database in this mode."
    fi
    ;;

  lab-start)
    if [[ "$NSPI" -eq 1 ]]; then
      echo "lab-start is available only in local simulator mode." >&2
      exit 1
    fi
    # Reconcile this isolated project on every start so changed image/network
    # settings take effect without deleting its database volume or old simulator data.
    "${LAB_COMPOSE[@]}" up -d --build
    echo "Targeted lab is up. Local API on http://localhost:8000."
    ;;

  scan|lab-scan)
    if [[ "$NSPI" -eq 1 ]]; then
      echo "scan is refused in --nspi mode: the agent runs on this laptop, so it would" >&2
      echo "record a Docker bridge as a customer network in the deployed environment." >&2
      exit 1
    fi
    if [[ "$1" == "lab-scan" ]]; then
      COMPOSE=("${LAB_COMPOSE[@]}")
      SCAN_MODE="extensive"
      SUBNET="172.31.13.0/29"
    else
      SCAN_MODE="${2:-nspi}"
      SUBNET="${3:-172.31.7.0/24}"
    fi
    # Run inside `api`, which already holds BACKEND_URL and the seeded admin
    # credentials, so the host needs no curl, jq or Python of its own.
    "${COMPOSE[@]}" exec -T -e SCAN_MODE="$SCAN_MODE" -e SUBNET="$SUBNET" api python - <<'PY'
import json
import os
import urllib.request

base = os.environ["BACKEND_URL"]


def call(path, payload=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        base + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers=headers,
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


token = call(
    "/api/v1/auth/login",
    {
        "email": os.environ["SIM_ADMIN_EMAIL"],
        "password": os.environ["SIM_ADMIN_PASSWORD"],
    },
)["access_token"]
agent_id = call("/api/v1/agents", token=token)["data"][0]["agent_id"]
command = call(
    f"/api/v1/agents/{agent_id}/commands",
    {"scan_mode": os.environ["SCAN_MODE"], "subnet": os.environ["SUBNET"]},
    token=token,
)
print("command_id=" + command["command_id"])
if command.get("scan_id"):
    print("scan_id=" + command["scan_id"])
PY
    ;;

  lab-verify)
    if [[ "$NSPI" -eq 1 ]]; then
      echo "lab-verify is available only in local simulator mode." >&2
      exit 1
    fi
    SCAN_ID="${2:-}"
    [[ -n "$SCAN_ID" ]] || { echo "usage: ./simulator.sh lab-verify <scan-id>" >&2; exit 2; }
    "${LAB_COMPOSE[@]}" exec -T api python /verify_targeted_scan.py "$SCAN_ID"
    ;;

  lab-stop)
    if [[ "$NSPI" -eq 1 ]]; then
      echo "lab-stop is available only in local simulator mode." >&2
      exit 1
    fi
    "${LAB_COMPOSE[@]}" down -v
    ;;

  stop)
    "${COMPOSE[@]}" down -v
    ;;

  logs)
    shift
    "${COMPOSE[@]}" logs "$@"
    ;;

  -h|--help)
    usage
    ;;

  *)
    echo "Unknown command: $1 (try --help)" >&2
    exit 2
    ;;
esac
