# Python OPC UA migration

Authorized by the user on 2026-10-21: replace the C#/.NET implementation entirely
with Python and preserve Tasks 1–4 behavior and security. The latest user instruction
supersedes automatic continuation: finish the migration and await a new command
before starting Task 5. This
decision supersedes the original SDK choice and the approval requests in the
historical `STRUCTURAL_REEVAL.md`. No second architecture approval is needed.
Tasks 1–4 remain completed history; their acceptance tests must pass again against
the Python implementation. Migration tasks M1 and M2 precede Task 5.

## Decision and source evidence

Implementation status: M1 and M2 are complete and independently approved. The
runtime and client tests use the Python worker; C# sources, projects, harness and
active .NET launch paths are removed. The integration matrix passed 476 tests
with 5 skipped; the final retained-evidence correction passed 31 mapper/worker
tests and four targeted loopback regressions. Ruff, Black 24.3 and diff checks
passed. The wheel audit found no .NET artifacts. Task 5 remains pending a new
user command; ARM64 validation remains Task 9.

Use the exact runtime dependency `asyncua==2.1.0`, with a small audited decoder
patch module and a bounded socket adapter installed only in a new worker process.
Keep the existing metadata-only `OpcUaClient` interface and JSON schema. Reuse
upstream UA types, encoders, secure-channel state machine and session services.
Do not implement another OPC UA stack or vendor the complete library.

Source inspected: the installed 2.1.0 distribution in
`%LOCALAPPDATA%/Dmitri/task4-validation-venv/Lib/site-packages/asyncua/` and its
`asyncua-2.1.0.dist-info/METADATA`. The metadata requires Python >=3.10 and lists
LGPLv3-or-later; preserve upstream license files in the dependency wheel and add
an attribution next to the adaptation. The application supports Python 3.11/3.12.
Cryptography's runtime requirement becomes >=45 through this dependency; resolve
and lock the complete dependency graph. ARM64 wheel availability and execution
remain a Task 9 gate, not an inference from Python portability.

| Upstream source and seam | Observed behavior | Required adaptation |
|---|---|---|
| `client/ua_client.py:UASocketProtocol._send_request` | All typed MSG/OPN/CLO requests serialize here, then call synchronous `transport.write(msg)`. | Exact request-class plus TypeId allowlist, one-use outbound permit, guarded socket adapter. |
| `UASocketProtocol.send_hello` | Separate direct write; Hello receive/send buffer defaults do not establish our contract. | Explicit HEL with 65536/65536/131072/16; same pacing and budget authority. |
| `UASocketProtocol._process_received_data` | Retains incomplete data before the secure connection handles it. | Bound frame lengths and accumulation before calling the upstream parser. |
| `common/connection.py:TransportLimits.update_client_limits` | ACK can replace all local limits. `create_hello_limits` assigns MaxMessageSize from max_chunk_count in the inspected distribution. | Validate ACK before delegation, construct HEL explicitly and never permit caps to increase. |
| `ua/ua_binary.py:_Bytes.unpack`, `_String.unpack` | Signed length is read before `data.read`; no application quota. Negative lengths other than -1 are not rejected here. | Validate length and remaining bytes before read/decode; separate string and byte caps. |
| `_create_uatype_array_deserializer`, `_Primitive1.unpack_array` | Variant/primitive arrays reach list/tuple allocation from a wire length without our quota. | Validate <=1024 before iteration, format construction, unpack or list allocation. |
| `_create_list_deserializer` | Dataclass lists have a separate length path. | Guard this path too; a Variant-only patch is insufficient. |
| `_create_dataclass_deserializer`, `variant_from_binary`, `extensionobject_from_binary` | Recursive decoder factories and cached closures can bypass a top-level guard. ExtensionObject length -1 can consume the remaining parent buffer. | Depth guard on generated decoders and recursive Variant/ExtensionObject entry; strict bounded ExtensionObject body. |
| `variant_from_binary`, `_reshape` | Dimensions can cause expansion; upstream's reshape cap is much larger than our array cap. | <=8 dimensions, nonnegative dimensions, checked product <=1024 and equal to the actual flat element count, before reshape; no padding from declared dimensions. |
| `client/ua_session.py:UaSession` | Create/Activate/CloseSession, Browse/BrowseNext and Read use the client's protocol. | Reuse explicit typed services without `Client.connect()`, Node helpers, supervisor, reconnect, health checks or publish loop. |

Primary upstream references: [binary codec](https://github.com/FreeOpcUa/opcua-asyncio/blob/v2.1.0/asyncua/ua/ua_binary.py),
[client protocol](https://github.com/FreeOpcUa/opcua-asyncio/blob/v2.1.0/asyncua/client/ua_client.py),
[connection](https://github.com/FreeOpcUa/opcua-asyncio/blob/v2.1.0/asyncua/common/connection.py).
The installed wheel is the implementation baseline; verify installed source and
lock hashes during M1 rather than relying on line numbers in a Git tag.

## Files and boundaries

All production paths below are under `hardware-agent/src/agent/ot/opcua/`.

| File | Responsibility |
|---|---|
| `client.py` (existing) | Launch `[sys.executable, "-m", "agent.ot.opcua.worker"]`; preserve public methods and parsers, bounded IPC reads, timeout/cancel kill and reap. Remove executable discovery and environment overrides. |
| `worker.py` (new) | Read one bounded JSON command, validate fields independently, install guards before UA decoding, run one operation, emit one sanitized JSON result, exit. No listener. |
| `bounded_decode.py` (new) | Worker-only, idempotent installation of audited patches into pinned `asyncua.ua.ua_binary`; bounded length helpers and decode depth. No import-time patching. |
| `guarded_transport.py` (new) | Guarded `UASocketProtocol` subclass, explicit serialized operation coordinator, bounded inbound framing, raw socket adapter/pumps, actual-send statistics and cleanup slot ownership. |
| `worker_mapping.py` (new) | Port the existing `OpcUaMapper` behavior from `helper/Program.cs`: anonymous session, bounded BFS, metadata reads and status-only Value probes. Raw SDK objects stay here/in worker. |
| `THIRD_PARTY_NOTICES.txt` (new) | asyncua attribution/license reference and description of the local runtime adaptation. Do not retain an orphan OPC Foundation notice for deleted C# code. |
| `models.py`, `inventory.py`, `mapper.py` (existing) | Preserve external dataclasses, reason vocabulary, budgets and observations; update worker wording or parsers only where required by parity. |

Only `worker.main()` installs patches. Importing application models, client or
test fixture must leave asyncua unchanged. The loopback lab server runs in the
parent/test process and uses its original decoder. Never edit site-packages on
disk. Assert dependency version and expected callable seams before opening a
socket; unsupported version or guard installation failure returns a closed error.
Clear all affected cached decoder factories after replacing the byte/string,
array, recursive and ExtensionObject seams: `_create_uatype_deserializer`,
`_create_uatype_array_deserializer`, `_create_list_deserializer`,
`_create_type_deserializer`, `_create_dataclass_deserializer`. Wrapped factories
must resolve recursive calls through the guarded module globals. Prove cached
and lazy recursive cases in tests; do not assume replacement of a module name
invalidates a previously captured callable.

Wire decoder limits: each array <=1024; nesting <=8; String <=1024 UTF-8 bytes
(then existing 128/256-character export caps); ByteString/ExtensionObject body
<=65536 and <=remaining bytes before copying. Permit -1 only where the UA nullable
type permits it; reject other negative sizes. Generic UA lists retain their
expected Python null/list representation. ExtensionObject bodies must be fully
bounded; reject malformed lengths/encoding, do not allow the upstream -1 fallback.
Use registered static UA types only, never load device type definitions, XML or
code. Unknown ExtensionObjects can remain bounded opaque data within the worker;
no opaque body is exported. Check array counts before any element decoder runs.
For fixed-size elements also check count*width against remaining bytes. Nesting
must include DiagnosticInfo recursion, nested Variants, dataclasses and registered
ExtensionObjects, and unwind in `finally` on all failures.

## Transport, actual sends and cancellation

The worker uses one numeric AF_INET socket and one serialized request stream.
Reuse `UASocketProtocol`/`SecureConnection`; give `UaClient` the guarded protocol
without invoking its default unrestricted `connect_socket` factory. Connect with
the validated discovered IPv4/port only. Endpoint paths are protocol data and
never replace the socket destination. Use explicit low-level session parameters,
including the Anonymous policy ID actually advertised for the selected endpoint.

The adapter supplies the small transport surface used by the protocol (`write`,
`close`, `abort`, connection state), while reader/writer tasks own the raw socket.
`write` stages one bounded serialized logical request with a one-use permit
created by the exact-type guard during synchronous serialization. Missing,
reused, mismatched or stale permits fail closed. Validate request TypeId against
its permitted class before serialization; changing a typed object's TypeId must
not bypass the guard. No caller receives the socket or adapter.

Do not use ordinary `asyncio.Transport.write()` return as proof of an actual
send: [Python documents that it buffers asynchronously](https://docs.python.org/3/library/asyncio-protocol.html#asyncio.WriteTransport.write).
The serialized writer awaits `loop.sock_sendall` for each frame. At first-frame
admission it checks cancellation/deadline, the sole request budget and >=100 ms
pacing, and claims a cleanup slot if applicable. Commit the service count once
the first complete frame's send finishes. Count full-frame bytes/chunks after
their sends finish; further chunks consume no new request or pacing unit. Await
the send receipt before returning an upstream response to a caller, including
OPN and no-response CLO. A response can arrive quickly; it must not let mapping
observe a stale request count. Override the small lifecycle wrappers as needed:
upstream CLO cancels its response future, which must not cancel the staged send.

Serialization/pre-send failure has no sent count. A completed send followed by
response timeout retains its count. `sock_sendall` can fail after a partial
write: increment attempt telemetry, retain the one-shot reservation, abort, and
mark request count unknown rather than assert a confirmed zero or full send.
Return that flag through IPC and `OpcUaClientResult.request_count_known`; existing
stage accounting conservatively charges unknown usage. No retry or automatic
renewal/reconnect. A socket send confirms submission to the local socket, not
peer receipt; fixture wire observations independently prove receipt in the lab.

Allow only HEL, OpenSecureChannel, GetEndpoints, CreateSession, ActivateSession,
Browse, BrowseNext, Read, CloseSession and CloseSecureChannel. Guard direct
`_send_request` calls as well as public service methods; explicitly test Write,
Call, HistoryRead/Update, registrations, node/reference mutations, subscriptions,
monitored items and Publish. Blocked attempts increment measured blocked/write
attempt telemetry, emit no frame and do not increase sent totals. Preserve the
existing measured `write_requests_sent` field's interpretation and tests; do not
replace it with a constant zero. Keep request, blocked-attempt and byte/chunk
metrics distinct.

Normal budget: configured <=32 per OPC UA host allocation (the stage shares <=64
with Modbus), ordinary work stops at budget-2. Reserve exactly one CloseSession
and one CLO independently, claimed once before a send, never reused after
ambiguity. Release continuation uses ordinary capacity, never a cleanup slot.
Budgets below two admit no ordinary work; do not connect for an unusable allocation.
Mapping and inventory consume the same stage allocation including both workers'
HEL/channel/cleanup costs. Preserve the current stage's unknown-count policy.

Reader uses bounded `sock_recv` calls, validates the 8-byte TCP header before
retaining the declared body, enforces chunk <=64 KiB, cumulative on-wire message
<=128 KiB / <=16 chunks and received total <=4 MiB, then forwards complete frames
to upstream. Count bytes before decode. Reject malformed minimum sizes, invalid
frame kind/chunk transitions, mismatched message sequence, 17th chunk and
oversized header without waiting for its body. Reset per-message accumulation
only on completed/aborted messages; retain the per-service byte total. ACK must
have positive bounded buffers/message/chunk values, and cannot raise any local
cap. Feed bounded complete ACK only after validation. Set the SDK limits too as
defense in depth, including caps reduced by the peer.

Per operation <=2 s or remaining time; host <=90 s; industrial stage <=600 s;
global deadline applies. Worker owns its overall monotonic deadline. Normal
cleanup <=1 s inside that deadline. On worker cancellation/deadline abort socket,
cancel pumps and send no cleanup. Parent cancellation kills and reaps the worker;
there is no normal-cleanup signal on that path. Recheck deadline after pacing
and before socket send. No queued request may run after cancellation. Preserve
partial metadata when the worker can return it; parent hard-kill keeps unknown
count and existing cancellation semantics.

## Mapping and IPC parity

Evidence-state review clarification: initialize the observed session/Browse/Read
state before the outer operation try block. Every result path, including metadata
failure and lifecycle cleanup, must reuse that retained state. A confirmed success
is monotonic; later failures change coverage and reasons, not the fact already
observed. This preserves the existing architecture rather than introducing a new
aggregation policy.

Port the completed C# algorithm, including its reviewer fixes, rather than
replacing it with high-level Node traversal. Keep Objects root, hierarchical
forward Object/Variable BFS, visited-before-queue, local textual NodeIds only,
depth 4, nodes 128, references 512, page 32, pages 16, BrowseNext per node 4,
one active continuation, metadata batches <=16 and <=8 ns>0 Value probes.
Retain denial/timeout/null facts, selection index, security provenance and
observation-size trimming semantics. Discard process Variants and their length,
timestamps and derivatives immediately; only status and attempt instant survive.
Inventory never opens a session or reads a process Value. No new findings.

Keep one closed JSON command/result per subprocess; request <=4 KiB, response
<=128 KiB. Parent must stop reading at cap+1 instead of `communicate()` buffering
arbitrary stdout before validation. Drain/wait with bounded time; suppress stderr
and all SDK logging in the worker. Never log exceptions with `str`/`repr`, SDK
objects, buffers, request/response bodies or process values. Worker constructs
only allowlisted output fields, sanitizes target URLs and metadata, then applies
the serialized output cap. Parent retains independent typed validation. Test
secrets in endpoint URLs, text, certificate fields, error diagnostics and Value.

## Removal and delivery audit

Delete tracked `hardware-agent/src/agent/ot/opcua/helper/{Program.cs,
opcua-bridge.csproj,LICENSE.txt,.gitignore}` and
`hardware-agent/tests/dotnet/opcua-bridge.tests/{Program.cs,
opcua-bridge.tests.csproj}` after Python parity. Remove .NET discovery,
`DMITRI_OPCUA_BRIDGE`, `DOTNET_HOST_PATH`/`DOTNET_ROOT` setup and helper build/skip
fixtures from `tests/unit/test_opcua_client.py`; check mapper tests for imported
fixtures. Remove only generated artifacts belonging to these exact directories
if cleanup is needed, after verifying their resolved paths. No unrelated edits.
Historical Tasks 1–4 descriptions and structural review remain an audit trail.

Inspection found no .NET build references in `hardware-agent/packaging/build-deb.sh`
or `.github/workflows/agent-release.yml`, and no root ignore entry for the helper.
The helper owns its own generated-output ignore. Recheck after migration with
`rg` including hidden files. Do not add a .NET install, executable, NuGet restore
or alternate runtime. The existing builder exports `--no-dev` locked runtime
requirements, builds the application wheel and downloads its wheelhouse; promoting
asyncua into runtime dependencies is required now. Task 9 validates offline ARM64
installation/import, dependency license files and inventory/mapping smoke; it is
not permission to leave the Python migration dependent on .NET until packaging.

## Sequential implementation and gates

1. **M1 — bounded worker inventory and transport/decoder.** Add worker entry,
   decoder guards, socket adapter, explicit HEL/ACK, GetEndpoints and sanitized
   inventory response; promote/pin asyncua and lock. Exercise the worker directly
   from tests while keeping the existing facade until mapping parity is ready.
   No fake map implementation or temporary runtime fallback. Tests:
   `test_opcua_decode.py`, `test_opcua_transport.py`, `test_opcua_worker.py` (new).
   Reviewer must inspect each pre-allocation seam and test the real pinned codec,
   generic list, Variant array, string/bytes, ExtensionObject and recursive paths.
2. **M2 — complete mapping, switch facade, remove .NET.** Add worker mapping,
   switch the existing facade to Python, preserve stage/caller contracts, remove
   C# and its test/build paths, and port all guard-harness assertions to Python.
   Tests: existing client/inventory/mapper/untrusted/stage/Modbus/runner/headless/
   daemon/TUI/egress/contract suites plus loopback wire observations. Preserve
   Task 4 DMITRI self-name and 32/64 limits. Reviewer requires actual worker
   success, denial, malformed response, cleanup at ordinary cutoff in both orders,
   duplicate cleanup block, cancellation during connect/Read/BrowseNext, no CLO
   after deadline, no forbidden peer request, metadata privacy and parent/fixture
   decoder isolation. Only then begin Task 5.
3. **Task 5 — backend persistence and ingest/read.** Existing target and contract
   remain; revalidate Alembic head before naming the migration. Start
   `./database.sh --test` before backend suite; missing `dmitri_test` is not a pass.

Focused guard tests must reject limits before allocation/element decode using
spies/sentinels, not rely solely on post-decode list truncation or memory sampling.
Test tiny malformed messages declaring enormous arrays and negative lengths,
cached decoder creation, dimensions product, 16/17 chunks and reset, header-only
oversize, ACK zero/oversize, byte totals, response timeout after a real send,
serialization failure before send, multi-chunk one-count behavior and partial
send ambiguity. Wire-observed fixture counters must agree with reported counts
on completed runs and show >=100 ms request pacing, including lifecycle.

The architectural feasibility is supported by the inspected seams. Passing the
new tests is still required before claiming parity. Main risks are cached decoder
closures, depth accounting, cancellation of a queued writer, fast-response send
receipt ordering, CLO's no-response lifecycle, and LGPL dependency packaging.
No production code, environment startup, commit or deployment was performed in
this design step.
