# Research: auth error disclosure, HTTP status choice, and invite state

> **Scope.** Dmitri backend (Python 3.11+, FastAPI, SQLModel/Postgres) plus the
> React SPA consumer. Linear issue **DMI-77** pins machine-readable
> `error.code` values and HTTP statuses on four auth/invite endpoints:
> `POST /auth/reset-password`, `POST /auth/change-password`,
> `POST /invites` (create), `POST /invites/accept`.
>
> Decisions under evaluation:
> - distinct error codes for "reset link dead/expired" vs "new password fails policy";
> - `410 Gone` (was `400`) for a consumed/expired single-use link;
> - `409 Conflict` (over `400`) for "this address already has a live invite";
> - `400` (not `401`) for wrong-current-password on change-password;
> - whether ordering cheap validation before the Argon2id verify leaks timing;
> - Argon2id memory as a DoS surface on the two unauthenticated endpoints.
>
> Primary sources only: RFC 9110 (rfc-editor.org), RFC 6750, RFC 9106,
> NIST SP 800-63B, OWASP Cheat Sheet Series (Authentication, Error Handling,
> Forgot Password, Password Storage, Denial of Service). Fetched 2026-08-03.

---

## TL;DR verdict

- **Q1 — disclosure.** The vague/specific line is drawn by *who is asking*, not
  by *which endpoint*. OWASP requires generic responses on the **unauthenticated
  enumeration surfaces** — login, forgot-password (request), account creation —
  because the response is the oracle. A caller who already presents a valid
  single-use reset token, or a valid bearer token, has already proven account
  possession, so distinguishing "token dead" from "password rejected by policy"
  discloses nothing new. **Caveat: no primary source states that carve-out
  explicitly** — see the flagged note in §1.
- **Q2 — 410 for a dead single-use link.** `410` is **defensible but not
  clean-cut**. RFC 9110 gates 410 on the condition being "likely to be
  permanent", which a *consumed* token satisfies and an *expired* one satisfies
  once you never re-issue against the same URL. The RFC's own example set
  ("limited-time, promotional services") is the closest analogue to a
  time-boxed link. `400` is also defensible (the token is a client-supplied
  request parameter). **The spec does not settle this.** Consistency with the
  invite-accept route is a legitimate tiebreaker; 410 wins on that ground.
- **Q3 — 409 for a live invite already existing.** **Correct.** RFC 9110's 409
  is literally "a conflict with the current state of the target resource" where
  "the user might be able to resolve the conflict and resubmit". A live invite
  blocking a new one is exactly that. The RFC's *example* is a PUT versioning
  conflict, not uniqueness — so 409 is well-fitted by the definition, not by
  precedent in the text.
- **Q4 — 400, not 401, for wrong current password.** **Confirmed by RFC 9110.**
  401 is scoped to "valid authentication credentials for the target resource",
  and the credential in question is the `Authorization` header field. A password
  in a JSON body is request *content*, not request credentials. Two hard
  corroborations: 401 **MUST** carry a `WWW-Authenticate` challenge (which we
  would be lying about), and RFC 6750 maps 401 to `invalid_token` only. SPA
  consequence: a 401 refresh-interceptor would bounce a correctly-logged-in user
  to the login screen on a typo.
- **Q5 — timing.** Not a real oracle here. OWASP's constant-time requirement is
  attached to **account enumeration** on unauthenticated surfaces, and it is
  timing *between accounts*, not between failure reasons. On an authenticated
  change-password the attacker is the account holder, who already knows the
  account exists. OWASP's DoS sheet actively **recommends** the cheap-check-first
  ordering. Rate-limiting is required by NIST §5.1.1.2/§5.2.2 (auth attempts) and
  by OWASP Forgot Password (per-account submission limits).
- **Q6 — memory.** Real, and sourced. OWASP: too high a work factor "could be
  used by an attacker to carry out a denial of service attack by exhausting the
  server's CPU". 19 MiB × concurrent unauthenticated requests is the number to
  budget. **No primary source gives a concurrency formula** — RFC 9106 §4 tells
  you to size `m` to "the maximum amount of memory that each call can afford",
  which pushes the concurrency math onto us.

---

## Findings

### 1. How much should an authentication error tell the caller?

Source: OWASP Authentication Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html

- **The rule, stated generally:** "An application must respond (both HTTP and
  HTML) in a generic manner." OWASP applies this to three named features —
  **login, password recovery, and account creation**.
- **The threat is enumeration.** Detailed messages create a "discrepancy factor"
  that lets an attacker determine valid usernames. OWASP also flags the timing
  channel: "the processing time can be significantly different according to the
  case (success vs failure) allowing an attacker to mount a time-based attack."
- **The prescribed strings:**
  - Login — "Login failed; Invalid user ID or password."
  - Password recovery — "If that email address is in our database, we will send
    you an email to reset your password."
  - Account creation — "A link to activate your account has been emailed to the
    address provided."
  - Explicitly rejected examples include "Login for User foo: invalid password"
    and "Login failed; account disabled", which leak account existence.
- **Change-password prerequisites.** OWASP requires that the user "is
  authenticated with an active session" and that there is "Current password
  verification", so that "the legitimate user who is changing the password" can
  be confirmed.

Source: OWASP Forgot Password Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html

- **Request step must be flat:** "Return a consistent message for both existent
  and non-existent accounts," and "Ensure that responses return in a consistent
  amount of time to prevent an attacker enumerating which accounts exist."
- **On the redemption step the sheet is silent.** It specifies token properties
  (CSPRNG, "Long enough to protect against brute-force attacks", "Invalidated
  after they have been used", "expire after an appropriate period", "Stored in a
  secure manner, as discussed in the Password Storage Cheat Sheet") but gives no
  guidance on the user-facing message when a token is invalid or expired.

Source: OWASP Error Handling Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Error_Handling_Cheat_Sheet.html

- The generic-response mandate here is about **implementation disclosure**, not
  business outcomes: stack traces, framework versions ("Apache Tomcat/7.0.56"),
  install paths ("D:\app\index_new.php on line 188"), SQL text. The prescription
  is "when an unexpected error occurs then a generic response is returned by the
  application but the error details are logged server side for investigation, and
  not returned to the user", and to use 4xx for client errors and 5xx without
  "any content as part of the response that would reveal implementation details".
- A stable `error.code` like `RESET_TOKEN_EXPIRED` is not an implementation
  detail in this sense — it discloses nothing about stack, schema, or file paths.

Source: NIST SP 800-63B — https://pages.nist.gov/800-63-3/sp800-63b.html

- **NIST is silent on this question.** There is no requirement prohibiting
  disclosure of which factor failed, and no error-message guidance for failed
  authentication or for account recovery. NIST's contribution to DMI-77 is
  throttling (see §5), not disclosure.

> **Flagged gap — the spec does not settle this.** No fetched primary source
> states, in one sentence, that it is *safe* to be specific once the caller holds
> a valid single-use token. The conclusion follows from OWASP's own stated
> rationale rather than from its text: every generic-response rule OWASP writes
> is scoped to a surface an **anonymous** caller can poke (login, recovery
> request, registration), and the harm named is always **account enumeration**.
> A caller presenting a valid, unexpired, unconsumed reset token has already
> demonstrated control of the mailbox tied to that account; telling them
> `PASSWORD_POLICY_VIOLATION` versus `RESET_TOKEN_EXPIRED` grants them no
> information they could not obtain by other means. The residual risk is
> narrower than enumeration: an *invalid* token's response must not vary by
> whether the token was **never valid**, **already used**, or **expired**,
> because that distinction is observable by someone holding a stolen or guessed
> token. Collapsing all three into one code is the conservative reading, and it
> costs nothing in usability — the SPA renders the same "request a new link"
> screen for all three.

**Line for DMI-77:**

| Surface | Caller | Disclosure |
|---|---|---|
| `POST /auth/login` | anonymous | generic — one code, one message, flat timing |
| `POST /auth/forgot-password` (request) | anonymous | generic — always 202/200, never reveal existence |
| `POST /auth/reset-password` (redeem) | holds a token | specific — but collapse *all* bad-token cases into one code |
| `POST /auth/change-password` | authenticated | specific — session already proves identity |
| `POST /invites/accept` | holds a token | specific — same collapse rule as reset |

### 2. HTTP status for a dead/expired single-use link

Source: RFC 9110 §15.5 — https://www.rfc-editor.org/rfc/rfc9110

- **§15.5.1, 400 Bad Request:** "The 400 (Bad Request) status code indicates that
  the server cannot or will not process the request due to something that is
  perceived to be a client error (e.g., malformed request syntax, invalid request
  message framing, or deceptive request routing)."
- **§15.5.5, 404 Not Found:** "The 404 (Not Found) status code indicates that the
  origin server did not find a current representation for the target resource or
  is not willing to disclose that one exists. A 404 status code does not indicate
  whether this lack of representation is temporary or permanent; the 410 (Gone)
  status code is preferred over 404 if the origin server knows, presumably
  through some configurable means, that the condition is likely to be permanent."
- **§15.5.11, 410 Gone:** "The 410 (Gone) status code indicates that access to
  the target resource is no longer available at the origin server and that this
  condition is likely to be permanent. If the origin server does not know, or has
  no facility to determine, whether or not the condition is permanent, the status
  code 404 (Not Found) ought to be used instead."
  - And on its intended use: "The 410 response is primarily intended to assist
    the task of web maintenance by notifying the recipient that the resource is
    intentionally unavailable and that the server owners desire that remote links
    to that resource be removed. **Such an event is common for limited-time,
    promotional services** and for resources belonging to individuals no longer
    associated with the origin server's site. It is not necessary to mark all
    permanently unavailable resources as 'gone' or to keep the mark for any
    length of time -- that is left to the discretion of the server owner."
  - Cache note: "A 410 response is heuristically cacheable" (as is 404, §15.5.5).
    404 and 410 are heuristically cacheable; **400 is not** listed as such.

**Reading these against a consumed/expired reset token.**

Three honest observations, and a verdict:

1. **The RFC's 4xx frame is resource-shaped, ours is payload-shaped.** 410's text
   is about "the target resource" — a URL. Our token arrives in the **request
   body** of `POST /auth/reset-password`, and the target resource (the
   reset-password endpoint) is emphatically *not* gone; it will serve the next
   caller fine. Read strictly, 410 describes the request URI, and by that reading
   400 is the better-specified choice: the token is client-supplied input the
   server "will not process… due to something that is perceived to be a client
   error."
2. **But 410's permanence test is exactly right for a one-time token.** A
   consumed token is permanently dead by construction; an expired token is
   permanently dead provided we never revive it. RFC 9110 sets permanence as the
   discriminator between 404 and 410, and we *do* know the condition is
   permanent, which is the condition under which "410 (Gone) status code is
   preferred over 404". So on the axis the RFC actually cares about, we pass.
3. **"Limited-time, promotional services" is the RFC's own named analogue** for a
   thing that was deliberately available for a bounded window and is now
   intentionally unavailable. A 1-hour reset link is precisely that shape. This
   is the strongest textual support for 410, and it is an *example*, not a
   normative clause.
4. **404 is wrong for us.** It is defined as the case where the server does *not*
   know whether the condition is temporary or permanent — and it carries the
   "not willing to disclose that one exists" enumeration flavour, which is
   backwards here: we want a definite answer, and the caller already holds a
   token.

> **The spec does not settle this.** RFC 9110 nowhere addresses one-time tokens
> carried in a request body. Both 400 and 410 are compliant readings; 404 is not
> a good fit. Neither status is *incorrect* under RFC 9110, so this is a design
> choice, not a conformance question.

**Verdict:** **410 is acceptable and slightly better-motivated than 400** for a
consumed/expired single-use link, because permanence is the RFC's stated test and
we can satisfy it, and because "limited-time" services are the RFC's own worked
example. The decisive practical argument is the one DMI-77 already makes:
`/auth/reset-password` and `/invites/accept` are the same interaction, and the
SPA should not need two branches to render one "this link is no longer valid"
screen. **Two implementation conditions attach:**

- Never re-validate a previously-410'd token — permanence must be true, or the
  status is a lie.
- Set `Cache-Control: no-store` on these responses. 410 is *heuristically
  cacheable* per §15.5.11, and a cached 410 on a POST is unlikely to bite but the
  header costs nothing and removes the question.

### 3. HTTP status for "this address already has a live invite"

Source: RFC 9110 §15.5.10 — https://www.rfc-editor.org/rfc/rfc9110

- **409 Conflict, verbatim:** "The 409 (Conflict) status code indicates that the
  request could not be completed due to a conflict with the current state of the
  target resource. This code is used in situations where the user might be able
  to resolve the conflict and resubmit the request. The server SHOULD generate
  content that includes enough information for a user to recognize the source of
  the conflict."
- **The RFC's example is versioning, not uniqueness:** "Conflicts are most likely
  to occur in response to a PUT request. For example, if versioning were being
  used and the representation being PUT included changes to a resource that
  conflict with those made by an earlier (third-party) request, the origin server
  might use a 409 response…"

**Assessment.** The *definition* fits cleanly and the *example* does not, so be
precise about which is doing the work:

- "A live invite already exists for this address" is a conflict **with the
  current state** of the invite collection — the definitional clause, met.
- "The user might be able to resolve the conflict and resubmit" — met: revoke or
  let the existing invite expire, then resubmit. This clause is what separates
  409 from 400; a 400 body is malformed no matter how many times you send it,
  whereas this request becomes valid once state changes. That is the whole
  argument for 409 over 400, and it is a strong one.
- The "SHOULD generate content that includes enough information for a user to
  recognize the source of the conflict" clause is an argument *in favour* of
  DMI-77's machine-readable code — RFC 9110 wants the conflict explained, not
  obscured. Something like `INVITE_ALREADY_PENDING` plus the existing invite's
  expiry satisfies the SHOULD.

> **Note:** RFC 9110 does not name "resource already exists" as a 409 use case;
> the only worked example is a PUT/versioning conflict. So "409 for duplicate
> creation" is **canonical by definition, not by citation**. No fetched primary
> source lists it explicitly.

**Verdict:** **409 is correct**, and better than 400 — the request is
well-formed, and the failure is a state condition the caller can clear. Include
enough detail in the body to satisfy the SHOULD.

### 4. Wrong-current-password on change-password: 400 vs 401

Source: RFC 9110 §15.5.2 and §11.6.2 — https://www.rfc-editor.org/rfc/rfc9110

- **§15.5.2, 401 Unauthorized, verbatim:** "The 401 (Unauthorized) status code
  indicates that the request has not been applied because it **lacks valid
  authentication credentials for the target resource**. The server generating a
  401 response **MUST send a WWW-Authenticate header field** (Section 11.6.1)
  containing at least one challenge applicable to the target resource."
  - Continued: "If the request included authentication credentials, then the 401
    response indicates that authorization has been refused for those
    credentials."
- **§11.6.2 defines what "credentials" means:** "The 'Authorization' header field
  allows a user agent to authenticate itself with an origin server… Its value
  consists of **credentials** containing the authentication information of the
  user agent for the realm of the resource being requested." Formally:
  `Authorization = credentials`.
- **§11.1** frames the whole of HTTP authentication as "an extensible set of
  **challenge-response** authentication schemes" — a challenge in a response
  header, a credential in a request header. A JSON body field is outside that
  framework entirely.

Source: RFC 6750 §3.1 — https://www.rfc-editor.org/rfc/rfc6750

- **`invalid_token` → 401:** "The access token provided is expired, revoked,
  malformed, or invalid for other reasons." Recommended status **401**; the
  client may obtain a new token and retry.
- **`invalid_request` → 400:** "The request is missing a required parameter,
  includes an unsupported parameter or parameter value, repeats the same
  parameter, uses more than one method for including an access token, or is
  otherwise malformed." Recommended status **400**.
- **What triggers 401 in this spec:** the request "does not include
  authentication credentials or does not contain an access token that enables
  access to the protected resource."

**Assessment.** In `POST /auth/change-password` the request's authentication
credential is the bearer token in the `Authorization` header, and it is **valid**
— that is precisely why the endpoint reached its handler. `current_password` is a
body field: it is data the endpoint validates, indistinguishable in HTTP terms
from any other rejected field value. Two mechanical checks confirm 401 is wrong:

1. A 401 **MUST** carry `WWW-Authenticate`. What challenge would we send? There
   is no scheme by which the client can retry with a "better" `Authorization`
   header — the one it holds is already correct. Emitting a 401 without the
   header violates a MUST; emitting one with a fabricated challenge is worse.
2. RFC 6750 gives 401 exactly one meaning for bearer-token APIs:
   `invalid_token`. Our token is valid. The residual bucket is
   `invalid_request` → **400**.

403 is also wrong: §15.5.4's 403 is for a server that "understood the request but
refuses to fulfill it" on authorization grounds — the caller is fully authorized
to change their own password; they simply supplied a wrong value.

**Practical SPA consequence.** A standard React/axios setup installs a response
interceptor that treats **any** 401 as "the session died": attempt refresh, and
on failure clear auth state and redirect to `/login`. If wrong-current-password
returns 401, a user who fat-fingers their existing password gets logged out of a
perfectly healthy session, loses whatever they had on screen, and is handed a
login form instead of a field-level "current password is incorrect". Returning
400 keeps the error inside the form where it belongs. (See
`docs/research/axios-withcredentials-auth-scoping.md` for this repo's interceptor
shape.)

**Verdict:** **400** with a specific code (e.g. `CURRENT_PASSWORD_INVALID`).
Reserve 401 strictly for "the bearer token is missing/expired/revoked".

### 5. Timing — does short-circuiting before the Argon2id verify leak?

**What OWASP actually requires constant-time behaviour for.**

Source: OWASP Authentication Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html

- The timing warning is stated inside the **generic-error / enumeration**
  section: even with a generic error page, "the processing time can significantly
  differ" between valid and invalid accounts, and developers should implement
  consistent processing logic regardless of authentication outcome.

Source: OWASP Forgot Password Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html

- "Ensure that responses return in a consistent amount of time to prevent an
  attacker enumerating **which accounts exist**."

Both sources scope the requirement to the same thing: timing that differs
**between accounts** on an **anonymous** endpoint. Neither asks for uniform
timing between *failure reasons* for a caller who is already authenticated.

**Applying that to our four endpoints.**

- `POST /auth/change-password` — authenticated. The observer is the account
  holder; there is no account to enumerate that they do not already own. A
  cheap-fails-fast ordering (missing field, new password fails policy, new ==
  old) short-circuiting *before* the Argon2id verify reveals only which of *their
  own* inputs was bad, which is exactly what the response body says anyway. **No
  oracle.**
- `POST /auth/reset-password` — unauthenticated, but the discriminating lookup is
  a **token hash lookup**, not a password comparison. Look the token up first; if
  it is absent/used/expired, return the single dead-link code without running
  Argon2. That path is fast and the fast path corresponds to "no valid token",
  which an attacker already knows because they made the token up. What matters is
  that the *three* dead-token sub-cases are indistinguishable in both body and
  timing — same code, same branch. (Token comparison itself: hash and compare
  digests; see `docs/research/opaque-token-generation-storage.md`.)
- `POST /auth/forgot-password` (request) — this is the one that **must** be
  timing-flat, per the Forgot Password sheet, because the response is the
  enumeration oracle.
- `POST /invites` / `POST /invites/accept` — invite *creation* is authenticated
  (admin), so the 409 timing is not an anonymous oracle. Invite *accept* follows
  the reset-password rule above.

**And OWASP explicitly endorses the cheap-first ordering.**

Source: OWASP Denial of Service Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html

- "Using validation that is cheap in resources first" — reduce impact as early as
  possible, with more CPU/memory/bandwidth-expensive validation performed
  afterwards. Also: "Avoid highly CPU consuming operations", and
  "Authentication as a means to expose functionality".

> **Note on the apparent tension.** OWASP asks for consistent timing (§Auth,
> enumeration) *and* for cheap validation first (§DoS, resource exhaustion).
> These do not actually conflict, because they apply to different surfaces:
> constant time on the anonymous enumeration endpoints, cheap-first everywhere
> else. Neither sheet states the reconciliation; the scoping above is inferred
> from the threat each sheet names.

**Rate limiting — what is required, and where.**

Source: NIST SP 800-63B — https://pages.nist.gov/800-63-3/sp800-63b.html

- **§5.1.1.2:** "Verifiers SHALL implement a rate-limiting mechanism that
  effectively limits the number of failed authentication attempts that can be
  made on the subscriber's account as described in Section 5.2.2."
- **§5.2.2 Rate Limiting (Throttling):** "the verifier SHALL implement controls
  to protect against online guessing attacks. Unless otherwise specified in the
  description of a given authenticator, the verifier SHALL limit consecutive
  failed authentication attempts on a single account to no more than 100."
  Optional softeners: CAPTCHA, an increasing wait after failures ("e.g., 30
  seconds up to an hour"), IP allowlisting, risk-based/adaptive techniques. "When
  the subscriber successfully authenticates, the verifier SHOULD disregard any
  previous failed attempts for that user from the same IP address."

Source: OWASP Authentication Cheat Sheet

- Lockout counters should be "associated with the account itself, rather than the
  source IP address", to survive distributed attacks. The three tunables are
  threshold, observation window, and duration; "rather than implementing a fixed
  lockout duration (e.g., ten minutes), some applications use an exponential
  lockout, where the lockout duration starts as a very short period (e.g., one
  second), but doubles after each failed login attempt."

Source: OWASP Forgot Password Cheat Sheet

- "Implement protections against excessive automated submissions such as
  rate-limiting on a per-account basis, requiring a CAPTCHA, or other controls."

**Verdict:** our ordering leaks nothing actionable. Rate-limit **all four**
endpoints — `change-password` and `reset-password` are password-verification
surfaces covered by NIST §5.2.2; `invites` create and `invites/accept` need
limits for the DoS reason in §6, not for guessing.

### 6. Memory — Argon2id as a DoS surface on unauthenticated endpoints

Source: OWASP Password Storage Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html

- **Parameter menu (all "provide an equal level of defense, and the only
  difference is a trade off between CPU and RAM usage"):** m=47104 (46 MiB) t=1
  p=1; **m=19456 (19 MiB) t=2 p=1**; m=12288 (12 MiB) t=3 p=1; m=9216 (9 MiB) t=4
  p=1; m=7168 (7 MiB) t=5 p=1.
- **The DoS statement, verbatim:** "Though higher work factors make hashes more
  difficult for an attacker to crack, they will slow down the process of
  verifying a login attempt. **If the work factor is too high, the performance of
  the application may be degraded, which could be used by an attacker to carry
  out a denial of service attack by exhausting the server's CPU.**"
- **Target:** "calculating a hash should take less than one second", with the
  optimal settings found by experimentation on your own infrastructure.

Source: RFC 9106 §4 (Parameter Choice) — https://www.rfc-editor.org/rfc/rfc9106

- Recommended options: "Argon2id with t=1 iteration, p=4 lanes, m=2^(21) (2 GiB
  of RAM)" and "Argon2id with t=3 iterations, p=4 lanes, m=2^(16) (64 MiB of
  RAM)".
- Sizing procedure: "Figure out the maximum amount of memory that each call can
  afford and translate it to the parameter m", and separately "Figure out the
  maximum amount of time (in seconds) that each call can afford"; then "Run the
  scheme… using a different number of passes t. Figure out the maximum t such
  that the running time does not exceed the affordable time. If it even exceeds
  for t = 1, reduce m accordingly."

**Assessment for DMI-77.**

- OWASP's DoS sentence names **CPU**, not RAM. The RAM angle is ours to infer
  from the tradeoff table (m is memory, in KiB) and RFC 9106's "maximum amount of
  memory that **each call** can afford". **Neither source gives a
  concurrent-request formula** — RFC 9106 §4 does not address DoS or concurrent
  session handling at all. Flagging that as a genuine gap.
- The arithmetic we must do ourselves: at OWASP's 19 MiB / t=2 / p=1 floor, peak
  Argon2 RSS ≈ `19 MiB × (concurrent in-flight verifies)`. 32 simultaneous
  unauthenticated requests ≈ 608 MiB of transient allocation on top of the
  process baseline. On a small container that is an OOM, reached without any
  credential ever being valid.
- **Which endpoints are exposed.** `reset-password` and `invites/accept` are
  unauthenticated *and* each runs a hash (they hash the **new** password before
  storing it — the same 19 MiB cost as a verify). `change-password` is behind a
  bearer token, so an attacker must first hold a session. `POST /invites` is
  admin-only.
- **Mitigations, in the order the sources support them:**
  1. **Validate token first, hash last** — reject dead/expired tokens before any
     Argon2 call. This is OWASP DoS's "validation that is cheap in resources
     first" applied literally, and it means an attacker with no valid token can
     never make us allocate 19 MiB.
  2. **Validate the new password against policy before hashing it** — same
     principle, and it also makes the DMI-77 error codes fall out naturally
     (policy failure is decided pre-hash).
  3. **Rate-limit both unauthenticated endpoints** (OWASP Forgot Password:
     "rate-limiting on a per-account basis, requiring a CAPTCHA, or other
     controls"). Because there is no account context before token lookup, an
     IP/global limiter is what applies on these two.
  4. **Bound worker concurrency.** Keep the number of simultaneous Argon2 calls
     bounded (a semaphore, or the thread-pool size FastAPI uses for sync
     handlers) so `19 MiB × N` has a known ceiling. This step has **no primary
     source** — it is the direct consequence of RFC 9106's per-call budgeting
     applied to a concurrent server.
  5. **Stay at the OWASP floor**, not above it. 19 MiB / t=2 / p=1 is the
     documented minimum and the cheapest of the memory-heavy options; RFC 9106's
     64 MiB and 2 GiB recommendations are calibrated for key derivation, not for
     a public HTTP endpoint under load.

---

## What this means for DMI-77

1. **Distinct error codes for dead-link vs policy-failure: yes, ship them.** The
   caller already holds a valid token, so nothing is disclosed that
   account-enumeration guidance is protecting. **One condition:** collapse *all*
   bad-token cases — never issued, already consumed, expired — into a **single**
   code and a single code path, so a token guesser cannot tell "wrong token" from
   "real but spent token". Keep `login` and `forgot-password` (request) generic
   and timing-flat, per OWASP's named strings.
2. **`410 Gone` for the dead reset link: adopt it.** RFC 9110's permanence test
   is the operative one and we satisfy it; "limited-time, promotional services"
   is the RFC's own nearest analogue. Be honest that **the spec does not settle
   this** — 400 would also be compliant, and the deciding argument is parity with
   `/invites/accept`. Requirements: never revive a 410'd token, and send
   `Cache-Control: no-store` (410 is heuristically cacheable).
3. **`409 Conflict` for a live invite: correct, keep it.** Definitional match —
   "a conflict with the current state of the target resource" that "the user
   might be able to resolve… and resubmit". Honour the SHOULD by putting the
   reason (and ideally the existing invite's expiry) in the body. Note this is
   canonical by definition, not by an example in RFC 9110.
4. **`400`, not `401`, for wrong current password: confirmed.** 401 means the
   request "lacks valid authentication credentials", and credentials means the
   `Authorization` header (§11.6.2); a body field is not that. 401 would also
   force a `WWW-Authenticate` MUST we cannot honestly satisfy, and RFC 6750
   reserves 401 for `invalid_token`. Practical payoff: the SPA's 401 refresh
   interceptor stops logging people out over a typo.
5. **Timing: our ordering is fine, and preferred.** Constant-time is required for
   *anonymous enumeration* surfaces, not for distinguishing failure reasons to an
   authenticated or token-bearing caller. Short-circuiting cheap checks before
   the Argon2id verify is what OWASP's DoS sheet recommends. Add rate limiting on
   all four endpoints — NIST §5.2.2 (≤100 consecutive failures per account,
   exponential backoff), account-keyed per OWASP where an account is known,
   IP-keyed on the pre-token paths.
6. **Memory: order the work so unauthenticated callers cannot make us hash.**
   Token lookup → policy validation → *then* Argon2id. Stay at OWASP's 19 MiB /
   t=2 / p=1 with a sub-second target, and cap concurrent hash calls so peak is
   `19 MiB × cap`. OWASP's DoS warning is stated in terms of CPU exhaustion; the
   RAM-times-concurrency budget is an inference from RFC 9106 §4's per-call
   sizing procedure, which **does not address concurrency** — no primary source
   gives that formula.
