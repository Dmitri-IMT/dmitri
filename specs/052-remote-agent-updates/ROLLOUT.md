# Operational rollout — remote agent updates

Status: **preparation in progress; production rollout not complete**. Evidence date: 2026-10-20.
The user authorized work needed for real use and selected GitHub Pages in Dmitri-IMT plus a
new official signing key with user-owned custody/recovery. Protected Pi sudo access is
confirmed; the actual production backend target remains a gate. No deployment is claimed.

Distribution uses GitHub Pages from **`Dmitri-IMT/dmitri`**, with expected repository base
**`https://dmitri-imt.github.io/dmitri/`**. Verify the actual HTTPS deployment before configuring
clients. The empty public `Dmitri-IMT/agent-releases` repository is reserved and unused:
organization policy rejected a deploy key (422). Do not weaken that policy, add a broad user
token to workflows, or delete the reserved repository. Same-repository `GITHUB_TOKEN`
permissions support the release path without cross-repository credentials.

Authoritative managed APT state belongs on isolated **`agent-apt-state`** in the source repo;
never execute code from this data branch. The protected environments
**`agent-release-signing`** and **`agent-release-publishing`** exist with reviewer **`Chambs`**
and deployment rules for branch `main` and tags `agent-v*`. Verify actual rules at execution.
The release workflow publishes from protected `main` pushes that change agent source, package
inputs, or `hardware-agent/pyproject.toml`; it does not require a release tag. Each intended
agent release must bump `hardware-agent/pyproject.toml` because published APT package identities
are immutable. Build has no signing secret or write permission.

The coordinating agent generated the official certification-only primary fingerprint
**`92BD91D03608EA3AFDB108AAB7EEC4E4E954DA7A`** and signing-only subkey fingerprint
**`49B97982F566B0FEF9F2412FDC0B27B955B74936`** in protected local AppData outside OneDrive/git.
Signing-subkey-only export (`sec#`) and sign/gpgv self-tests passed. Only that subkey and its
passphrase are stored in `agent-release-signing`; the primary secret stays outside CI.
The user owns offline primary/recovery custody. Remove any unusable deploy-key secret.

The user prepared the Pi sudo credential at
`$env:LOCALAPPDATA/Dmitri/credentials/rasp-sudo.xml` with Windows DPAPI. Its existence and
successful protected sudo use were confirmed by the coordinating agent. Do not commit, copy to OneDrive, print
or pass the decrypted credential on a command line.

## Evidence and boundaries

Source inspected on `feature/remote-agent-updates`, HEAD `77dfe5a`, with approved Tasks 13/14
changes present in the working tree. Preserve those changes. A build from this dirty tree
cannot truthfully use `77dfe5a` as its sole source provenance. Complete review, commit the
release payload, and build from that clean committed source before a production publication.

Read: root `AGENTS.md`, `.agents/skills/consult-docs/SKILL.md`, canonical code-map index,
`docs/README.md`, ADR-021 and ADR-007, feature ARCHITECTURE/INTEGRATION/TASKS/PROGRESS,
packaging/provisioning sources, backend catalog/worker/config/deployment sources and CI.
The architecture document still has historical proposed-status wording; Tasks 1–14 and their
approval evidence are in TASKS/PROGRESS. Historical ADR-021 describes automatic installation;
the implemented manual-update/check-only policy must be reflected in the operational runbook.

Read-only inventory supplied by the coordinating agent:

| Surface | Observed | Remaining gate |
|---|---|---|
| Pi access | SSH `dmitri@dmitri.local` with local `~/.ssh/dmitri-codex` succeeds; root SSH unavailable; protected DPAPI sudo use confirmed | Idle maintenance window and verified recovery baseline |
| Pi platform | Debian 13/trixie, aarch64; approximately 24 GB disk free and 1.6 GB RAM available | Confirm inodes, package-manager health, current scans/uploads/finalization and recoverable backup in maintenance window |
| Installed agent | `hardware-agent` 1.0.5, Architecture all; no companion; root-owned persistent scan lock; old timer targets install service | Assisted migration; existing package is not an updater-aware rollback baseline |
| Runtime | Python 3.12.15 under `/opt/uv-python/cpython-3.12.15-linux-aarch64-gnu/bin/python3.12`; required `/opt/uv-python/bin/python` absent; uv 0.12.24 | Prepare stable Python path and pinned uv 0.11.20 without removing the existing runtime |
| GitHub | Public `Dmitri-IMT/dmitri`; authenticated organization admin; protected main; empty agent-releases reserved; deploy keys disallowed | Configure Pages from source repository and retained agent-apt-state branch |
| GitHub environments | agent-release-signing and agent-release-publishing created with reviewer Chambs and main/agent-v* deployment rules; signing subkey/passphrase installed only in signing environment | Verify effective environment/tag rules and least job permissions; unrelated Dmitri / nspi is not the release trust boundary |
| Backend | Local API/worker/database Docker exists; local container has gpgv/dpkg/apt-cache but no update env configured; repository describes Railway deployment; actual production target not verified | Identify project/environment/API/worker/frontend, access, running commit and DB migration head before mutation |

Absence of a visible scan process is a point-in-time observation, not authorization to stop
an active command or proof of durable finalization. Do not print device identity secrets,
private signing material, backend credentials or environment-file contents into evidence.

## Ordered implementation and gates

### R1 — correct operational packaging and bootstrap

Exact files: `hardware-agent/packaging/build-deb.sh`,
`hardware-agent/scripts/provision-pi.sh`, `hardware-agent/packaging/updater.py`,
`hardware-agent/packaging/dmitri-agent-update.service`,
`hardware-agent/packaging/dmitri-agent-update.timer`,
`hardware-agent/packaging/dmitri-agent-update-check.service`,
`hardware-agent/tests/unit/test_update_scripts.py`,
`hardware-agent/tests/unit/test_updater.py`,
`hardware-agent/tests/integration/test_update_recovery.py`.

Concrete gaps found in source:

1. Bootstrap installs caller-supplied local packages without verifying an approved hash or
   binding the agent package to the authenticated fixed repository. Establish the approved
   public-key fingerprint out of band, install a root-owned dedicated keyring under
   `/etc/apt/keyrings`, and one source with HTTPS, `Signed-By`, suite `stable`, component
   `main`. The companion currently requires Release Origin **Dmitri** and Suite **stable**;
   do not choose another origin without changing and verifying that contract. Verify package
   name/version/architecture/digest from authenticated metadata before local installation.
   Extend `publish-apt.sh` to include the companion in the signed Packages index: its current
   `package_control()` accepts only hardware-agent/arm64 and prepare accepts one agent package.
   Add an explicit companion input, independently versioned hardware-agent-updater/all identity,
   immutable content-addressed pool bytes and provenance. Keep the browser/catalog admission
   contract agent-only. Filter publisher verification by package/version/architecture, not
   version alone: agent and companion may use the same numeric version. Authenticate both
   bootstrap packages through the approved signed snapshot, never a locally invented hash.
   Copy the public key and both DEBs into root-owned private staging before validation.
   Fingerprint verification, keyring installation, package authentication, dpkg installation
   and recovery-cache seeding must consume those same protected copies. Replacing caller
   inputs after validation must not change any consumed bytes.
2. Bootstrap does not disable the loaded legacy automatic-install timer before migration,
   enable/start the new check timer afterward, or verify its loaded `Unit=` target. Stop the
   legacy timer/service while idle, hold the existing scan-lock inode for mutation, reload
   units, then verify the timer targets `dmitri-agent-update-check.service`. A manual check
   must change metadata only, with agent MainPID/invocation and package versions unchanged.
3. Bootstrap never seeds the recovery cache. `_accept_update` requires both
   `/var/lib/dmitri/updates/cache/<installed-package-version>.deb` and its `.sha256` manifest.
   Seed the newly installed updater-aware bootstrap release only after authenticating its
   bytes; fsync the package and manifest, preserve restrictive ownership/mode, and prove the
   installed version matches. Do not create a manifest that merely blesses arbitrary input.
   The legacy 1.0.5 Architecture-all package is retained for assisted recovery, not promoted
   into the normal arm64 rollback chain.
4. `Updater.inspect()` derives readiness from source/keyring/platform and active state; it
   does not prove the previous package/cache exists or matches the installed package. Tie
   advertised installation readiness to the prepared recovery baseline as well. A device
   must not offer a manual update known to fail `previous_package_unavailable` immediately.
5. The supervisor uses `Type=notify` correctly in source: initialization and socket binding
   precede READY; recovery starts afterward. It is static (no `[Install]`) and is pulled in
   by the enabled agent's `Requires`/`After`. Make this lifecycle explicit in provisioning
   and verify it on real systemd; absence of `[Install]` alone is not a proven boot defect.

Gate: disposable Debian 13 arm64 environment with real systemd and signed test repository.
Verify legacy ownership transfer, unchanged lock inode, legacy timer suppression, offline
agent postinst, check-only timer, boot ordering, agent readiness bound to MainPID/invocation,
and interrupted-update recovery before agent scan admission. Preserve identity/results and
an assisted restore baseline. Never inject a destructive failure into the production Pi.

### R2 — restore CI and implement protected release publication (H6)

Exact files: `.github/workflows/ci.yml`, new `.github/workflows/agent-release.yml`,
`hardware-agent/packaging/build-deb.sh`, `hardware-agent/packaging/publish-apt.sh`,
`backend/tests/test_agent_updates.py`, dependency manifests as needed.

Current agent-package CI is incompatible with the builder: it supplies neither pinned uv
0.11.20 nor Python 3.12/arm64 execution, expects upstream version without `-1`, and searches
for companion-owned files inside the agent package. Build both packages on matching arm64
Linux; verify agent `MAJOR.MINOR.PATCH-1`/arm64 and companion independent version/all, correct
file ownership, wheelhouse/hash requirements and installed final-path entrypoint. An explicit
cross build can produce artifacts but is not arm64 install/health evidence.

Backend zero-skip CI installs backend dependencies only. The integrated update test imports
`pymodbus` and `ssh_audit` through `pytest.importorskip`; install the required agent integration
dependencies in the same backend test environment so this coverage executes. Keep the
zero-skip gate. Use PostgreSQL `dmitri_test` and the repository database preparation workflow.

Release flow must have separate jobs and permissions:

1. On a protected `main` push that changes release inputs, validate clean committed source and
   the semantic version in `hardware-agent/pyproject.toml`. Bump that version for every agent
   release; never reuse an immutable published APT package identity.
2. Build/test arm64 artifacts without signing or publication credentials. Record commit,
   UUID, package versions, hashes/sizes, tool versions and test evidence.
3. Signing job uses `agent-release-signing`, read-only source/state access and no hosting
   permission. Verify artifact identity/hashes and the existing signed authoritative state
   before preparing the next candidate. Sign Release/InRelease and verify with the approved
   public keyring. Never run code restored from `agent-apt-state` or import the primary key.
4. State-publish job uses `agent-release-publishing` and its own job-scoped `GITHUB_TOKEN`
   with `contents: write`, without signing secrets. Independently verify/promote the signed
   candidate, compare its base to the current state branch, then update `agent-apt-state`
   without force-push. Retain a publishable artifact/retry path if deployment fails afterward.
5. Pages deployment consumes the verified flattened artifact and uses `pages: write` plus
   `id-token: write`, without signing secrets or cross-repository credentials. Configure
   Pages source as GitHub Actions. Record actual HTTPS acceptance results after deployment.

Use a shared workflow concurrency group for releases and metadata refresh, with
`cancel-in-progress: false`. Serialize state promotion; the publisher's local flock
does not serialize different CI runners. Restore the authoritative current catalog, retained
pool and by-hash indexes before prepare; starting each run with an empty repository loses
generation/retention and conflicts with backend replay protection. Protect the signing
environment and tag namespace; an unprotected environment name is insufficient.

For GitHub Pages at `https://dmitri-imt.github.io/dmitri/`, prepare a deployment artifact with symlinks flattened to regular
files: the publisher's managed `dists/stable` is a symlink into `snapshots/`. Exclude signing
homes, `.staging`, locks and secret files. Retain all referenced pool and by-hash content.
Prove publication consistency from actual HTTPS reads; local atomic rename is not proof of
hosting atomicity. Readers reject mismatched metadata rather than install it.

Implementation gate: local workflow/permission checks and signed fixture publications retain
prior release bytes and increase catalog generation; repeated package identity with changed
bytes and stale-candidate promotion fail. Verify the arm64 build/install path and execute the
backend integration coverage without skips. This approves the implementation, not a release.

Release gate, required before O4 completes: protected CI passes on the committed source;
official publications retain prior bytes and increase generation; clean appliance APT and
backend import verify the actual hosted signature/hashes. CI execution and official hosting
follow the reviewed source commit, so they must not be treated as pre-commit evidence.

### R3 — production backend and frontend

Exact files: `backend/railpack.json`, `backend/railway.api.toml`,
`backend/railway.worker.toml`, `backend/src/api/core/config.py`,
`backend/src/api/services/release_catalog.py`, `backend/src/api/services/worker.py`,
`backend/alembic/versions/20261017_41_remote_agent_updates.py`,
`backend/alembic/versions/20261018_42_merge_evidence_and_deletion.py`,
`backend/alembic/versions/20261019_43_update_authorization_expired.py`,
`backend/.env.example`, `backend/agent-release/public-keyring.gpg`,
`backend/tests/test_release_catalog.py`, `backend/tests/test_settings.py`,
`.github/workflows/agent-release.yml`, `hardware-agent/tests/unit/test_release_workflow.py`,
frontend deployment configuration and runtime environment; factual runbook updates in
`docs/cloud/railway/SETUP.md`, `docs/PI-INSTALLER.md`, `docs/PI-RECOVERY.md`, and
`docs/adr/ADR-021-pi-agent-updates.md`.

Verify migration file names/head against source before execution; current terminal revision
is `20261019_43`. Identify the actual production deployment and take a database backup before
applying migrations. Keep one API process/replica: the live WS registry is process-local.

The shared Railpack image installs runtime `gpgv`, `dpkg` (Debian version comparison), and CA
certificates. The single approved keyring at `backend/agent-release/public-keyring.gpg` must be
part of both API and worker images at `/app/agent-release/public-keyring.gpg`, and the release
workflow must consume that same asset. A keyring path setting alone does not deploy the file.
Set, consistently:

- `AGENT_UPDATE_REPOSITORY_URL`: chosen fixed HTTPS repository base.
- `AGENT_UPDATE_KEYRING_PATH`: deployed readable dedicated public keyring.
- `AGENT_UPDATE_ORIGIN=Dmitri`, `AGENT_UPDATE_SUITE=stable`.
- `AGENT_UPDATE_REFRESH_INTERVAL_SECONDS`: configured operational refresh interval (default 300).

The worker imports/verifies the catalog and expires unclaimed requests; API GETs do neither.
Deploy API and worker from the same reviewed commit, then frontend with its actual API URL.
Prove worker import persists catalog generation/digest/validity; bad/expired signatures must
fail closed. Verify legacy Pi still connects and scans remain available before bootstrap.
Do not perform a real scan merely to test deployment. Use health, protocol and read surfaces.

### R4 — assisted bootstrap on the real Pi (H3/H4)

Depends on verified hosting/fingerprint, R1–R3, privileged access and idle maintenance window.
Preserve `/etc/dmitri/agent.env`, `/var/lib/dmitri`, results at configured paths, installed
package metadata and current tree/venv/system units. Backup ownership/modes must protect
device secrets. Prepare `/opt/uv-python/bin/python` to use the existing Python 3.12.15 and
uv 0.11.20 at `/usr/local/bin/uv`; retain the previous runtime for assisted restoration.

Install the authenticated offline bootstrap agent plus companion, retain its exact agent
package as normal recovery baseline, and start supervisor/agent/check-only timer. Confirm
fully configured dpkg state; active systemd units; persistent healthy journal; readiness
handshake; check-only timer; signed repository metadata; exact installed package/cache hash;
same device registration, credentials and results. Prove a reboot starts the supervisor and
restores its gate before agent admission. Obtain current accepted hello with arm64/stable,
compatibility level 1, package version and `agent_update_v1`. Version alone is insufficient.

### R5 — canary, retention and continued operation (H5)

Use two independently versioned, committed, signed updater-aware releases. Bootstrap the
earlier release; publish the later release; request one update through the admin UI/API.
Do not simulate an update by reusing a version with changed bytes. Record operation UUID,
claim/events, installed version/digest and invocation, durable local health, and backend
`succeeded` after matching current-session hello. Preserve privacy in recorded evidence.

Validate package failure/rollback and interrupted recovery on the disposable arm64/systemd
appliance first. Record who can perform assisted recovery on the real Pi and how to reach
them. Expand only after the real canary succeeds and retention/recovery evidence is complete.

Schedule signed metadata refresh before expiry using `publish-apt.sh prepare` without a new
package, then sign/promote/publish from the retained current repository. Default validity is
7 days (accepted range 1–30); choose an owned schedule with alerting and adequate margin.
Track HTTPS reachability, signature/expiry, catalog import age, update phase/contact age,
disk/inodes and recovery availability. Keep current and all fleet/unfinished-operation
referenced releases, snapshots, recovery packages and by-hash indexes; do not prune by age
alone. Document signing custody, rotation/revocation and emergency withdrawal procedure.

## Sequential coder pipeline

Use one coder task at a time; independent test/review follows each task before the next.
Infrastructure operations run only after the relevant local code and gates pass.

| Task | Status | Dependency | Review rejections |
|---|---|---|---|
| O1 | COMPLETE — independent final review APPROVE | Approved development Tasks 1–14 | 2 |
| O2 | COMPLETE — implementation and local review APPROVE | O1 approval | 0 |
| O3 | COMPLETE - local gates and independent review APPROVE | O2 approval | 0 |
| O4 | PARTIALLY_PREPARED — trust/environment setup only | O1–O3; user recovery custody | 0 |
| O5 | PENDING — production access unavailable | O1–O4; authorized Railway owner | 0 |
| O6 | PENDING | O5 verified baseline and deployment | 0 |

| Task | Exact scope | Completion gate |
|---|---|---|
| O1 | R1 publisher companion support, bootstrap authenticated packages/cache, timer migration and truthful readiness; package/provision/updater tests | Signed test snapshot with both packages; legacy migration and verified cached rollback baseline; real systemd ordering/recovery test |
| O2 | R2 CI repairs and release workflow; source repository workflow plus Pages export/publication tooling | Local workflow credential separation checks, arm64 package/install evidence, backend integration zero skips, immutable publication and refresh/retention fixture tests |
| O3 | R3 backend runtime tools/public keyring delivery and deployment runbook; installer/recovery/ADR-021 factual update | Tool/keyring delivery and signature smoke checks, tested migrations, accurate env/runbook commands; no secrets in source; actual deployed-image verification remains O5 |
| O4 | Official key/release environments already prepared; finish same-repo agent-apt-state and Pages setup | Protected CI on committed source; user-owned offline primary/recovery copy, approved fingerprint, effective reviewer/tag rules; actual HTTPS signed snapshot verified |
| O5 | Reviewed committed source, production API/worker/frontend deploy and Pi assisted bootstrap | Actual deployment identified, backup/migration evidence, idle lock/identity/results preservation, signed baseline, check-only timer and capability |
| O6 | Canary release and steady operation | Real manual update reaches confirmed succeeded; previous package retained; refresh schedule and assisted recovery contact operational |

O1–O3 can proceed while production backend access is identified. Protected sudo is ready. Creation
of the official key establishes trust identity and requires a protected recovery copy before
use. Package publication makes version bytes immutable. Applying production migrations,
stopping the legacy agent, replacing runtime/packages and rebooting cross the actual-device
boundary; execute only after their listed verified prerequisites. User authorization already
covers this work; no separate plan approval is required.

## Access and evidence still required

| Item | Needed before |
|---|---|
| Selected GitHub Pages in source repository: configure Actions source, agent-apt-state and actual HTTPS URL; designate availability/retention owner | H1 publication and deployment configuration |
| Official key generated and subkey-only CI export tested: verify user recovery custody and effective environment/tag rules; remove unusable deploy credential | H2 signing and trust-root provisioning |
| Protected DPAPI sudo use confirmed: verify idle maintenance window and maintenance/recovery contact | H4 bootstrap and actual systemd/reboot evidence |
| Verified Railway project/environment/services and authorized access | Production migrations/configuration/deploy |
| Reviewed committed release source and protected promotion/tag procedure | Truthful source provenance and H6 publication |

Completion requires evidence for H1–H6, a successful real canary, and a retained recovery
baseline. Tasks 1–14 passing alone do not establish these operational facts.

## Execution log — 2026-10-20

- O1 implementation is in progress; no appliance package or runtime has been changed.
- The user-owned DPAPI sudo credential was saved outside the workspace and authenticated
  successfully. Privileged read-only inventory confirmed an empty dpkg audit, synchronized
  clock, no scan-finalization checkpoint or update gate, and ample disk/inodes.
- The appliance currently reports to `http://192.168.15.153:8000`. Its registration and
  results will be preserved; switching to production requires verifying the production
  device identity first. Local database revision is `20261018_42`.
- `https://dmitri.peirce.dev` currently serves a frontend configured for
  `https://api.peirce.dev`; production API health returned `status=ok`. Railway CLI
  authentication is pending; no production migration or deploy has been performed.
- The official primary and signing subkey were generated with protected local recovery
  material outside OneDrive/git. Both primary-home and exported-subkey signing self-tests
  passed GPG verification. The CI export has an unavailable primary secret (`sec#`).
- `agent-release-signing` holds only the signing subkey/passphrase and requires reviewer
  `Chambs`; `agent-release-publishing` requires the same reviewer and has no signing secret.
  Both admit only `main` and `agent-v*` refs. Public fingerprint/repository/state variables
  are configured in GitHub.
- GitHub Pages is enabled at `https://dmitri-imt.github.io/dmitri/` using workflow builds;
  HTTPS is enforced, but no repository snapshot has been published. Rulesets
  `agent-release-tags` and `agent-apt-state-history` prevent tag mutation/deletion and
  state-branch force-push/deletion respectively.
- The earlier empty `Dmitri-IMT/agent-releases` repository remains reserved and unused.
  Organization deploy-key policy was respected. The unused deploy key/secret was removed;
  publication will use job-scoped permissions in the source repository.
- Independent O1 testing ran the publisher/bootstrap/updater/recovery scope with **102
  passed, zero skipped**, including disposable Docker dpkg rollback and signed HTTPS APT
  checks. Scoped Ruff, Black 24.3 and shell syntax checks passed. Windows `git diff --check`
  passed; its LF/CRLF conversion notices do not represent whitespace failures.
- A subsequent regression using the real APT helper return contract exposed a readiness
  defect: `inspect()` treats the returned keyring path as the repository suite. The regression
  initially failed. The corrective round now reports `stable` only after authenticated suite,
  recovery-cache and agent-configuration verification. Its 63 updater tests passed; an
  independent rerun of the three-file O1 scope passed **102 tests, zero skipped**. O1 is not
  yet approved.
- Disposable Debian 13 arm64 package-index retrieval succeeded. Actual systemd lifecycle,
  legacy timer migration, startup ordering and recovery evidence remain outstanding. No
  production runtime or Pi package has been changed.
- A native Debian 13 disposable container successfully booted real systemd as PID 1.
  The tester exercised repository units and the real supervisor, legacy-to-check timer
  replacement, supervisor startup through agent dependencies, unchanged scan-lock inode and
  a durable interrupted-operation recovery gate. The agent executable and the first metadata
  check helper were fixtures, so this alone does not prove a real daemon or signed metadata
  check. ARM64 systemd reached D-Bus availability under emulation; its lifecycle checks are
  still in progress. All these changes are confined to disposable containers.
- The ARM64 Docker run proved legacy-to-check timer migration and unchanged lock inode.
  It could not run the unmodified hardened updater unit: systemd reported `226/NAMESPACE`;
  distro units also reported `243/CREDENTIALS`. This is unavailable lifecycle evidence,
  not a passing appliance test. The tester removed its disposable containers/images.
  A full-system ARM64 VM using the official Debian 13 image (SHA512 verified) is being
  prepared to test the existing service protections without weakening them.
- The user confirmed they do not have Railway access and cannot authorize the CLI now.
  The second device code expired. Production configuration, migrations and deployment
  require an authorized project owner; no further login attempt is pending. Local coding,
  review and deployment instructions can continue independently of that access.
- O1 review round 1: **REJECTED**. One blocking code finding: caller-controlled key and
  package paths were reopened after authentication, allowing input replacement between
  verification and installation/cache seeding. A fresh coder is staging all three inputs
  privately before validation and adding replacement regressions. The separate ARM lifecycle
  evidence gap remains open; no service hardening will be removed to make the test pass.
- The full-system ARM64 VM is reachable over its isolated SSH port. It reports `aarch64`,
  systemd `running`, Python 3.13.5 and distro cryptography 43. This establishes test-platform
  availability only; the updater lifecycle/recovery assertions still require independent
  execution. Its base image and ephemeral test identity remain outside the repository.
- The user explicitly confirmed that the Raspberry is a test/validation appliance and
  authorized necessary hardware changes. Protected sudo is already available; no plaintext
  credential is recorded here. Preserve existing device identity/results through migration.
- During the input-staging corrective round, an overly broad test patch damaged
  `test_update_scripts.py`. That coder stopped and saved a snapshot. Recovery from the
  original O1 coder's exact test changes is in progress; collection is not currently green.
  No package deployment can proceed from this intermediate state.
- The damaged test source was recovered from HEAD plus eight exact original coder patch
  calls, with original formatting restored. Its function set and source size match the
  preserved pre-corruption bytecode after CRLF normalization. Recovery artifacts are at
  WSL `/tmp/o1-corrective-1792523294`; the recovered baseline passed all 35 original cases.
- The subsequent staging correction passed **38 script tests, zero skipped**. It validates
  root-owned `/` and `/run` before creating private staging, avoids chmod on existing
  parents, and uses the protected copies for every authentication/installation/cache read.
  New regressions replace original inputs and reject unsafe staging parents. Independent
  retesting and full-system ARM64 validation are in progress; review approval is pending.
- Independent retesting passed **105 tests, zero skipped**, without repository changes.
  The full ARM64 VM now executes the actual hardened supervisor and metadata-check unit.
  Signed HTTPS APT refresh succeeded after correcting the external test server's TLS
  shutdown behavior. Check-only execution preserved service MainPID/InvocationID, installed
  versions and the scan lock; the legacy installer stayed inactive.
- ARM64 readiness exposed a product parser defect: APT's installed-version row starts with
  `***`, which `_verify_apt_origin_suite()` does not recognize. It rejects the authenticated
  installed recovery baseline as `metadata_unavailable` while accepting the newer uninstalled
  version. A focused corrective round and installed-marker regressions are required before
  repeating readiness/recovery validation. This is not a passing O1 readiness gate.
- The installed-marker correction passed **65 updater tests**. Its two new cases cover the
  installed non-candidate version and refusal to inherit another version's repository trust.
  Independent ARM64 rerun then passed hard readiness assertions (`true`, `stable`, `arm64`,
  not blocked), check-only identity/version invariants, durable recovery and real scan-lease
  refusal. Evidence: WSL `/tmp/dmitri-o1-arm-vm/validation.log`.
- O1 review round 2: **REJECTED, evidence only**. Both code fixes and five targeted
  regressions/scoped gates passed review. The remaining R1 criterion is offline agent
  postinst on ARM64 with genuine uv 0.11.20 and Python 3.12; the native Docker test used
  simulated uv and the VM lifecycle agent fixture had no agent postinst. The tester is
  preparing the genuine toolchain before running that installation with networking blocked.
  Full production-daemon/canary behavior remains an O5/O6 gate.
- Gate ordering clarified before O2 implementation: O2/O3 implementation reviews use local
  reproducible tests. Actual protected CI and official hosted signatures remain mandatory
  O4 gates after a reviewed source commit; actual production-image/runtime verification
  remains O5. This prevents a pre-commit implementation task from claiming deployment
  evidence that cannot exist yet. No publication, deployment or canary gate was removed.
- O1 final evidence: current `hardware-agent_1.0.7-1_arm64.deb` built for Debian 13 arm64;
  actual `DEBIAN/postinst` completed under `unshare -n` with genuine uv 0.11.20 and CPython
  3.12.15, installing all 27 hash-pinned dependencies and the app wheel from the local wheelhouse.
  Final venv shebang and CLI smoke check passed. Pi `agent.env`, results, cache and scan-lock
  hashes stayed unchanged; lock inode/mode/size stayed `65025:131348:0:644`. The synthetic
  package tree/unit were restored and timer, update and agent services are active. Independent
  final reviewer returned `[APPROVE]`; the missing consolidated tee transcript does not invalidate
  the command output and independent smoke/hash/service evidence. O1 is complete; no production
  package was changed. O2 CI/release implementation is now in progress.
- O2 implementation evidence (review pending): CI now installs the backend integration runtime
  dependencies and editable hardware-agent package, and adds a native ARM64 package gate using
  pinned uv 0.11.20/Python 3.12. The protected release workflow separates build, signing and
  promotion permissions/environments; Pages export verifies signed metadata and exports only
  the immutable snapshot. The tracked public keyring fingerprint is
  `92BD91D03608EA3AFDB108AAB7EEC4E4E954DA7A` (SHA-256
  `E133D6975F2E5DF775CE407BA902CB6BD40F19F5972C3BC61C991392D96346AA`). Focused local signed
  publication/workflow tests passed **8/8**; the backend websocket integration gate passed
  **1/1, zero skipped** after recreating only the dedicated stale `dmitri_test` database and
  installing the agent runtime into the isolated test environment. Syntax, scoped Ruff/Black,
  shell and Python compilation checks passed. Disposable Debian 13 ARM64 guest install tested
  both current-source packages (`hardware-agent 1.0.7-1`, updater `1.0.1-1`); both postinsts
  exited successfully and offline agent venv creation installed all 27 hash-locked wheels.
  Because a native TCG build exceeded the practical time limit, packages were cross-built from
  current checkout source under the pinned ARM64 cross-build path and installed natively in the
  ARM64 guest; this is install evidence, not evidence of a native local build. GitHub's native
  ARM64 release runner remains the build gate. Before installation, the full VM work directory
  was snapshotted outside the repository (archive SHA-256
  `D49A2FD5B90C0757F2AA2B223097A2A11D04A9A363E8614CDA690FDB3A8A3BC4`). After the test, the
  guest was powered off and the exact snapshot restored; tar comparison returned exit 0 and
  QEMU is stopped. No Raspberry, production system, signing secret, publication, or deployment
  was changed. O2 implementation and local gates passed focused independent review:
  **APPROVED**. Real protected CI, hosted signing/publication and O4 remain outstanding.
- O2 review corrections: before preparing a candidate, the signing job now verifies the current
  `agent-apt-state` snapshot with the approved public keyring. This checks both Release
  signatures, every signed metadata hash, catalog-to-index bindings, and hashes/control
  identities for all referenced package bytes. Regression tests tamper with the retained
  catalog and Packages index and confirm verification rejects each. Reusing an existing
  updater `version+architecture` is allowed only when index and provenance hashes/sizes match;
  changed bytes for that identity fail. Tests cover two different agent versions sharing the
  exact updater package and rejection of changed updater bytes. The complete focused
  `test_release_workflow.py` + `test_update_scripts.py` run passed **47 tests**. It emitted 12
  pytest cleanup warnings because read-only package fixtures could not be removed by WSL; all
  assertions passed. The independent reviewer approved both P1 corrections and the focused
  47-test gate with zero skips. O2 is **COMPLETE**; real protected CI and hosted
  signing/publication remain O4 gates.
- O3 implementation evidence (independent review pending): moved the only tracked public
  keyring to `backend/agent-release/public-keyring.gpg` so the release workflow and shared
  `/backend` Railpack image consume the same asset. Verified the approved primary/subkey
  fingerprints and SHA-256 `E133D6975F2E5DF775CE407BA902CB6BD40F19F5972C3BC61C991392D96346AA`;
  no duplicate remains at repository root. Added runtime `ca-certificates`, `dpkg`, and `gpgv`,
  backend environment example values, and regressions for tool availability, trust-anchor
  identity, rejection of another signing key, environment aliases/defaults, and release workflow
  path. Updated Railway, installer, recovery and ADR-021 instructions to describe shared config,
  assisted two-package bootstrap, admin-approved updates, check-only timer behavior and gates
  still pending. Local tests: `test_release_catalog.py` plus
  `test_agent_updates_migration.py` **21 passed, 0 skipped**; focused `test_settings.py` **4
  passed**; release workflow tests **2 passed**; scoped Ruff **passed**. The full catalog/migration
  run emitted 13 existing WSL fixture-cleanup/Starlette warnings but all assertions passed.
  No code migration was changed; migration coverage exercised existing revisions against only
  the dedicated `dmitri_test` database. Actual Railway image contents, hosted catalog import and
  production configuration remain O5 gates. No deployment, publication, GitHub environment or Pi
  was changed. The first independent review found two P2 documentation errors: recovery named a
  nonexistent timer, and the installer instructions omitted the locked uv/Python runtime and
  preexisting-lock requirements while retaining an obsolete one-package procedure. Corrected
  the timer to `dmitri-agent-update.timer` and rewrote the installer sequence with exact
  bootstrap prerequisites and a truthful hardware-validation boundary. A subsequent review
  identified additional installer ordering and Railway source-provenance details. The installer
  now distinguishes new devices (pre-create root-owned `/opt/dmitri-agent` before the script
  starts its supervisor) from existing devices (wait for scan result finalization, then stop the
  active agent service before bootstrap; never replace its lock/runtime). It attributes APT
  keyring/source setup to `provision-pi.sh`, not the companion package. Railway instructions now
  use `redeploy` for env-only changes and require a clean detached worktree at the reviewed full
  SHA before `railway up`, which uploads local directory contents. These doc-only corrections
  were checked against `provision-pi.sh`, the updater service unit and Railway CLI behavior;
  Final independent review approved all corrections with no new findings. O3 is **COMPLETE**; actual Railway image verification, hosted catalog import and production configuration remain O5 gates.
