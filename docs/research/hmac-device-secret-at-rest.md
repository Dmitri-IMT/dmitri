# Research: storing a per-device HMAC-SHA256 shared secret at rest in Postgres

> **⚠️ Superseded (2026-07-24).** This note backed ADR-015 (encrypt the device secret at rest),
> which existed only because HMAC is symmetric and forces the backend to hold a recoverable
> secret. ADR-005 was amended to **Ed25519 asymmetric signing** — the backend stores only a
> **public** key, so there is no secret to store at rest and **ADR-015 is retired**. This note is
> kept for history; the current decision and its rationale are in
> [`device-auth-hmac-vs-asymmetric.md`](device-auth-hmac-vs-asymmetric.md).

> **Scope note.** This concerns the ADR-005 agent auth path: each Raspberry Pi
> agent shares an HMAC-SHA256 secret with the backend, which recomputes
> `HMAC-SHA256(secret, canonical_string)` on every `POST /api/v1/scans` and on
> every WSS upgrade to `…/agents/{agent_id}/commands` (ADR-011). Because
> verification is a recomputation, the secret is **symmetric and must be
> recoverable server-side** — a one-way password hash (bcrypt/argon2/scrypt) is
> cryptographically impossible here. The question is narrowly: given the secret
> MUST be recoverable, how do we store the per-device secret in the `agents`
> table as safely as possible against a database read. No application code or
> schema change is proposed; this is a decision note.

**Question.** What is the most secure practical way to hold a recoverable
per-device HMAC secret at rest in Postgres for a FastAPI + SQLModel/psycopg3
backend on Supabase Postgres, deployed on Railway, for a September MVP running a
single Railway replica — and what is the ideal end-state to grow into?

---

## TL;DR verdict

**Store the secret encrypted, with the encryption key held outside the
database.** Concretely, in order of preference for this deployment:

1. **Pragmatic MVP (recommended now): application-layer AEAD (AES-256-GCM)** on
   the secret before it is written to `agents`, with the 256-bit key supplied
   as a **Railway environment variable** (ideally a *sealed* variable) and read
   into the FastAPI process at startup — never stored in Postgres. Store
   ciphertext + per-row nonce + a key-version tag. This is the OWASP
   "separation of keys and data" property (§1): a DB dump, backup theft, SQL
   injection, or a read of the `agents` table yields only ciphertext, because
   the key lives in the app process's environment on a different system.
2. **Supabase-native alternative: Supabase Vault.** Vault stores secrets as
   libsodium AEAD ciphertext and keeps the root key *in Supabase's backend, not
   in the database* — so dumps and backups contain only ciphertext (§5). This
   gets you the same key-data separation with zero key-handling code, at the
   cost of decrypting through a SQL view (`vault.decrypted_secrets`) rather than
   in Python.
3. **End-state (post-MVP): envelope encryption with a managed KMS/Vault.** A
   Key-Encryption-Key in AWS KMS / HashiCorp Vault wraps a Data-Encryption-Key;
   only the wrapped DEK sits near the data (OWASP KEK/DEK, §1; ASVS 6.4.1 /
   6.4.2, §2). This is what ASVS and OWASP actually ask for and what a
   multi-replica production deployment should converge on.

**Explicitly rejected:**

- **Plaintext in the table** — acceptable *only* as a deliberate, documented
  stopgap and only if the key-separation options above are genuinely
  unavailable. It fails every DB-read threat (§4). Not recommended given
  Railway env vars make option 1 nearly free.
- **A one-way hash of the secret (bcrypt/argon2)** — impossible: HMAC needs the
  raw secret to recompute the MAC (RFC 2104, §3). Do not treat this like a
  password column.
- **`HMAC(pepper, secret)` "keyed-hash" storage** — does **not** work here. See
  §6: it is still one-way, so the server could never recompute the device MAC.

**Rotation** (ADR-005 requires issuing a new secret and invalidating the old):
keep the storage envelope rotation-friendly — a `key_version` column and the
ability to hold two active device secrets briefly (old + new) during a Pi's
cutover. None of the at-rest options obstructs this; envelope encryption (KMS)
adds cheap *key* rotation on top of *secret* rotation (§7).

---

## Findings

### 1. What authoritative sources say to do with a recoverable secret

- **Separate the key from the data.** OWASP Cryptographic Storage Cheat Sheet:
  *"Where possible, encryption keys should be stored in a separate location from
  encrypted data."* If the data is in a database, keep the key in the
  filesystem/env/KMS instead, so that compromise of one location does not yield
  both. This single principle is the entire basis of the recommendation:
  encrypting the secret only helps if the key is **not** in the same
  compromised store. —
  https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- **Use an authenticated cipher.** Same source: *"AES with a key that's at
  least 128 bits (ideally 256 bits) and a secure mode should be used"*, and
  authenticated modes like **GCM** provide *"guarantees of the integrity and
  authenticity of the data, as well as confidentiality."* → AES-256-GCM for the
  application-layer option. —
  https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- **Envelope encryption (KEK/DEK) is the recommended key architecture.** OWASP:
  a **Data Encryption Key (DEK)** encrypts the data; a **Key Encryption Key
  (KEK)** encrypts the DEK; *"The KEK must be stored separately from the DEK."*
  The encrypted DEK may travel with the data, but is useless without the
  separately-held KEK. This is the end-state (option 3). —
  https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- **Prefer a managed secrets store / KMS.** OWASP names *"Amazon KMS or Azure
  Key Vault"* and *"HashiCorp Vault"* as the recommended key-storage
  mechanisms; the Secrets Management Cheat Sheet adds *"Use a designated secret
  management solution in any environment"* and lists the protections a manager
  provides: encryption at rest by default (*"The secret is then safeguarded
  against compromise while at rest"*), fine-grained least-privilege access,
  audit logging, and fast revocation/rotation. —
  https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
- **Environment variables are a compromise, not the ideal.** The Secrets
  Management Cheat Sheet cautions env vars are *"generally accessible to all
  processes and may be included in logs or system dumps … therefore not
  recommended unless the other methods are not possible."* For the **MVP the key
  in a Railway env var is exactly that "other methods not possible" fallback**
  — but note it is graded below a real vault, and it is what justifies moving to
  option 3 later. (The Cryptographic Storage sheet's blanket "avoid environment
  variables" warning is aimed at leaks like `phpinfo()`; the mitigation on
  Railway is a *sealed* variable, §8.) —
  https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

### 2. ASVS: what the standard actually requires

- **V6.4.1** — *"Verify that a secrets management solution such as a key vault
  is used to securely create, store, control access to and destroy secrets."*
- **V6.4.2** — *"Verify that key material is not exposed to the application but
  instead uses an isolated security module like a vault for cryptographic
  operations."*
- **V6.2.4** — *"Verify that … key lengths, rounds, ciphers or modes, can be
  reconfigured, upgraded, or swapped at any time, to protect against
  cryptographic breaks."* → argues for a `key_version` tag on stored
  ciphertext.
- **V6.2.6** — *"Verify that nonces, initialization vectors, and other single
  use numbers must not be used more than once with a given encryption key."* →
  for AES-GCM, generate a fresh random nonce per encryption and store it
  alongside the ciphertext.
- Source:
  https://raw.githubusercontent.com/OWASP/ASVS/v4.0.3/4.0/en/0x14-V6-Cryptography.md
- **Honest gap:** the MVP option 1 (key in an env var, crypto done in the app)
  satisfies 6.4.1 only weakly and does **not** satisfy 6.4.2 (key material *is*
  exposed to the app process). Supabase Vault (§5) or a KMS (§1) is what closes
  6.4.2. Record this as accepted MVP debt.

### 3. RFC 2104: the secret is symmetric and must be kept, not hashed

- HMAC verification is recomputation with the shared key `K`; the server cannot
  substitute a one-way digest of `K`. RFC 2104 on `K`: *"Keys need to be chosen
  at random (or using a cryptographically strong pseudo-random generator seeded
  with a random seed)"*, *"The minimal recommended length for K is L bytes (as
  the hash output length)"* — i.e. **≥ 32 bytes for HMAC-SHA256** — and keys
  should be *"periodically refreshed … limits the damage of an exposed key."*
  RFC 2104 also states *"good secrecy protection of keys [is] essential"* for
  the integrity mechanism. —
  https://datatracker.ietf.org/doc/html/rfc2104
- Takeaways for storage: (a) the column holds a high-entropy 32-byte random
  value, not a user string; (b) "periodically refreshed" is the RFC-level
  mandate behind ADR-005's per-device rotation (§7); (c) "good secrecy
  protection of keys" is the requirement this whole note is trying to satisfy at
  rest.

### 4. NIST SP 800-57 Part 1: protection duties and cryptoperiod

- Part 1 (Rev. 5) assigns protection requirements per key type: **secret keys
  must be protected against unauthorized disclosure, and all keys against
  unauthorized substitution and modification.** For an HMAC key this means
  both confidentiality (encrypt at rest / keep off-database) *and* integrity —
  AES-**GCM**'s authentication tag provides the latter for the stored blob. —
  https://csrc.nist.gov/News/2020/NIST-Publishes-SP-800-57-Pt-1-Revision-5
- **Cryptoperiod.** 800-57 recommends bounded lifetimes for symmetric keys
  (commonly cited as ~1–2 years for symmetric encryption keys); the longer a
  key lives, the more exposure a compromise carries. This applies both to the
  **device HMAC secret** (bound its lifetime; rotate per ADR-005) and to the
  **encryption key** protecting it (rotate on a schedule; a `key_version`
  column makes this non-breaking). —
  https://csrc.nist.gov/projects/key-management/key-management-guidelines

### 5. Supabase Vault — the Supabase-native key/data separation

- **What it is:** *"Vault is a Postgres extension and accompanying Supabase UI
  that makes it safe and easy to store encrypted secrets."* It stores secrets in
  *"an authenticated encrypted form"* (AEAD, historically libsodium). —
  https://supabase.com/docs/guides/database/vault
- **The decisive property — key is not in the database:** *"The encryption key
  is never stored in the database alongside the encrypted data"*; Supabase
  *"creates and manages a unique encryption key for each project in our secured
  backend systems."* Therefore *"even if an attacker can capture a dump of your
  entire database, they will see only encrypted data, never the encryption key
  itself."* This is exactly OWASP's key-data separation (§1), delivered
  natively. —
  https://supabase.com/docs/guides/database/vault
- **Decryption path:** an auto-created view `vault.decrypted_secrets` *"will
  decrypt secret data on the fly"* at query time, so *"the secret remains
  encrypted on disk, and in any backup dumps or replication streams."* Access to
  that view must be locked down with SQL privileges — the view is the new
  crown-jewel surface (§4 threat model). —
  https://supabase.com/docs/guides/database/vault
- **Stability note:** `pgsodium`/Transparent Column Encryption is being
  deprecated and Supabase *"does not recommend any new usage of pgsodium"*, but
  **Vault's public API is stable** — its internals are being reimplemented
  without pgsodium (PR merged Mar 2025) while the interface is unchanged. So
  building on Vault (not raw pgsodium/TCE) is the safe Supabase bet. —
  https://supabase.com/docs/guides/database/extensions/pgsodium,
  https://github.com/orgs/supabase/discussions/27109
- **Tradeoff vs. app-layer:** Vault decrypts inside Postgres, so the FastAPI app
  reads plaintext over the (TLS) DB connection and never handles the key — this
  is *stronger* on ASVS 6.4.2 than option 1. The cost is coupling secret access
  to a Postgres view + privilege model, and a per-device secret is fetched via
  the view on each verification (or cached in-process).

### 6. Why `pgcrypto` column encryption is a weaker fit than either above

- `pgcrypto` runs **inside the database server**, and the key is passed as a
  function argument (`pgp_sym_encrypt(data, psw)` / `encrypt(data, key, type)`).
  The docs' Security Limitations are explicit: *"All pgcrypto functions run
  inside the database server. That means that all the data and passwords move
  between pgcrypto and client applications in clear text."* The key therefore
  travels in the SQL statement text and can surface in `pg_stat_activity` and
  statement logs. —
  https://www.postgresql.org/docs/current/pgcrypto.html
- Raw `encrypt()/decrypt()` are further discouraged by the docs: *"usage of raw
  encryption functions is discouraged"* (they use the user key directly as
  cipher key, provide no integrity check, and force manual IV management). If
  pgcrypto is ever used, it must be **PGP symmetric** (`pgp_sym_*`, which is
  AEAD-ish and handles IV), never `encrypt()`.  —
  https://www.postgresql.org/docs/current/pgcrypto.html
- **Net:** pgcrypto's core problem for *this* threat model is that the key is
  supplied to the DB engine, so it does not cleanly satisfy §1's key-data
  separation and risks logging the key. Supabase Vault (§5) is strictly better
  on Supabase because it keeps the key out of the database entirely; app-layer
  AES-GCM (option 1) is better still at keeping the key off the DB host. Prefer
  those over pgcrypto.

### 7. The `HMAC(pepper, secret)` idea does not apply here — and why

- The pattern "store `HMAC(pepper, value)` with the pepper in a KMS" is a
  *password/lookup* technique: it lets you verify a **presented** value without
  storing it recoverably. It works for passwords because the client sends the
  password and you re-derive the keyed hash to compare.
- **It cannot work for the device HMAC secret**, because in this protocol the
  device never sends its secret over the wire — it sends
  `X-Signature = HMAC-SHA256(secret, canonical)`. To verify, the server must
  itself compute `HMAC-SHA256(secret, canonical)`, which requires the **raw
  secret**. If the server only held `HMAC(pepper, secret)`, it could never
  reconstruct `secret` to recompute the request MAC — verification is
  impossible. So keyed-hash-at-rest is a category error here; the secret must be
  stored **reversibly** (encrypted), not one-way. The correct use of a KMS in
  this context is to hold the *encryption key* (KEK/DEK, §1), not to keyed-hash
  the secret.

### 8. Rotation support per option (ADR-005: issue new secret, invalidate old)

- **Secret rotation** (the device's HMAC key) is orthogonal to the at-rest
  method and works the same everywhere: generate a new 32-byte random secret,
  encrypt/store it, provision it to the Pi out-of-band (ADR-005 §Provisionamento),
  keep the old one valid for a short overlap window, then delete the old. Model
  as `key_version` + optionally a second active-secret slot per device so a Pi
  can cut over without a failed-auth gap. WSS upgrades follow the same rules
  (ADR-011).
- **Encryption-key rotation** (the KEK/DEK or env key protecting the secrets):
  - *App-layer AES-GCM (opt 1):* store a `key_version` tag per row; add the new
    key to the env, re-encrypt rows lazily or in a migration, then retire the
    old key. NIST cryptoperiod §4.
  - *Supabase Vault (opt 2):* Supabase manages the project root key; you get
    rotation without touching ciphertext.
  - *KMS envelope (opt 3):* rotate the KEK in KMS with the DEK unchanged, or
    re-wrap DEKs — the cheapest rotation story, and the reason it is the
    end-state.

### 9. Ecosystem fit: FastAPI + psycopg3 + Supabase + Railway, single replica

- **Railway** injects variables into the deployment environment
  (*"made available to your application as environment variables"*) and offers
  **sealed variables** — *"its value is provided to builds and deployments but
  is never visible in the UI nor can it be retrieved via the API"* (and cannot
  be un-sealed or CLI-exported). Railway documents **no native KMS**. So the
  practical Railway primitive is a **sealed env var holding the AES key** — the
  key sits in the app process, separate from Supabase Postgres. This is the
  MVP's key-data separation boundary. —
  https://docs.railway.com/guides/variables
- **Supabase** provides the native alternative (Vault, §5) whose key lives in
  Supabase's backend, off the database. For a Supabase-hosted DB this is the
  most idiomatic way to get 6.4.2-grade separation without standing up AWS KMS.
- **Single-replica reality:** with one Railway replica and no HSM/KMS in the
  stack yet, **env-var-based keys are the practical option** for the September
  MVP (OWASP's "unless other methods are not possible", §1). Because Supabase
  Vault is already available on the same database, prefer Vault if the extra
  view-based access path is acceptable; otherwise app-layer AES-256-GCM with a
  sealed Railway key. Either keeps a DB read from yielding usable secrets.
  Defer the AWS KMS / HashiCorp Vault envelope design to when the deployment
  goes multi-replica or needs audit-grade key access.

---

## Threat-model comparison

Legend: **P** = protects, **✗** = does not protect, **~** = partial/conditional.

| Storage option (key location) | SQLi / single-table read | Full DB dump | Backup / replica theft | App-server compromise | Malicious/curious DBA (insider) | ASVS 6.4.2 (key not in app) |
|---|---|---|---|---|---|---|
| **Plaintext in `agents`** (RLS + least-priv role) | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| **App-layer AES-256-GCM**, key in Railway sealed env (opt 1) | **P** | **P** | **P** | ✗ (key in process memory/env) | **P** (DBA has no key) | ✗ (app holds key) |
| **Supabase Vault**, key in Supabase backend (opt 2) | **P** (view locked down) | **P** | **P** (dump = ciphertext) | ~ (app can call the view; compromised app can decrypt) | ~ (DBA with view privilege can read; lock down) | **P** (app never holds key) |
| **pgcrypto PGP-sym**, key passed in SQL (opt, §6) | ~ (ciphertext at rest) | ~ | ~ | ✗ | ✗ (key transits DB, may hit logs/`pg_stat_activity`) | ✗ |
| **KMS/Vault envelope** (KEK in KMS, DEK wrapped by data) (opt 3) | **P** | **P** | **P** | ~ (app can call KMS decrypt; add per-call audit + rate limits) | **P** | **P** |
| **One-way hash of secret** (bcrypt/argon2) | — | — | — | — | — | **N/A: breaks HMAC verification (§3, §7)** |

Reading the table:

- The plaintext row fails every database-read column — the exact scenarios ADR
  cares about. Its only "defense" (RLS + least-priv DB role) does nothing once
  the attacker *is* that role or has a dump.
- App-layer AES-GCM and Vault both neutralize the pure database-read threats
  (SQLi, dump, backup) because the key is elsewhere (§1). Their residual
  exposure is **app-server compromise** — which no at-rest scheme fully solves,
  and which is the argument for KMS with per-decrypt audit at end-state.
- pgcrypto's weakness is precisely that the key is handed to the database, so it
  is only marginally better than plaintext against the insider/log threat.

---

## Decision inputs (concrete)

| Input | Value | Source |
|---|---|---|
| Can the secret be a one-way hash? | **No** — HMAC verify recomputes `HMAC(secret, msg)`; needs raw secret | RFC 2104; ADR-005 §1 |
| Secret entropy / length | ≥ **32 bytes** random (HMAC-SHA256 `L`), CSPRNG-generated | RFC 2104 |
| Core principle | Encrypt the secret; **keep the key in a separate location from the data** | OWASP Cryptographic Storage (Separation of Keys and Data) |
| Cipher for app-layer | **AES-256-GCM** (authenticated: confidentiality + integrity), fresh nonce/row | OWASP Crypto Storage; ASVS 6.2.6; NIST 800-57 (integrity) |
| Standard's ask | Secrets in a **key vault**; **key material not exposed to the app** | ASVS 6.4.1 / 6.4.2 |
| Key architecture (end-state) | **KEK/DEK envelope**, KEK in KMS, KEK stored separately from DEK | OWASP Cryptographic Storage |
| Supabase-native option | **Vault** — AEAD ciphertext, **root key in Supabase backend, never in DB dump**; decrypt via `vault.decrypted_secrets` view | supabase.com/docs/guides/database/vault |
| pgcrypto caveat | Key passed to DB in clear text → risk in logs/`pg_stat_activity`; raw `encrypt()` "discouraged" | postgresql.org/docs/current/pgcrypto.html |
| Railway primitive | **Sealed env var** for the AES key (no native KMS); injected into deployment env | docs.railway.com/guides/variables |
| Env-var caveat | "not recommended unless other methods are not possible" — accept as MVP debt | OWASP Secrets Management |
| Cryptoperiod | Bound device-secret & encryption-key lifetimes (~1–2 yr symmetric); rotate | NIST SP 800-57 Pt 1 Rev 5 |
| Rotation shape | New secret + short overlap window + `key_version`; invalidate old | ADR-005 (Provisionamento e rotacao); ADR-011 |
| `HMAC(pepper, secret)` at rest | **Does not apply** — still one-way, can't recompute device MAC | derived from RFC 2104 protocol shape (§7) |

---

## Recommendation, restated for the September MVP

Store each device secret as **AES-256-GCM ciphertext** (ciphertext + per-row
nonce + `key_version`) in the `agents` table, with the 256-bit key in a
**sealed Railway environment variable** read at process startup — or, if the
team prefers a Supabase-native path with the key fully off the app, use
**Supabase Vault** (`vault.decrypted_secrets`, view privileges locked down).
Both satisfy the load-bearing property — a read of the database (SQLi, dump,
stolen backup) yields only ciphertext because the key is not in Postgres.
Rotation stays a `key_version` + short-overlap operation and is unaffected by
the choice. Grow toward a **KMS/HashiCorp-Vault envelope (KEK/DEK)** when the
deployment goes multi-replica or needs audited key access — that is the ASVS
6.4.1/6.4.2 end-state, deferred as documented MVP debt.
