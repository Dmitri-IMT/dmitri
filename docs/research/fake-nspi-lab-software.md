# Fake "NSPi lab" software picks for the Pi simulator target network

> **Question.** For DMI-187, pick real, runnable open-source software for a fake "NSPi lab"
> network that the Dmitri Pi scanner (`docker/pi-simulator/`) scans over a private Docker
> bridge. Weak devices must produce real findings; clean devices must produce none. For each
> device: concrete software + exact version + image/build path, relevant CVEs from primary
> sources, which Dmitri check should detect each issue, whether `nmap -sV` identifies the
> product/version/CPE, arm64/amd64 availability, and risks.
>
> Researched 2026-10-12. Decisions 1-8 in the issue are fixed; this note only fills in the
> software and verifies detectability. Primary sources: the scanner source in this repo,
> nmap `nmap-service-probes` and `vulners.nse` (github.com/nmap/nmap, master), NVD, Docker Hub
> registry API, vendor repos. **Build verification was NOT run**: this environment's sandbox
> blocks building external source (Docker builds and `git clone` of third-party repos were
> denied). Every "runnable" claim below rests on registry tags, upstream Dockerfiles and
> published CVE data, not on a local build. Items that build only from source are marked
> `unverified (build)`.

---

## How the scanner actually turns a service into a finding (source of truth)

Confirmed by reading the agent:

- **vulners is an online API.** `vulners.nse` calls `https://vulners.com/api/v3/burp/software/`
  (github.com/nmap/nmap master, `scripts/vulners.nse` line ~126). It fires **only** when
  `nmap -sV` already produced a product **and** a version (`portrule` requires
  `port.version.version`), and it queries by CPE first, then by `product+version`
  (`vulners.nse` `action`, lines ~225-240). Dmitri runs it with `-sV` and
  `vulners.mincvss=<min_cvss>` (`hardware-agent/src/agent/discovery/vulnerability_detection.py`
  lines 39-45). `min_cvss` is 5.0 for `nspi`/`standard`, 3.0 for `extensive`, 1.0 for `max`
  (`config.py` `min_cvss_for_mode`).
  **RISK (lab-wide):** the scanner container therefore needs **outbound HTTPS to vulners.com**.
  The private bridge must allow egress for the agent, or every vulners-based CVE finding
  silently disappears and the "weak" devices look clean. Nothing needs to be *inbound* from the
  internet; only the scanner's egress.
- **Version intensity** is forced to at least 7 (`config.py` `effective_version_intensity`), so
  rarity-5 probes such as the RTSP probe do run.
- **Findings without vulners** come from NSE extractors in
  `hardware-agent/src/agent/normalize/findings.py` (`_EXTRACTORS`): `smb-protocols` -> SMBv1,
  `smb2-security-mode` -> SMB signing, `ssh-auth-methods` -> password auth, `http-methods`,
  `ssl-cert`, `ssl-enum-ciphers`, `ftp-anon`, plus a generic CVE/`vuln`-table scraper. Any NSE
  output line containing a `CVE-\d{4}-\d+` is also harvested generically.
- **Targeted tools** (`extensive`/`max`/`nspi` only; see `targeted/selection.py`): ffuf + nikto
  on http/https (ports 80/443/8080/8443 or named http), testssl.sh on TLS ports, enum4linux-ng
  on one SMB port (445 preferred), ssh-audit on 22, ftp-check on 21, telnet-check on 23. nikto
  severity maps from OSVDB category (`web.py` `_nikto_severity`); testssl maps from its own
  severity field; ssh-audit from fail/warn + score.
- **OT/Modbus** (`ot/modbus/`): FC43 device identification is read via pymodbus
  `read_device_information(read_code=0x02)` (`client.py` lines ~95-97). The Schneider CPE is
  synthesised **only** when `vendor_name` canonicalises to `schneiderelectric`/
  `schneiderautomation` **and** the product maps to Modicon M340/M580
  (`ot/modbus/fingerprints.py` `fingerprint_identification` / `_schneider_family`). That CPE is
  appended to the port's CPE list, so vulners can then match it.
- **NSPi ports** (`config.py` `NSPI_PORTS`): `502,4840,44818,445,139,3389,5985`, merged with a
  top-1000 TCP pass. **TCP only** — no UDP, so SNMP/BACnet/printer-discovery-over-UDP are invisible.
- **OPC UA has no probe and no check.** `nmap-service-probes` (master) has **zero** matches for
  `opcua`/`opc.ua`/`4840`; there is no NSE OPC UA script in Dmitri's lists. Port 4840 is in
  `NSPI_PORTS` so it is scanned, but `-sV` cannot name the product or version, so vulners never
  fires and there is no deep OPC UA inspection.

---

## 1. Schneider-like PLC — OpenPLC_v3 (Modbus 502 + web 8080)

**Software / version.** OpenPLC Runtime v3, `thiagoralves/OpenPLC_v3`. The repo is **archived /
End-of-Life** as of 2026 (README: "reached End of Life", replaced by v4) but still clones and the
Docker build path exists (`Dockerfile`, now `FROM debian:trixie-20251020`). Pin an **old** commit
for old-version CVEs, e.g. `b4702061` (2024-04-10, `FROM debian:bullseye-20211201`), the commit
family named in the Talos EtherNet/IP advisories.
Build path: `git clone https://github.com/thiagoralves/OpenPLC_v3 && git checkout b4702061 &&
docker build .` (`./install.sh docker` inside). `unverified (build)` — not built here.
Repo: https://github.com/thiagoralves/OpenPLC_v3

**Exposed ports.** 502 Modbus TCP, 8080 web UI (Flask/Werkzeug, Python).

**CVEs (NVD).**
- CVE-2018-20818 — CVSS 9.8 — buffer overflow in `modbus.cpp mapUnknown` on the Modbus TCP
  server, OpenPLC_v2/v3. https://nvd.nist.gov/vuln/detail/CVE-2018-20818
- CVE-2021-3351 — CVSS 5.4 — stored XSS via Device Name on the web UI Add-New-Device page.
  https://nvd.nist.gov/vuln/detail/CVE-2021-3351
- CVE-2024-34026 — CVSS 9.0 — stack buffer overflow in the EtherNet/IP parser (port 44818, which
  OpenPLC does not open by default; relevant only if ENIP is enabled).
  https://nvd.nist.gov/vuln/detail/CVE-2024-34026
- CVE-2021-47770 — CVSS 8.8 — authenticated RCE via the web UI.
  https://nvd.nist.gov/vuln/detail/CVE-2021-47770

**Will `nmap -sV` identify it / will Dmitri detect the CVEs?** **Largely no — this is the central
finding for decision 1.**
- On **8080**, `-sV` sees a Werkzeug/Python HTTP banner, not "OpenPLC". There is no OpenPLC CPE,
  so **vulners cannot match the OpenPLC web CVEs**. The web CVEs above are invisible to vulners.
- On **502**, `nmap-service-probes` has no "OpenPLC" product string; the port is named `modbus`
  generically. vulners has no version/CPE, so **CVE-2018-20818 is not matched** either.
- **FC43 Schneider identity is NOT achievable in OpenPLC.** `webserver/core/modbus.cpp` defines
  function codes 1-6, 15, 16 and debug codes 0x41-0x45 only — **there is no case for 0x2B (FC43
  MEI) and none for 0x11 (Report Server ID)**; both fall through to
  `ModbusError(..., ERR_ILLEGAL_FUNCTION)`. So `read_device_information()` from Dmitri's pymodbus
  probe (`ot/modbus/client.py`) gets an illegal-function exception, `vendor_name` stays empty,
  and `fingerprint_identification()` returns `None`. **OpenPLC cannot be configured to report a
  Schneider identity over Modbus** — there is no vendor-name field to set.
- What Dmitri *will* record: `modbus-discover` (nmap) and the pymodbus probe still see a
  responding Modbus endpoint, so `inventory_modbus_host` marks port 502 as a Modbus/ICS service
  (`confidence="confirmed"` via the responding/exception unit), feeding the OT exposure role in
  `assessment/exposure.py`. That is an **ICS-exposure** signal, not a CVE finding.

**arm64/amd64.** Builds from `debian:bullseye`/`trixie` base, both multi-arch, so amd64 and arm64
both build in principle. `unverified (build)`.

**Open question / recommendation (in scope — decision 1 asked me to check configurability).**
OpenPLC gives real OT presence but **no scanner-visible CVE finding and no Schneider identity**.
If decision 1 wants either (a) a vulners CVE hit on the PLC or (b) a visible Schneider/Modicon
fingerprint through Dmitri's FC43 path, OpenPLC delivers neither. A Modbus server that answers
FC43 with a configurable device identification (e.g. a small pymodbus-based server setting
`ModbusDeviceIdentification` vendor_name="Schneider Electric", product/model "BMXP34..." /
"M340") is the only way to make the Schneider look land in `fingerprints.py`, and the synthesised
`cpe:2.3:o:schneider-electric:modicon_m340_firmware:<ver>` then lets vulners match Modicon CVEs.
That is not "old PLC software with its own CVEs", so there is a genuine tension between the two
goals. **Flag for the user to choose** before implementation.

---

## 2. Beckhoff-like controller — OPC UA server on 4840

**Software / version.** `open62541` (open-source OPC UA stack, github.com/open62541/open62541).
An old tag such as **v1.0.1** or **v1.2.4** carries the DoS CVEs below. It is a C library with
example servers (`examples/server.c`) that let you set `ApplicationName`, `ProductUri` and
`ManufacturerName` in the build — so a "Beckhoff" application/product/manufacturer string is
configurable in the server you compile. Build from the source tag with its CMake; no official
Docker Hub image, so `unverified (build)`.
Repo/tags: https://github.com/open62541/open62541/tags

**CVEs (NVD).**
- CVE-2022-25761 — CVSS 7.5 — DoS, open62541 before 1.2.5 and 1.3.x before 1.3.1.
  https://nvd.nist.gov/vuln/detail/CVE-2022-25761
- CVE-2020-36429 — CVSS 5.5 — out-of-bounds write (`Variant_encodeJson`) before 1.0.4.
  https://nvd.nist.gov/vuln/detail/CVE-2020-36429
- CVE-2024-53429 — CVSS 7.5 — assertion-failure crash, v1.4.6.
  https://nvd.nist.gov/vuln/detail/CVE-2024-53429

**Will Dmitri detect it?** **No — port exposure only.** As established above, nmap has no OPC UA
probe and Dmitri has no OPC UA NSE check. Port 4840 shows open, service unnamed, no version, no
vulners, no deep check. **None of the open62541 CVEs are detectable by this scanner.** The
Beckhoff "identity" (ApplicationName etc.) is also invisible — nothing reads it. This device
contributes only an open-4840 line in the inventory.
**This is expected given decision 2, but it means this device cannot be a "weak device that
produces a real CVE finding".** Treat it as a presence-only node. If a visible finding is wanted
on it later, it would have to come from a *second* exposed service (e.g. an old web UI or TLS on
another port), not from OPC UA.
python-opcua/asyncua would be the same story for detection (port only); open62541 is the better
pick because its CVEs are documented and its example server is trivial to brand.

**arm64/amd64.** Pure C + CMake, builds on both. `unverified (build)`.

---

## 3. Database with known CVEs — MySQL 8.0.31 (port 3306)

**Pick: `mysql:8.0.31`.** Chosen over MariaDB specifically for clean version detection (see trap
below).
Image: Docker Hub `library/mysql:8.0.31`, `['amd64','arm64v8']`, published 2022-12-07 — **arm64
present** (good for Apple Silicon and Pi). Still pullable today.
https://hub.docker.com/_/mysql

**`nmap -sV` identification.** `nmap-service-probes` line 2258:
`match mysql m|^.\0\0\0\x0a(8\.[-_~.+\w]+)\0....| p/MySQL/ v/$1/ cpe:/a:mysql:mysql:$1/`.
The MySQL handshake carries `8.0.31` verbatim, so `-sV` yields product MySQL, version 8.0.31, and
`cpe:/a:mysql:mysql:8.0.31` — exactly what vulners needs.

**CVEs (NVD, matched to `cpe:2.3:a:oracle:mysql:8.0.31`, 131 results; patched in 8.0.32+).**
- CVE-2023-21877 — CVSS 5.5 — InnoDB, high-availability DoS.
  https://nvd.nist.gov/vuln/detail/CVE-2023-21877
- CVE-2023-21880 — CVSS 5.5 — InnoDB, authenticated DoS.
  https://nvd.nist.gov/vuln/detail/CVE-2023-21880
- CVE-2023-21875 — CVSS 5.9 — Server: Security: Encryption.
  https://nvd.nist.gov/vuln/detail/CVE-2023-21875
  (Most are CVSS 4.9-6.5 DoS; with `min_cvss=5.0` on `nspi`/`standard`, the 5.5/5.9 ones surface;
  `extensive` (3.0) surfaces the rest.)

**Which Dmitri check / expected finding.** `-sV` CPE -> vulners NSE -> `_extract_vulners_findings`
emits "Known CVE detected via vulners: CVE-2023-XXXXX" with the vulners CVSS and a
`vulners.com/cve/...` reference. Several medium findings expected.

**MariaDB trap (why not MariaDB, for the record).** MariaDB's handshake prefixes a fake
`5.5.5-` replication-compatibility string, e.g. `5.5.5-10.5.8-MariaDB-...`. nmap line 2251/2345
`([15]\d?\.[-_~.+:\w]+?)-MariaDB` captures the string up to the first `-MariaDB`, which yields a
wrong/garbled version (and historically `5.5.5`) rather than the real 10.5.8. vulners then matches
the wrong version set. MariaDB arm64 images (e.g. `mariadb:10.5.8`, arm64v8, 2021) do exist and
have 69 CVEs at 10.5.8, but the version-prefix issue makes findings unreliable. MySQL 8.0.31 is
the clean choice.

**Risk.** Needs vulners egress (see lab-wide risk). No auth bruteforce is attempted by Dmitri, so
leaving default creds is harmless to the scan; the finding comes purely from the version banner.

---

## 4. IP camera — MIXED: mediamtx RTSP (554) + a web UI

**Streaming: `bluenviron/mediamtx:1.21.2`** (formerly rtsp-simple-server). Docker Hub
`['amd64','arm','arm64']`, updated 2026-10-08 — **arm64 present**, pulls today.
https://hub.docker.com/r/bluenviron/mediamtx

**Will `-sV` identify RTSP?** The RTSP probe runs on port 554 (`nmap-service-probes` line 12295-ish,
`ports 80,554,...`, rarity 5, within Dmitri's forced intensity 7). But mediamtx has **no signature**
in `nmap-service-probes` — the only RTSP signatures with versions are Live555, Darwin/QTSS,
AirTunes, etc. So mediamtx is named `rtsp` with **no version**, so **no vulners on RTSP**. mediamtx
also currently has **no NVD CVEs** (keyword search empty). So the RTSP port is a **camera-identity /
exposure signal only** (port 554 open + `rtsp` service), which is the intended "looks like a camera"
part — it is *not* the vulnerable part.

**The vulnerable part must be the web side.** Options that give a *detectable* weak finding:
- An **old `lighttpd`** or **old `nginx`** serving the camera login over HTTP/HTTPS. `-sV`
  captures `lighttpd/x.y.z` (probes line 5749, `cpe:/a:lighttpd:lighttpd:$1`) or `nginx/x.y.z`
  (line 7025-7027) -> vulners matches version CVEs. For a visible weak camera: pin an old
  `nginx:1.18.0` / old `lighttpd` with known CVEs.
- **TLS weaknesses** on an HTTPS login: self-signed cert and/or TLS 1.0 -> `ssl-cert` /
  `ssl-enum-ciphers` NSE findings (`findings.py` `_extract_ssl_cert_findings`,
  `_extract_weak_cipher_findings`) and testssl.sh targeted issues (`extensive`/`nspi`).
- **nikto/ffuf** against the web root: exposed `.git`, `.env`, directory listing, risky HTTP
  methods -> `web.py` WEB-* rules and `http-methods`.

**Alternative RTSP that nmap *does* version (if a vulners RTSP hit is wanted):** an **old
Live555** ("Live555 Streaming Media"). nmap line 12363 matches `p/Live555 Streaming Server rtspd/`
**but captures no version** in that signature, so even Live555 would not feed vulners a version.
Conclusion: RTSP on this scanner is presence-only regardless of server; put the camera's real
weakness in the web UI.

**Recommendation.** mediamtx:1.21.2 (current, clean RTSP) + an old-version web server (old nginx or
lighttpd with self-signed TLS 1.0) for the "vulnerable" half. Mixed device: RTSP clean/identity,
web weak. Verified runnable: mediamtx **yes** (registry); old nginx/lighttpd **yes** (registry).

---

## 5. Windows-style PC — MIXED: SMB 139/445 (Samba) + RDP 3389 (xrdp)

**SMB: Samba.** Two instances to show mixed:
- Weak: an **old Samba** (e.g. Debian bookworm `samba 2:4.17.12`, in the Debian snapshot archive:
  https://snapshot.debian.org/mr/package/samba/) configured with **SMBv1 (NT1) enabled** and
  **`server signing = disabled`** and a **guest-readable share** (like the simulator's existing
  `smb.conf` `map to guest = Bad User` + `[public] guest ok = yes`).
- Clean: a current Samba (bookworm `4.17` default, or trixie `4.24`) with SMBv1 off and signing on.

The existing simulator target already builds `samba` from `debian:12-slim`
(`docker/pi-simulator/target.Dockerfile`), so the weak/clean split is a `smb.conf` change plus a
second container, no new base image.

**`nmap -sV`.** `nmap-service-probes` names Samba as `p/Samba smbd/ v/3.X - 4.X/
cpe:/a:samba:samba` (lines 14104-14116) — a **version range, not an exact version**, so the CPE
has no concrete version and **vulners does not fire on Samba**. Samba findings come from NSE +
targeted, not vulners.

**Which Dmitri check / expected finding on the weak Samba.**
- `smb-protocols` -> `_extract_smbv1_finding` -> **high** "SMBv1 protocol enabled" (triggers on
  "NT LM 0.12" / "SMBv1" in output).
- `smb2-security-mode` / `smb-security-mode` -> `_extract_smb_signing_finding` -> **medium**
  "SMB signing disabled".
- enum4linux-ng (targeted, `nspi`/`extensive`) -> `targeted/smb.py`: **null/guest session**
  findings and **anonymously readable share** (the `[public]` share) -> "SMB share public is
  anonymously readable".

**Confirm the issue note (decision 5).** `smb-vuln-ms17-010` targets the **Windows** SMBv1
EternalBlue code path; it will **not** trigger against Samba (Samba is not the vulnerable Windows
`srv.sys`). So no MS17-010 finding will appear here. What the SMB checks **will** report on this
Samba instead: **SMBv1 enabled (high)**, **SMB signing disabled (medium)**, and from enum4linux-ng
**null/guest session + anonymous share read (medium/high)**. That is the honest Samba equivalent of
"weak SMB".

**RDP: `xrdp` on 3389.** Debian package `xrdp` (bookworm ships 0.9.21; pin an **older** 0.9.x from
the snapshot archive for the CVEs). `-sV` names it `p/xrdp/ cpe:/a:jay_sorg:xrdp/`
(nmap-service-probes lines 2269, 15159) — **no version captured**, so vulners again does not fire;
the xrdp CVEs below are *not* auto-detected.
What Dmitri detects on 3389: `rdp-enum-encryption` NSE (in `NSPI_NSE_SCRIPTS`) -> if it reports
weak/standard RDP security or "CredSSP not required", that surfaces via the generic extractor;
otherwise 3389 is a presence/identity signal.
xrdp CVEs for reference (NVD, not scanner-detected): CVE-2022-23613 (7.8), CVE-2022-23493 (9.1),
CVE-2020-4044 (7.5 sesman crash). https://nvd.nist.gov/vuln/detail/CVE-2022-23613

**arm64/amd64.** Samba and xrdp are Debian packages -> both arches. The simulator's existing Samba
target already proves the amd64 path; arm64 is the same Debian base. Verified runnable: Samba
**yes** (already in repo), xrdp **unverified (build)** but standard Debian package.

---

## 6. Network printer — MIXED: web page (CUPS) + raw 9100

**Web/IPP: CUPS.** Old `CUPS 2.3.x`/`2.4.x` for the weak web config, current CUPS for clean.
Image option: `olbat/cupsd` (Docker Hub, tags `*-amd64` and `stable-*-arm64`, updated 2026-10-12 —
**both arches present**). https://hub.docker.com/r/olbat/cupsd  Or build CUPS from a pinned Debian
snapshot version.

**`nmap -sV`.** The `ipp` probe matches `p/CUPS/ v/$1/ cpe:/a:apple:cups:$1` from the
`Server: CUPS/x.y.z` header (nmap-service-probes lines 11372-11373). So CUPS version **is**
captured on the web/IPP port -> vulners can match CUPS CVEs.

**CVE (NVD, web/scheduler, not the UDP cups-browsed ones).**
- CVE-2022-26691 — CVSS 6.7 — CUPS auth bypass / privilege issue, fixed in 2.4.2.
  https://nvd.nist.gov/vuln/detail/CVE-2022-26691
  (Note: the 2024 cups-browsed CVEs — CVE-2024-47076/47175/47176/47177 — ride **UDP 631 / IPP
  browsing**, which the TCP-only scanner cannot see. Keep the weak finding on the TCP web port.)

**Which Dmitri check / expected finding.** vulners on the CUPS version CPE (if egress allowed);
plus nikto/ffuf against the CUPS web admin and `http-methods` (CUPS admin exposes PUT/DELETE-like
verbs), and `http-title`/`http-server-header` identity.

**Raw 9100.** A plain JetDirect-style listener on TCP 9100 (e.g. a socat/ncat loop or p910nd).
**Important TCP-scan caveat:** `nmap-service-probes` line 29 is `Exclude T:9100-9107` — nmap
**excludes 9100 from service-probe traffic by default** to avoid printing garbage. 9100 is not in
`NSPI_PORTS` and not in Dmitri's extra port set, so unless 9100 lands in the top-1000 TCP SYN pass
it may not even show, and even when open it is version-less. Treat 9100 as a **presence-only**
printer-identity port; the detectable weakness is the CUPS web side.

**arm64/amd64.** `olbat/cupsd` both arches; raw-9100 listener is arch-neutral. Verified runnable:
CUPS **yes** (registry), 9100 listener **unverified (build)** but trivial.

---

## 7. Linux PC — FULLY CLEAN: current OpenSSH only (port 22)

**Software.** Current **OpenSSH** (Debian trixie `openssh-server` 9.x, or `linuxserver/openssh-server`
latest). Config: **key-only auth** (`PasswordAuthentication no`, `KbdInteractiveAuthentication no`),
modern KEX/cipher/MAC only, nothing else exposed.
Images: Debian base both arches; `linuxserver/openssh-server` is multi-arch (amd64/arm64).

**`nmap -sV`.** Names `p/OpenSSH/ v/9.x Debian.../ cpe:/a:openbsd:openssh:9.x`
(nmap-service-probes lines 3560-3566). With a **current** OpenSSH, vulners should return nothing
above `min_cvss`. If a brand-new low-CVSS advisory ever matches, it would show under `extensive`
(min 3.0) — keep the version current to avoid it.

**Which checks must report nothing.**
- `ssh-auth-methods` -> `_extract_ssh_auth_methods_finding` fires **only if "password" appears** in
  the methods. With `PasswordAuthentication no`, the method list is `publickey` only -> **no
  finding** (this is the whole point of key-only auth).
- `ssh2-enum-algos` + ssh-audit (targeted) -> with modern algorithms only, ssh-audit yields no
  fail/warn -> **no finding**.
- No other port open -> no other check.

Expected result: **zero findings**. This proves no-false-positive on a clean host. Verified
runnable: **yes** (standard Debian / multi-arch image).

---

## 8. Router/switch — FULLY CLEAN: current web admin (modern TLS) + current SSH

**Software.**
- Web admin: **OpenWrt LuCI** in a container — `openwrt/rootfs` (Docker Hub, tags like
  `armsr-armv8-openwrt-25.12` for arm64/aarch64 and `x86-64-openwrt-25.12` for amd64, updated
  2026-10-12). LuCI runs on **uhttpd**; put it behind current TLS. arm64 (aarch64) and amd64 tags
  both exist. https://hub.docker.com/r/openwrt/rootfs
  Simpler, lower-risk alternative: **current `nginx:1.27`** or **current `lighttpd`** serving a
  router-like admin page with a **modern, CA-or-fresh self-signed TLS 1.2/1.3** cert. nginx is
  multi-arch (`library/nginx:1.27`, amd64+arm64).
- SSH: current OpenSSH / Dropbear, key-only, modern algorithms (as device 7).

**`nmap -sV`.** nginx/lighttpd/uhttpd versions are captured; with **current** versions vulners
returns nothing above threshold.

**Which checks must report nothing.**
- `ssl-cert` -> not expired, not (ideally) self-signed; if self-signed is unavoidable in a lab,
  note that `_extract_ssl_cert_findings` emits a **medium "Self-signed TLS certificate"** even for
  a fresh cert. **To keep this device truly clean, use a cert whose subject != issuer** (e.g. a
  tiny internal CA), otherwise the self-signed rule fires. Flagged so "clean" stays clean.
- `ssl-enum-ciphers` -> TLS 1.2/1.3 only, no SSLv3/TLS1.0, no weak ciphers -> **no finding**.
- testssl.sh (targeted) -> modern config -> no `low/medium/high/critical` issue rows -> **no
  finding**.
- `http-methods` -> only GET/HEAD/POST enabled -> **no finding**.
- `ssh-auth-methods`/ssh-audit -> key-only + modern algos -> **no finding**.

Expected result: **zero findings** (provided the self-signed caveat is handled). Verified runnable:
nginx **yes** (registry); OpenWrt LuCI container **unverified (build/run)** — the rootfs image runs
but wiring uhttpd+LuCI+TLS in a container is non-trivial; the nginx/lighttpd option is the safer,
verified pick.

---

## Lab-wide risks and open questions

1. **vulners needs outbound internet.** Every CVE finding on devices 3 (MySQL) and 6 (CUPS), and
   any version-based CVE anywhere, depends on the scanner reaching `vulners.com`. The brief says
   "nothing exposed to the internet" — that is fine for *inbound*, but the agent container must be
   allowed *outbound* HTTPS or the weak devices show no CVEs. Decide the egress policy.
2. **Decision 1 (Schneider PLC) cannot meet both goals at once.** OpenPLC has real CVEs but (a)
   none are scanner-detectable (no OpenPLC CPE from `-sV`, generic `modbus` on 502) and (b) it
   **cannot** present a Schneider FC43 identity (no FC43/0x2B handler in `modbus.cpp`). A
   configurable FC43 Modbus server can produce the Schneider fingerprint + Modicon vulners match,
   but is not "old PLC software with its own CVEs". **User must pick** which property matters.
3. **Decision 2 (OPC UA / Beckhoff) is presence-only.** No nmap OPC UA probe and no Dmitri OPC UA
   check, so open62541's CVEs and the Beckhoff identity are both invisible to the scanner. This
   device cannot be a "weak device with a real finding"; it only proves port 4840 shows up.
4. **No build verification here.** The sandbox blocked Docker builds / third-party `git clone`, so
   source-built items (OpenPLC, open62541, xrdp, OpenWrt LuCI, 9100 listener) are
   `unverified (build)`. Registry-pulled items (MySQL, mediamtx, nginx, olbat/cupsd, openwrt/rootfs)
   are verified present with the stated architectures. A follow-up `docker build`/`docker pull`
   pass on an allowed host should confirm the build-path items before they land in compose.
5. **Secondary nuances:** 9100 is in nmap's default service-probe **exclude** list and not in
   `NSPI_PORTS`; Samba and xrdp get version *ranges* only (no vulners); the router's TLS cert must
   not be self-signed or `ssl-cert` will flag the "clean" device.

---

## Summary table

| Device | Software + version | weak/clean/mixed | Ports | Expected findings | Scanner check | Verified runnable |
|---|---|---|---|---|---|---|
| PLC (Schneider-like) | OpenPLC_v3 @ commit b4702061 | weak (intended) | 502, 8080 | ICS/Modbus exposure only; **no CVE finding, no Schneider FC43 identity** | modbus-discover + pymodbus inventory; exposure role | no (build) |
| Controller (Beckhoff-like) | open62541 v1.2.4 (OPC UA) | weak (intended) | 4840 | **none** — port exposure only (no OPC UA probe/check) | port scan only | no (build) |
| Database | MySQL 8.0.31 | weak | 3306 | several medium CVEs (CVE-2023-21875/21877/21880) | `-sV` CPE -> vulners | yes (hub, amd64+arm64) |
| IP camera | mediamtx 1.21.2 (RTSP) + old nginx/lighttpd web + TLS1.0 | mixed | 554, 80/443 | RTSP = identity only; web = TLS self-signed/weak-cipher, nikto/ffuf, version CVEs | ssl-cert, ssl-enum-ciphers, testssl, nikto/ffuf, vulners (web) | yes (mediamtx+nginx hub) |
| Windows-style PC | Samba 4.17 (weak, SMBv1+no signing+guest) & 4.17/4.24 (clean) + xrdp 0.9.x | mixed | 139/445, 3389 | SMBv1 (high), SMB signing disabled (medium), null/guest + anon share (enum4linux); **no MS17-010** (Samba, not Windows) | smb-protocols, smb2/smb-security-mode, enum4linux-ng; rdp-enum-encryption | partial (Samba yes, in repo; xrdp build) |
| Network printer | CUPS 2.3.x/2.4.x (weak) + current (clean) + raw 9100 | mixed | 631/80, 9100 | CUPS version CVE (CVE-2022-26691), nikto/http-methods; 9100 presence only | ipp `-sV` -> vulners, nikto/ffuf, http-methods | yes (olbat/cupsd hub); 9100 build |
| Linux PC | current OpenSSH 9.x, key-only, modern algos | clean | 22 | **none** | ssh-auth-methods, ssh2-enum-algos, ssh-audit all silent | yes (Debian/LSIO) |
| Router/switch | current nginx 1.27 (or OpenWrt LuCI) + modern TLS + current SSH | clean | 443, 22 | **none** (use non-self-signed cert) | ssl-cert, ssl-enum-ciphers, testssl, http-methods, ssh checks all silent | yes (nginx hub); LuCI unverified |
