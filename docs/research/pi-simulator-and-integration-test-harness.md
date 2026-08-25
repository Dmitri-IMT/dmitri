# Research: Pi simulator and the first full-wire integration test

> **Scope.** Dmitri has strong unit/mock coverage on both sides of the Pi↔backend
> wire (`test_provision_agent.py`, `test_agent_ws_channel.py`, `test_ingest_scan.py`,
> `test_device_sig.py`; agent-side `test_daemon.py`, `test_ingest_client.py`,
> `test_transport_signing.py`) and **zero** process-level coverage: nothing runs a real
> daemon against a real server over a real socket. Two proposals are on the table —
> (A) a docker-compose full-wire CI gate with real ICS protocol emulators, QEMU arm64
> wheel check and a shared `provision.sh`; (B) a local "fake Pi" container the developer
> runs on their own machine against the deployed API/WS to produce real data for the
> not-yet-built Hosts/Scans/Agents screens. This note weighs both against primary
> sources (martinfowler.com, Google Testing Blog, GitHub Actions docs, Testcontainers
> docs, nmap NSEDoc, AWS/Azure/balena first-party device-simulation docs).
> Fetched 2026-08-23.

---

## TL;DR verdict

**Recommendation for Dmitri: build (B) first — the local simulator — and let (A) grow
out of it.** The two proposals share ~80% of their machinery (a Debian container that
provisions, connects, scans, signs and uploads). Building the local one first gets the
UI unblocked in a fraction of the time, and the CI gate is then a thin wrapper around a
thing that already works, rather than a green-field 8–16h build.

- **Proportionality.** One full-wire test is *not* over-engineering — Fowler's pyramid
  argues for *few*, not *zero*, broad-stack tests, and calls the high-level test "a
  second line of test defense". But the proposed gate is well past "one": ICS emulators
  + QEMU + shared installer script + structural finding assertions is four features
  wearing one issue's clothes.
- **Where the first one goes.** Fowler's *narrow* integration test — Pi transport code
  against a real backend process, nothing else live — is the documented cheap starting
  point. Everything past that is broad-stack and "harder to maintain and slower".
- **Tooling.** GitHub Actions `services:` cannot build images and only handles
  pre-built ones; Dmitri already uses it for Postgres. The fake-Pi and ICS-target
  containers need building, so `services:` alone does not fit. Plain `docker compose up`
  in a step, or `testcontainers-python`'s `DockerCompose`, both work; Testcontainers'
  documented edge is IDE-local runs and automatic cleanup, not CI capability.
- **ICS emulators.** No authoritative source recommends hand-rolling protocol
  emulators to test a scanner. The conventional pattern is pre-built vulnerable
  environments (vulhub is literally "Pre-Built Vulnerable Environments Based on
  Docker-Compose"). **Defer.** Samba alone covers ports 445/139 and gives a real
  service-detection surface for a fraction of the work.
- **`vulners` in a blocking gate: no.** NSEDoc states outright that a local DB is
  impossible and every scan makes a live request to vulners.com. That is an external
  network dependency inside a required check — precisely what hermetic-test guidance
  exists to prevent, and Google's data shows flakiness scaling with test size.
- **Simulator against *production*: no.** Every first-party device-simulation product
  found (AWS, Azure, balena) frames simulators as development/test tooling; AWS states
  it explicitly. Point the simulator at a dedicated non-prod org or environment.
- **`size:L` for plan (A) as described is optimistic.** See §7.

---

## 1. Proportionality: how big should the first integration test be?

**Documented recommendation.** Fowler's TestPyramid: "you should have many more
low-level UnitTests than high level BroadStackTests running through a GUI", because
broad tests are "brittle, expensive to write, and time consuming to run" and especially
prone to non-determinism. Note the shape of the claim — *fewer*, not *none*. He also
records the counter-case: "If my high level tests are fast, reliable, and cheap to
modify — then lower-level tests aren't needed."
— https://martinfowler.com/bliki/TestPyramid.html

BroadStackTest adds the tradeoff explicitly: broad-stack tests "exercise
interconnected components, uncovering interaction bugs that component tests miss" but
"tend to be harder to maintain and slower to execute", hence "using fewer broad-stack
tests". It also notes such tests "typically use test doubles for remote systems rather
than calling them directly, avoiding unnecessary slowness and brittleness."
— https://martinfowler.com/bliki/BroadStackTest.html

The distinction that matters most here is Fowler's **narrow vs broad integration test**.
A *narrow* integration test covers "only that portion of the code in my service that
talks to a separate service", is limited in scope, runs quickly, and can run early in
the pipeline. A *broad* integration test "requires live versions of all services" and
"exercises code paths through all services". His recommendation is direct: teams
relying solely on broad integration tests should explore the narrow approach, which
"significantly improves testing speed, usability, and reliability".
— https://martinfowler.com/bliki/IntegrationTest.html

**Google's test sizes** give the same answer in different units. Small: no network,
no DB, no filesystem, <60s. Medium: may use "network access, database, file system",
<300s, still parallelisable. Large: >300s, end-to-end, minimal restrictions.
— https://testing.googleblog.com/2010/12/test-sizes.html

And the follow-up analysis of 4.2M tests found **test size is the primary correlate of
flakiness** — a roughly linear relationship between test binary size and flake rate,
with timing dependence, randomness and infrastructure timeouts named as the mechanisms.
The stated rule: "You always want to start with the smallest tests you can."
— https://testing.googleblog.com/2017/04/where-do-our-flaky-tests-come-from.html

**My analysis.** Dmitri's gap is real and worth closing: mock-only coverage of a
protocol boundary is exactly the case where doubles drift from the thing they double,
which is why Fowler defines ContractTest at all. But the plan as written jumps
straight to a *large*, *broad* test on the first attempt. The documented ordering is
the reverse: get a narrow, medium-sized test green first — real agent process, real
backend process, real Postgres, real socket, `nmap` pointed at something trivially
present (`127.0.0.1`, or one Samba container) — and only then decide whether the ICS
surface and the arm64 wheel check earn their maintenance.

Note also Fowler's guidance on contract tests, which is what a full-wire test partly
is: failures "shouldn't automatically break builds" and running them "once a day is
plenty" when the rhythm of change is slow. — https://martinfowler.com/bliki/ContractTest.html
That argues against `required: true` on the gate at day one.

---

## 2. Tooling: `services:`, docker compose, or Testcontainers?

**GitHub Actions service containers.** First-party docs describe them as "a simple and
portable way for you to host services that you might need to test or operate your
application in a workflow", intended for integration tests needing a database or cache.
Documented limits: accessible only within the same job, unusable inside composite
actions, Linux runners only, and explicit host port mapping needed when the job runs
directly on the runner. The docs are framed entirely around **pre-built images**; there
is no build-from-Dockerfile support described.
— https://docs.github.com/en/actions/using-containerized-services/about-service-containers

Dmitri already uses this correctly: `.github/workflows/ci.yml` runs the `backend` job
with a `postgres:17` service and `DATABASE_URL_TEST` pointed at it.

**Testcontainers.** The first-party pitch is: no pre-provisioned integration-test
infrastructure, data isolation between parallel pipelines, feature parity with the real
database instead of in-memory substitutes, and — the point that matters most for a
solo developer — "Run your integration tests right from your IDE, just like you run unit
tests", with automatic cleanup and infrastructure code living next to test code.
The introduction page makes **no claim about being better than docker compose**; its
comparison is against in-memory databases like H2.
— https://testcontainers.com/guides/introducing-testcontainers/

**Testcontainers compose module.** `testcontainers-python` does ship a `DockerCompose`
class (`testcontainers.compose`) taking `filepath`, `compose_file_name`, `pull`,
`build` and `env_file`, exposing `start()`/`stop()` and per-service host/port lookup.
So a compose file authored for local use can be driven from pytest without a second
definition of the stack.
— https://testcontainers-python.readthedocs.io/en/testcontainers-v4.12.0/compose.html
— https://github.com/testcontainers/testcontainers-python/blob/main/compose.rst

**Where the sources genuinely do not decide it.** I found **no authoritative primary
source** stating a preference between "docker compose in a CI step" and
"testcontainers-python" for a Python project. The trade-off available from first-party
material is narrow: `services:` is simplest but image-only; compose is one artifact the
developer also runs locally; Testcontainers' documented advantage is programmatic
lifecycle from inside the test run. Anything stronger than that would be my opinion,
not a citation.

**My analysis for Dmitri.** The fake-Pi and any target container must be *built*, so
`services:` is out for them (Postgres can stay a service). Since proposal (B) requires
a compose file the developer runs by hand anyway, author the compose file first and use
it from CI directly; add `DockerCompose` from pytest only if/when you want the wire test
to run under `uv run pytest` alongside everything else. That keeps exactly one
definition of the stack.

---

## 3. Do real ICS emulators earn their place?

**What the conventional pattern actually is.** The dominant published pattern for
"stand up something for a scanner to scan" is **pre-built vulnerable environments**,
not hand-written emulators. vulhub describes itself as "Pre-Built Vulnerable
Environments Based on Docker-Compose", one command per environment, each with a README
of reproduction steps, explicitly "for testing and educational purposes only".
— https://github.com/vulhub/vulhub — https://vulhub.org/

**Nmap's own documentation.** The NSE tutorial covers script structure, rules and
actions; it contains **no guidance on testing NSE scripts or on standing up test
targets**. — https://nmap.org/book/nse-tutorial.html I could not find first-party nmap
guidance on how downstream consumers should test NSE-dependent code; if it exists it is
not in the NSE book chapters.

**Greenbone/OpenVAS.** Public material confirms nmap XML/greppable output is a
consumed *input format* (`nmap.nasl` reads greppable output; the experimental
`nmap_net` plugin reads XML), which is the shape a parser-fixture strategy takes.
— https://github.com/greenbone/openvas-scanner I could **not** find first-party
Greenbone documentation describing their test-fixture strategy; the repository's test
layout was not verifiable from the docs surfaced. Do not treat "OpenVAS uses XML
fixtures" as established — it is a reasonable inference, not a cited fact.

**My analysis.** The two things being conflated:

| What you want to prove | Cheapest thing that proves it |
|---|---|
| The parser turns nmap XML into correct findings | Recorded XML fixtures (already the right tool; no containers) |
| A real `nmap` subprocess runs, produces XML, and the wire carries it to DB rows | One reachable service — Samba covers 445/139 — and structural assertions |
| Modbus/OPC-UA/EtherNet/IP scripts produce the fields we expect | Real emulators (pymodbus, OPC-UA, cpppo) |

Only row 3 needs the ICS emulators, and row 3 is the *least* likely to break silently:
NSE script output shape is owned by upstream nmap and changes on nmap's release
cadence, not on Dmitri's commits. Rows 1 and 2 are where Dmitri's own regressions live.
**Defer the ICS emulators.** Start with Samba (`445`, `139`) — a real service, a real
service-detection result, no bespoke emulator code — and add pymodbus/OPC-UA later if
a real bug in the `nspi` profile ever motivates it.

Note this also collides with the project's "No temporary code" rule in `CLAUDE.md`: a
half-built ICS target that is "good enough for now" is exactly the stopgap that rule
forbids. Either build the emulator target properly or leave it out; do not ship a
placeholder ICS container.

---

## 4. `vulners` inside a blocking CI gate

**This is settled by the script's own documentation.** NSEDoc for `vulners`:
"Since the size of the DB with all the vulns is more than 250GB there is no way to use
a local db. So we do make requests to a remote service." The script sends software
name and version to the vulners.com API and returns CVEs and CVSS scores. The NSEDoc
page does **not** document an API key requirement, rate limits, or any offline mode.
— https://nmap.org/nsedoc/scripts/vulners.html

So: **no offline mode exists**, and the terms/limits are not documented on the nmap
side — meaning a CI gate running `vulners` depends on an undocumented third-party quota
from a shared GitHub-hosted runner IP range.

**What the guidance says about that.** Google's hermetic-server post makes the case
for test environments with all external dependencies injected/bundled so tests run
without live databases, external services or network infrastructure; it also concedes
these are "large tests and certainly some of our slower tests", typically run at
intervals rather than on every change.
— https://testing.googleblog.com/2012/10/hermetic-servers.html
Flakiness data reinforces it: infrastructure timeouts and non-determinism are named
mechanisms, and flake rate rises with test size.
— https://testing.googleblog.com/2017/04/where-do-our-flaky-tests-come-from.html
Fowler's ContractTest guidance points the same way: run tests against external services
on the *external service's* rhythm, don't break the build on them, and prefer service
instances over production. — https://martinfowler.com/bliki/ContractTest.html

**My analysis.** Two clean options, both defensible:

1. **Run the `nspi` profile in CI with `vulners` disabled** (`--script` list minus
   `vulners`, or `--script-args` gating). The gate then proves the wire, the nmap
   subprocess, the XML parse, the signing and the DB rows — everything Dmitri owns.
2. Keep `vulners` in a **separate, non-blocking, scheduled** job that is allowed to
   fail loudly without red-flagging PRs.

Do not put a live vulners.com call inside a required check. Doing so makes every PR
merge depend on a third party's uptime and an unpublished rate limit.

---

## 5. The local device simulator pattern

**It is a recognised, first-party-supported pattern.** AWS ships an IoT Device
Simulator solution whose stated purpose is to let customers "get started quickly
assessing AWS IoT services without an existing pool of devices" and "create and
simulate thousands of connected devices".
— https://github.com/aws-solutions/iot-device-simulator
— https://docs.aws.amazon.com/solutions/latest/iot-device-simulator/overview.html
Azure had the equivalent (Device Simulation solution accelerator: define device models,
message formats, twin properties and methods; "run simulations for one to thousands of
devices connecting to any IoT hub"), now archived/unsupported as of 2021-05-06.
— https://learn.microsoft.com/en-us/previous-versions/azure/iot-accelerators/iot-accelerators-device-simulation-overview
— https://github.com/Azure/device-simulation-dotnet
balena documents both a local-development mode and virtual devices that join a
balenaCloud fleet by passing `API_TOKEN` and `FLEET`, while warning that "virtual
devices tend to be more difficult to work with than physical devices and are often much
slower". — https://docs.balena.io/learn/develop/local-mode
— https://github.com/balena-io-experimental/balena-virt

**On pointing it at production.** The AWS README is explicit: "This solution is
designed to simulate device data for testing. It is not recommended for use in
production environments." (The solution was also deprecated 2025-01-29.)
— https://github.com/aws-solutions/iot-device-simulator

**Where I have to be honest about a gap.** I did **not** find a first-party document
enumerating the specific production hazards (fleet-count skew, billing distortion, data
pollution, credential blast radius) as a list. AWS's statement is a blanket "not for
production" without a rationale; balena's caution is about developer ergonomics, not
production safety. The hazards below are **my analysis**, not documented guidance:

- Dmitri's simulated agent will occupy a real `agent_id` row, appear in agent counts,
  and its scan results will be indistinguishable from customer data unless tagged.
- Provisioning a simulator means a real long-lived credential on a laptop.
- Findings from a fake ICS target inflate whatever severity/finding aggregates the
  Home screen shows.

Given Dmitri is pre-MVP with no customers, "production" is currently a
demo environment, so the risk is low *today* and rises the moment a real customer org
exists. The cheap insurance is to create a dedicated org for the simulator now, so the
habit is established before it matters — not to build a separate staging stack.

---

## 6. What the sources agree and disagree on

- **Agreement:** start small; broad/large tests are slower, flakier and costlier;
  external network calls belong outside the fast feedback loop; device simulators are a
  legitimate development tool.
- **Disagreement / tension:** Fowler explicitly allows skipping the pyramid *if* the
  high-level tests are "fast, reliable, and cheap to modify"
  (https://martinfowler.com/bliki/TestPyramid.html), which is the strongest available
  argument *for* the full-wire gate. Google's flakiness data
  (https://testing.googleblog.com/2017/04/where-do-our-flaky-tests-come-from.html)
  is the strongest argument against believing a compose-plus-nmap-plus-vulners test
  will be fast and reliable. My read: the escape hatch does not apply here, because
  `vulners` alone guarantees the "reliable" precondition fails.
- **Not found:** authoritative guidance choosing testcontainers vs compose for Python;
  first-party nmap guidance on testing NSE-dependent consumers; a documented list of
  production-simulator hazards.

---

## 7. Recommendation

**1. Smallest genuinely useful first step — build the local simulator (proposal B).**
One `docker-compose.yml` + one Debian image that: generates an Ed25519 keypair,
provisions against a configurable base URL, opens the outbound WS, accepts a scan
command, runs `nmap` against a configurable target, signs, and `POST`s to
`/api/v1/scans`. Target defaults to a second container (Samba) so it produces non-empty
findings offline. That is the artifact both proposals need. It unblocks the
Hosts/Scans/Agents screens immediately, and it is the *only* deliverable here with a
user waiting on it.

**2. ICS emulators — later.** Ship Samba only (ports 445/139, real service detection).
Add pymodbus/OPC-UA/cpppo when a concrete `nspi`-profile bug demands it, and build them
properly when you do (no placeholder container — `CLAUDE.md` "No temporary code").

**3. Local simulator before the CI gate.** Ordering is not close: the simulator has a
waiting consumer (the unbuilt UI screens), the gate does not. Once the simulator runs
green by hand, the CI job is `docker compose up` + a pytest file asserting DB rows —
a small increment, not a project. When you add it:
   - **drop `vulners`** from the CI scan profile, or move it to a separate scheduled,
     non-blocking job (§4);
   - start it **non-blocking**, promote to required only after ~2 weeks of no false
     reds (Fowler on contract-test failures);
   - keep Postgres as a GitHub `services:` container as CI already does; build only the
     agent and target images.

**4. Drop from scope for now:** the QEMU arm64 install-only step and the shared
`provision.sh`/installer-playbook validation. Both are real concerns, neither is a
test — the arm64 wheel question is answered once by a manual `docker run --platform
linux/arm64` and re-answered when you bump `pydantic-core`/`cryptography`, and the
installer script is an installer refactor wearing test clothes. Track them separately.

**5. Is `size:L` (8–16h) realistic for plan (A) as described?** **No — my estimate,
not a documented one.** Plan (A) contains: a 4-container compose stack, three bespoke
ICS emulators, a shared installer script refactor, a QEMU cross-arch job, a
path-filtered blocking workflow, and structural finding assertions. Each of the first
four is itself an L-sized unknown for a solo developer, and the first run of anything
involving `nmap` inside Docker (raw-socket capabilities, `--privileged`/`NET_RAW`,
container-network scan semantics) reliably eats a day on its own. Call plan (A) XL and
split it. The recommendation above — simulator + Samba, no CI gate — is a genuine
`size:M`, and the follow-up CI gate on top of it is a genuine `size:S`.

---

## Sources

- Martin Fowler — TestPyramid (fewer broad tests; the "fast, reliable, cheap" escape hatch): https://martinfowler.com/bliki/TestPyramid.html
- Martin Fowler — IntegrationTest (narrow vs broad; prefer narrow): https://martinfowler.com/bliki/IntegrationTest.html
- Martin Fowler — BroadStackTest (slower, harder to maintain; doubles for remote systems): https://martinfowler.com/bliki/BroadStackTest.html
- Martin Fowler — ContractTest (run on the external service's rhythm; don't break the build; avoid production): https://martinfowler.com/bliki/ContractTest.html
- Google Testing Blog — Test Sizes (small/medium/large; network allowed only at medium+): https://testing.googleblog.com/2010/12/test-sizes.html
- Google Testing Blog — Where do our flaky tests come from? (size correlates with flakiness; "start with the smallest tests you can"): https://testing.googleblog.com/2017/04/where-do-our-flaky-tests-come-from.html
- Google Testing Blog — Hermetic Servers (bundle/inject external dependencies; these are large, slow tests): https://testing.googleblog.com/2012/10/hermetic-servers.html
- GitHub Actions — About service containers (same-job only, Linux runners, no composite actions, image-oriented): https://docs.github.com/en/actions/using-containerized-services/about-service-containers
- Testcontainers — Introducing Testcontainers (IDE-local runs, auto cleanup, isolation; compared to in-memory DBs, not compose): https://testcontainers.com/guides/introducing-testcontainers/
- testcontainers-python — Docker Compose module (`DockerCompose`, `build`, `env_file`, per-service host/port): https://testcontainers-python.readthedocs.io/en/testcontainers-v4.12.0/compose.html · https://github.com/testcontainers/testcontainers-python/blob/main/compose.rst
- nmap NSEDoc — `vulners` ("no way to use a local db… we do make requests to a remote service"): https://nmap.org/nsedoc/scripts/vulners.html
- nmap — NSE tutorial (no testing guidance present): https://nmap.org/book/nse-tutorial.html
- vulhub — Pre-Built Vulnerable Environments Based on Docker-Compose: https://github.com/vulhub/vulhub · https://vulhub.org/
- Greenbone openvas-scanner (nmap XML/greppable as consumed input; test strategy not documented): https://github.com/greenbone/openvas-scanner
- AWS IoT Device Simulator — purpose and "not recommended for use in production environments"; deprecated 2025-01-29: https://github.com/aws-solutions/iot-device-simulator · https://docs.aws.amazon.com/solutions/latest/iot-device-simulator/overview.html
- Azure IoT Device Simulation — device models, any IoT hub, archived 2021-05-06: https://learn.microsoft.com/en-us/previous-versions/azure/iot-accelerators/iot-accelerators-device-simulation-overview · https://github.com/Azure/device-simulation-dotnet
- balena — local mode; virtual devices joining a fleet via `API_TOKEN`/`FLEET`; virtual devices "more difficult to work with… much slower": https://docs.balena.io/learn/develop/local-mode · https://github.com/balena-io-experimental/balena-virt
