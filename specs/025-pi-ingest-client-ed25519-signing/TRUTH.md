# TRUTH — Pi ingest client and Ed25519 signing

## Narrative

The scanning device can already produce a normalized scan result and retain it locally, while the
backend can already accept authenticated scan submissions. The missing link is a reusable device
client that submits a result with proof of the device's identity. This gives the future Pi daemon a
safe upload path without coupling transport behavior to the scan pipeline or sacrificing the local
result when the network or backend is unavailable.

## Business rules

- Every submission is authenticated with the device's Ed25519 private key; no shared secret is
  transmitted or stored by the backend.
- The signed proof covers the request method, destination path, device identity, timestamp, nonce,
  and exact submitted body.
- Each request attempt uses a fresh timestamp, nonce, and signature, including retries of the same
  scan result.
- Connection failures and server failures may be retried only a bounded number of times.
- Authentication, authorization, and payload-validation failures are surfaced immediately and are
  not retried.
- A submission signed while the device clock sits outside the service's freshness window is one of
  those authentication failures: it is surfaced immediately and not retried. Keeping the device
  clock synchronised is an operating requirement, not a client responsibility.
- A submission is successful only when the backend acknowledges that it accepted the scan.
- The local scan artifact is never deleted, replaced, or made unreadable by submission success,
  failure, or retry.
- A submission the service rejects because its scan is already closed is final. The service discards
  that result deliberately, resubmitting it will never succeed, and the correct recovery is to start
  a new scan rather than to requeue the old one. Retaining the local artifact is a guarantee that
  the client destroys nothing, not a promise that every retained result can eventually be uploaded.
- When a backend-assigned scan identity is supplied, it is used for the submitted result without
  mutating the caller's in-memory result or local artifact. Otherwise, the result's existing scan
  identity is submitted.
- Private-key material and request signatures must not appear in user-facing errors or logs.

## User stories

1. As a device operator, I want completed scan results submitted securely, so that they become
   available in the central system without manual transfer.
2. As a device operator, I want the local scan artifact retained when submission fails, so that a
   transient outage never causes silent data loss.
3. As the future Pi daemon, I want to supply the scan identity assigned to a remote command, so that
   the uploaded result is associated with the correct backend scan.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Accepted submission | A registered device, its matching private key, a normalized result, and a reachable ingest service | The device submits the result | The service acknowledges acceptance, persists the result, and the local artifact still exists unchanged |
| Valid signed envelope | A normalized result ready for submission | The request is received by the service | The service can validate the device identity, freshness, uniqueness, body digest, and Ed25519 signature against the exact submitted bytes |
| Original scan identity | No backend-assigned scan identity is supplied | The result is submitted | The submitted result uses its existing scan identity |
| Backend-assigned scan identity | A backend-assigned scan identity is supplied | The result is submitted | The submitted result uses the assigned identity while the caller's result and local artifact retain their original contents |
| Wrong private key | The device uses a private key that does not match its registered public key | The result is submitted | The caller receives a clear unauthorized outcome, no automatic retry occurs, and the local artifact remains available |
| Unknown device | The device identity is not registered | The result is submitted | The caller receives a clear unauthorized outcome, no automatic retry occurs, and the local artifact remains available |
| Revoked device | The device identity is registered but revoked | The result is submitted | The caller receives a clear forbidden outcome, no automatic retry occurs, and the local artifact remains available |
| Invalid result | The service rejects the submitted result as invalid | The result is submitted | The caller receives a clear validation failure, no automatic retry occurs, and the local artifact remains available |
| Closed scan | The service has already given up on the scan this result belongs to | The result is submitted | The caller receives a clear terminal rejection, no automatic retry occurs, resubmission is not attempted, and the local artifact remains available |
| Transient recovery | A connection failure or server failure occurs before a later successful attempt | The device submits the result | The client retries within its fixed limit, signs every attempt with fresh proof, and reports success after acceptance |
| Unsynchronised device clock | The device clock is far enough from real time that the proof is not fresh | The result is submitted | The caller receives the same unauthorized outcome as any other rejected proof, no automatic retry occurs, and the local artifact remains available |
| Retry exhaustion | Connection or server failures continue through the retry limit | The device submits the result | The caller receives a clear failure after the bounded attempts and the local artifact remains available |
| Safe resubmission | A result was already accepted but its original acknowledgement was lost | The device submits it again with fresh proof | The service acknowledges the result without duplicating its stored scan data |
| Secret-safe diagnostics | A configuration, signing, or submission error occurs | The failure is surfaced | The diagnostic identifies the failure category without exposing private-key material or signatures |

## Out of scope (v1)

- WebSocket command handling, command status messages, daemon lifecycle, reconnect behavior, and
  service-manager configuration.
- Automatically uploading results from the TUI or the interactive headless command.
- Device provisioning, key generation, public-key registration, and key rotation.
- Changes to scan stages, scan modes, normalization behavior, or the normalized result format.
- Backend ingest behavior, persistence changes, and new API endpoints.
- A persistent offline upload queue or background retry scheduler.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Cross-layer contract: `INTEGRATION.md`
