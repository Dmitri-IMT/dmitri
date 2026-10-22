# OPC UA: package gates and real-device validation

## What the automated gates establish

The release workflow is configured to build on a native Linux ARM64 runner with Python 3.12. `build-deb.sh` exports the committed `uv.lock` runtime with hashes, downloads only binary wheels for the target, and places them in the agent package. The package post-install creates the venv and installs from that wheelhouse with `UV_OFFLINE=1`, `--offline`, and `--no-index`; it then checks the installed CLI entry point. The ARM64 CI job is configured to import `asyncua`, `cryptography`, and Dmitri's OPC UA modules, run `dmitri health --json`, and perform endpoint inventory plus bounded mapping against a server bound to `127.0.0.1`.

The general hardware-agent test gate continues to run on Python 3.11. The ARM64 package gate runs Python 3.12, matching the Raspberry Pi package runtime. The lock supports Python 3.11 and 3.12; the package target is specifically Python 3.12 on Linux ARM64.

### Results actually observed for this branch

- Linux x86_64 with Python 3.12: imports, `dmitri health --json`, and the loopback inventory/mapping smoke passed. The Python 3.12 test suite also passed its focused OPC UA and integration gates.
- Raspberry Pi native ARM64, Python 3.12.15: the current `.deb` was extracted into a temporary directory, and its 33 hash-verified wheels plus agent wheel were installed offline into a separate `/tmp` virtual environment. `asyncua`/`cryptography`/OPC UA imports and `dmitri health --json` passed (`ok: true`). The loopback inventory/mapping smoke passed, confirming inventory and bounded mapping including `LabValue`. The final workspace `client.py` was copied into that temporary venv for the rerun; the system package was not installed or changed. The existing `dmitri-agent` service remained active and was not restarted.
- Linux ARM64 under QEMU: the `.deb` and updater installed successfully from 33 hash-verified wheels with networking disabled; imports and health (`ok: true`) passed. The loopback inventory/mapping smoke did not complete under emulation. The initial attempt timed out before sending a request; after increasing only the harness's worker-startup allowance, a second attempt remained CPU-bound and was stopped. Native Pi evidence above supplies the ARM64 smoke result; QEMU smoke remains inconclusive.
- Python 3.11: the hardware-agent suite passed with 1,698 passed and 27 skipped. The QEMU package test and the Python 3.11 test are separate gates.
- The native ARM64 CI job contains the package and smoke steps, but it has not run against this unpushed worktree. The Pi check used a temporary offline venv built from the extracted package and current client module; it did not install or validate the system package or service upgrade path.

These results show offline wheel installation, CLI/import operation, and loopback inventory/mapping on native ARM64 in an isolated temporary venv. They do not validate installation over the Pi's existing system package, service restart/upgrade behavior, or a commercial PLC. QEMU evidence is emulated behavior, not native architecture validation.

## What they do not establish

The loopback server is a software fixture, not a PLC, OPC UA gateway, or production system. Passing it does not establish compatibility with a vendor's device, firmware, endpoint configuration, certificate deployment, network conditions, performance under plant load, or operational safety. It does not certify the protocol implementation or prove that every OPC UA server behaves alike. No commercial PLC interoperability claim should be made from these tests.

OPC UA inventory records endpoint announcements. Mapping is limited to an explicitly advertised endpoint that permits `SecurityPolicy None`, `MessageSecurityMode None`, and Anonymous access. It is read-only and bounded; the fixture cannot verify that a vendor device labels or implements its services correctly.

## Checklist before a real-device trial

Run this only after the asset owner has authorized the exact device and test window.

1. Record written authorization, responsible operator, device owner, maintenance contact, approved source host, destination IP/port, and test window. Confirm the trial will not overlap a safety-critical or production operation.
2. Record device vendor/model, firmware, OPC UA server version, network path, endpoint URL as configured on the device, security policy/mode, and whether Anonymous access is intentionally enabled. Keep credentials and private keys out of scan evidence and logs.
3. Agree on a stop condition and a way for the operator to halt the test. Confirm the scan's connection pacing, timeout, and shared NSPi request budget with the owner before starting.
4. Start with one explicitly approved device and the NSPi inventory stage. Confirm observed IP/port, confirmed-vs-suspected status, endpoint count, and reported request counters with packet capture or device-side audit logs where available.
5. Only proceed to read-only mapping if the owner approved it and the endpoint meets the implementation's explicit Anonymous/None policy. Verify on the wire that requests are limited to the allowed endpoint/session/Browse/Read and required close services; confirm no Write, Call, history, registration, or subscription services are sent.
6. Have the operator monitor device health and process impact throughout. Stop immediately on unexpected load, alarms, connection instability, or any change in process behavior. Do not retry automatically against a device that has denied or failed the trial.
7. Compare scanner counters and sanitized observations with the packet/device evidence. Confirm process values, credentials, certificate contents, and opaque identifiers are not retained in the report. Record partial/denied results as such; do not interpret them as proof of absence or a vulnerability.
8. Obtain owner sign-off on the result, document exact model/firmware/configuration and limitations, and decide separately whether that device family needs more controlled interoperability testing.

Product notes may say “OPC UA loopback inventory and bounded mapping validated on native Raspberry Pi ARM64 in an isolated offline virtual environment.” They must still state that the installed system package/service upgrade path and commercial PLC interoperability have not been validated; do not claim “validated with PLCs” or “production compatible.”
