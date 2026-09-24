#!/bin/sh
# Build an Architecture: all .deb. Python 3.12 is installed on the device
# by postinst (UV_PYTHON_INSTALL_DIR=/opt/uv-python), not inside the package.
set -eu

root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
version=$(sed -n 's/^version = "\(.*\)"/\1/p' "$root/pyproject.toml")
if [ -z "$version" ]; then
    echo "build-deb: no version in $root/pyproject.toml" >&2
    exit 1
fi

command -v dpkg-deb >/dev/null 2>&1 || {
    echo "build-deb: dpkg-deb is required" >&2
    exit 1
}

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

mkdir -p "$stage/DEBIAN" \
    "$stage/opt/dmitri-agent" \
    "$stage/usr/lib/dmitri" \
    "$stage/lib/systemd/system"

cp "$root/pyproject.toml" "$root/uv.lock" "$root/README.md" "$stage/opt/dmitri-agent/"
cp -R "$root/src" "$stage/opt/dmitri-agent/src"
cp "$root/packaging/apt-upgrade-agent" "$stage/usr/lib/dmitri/apt-upgrade-agent"
chmod 755 "$stage/usr/lib/dmitri/apt-upgrade-agent"
cp "$root/dmitri-agent.service" \
    "$root/packaging/dmitri-agent-update.service" \
    "$root/packaging/dmitri-agent-update.timer" \
    "$stage/lib/systemd/system/"

cat >"$stage/DEBIAN/control" <<EOF
Package: hardware-agent
Version: $version
Section: admin
Priority: optional
Architecture: all
Maintainer: Dmitri IMT <dev@dmitri.imt>
Depends: systemd
Recommends: nmap
Description: Dmitri scanner agent
 Installs the agent tree at /opt/dmitri-agent, dmitri-agent.service,
 and a daily apt upgrade timer.
 The device key in /etc/dmitri/agent.env is not part of this package.
EOF

cat >"$stage/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -eu
if ! command -v uv >/dev/null 2>&1; then
    echo "hardware-agent: uv is not on PATH" >&2
    exit 1
fi
mkdir -p /var/lib/dmitri /opt/uv-python
env HOME=/root UV_PYTHON_INSTALL_DIR=/opt/uv-python uv sync --project /opt/dmitri-agent
if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload
    systemctl enable dmitri-agent.service dmitri-agent-update.timer
    systemctl start dmitri-agent-update.timer || true
    # Run the new tree now. Before provisioning writes DEVICE_ID the unit
    # cannot start, so provision-pi.sh starts it after registration.
    if grep -q '^DEVICE_ID=' /etc/dmitri/agent.env 2>/dev/null; then
        systemctl restart dmitri-agent.service
    fi
fi
EOF
chmod 755 "$stage/DEBIAN/postinst"

out=${1:-"$root/dist/hardware-agent_${version}_all.deb"}
mkdir -p "$(dirname "$out")"
dpkg-deb --root-owner-group --build "$stage" "$out"
echo "$out"
