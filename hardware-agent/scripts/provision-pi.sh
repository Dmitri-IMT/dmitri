#!/bin/sh
set -eu

die() { echo "provision-pi: $*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "run as root"
[ "$#" -eq 2 ] || die "usage: provision-pi.sh HARDWARE_AGENT.deb HARDWARE_AGENT_UPDATER.deb"
agent_deb=$(CDPATH='' cd -- "$(dirname "$1")" && pwd)/$(basename "$1")
updater_deb=$(CDPATH='' cd -- "$(dirname "$2")" && pwd)/$(basename "$2")
[ -f "$agent_deb" ] && [ -f "$updater_deb" ] || die "both prebuilt packages must exist"
agent_src=$(CDPATH='' cd -- "$(dirname "$0")/.." && pwd)
env_file=/etc/dmitri/agent.env
lock_expected=/var/lib/dmitri/scan.lock
lock_directory=/var/lib/dmitri
configured_lock=$(cat "$agent_src/packaging/scan-lock-path")
[ "$configured_lock" = "$lock_expected" ] || die "unsafe or non-canonical scan lock path"
[ "$(readlink -f "$lock_directory")" = "$lock_directory" ] \
    || die "scan lock directory is not canonical"
lock=$lock_expected
[ ! -L "$lock" ] || die "scan lock must not be a symbolic link"
[ -f "$lock" ] || die "persistent scan lock is missing; cannot prove the agent is idle"
exec 9<>"$lock"
lock_release() { flock -u 9 || true; }
lock_acquire() { flock -n -x 9 || die "scan or update in progress; try again later"; }
lock_acquire

os_id=$(sed -n 's/^ID=//p' /etc/os-release | tr -d '"')
os_version=$(sed -n 's/^VERSION_ID=//p' /etc/os-release | tr -d '"')
[ "$os_id" = debian ] && [ "$os_version" = 13 ] || die "Debian 13 is the only supported bootstrap platform"
[ "$(dpkg --print-architecture)" = arm64 ] || die "arm64 is the only supported bootstrap architecture"
[ -x /opt/uv-python/bin/python ] || die "prepare Python 3.12 at /opt/uv-python/bin/python before bootstrap"
[ -x /usr/local/bin/uv ] || die "prepare the pinned uv binary at /usr/local/bin/uv before bootstrap"
[ "$(/usr/local/bin/uv --version | awk '{print $2}')" = 0.11.20 ] || die "prepare pinned uv 0.11.20 before bootstrap"
/opt/uv-python/bin/python -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)' || die "prepared Python must be 3.12"
[ "$(dpkg-deb -f "$agent_deb" Package)" = hardware-agent ] || die "first package must be hardware-agent"
[ "$(dpkg-deb -f "$updater_deb" Package)" = hardware-agent-updater ] || die "second package must be hardware-agent-updater"
[ "$(dpkg-deb -f "$agent_deb" Architecture)" = arm64 ] || die "hardware-agent package must target arm64"
[ "$(dpkg-deb -f "$updater_deb" Architecture)" = all ] || die "hardware-agent-updater package must be Architecture: all"

assert_legacy_idle() {
    if systemctl is-active --quiet dmitri-agent.service 9>&- 2>&-; then
        die "dmitri-agent is active; stop it after the current scan completes"
    fi
    /usr/bin/python3 - <<'PY'
import os, sys
busy = {"nmap", "ffuf", "nikto", "testssl.sh", "enum4linux-ng", "ssh-audit", "smbclient", "hydra"}
for entry in os.scandir('/proc'):
    if not entry.name.isdigit():
        continue
    try:
        raw = open(f'{entry.path}/cmdline', 'rb').read().split(b'\0')
    except (OSError, PermissionError):
        continue
    args = [os.path.basename(os.fsdecode(arg)) for arg in raw if arg]
    if not args:
        continue
    if args[0] in busy or (len(args) > 1 and args[0] == 'python' and 'dmitri' in args[1] and 'agent' in args[2:]):
        print(f'active scan-related process: {args[0]}', file=sys.stderr)
        raise SystemExit(1)
PY
    [ "$?" -eq 0 ] || die "scan-related process remains; refusing bootstrap"
}
assert_legacy_idle

# Never replace an installed supervisor whose durable state cannot be read.
if dpkg-query -W -f='${Status}' hardware-agent-updater 2>/dev/null \
    | grep -q 'install ok installed'; then
    systemctl is-active --quiet dmitri-agent-update.service 9>&- \
        || die "installed update supervisor is not active; refusing to replace its state owner"
    [ -S /run/dmitri-agent-updater/control.sock ] \
        || die "installed supervisor control socket is missing"
    [ -x /usr/lib/dmitri/updater.py ] \
        || die "installed supervisor program is missing"
    /usr/bin/python3 /usr/lib/dmitri/updater.py --inspect 9>&- \
        | /usr/bin/python3 -c 'import json,sys; x=json.load(sys.stdin); raise SystemExit(0 if x.get("ok") is True and x.get("blocked") is False else 1)' \
        || die "installed supervisor has active, gated or unreadable state"
    [ ! -e /var/lib/dmitri/update-gate.json ] \
        || die "persistent update gate exists; recovery is required before bootstrap"
    /usr/bin/python3 - <<'PY'
import sqlite3, sys
path = '/var/lib/dmitri/updates/state.sqlite3'
try:
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
        raise ValueError('integrity')
    columns = {row[1] for row in db.execute('PRAGMA table_info(operations)')}
    if not {'operation_id', 'phase'} <= columns:
        raise ValueError('schema')
except Exception as exc:
    print(f'update journal is missing or invalid: {exc}', file=sys.stderr)
    raise SystemExit(1)
PY
    [ "$?" -eq 0 ] || die "installed supervisor journal is missing or invalid"
fi

mkdir -p /var/lib/dmitri/updates/bootstrap-baselines
baseline=$(mktemp -d "/var/lib/dmitri/updates/bootstrap-baselines/$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
if [ -d /opt/dmitri-agent ]; then tar -C / -cpf "$baseline/agent-tree.tar" opt/dmitri-agent 9>&- || die "could not preserve the existing agent runtime"; fi
for path in lib/systemd/system/dmitri-agent.service lib/systemd/system/dmitri-agent-update.service lib/systemd/system/dmitri-agent-update.timer lib/systemd/system/dmitri-agent-update-check.service usr/lib/dmitri/apt-upgrade-agent usr/lib/dmitri/scan-lock-path; do
    if [ -e "/$path" ] || [ -L "/$path" ]; then printf '%s\n' "$path" >>"$baseline/system-paths.txt"; fi
done
if [ -s "$baseline/system-paths.txt" ]; then tar -C / -cpf "$baseline/system-files.tar" -T "$baseline/system-paths.txt" 9>&- || die "could not preserve the current system updater files"; fi
if [ -f "$env_file" ]; then cp -p "$env_file" "$baseline/agent.env"; fi
if dpkg-query -W -f='${Status}' hardware-agent 2>/dev/null | grep -q 'install ok installed'; then dpkg-query -W -f='${Package} ${Version} ${Architecture}\n' hardware-agent >"$baseline/package.txt"; else printf '%s\n' "hardware-agent was not registered with dpkg" >"$baseline/package.txt"; fi
chmod 700 "$baseline"
provisioned=false
if [ -f "$env_file" ] && grep -q '^DEVICE_ID=' "$env_file"; then provisioned=true; fi

export DEBIAN_FRONTEND=noninteractive
apt-get install -y "$updater_deb" 9>&- || die "supervisor package installation failed; recovery baseline retained at $baseline"
lock_release
systemctl daemon-reload 9>&-
systemctl enable dmitri-agent-update.service 9>&- || die "could not enable supervisor; baseline retained at $baseline"
systemctl start dmitri-agent-update.service 9>&- || die "could not start supervisor; baseline retained at $baseline"

[ -S /run/dmitri-agent-updater/control.sock ] || die "supervisor control socket is missing"
/usr/bin/python3 /usr/lib/dmitri/updater.py --inspect 9>&- >"$baseline/supervisor-inspect.json" || die "supervisor state could not be inspected"
/usr/bin/python3 - "$baseline/supervisor-inspect.json" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding='utf-8'))
if value.get('ok') is not True or value.get('blocked') is not False:
    raise SystemExit('updater has an active, gated or unreadable operation')
PY
[ ! -e /var/lib/dmitri/update-gate.json ] || die "persistent update gate exists; recovery is required before agent installation"
/usr/bin/python3 - <<'PY'
import sqlite3, sys
path = '/var/lib/dmitri/updates/state.sqlite3'
try:
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    if db.execute('PRAGMA integrity_check').fetchone() != ('ok',): raise ValueError('integrity')
    columns = {row[1] for row in db.execute('PRAGMA table_info(operations)')}
    if not {'operation_id', 'phase'} <= columns: raise ValueError('schema')
    if db.execute("SELECT count(*) FROM operations WHERE phase IN ('requested','preparing','installing','verifying','recovering','needs_intervention')").fetchone()[0]: raise ValueError('active update')
except Exception as exc:
    print(f'update journal is missing or invalid: {exc}', file=sys.stderr)
    raise SystemExit(1)
PY
[ "$?" -eq 0 ] || die "update journal is missing or invalid"

lock_acquire
assert_legacy_idle
/usr/bin/python3 /usr/lib/dmitri/updater.py --inspect 9>&- | /usr/bin/python3 -c 'import json,sys; x=json.load(sys.stdin); raise SystemExit(0 if x.get("ok") is True and x.get("blocked") is False else 1)' || die "updater became busy before package mutation"
apt-get install -y "$agent_deb" 9>&- || die "agent package installation failed; recovery baseline retained at $baseline"
lock_release
exec 9>&- 9<&-

if [ "$provisioned" != true ]; then /opt/dmitri-agent/.venv/bin/dmitri provision || die "registration failed; recovery baseline retained at $baseline"; fi
systemctl daemon-reload 9>&-
systemctl enable dmitri-agent.service 9>&- || die "could not enable agent service; baseline retained at $baseline"
systemctl restart dmitri-agent.service 9>&- || die "could not start agent service; baseline retained at $baseline"
i=0
while [ "$i" -lt 30 ]; do
    invocation=$(systemctl show -p InvocationID --value dmitri-agent.service 9>&-)
    if [ -n "$invocation" ] && journalctl --no-pager _SYSTEMD_INVOCATION_ID="$invocation" 9>&- | grep -q "command channel connected"; then
        echo "Ready. command channel connected. Recovery baseline: $baseline"
        exit 0
    fi
    i=$((i + 1)); sleep 2
done
die "dmitri-agent did not connect. Recovery baseline retained at $baseline"
