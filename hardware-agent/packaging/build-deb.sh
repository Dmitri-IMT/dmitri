#!/bin/sh
set -eu

root=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
version=$(sed -n 's/^version = "\(.*\)"/\1/p' "$root/pyproject.toml" | tr -d '\r')
updater_version=$(tr -d '[:space:]' < "$root/packaging/updater-version")
version_pattern='^[0-9]+\.[0-9]+\.[0-9]+$'
printf '%s\n' "$version" | grep -Eq "$version_pattern" || {
    echo "build-deb: hardware-agent version must be MAJOR.MINOR.PATCH" >&2
    exit 1
}
printf '%s\n' "$updater_version" | grep -Eq "$version_pattern" || {
    echo "build-deb: updater version must be MAJOR.MINOR.PATCH" >&2
    exit 1
}

for tool in dpkg-deb uv python3 pip3; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "build-deb: $tool is required" >&2
        exit 1
    }
done
[ "$(uv --version | awk '{print $2}')" = 0.11.20 ] || {
    echo "build-deb: uv 0.11.20 is required" >&2
    exit 1
}
cross_arm64=false
if [ "$(uname -m)" != aarch64 ]; then
    [ "${DIMITRI_BUILD_ARM64_CROSS:-0}" = 1 ] && [ "$(uname -s)" = Linux ] || {
        echo "build-deb: use Linux arm64, or explicitly set DIMITRI_BUILD_ARM64_CROSS=1" >&2
        exit 1
    }
    cross_arm64=true
fi
[ "$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')" = 3.12 ] || {
    echo "build-deb: Python 3.12 is required to select locked runtime artifacts" >&2
    exit 1
}

agent_deb_version="${version}-1"
updater_deb_version="${updater_version}-1"
# Ownership moved out of the legacy agent at 1.0.5; keep this cutover stable.
updater_transfer_cutoff=1.0.5-1
out=${1:-"$root/dist/hardware-agent_${agent_deb_version}_arm64.deb"}
updater_out=${2:-"$(dirname "$out")/hardware-agent-updater_${updater_deb_version}_all.deb"}
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT HUP INT TERM
mkdir -p "$stage/agent/DEBIAN" "$stage/updater/DEBIAN"

agent_root=$stage/agent
updater_root=$stage/updater
mkdir -p "$agent_root/opt/dmitri-agent" \
    "$agent_root/lib/systemd/system" \
    "$updater_root/usr/lib/dmitri" \
    "$updater_root/lib/systemd/system"

export UV_PYTHON_DOWNLOADS=never
export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-0}
uv export --locked --no-dev --no-emit-project --format requirements.txt \
    --output-file "$stage/runtime-requirements.txt" --project "$root"
mkdir -p "$agent_root/opt/dmitri-agent/wheelhouse" "$stage/wheels"
uv build --wheel --out-dir "$stage/wheels" --project "$root"
set -- "$stage"/wheels/hardware_agent-*.whl
[ -f "$1" ] || { echo "build-deb: application wheel was not built" >&2; exit 1; }
cp "$1" "$agent_root/opt/dmitri-agent/"
cp "$stage/runtime-requirements.txt" \
    "$agent_root/opt/dmitri-agent/runtime-requirements.txt"
if [ "$cross_arm64" = true ]; then
    pip3 download --require-hashes --only-binary=:all: \
        --platform manylinux_2_34_aarch64 \
        --platform manylinux_2_28_aarch64 \
        --platform manylinux2014_aarch64 \
        --implementation cp --python-version 3.12 \
        --abi cp312 --abi abi3 --abi none \
        --dest "$agent_root/opt/dmitri-agent/wheelhouse" \
        -r "$stage/runtime-requirements.txt"
else
    pip3 download --require-hashes --only-binary=:all: \
        --dest "$agent_root/opt/dmitri-agent/wheelhouse" \
        -r "$stage/runtime-requirements.txt"
fi
cp -R "$root/src" "$agent_root/opt/dmitri-agent/src"
cp "$root/README.md" "$agent_root/opt/dmitri-agent/README.md"
cp "$root/dmitri-agent.service" "$agent_root/lib/systemd/system/"

cp "$root/packaging/updater.py" "$updater_root/usr/lib/dmitri/updater.py"
cp "$root/src/agent/transport/signing.py" \
    "$updater_root/usr/lib/dmitri/device_signing.py"
cp "$root/packaging/apt-upgrade-agent" \
    "$updater_root/usr/lib/dmitri/apt-upgrade-agent"
tr -d '\r' < "$root/packaging/scan-lock-path" \
    > "$updater_root/usr/lib/dmitri/scan-lock-path"
cp "$root/packaging/dmitri-agent-update.service" \
    "$root/packaging/dmitri-agent-update.timer" \
    "$root/packaging/dmitri-agent-update-check.service" \
    "$updater_root/lib/systemd/system/"
chmod 755 "$updater_root/usr/lib/dmitri/updater.py" \
    "$updater_root/usr/lib/dmitri/apt-upgrade-agent"

cat >"$agent_root/DEBIAN/control" <<EOF
Package: hardware-agent
Version: $agent_deb_version
Section: admin
Priority: optional
Architecture: arm64
Maintainer: Dmitri IMT <dev@dmitri.imt>
Depends: systemd, hardware-agent-updater (>= $updater_deb_version)
Recommends: nmap
Description: Dmitri scanner agent
 Installs the offline agent wheel and its hash-pinned arm64 dependency wheelhouse.
 The device key in /etc/dmitri/agent.env is not part of this package.
EOF

cat >"$agent_root/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -eu
exec 9>&- 9<&-
python=/opt/uv-python/bin/python
uv=/usr/local/bin/uv
agent=/opt/dmitri-agent
[ -x "$python" ] || { echo "hardware-agent: prepared Python 3.12 is required" >&2; exit 1; }
[ -x "$uv" ] || { echo "hardware-agent: prepared uv is required at /usr/local/bin/uv" >&2; exit 1; }
[ "$("$uv" --version | awk '{print $2}')" = 0.11.20 ] || { echo "hardware-agent: pinned uv 0.11.20 is required" >&2; exit 1; }
"$python" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)' \
    || { echo "hardware-agent: /opt/uv-python must provide Python 3.12" >&2; exit 1; }
test -d "$agent/wheelhouse" || { echo "hardware-agent: wheelhouse is missing" >&2; exit 1; }
test -s "$agent/runtime-requirements.txt" || { echo "hardware-agent: runtime lock is missing" >&2; exit 1; }
old="$agent/.venv.previous"
if [ -e "$old" ]; then
    echo "hardware-agent: previous runtime snapshot exists; assisted recovery is required" >&2
    exit 1
fi
completed=false
restore_runtime() {
    status=$?
    if [ "$completed" != true ]; then
        rm -rf "$agent/.venv"
        if [ -e "$old" ]; then mv "$old" "$agent/.venv"; fi
    fi
    return "$status"
}
trap restore_runtime EXIT HUP INT TERM
if [ -e "$agent/.venv" ]; then
    mv "$agent/.venv" "$old"
fi
wheel=$(find "$agent" -maxdepth 1 -type f -name 'hardware_agent-*.whl' -print -quit)
[ -n "$wheel" ] || { echo "hardware-agent: valid application wheel is missing" >&2; exit 1; }
UV_OFFLINE=1 UV_PYTHON_DOWNLOADS=never "$uv" venv --offline --python "$python" "$agent/.venv"
UV_OFFLINE=1 "$uv" pip install --offline --no-index \
    --find-links "$agent/wheelhouse" --require-hashes \
    --python "$agent/.venv/bin/python" \
    -r "$agent/runtime-requirements.txt"
UV_OFFLINE=1 "$uv" pip install --offline --no-index --no-deps \
    --python "$agent/.venv/bin/python" "$wheel"
entry="$agent/.venv/bin/dmitri"
[ -x "$entry" ] || { echo "hardware-agent: dmitri CLI entrypoint was not installed" >&2; exit 1; }
IFS= read -r shebang <"$entry"
case "$shebang" in "#!$agent/.venv/bin/python"*) ;; *)
    echo "hardware-agent: CLI entrypoint has an invalid final-path shebang: $shebang" >&2
    exit 1 ;;
esac
set +e
smoke_output=$("$entry" __dmitri_install_smoke_check__ 2>&1)
smoke_status=$?
set -e
[ "$smoke_status" -eq 2 ] && printf '%s' "$smoke_output" | grep -q 'Unknown command' || {
    echo "hardware-agent: CLI smoke check failed: $smoke_output" >&2
    exit 1
}
rm -rf "$old"
completed=true
trap - EXIT HUP INT TERM
EOF
chmod 755 "$agent_root/DEBIAN/postinst"

cat >"$updater_root/DEBIAN/control" <<EOF
Package: hardware-agent-updater
Version: $updater_deb_version
Section: admin
Priority: optional
Architecture: all
Maintainer: Dmitri IMT <dev@dmitri.imt>
Depends: apt, ca-certificates, systemd, python3 (>= 3.11), python3-cryptography
Breaks: hardware-agent (<< $updater_transfer_cutoff)
Replaces: hardware-agent (<< $updater_transfer_cutoff)
Description: Dmitri independent agent update supervisor
 Durable metadata-check supervisor and its systemd units, independent from
 the replaceable hardware-agent runtime tree.
EOF

cat >"$updater_root/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -eu
exec 9>&- 9<&-
lock_expected=/var/lib/dmitri/scan.lock
lock_directory=/var/lib/dmitri
lock=$(cat /usr/lib/dmitri/scan-lock-path)
[ "$lock" = "$lock_expected" ] \
    || { echo "hardware-agent-updater: unsafe or non-canonical lock path" >&2; exit 1; }
[ "$(readlink -f "$lock_directory")" = "$lock_directory" ] \
    || { echo "hardware-agent-updater: lock directory is not canonical" >&2; exit 1; }
mkdir -p "$lock_directory" /var/lib/dmitri/updates
[ ! -L "$lock_expected" ] \
    || { echo "hardware-agent-updater: scan lock must not be a symbolic link" >&2; exit 1; }
lock=$lock_expected
if [ ! -e "$lock" ]; then
    (umask 022; set -C; : >"$lock") || [ -e "$lock" ]
fi
[ ! -L "$lock" ] \
    || { echo "hardware-agent-updater: scan lock must not be a symbolic link" >&2; exit 1; }
chmod 644 "$lock"
EOF
chmod 755 "$updater_root/DEBIAN/postinst"

for tree in "$agent_root" "$updater_root"; do
    find "$tree" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
done
mkdir -p "$(dirname "$out")" "$(dirname "$updater_out")"
build_immutable() {
    tree=$1
    output=$2
    temporary="$output.tmp.$$"
    dpkg-deb --root-owner-group --build "$tree" "$temporary"
    if [ -e "$output" ]; then
        old_hash=$(sha256sum "$output" | cut -d ' ' -f 1)
        new_hash=$(sha256sum "$temporary" | cut -d ' ' -f 1)
        rm -f "$temporary"
        [ "$old_hash" = "$new_hash" ] || {
            echo "build-deb: refusing different bytes for existing package identity: $output" >&2
            return 1
        }
    else
        mv "$temporary" "$output"
    fi
}
build_immutable "$agent_root" "$out"
build_immutable "$updater_root" "$updater_out"
printf '%s\n%s\n' "$out" "$updater_out"
