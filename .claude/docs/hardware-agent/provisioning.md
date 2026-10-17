---
type: Module
title: transport/provision — agent registration and local keys
description: Registers a Pi agent over HTTPS and atomically stores its device identity and private key locally.
resource: hardware-agent/src/agent/transport/provision.py
tags: [hardware-agent, transport, provisioning, ed25519, security]
timestamp: 2026-10-17T00:00:00Z
---

# transport/provision — agent registration and local keys

## Purpose

`agent.transport.provision` registers a hardware agent with the backend and writes the local
connection configuration. The private Ed25519 key is generated or reused on the Pi; only its public
key is sent to the backend. Registration uses HTTPS and an admin login, then stores the backend URL,
agent ID and private key in the local environment file.

## Key classes / functions

| Symbol | What it does | Ref |
|--------|--------------|-----|
| `load_or_create_key()` | Reuses the dedicated key file or a configured key, otherwise creates and saves a new key without replacing a concurrent creator's file. | `provision.py:78` |
| `_write_private_file()` | Writes through a same-directory temporary file, flushes it, and publishes it atomically. | `provision.py:44` |
| `_sync_directory()` | Syncs the parent directory on POSIX; skips directory fsync on Windows, where opening a directory this way is unsupported. | `provision.py:62` |
| `parse_https_url()` | Requires HTTPS before accepting a backend URL. | `provision.py:107` |
| `register()` | Logs in as an organization admin and registers the agent public key. | `provision.py:120` |
| `provision()` / `main()` | Collects operator inputs, registers, writes local config, and reports expected setup failures without exposing key contents. | `provision.py:147`, `:176` |

## How it connects

- Invoked by `hardware-agent/scripts/provision-pi.sh` as `dmitri provision`.
- Stores configuration consumed by the signed [ingest client](/hardware-agent/transport.md) and
  [command channel](/hardware-agent/command-channel.md).
- Pi setup also provisions external service-targeted tools before reporting the appliance ready; see
  [targeted checks](./targeted.md).

## Notes / gotchas

- Registration joins the organization of the admin account supplied during provisioning.
- The private key stays on the Pi; rerunning after a registration failure reuses the existing key.
- Directory fsync is used on POSIX after atomic file publication. Windows skips this directory sync,
  while still flushing the written file before publishing it.
