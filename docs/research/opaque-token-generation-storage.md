# Research: generating and storing opaque security tokens

> **Scope.** Dmitri backend (Python 3.11+, FastAPI, SQLModel/Postgres),
> auth spec `specs/016-sessions-auth-routes/`. Two kinds of opaque, random
> tokens:
> - **refresh tokens** — long-lived (7 days), delivered to the browser in an
>   `httpOnly` cookie, rotated on each use, presented back to `/auth/refresh`.
> - **password-reset tokens** — short-lived (~1h), single-use, emailed as a link.
>
> Planned design: generate a random raw token, store only `SHA-256(raw)` in the
> DB (raw never stored), look the row up by that hash on presentation.
>
> Primary sources only: Python `secrets` and `hashlib` official docs, OWASP
> Cheat Sheets (Session Management, Forgot Password, Password Storage,
> Cryptographic Storage), NIST SP 800-63B, IETF RFC 9700 (OAuth 2.0 Security
> BCP). Fetched 2026-07-23.

---

## TL;DR verdict

- **Generate** raw tokens with `secrets.token_urlsafe(32)` — 32 bytes = **256
  bits** of CSPRNG entropy, comfortably above the OWASP ≥128-bit bar. Never use
  the `random` module.
- **Store** only `hashlib.sha256(raw.encode()).hexdigest()`. A **plain fast hash
  is correct here** — the token is high-entropy random, so a slow hash
  (argon2/bcrypt) buys nothing. Slow hashing exists to defend *low-entropy human
  passwords*; it does not apply to 256-bit random tokens.
- **Look up** the row by the stored hash (indexed, exact-match). The hash is not
  a secret, so an indexed lookup on it is fine. Compare with
  `hmac.compare_digest` / `secrets.compare_digest` if you compare in code.
- **Reset tokens:** CSPRNG, single-use (consumed on use), short TTL, hash-at-rest
  (OWASP Forgot Password).
- **Refresh tokens:** rotate on every use, and on reuse of an already-used token
  revoke the whole grant family (RFC 9700 §4.14) — already decided by the spec.

---

## Findings

### 1. Generating the raw token in Python

Source: Python `secrets` docs — https://docs.python.org/3/library/secrets.html

- **Use `secrets`, not `random`.** "In particular, `secrets` should be used in
  preference to the default pseudo-random number generator in the `random`
  module, which is designed for modelling and simulation, not security or
  cryptography." `secrets` draws from the OS CSPRNG.
- **Token constructors** (all take `nbytes` random bytes; default is
  `DEFAULT_ENTROPY` = 32 bytes if omitted):
  - `token_bytes(nbytes)` — "Return a random byte string containing *nbytes*
    number of bytes." Raw bytes; not URL/DB-safe as text.
  - `token_hex(nbytes)` — "Return a random text string, in hexadecimal. The
    string has *nbytes* random bytes, each byte converted to two hex digits." →
    output length = `2 * nbytes` chars.
  - `token_urlsafe(nbytes)` — "Return a random URL-safe text string, containing
    *nbytes* random bytes. The text is Base64 encoded, so on average each byte
    results in approximately 1.3 characters." → output length ≈ `1.3 * nbytes`
    chars.
- **Entropy math.** `nbytes` bytes from a CSPRNG = `8 * nbytes` bits of entropy,
  regardless of the encoding (hex/base64 only changes the *string length*, not
  the underlying entropy). So `nbytes=16` → 128 bits, `nbytes=32` → 256 bits.
  - `token_urlsafe(32)` → 256 bits, ~43-char string.
  - `token_hex(32)` → 256 bits, 64-char string.
- **How much is enough.** Python docs: "As of 2015, it is believed that 32 bytes
  (256 bits) of randomness is sufficient for the typical use-case expected for
  the `secrets` module." OWASP Session Management Cheat Sheet sets the floor:
  "Session identifiers must have at least `64 bits` of entropy," and when rolling
  your own generator, "use a cryptographically secure pseudorandom number
  generator (CSPRNG) with a size of at least `128 bits`." 256 bits clears both.
  - Context on why 128+ bits: with only 64 bits OWASP estimates "approximately
    585 years to successfully guess a valid session ID" under their assumptions —
    128/256 bits pushes brute-force firmly out of reach.
- **Cookie note.** OWASP: the `HttpOnly` cookie attribute is "mandatory to
  prevent session ID stealing through XSS attacks" — matches the spec's httpOnly
  refresh cookie.

Sources: Session Management Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html

### 2. Storing the token — hash, not raw; fast hash, not slow

**Why store a hash, not the raw value.** OWASP Forgot Password Cheat Sheet says
the reset token must be "Stored in a secure manner, as discussed in the Password
Storage Cheat Sheet" — i.e. persist a hash, not the plaintext. The reason: if an
attacker gets DB read access (SQLi, backup leak), stored raw tokens are
immediately replayable as valid sessions/resets; stored *hashes* are not — the
attacker would have to invert SHA-256 to mint a usable token, which is
infeasible.

**Why a plain fast hash (SHA-256) is the right tool here — and slow hashes are
not.** The primary sources frame slow hashing entirely as a defense against
*guessing low-entropy secrets*:

- Python `hashlib` docs: "Key derivation and key stretching algorithms are
  designed for secure password hashing. Naive algorithms such as `sha1(password)`
  are not resistant against brute-force attacks." The vulnerability is that a
  *password* is guessable.
  https://docs.python.org/3/library/hashlib.html
- OWASP Password Storage Cheat Sheet: "Fast hashing algorithms such as SHA-256
  are not suitable for password storage because they allow attackers to perform
  large numbers of guesses quickly." Again, the threat model is *guessing* — only
  meaningful when the input space is small enough to enumerate.
  https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

Our tokens are the opposite of a password: a `token_urlsafe(32)` value has 256
bits of CSPRNG entropy. There is no dictionary, no "top 10k", no human-chosen
pattern — the keyspace is `2^256`, which per the Python `secrets` docs is
"sufficient... against brute-force attacks." A slow, memory-hard hash (argon2id,
bcrypt) exists to add cost *per guess* so that enumerating a small keyspace is
uneconomical; when the keyspace is already unenumerable, that per-guess cost adds
latency and CPU on every login/refresh for zero security gain. So:

- **SHA-256 over the raw token: appropriate.** Pre-image resistance of SHA-256 is
  what protects the stored value, and the token's own entropy defeats brute
  force.
- **argon2id/bcrypt over the raw token: unnecessary.** They defend against
  low-entropy guessing, a threat that does not exist for a 256-bit random token,
  and they add per-request cost.
- **Passwords remain the opposite case** — low-entropy, human-chosen, guessable →
  they *do* require the slow hash (see
  `docs/research/password-handling-best-practices.md`).

> Note: none of the fetched OWASP cheat sheets states the high-entropy-token
> carve-out in one explicit sentence — the sheets discuss password storage. The
> conclusion above is the direct consequence of *their own stated rationale*
> (slow hashing defends guessable secrets) applied to a 256-bit random token,
> plus the Python-docs statement that 256 bits defeats brute force. No salt is
> needed either: salts defend against precomputation/rainbow tables across
> *many low-entropy* secrets; unique 256-bit tokens are already unique and
> unprecomputable.

Sources: Cryptographic Storage Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html

### 3. Lookup / comparison

- **`hashlib.sha256`.** `hashlib.sha256(b"...").hexdigest()` yields a 256-bit
  (32-byte) digest as 64 hex chars. https://docs.python.org/3/library/hashlib.html
- **Indexing by the hash is fine.** The stored SHA-256 is *not itself a secret*
  (knowing it doesn't let you produce a matching raw token), so putting a unique
  index on the `token_hash` column and doing an exact-match `WHERE token_hash =
  :h` lookup is acceptable. The DB does an equality match on a value the attacker
  cannot forge without the pre-image.
- **Constant-time comparison.** For *in-code* comparison of secret-derived
  values, use a constant-time compare to avoid timing side channels:
  `secrets.compare_digest(a, b)` "Return `True` if strings or bytes-like objects
  *a* and *b* are equal... using a 'constant-time compare' to reduce the risk of
  timing attacks." (`secrets.compare_digest` is `hmac.compare_digest`.)
- **Timing nuance for the DB lookup.** A B-tree index lookup keyed on the hash
  can in principle leak timing about how far a comparison proceeded, but the
  attacker is matching against `SHA-256(raw)` and only controls `raw`; they
  cannot steer the stored hash byte-by-byte the way a classic
  compare-the-raw-secret timing attack requires, because the hash destroys the
  structure of their input. Timing a match therefore reveals essentially nothing
  actionable. Where you *do* compare the presented token to a stored value in
  Python (rather than via SQL), hash the presented token first and compare the
  digests with `compare_digest`.

### 4. Single-use + expiry (reset tokens)

Source: OWASP Forgot Password Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html

Reset tokens must be:

- **CSPRNG-generated** — "Generated using a cryptographically secure random
  number generator."
- **Long enough** — "Long enough to protect against brute-force attacks."
- **Single-use** — "Invalidated after they have been used." Consume the row (mark
  used / delete) inside the same transaction that performs the password change,
  so a token can never be redeemed twice.
- **Short-lived** — enforce a limited lifetime / expiry; store an `expires_at`
  and reject on/after it. A short TTL (minutes to ~an hour) is standard; our ~1h
  fits.
- **Hashed at rest** — "Stored in a secure manner, as discussed in the Password
  Storage Cheat Sheet" (store `SHA-256(raw)`, not the raw token).
- **No enumeration** — "Return a consistent message for both existent and
  non-existent accounts," with responses in "a consistent amount of time," so the
  reset endpoint doesn't reveal which emails have accounts.

### 5. Refresh token rotation & reuse detection (concept)

Source: IETF RFC 9700, *Best Current Practice for OAuth 2.0 Security*, §4.14 —
https://www.rfc-editor.org/rfc/rfc9700

The spec already decides this; recording the primary-source basis:

- **Rotation.** Refresh tokens for public clients "MUST be sender-constrained or
  use refresh token rotation" — i.e. each `/auth/refresh` call issues a new
  refresh token and invalidates the presented one.
- **Reuse / replay detection.** With rotation, "if a refresh token is leaked and
  used by both the attacker and the legitimate client, reuse of an
  already-used/invalidated refresh token is detected and the authorization server
  SHALL revoke the active refresh tokens of that authorization grant." So on
  presentation of a token whose hash is found but already marked
  used/superseded, revoke the whole family/session rather than just rejecting the
  one request.

This composes cleanly with the hash-at-rest design: the rotated (old) token's
hash row is retained just long enough to detect reuse, then the family is
revoked.

---

## Recommended recipe for this codebase

**Generate (both token kinds):**

```python
import secrets

raw = secrets.token_urlsafe(32)   # 32 bytes = 256 bits CSPRNG entropy, ~43 chars
```

Send `raw` to the client (refresh cookie / reset-link query param). Never persist
`raw`.

**Hash for storage / lookup:**

```python
import hashlib

def token_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()   # 64 hex chars
```

Store `token_hash(raw)` in a `NOT NULL UNIQUE`-indexed column. Look up rows by
exact match on that column. **Do not** run tokens through argon2/bcrypt — a fast
SHA-256 is correct for 256-bit random tokens; slow hashing is only for
low-entropy passwords.

**Compare (when comparing in Python rather than via SQL equality):**

```python
import secrets

secrets.compare_digest(token_hash(presented_raw), stored_hash)  # constant-time
```

**Lifecycle:**

- **Reset token:** `expires_at = now + 1h`; on redeem, verify not-used and
  not-expired, apply the password change and mark the row used **in one
  transaction**; return an identical response/timing whether or not the email
  exists.
- **Refresh token:** `expires_at = now + 7d`, `httpOnly` + `Secure` +
  `SameSite` cookie; on `/auth/refresh` rotate (issue new, invalidate old); if a
  hash matches a row already marked used/superseded, revoke the whole
  session/grant family (RFC 9700 §4.14).
