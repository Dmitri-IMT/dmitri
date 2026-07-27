# ADR-015: Agent HMAC secret storage at rest

> **Status: SUPERSEDED / REVERSED (2026-07-24).** This ADR exists only because HMAC is symmetric,
> which forces the backend to hold a **recoverable** per-device secret. [`ADR-005`](ADR-005-security-model.md)
> was amended on 2026-07-24 to use **Ed25519 asymmetric signing** for the agent: the backend now
> stores only each device's **public key** (plaintext — a public key is not a secret), and holds
> **no recoverable secret at all**. There is therefore nothing to encrypt at rest, and this ADR no
> longer applies. The `agents` table drops `secret_ciphertext` / `secret_nonce` /
> `secret_key_version` in favour of a single plaintext `public_key` column; the sealed Railway AES
> key, the `secret_key_version` rotation tag, the ASVS-6.4.2 MVP-debt note, and the Supabase-Vault /
> KMS end-state below all fall away. Decision record and rationale:
> [`docs/research/device-auth-hmac-vs-asymmetric.md`](../research/device-auth-hmac-vs-asymmetric.md).
> **The text below is retained for history only and is no longer in force.**

---

**Status (original):** accepted — amends [`ADR-005`](ADR-005-security-model.md) (which specified per-device
HMAC-SHA256 but never how the backend stores the secret).

## Context

Every `POST /api/v1/scans` and every WSS upgrade to `…/agents/{agent_id}/commands` is authenticated by
the backend **recomputing** `HMAC-SHA256(secret, canonical_string)` and comparing it to `X-Signature`
([`ADR-005`](ADR-005-security-model.md), [`ADR-011`](ADR-011-pi-command-channel.md)). Recomputation
means the per-device secret is **symmetric and must be recoverable server-side** — a one-way password
hash (bcrypt/argon2) is cryptographically impossible here, so the field name `secret_hash` from the
DMI-59 brief is wrong and is not used.

The question is therefore how to hold a *recoverable* secret as safely as possible against a database
read (SQL injection, full dump, backup/replica theft). The load-bearing principle (OWASP Cryptographic
Storage Cheat Sheet; ASVS 6.4.1/6.4.2) is **separate the key from the data**: encrypting the secret only
helps if the encryption key is not in the same store an attacker reads. Full research and threat model:
[`docs/research/hmac-device-secret-at-rest.md`](../research/hmac-device-secret-at-rest.md).

## Decision

**Store each agent secret as application-layer AES-256-GCM ciphertext**, with the 256-bit key held in a
**sealed Railway environment variable** read into the FastAPI process at startup — never in Postgres.

The `agents` table stores three columns (no plaintext, no `secret_hash`):

- `secret_ciphertext` — AES-256-GCM ciphertext of the 32-byte random device secret
- `secret_nonce` — per-row random GCM nonce
- `secret_key_version` — integer tag identifying the encryption key, for non-breaking key rotation

A database read (SQLi, dump, stolen backup) yields only ciphertext because the key lives in the app
environment, on a different system from Supabase Postgres.

**Scope:** DMI-59 defines these columns only. The encrypt/decrypt logic lands with the HMAC verification
path (DMI-62 WS upgrade, DMI-63 ingest). Secret **rotation** (issue new secret, short overlap, invalidate
old — ADR-005) is orthogonal to storage and unaffected; **encryption-key** rotation uses `secret_key_version`.

## Considered and rejected

- **Plaintext in a fenced table** (RLS + `dmitri_runtime` grants) — fails every database-read threat once
  the attacker holds a dump or is that role. The fence is defense-in-depth, not the primary control.
- **One-way hash** — breaks HMAC verification (see Context).
- **pgcrypto** — the key is passed into the DB engine in SQL and can surface in logs / `pg_stat_activity`;
  it does not achieve key-data separation.

## Production end-state (deferred as documented MVP debt)

App-layer AES-GCM keeps the key in the application process, so it does **not** satisfy ASVS 6.4.2 ("key
material not exposed to the application"). The better production design is:

- **Supabase Vault** — AEAD ciphertext with the root key held in Supabase's backend, never in the DB; the
  app never handles the key (satisfies 6.4.2). The `agents` table would instead hold a `secret_id`
  reference and decrypt via the locked-down `vault.decrypted_secrets` view. This is the recommended
  production version and should replace (A) when the Supabase-view access path is acceptable.
- **KMS/HashiCorp-Vault envelope encryption (KEK/DEK)** — the full ASVS 6.4.1/6.4.2 target for a
  multi-replica or audit-grade deployment.

Migrating from (A) to Vault is a data migration (decrypt with the env key, re-store via Vault) plus
swapping three columns for `secret_id` — the reason this ADR records the direction now.
