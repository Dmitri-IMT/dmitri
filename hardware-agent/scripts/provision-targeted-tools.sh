#!/usr/bin/env bash
# Provision the external service-targeted tools on Raspberry Pi OS Bookworm.
# Scans never call this script.  --verify-only performs local checks only.
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly AGENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
readonly TOOLS_ROOT="/opt/dmitri/tools"
readonly BIN_DIR="/usr/local/bin"
readonly FFUF_VERSION="2.1.0"
readonly FFUF_ARMHF_SHA256="b9d4b7e485f098bbcd2a61ba0c8304aac8634c71a7a0d29ad243aaf7db16ec9b"
readonly FFUF_ARM64_SHA256="6ae920d09d5202762fca21967a460c6fb88135bdfa806bee4d3d2c430dcedeea"
readonly NIKTO_VERSION="2.6.0"
readonly NIKTO_COMMIT="69681e2e4213c15b85a90c53b2169ecb2a88fb01"
readonly NIKTO_DB_SHA256="e221b0ab6db1b3dec26a11674a68216fc6ee690b8b20f07056d4e4ae33ed30a2"
readonly ENUM4LINUX_VERSION="1.3.10"
readonly ENUM4LINUX_COMMIT="f34e7bb3bc2bcd10267a7257fb3658154434ccf4"
readonly TESTSSL_VERSION="3.0.8+dfsg-1"
readonly DIRB_MAX_BYTES=1048576
readonly DIRB_MIN_ENTRIES=4000
readonly DIRB_MAX_ENTRIES=10000

VERIFY_ONLY=0
TMP_DIR=""
CHECK_FAILURES=0

info() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: provision-targeted-tools.sh [--verify-only]

Install the pinned service-targeted tools on Raspberry Pi OS Bookworm.
  --verify-only  Check architecture, versions, capabilities, and DIRB locally.
                 This mode does not use apt, git, curl, or any network access.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verify-only) VERIFY_ONLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
  shift
done

require_arm_arch() {
  local arch=""
  if command -v dpkg >/dev/null 2>&1; then
    arch="$(dpkg --print-architecture)"
  else
    case "$(uname -m)" in
      armv6l|armv7l) arch="armhf" ;;
      aarch64) arch="arm64" ;;
      *) arch="$(uname -m)" ;;
    esac
  fi
  case "$arch" in
    armhf|arm64) printf '%s\n' "$arch" ;;
    *) die "unsupported architecture ${arch}; targeted tools support Raspberry Pi armhf or arm64 only" ;;
  esac
}

require_root_for_install() {
  [[ "$VERIFY_ONLY" -eq 1 || "${EUID}" -eq 0 ]] || die "installation requires root; re-run with sudo (or use --verify-only)"
}

cleanup() {
  if [[ -n "$TMP_DIR" && -d "$TMP_DIR" ]]; then
    rm -rf -- "$TMP_DIR"
  fi
}
trap cleanup EXIT

install_apt_dependencies() {
  info "Installing Bookworm runtime dependencies"
  apt-get update
  apt-get install -y --no-install-recommends \
    ca-certificates curl git perl libnet-ssleay-perl libio-socket-ssl-perl \
    libjson-perl libxml-writer-perl dirb "testssl.sh=${TESTSSL_VERSION}" \
    smbclient samba-common-bin python3-ldap3 python3-yaml python3-impacket
}

install_ffuf() {
  local arch="$1"
  local asset sha archive downloaded extracted
  if [[ "$arch" == armhf ]]; then
    asset="armv6"
    sha="$FFUF_ARMHF_SHA256"
  else
    asset="arm64"
    sha="$FFUF_ARM64_SHA256"
  fi
  archive="${TOOLS_ROOT}/ffuf-${FFUF_VERSION}-linux_${asset}.tar.gz"
  if [[ -x "${BIN_DIR}/ffuf" ]] \
    && command_has_exact_version "$FFUF_VERSION" "${BIN_DIR}/ffuf" -V \
    && ffuf_archive_matches_binary "$sha" "$archive" "${BIN_DIR}/ffuf"; then
    info "ffuf ${FFUF_VERSION} already installed"
    return 0
  fi

  mkdir -p "${TOOLS_ROOT}"
  if ! ffuf_archive_has_sha256 "$sha" "$archive"; then
    downloaded="${TMP_DIR}/ffuf.tar.gz"
    info "Installing ffuf ${FFUF_VERSION} (${asset})"
    curl --fail --location --silent --show-error \
      "https://github.com/ffuf/ffuf/releases/download/v${FFUF_VERSION}/ffuf_${FFUF_VERSION}_linux_${asset}.tar.gz" \
      --output "$downloaded"
    printf '%s  %s\n' "$sha" "$downloaded" | sha256sum --check --status - \
      || die "ffuf archive checksum mismatch"
    install -m 0644 "$downloaded" "$archive"
  fi

  extracted="${TMP_DIR}/ffuf"
  mkdir -p "$extracted"
  tar -xzf "$archive" -C "$extracted"
  [[ -x "${extracted}/ffuf" ]] || die "ffuf archive did not contain an executable"
  install -m 0755 "${extracted}/ffuf" "${BIN_DIR}/ffuf"
}

checkout_pinned_repo() {
  local url="$1" destination="$2" commit="$3"
  if [[ -e "$destination" ]]; then
    [[ -d "$destination/.git" ]] || die "existing ${destination} is not a Git checkout"
    local current
    current="$(git -C "$destination" rev-parse HEAD)"
    [[ "$current" == "$commit" ]] || die "${destination} is at ${current}, expected pinned commit ${commit}; remove it and retry"
    return 0
  fi

  local checkout="${TMP_DIR}/$(basename "$destination")"
  git clone --quiet "$url" "$checkout"
  git -C "$checkout" checkout --quiet --detach "$commit"
  [[ "$(git -C "$checkout" rev-parse HEAD)" == "$commit" ]] || die "checked-out commit mismatch for ${url}"
  mkdir -p "$(dirname "$destination")"
  mv -- "$checkout" "$destination"
}

install_nikto() {
  local destination="${TOOLS_ROOT}/nikto-${NIKTO_VERSION}"
  info "Installing Nikto ${NIKTO_VERSION} (${NIKTO_COMMIT})"
  checkout_pinned_repo "https://github.com/sullo/nikto.git" "$destination" "$NIKTO_COMMIT"
  local database="${destination}/program/databases/db_tests"
  [[ -f "$database" ]] || die "Nikto database missing: ${database}"
  [[ "$(sha256sum "$database" | awk '{print $1}')" == "$NIKTO_DB_SHA256" ]] \
    || die "Nikto database checksum mismatch"
  cat >"${TMP_DIR}/nikto" <<EOF
#!/usr/bin/env bash
exec perl "${destination}/program/nikto.pl" "\$@"
EOF
  install -m 0755 "${TMP_DIR}/nikto" "${BIN_DIR}/nikto"
}

install_enum4linux() {
  local destination="${TOOLS_ROOT}/enum4linux-ng-${ENUM4LINUX_VERSION}"
  info "Installing enum4linux-ng ${ENUM4LINUX_VERSION} (${ENUM4LINUX_COMMIT})"
  checkout_pinned_repo "https://github.com/cddmp/enum4linux-ng.git" "$destination" "$ENUM4LINUX_COMMIT"
  local entry=""
  for candidate in enum4linux-ng.py enum4linux-ng; do
    if [[ -f "${destination}/${candidate}" ]]; then
      entry="${destination}/${candidate}"
      break
    fi
  done
  [[ -n "$entry" ]] || die "enum4linux-ng entrypoint missing in pinned checkout"
  cat >"${TMP_DIR}/enum4linux-ng" <<EOF
#!/usr/bin/env bash
exec /usr/bin/python3 "${entry}" "\$@"
EOF
  install -m 0755 "${TMP_DIR}/enum4linux-ng" "${BIN_DIR}/enum4linux-ng"
}

find_dirb_wordlist() {
  local candidate
  for candidate in /usr/share/wordlists/dirb/common.txt /usr/share/dirb/wordlists/common.txt; do
    if [[ -r "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

check_dirb_wordlist() {
  local list="$1" bytes entries
  [[ -f "$list" ]] || { warn "DIRB list is not a regular file: ${list}"; return 1; }
  bytes="$(wc -c <"$list")"
  (( bytes <= DIRB_MAX_BYTES )) || { warn "DIRB list exceeds ${DIRB_MAX_BYTES} bytes"; return 1; }
  command -v iconv >/dev/null 2>&1 || { warn "iconv is required to validate DIRB UTF-8"; return 1; }
  iconv -f UTF-8 -t UTF-8 "$list" >/dev/null || { warn "DIRB list is not valid UTF-8"; return 1; }
  entries="$(awk 'NF && $1 !~ /^#/ {n++} END {print n+0}' "$list")"
  (( entries >= DIRB_MIN_ENTRIES && entries <= DIRB_MAX_ENTRIES )) \
    || { warn "DIRB list has ${entries} entries; expected ${DIRB_MIN_ENTRIES}-${DIRB_MAX_ENTRIES}"; return 1; }
}

command_has_exact_version() {
  local expected="$1"; shift
  local output
  # Compare a complete whitespace-delimited version token.  A substring check
  # would incorrectly accept values such as 12.1.0 for 2.1.0 or 2.6.01 for
  # 2.6.0.  Upstream tools differ only in whether they prefix the token with
  # a literal `v`.
  output="$({ timeout 30s "$@"; } 2>&1)" || return 1
  awk -v expected="$expected" '
      {
        for (i = 1; i <= NF; i++) {
          token = $i
          sub(/^v/, "", token)
          if (token == expected) found = 1
        }
      }
      END { exit(found ? 0 : 1) }
    ' <<<"$output"
}

check_command_exact_version() {
  local label="$1" expected="$2"; shift 2
  if command_has_exact_version "$expected" "$@"; then
    printf 'PASS  %s\n' "$label"
    return 0
  fi
  printf 'FAIL  %s\n' "$label" >&2
  CHECK_FAILURES=$((CHECK_FAILURES + 1))
  return 1
}

check_package_exact_version() {
  local label="$1" package="$2" expected="$3" actual
  actual="$(dpkg-query -W -f='${Version}' "$package" 2>/dev/null)" || actual=""
  if [[ "$actual" == "$expected" ]]; then
    printf 'PASS  %s\n' "$label"
    return 0
  fi
  printf 'FAIL  %s\n' "$label" >&2
  CHECK_FAILURES=$((CHECK_FAILURES + 1))
  return 1
}

check_python_package_exact_version() {
  local label="$1" package="$2" expected="$3" actual
  actual="$("${AGENT_DIR}/.venv/bin/python" -c 'import importlib.metadata, sys; print(importlib.metadata.version(sys.argv[1]))' "$package" 2>/dev/null)" || actual=""
  if [[ "$actual" == "$expected" ]]; then
    printf 'PASS  %s\n' "$label"
    return 0
  fi
  printf 'FAIL  %s\n' "$label" >&2
  CHECK_FAILURES=$((CHECK_FAILURES + 1))
  return 1
}

check_pinned_checkout() {
  local label="$1" checkout="$2" expected="$3"
  local current
  if [[ -d "$checkout/.git" ]] \
    && current="$(git -C "$checkout" rev-parse HEAD 2>/dev/null)" \
    && [[ "$current" == "$expected" ]]; then
    printf 'PASS  %s\n' "$label"
    return 0
  fi
  printf 'FAIL  %s\n' "$label" >&2
  CHECK_FAILURES=$((CHECK_FAILURES + 1))
  return 1
}

check_pinned_source_version() {
  local label="$1" file="$2" expected_line="$3"
  if [[ -f "$file" ]] && grep -Fxq -- "$expected_line" "$file"; then
    printf 'PASS  %s\n' "$label"
    return 0
  fi
  printf 'FAIL  %s\n' "$label" >&2
  CHECK_FAILURES=$((CHECK_FAILURES + 1))
  return 1
}

check_file_sha256() {
  local label="$1" expected="$2" file="$3"
  local actual
  if [[ -f "$file" ]] \
    && actual="$(sha256sum "$file" | awk '{print $1}')" \
    && [[ "$actual" == "$expected" ]]; then
    printf 'PASS  %s\n' "$label"
    return 0
  fi
  printf 'FAIL  %s\n' "$label" >&2
  CHECK_FAILURES=$((CHECK_FAILURES + 1))
  return 1
}

ffuf_archive_has_sha256() {
  local expected="$1" archive="$2" actual
  [[ -f "$archive" ]] \
    && actual="$(sha256sum "$archive" | awk '{print $1}')" \
    && [[ "$actual" == "$expected" ]]
}

ffuf_archive_matches_binary() {
  local expected="$1" archive="$2" binary="$3"
  ffuf_archive_has_sha256 "$expected" "$archive" \
    && [[ -f "$binary" ]] \
    && tar -xOf "$archive" ffuf 2>/dev/null | cmp -s - "$binary"
}

check_capabilities() {
  local arch="$1" ffuf_bin nikto_bin testssl_bin enum_bin ssh_bin dirb ffuf_sha256 ffuf_archive
  if [[ "$arch" == armhf ]]; then
    ffuf_sha256="$FFUF_ARMHF_SHA256"
  else
    ffuf_sha256="$FFUF_ARM64_SHA256"
  fi
  if [[ "$arch" == armhf ]]; then
    ffuf_archive="${TOOLS_ROOT}/ffuf-${FFUF_VERSION}-linux_armv6.tar.gz"
  else
    ffuf_archive="${TOOLS_ROOT}/ffuf-${FFUF_VERSION}-linux_arm64.tar.gz"
  fi
  ffuf_bin="$(command -v ffuf || true)"
  nikto_bin="$(command -v nikto || true)"
  testssl_bin="$(command -v testssl || command -v testssl.sh || true)"
  enum_bin="$(command -v enum4linux-ng || true)"
  ssh_bin="$(command -v ssh-audit || true)"
  if [[ -z "$ssh_bin" && -x "${AGENT_DIR}/.venv/bin/ssh-audit" ]]; then
    ssh_bin="${AGENT_DIR}/.venv/bin/ssh-audit"
  fi

  if [[ -n "$ffuf_bin" ]]; then
    check_command_exact_version "ffuf ${FFUF_VERSION}" "$FFUF_VERSION" "$ffuf_bin" -V || true
    check_file_sha256 "ffuf ${arch} archive checksum" "$ffuf_sha256" "$ffuf_archive" || true
    if ffuf_archive_matches_binary "$ffuf_sha256" "$ffuf_archive" "$ffuf_bin"; then
      printf 'PASS  ffuf %s executable matches pinned archive member\n' "$arch"
    else
      printf 'FAIL  ffuf %s executable matches pinned archive member\n' "$arch" >&2
      CHECK_FAILURES=$((CHECK_FAILURES + 1))
    fi
  else
    printf 'FAIL  ffuf executable unavailable\n' >&2
    CHECK_FAILURES=$((CHECK_FAILURES + 1))
  fi
  if [[ -n "$nikto_bin" ]]; then
    check_pinned_checkout "Nikto commit ${NIKTO_COMMIT}" \
      "${TOOLS_ROOT}/nikto-${NIKTO_VERSION}" "$NIKTO_COMMIT" || true
    check_pinned_source_version "Nikto ${NIKTO_VERSION}" \
      "${TOOLS_ROOT}/nikto-${NIKTO_VERSION}/program/nikto.pl" \
      "\$VARIABLES{'version'}   = \"${NIKTO_VERSION}\";" || true
    check_file_sha256 "Nikto database checksum" "$NIKTO_DB_SHA256" \
      "${TOOLS_ROOT}/nikto-${NIKTO_VERSION}/program/databases/db_tests" || true
  else
    printf 'FAIL  Nikto executable unavailable\n' >&2
    CHECK_FAILURES=$((CHECK_FAILURES + 1))
  fi
  if [[ -n "$testssl_bin" ]]; then
    check_package_exact_version "testssl ${TESTSSL_VERSION}" testssl.sh "$TESTSSL_VERSION" || true
  else
    printf 'FAIL  testssl executable unavailable\n' >&2
    CHECK_FAILURES=$((CHECK_FAILURES + 1))
  fi

  if [[ -n "$enum_bin" ]]; then
    check_pinned_checkout "enum4linux-ng commit ${ENUM4LINUX_COMMIT}" \
      "${TOOLS_ROOT}/enum4linux-ng-${ENUM4LINUX_VERSION}" "$ENUM4LINUX_COMMIT" || true
    check_pinned_source_version "enum4linux-ng ${ENUM4LINUX_VERSION}" \
      "${TOOLS_ROOT}/enum4linux-ng-${ENUM4LINUX_VERSION}/enum4linux-ng.py" \
      "GLOBAL_VERSION = '${ENUM4LINUX_VERSION}'" || true
    if grep -Fq -- 'out_group.add_argument("-oJ"' \
      "${TOOLS_ROOT}/enum4linux-ng-${ENUM4LINUX_VERSION}/enum4linux-ng.py"; then
      printf 'PASS  enum4linux-ng structured JSON capability\n'
    else
      printf 'FAIL  enum4linux-ng structured JSON capability\n' >&2
      CHECK_FAILURES=$((CHECK_FAILURES + 1))
    fi
  else
    printf 'FAIL  enum4linux-ng executable unavailable\n' >&2
    CHECK_FAILURES=$((CHECK_FAILURES + 1))
  fi

  if [[ -n "$ssh_bin" ]]; then
    local ssh_version ssh_help
    check_python_package_exact_version "ssh-audit 3.9.0" ssh-audit "3.9.0" || true
    ssh_version="$({ timeout 30s "$ssh_bin" --version; } 2>&1 || true)"
    ssh_help="$({ timeout 30s "$ssh_bin" --help; } 2>&1 || true)"
    if [[ -n "$ssh_version" ]] && grep -Fq -- '-j' <<<"$ssh_help" && grep -Fq -- '--skip-rate-test' <<<"$ssh_help"; then
      printf 'PASS  ssh-audit JSON and safe-rate capabilities\n'
    else
      printf 'FAIL  ssh-audit JSON and safe-rate capabilities\n' >&2
      CHECK_FAILURES=$((CHECK_FAILURES + 1))
    fi
  else
    printf 'FAIL  ssh-audit executable unavailable; run uv sync --extra dev\n' >&2
    CHECK_FAILURES=$((CHECK_FAILURES + 1))
  fi

  if dirb="$(find_dirb_wordlist)" && check_dirb_wordlist "$dirb"; then
    printf 'PASS  DIRB common.txt (%s)\n' "$dirb"
  else
    printf 'FAIL  DIRB common.txt unavailable or invalid\n' >&2
    CHECK_FAILURES=$((CHECK_FAILURES + 1))
  fi
}

run_local_smoke_tests() {
  command -v uv >/dev/null 2>&1 || die "uv is required for local targeted-tool smoke tests"
  info "Running offline targeted parser and fake-listener smoke tests"
  (cd "$AGENT_DIR" && uv run --offline pytest -q \
    tests/unit/test_targeted_web.py \
    tests/unit/test_targeted_tls.py \
    tests/unit/test_targeted_smb.py \
    tests/unit/test_targeted_ssh.py \
    tests/unit/test_targeted_cleartext.py)
}

verify_only() {
  info "Verifying targeted-tool provision (${1})"
  check_capabilities "$1"
  if (( CHECK_FAILURES > 0 )); then
    die "${CHECK_FAILURES} targeted-tool verification check(s) failed"
  fi
  run_local_smoke_tests
  info "Targeted-tool verification passed"
}

install_all() {
  local arch="$1"
  require_root_for_install
  TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/dmitri-targeted.XXXXXX")"
  install_apt_dependencies
  mkdir -p "$TOOLS_ROOT" "$BIN_DIR"
  install_ffuf "$arch"
  install_nikto
  install_enum4linux
  info "Verifying installed targeted tools"
  verify_only "$arch"
}

ARCH="$(require_arm_arch)"
if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  verify_only "$ARCH"
else
  install_all "$ARCH"
fi
