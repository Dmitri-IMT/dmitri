# Audit — the NSPi Modbus and operating-system work

| | |
|---|---|
| **PR** | [#137](https://github.com/Dmitri-IMT/dmitri/pull/137) — `feature/nspi-modbus-methodology` → `main` |
| **Author** | João Ferrenha (`ferrenha`) |
| **Merged** | 2026-09-08 20:42 -03, merge commit `eda7ca2`. PR body empty. |
| **Delta** | `git diff 8688597 8fb1c8c` — 116 files, +9,606 / −118, 8 commits |
| **Also in scope** | `6e19062` and `79c559d` — pushed directly to `main` 2026-09-11, no pull request (see Addendum, findings 16-18) |
| **Scope is complete** | These are every commit by this author on `main` since 2026-09-03. His remaining commits predate the current work (March 2026) |
| **Excluded** | PR #135, #136, #141 (other authors' or the reviewer's own work). PR #138 — merged then fully reverted by #139; only a 4-line formatting tidy survives, so nothing of it is live to fix |
| **Audited** | 2026-09-08 and 2026-09-12, post-merge, unreviewed at merge time |
| **Verdict** | **Do not build on this until blockers 1–2 are resolved.** `main` cannot migrate. Blocker 3 is discharged by ADR-019 (Accepted 2026-09-12). |
| **Findings** | 3 blockers, 16 findings. Finding 19 was found during design, not review, and is pre-existing rather than caused by this work |

Base `8688597` is the tip of `main` before this work. The branch merged PR #135 and #136 into
itself but did not author them, so they are outside the delta above.

## Scope — two features in one PR

- **`specs/042-nspi-modbus-ot`** — active Modbus/OT scanning. New `hardware-agent/src/agent/ot/`
  (`modbus/client.py`, `mapper.py`, `nse.py`, `inventory.py`, `fingerprints.py`, `models.py`,
  `policy.py`), wired through `scanner/stages.py` (+300), `scanner/runner.py` (+72), and the TUI.
  New ADR-018; amendments to ADR-004 and ADR-010.
- **`specs/043-operating-system-inventory`** — OS detection across agent, backend
  (migration `20260908_19`, `schemas/operating_system.py`), contracts (+300 OpenAPI) and frontend.

## Gate results

| Gate | Result |
|---|---|
| `hardware-agent` — `ruff check src tests` | clean |
| `hardware-agent` — `uv run pytest` | **785 passed** |
| `backend` — `ruff check src tests` | clean |
| `backend` — `uv run pytest` | 568 passed / **599 skipped** — no database. Per CLAUDE.md this proves nothing about services, routers or migrations. **The skipped set is exactly where blocker 1 detonates.** |

Every gate is green. That is why this merged. The green backend run is the false signal
CLAUDE.md warns about.

---

# Blockers

## 1. CRITICAL — Alembic has two heads; `alembic upgrade head` fails

`backend/alembic/versions/20260903_18_nspi_options.py:7` — `down_revision = "20260811_17"`.
`20260904_18_scan_box_and_duration.py`, already on `main`, claims the same parent. The chain
forks and never rejoins:

```
20260811_17 ─┬─ 20260903_18 ── 20260908_19   (this PR)      head
             └─ 20260904_18 ── 20260905_19   (main, #135)   head
```

Verified directly:

```
$ uv run alembic heads
20260905_19 (head)
20260908_19 (head)
```

`ScriptDirectory._upgrade_revs('head', ...)` → `CommandError: Multiple head revisions are
present for given argument 'head'`.

**Failure scenario.** Any deploy or CI step running `alembic upgrade head` aborts before
applying anything: `operating_system_json` and `commands.nspi_options` never land, so `/scans`
ingest and `/agents/{id}/commands` 500 on missing columns. Locally,
`backend/tests/conftest.py:143` calls `_migrate(engine, "head")` — so with `DATABASE_URL_TEST`
set, **all 599 currently-skipped tests error at fixture setup**.
`backend/tests/test_operating_system_migration.py:82` fails the same way in its `finally`.

**Cause.** `20260903_18_nspi_options.py` was *modified* (+17 lines) on a branch cut before
`20260904_18` existed. Nobody rebased the revision pointer at merge.

**Fix direction.** `alembic merge` producing a merge revision, or repoint `20260903_18`.
Renumbering an already-pushed revision is the riskier option.

## 2. HIGH — `industrial_services` is accepted, then silently discarded

`backend/src/api/schemas/scan.py:123`. The field exists in exactly three places repo-wide:

```
$ grep -rn "industrial_services" backend contracts frontend/src
backend/src/api/schemas/scan.py:123
contracts/openapi/openapi.yaml:2598
frontend/src/types/openapi.d.ts:664
```

No column in `20260908_19` (it adds only `operating_system_json`), nothing in
`services/persistence.py::_persist_scan_host`, nothing in `services/read.py`, no route.

**Failure scenario.** A `read_only_mapping` scan of a real PLC produces FC43 identification,
unit inventory and address-range evidence. The agent POSTs it. The API returns 202. The payload
is dropped. **Nothing feature 042 produces is retrievable through the API or the web UI** — it
exists only in the agent's local JSON and the TUI `scan_view.py`.

Either persistence is missing, or the ingest field plus its OpenAPI/TS surface is dead code.
`docs/tests/nspi-modbus-inventory.md:60-75` and `nspi-modbus-read-only-mapping.md:75-91` both
teach operators to read `industrial_services`, so the intent was evidently that it persists.

## 3. HIGH — ADR-002 forbids what shipped, and was not amended

`docs/adr/ADR-002-scanning-tools-selection.md:248,256` — "v1 … **apenas ferramentas passivas,
sem dependências adicionais**" and "O escopo da v1 está fixo … **Nenhuma ferramenta ativa
adicional**", with §7/§8 requiring a new ADR for any tool addition.

This PR adds `pymodbus==3.13.1` (`hardware-agent/pyproject.toml:18`) and an active Modbus client
originating its own TCP/502 traffic outside Nmap. ADR-018 references only the spec files
(`ADR-018:79-83`) and never supersedes ADR-002. A reader of ADR-002 today concludes no active
tool ships.

---

# Bugs

Ordered by consequence. All CONFIRMED unless marked.

## 4. MEDIUM — A zero-padded unit id voids an entire NSE parse

`hardware-agent/src/agent/ot/modbus/nse.py:178-180`, swallowed at `:55`.

`_parse_unit_id` uses `int(value, 0)`; base-0 rejects leading zeros. Verified:
`int('08', 0)` → `ValueError`, `int('007', 0)` → `ValueError`, `int('1', 0)` → `1`.
`parse_modbus_discover` catches `ValueError`, returns what it accumulated, logs nothing.

**Failure scenario.** NSE output with a zero-padded sid discards every unit from that script.
`_inventory_port` then sees `units == {}` and falls back to probing unit 1 only
(`inventory.py:101`). The real units are never probed, mapping targets nothing — and the scan
reports success.

## 5. MEDIUM — One malformed FC43 response erases a whole port's evidence

`hardware-agent/src/agent/ot/modbus/inventory.py:51-59`.

`probe_device_identification` catches `(TimeoutError, ModbusIOException, ModbusException,
OSError, RuntimeError, ValueError)`. pymodbus decoding a malformed response can raise
`KeyError` / `IndexError` / `AttributeError` / `struct.error` — none in that tuple. These reach
the outer `except Exception` in `inventory_modbus_host`, which replaces the **entire**
`ModbusService`, including units already merged from `modbus-discover` at `:88-90`, with an
empty `confidence="suspected"` stub.

**Failure scenario.** One badly-framed response from unit 3 erases the evidence for units 1, 2
and 4 on that port.

## 6. MEDIUM — Device-controlled strings crash the TUI via Rich markup

`hardware-agent/src/agent/tui/screens/scan_view.py:67,77` — `Static` with markup enabled by
default, rendering `unit.device_identification.vendor_name` / `product_name`.

Rich raises on a stray closing tag: `render('Vendor: [/nope]')` → `MarkupError: closing tag
'[/nope]' doesn't match any open tag`. FC43 strings are fully device-controlled and never passed
through `Text()` or `escape()`.

**Failure scenario.** A PLC whose vendor string contains `[/b]` makes the scan-view screen raise
when the operator opens it after the scan. The port-banner path had this shape before this PR;
the new fields widen it substantially.

## 7. MEDIUM — One bad DB row 500s `GET /hosts` for the whole org

`backend/src/api/services/read.py:389-392`. `OperatingSystemDetection.model_validate(value)`
with `extra="forbid"` and `strict=True` on `accuracy`, no guard.

**Failure scenario.** A row whose `operating_system_json` came from an older agent, or holds a
future field or a partially-written value, raises `ValidationError` inside the GET handler.
Because `_to_host_summary` runs over the list, the whole `GET /hosts` fails — not just that host.

## 8. MEDIUM — FC43 inventory ignores the policy's pacing

`hardware-agent/src/agent/scanner/stages.py:352` → `ot/modbus/inventory.py:106-115`.

`inter_request_delay_ms` is applied **only** in `mapper._read_chunk:191`. The inventory loop
issues up to `MAX_IDENTIFICATION_FALLBACKS_PER_HOST = 4` FC43 probes back to back with no delay,
and `probe_device_identification` opens a **fresh TCP connection per probe**
(`client.py:190`).

**Failure scenario.** A host where NSE reported 4 unidentified unit ids gets 4 connect/FC43/close
cycles at full speed. On a fragile controller with a small TCP backlog that is exactly the
traffic ADR-018's delay exists to prevent. Count is bounded; rate is not.

## 9. MEDIUM — The mapper's `deadline` bound is dead code

`hardware-agent/src/agent/scanner/runner.py:210-213`, `ot/modbus/mapper.py:265-272`.

`deadline` is `None` unless `settings.scan_deadline_s > 0`; `AgentSettings.scan_deadline_s`
defaults to `0` (`config.py:31`) and no path sets it. Every `_must_stop()` reduces to the cancel
check. The only real bound on mapping traffic is `MappingBudget` (≤32 requests/host), which is
adequate — but the **time** bound the code and spec advertise is never enforced. A slow device
runs ~51 s per host (1.5 s × 32 + 32 × 100 ms) regardless of elapsed scan time.

## 10. MEDIUM — The partial/exit-10 signal is inferred from absent nmap elements

`hardware-agent/src/agent/discovery/port_discovery.py:154-155`, consumed at
`scanner/stages.py:152-160,176`.

`results[ip].skipped = ip not in pass1_hosts or ip not in pass2_hosts` infers a host timeout from
a missing `<host>` element. With `-Pn`, nmap emits a `<host>` element for every target including
ones cut short by `--host-timeout`, so genuine timeouts usually are **not** flagged — and nothing
distinguishes a timeout from any other reason a host is absent. This now drives two behaviours it
did not before: `CircuitBreakerError` on `hosts_skipped / len(hosts) > 0.5`, and
`partial_result` → headless exit code **10** (ADR-012).

**Failure scenario.** A clean 254-host scan where nmap omits a few unreachable hosts from one
pass exits 10 and reports partial; a run where many hosts genuinely time out but still emit host
elements reports success.

## 11. MEDIUM — A device chooses which mapping profile is applied to it

`hardware-agent/src/agent/ot/modbus/mapper.py:75-90`.

`resolve_mapping_plan` calls `_fingerprint_values(service)` and feeds the resulting `vendors` /
`products` into `selector_matches`. Those strings come from the device's own FC43 identification
response. A responder on TCP/502 therefore influences which `MappingProfile` — and so which
address ranges and block sizes — the scan applies to it.

**Failure scenario.** A hostile or misconfigured device on an authorised subnet claims a vendor
string matching the operator's most permissive vendor profile, and receives that profile's
mapping plan instead of the generic baseline.

**Bounded by.** Site profiles keyed on `cidrs` or `macs` take precedence over vendor/product
profiles (`mapper.py:87-91`), so network position beats self-claim where a site profile exists.
Every profile remains capped by the `MAX_MAPPING_*` ceilings in `ot/policy.py:15-19`, so this
escalates only up to the operator's own most permissive configured profile — never beyond the
global bounds.

**Fix direction.** Device-claimed identity should only ever be allowed to narrow scope. Require
CIDR or MAC corroboration for any profile more aggressive than the generic baseline.

## 12. LOW — `modbus_write_requests_sent` is a literal, not a measurement

`hardware-agent/src/agent/scanner/stages.py:614` — `"modbus_write_requests_sent": 0`, asserted by
`tests/unit/test_modbus_stage.py:131`. True today because no write path exists. It is the metric
that would have to prove ADR-018's central claim, and it will keep printing `0` unchanged the day
`active_validation` ships. It should count, not assert.

## 13. LOW — The "no write escape hatch" test checks a namespace, not reachability

`hardware-agent/tests/unit/test_modbus_client.py:137-148` asserts
`{"write_coil", …}.isdisjoint(vars(client_module))` and `vars(ModbusReadSession)`. But
`ModbusReadSession._client` is a full `ModbusTcpClient` — `session._client.write_register(...)`
works. The read-only boundary is a naming convention this test does not verify.

## 14. LOW — `ScanRunner` never validates `nspi_submode`

`hardware-agent/src/agent/scanner/runner.py:48`. `headless.validate_inputs` rejects
`active_validation` (`headless.py:65`), but `ScanRunner` is also constructed directly by
`ScanProgressScreen` (`scan_progress.py:147`). Unreachable today because the TUI option is
`disabled=True`, but the safety gate lives one layer above the object that acts on it.
`ScanRunner` accepts the value, runs an inventory-only scan, and stamps
`nspi_submode: "active_validation"` into the result metadata — a result that misdescribes what
was done.

## 15. LOW — Miscellaneous

- `ot/modbus/mapper.py:319-320` — `value_min=min(numeric) if numeric else (0 if numeric == [] else None)`
  reports `0` for an empty value list. Unreachable (`client.py:162` rejects short reads), so dead
  branching that would also lie if reached.
- `ot/modbus/nse.py:175` — `_is_error_entry` returns True for any value *containing* `"exception"`,
  so a product name like `"ExceptionLogger 3000"` becomes the unit's `error` and flips its status.
- `scanner/stages.py:148` — `results[ip]` replaced a defensive `results.get(ip, [])`; safe only
  because every callee pre-seeds all ips.
- `normalize/contracts.py:36-107` — agent-side Modbus models omit `extra="forbid"` while their
  backend twins in `schemas/scan.py` have it. Asymmetric strictness, not a break.

## SUSPECTED — not reproduced

- **`--host-timeout 300s` vs the 600 s subprocess budget.** `port_discovery.py:12-22` sets
  `--host-timeout 300s` on both NSPi passes while `host_batch_size` is 8 and
  `TIMEOUTS["ports"]["nspi"]` is 600 s. If nmap's host-group parallelism serialises even three
  slow hosts, the batch exceeds 600 s → `BudgetExceeded` → all 8 hosts skipped → with
  `unit_failure_threshold = 0.5` a two-batch scan can trip the circuit breaker. Needs real slow
  targets to reproduce. Note the `nse` timeout was also halved 1200 → 600 (`config.py:130`) in
  the same commit that moved `-O` into the deep stage alongside 14 scripts (see note below).

## NOTE — `-O` was moved, not added

Recorded because the team disagreed about it. Before this PR,
`NSPI_PASS1_ARGS = ["-Pn", "-T4", "-n", "-sV", "-O"]` — NSPi ran OS fingerprinting against
**every host in pass 1**. This PR removed `-sV` and `-O` from pass 1, added `--host-timeout`, and
reintroduced `-O` in the deep stage gated on `detect_os: True` for NSPi only
(`scanner/stages.py:225`, `discovery/vulnerability_detection.py:51`).

Net effect: `-O` still runs on NSPi, but once, later, and only against hosts that reached the
deep stage with open ports. This is an improvement. **The root/`CAP_NET_RAW` requirement that
`-O` implies is therefore not new** — it predates this PR. `scanner/nmap.py:112` invokes nmap
with no `sudo` and no privilege check, so the agent's deployed privilege level decides whether
`-O` works at all.
- **`_decode_device_information` bounds nothing** (`ot/modbus/client.py:249-267`) — no cap on
  object count or string length before they reach `objects`, and the backend's
  `objects: dict[str, str]` is likewise uncapped. A Modbus PDU is ≤253 bytes so a single response
  cannot be large; if pymodbus ever follows `more_follows`, this becomes unbounded.

---

# Documentation

## Changed but wrong

- **`docs/CLI.md:37-40`** — says "`nspi` currently selects the `inventory` submode
  automatically" and documents only `dmitri agent <mode> <subnet>`. But `cli.py:54` accepts
  arity 3, `cli.py:77` unpacks `mode, nspi_submode, subnet`, and `cli.py:105` prints
  `dmitri agent [<mode> [<nspi-submode>] <subnet>]`. CLI.md is the canonical CLI reference and
  the only doc denying the submode exists.
- **`docs/tests/nspi-modbus-read-only-mapping.md:56`** — "Active validation permanece
  desabilitado" is true for the TUI (`scan_mode.py:33-37`, `disabled=True`) but false for the
  web: `ScanControl.tsx:82-86` renders only two `SelectItem`s. The web behaviour is *absent*,
  not disabled.
- **`docs/tests/nspi-modbus-inventory.md:11`** — tells the operator to be on
  `feature/nspi-modbus-methodology`. A lab checklist naming the wrong branch gets followed
  literally.

## Should have changed, did not

- **`.claude/docs/hardware-agent/daemon.md:103-106`** — states the `invalid_command` branch is
  unreachable because `scan_mode` is a `Literal`. **It is now the only thing rejecting a remote
  `active_validation` command**: the backend enqueues it (`schemas/commands.py:35-39`), the agent
  refuses it (`headless.py:65-67`), `daemon.py:112-114` converts that to `failed`. The code map
  calls the active-write guard dead code. Highest-consequence doc finding.
- **`.claude/docs/backend/migrations.md:42,54-55`** — documents the single-head convention this
  branch breaks, and its revision table lists neither new migration. See blocker 1.
- **`.claude/docs/` is untouched by the entire diff** — no `ot.md`; `hardware-agent/index.md:16-30`
  and `overview.md:52-64` list every package area but not `ot/`; `overview.md:26-33` describes a
  4-step pipeline with no Modbus stage; `overview.md:68-70` omits `pymodbus`; `overview.md:19`
  still pins `AGENT_VERSION` `0.1.4`.
- **`.claude/docs/hardware-agent/cli.md:56-57`** — "one or three-plus arguments is a usage error"
  contradicts `cli.py:54` (`if len(args) not in (0, 2, 3)`); `:30` omits `nspi_submode` from the
  `AgentSettings` field list.
- **`.claude/docs/hardware-agent/scanner/stages.md:23`** — stale circuit-breaker formula
  (`batches_failed / batches_total`); the code is `hosts_skipped / len(hosts)`
  (`stages.py:176-179`). The human ADR-010 was amended, the code map was not.
- **`.claude/docs/hardware-agent/tui.md:31`** — NSPi picker described as single-option; there are
  now three submodes and a submode label in `scan_progress.py:84-89`.
- **`.claude/docs/frontend/devices-screen.md:30`** — `trigger(scanMode)` is now
  `trigger(selection: ScanSelection)` posting `nspi_options` (`useScanCommand.ts:16-27`).
- **`.claude/docs/backend/schemas.md` / `models.md`** — omit `operating_system`,
  `industrial_services`, `nspi_options` and `operating_system_json`; the new
  `schemas/operating_system.py` appears in no map file; `.claude/docs/contracts.md` covers none
  of the seven new contract schemas.
- **`docs/DEV-SETUP.md:125-137`** — no entry for `DMITRI_OT_POLICY_PATH` or
  `~/.config/dmitri/ot-policy.json` (`ot/policy.py:136-144`).
- **`docs/README.md:26-39`** — routing index stops at ADR-012; ADR-018 unlisted, and no row for
  `docs/tests/` or `docs/examples/`. (ADR-013–017 missing is pre-existing.)
- **`docs/roadmap/TASKS.md:40-44`** — T4.1 "Study and fix NSPi port stage" still unchecked and
  `roadmap/README.md:23` still shows it open, although this branch's ADR-004 amendment plus
  `port_discovery.py:12-22` and `stages.py:176` are exactly that fix. No roadmap file mentions
  Modbus/OT at all.

---

# What is sound

Stated plainly, because it matters for deciding how much to unpick.

- **The CLAUDE.md integration rule holds.** All three construction sites — `headless.py:111`,
  `scan_progress.py:147` (`ScanRunner`) and `home.py:74` (`ScanProgressScreen`) — pass
  `nspi_submode`, and `ScanRunner` loads the OT policy itself rather than trusting a caller. No
  TUI-initiated scan drops the safety policy.
- **No write function code is reachable.**
  `grep -rn "write_coil\|write_register\|execute\|mask_write\|readwrite" src/agent/ot/` returns
  nothing. `ModbusReadSession` dispatches only FC01–FC04; `probe_device_identification` only
  FC43/MEI-14.
- **Range and unit bounds are real, not happy-path.** `MappingRangeRule` (`policy.py:26-49`)
  enforces `start + count ≤ 65536`, block size ≤32 registers / ≤64 bits (well under the Modbus
  125/2000 limits), raw capture ≤128 values. `resolve_mapping_plan:73` restricts to
  `1 ≤ unit_id ≤ 247` — excluding broadcast 0 and 248–255 — and caps at 4 units. `MappingBudget`
  caps 32 requests/host across all services. The bisect recursion terminates in ≤log₂(count)
  levels with a budget check at each. Partial reads are rejected (`client.py:162`);
  `ModbusIOException` and `isError()` are distinguished; every socket closes via `finally` /
  `__exit__`.
- **ADR-004 and ADR-010 amendments match the code** they describe.
- **The read-only-mapping doc's stated defaults are accurate** — 100 ms, 32 requests/host,
  addresses 0–3 across four spaces, max 4 unit ids (`ot/policy.py:15-19,95-99,104-133`).
- **The Modbus integration tests run against a real local pymodbus server**, not mocks, and the
  pymodbus 3.13.1 signatures used (`device_id=`, `retries=0`) match the pinned version.

---

# Method

Three parallel reviews over `git diff 8688597 8fb1c8c`: a docs-drift pass, a full code review,
and a `/nuke` branch-delta pass. **`/nuke` did not run** — the skill sets
`disable-model-invocation: true` and is reserved for explicit human invocation, so its verdict is
still outstanding. Run `/nuke` in this worktree while local `main` still points at `8688597`
(do not `git fetch` first, or the delta collapses to empty).

Blocker 1 was verified independently twice, plus by hand via `alembic heads`. Blocker 2 and
finding 4 were re-verified by hand. Findings marked SUSPECTED were not reproduced.

---

# Addendum — commits pushed directly to `main`

Audited 2026-09-12 at the user's request. Two commits by João Ferrenha, 2026-09-11 09:03,
**pushed straight to `main` with no pull request and no review**:

| Commit | Scope |
|---|---|
| `6e19062` | `fix: deduplicate nmap enrichment stages` — 13 files, +479/−144. `config.py`, `discovery/port_discovery.py`, `discovery/vulnerability_detection.py`, `scanner/runner.py`, `scanner/stages.py`, 8 test files |
| `79c559d` | `docs: document nmap enrichment ownership` — 9 code-map files under `.claude/docs/` |

`79c559d` **repairs several code-map findings from this audit** — `cli.md`, `overview.md`,
`scanner/runner.md`, `scanner/stages.md`, `discovery.md`. Task O must be re-scoped against
current `main`, not against `8688597`.

## What `6e19062` does

It removes the duplicated `-sV`/NSE work between the port stage and the deep stage:

- `-sV` deleted from `discovery_arguments()` for every mode, and from `NSPI_PASS2_ARGS`.
- `port_stage_scripts()` deleted — the port stage now runs **no NSE scripts at all**.
- The deep stage becomes the single service-detection pass, with a new
  `effective_version_intensity(configured) = max(configured, 7)` floor.
- `-n` added to the port and deep stages (the NSPi passes already had it).

In the happy path this is a real improvement: one `-sV` pass instead of two. Hostnames are
unaffected — they come from `network_discovery.py:46-51`, which this commit does not touch.

It also fixes a genuine silent failure. Previously
`if result is None and settings.scan_mode == "nspi"` meant that outside NSPi, a deep-stage run
returning no `<host>` element was **ignored**. It is now counted for every mode. That is correct,
and it widens the trigger for finding 16.

## 16. HIGH — A completed scan is recorded as terminated by error, against ADR-010

`hardware-agent/src/agent/scanner/runner.py`, in the success path. Before:

```python
partial_result=hosts_skipped > 0,
interrupted_stage=None,
terminated_by="completed",
```

After:

```python
partial_result = bool(port_units_skipped or deep_units_skipped)
partial_stage = "ports" if port_units_skipped else "deep_inspection" if deep_units_skipped else None
...
interrupted_stage=partial_stage,
terminated_by="error" if partial_result else "completed",
```

The old pairing was right: a run that finished with some hosts incomplete is
`terminated_by="completed"` with `partial_result=True`. The new code collapses "finished with
partial results" into "died".

**Failure scenario.** A scan completes normally; one host's deep inspection returns no `<host>`
element. The run is recorded with `terminated_by="error"` and `interrupted_stage="deep_inspection"`
— naming a stage that ran to completion. `workspace.py:89` defines
`_FAILED_TERMINATED_BY = {"timeout", "error", "user_cancel"}`, so `prune_logs` classifies the
successful run as failed and retains it on that basis; the TUI label at
`scan_progress.py:448` reads from the same field.

**Blast radius is agent-local.** Neither `partial_result` nor `interrupted_stage` appears
anywhere in `backend/src` or `contracts/openapi/openapi.yaml`, and `headless.py:136-140` still
derives the exit code from `partial_result`, so the ADR-012 contract (`partial` → 10) is
unchanged.

**This violates ADR-010 verbatim.** `docs/adr/ADR-010-scan-contingency-policy.md` §3:

> "Se qualquer host for pulado e o pipeline ainda conseguir terminar, o resultado final usa
> `partial_result=True` com `terminated_by="completed"`; não há `interrupted_stage`, pois nenhum
> estágio foi interrompido."

The same section closes: "nenhum estado terminal novo é inventado." And §1 **reserves**
`terminated_by="error"` for `CircuitBreakerError` — "varredura interrompida cedo", a scan stopped
early because more than half the units failed. So the commit does not merely pick a confusing
value: it overloads a value that already means something else, making the two cases
indistinguishable in the record.

**Fix direction.** Restore `terminated_by="completed"` and `interrupted_stage=None` on the success
path; keep `partial_result` as the signal. No new terminal state, and no ADR amendment — ADR-010
already prescribes the behaviour. Severity raised from MEDIUM to HIGH on that basis: this is a
documented-decision violation, not a judgement call.

## 17. MEDIUM — Service and version evidence now depends entirely on the deep stage

Same commit. With `-sV` gone from the port stage and `port_stage_scripts()` deleted, the port
stage returns ports whose `service` is Nmap's port-number guess from `nmap-services` and whose
`version` is `None`. The deep stage is the only source of real version data.

**Failure scenario.** A host has open ports but its deep inspection fails or returns no host
element. Previously the port stage had already supplied independent `-sV` service and version
evidence, which survived a deep-stage failure. Now that host reports guessed service names and no
version at all — and, per the change above, is also counted as skipped and flips the run to
`terminated_by="error"`.

The deduplication is sound; what it removed was the redundancy that made the port stage's
evidence independent of the deep stage. Whether that redundancy should be restored, or the
deep-stage failure path made more robust, is a design decision rather than a defect.

## 18. LOW — Process: 479 lines to `main` with no pull request

`6e19062` changes the scan lifecycle's terminal-state semantics and removes a stage's entire NSE
configuration. It received no review. This is the same pattern as PR #137 — an empty PR body and
no reviewer — and the finding above is exactly what a review would have caught.

## 19. MEDIUM — A correctly finished scan is shown to the operator as interrupted

Found while designing the TUI for this spec, not in the original review. **Pre-existing — it is
not caused by `6e19062`**, but it must be fixed alongside finding 16 or the operator-facing
result stays wrong.

`hardware-agent/src/agent/tui/screens/scan_progress.py:450-451`:

```python
stage = self._INTERRUPTED_STAGE_LABELS.get(
    metadata.get("interrupted_stage"), "an earlier stage"
)
```

ADR-010 §3 requires a pipeline that finishes with skipped hosts to record
`interrupted_stage=None`. That is exactly the value this lookup treats as unknown, so it falls
through to the default and the screen reports the scan as interrupted at `"an earlier stage"`.
The badge on the line above reads `PARTIAL`.

**Failure scenario.** A scan completes, one host is skipped, the payload is recorded correctly
per ADR-010 — and the operator is told the scan was interrupted at an unnamed earlier stage.

**Note on scope.** This worktree (PR #137) still has the correct pairing at
`scanner/runner.py:308-310`. On `main`, `6e19062` changed it so `interrupted_stage` is now set on
finished scans, which incidentally hides this defect by feeding the lookup a value it recognises.
Reverting finding 16 without fixing this restores the wrong label.

**Fix direction.** Name a stage only when one was actually interrupted, and distinguish
"finished, some evidence incomplete" from "stopped early" in the badge as well as the reason
line. Covered by `DESIGN.md` states S4-incomplete and S4-stopped.
