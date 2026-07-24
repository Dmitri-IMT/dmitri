# ADR-015: Password policy — strong policy + breach screening, no forced rotation

> **Status:** Accepted (2026-07-23). **Supersedes** the "Password rotation — Every 3 months" row
> in [`AUTH.md`](../roadmap/AUTH.md) (Phase 1, Passwords). Research backing this decision:
> [`docs/research/password-handling-best-practices.md`](../research/password-handling-best-practices.md).

## Context

[`AUTH.md`](../roadmap/AUTH.md) Phase 1 mandated **forced password rotation every 3 months**:
a password expiring blocked normal API use until the user set a new one. Background research
against primary sources (NIST SP 800-63B, OWASP) surfaced a direct conflict with that decision.

NIST SP 800-63B §5.1.1.2 (Memorized Secret Verifiers):

> "Verifiers SHOULD NOT require memorized secrets to be changed arbitrarily (e.g., periodically)."

NIST's rationale, and the pattern OWASP documents independently: forced periodic rotation drives
users toward weaker, predictable passwords (small incremental edits, written-down passwords) and
should instead be triggered by **evidence of compromise**, not a calendar.

The same section is where NIST's other memorized-secret rules live, and Dmitri's existing policy
already agrees with most of them:

| Rule | NIST §5.1.1.1 / §5.1.1.2 | Dmitri (AUTH.md) |
|------|--------------------------|------------------|
| Minimum length | SHALL be ≥ 8 chars | Agrees |
| Reject breached/common passwords | SHALL screen against a compromised/commonly-used list | Agrees — but was not implemented as a concrete check |
| Reject obvious patterns / identity-derived guesses | Listed as screening targets (repetitive/sequential, context-specific words) | Agrees |
| Forced composition/complexity rules | SHOULD NOT impose | Not required beyond baseline; no conflict |
| **Forced periodic rotation** | **SHOULD NOT require** | **Conflicted — `AUTH.md` required it** |

A useful side effect of dropping rotation: it dissolves a real implementation deadlock (contract
ask **C5** in [`BACKEND.md`](../roadmap/BACKEND.md)) — an expired password made login return `403`
with no token, but `POST /auth/change-password` requires a Bearer token, so a user forced to change
their password had no way to authenticate the change. With no forced rotation, that branch does not
exist: login is `200` (valid) or `401` (bad credentials) only.

## Decision

### 1. No forced periodic password rotation

Drop the 3-month forced-rotation requirement entirely. Passwords are never expired by the passage
of time. A user changes their password only:

- **Voluntarily**, via `POST /auth/change-password` (requires current password + Bearer), or
- **Via self-serve reset**, via the forgot-password flow (`POST /auth/reset-password`).

There is no "password expired" state, no expiry-driven `403`, and no forced-change screen.

### 2. Strong policy enforced at every password-set point

Applied uniformly at invite completion, voluntary change-password, and reset:

- **Minimum length** per NIST §5.1.1.1 (≥ 8 chars; Dmitri's implementation may set a higher floor).
- **No forced character-class composition rules** (NIST §5.1.1.2 SHOULD NOT).
- **Reject obvious patterns and identity-derived guesses:** repeated characters (e.g. `111`),
  keyboard/simple suffixes (e.g. `1!`), repeated number sequences, birth dates, and names (user
  name, org name — implementation defines matching).

### 3. Breach screening via HIBP Pwned Passwords (k-anonymity)

Every password set (invite completion, change-password, reset) is screened against the **Have I
Been Pwned Pwned-Passwords range API**:

- `GET https://api.pwnedpasswords.com/range/{first 5 hex chars of SHA-1(password)}` — only the
  5-character prefix leaves the server; the full password/hash never does.
- The response lists suffix+count pairs for that prefix; a local match against the remaining 35
  hex characters rejects the password if it appears in the corpus.
- No API key required. Treated as **best-effort**: timeout + graceful degradation if the API is
  unreachable, rather than blocking account creation/password changes on an external dependency.
  A downloadable offline corpus is a documented fallback if zero-external-call behavior is later
  required.

This is the concrete mechanism for the "reject common/breached passwords" rule NIST §5.1.1.2
requires and that `AUTH.md` already named but did not specify how to implement.

## Consequences

- `AUTH.md`'s Passwords table row **"Password rotation — Every 3 months"** is superseded by this
  ADR; the roadmap doc is updated to link here instead of describing forced rotation.
- The `403` "password expired" login response, `password_change_token`, and the forced
  change-password screen are removed from the contract, spec, and UI docs (tracked in their
  owning documents, not this ADR).
- Contract ask **C5** (`BACKEND.md`) is void — the deadlock it described cannot occur.
- `password_changed_at` (from the DMI-58 identity migration) remains a harmless column; it is
  simply no longer read to compute an expiry.
- Voluntary change-password (`POST /auth/change-password`) and self-serve reset
  (`POST /auth/reset-password`) are unaffected and remain in scope.

## References

- NIST SP 800-63B, §5.1.1 Memorized Secrets — https://pages.nist.gov/800-63-3/sp800-63b.html
- OWASP Password Storage Cheat Sheet —
  https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- HIBP API v3 (Pwned Passwords) — https://haveibeenpwned.com/API/v3
- [`docs/research/password-handling-best-practices.md`](../research/password-handling-best-practices.md)
- [`AUTH.md`](../roadmap/AUTH.md) — superseded Passwords row
- [`BACKEND.md`](../roadmap/BACKEND.md) — contract ask C5 (now moot)
