# Research: password handling for a web application backend

> **Scope.** Dmitri backend (Python 3.11+, FastAPI, SQLModel/Postgres),
> AUTH.md Phase 1: email+password login, strong password policy, 3-month
> rotation, self-serve reset. Spec: `specs/016-sessions-auth-routes/`.
> Library decision under evaluation: **argon2-cffi** vs **passlib+bcrypt**,
> and **python-jose** vs **PyJWT** for the surrounding token work.
> Primary sources only (OWASP Cheat Sheets, NIST SP 800-63B, first-party
> library docs / PyPI, HIBP API docs). Fetched 2026-07-23.

---

## TL;DR verdict

- **Algorithm: Argon2id.** OWASP's first-choice recommendation, minimum
  config 19 MiB / t=2 / p=1.
- **Library: `argon2-cffi`** (`PasswordHasher`), not `passlib`. Passlib's last
  release is 1.7.4 (2020-10-08) and it is effectively unmaintained — it breaks
  against modern `bcrypt` (4.1+/5.0). `argon2-cffi` is actively maintained
  (25.1.0, 2025-06-03) and gives a first-class Argon2id API with built-in
  parameter-upgrade detection (`check_needs_rehash`).
- **JWT: `PyJWT`**, not `python-jose`. PyJWT is actively maintained (2.13.0,
  2026-05-21) and is the library FastAPI's own security docs use. python-jose
  has a history of security advisories and is a heavier JOSE stack we don't
  need for symmetric access tokens.
- **Policy: adopt NIST SP 800-63B** — enforce length + breached-password
  screening, drop composition/complexity rules. **AUTH.md's 3-month forced
  rotation directly conflicts with NIST**, which says verifiers SHOULD NOT
  require memorized secrets to be changed periodically. See reconciliation
  below.
- **Breached check: HIBP Pwned Passwords range API** (k-anonymity, SHA-1
  5-char prefix). External HTTP call; an offline downloadable list is a
  supported alternative.
- **Reset tokens: CSPRNG, single-use, short TTL, store only a hash, identical
  response for existent/non-existent accounts** (OWASP Forgot Password).

---

## Findings

### 1. Password hashing algorithm (OWASP)

Source: OWASP Password Storage Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

- **Argon2id is the first recommendation.** "Use Argon2id with a minimum
  configuration of 19 MiB of memory, an iteration count of 2, and 1 degree of
  parallelism." OWASP lists several equivalent configs (e.g. m=47104 KiB/46 MiB
  t=1 p=1 … through m=7168 KiB/7 MiB t=5 p=1) that "provide an equal level of
  defense, and the only difference is a trade off between CPU and RAM usage."
- **scrypt** is the fallback if Argon2id is unavailable: "use scrypt with a
  minimum CPU/memory cost parameter of (2^17), a minimum block size of 8 (1024
  bytes), and a parallelization parameter of 1."
- **bcrypt** is framed as for *legacy* systems: "For legacy systems using
  bcrypt, use a work factor of 10 or more and with a password limit of 72
  bytes."
- **bcrypt's 72-byte truncation caveat:** "bcrypt has a maximum length input
  length of 72 bytes for most implementations, so you should enforce a maximum
  password length of 72 bytes." OWASP warns that pre-hashing to dodge the limit
  introduces "password shucking" and null-byte issues, so it is not a clean
  workaround.
- **PBKDF2** only for FIPS-140 compliance: "use PBKDF2 with a work factor of
  600,000 or more and set with an internal hash function of HMAC-SHA-256."

Takeaway for Dmitri: no FIPS constraint, no legacy hash to migrate → Argon2id
at the OWASP minimum (19 MiB / t=2 / p=1) or above.

### 2. Python library choice

**argon2-cffi (recommended).**
Source: PyPI — https://pypi.org/project/argon2-cffi/ (latest **25.1.0**,
released **2025-06-03**; "Argon2 for Python", "the simplest way to use it in
Python"). API docs — https://argon2-cffi.readthedocs.io/en/stable/api.html

- `PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32,
  salt_len=16, encoding='utf-8', type=Type.ID)` — defaults to **Argon2id**,
  memory_cost in **kibibytes** (65536 KiB = 64 MiB, above the OWASP 19 MiB
  floor), parallelism 4.
- `hash(password, *, salt=None) -> str` — generates a secure random salt per
  call; returns the encoded hash; raises `HashingError` on failure.
- `verify(hash, password) -> Literal[True]` — returns `True` on match;
  otherwise raises `VerifyMismatchError` (mismatch), `VerificationError`
  (other), or `InvalidHashError` (malformed hash). Note: it *raises* rather
  than returning `False`, so callers wrap it.
- `check_needs_rehash(hash) -> bool` — reports whether `hash` was produced with
  the instance's current parameters; the standard hook for transparently
  upgrading cost factors on successful login.

**passlib (not recommended in 2026).**
Source: PyPI — https://pypi.org/project/passlib/ — latest **1.7.4**, released
**2020-10-08** ("password hashing library for Python 2 & 3 … over 30 password
hashing algorithms"). No release in ~6 years.

- Passlib is effectively unmaintained and breaks against modern `bcrypt`.
  Downstream evidence (primary bug trackers / project threads):
  - "module `passlib` is unmaintained and need to be replaced" —
    https://github.com/Kozea/Radicale/issues/1405 and
    https://github.com/Kozea/Radicale/issues/1952
  - "Passlib cannot detect bcrypt's version" —
    https://bugs.launchpad.net/kolla-ansible/+bug/2102117 ; `bcrypt` 4.1.x
    broke passlib's bcrypt backend —
    https://bugs.gentoo.org/925289 (and `bcrypt` 5.0.0 broke it further).
  - FastAPI's own community flagged the problem: "passlib seems not being
    maintained anymore. However FastAPI's docs still using. Consider change it."
    — https://github.com/fastapi/fastapi/discussions/11773
- Practical failure mode: with newer `bcrypt`, passlib mis-reads the backend
  version and can raise spurious "password cannot be longer than 72 bytes"
  errors. Pinning `bcrypt<4.1` (or `<5`) is the only stopgap.

**Verdict:** for a greenfield Argon2id backend, depend on `argon2-cffi`
directly. Passlib's only real draw is multi-scheme migration, which Dmitri
(no existing hashes) does not need.

### 3. Password policy (NIST SP 800-63B)

Source: NIST SP 800-63B, §5.1.1 Memorized Secrets —
https://pages.nist.gov/800-63-3/sp800-63b.html

- **Minimum length (§5.1.1.1):** "Memorized secrets SHALL be at least 8
  characters in length if chosen by the subscriber."
- **Maximum length (§5.1.1.2):** "Verifiers SHOULD permit subscriber-chosen
  memorized secrets at least 64 characters in length."
- **No composition rules (§5.1.1.2):** "Verifiers SHOULD NOT impose other
  composition rules (e.g., requiring mixtures of different character types or
  prohibiting consecutively repeated characters) for memorized secrets."
- **Breached / common-password screening (§5.1.1.2):** "Verifiers SHALL compare
  the prospective secrets against a list that contains values known to be
  commonly-used, expected, or compromised." (NIST examples of what to include:
  breach-corpus passwords, dictionary words, repetitive/sequential characters,
  and context-specific words such as the service name or the username.)
- **No hints (§5.1.1.2):** "Memorized secret verifiers SHALL NOT permit the
  subscriber to store a 'hint' that is accessible to an unauthenticated
  claimant."
- **No periodic rotation (§5.1.1.2):** "Verifiers SHOULD NOT require memorized
  secrets to be changed arbitrarily (e.g., periodically)." NIST's guidance is to
  force a change only on evidence of compromise.

**AUTH.md vs NIST — agreement and conflict:**

| AUTH.md rule | NIST position | Verdict |
|---|---|---|
| Minimum length | SHALL ≥ 8, SHOULD allow ≥ 64 | Agrees (ensure a max of ≥64, don't cap low) |
| Reject common / breached passwords | SHALL screen against compromised list | Agrees — this is the core NIST control |
| Reject patterns / names (username, service) | NIST lists context-specific words & repetitive/sequential chars as screen targets | Agrees |
| Forced composition/complexity (if any) | SHOULD NOT impose composition rules | Would conflict — do **not** require character-class mixes |
| **3-month forced rotation** | **SHOULD NOT require periodic change** | **CONFLICTS** — see reconciliation |

### 4. Breached-password check (HIBP Pwned Passwords)

Source: HIBP API v3 docs — https://haveibeenpwned.com/API/v3

- **k-anonymity range model:** the API "allows the first 5 characters of either
  a SHA-1 or an NTLM hash (not case-sensitive) to be passed to the API." The
  full password/hash never leaves the client.
- **Request:** `GET https://api.pwnedpasswords.com/range/{first 5 SHA-1 chars}`.
- **Response:** "the suffix of every hash beginning with the specified prefix,
  followed by a count of how many times it appears in the data set" (~hundreds
  of suffix+count lines). The client hashes the candidate password with SHA-1,
  sends the 5-char prefix, then matches the remaining 35 hex chars locally.
- **No API key / free:** "The Pwned Passwords API is freely accessible without
  the need for a subscription and API key." (`?mode=ntlm` switches to NTLM
  suffixes.)
- **Offline alternative:** "all password hashes are also available for download"
  via the Pwned Passwords Downloader (GitHub), "enabling offline querying
  without API dependency."

Takeaway for Dmitri: the range API is one outbound HTTPS GET at signup/change
time — privacy-preserving and keyless. Because it's an external dependency,
treat it as best-effort (timeout + fallback), and consider the downloadable
corpus if we want zero external calls or offline determinism.

### 5. Reset tokens (OWASP Forgot Password)

Source: OWASP Forgot Password Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html

- **CSPRNG:** the token must be "Generated using a cryptographically secure
  random number generator."
- **Unguessable:** "Long enough to protect against brute-force attacks."
- **Single-use:** "Invalidated after they have been used."
- **Short-lived:** tokens must have a limited lifetime / expiry (no token
  persisting indefinitely); a short TTL (commonly minutes to an hour) is the
  standard.
- **Store only a hash:** the token/identifier should be "Stored in a secure
  manner, as discussed in the Password Storage Cheat Sheet" — i.e. persist a
  hash of the token, not the raw value, so a DB read can't mint valid resets.
- **No account enumeration:** "Return a consistent message for both existent and
  non-existent accounts," and ensure "responses return in a consistent amount
  of time to prevent an attacker enumerating which accounts exist."

### 6. JWT library (PyJWT vs python-jose)

- **PyJWT** — PyPI https://pypi.org/project/PyJWT/ — latest **2.13.0**, released
  **2026-05-21**, "JSON Web Token implementation in Python" (RFC 7519). Actively
  maintained and the library used throughout FastAPI's own security tutorial.
- **python-jose** — PyPI https://pypi.org/project/python-jose/ — latest
  **3.5.0**, released **2025-05-28**, "A JOSE implementation in Python" (JWS/
  JWE/JWK/JWA). Broader JOSE surface than we need for symmetric HS256 session
  tokens, and it has a track record of security advisories.

**Verdict:** use **PyJWT** — smaller surface, actively maintained, matches the
FastAPI docs. python-jose only earns its keep if we need full JWE/JWK, which
Phase 1 does not.

---

## Recommendation for Dmitri

1. **Hashing:** Argon2id via **`argon2-cffi`** `PasswordHasher`. Start at or
   above the OWASP floor (memory ≥ 19 MiB; the library default 64 MiB / t=3 /
   p=4 is comfortably above it). Wrap `verify()` (it raises, not returns
   `False`) and call `check_needs_rehash()` on each successful login to upgrade
   parameters transparently. Do **not** add `passlib`.
2. **JWT:** **`PyJWT`** for session/access tokens (HS256 with a server secret,
   or RS256 later if we split issuer/verifier). Skip `python-jose`.
3. **Policy:** enforce **length + breached-password screening** (HIBP range
   API, with timeout/fallback, or the offline corpus) and reject
   context-specific terms (username/email/service name). **Drop any forced
   character-class complexity** — NIST §5.1.1.2 advises against it.
4. **Reconciling the 3-month rotation with NIST:** NIST §5.1.1.2 explicitly
   discourages arbitrary periodic rotation, so blanket 90-day expiry is a
   documented conflict. Options, best-aligned first:
   - **Preferred:** replace periodic rotation with **event-driven rotation** —
     force a change only when a password is found in a breach list (re-check
     stored passwords against HIBP, or screen on every login), matching NIST's
     "change on evidence of compromise" model.
   - **If the 3-month rule is a hard business/compliance requirement:** keep it,
     but record it as a conscious deviation from NIST SP 800-63B §5.1.1.2 in the
     spec/ADR, and pair it with the breach screening above so the periodic reset
     is a belt-and-suspenders control rather than the primary defense.
5. **Reset flow:** CSPRNG token (e.g. `secrets.token_urlsafe`), store only its
   hash, single-use, short TTL (minutes), and return an **identical response +
   consistent timing** whether or not the email exists.
