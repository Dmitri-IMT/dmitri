# Remote agent updates — proposed architecture

Status: PROPOSED, NOT APPROVED. Planning only. TRUTH.md is the product boundary. Architecture approval does not provision production or authorize implementation.

Task breakdown was authorized on 2026-10-17 and is recorded in `TASKS.md`; product implementation
awaits the user's start command. The original evidence below used `b207a83`. The task ledger
was prepared on `a178aa6`, where the visible migration chain ends at `20260928_38`; revalidate
the effective source and migration parent before implementation. No architecture decision is
silently changed by this source-base difference.

## New files and naming

The exact E/N source paths and proposed test names are defined by the **Source map and proposed
ownership** and **Planned verification** tables in `INTEGRATION.md`. Those tables are the naming
source for `TASKS.md`; `DESIGN.md` adds the UI placement/verification paths. Installed appliance
paths are not repository source files. Publication workflow integration remains a human
infrastructure prerequisite, distinct from the locally testable publisher and package builder.

## Evidence and limits

Read on 2026-10-17: root AGENTS.md, architecture-agent profile, consult-docs and frontend-conventions skills, TRUTH.md, PROGRESS.md, code-map index, docs/README.md and only ADR-021/ADR-011 from the knowledge base. Selective source reads and `rg` checked the paths below. A read-only filesystem check covered all 90 repository paths in the integration/test tables: existing/new classifications matched. No tests, builds, scans, network access, SSH, services or secret files were used.

Source differs from historical ADR text: `hardware-agent/pyproject.toml` is **1.0.5**, not 0.1.4; this does not prove any published release. `packaging/build-deb.sh` builds an unsigned `Architecture: all` package and embeds a postinst that runs `uv sync --frozen`, enables the daily timer and restarts the agent. `apt-upgrade-agent` holds an exclusive flock and installs the unpinned APT candidate. CI builds a package and checks a version bump against main; it does not publish releases.

`backend/src/api/models/command.py` defines both Agent and scan-specific Command. Agent has no version fields. `agent_connections.py` holds hello/version only in memory. Hello models on both sides forbid extra fields. Existing admin gates, Ed25519 request authentication and device-detail UI are reusable. The source migration chain includes `20261010_40`, beyond the code-map's stated revision 38; the migration parent must be rechecked at implementation time.

## Release identity and trust

Use immutable stable releases of **hardware-agent**. Upstream version remains numeric `MAJOR.MINOR.PATCH` in pyproject.toml; proposed Debian mapping is `MAJOR.MINOR.PATCH-1`, for example app 1.0.6 → package 1.0.6-1. Every changed payload requires a new upstream version. No prereleases, epoch, build suffixes or revision-only rebuilds in this first contract. Use Debian version comparison, never lexical comparison. A UI update is strictly newer; only recovery may downgrade to the recorded previous version.

Release identity binds UUID, source commit, upstream/Debian versions, package name, architecture, suite, SHA-256, size, notes, required updater/protocol versions and publication time. Never replace bytes for a published `(package, Debian version, architecture)`. Reject duplicate identity with a different digest. Preserve prior artifacts and provenance when a release is withdrawn from new installation.

Proposed initial supported appliance: Debian 13, arm64, Python 3.12. Bootstrap must verify the actual appliance matches; its architecture and OS were **not inspected**. Change the builder to an arm64 package containing the application wheel, dependency wheelhouse, hash-pinned runtime requirements derived from uv.lock, and source. Build and validate those artifacts on a matching Linux environment; no source builds run on the Pi. Keep Python under `/opt/uv-python` and a pinned uv binary outside the agent tree; normal updates cannot replace either. Other platforms require separate validated release entries.

APT trust is **signed repository metadata**, not a mandatory signature on each .deb: trusted InRelease (or Release plus Release.gpg) → hashes of Packages → package SHA-256. Require a dedicated keyring and `Signed-By`, expected origin/suite, valid metadata dates/Valid-Until and HTTPS. Never use trusted=yes, allow-unauthenticated or disable expiry checking. The signed Release also hashes a bounded release-catalog.json; the backend verifies that chain and matching Packages entries before import. Persist a monotonic catalogue generation to reject older signed catalogues. TLS alone is insufficient.

Reuse `build-deb.sh` and the CI package gate. Proposed release pipeline: protected immutable version tag → version/source checks → arm64 build and offline install/recovery validation → artifact hashes/provenance → review/promotion → metadata signing → atomic repository snapshot publication → verified backend catalogue import. Signing runs in a separate protected job or human signing station; a build job does not receive the signing key. Credentials, signing access and hosting are prerequisites, not assumed resources. Catalogue approval is represented by inclusion in the promoted signed catalogue, not a browser-supplied flag.

Repository snapshots use content-addressed indexes, atomic metadata promotion and package paths that never change. Retain the current and every fleet-referenced recovery release; do not prune an artifact while a device/unfinished operation depends on it. Refresh signed metadata before expiry without changing package bytes. A backend worker imports only the configured repository; browser requests accept no repository or package URL.

## Permanent updater and manual policy

Extract the existing helper into a permanent companion Debian package, **hardware-agent-updater**, built by the same builder. Its independent numeric version comes from new `hardware-agent/packaging/updater-version`, with the same Debian `-1` mapping; it can remain Architecture: all because it uses distro runtime dependencies. Rebuild/publish it only under a new companion version. It owns `/usr/lib/dmitri/apt-upgrade-agent`, the lock-path contract, update service and timer; transfer ownership with version-bounded Breaks/Replaces during bootstrap. The new hardware-agent package depends on a compatible updater. Ordinary remote updates target only hardware-agent and cannot upgrade the updater itself.

The existing update service becomes a persistent root supervisor, started on boot before the agent. Use Type=notify: inspect the journal and reestablish any mutation gate before releasing startup readiness; full recovery can then start the agent for health verification without a unit-ordering deadlock. Local health handshakes do not acquire scan locks. Its helper starts `/usr/bin/python3 /usr/lib/dmitri/updater.py`, outside `/opt/dmitri-agent` and its virtualenv. The companion depends on distro python3, python3-cryptography, apt, ca-certificates and systemd. Bundle the existing signing.py in the companion as `/usr/lib/dmitri/device_signing.py`; reuse its Ed25519 canonical request format and existing device identity without importing from the replaced tree. Its runtime needs neither the agent environment nor uv. No remote shell or arbitrary argv facility is exposed.

The supervisor accepts bounded typed messages on a root-only local Unix socket, checks peer credentials, journals operations, owns package-manager children, performs local health checks and sends durable signed HTTP reports. It parses the existing environment format as data; it never sources it as shell code or logs credential values. It is independently restartable and remains installed during agent replacement.

Reconcile the current automatic timer in the **bootstrap release**: keep the daily timer, but point it at a new check-only unit. Checks refresh trusted APT metadata/cache and never install, stop or restart the agent. The helper's default mode is also check-only; install requires a valid admitted operation. Postinst must no longer re-enable an automatic installation path. Bootstrap verifies both loaded unit configuration and timer behavior. Existing unprepared devices retain their old behavior until this assisted migration; the web feature cannot change them retroactively. Legacy bootstrap needs an assisted maintenance window: verify scans/uploads/finalization are idle, stop old processes and retain identity/results before changing a tree whose old code may lack the lock contract.

## Admission, exclusion and process lifetime

Backend update admission and scan admission both lock the same Agent row with `SELECT FOR UPDATE`, then inspect active scan and update reservations. Update creation also uses a partial unique active-operation index and an idempotency constraint. Do not reuse Command or create a stub scan: updates have their own table, schemas, IDs and lifecycle. GET only reads projections; it performs no sweep, delivery, APT call or installation.

One API replica remains a prerequisite because the WS registry is process-local. A per-device async guard serializes session replacement, capable hello persistence, admission and the single frame send; DB work stays in the threadpool. Lock order is registry guard → Agent row. Recheck revocation, current socket/session and readiness before send and claim. A lost send is never retried on another socket. Before durable updater claim, an expired request cannot execute; after claim, disconnect means reconciliation is needed, not failure.

Reuse `/var/lib/dmitri/scan.lock` without unlinking/recreating its inode: scans take shared nonblocking locks; installation takes an exclusive nonblocking lock. Concurrent local scans retain today's shared semantics. A local scan wins → update refuses immediately; update wins → all scan paths refuse. APT/dpkg locks are an additional constraint, never files to delete. Timer checks and remote preflight share one updater transaction mutex. Bootstrap/provisioning uses the same exclusive appliance lock and cannot run beside an admitted update.

Extend the existing scan lease through **result persistence and finalization**: daemon → headless → ScanRunner holds it through upload and durable terminal-status acknowledgement; standalone headless owns it through `write_scan_result`; HomeScreen → ScanProgressScreen → ScanRunner retains it until the HomeScreen completion callback persists the result. Source currently releases the inner runner lock before the headless write, and TUI writes only on dismissal. Do not leave those gaps. A durable remote-scan checkpoint records command/scan IDs, phase, saved-result reference and pending terminal status. Replay/reconcile it before an updater claim after daemon restart; do not attempt to resume an interrupted Nmap pipeline.

Borrow the same lease through nested scan calls. Pass its shared FD explicitly to Nmap and targeted tool subprocesses; an orphan child must continue to block installation until it exits. Join scan children before releasing the parent lease. Updater exclusive FDs are close-on-exec and are not inherited by apt, dpkg, postinst or the restarted agent. The persistent updater service owns their cgroup with KillMode=control-group; restart waits for old children to stop before inspecting dpkg state.

Before any mutation, durably set a public, non-sensitive update gate while holding the exclusive lock. All packaged scan entrypoints acquire shared lock then check that gate and their process-start release identity against the current installed release. A stale idle TUI must restart before another scan. If the supervisor dies, the gate still blocks scans while its children are stopped and recovery reacquires the lock. Boot starts recovery before the agent. Never clear the gate solely because a PID or flock disappeared. Source checkouts remain outside appliance update support.

## Installation and recovery

The updater verifies the promoted release, local trust, package/version/hash, arm64/suite, minimum updater, current installed version, free space/inodes and package-manager health. Simulate the transaction first: reject removal, OS upgrades or changes to any package other than hardware-agent. A missing runtime/system prerequisite requires bootstrap. Cache and rehash **both** target and previous trusted .deb before mutation; refuse if the previous package is unavailable. Keep one last locally healthy source tree and virtualenv snapshot on the same filesystem. No application data or credentials belong in this snapshot.

Under the exclusive lock: journal the prior version and package state; stop the agent and wait for its process/cgroup to exit; snapshot source and `.venv`; then install the exact `hardware-agent=<Debian version>` from the verified cache with network acquisition disabled. Postinst replaces runtime uv sync with offline uv environment creation and hash-verified wheel installation from the packaged runtime requirements/wheelhouse; it cannot fetch Python/dependencies. It does not start the agent. Only the updater restarts after dpkg reports fully configured and the virtualenv reports the expected version. Pin by explicit version/digest and restrict origin/package; no candidate-only install or unbounded dependency repair.

Local health requires a new fixed read-only `dmitri health --json` command (imports, version, config readability and results-directory access; no scan or secret output), fully configured dpkg status, active expected systemd invocation, and a local readiness handshake from that MainPID reporting the target app/package version. The process need not reach the backend to pass local health. The companion records invocation ID and health nonce so an old process cannot satisfy a new verification.

Pre-mutation failure leaves the running agent unchanged. After mutation begins, an install/postinst/uv/local-health failure stops the new agent and attempts **one controlled recovery**. Reinstall only the cached previous .deb, allow that exact downgrade, and configure only hardware-agent offline. The updater then restores the matching saved tree/virtualenv at their original paths, verifies dpkg and local health, and restarts. Restoring the old virtualenv avoids network rebuild and invalid shebang relocation. The shared Python installation and uv are never removed. A failed dpkg configuration is not hidden by a healthy-looking copied environment.

Do not run unrestricted `apt --fix-broken install` or configure unrelated packages. On an interrupted dpkg journal, inspect actual package status and finish/recover only this transaction after all old children exit. If dpkg is corrupt, needs unrelated repair, storage is damaged, memory is insufficient again, or recovery health fails: keep the mutation gate, preserve artifacts/evidence and report `needs_intervention`. No restart/install loop. A failed preflight due to low memory/space does not begin installation; an OOM during uv is handled from the surviving supervisor or its boot journal using the saved environment.

Journal every boundary before the side effect and commit local outcome before releasing the gate. Use SQLite durable transactions plus fsynced snapshots/atomic gate replacement; reserve room for the journal before work. After power loss, inspect journal + dpkg + snapshots, then resume verification/recovery rather than blindly rerun install. Retain target, prior package, prior environment and unacknowledged events until confirmation/recovery is resolved; keep the last known-good recovery set afterward. Never prune device identity, `/etc/dmitri/agent.env`, `/var/lib/dmitri` results/logs or user-configured result paths. Only updater-aware packages with compatible recovery hooks qualify as a recovery baseline; the current online-uv postinst needs assisted bootstrap first.

This is package-level recovery, not an atomic OS update. It cannot guarantee recovery from SD-card failure, torn filesystem/dpkg state, power loss during repair, or unsupported Python/OS changes. Such cases require assisted recovery and possibly physical access. Signed artifacts and journals improve diagnosis; they do not remove that limit.

## Durable outcome and rollout boundary

The updater posts sequenced events directly using device-signed HTTP, retrying with a fresh nonce and persisting the acknowledgement. Agent WS may show progress but is never the sole owner of finalization. Local success enters `awaiting_confirmation`; backend success requires both durable local health and a matching current-session hello for the same operation/invocation/target version. Either fact can arrive first. Backend/network outage alone leaves confirmation pending and never triggers rollback. Local scans can resume after verified local completion; the backend keeps new remote mutations reserved until it reconciles the outcome.

Deploy order proposed for later authorization: verified distribution/bootstrap prerequisites → additive backend/migration accepting legacy hello → assisted updater-aware bootstrap with timer reconciliation → capability-gated device UI → one canary release → wider manual use after recovery evidence. Legacy hello continues to support scans; it never implies update capability. A new agent probes backend update-protocol support before sending extended hello, since an old backend forbids extra fields. Companion upgrades and protocol breaks require a separate assisted maintenance path.

ADR-021 needs a future amendment for repository-metadata trust wording, manual default/check-only timer, Debian version mapping, companion ownership, durable state, offline recovery and local versus remote health. ADR-011 must document additive update frames and session fencing without changing scan Command semantics. Do not edit either ADR in this planning stage.

## HUMAN_INFRA_REQUIRED

No operational release is promised. These decisions and evidence are still required:

| Human choice / prerequisite | Verifiable completion evidence |
|---|---|
| Repository hosting, HTTPS origin, suite and availability/retention owner | Public metadata/package fetch from a clean test appliance; atomic publication and retained prior artifacts demonstrated |
| Signing authority: protected CI signer or human signing station; key custody, rotation and revocation policy | Approved public-key fingerprint, protected signing procedure and valid/invalid/expired metadata acceptance evidence; no private key in repo/build logs |
| Publication/promotion rights and protected tag/environment rules | Authorized release owner, immutable version collision refusal and catalogue promotion audit |
| Initial Pi OS/architecture, runtime and distro updater dependencies | Inventory confirms support; Python 3.12, pinned uv, system Python/cryptography, disk/memory and previous-release cache verified |
| Assisted bootstrap owner/access and initial trust distribution | Out-of-band fingerprint verification, signed repository configured, companion/agent pair installed, old automatic timer removed, identity/results retained |
| Canary and assisted recovery access | Offline failure/reboot evidence and a person able to recover the appliance if package recovery fails |

Hosting, signing method and bootstrap access are genuine unresolved production blockers. None was probed, provisioned or assumed available. Architecture approval resolves none of them by itself.
