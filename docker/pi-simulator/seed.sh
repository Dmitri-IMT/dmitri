#!/bin/sh
set -eu

bootstrap=$(uv run --frozen backend-bootstrap-org --org-name sim --email "$SIM_ADMIN_EMAIL")
org_id=$(printf '%s\n' "$bootstrap" | sed -n 's/^org_id=//p')
invite_token=$(printf '%s\n' "$bootstrap" | sed -n 's/^invite_token=//p')

INVITE_TOKEN="$invite_token" python - <<'PY'
import json
import os
import urllib.request

request = urllib.request.Request(
    os.environ["BACKEND_URL"] + "/api/v1/invites/accept",
    data=json.dumps(
        {
            "token": os.environ["INVITE_TOKEN"],
            "password": os.environ["SIM_ADMIN_PASSWORD"],
        }
    ).encode(),
    headers={"Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(request) as response:
        if response.status != 201:
            raise SystemExit(f"invite accept returned {response.status}")
except urllib.error.HTTPError as error:
    raise SystemExit(f"invite accept returned {error.code}: {error.read().decode()}")
PY

provision=$(uv run --frozen backend-provision-agent \
    --org-id "$org_id" --display-name sim-pi --generate)
agent_id=$(printf '%s\n' "$provision" | sed -n 's/^agent_id=//p')
private_key=$(printf '%s\n' "$provision" | sed -n 's/^private_key=//p')

install -m600 /dev/null /shared/agent.env
cat >/shared/agent.env <<EOF
BACKEND_URL=$BACKEND_URL
DEVICE_ID=$agent_id
DEVICE_PRIVATE_KEY=$private_key
EOF
