#!/bin/sh
# Install the hardware-agent package on this Pi and leave it connected to the
# deployed backend. Run it on the Pi, from a checkout of the repo, as root.
# The key, the login, and the registration are `dmitri provision`
# (agent/transport/provision.py); this script only installs and starts.
set -eu

die() {
    echo "provision-pi: $*" >&2
    exit 1
}

[ "$(id -u)" -eq 0 ] || die "run as root"

agent_src=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
env_file=/etc/dmitri/agent.env

# Checked before the install: the package's postinst restarts the agent only
# when DEVICE_ID is already set.
provisioned=false
if [ -f "$env_file" ] && grep -q '^DEVICE_ID=' "$env_file"; then
    provisioned=true
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y nmap ca-certificates curl

# The package's postinst runs `uv sync`, so uv must be on PATH first.
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | env HOME=/root UV_INSTALL_DIR=/usr/local/bin sh
fi
command -v uv >/dev/null 2>&1 || die "uv install failed"

# A hand-installed copy of the unit in /etc overrides the packaged one.
if [ -f /etc/systemd/system/dmitri-agent.service ]; then
    systemctl disable dmitri-agent.service || true
    rm -f /etc/systemd/system/dmitri-agent.service
fi
# A hand-copied tree (before the package) can hold modules the package
# no longer ships. dpkg does not remove files it does not own.
if ! dpkg -s hardware-agent >/dev/null 2>&1; then
    rm -rf /opt/dmitri-agent/src /opt/dmitri-agent/dmitri-agent.service
fi

deb_dir=$(mktemp -d)
sh "$agent_src/packaging/build-deb.sh" "$deb_dir/hardware-agent.deb" >/dev/null \
    || die "package build failed"
dpkg -i "$deb_dir/hardware-agent.deb" || die "package install failed"
rm -rf "$deb_dir"

if [ "$provisioned" = true ]; then
    echo "This Pi is already provisioned. The package restarted the agent."
else
    /opt/dmitri-agent/.venv/bin/dmitri provision || die "registration failed"
    systemctl restart dmitri-agent
fi

# Read only the journal of the current process. An older run's
# "connected" line must not count.
i=0
while [ "$i" -lt 30 ]; do
    invocation=$(systemctl show -p InvocationID --value dmitri-agent)
    if [ -n "$invocation" ] \
        && journalctl --no-pager _SYSTEMD_INVOCATION_ID="$invocation" \
            | grep -q "command channel connected"; then
        echo "Ready. command channel connected."
        exit 0
    fi
    i=$((i + 1))
    sleep 2
done
die "dmitri-agent did not connect. See journalctl -u dmitri-agent"
