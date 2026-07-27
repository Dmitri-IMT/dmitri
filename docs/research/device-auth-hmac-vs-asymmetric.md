# Research: device→backend auth — symmetric HMAC vs. asymmetric signing (Ed25519 / mTLS)

> **Scope.** The ADR-005 agent auth path: each Raspberry Pi signs every
> `POST /api/v1/scans` and every WSS upgrade to `…/agents/{agent_id}/commands`
> (ADR-011). ADR-005 chose **per-device HMAC-SHA256**; because HMAC verification
> is a *recomputation*, the per-device secret is symmetric and must be recoverable
> server-side, which is the entire reason ADR-015 exists (store the secret as
> AES-256-GCM ciphertext with the key in a Railway env var). This note asks whether
> that whole problem is self-inflicted: would switching device→backend auth to
> **asymmetric** request signing (Ed25519) or **mTLS** eliminate the need to hold
> any recoverable secret server-side. No code exists yet — device auth is
> greenfield (AUTH.md "Built today → Everything: Not built"). Primary sources only
> (RFCs, pyca/cryptography, PyNaCl, AWS/Azure first-party IoT docs, OWASP ASVS,
> Railway docs). Fetched 2026-07-24.

---

## TL;DR verdict

**Recommendation: adopt asymmetric per-device request signing (Ed25519) now, and
retire ADR-015's "encrypt the secret at rest" machinery.** The project is
greenfield — no device-auth code and no `agents` secret rows exist — so this is
the cheapest moment it will ever be to make the switch, and it deletes an entire
class of problem rather than mitigating it.

- **The crux (Q1).** HMAC forces a *recoverable* secret server-side because both
  sides must hold the **same** key to recompute the MAC (RFC 2104). ADR-015 is
  the tax on that fact. Asymmetric signing removes the tax outright: the backend
  stores **only the device's public key**, holds **no secret**, and a full DB
  dump leaks **nothing usable** — there is no ciphertext, no nonce, no key
  version, and no env-var key to protect. The "encrypt the secret at rest"
  problem ADR-015 solves *stops existing.*
- **ADR-015's key-data separation is real but thin (Q2).** Key in Railway env,
  ciphertext in Supabase = genuine separation against a **pure database read**
  (SQLi, dump, backup theft) — that's a real win over a plaintext column. But
  the app process holds both the key and the ciphertext, so it **does not**
  satisfy ASVS 6.4.2 (ADR-015 admits this), and it does nothing against an
  app-server compromise. Asymmetric signing beats it on the *high* end too: even
  a compromised app process holds no device secret to steal.
- **Industry default is asymmetric (Q3).** AWS IoT Core leads with X.509 client
  certs / mTLS precisely because "the private key never leaves the device"; Azure
  DPS supports X.509, TPM, and symmetric SAS keys but states plainly that
  "X.509 certificate is more secure, and should be used for more stringent
  security requirements," positioning symmetric keys as the "Hello world" option.
  Symmetric survives mainly for constrained/legacy devices — a Pi is neither.
- **mTLS is not viable behind Railway (Q3).** Railway's edge terminates TLS with
  its own Let's Encrypt cert; a FastAPI HTTP service never sees a client cert.
  mTLS would require a raw TCP proxy with app-side TLS termination — too heavy.
  So the asymmetric option to actually adopt is **Ed25519 request signing**, not
  mTLS.
- **Ed25519 is a drop-in for the existing envelope (Q3b).** The Pi holds a 32-byte
  private key in `/etc/dmitri/agent.env`, signs the **same canonical string
  ADR-005 already defines**, and the backend verifies with a stored 32-byte public
  key. The only change is `X-Signature = Ed25519_sign(...)` instead of
  `HMAC-SHA256(...)`, and "recompute HMAC" → "verify signature with public key."
  Timestamp / nonce / body-hash envelope is unchanged.
- **Smaller blast radius on provisioning (Q4).** Asymmetric: the private key is
  generated **on the device** and never transmitted; only the public key goes to
  the backend — over a *non-secret* channel. Symmetric (today's AUTH.md flow): the
  backend generates the secret and must hand the plaintext to the installer via a
  "vendor channel," a secret in motion that can be intercepted, logged, or leaked.

**When HMAC would be "fine anyway":** at single-digit devices with the secret
encrypted at rest and TLS in transit, HMAC is not *broken* — it's a defensible
defense-in-depth posture. The argument for switching is not that HMAC is unsafe;
it's that asymmetric is **strictly less to defend** (no recoverable secret
anywhere) and costs almost nothing to adopt while nothing is built.

---

## Findings

### 1. Does symmetric HMAC force a recoverable secret — and is that the weak point?

**Yes, unavoidably.** HMAC is a symmetric MAC: verification is *recomputation*
with the shared key. RFC 2104 defines HMAC over a single key `K` used by both
producer and verifier; the verifier computes `HMAC(K, text)` and compares — there
is no separate "verification key." Because the device sends
`X-Signature = HMAC-SHA256(secret, canonical)` (ADR-005) and never sends the
secret itself, the backend must possess the **raw** `secret` to recompute the MAC.
A one-way hash of the secret (bcrypt/argon2) is therefore cryptographically
impossible here — you cannot recompute an HMAC from a digest of the key. This is
exactly what ADR-015 and the prior research note establish, and it is correct.
— https://datatracker.ietf.org/doc/html/rfc2104

**Asymmetric signing removes the requirement entirely.** In a public-key
signature scheme the signer holds a **private** key and the verifier uses the
**corresponding public** key; the two keys are different, and the public key
cannot produce signatures. RFC 8032 (EdDSA/Ed25519): Ed25519 "operates as a
public-key signature scheme where a private key holder generates signatures that
can be verified using the corresponding public key," with 32-byte public keys and
64-byte signatures, targeting ~128-bit security, and — usefully — **deterministic**
signatures that "protect against attacks arising from signing with bad
randomness." — https://datatracker.ietf.org/doc/html/rfc8032

**Consequence for storage.** With Ed25519 the backend stores only the device's
**public** key. A public key is not a secret: a full DB dump, SQLi, or stolen
backup leaks a value that lets an attacker *verify* signatures but never *forge*
them. There is nothing to encrypt at rest, no env-var key to guard, no
`secret_ciphertext` / `secret_nonce` / `secret_key_version`. **The entire problem
ADR-015 exists to solve — "how do we hold a recoverable secret as safely as
possible against a database read" — disappears**, because there is no recoverable
secret. That is the load-bearing finding of this note: the weak point is not
*how* ADR-015 encrypts the secret, it's that a symmetric design obliges the
backend to hold a forgeable secret at all.

### 2. Does app-layer AES-GCM with an env-var key meaningfully beat a fenced plaintext column?

**Partly yes, but less than it first appears — and both are dominated by
asymmetric.** Two questions: (a) is ADR-015 better than plaintext, and (b) how
does it measure against what the standards actually ask for.

**(a) vs. plaintext: a real but bounded win.** The OWASP Cryptographic Storage
Cheat Sheet's load-bearing rule is *separation of keys and data* — "Where
possible, encryption keys should be stored in a separate location from encrypted
data" — so that compromise of one store does not yield both.
— https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
ADR-015 satisfies this against a **pure database read**: the AES-256-GCM key is a
Railway env var in the FastAPI process, the ciphertext is in Supabase Postgres, so
a dump / SQLi / stolen backup / replica yields only ciphertext. That genuinely
beats a plaintext column, which fails every database-read threat. This part of
ADR-015's "key-data separation" claim is honest and correct.

**(b) vs. the standard, and the counter-argument.** The separation is only across
the **database↔app** boundary, not the **app↔key** boundary. The same process
that reads the ciphertext also holds the key, so **a compromised app process has
both** and can decrypt every device secret. ASVS is explicit about what "real"
key management requires:

- **V6.4.1** — "Verify that a secrets management solution such as a key vault is
  used to securely create, store, control access to and destroy secrets."
- **V6.4.2** — "Verify that key material is not exposed to the application but
  instead uses an isolated security module like a vault for cryptographic
  operations."
- Source: https://raw.githubusercontent.com/OWASP/ASVS/v4.0.3/4.0/en/0x14-V6-Cryptography.md

App-layer AES-GCM with an env-var key satisfies 6.4.1 only weakly and **fails
6.4.2 outright** — key material *is* exposed to the app. ADR-015 concedes exactly
this ("does not satisfy ASVS 6.4.2") and books it as MVP debt, pointing at
Supabase Vault / KMS as the end-state. So the honest grading: ADR-015 lands
**above plaintext, below a vault**, and its protection is entirely against
DB-read threats, buying nothing against app compromise.

**Where asymmetric lands relative to this.** Ed25519 sidesteps the whole ASVS
6.4.x question for the *stored* value: the backend stores a **public** key, which
is not "key material" needing protection at all — no vault, no env-var key, no
6.4.2 gap, because there is no server-side secret to isolate. (The device's
private key still needs protecting *on the Pi* — filesystem perms on
`/etc/dmitri/agent.env`, per ADR-005's "store off source, off versioned
artifacts" — but that is true of the HMAC secret today too, and is unchanged.)
In the threat-model language of the prior note: asymmetric is the only option
whose "app-server compromise" column is also safe, because a compromised backend
holds nothing that can impersonate a device.

### 3. Industry best practice for device→cloud auth, 2024–2026

**The major clouds default to *asymmetric* per-device identity and keep only the
public/CA portion server-side.**

**AWS IoT Core — X.509 client certs, mutual TLS, private key never leaves the
device.** AWS's own words: "X.509 certificates enable asymmetric keys to be used
with devices. For example, you could burn private keys into secure storage on a
device so that sensitive cryptographic material never leaves the device. X.509
certificates provide stronger client authentication over other schemes, such as
user name and password or bearer tokens, because the private key never leaves the
device." Auth is TLS client-authentication mode: "AWS IoT requests an X.509 client
certificate … It then challenges the client for proof of ownership of the private
key that corresponds to the public key contained in the certificate." AWS
recommends "each device or client be given a unique certificate." The backend
holds certificates/CA registrations, not device private keys.
— https://docs.aws.amazon.com/iot/latest/developerguide/x509-client-certs.html

**Azure IoT Hub / DPS — X.509, TPM, *or* symmetric SAS keys, with asymmetric
explicitly recommended for stronger requirements.** DPS supports three attestation
mechanisms: X.509 certificates, TPM, and Symmetric Key.
— https://learn.microsoft.com/en-us/azure/iot-dps/concepts-service
On the symmetric option Microsoft is blunt: "Symmetric key attestation is a simple
approach … a 'Hello world' experience for developers who are new to device
provisioning, or don't have strict security requirements. Device attestation using
a TPM or an X.509 certificate is more secure, and should be used for more stringent
security requirements," and symmetric "provide[s] a way for legacy devices with
limited security functionality to bootstrap to the cloud."
— https://learn.microsoft.com/en-us/azure/iot-dps/concepts-symmetric-key-attestation

**When symmetric keys still get used, and why.** Two reasons, per the Azure docs
above: (1) *legacy / constrained devices* that can't do certificate/TPM crypto,
and (2) *developer simplicity* for low-security scenarios. Notably, even Azure's
symmetric **group** enrollment avoids shipping one shared secret to every device:
each device gets a **derived** key = `HMAC-SHA256(group_key, registration_id)`,
so "the group key is never stored on a device" and "the device key is never
copied to another location." A Raspberry Pi running Python is neither legacy nor
constrained — it can do Ed25519 trivially — so the "reasons to stay symmetric"
don't apply to Dmitri.

**Google Cloud IoT Core** was **retired on 2023-08-16**; Google exited the
first-party device-auth business and pointed customers at partners (ClearBlade,
EMQX, et al.). Its successor patterns are those partners' brokers, which likewise
center on X.509 / per-device keypairs. So there is no live Google first-party
counter-example to the AWS/Azure asymmetric-default story.
— https://www.itpro.com/network-internet/internet-of-things-iot/368845/google-cloud-to-retire-iot-core-service-in-2023
— https://blog.balena.io/gcp-iot-core-retirement-migration-to-balena/

**Is mTLS realistic for a Pi → FastAPI-behind-Railway setup? No.** Railway's edge
proxy **terminates TLS** with an automatically provisioned Let's Encrypt
certificate, requires TLS 1.2+ and mandatory SNI, and redirects/served all HTTP
traffic over its own cert.
— https://docs.railway.com/networking/public-networking/specs-and-limits
Because Railway terminates TLS at the edge for HTTP services, a client certificate
presented by the Pi never reaches the FastAPI process — there is no documented
client-cert / mTLS passthrough for HTTP services. Getting mTLS would mean running a
**raw TCP proxy** and doing TLS (and cert validation) inside the app, which is a
large operational change for a single-service deployment. **Conclusion: mTLS is
off the table for this stack; the practical asymmetric option is Ed25519 request
signing at the application layer**, which is transport-agnostic and rides straight
through Railway's HTTPS proxy.

### 3b. Ed25519 request signing, concretely — is it a drop-in for ADR-005's envelope?

**Yes. It reuses ADR-005's canonical string and headers verbatim; only the
signature primitive and the verify step change.** Confirmed from first-party
crypto-library docs:

- **PyNaCl (libsodium).** "Signing keys are produced from a 32-byte (256-bit)
  random seed"; `SigningKey.generate()` makes a private key; its `verify_key`
  property is the public key; `sign()` signs a message; `VerifyKey.verify()`
  "verifies the signature of a signed message" and raises `BadSignatureError` on
  failure. "Ed25519 keys are only 256-bits (32 bytes)" and "Ed25519 signatures
  are only 512-bits (64 bytes)," with raw / Hex / Base64 encoders for
  serialization. — https://pynacl.readthedocs.io/en/latest/signing/
- **pyca/cryptography.** `Ed25519PrivateKey.generate()`; `private_key.sign(data)`
  "Returns bytes: The 64 byte signature"; `public_key.verify(signature, data)`
  raises `cryptography.exceptions.InvalidSignature` on failure. Keys serialize via
  `private_bytes_raw()` / `public_bytes_raw()` and reload via
  `Ed25519PrivateKey.from_private_bytes(data)` /
  `Ed25519PublicKey.from_public_bytes(data)`, "each requiring exactly 32 bytes."
  — https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/

**The mapping to ADR-005 is one-to-one:**

| ADR-005 today (HMAC) | Ed25519 variant |
|---|---|
| Pi holds `DEVICE_SECRET` (32-byte shared) in `/etc/dmitri/agent.env` | Pi holds `DEVICE_PRIVATE_KEY` (32-byte Ed25519 seed) in `/etc/dmitri/agent.env` |
| Canonical string = METHOD\nPATH\nX-Device-Id\nX-Timestamp\nX-Nonce\nX-Body-SHA256 | **unchanged** |
| `X-Signature = hex(HMAC-SHA256(secret, canonical))` | `X-Signature = hex(Ed25519_sign(privkey, canonical))` (64-byte sig → 128 hex chars) |
| Headers `X-Device-Id/-Timestamp/-Nonce/-Body-SHA256`, 5-min skew, nonce anti-replay | **unchanged** |
| Backend **recomputes** `HMAC(secret, canonical)`, compares | Backend **verifies** `Ed25519_verify(pubkey, canonical, sig)` |
| `agents.secret_ciphertext/secret_nonce/secret_key_version` (+ env-var AES key) | `agents.public_key` (32 bytes, plaintext — it's public) |

So the request envelope (timestamp, nonce, body hash, skew window, replay
defense, and the WSS-upgrade variant with empty-body hash from ADR-011) is
**identical**; the change is confined to the signing call on the Pi and the verify
call on the backend, plus swapping three encrypted columns for one plaintext
`public_key` column.

**Downsides / costs (small, and worth naming):**
- **Signature size.** 64 bytes vs HMAC-SHA256's 32 bytes → the `X-Signature`
  header roughly doubles (128 hex chars vs 64). Negligible over HTTP.
- **Verify cost.** Ed25519 verification is asymmetric-curve math, so per-request
  verification is more CPU than an HMAC recompute. At single-digit devices and
  Dmitri's request volumes this is immaterial (Ed25519 verifies are sub-millisecond
  and RFC 8032 markets "high performance on a variety of platforms"). It matters
  only at very high RPS, which is not this workload.
- **Key format / serialization discipline.** Must pin a serialization (raw 32-byte
  keys, hex-encoded, is simplest and matches ADR-005's hex convention) and store
  the public key in exactly that form. Both libraries make this a one-liner
  (`public_bytes_raw()` / `VerifyKey.encode()`), so it's a convention to fix, not
  a hazard.
- **No shared HMAC test vectors** — but Ed25519 has RFC 8032 test vectors, so
  interop testing is at least as well-supported.

### 4. Provisioning / secret handoff — blast radius

**Symmetric (today's AUTH.md flow) — secret in motion.** AUTH.md §"September
provisioning flow": the **backend generates** `agent_id` + secret; the **installer
receives the plaintext secret once via a vendor channel** (install playbook,
secure handoff); the installer writes it into the Pi config. The secret therefore
**exists in at least three places over time** — backend RNG output, the vendor
channel/handoff artifact, and the Pi — and travels over a channel that must be
kept confidential. Every hop is an interception/logging/leak opportunity, and the
backend must *store it recoverably* forever after (the ADR-015 problem). This is a
meaningful blast radius for a **non-technical provisioning audience**: "one-time
secret handoff over a vendor channel" is exactly the fragile step, and it's the
part hardest to make idiot-proof.

**Asymmetric — nothing secret ever moves.** The Pi **generates its own keypair
on-device** (`Ed25519PrivateKey.generate()`), the private key **never leaves the
device**, and only the **public** key is sent to the backend — over a channel that
**does not need to be confidential** (a public key is safe to email, log, print in
a playbook, or POST in the clear; it only needs *integrity*, i.e. binding the
right pubkey to the right `agent_id`/`org_id`). This is precisely why AWS frames
X.509 as "stronger … because the private key never leaves the device" (Q3). The
secret-handling blast radius shrinks to **one location (the Pi)** and **zero
secret-in-transit hops**.

**What this means for the installer flow.** The awkward "transmit a plaintext
secret to a non-technical-adjacent installer without leaking it" step is replaced
by "the device makes its own key and reports a non-secret public key." The
provisioning playbook still needs to bind pubkey→agent_id→org_id with integrity
(so an attacker can't register their own pubkey for someone's agent), but that is
an **authorization/enrollment** problem (an admin-approved enrollment token or an
out-of-band confirmation), not a **secrecy** problem — and it's the same
enrollment-trust problem the symmetric flow already has *on top of* the secrecy
problem. Net: asymmetric strictly reduces what the vendor channel must protect.

### 5. Bottom line / recommendation

**Given the facts — single-digit devices per org, one device per org initially, a
cloud backend, a non-technical provisioning audience, and no device-auth code
written yet — revise to Ed25519 per-device request signing.** The reasoning:

1. **It deletes a problem instead of mitigating one.** ADR-015 is an entire ADR,
   three columns, an env-var key, a rotation story, and self-admitted ASVS-6.4.2
   debt — all of it in service of safely holding a secret the backend only needs
   because HMAC is symmetric. Ed25519 makes the server-side stored value a
   **public** key, so the DB-read threat class (SQLi, dump, backup theft) is
   neutralized *by construction*, and the app-compromise threat is reduced too
   (no device secret to steal). See Q1–Q2.
2. **It's the industry default for exactly this shape.** AWS and Azure lead with
   asymmetric per-device identity and keep only public/CA material server-side;
   symmetric survives for legacy/constrained devices, which a Pi is not. See Q3.
3. **It's a genuine drop-in.** Same canonical string, same headers, same skew and
   nonce/replay envelope, same WSS variant — only `sign`/`verify` and the stored
   column change. See Q3b.
4. **Smaller provisioning blast radius** for a non-technical audience: no secret
   in transit; the private key is born on the device and stays there. See Q4.
5. **Greenfield = free.** No `agents` secret rows exist; there is no data to
   migrate, no deployed Pi to re-key, no shipped client to break. The migration
   cost is "write the verify path against a public-key column instead of an
   encrypted-secret column" — the same amount of code either way, minus all the
   encryption plumbing.

**The even-handed caveat.** HMAC-with-encrypted-secret is **not broken** at this
scale. With TLS in transit, the secret encrypted at rest per ADR-015, and a
handful of devices, it's a defensible defense-in-depth posture, and if a
meaningful amount of HMAC code already existed, "leave it" would be reasonable.
The case for switching rests on two things being simultaneously true *right now*:
(a) asymmetric is **strictly less to defend** (no recoverable server-side secret
under any threat), and (b) it is **nearly free to adopt today** because nothing is
built. Both hold, so switch.

**If the team chooses to keep HMAC anyway** (e.g. to minimize novelty before the
September demo): ADR-015's app-layer AES-GCM is an acceptable MVP posture *as
written* — keep the `key_version` tag, use a **sealed** Railway variable for the
key, and keep the documented path to Supabase Vault / KMS for 6.4.2. That's a
legitimate "defense-in-depth is adequate at this scale" call. It is just more
moving parts, indefinitely, than the asymmetric design needs.

---

## Implications for ADR-005 / ADR-015 / DMI-61

**If the recommendation (Ed25519) is adopted:**

- **ADR-005 §1 (Agent → API).** Change "HMAC-SHA256 por device" to "Ed25519
  per-device signature." Canonical string, the five `X-*` headers, 5-min skew,
  and nonce anti-replay stay **verbatim**. Redefine `X-Signature` as the
  hex-encoded 64-byte Ed25519 signature over the same canonical string. Update the
  ADR-011 WSS-upgrade amendment the same way (verify signature over the empty-body
  canonical string instead of recomputing HMAC). Update the "Provisionamento e
  rotacao" section: the keypair is generated **on the device**; only the public
  key is registered with the backend; rotation = issue a new keypair on the Pi and
  replace the stored public key (no secret to transmit or invalidate confidentially).
  Change the reference from "RFC 2104: HMAC" to "RFC 8032: EdDSA/Ed25519."
- **ADR-015.** **Superseded / retired.** There is no recoverable secret to store,
  so `secret_ciphertext` / `secret_nonce` / `secret_key_version`, the sealed
  Railway AES key, the Supabase-Vault end-state, and the ASVS-6.4.2 MVP-debt note
  all fall away. Replace the whole concern with a single `agents.public_key` column
  (32 raw bytes, or 64 hex chars) stored in **plaintext** — because it is public.
  Record ADR-015's decision as reversed: "encrypt-secret-at-rest no longer needed;
  device auth is asymmetric, backend stores only public keys."
- **AUTH.md.** Rewrite the "September provisioning flow" and the two-audience
  table: installer step becomes "device generates keypair, installer registers the
  device's **public** key with the backend" (integrity-bound to `agent_id`/`org_id`
  via an admin-approved enrollment, no confidential handoff). Drop "installer
  receives plaintext secret once via vendor channel." The `secret_hash` wording
  (already flagged wrong) is deleted rather than corrected.
- **DMI-61 (and the DMI-59 schema / DMI-62 WSS / DMI-63 ingest work).** The
  `agents` migration defines `public_key` instead of the three secret columns; the
  verify path (WSS upgrade + ingest) calls `Ed25519PublicKey.from_public_bytes(...)
  .verify(sig, canonical)` (pyca/cryptography, already a likely dependency) or
  PyNaCl `VerifyKey.verify(...)`; the Pi client signs with a locally-generated
  private key from `/etc/dmitri/agent.env`. No encryption/decryption code, no
  env-var key handling, no key-rotation-of-the-encryption-key logic.

**If the recommendation is NOT adopted (keep ADR-005/015 HMAC):**

- **ADR-005 / ADR-015 / AUTH.md** stay as written; correct only the known nit that
  `secret_hash` is a misnomer (the column holds AES-GCM ciphertext, not a hash) —
  already captured in ADR-015.
- **DMI-61 etc.** implement the AES-256-GCM encrypt/decrypt path with the key in a
  **sealed** Railway variable, keep the `secret_key_version` tag for key rotation,
  and carry ADR-015's documented ASVS-6.4.2 debt plus the Supabase-Vault / KMS
  end-state as the Phase-2 hardening item (AUTH.md Phase 2 "prod secrets"). The
  provisioning flow keeps the confidential one-time secret handoff over the vendor
  channel, with its larger blast radius (Q4).

---

## Sources

- RFC 2104 — HMAC (symmetric, verifier needs the raw key): https://datatracker.ietf.org/doc/html/rfc2104
- RFC 8032 — EdDSA / Ed25519 (public/private keypair, 32-byte keys, 64-byte sigs, deterministic): https://datatracker.ietf.org/doc/html/rfc8032
- pyca/cryptography — Ed25519 API: https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/
- PyNaCl — digital signatures: https://pynacl.readthedocs.io/en/latest/signing/
- AWS IoT Core — X.509 client certificates ("private key never leaves the device"): https://docs.aws.amazon.com/iot/latest/developerguide/x509-client-certs.html
- Azure IoT DPS — attestation mechanisms (X.509 / TPM / symmetric): https://learn.microsoft.com/en-us/azure/iot-dps/concepts-service
- Azure IoT DPS — symmetric key attestation ("X.509 … more secure … for more stringent security requirements"; derived device keys): https://learn.microsoft.com/en-us/azure/iot-dps/concepts-symmetric-key-attestation
- Google Cloud IoT Core retirement (2023-08-16): https://www.itpro.com/network-internet/internet-of-things-iot/368845/google-cloud-to-retire-iot-core-service-in-2023 · https://blog.balena.io/gcp-iot-core-retirement-migration-to-balena/
- OWASP ASVS v4.0.3 V6 Cryptography (6.4.1 / 6.4.2): https://raw.githubusercontent.com/OWASP/ASVS/v4.0.3/4.0/en/0x14-V6-Cryptography.md
- OWASP Cryptographic Storage Cheat Sheet (separation of keys and data): https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- Railway networking specs & limits (edge terminates TLS, Let's Encrypt, TLS 1.2+, mandatory SNI): https://docs.railway.com/networking/public-networking/specs-and-limits
