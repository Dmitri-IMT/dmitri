# Structural reevaluation: OPC UA request-send accounting

## Symptom

Task 4 requires request counters and the shared request budget to describe outbound service requests that reach the transport. The current `GuardedTransportChannel.SendRequestAsync` in `hardware-agent/src/agent/ot/opcua/helper/Program.cs` calls `stats.SentRequest(name)` immediately before `inner.SendRequestAsync`. A serialization, channel-state, or transport failure before an outbound frame is sent therefore increments the sent counter. Conversely, the raw `CountingTcpByteTransport` counts only HEL, OPN, and CLO frames through `RequestAtStart`; ordinary MSG service requests (GetEndpoints, Browse, BrowseNext, Read, and session lifecycle) are not associated with their service name there.

There is a second structural hazard: budget and pacing are currently admitted at both `GuardedTransportChannel.AdmitServiceAsync` and `TransportStats.AdmitAndSend` for channel messages such as OPN. Moving only the counter would retain double admission or create a gap in enforcement. `ARCHITECTURE.md` already defines the intended meaning: one request is an application/lifecycle UA or Modbus send, counted at the transport even if its response fails; frame bytes/chunks remain separate metrics.

## Root cause

The code has two layers with different knowledge. The typed `ITransportChannel` boundary knows the allowed CLR request type, but cannot prove the request was sent. The `IUaSCByteTransport.SendChunkAsync` boundary can observe the actual serialized outbound frame and whether the underlying send completed, but currently recognizes only transport control frames. Counting a service call at the former boundary treats invocation as transmission; counting only at the latter without carrying service identity loses MSG categories.

The transport wrapper is the right authority for actual send accounting. `GuardedTransportChannel` should remain the early allowlist gate; it must not be the source of the `*_sent` total.

## Options considered

1. **Keep counting before `inner.SendRequestAsync`.** Simple, but violates the sent-counter contract and reports false sends on pre-send failures. Reject.
2. **Parse the UA Binary MSG body at the byte transport.** The service type ID is available in a clear None-security message, but this couples policy/accounting to UA Binary header details, chunk assembly, NodeId encodings, and future security modes. It also adds another parser to a security-sensitive framing path. Do not choose as the primary mechanism.
3. **Carry the guarded service identity to the transport send and acknowledge it after the underlying send completes.** Keep the typed gate and map the service category at the guard; let the byte transport admit/paces the request once and record its sent count only after the first outbound request frame completes. This avoids parsing the untrusted inbound protocol and preserves typed categories. Recommend, subject to a focused SDK-path test proving the correlation survives UA-.NETStandard 2.0.1's async send path.

## Recommendation

Introduce a scoped outbound-request context in the helper that associates the current allowed request name and a one-shot send state with its transport send. An `AsyncLocal` scope is a viable implementation if verified against the pinned SDK's real call path; if the SDK dispatches sends outside the flowed execution context, use an explicit correlation token or a small serialized send coordinator instead. Do not silently count an uncorrelated MSG as a named application request. The agent currently issues one request at a time per helper process, so a serialized coordinator is also a valid simpler fallback, but document and test that invariant.

The send flow should be:

1. `GuardedTransportChannel.SendRequestAsync` validates the exact request type against the existing closed allowlist, maps it to the metric category, and establishes the scoped context. It does not increment `requests_sent`.
2. `CountingTcpByteTransport.SendChunkAsync` recognizes one request start (HEL, first OPN chunk, first MSG chunk, or CLO), performs the sole budget admission and pacing before forwarding, and increments attempt accounting at that boundary. For MSG it reads the scoped category; for OPN it uses the scoped `OpenSecureChannel` category when available. HEL/CLO keep their transport categories.
3. After the wrapped `inner.SendChunkAsync` succeeds for the first chunk of that request, the wrapper records exactly one service request and its category. A response timeout after this point leaves the sent count incremented. A failure before entering the byte send or before a successful first frame leaves it unchanged. `bytes_sent` and `chunks_sent` remain incremented only after successful sends as they are now.
4. Further chunks belonging to the same UA request do not increment request count, budget, or request pacing again. Reset the one-shot state at the request boundary and clear the scope in `finally`.
5. Remove the duplicate service-level `AdmitServiceAsync` budget/pacing charge, or reduce it to a non-counting authorization/reservation that cannot consume budget independently. There must be one budget charge and one pacing interval per logical UA service/lifecycle request, including OPN. A blocked allowlist attempt remains counted by the existing blocked-attempt telemetry but is never counted as sent.

If the socket API can partially write and then throw, report the metric as a *request-send attempt* at the boundary and keep confirmed full-frame bytes separate; do not claim a complete frame was sent unless the byte transport confirms it. The exact partial-write behavior of the pinned SDK/socket implementation needs to be verified during implementation. Do not add raw request bodies or process values to telemetry.

## Files and test expectations

Implementation should stay within `hardware-agent/src/agent/ot/opcua/helper/Program.cs`; no wire contract or Python call-site change is needed if the existing `requests`, `requests_total`, `request_attempts`, `bytes_sent`, and `chunks_sent` fields retain their meanings. Confirm the Python consumers in `hardware-agent/src/agent/ot/opcua/client.py`, `inventory.py`, and `mapper.py` continue to handle timeout/error results and known/unknown counts correctly.

Extend `hardware-agent/tests/dotnet/opcua-bridge.tests/Program.cs` (and its harness helpers as needed) with assertions against the real wrapper path:

- a request rejected or serialization/channel validation failure before `SendChunkAsync` has sent a frame leaves `requests_total` and the category map unchanged;
- an underlying send that fails before completing the first request frame does not claim a confirmed send (and reports the attempt according to the explicitly selected partial-write semantics);
- a completed outbound request followed by response timeout is counted once under its service category;
- multi-chunk OPN/MSG counts once per logical request; HEL and CLO retain their own one-count lifecycle behavior;
- OPN does not consume two units of budget or two pacing intervals because both channel layers observed it;
- a blocked forbidden service produces no outbound frame and no sent count;
- unrelated transport data cannot inherit a stale service category after success, exception, or cancellation.

Add/adjust `hardware-agent/tests/unit/test_opcua_client.py` coverage proving `request_count_known` and the result counter distinguish a pre-send failure from a timeout after a send. Preserve the current timeout safety rule: if the bridge cannot establish whether a frame was sent, return an unknown count rather than fabricate zero or a positive count. At the shared-stage seam, keep `test_opcua_stage.py`'s host/protocol budget assertions to ensure the transport's single admission still enforces the 32-per-protocol and 64-per-host limits.

Keep the existing Modbus transport instrumentation in `hardware-agent/src/agent/ot/modbus/readonly.py` and its tests (`hardware-agent/tests/unit/test_modbus_readonly.py`) unchanged unless the independent Task 4 tester identifies a concrete failing send-boundary case. Do not couple the OPC UA fix to Modbus.

## Risks and unresolved checks

- The critical unknown is whether UA-.NETStandard 2.0.1 executes `IUaSCByteTransport.SendChunkAsync` in an async context that carries an `AsyncLocal` scope from `ITransportChannel.SendRequestAsync`. Verify with the pinned SDK and a real loopback request, not only a mock.
- Confirm how the SDK chunks OPN and MSG and whether first-chunk completion constitutes the intended counted attempt. Response timeout after a complete frame must remain counted.
- Ensure cancel/deadline handling still aborts without cleanup sends, while ordinary cleanup consumes the reserved budget exactly once.
- Preserve category names and output schema consumed by Python; this proposal does not change public counters or claim to count TCP packets.

This document records the structural recommendation only. It does not implement the change or mark Task 4 complete.


# Structural re-evaluation 2: reserve session and channel cleanup independently

## New reviewer finding

The fourth Task 4 review found a normal-path cleanup failure at the transport budget boundary. `TransportStats.ReserveRequest` currently exempts only `CloseSecureChannel` from the ordinary threshold `_budget - 4`. `CloseSession` is an MSG service request: `GuardedTransportChannel.SendRequestAsync` scopes its type name in `OutboundServiceScope`, `RequestAtStart` reads that name for the first MSG chunk, and `ReserveRequest` therefore admits it as ordinary work. Once regular mapping reaches the threshold, the `finally` path's `CloseSessionAsync` is rejected with `request_budget_exhausted`; the later CLO can still use the cleanup threshold. This may leave a session without an orderly `CloseSession` before the channel closes.

The four reserved units are a pool with no per-lifecycle ownership today. Merely adding `CloseSession` to a broad `cleanup` boolean would allow repeated close requests to consume all remaining capacity and could let one cleanup kind starve the other.

## Root cause

The budget reservation is correctly located at the outbound byte-transport boundary, but cleanup classification is incomplete and not one-shot. The typed channel knows `CloseSessionRequest`, while the transport sees MSG plus the `AsyncLocal` service identity. CLO has a directly recognizable transport kind and bypasses the ordinary threshold. These two cleanup operations therefore enter the same accounting layer through different identification paths, and only one is treated as cleanup.

`GuardedTransportChannel` already serializes typed service sends with `_serviceSendCoordinator` and scopes the exact request category around `inner.SendRequestAsync`. `CountingTcpByteTransport` makes the budget reservation at first logical frame, then commits it after `inner.SendChunkAsync` completes. The revised design should keep this single authority: do not add budget consumption in the guard or reserve cleanup capacity separately at both layers.

## Revised design recommendation

Reserve exactly two of the existing per-helper request budget for the normal lifecycle pair: one dedicated `CloseSession` slot and one dedicated `CloseSecureChannel` slot. Change the ordinary admission cutoff from `_budget - 4` to `_budget - 2`, so the declared total budget remains unchanged and usable capacity is not stranded. Keep `CanReleaseContinuation` aligned with the same ordinary cutoff. A configured budget below two must safely allow zero ordinary requests and only the cleanup slots that fit (the implementation should reject an unusable budget or define this case explicitly rather than underflowing).

At `TransportStats`' single transport-level reservation point:

1. Classify the first MSG frame from the current request-scoped outbound context. Only the exact `CloseSession` category is eligible for its reserved slot; a missing or mismatched context remains fail-closed. Classify CLO as `CloseSecureChannel` from its frame kind.
2. Track the two reserved cleanup kinds independently, including an in-flight/claimed state under `_sync`. Each kind may claim its slot once; the other kind remains independently available. Ordinary service requests cannot consume either slot.
3. Keep `GuardedTransportChannel`'s semaphore and `OutboundServiceScope` around the entire SDK call. Prefer a scoped correlation object with service name and one-request identity over a bare `AsyncLocal<string>` if practical; it must flow to the pinned SDK's byte-send callback, be restored in `finally`, and never leak a prior request category. The existing serialized-send invariant should be documented and tested. If the SDK does not preserve the context, fail closed and use an explicit token/coordinator; do not infer `CloseSession` from arbitrary MSG bytes.
4. Do not count a cleanup request as sent until its first frame's underlying `SendChunkAsync` completes, preserving the current sent-counter contract. However, claim its one-shot slot at admission and do not make it reusable after an ambiguous transport exception: a partial socket write cannot be ruled out, and retrying could duplicate/corrupt the lifecycle request. An exception before the transport boundary is reached claims no slot. Document this conservative distinction between slot claim, attempt telemetry, and confirmed sent count.
5. After either cleanup slot is committed or claimed, a duplicate of that same type is blocked without an outbound frame. A send of the other cleanup type is still eligible once, subject to the total `_budget`; no path may admit more than the configured total. Cancellation/deadline policy remains authoritative: when already cancelled/expired, do not initiate cleanup and abort the socket as currently specified.

This recommendation changes the architecture's explicit cleanup reserve from four units to two. The other two units are not needed by the identified normal lifecycle and must not be presented as guaranteed cleanup retries. If later implementation evidence establishes another mandatory lifecycle request, revise the reservation from that evidence before adding a slot. Because `ARCHITECTURE.md` currently says four units, update it only after human approval of this structural change; Task 4 remains blocked until then.

## Required tests before reopening Task 4

Extend the .NET bridge harness and the focused Python/scan-stage tests after human approval:

- With a small deterministic budget, admit ordinary requests exactly up to `_budget - 2`; verify further ordinary requests and continuation work stop at the same cutoff.
- At that boundary, admit one `CloseSession` MSG request and one `CloseSecureChannel` CLO independently, in either order. Confirm each is counted once only after the underlying first-frame send succeeds and the combined count never exceeds `_budget`.
- After claiming/sending one cleanup kind, reject a duplicate of that kind with no frame and no extra sent count, while allowing the other reserved kind once.
- Simulate an exception before entering the byte transport and confirm no cleanup slot is claimed. Simulate an ambiguous exception from the wrapped send and confirm the sent counter remains unconfirmed, the slot is not reusable, and the transport/helper abort path prevents a duplicate send.
- Exercise CloseSession through the real pinned SDK loopback path, not only direct `OutboundServiceScope.Enter`, proving its MSG send retains the request-scoped identity across awaits and receives the dedicated reservation. Assert that a later unrelated MSG cannot inherit the identity after success, exception, or cancellation.
- Exercise normal mapper completion at the ordinary cutoff and verify graceful `CloseSession` then `CloseSecureChannel`; separately confirm cancel/deadline still sends neither cleanup request after cancellation and aborts.
- Preserve existing tests for multi-chunk logical counting, OPN single admission/pacing, HEL, blocked-service behavior, shared per-host/protocol budgets, and accurate service-level coverage.

The ordinary cutoff and cleanup sends must be tested together at the shared-stage seam so the host/protocol budget is not accidentally exceeded when Modbus reservations are included. Keep Modbus transport behavior out of scope unless a test demonstrates a concrete regression.

## Human decision required

Approve or revise the proposed two-slot lifecycle reserve and the conservative one-shot semantics above before implementation resumes. Task 4 is `BLOCKED_STRUCTURAL`; this document is a proposal, not a code change or approval.
