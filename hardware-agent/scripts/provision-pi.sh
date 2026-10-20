#!/bin/sh
set -eu

die() { echo "provision-pi: $*" >&2; exit 1; }
usage() {
    printf '%s\n' \
        "Usage: $0 --repository HTTPS_URL --fingerprint PRIMARY_FINGERPRINT --public-key KEYFILE -- HARDWARE_AGENT.deb HARDWARE_AGENT_UPDATER.deb" \
        "The fingerprint must be approved out of band. KEYFILE must contain that OpenPGP public key." \
        "Example: $0 --repository https://dmitri-imt.github.io/dmitri/ --fingerprint 92BD91D03608EA3AFDB108AAB7EEC4E4E954DA7A --public-key dmitri-archive.asc -- hardware-agent.deb hardware-agent-updater.deb"
}
[ "$(id -u)" -eq 0 ] || die "run as root"
repository=${DMITRI_APT_REPOSITORY:-}
fingerprint=${DMITRI_APT_FINGERPRINT:-}
public_key=${DMITRI_APT_PUBLIC_KEY:-}
while [ "$#" -gt 0 ]; do
    case "$1" in
        --help) usage; exit 0 ;;
        --repository) [ "$#" -ge 2 ] || die "--repository needs a value"; repository=$2; shift 2 ;;
        --fingerprint) [ "$#" -ge 2 ] || die "--fingerprint needs a value"; fingerprint=$2; shift 2 ;;
        --public-key) [ "$#" -ge 2 ] || die "--public-key needs a value"; public_key=$2; shift 2 ;;
        --) shift; break ;;
        -*) die "unknown option: $1" ;;
        *) break ;;
    esac
done
[ "$#" -eq 2 ] || die "usage: provision-pi.sh --repository HTTPS_URL --fingerprint FINGERPRINT --public-key KEYFILE -- HARDWARE_AGENT.deb HARDWARE_AGENT_UPDATER.deb"
[ -n "$repository" ] && [ -n "$fingerprint" ] && [ -n "$public_key" ] \
    || die "repository, approved fingerprint and public key are required"
case "$repository" in https://*) ;; *) die "repository must use HTTPS" ;; esac
case "$fingerprint" in *[!A-Fa-f0-9]*|'') die "fingerprint must be hexadecimal" ;; esac
[ "${#fingerprint}" -ge 40 ] && [ "${#fingerprint}" -le 64 ] || die "fingerprint must be 40 to 64 hex characters"
fingerprint=$(printf '%s' "$fingerprint" | tr '[:lower:]' '[:upper:]')
agent_deb=$(CDPATH='' cd -- "$(dirname "$1")" && pwd)/$(basename "$1")
updater_deb=$(CDPATH='' cd -- "$(dirname "$2")" && pwd)/$(basename "$2")
agent_input=$agent_deb
updater_input=$updater_deb
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
# Keep the persistent scan-lock inode locked until package, timer and agent checks finish.
lock_acquire
stage_bootstrap_inputs() {
    /usr/bin/python3 - "$public_key" "$agent_input" "$updater_input" <<'PY'
import os, shutil, stat, sys, tempfile
from pathlib import Path

# Validate every ancestor before creating or changing anything beneath it.
for path in (Path('/'), Path('/run')):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise SystemExit(f'untrusted staging parent: {path}')
stage = Path(tempfile.mkdtemp(prefix='dmitri-bootstrap-', dir='/run'))
names = ('public-key', 'hardware-agent.deb', 'hardware-agent-updater.deb')
try:
    for source_name, target_name in zip(sys.argv[1:], names):
        descriptor = os.open(source_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError('bootstrap input must be a regular file')
            descriptor = os.open(stage / target_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as target:
                shutil.copyfileobj(source, target)
                target.flush()
                os.fsync(target.fileno())
except (OSError, ValueError):
    for name in names:
        (stage / name).unlink(missing_ok=True)
    stage.rmdir()
    raise
print(stage)
PY
}
input_stage=$(stage_bootstrap_inputs) || die "could not securely stage bootstrap inputs"
cleanup_bootstrap_inputs() {
    rm -f -- "$input_stage/public-key" "$input_stage/hardware-agent.deb" "$input_stage/hardware-agent-updater.deb"
    rmdir -- "$input_stage"
}
trap cleanup_bootstrap_inputs EXIT
trap 'exit 1' HUP INT TERM
public_key=$input_stage/public-key
agent_deb=$input_stage/hardware-agent.deb
updater_deb=$input_stage/hardware-agent-updater.deb
[ -f "$agent_deb" ] && [ -f "$updater_deb" ] || die "both prebuilt packages must exist"
command -v gpg >/dev/null 2>&1 || die "install gpg before bootstrap to verify the operator-supplied key fingerprint"

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

keyring_directory=/etc/apt/keyrings
keyring=$keyring_directory/dmitri-agent-archive-keyring.gpg
source_file=/etc/apt/sources.list.d/dmitri-agent-updates.list

assert_legacy_idle() {
    if systemctl is-active --quiet dmitri-agent.service 9>&- 2>&-; then
        die "dmitri-agent is active; stop it after the current scan completes"
    fi
    /usr/bin/python3 - <<'PY'
import os, sys
busy = {"nmap", "ffuf", "nikto", "testssl.sh", "enum4linux-ng", "ssh-audit", "smbclient", "hydra", "apt-get", "dpkg", "unattended-upgrade"}
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

capture_bootstrap_baseline() {
    mkdir -p /var/lib/dmitri/updates/bootstrap-baselines
    baseline=$(mktemp -d "/var/lib/dmitri/updates/bootstrap-baselines/$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
    if [ -d /opt/dmitri-agent ]; then tar -C / -cpf "$baseline/agent-tree.tar" opt/dmitri-agent 9>&- || die "could not preserve the existing agent runtime"; fi
    for path in lib/systemd/system/dmitri-agent.service lib/systemd/system/dmitri-agent-update.service lib/systemd/system/dmitri-agent-update.timer lib/systemd/system/dmitri-agent-update-check.service usr/lib/dmitri/apt-upgrade-agent usr/lib/dmitri/scan-lock-path etc/apt/keyrings/dmitri-agent-archive-keyring.gpg etc/apt/sources.list.d/dmitri-agent-updates.list; do
        if [ -e "/$path" ] || [ -L "/$path" ]; then printf '%s\n' "$path" >>"$baseline/system-paths.txt"; fi
    done
    if [ -s "$baseline/system-paths.txt" ]; then tar -C / -cpf "$baseline/system-files.tar" -T "$baseline/system-paths.txt" 9>&- || die "could not preserve the current system updater files"; fi
    if [ -f "$env_file" ]; then cp -p "$env_file" "$baseline/agent.env"; fi
    if dpkg-query -W -f='${Status}' hardware-agent 2>/dev/null | grep -q 'install ok installed'; then dpkg-query -W -f='${Package} ${Version} ${Architecture}\n' hardware-agent >"$baseline/package.txt"; else printf '%s\n' "hardware-agent was not registered with dpkg" >"$baseline/package.txt"; fi
    systemctl is-enabled dmitri-agent-update.timer >"$baseline/old-update-timer-enabled.txt" 2>&1 || true
    systemctl is-enabled apt-upgrade-agent.service >"$baseline/old-installer-enabled.txt" 2>&1 || true
    mkdir -p "$baseline/pre-bootstrap-trust"
    if [ -e "$keyring" ]; then cp -a "$keyring" "$baseline/pre-bootstrap-trust/keyring"; else printf '%s\n' absent >"$baseline/pre-bootstrap-trust/keyring"; fi
    if [ -e "$source_file" ]; then cp -a "$source_file" "$baseline/pre-bootstrap-trust/source.list"; else printf '%s\n' absent >"$baseline/pre-bootstrap-trust/source.list"; fi
    chmod 700 "$baseline"
}

assert_legacy_idle

if ! dpkg-query -W -f='${Status}' hardware-agent-updater 2>/dev/null \
    | grep -q 'install ok installed' \
    && systemctl is-active --quiet dmitri-agent-update.service 9>&- 2>&-; then
    die "legacy automatic installer is active; let it finish before bootstrap"
fi
capture_bootstrap_baseline

if systemctl is-active --quiet dmitri-agent-update.timer 9>&- 2>&-; then
    systemctl stop dmitri-agent-update.timer 9>&- || die "could not stop legacy update timer"
fi
systemctl disable dmitri-agent-update.timer 9>&- 2>&- || true
if systemctl is-active --quiet apt-upgrade-agent.service 9>&- 2>&-; then
    systemctl stop apt-upgrade-agent.service 9>&- || die "could not stop legacy package installer"
fi
systemctl disable apt-upgrade-agent.service 9>&- 2>&- || true
mkdir -p /var/lib/dmitri/updates/bootstrap-baselines
actual_fingerprint=$(gpg --batch --show-keys --with-colons "$public_key" 2>/dev/null \
    | awk -F: '$1 == "pub" { primary++ } $1 == "fpr" && !fingerprint { fingerprint = toupper($10) } END { if (primary != 1) exit 1; print fingerprint }') \
    || die "key file must contain exactly one primary signing authority"
[ "$actual_fingerprint" = "$fingerprint" ] \
    || die "operator-supplied key does not match the approved primary fingerprint"
mkdir -p "$keyring_directory"
keyring_tmp=$(mktemp "$keyring_directory/.dmitri-key.XXXXXX")
if head -n 1 "$public_key" | grep -q 'BEGIN PGP PUBLIC KEY BLOCK'; then
    gpg --batch --yes --dearmor --output "$keyring_tmp" "$public_key" || die "could not convert the approved signing key"
else
    cp "$public_key" "$keyring_tmp"
fi
chmod 644 "$keyring_tmp"
mv -f "$keyring_tmp" "$keyring"
printf 'deb [arch=arm64 signed-by=%s] %s stable main\n' "$keyring" "$repository" >"$source_file"
chmod 644 "$source_file"
apt-get -o Dir::Etc::sourcelist="$source_file" -o Dir::Etc::sourceparts=- \
    -o Acquire::Check-Valid-Until=true update 9>&- \
    || die "approved signed repository metadata could not be refreshed"
/usr/bin/python3 "$agent_src/packaging/verify-bootstrap-packages.py" \
    --repository "$repository" "$agent_deb" "$updater_deb" \
    || die "bootstrap packages do not match authenticated signed metadata"

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

provisioned=false
if [ -f "$env_file" ] && grep -q '^DEVICE_ID=' "$env_file"; then provisioned=true; fi

export DEBIAN_FRONTEND=noninteractive
apt-get install -y "$updater_deb" 9>&- || die "supervisor package installation failed; recovery baseline retained at $baseline"
systemctl daemon-reload 9>&-
# This supervisor is static; the enabled agent's Requires= pulls it in on boot.
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

assert_legacy_idle
/usr/bin/python3 /usr/lib/dmitri/updater.py --inspect 9>&- | /usr/bin/python3 -c 'import json,sys; x=json.load(sys.stdin); raise SystemExit(0 if x.get("ok") is True and x.get("blocked") is False else 1)' || die "updater became busy before package mutation"
apt-get install -y "$agent_deb" 9>&- || die "agent package installation failed; recovery baseline retained at $baseline"
installed_version=$(dpkg-query -W -f='${Version}' hardware-agent 9>&-)
supplied_version=$(dpkg-deb -f "$agent_deb" Version)
[ "$installed_version" = "$supplied_version" ] || die "installed agent does not match the authenticated bootstrap package"
mkdir -p /var/lib/dmitri/updates/cache
chmod 700 /var/lib/dmitri/updates/cache
/usr/bin/python3 - "$agent_deb" "$installed_version" <<'PY'
import hashlib, os, shutil, sys, tempfile
from pathlib import Path
source = Path(sys.argv[1])
version = sys.argv[2]
cache = Path('/var/lib/dmitri/updates/cache')
digest = hashlib.sha256()
with source.open('rb') as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
hexdigest = digest.hexdigest()
for name, contents in ((f'{version}.deb', None), (f'{version}.sha256', (hexdigest + '\n').encode('ascii'))):
    descriptor, temporary_name = tempfile.mkstemp(prefix='.bootstrap-', dir=cache)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            if contents is None:
                with source.open('rb') as input_file:
                    shutil.copyfileobj(input_file, output)
            else:
                output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, cache / name)
    finally:
        temporary.unlink(missing_ok=True)
descriptor = os.open(cache, os.O_RDONLY)
try:
    os.fsync(descriptor)
finally:
    os.close(descriptor)
PY
if [ "$provisioned" != true ]; then /opt/dmitri-agent/.venv/bin/dmitri provision || die "registration failed; recovery baseline retained at $baseline"; fi
systemctl daemon-reload 9>&-
systemctl enable --now dmitri-agent-update.timer 9>&- || die "could not enable the check-only metadata timer; baseline retained at $baseline"
timer_target=$(systemctl show -p Unit --value dmitri-agent-update.timer 9>&-)
[ "$timer_target" = dmitri-agent-update-check.service ] \
    || die "loaded timer does not target the check-only service; baseline retained at $baseline"
systemctl is-active --quiet dmitri-agent-update.timer 9>&- \
    || die "check-only timer is not active; baseline retained at $baseline"
systemctl enable dmitri-agent.service 9>&- || die "could not enable agent service; baseline retained at $baseline"
systemctl restart dmitri-agent.service 9>&- || die "could not start agent service; baseline retained at $baseline"
i=0
while [ "$i" -lt 30 ]; do
    invocation=$(systemctl show -p InvocationID --value dmitri-agent.service 9>&-)
    if [ -n "$invocation" ] && journalctl --no-pager _SYSTEMD_INVOCATION_ID="$invocation" 9>&- | grep -q "command channel connected"; then
        lock_release
        exec 9>&- 9<&-
        echo "Ready. command channel connected. Recovery baseline: $baseline"
        exit 0
    fi
    i=$((i + 1)); sleep 2
done
die "dmitri-agent did not connect. Recovery baseline retained at $baseline"
