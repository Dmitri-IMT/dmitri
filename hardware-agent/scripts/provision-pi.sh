#!/bin/sh
# Install this Pi and leave it connected to the deployed backend.
# Run it on the Pi, from a checkout of the repo, as root.
set -eu

die() {
    echo "provision-pi: $*" >&2
    exit 1
}

prompt() {
    printf "%s" "$1"
    read -r "$2"
}

[ "$(id -u)" -eq 0 ] || die "run as root"

agent_src=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
env_file=/etc/dmitri/agent.env

if [ -f "$env_file" ] && grep -q '^DEVICE_ID=' "$env_file"; then
    echo "This Pi is already provisioned. Restarting the agent."
else
    prompt "Backend URL (https://...): " backend_url
    case "$backend_url" in
        http://*|https://*) ;;
        *) die "BACKEND_URL must start with http:// or https://" ;;
    esac
    backend_url=${backend_url%/}
    prompt "Admin email for that backend: " admin_email
    printf "Admin password: "
    stty -echo
    read -r admin_password
    stty echo
    printf "\n"
    prompt "Name for this Pi: " display_name
    [ -n "$admin_email" ] && [ -n "$admin_password" ] && [ -n "$display_name" ] \
        || die "email, password, and name are required"
    echo "The Pi joins the org of that admin account."

    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y nmap ca-certificates curl

    if ! command -v uv >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | env HOME=/root UV_INSTALL_DIR=/usr/local/bin sh
    fi
    command -v uv >/dev/null 2>&1 || die "uv install failed"

    mkdir -p /opt/dmitri-agent /var/lib/dmitri /etc/dmitri /opt/uv-python
    chmod 700 /etc/dmitri
    cp "$agent_src/pyproject.toml" "$agent_src/uv.lock" "$agent_src/README.md" \
        "$agent_src/dmitri-agent.service" /opt/dmitri-agent/
    rm -rf /opt/dmitri-agent/src
    cp -R "$agent_src/src" /opt/dmitri-agent/src
    env HOME=/root UV_PYTHON_INSTALL_DIR=/opt/uv-python \
        uv sync --project /opt/dmitri-agent \
        || die "uv sync failed"

    python=/opt/dmitri-agent/.venv/bin/python
    [ -x "$python" ] || die "uv sync did not create $python"

    if [ -f "$env_file" ] && grep -q '^DEVICE_PRIVATE_KEY=' "$env_file"; then
        public_key=$("$python" - <<'PY'
from pathlib import Path
from cryptography.hazmat.primitives import serialization as s
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

text = Path("/etc/dmitri/agent.env").read_text()
private = ""
for line in text.splitlines():
    if line.startswith("DEVICE_PRIVATE_KEY="):
        private = line.split("=", 1)[1].strip()
key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private))
print(key.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex())
PY
)
    else
        public_key=$("$python" - <<'PY'
from cryptography.hazmat.primitives import serialization as s
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

key = Ed25519PrivateKey.generate()
private_hex = key.private_bytes(
    s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption()
).hex()
public_hex = key.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw).hex()
with open("/etc/dmitri/agent.env", "w") as env:
    env.write("DEVICE_PRIVATE_KEY=" + private_hex + "\n")
print(public_hex)
PY
)
        chmod 600 "$env_file"
        chown root:root "$env_file"
    fi

    BACKEND_URL="$backend_url" \
        ADMIN_EMAIL="$admin_email" \
        ADMIN_PASSWORD="$admin_password" \
        DISPLAY_NAME="$display_name" \
        PUBLIC_KEY="$public_key" \
        "$python" - <<'PY' > /tmp/dmitri-provision-agent-id
import json
import os
import urllib.error
import urllib.request

body = json.dumps(
    {"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}
).encode()
request = urllib.request.Request(
    os.environ["BACKEND_URL"] + "/api/v1/auth/login",
    data=body,
    headers={"Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        token = json.load(response)["access_token"]
except urllib.error.HTTPError as exc:
    raise SystemExit(f"login failed: HTTP {exc.code}") from exc

body = json.dumps(
    {
        "display_name": os.environ["DISPLAY_NAME"],
        "public_key": os.environ["PUBLIC_KEY"],
    }
).encode()
request = urllib.request.Request(
    os.environ["BACKEND_URL"] + "/api/v1/agents",
    data=body,
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
    },
)
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        print(json.load(response)["agent_id"])
except urllib.error.HTTPError as exc:
    detail = exc.read().decode()
    raise SystemExit(f"register failed: HTTP {exc.code} {detail}") from exc
PY
    device_id=$(cat /tmp/dmitri-provision-agent-id)
    rm -f /tmp/dmitri-provision-agent-id
    unset admin_password ADMIN_PASSWORD

    private_line=$(grep '^DEVICE_PRIVATE_KEY=' "$env_file")
    tmp=$(mktemp)
    printf 'BACKEND_URL=%s\nDEVICE_ID=%s\n%s\n' \
        "$backend_url" "$device_id" "$private_line" >"$tmp"
    chmod 600 "$tmp"
    chown root:root "$tmp"
    mv "$tmp" "$env_file"
fi

cp /opt/dmitri-agent/dmitri-agent.service /etc/systemd/system/dmitri-agent.service
systemctl daemon-reload
systemctl enable --now dmitri-agent
systemctl restart dmitri-agent

i=0
while [ "$i" -lt 30 ]; do
    if journalctl -u dmitri-agent --no-pager | grep -q "command channel connected"; then
        echo "Ready. command channel connected."
        exit 0
    fi
    i=$((i + 1))
    sleep 2
done
die "dmitri-agent did not connect. See journalctl -u dmitri-agent"
