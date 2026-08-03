# Research: where a single-use token belongs in an emailed link

> **Scope.** Dmitri backend (Python 3.11+, FastAPI, SQLModel/Postgres) plus the
> React SPA on a separate origin. Question: path segment vs query string vs URL
> fragment for the token in an emailed invite/reset link, and what mitigations
> the sources actually prescribe.
>
> **Verified against the code, 2026-08-03:**
> - `backend/src/api/services/mailer.py:45-52` — `invite_link()` →
>   `{app_base_url}/invite/{token}` (**path segment**); `reset_link()` →
>   `{app_base_url}/reset-password?token={token}` (**query string**). Confirmed.
> - Tokens: 32-byte `secrets.token_urlsafe`, stored as a hash only
>   (`services/tokens.py`), single-use via `consumed_at`, `expires_at` enforced.
> - `backend/src/api/core/config.py:58,64` — `reset_token_ttl_minutes` default
>   **60**, `invite_ttl_hours` default **48**.
> - `backend/src/api/main.py:55-56` + `middleware.py` — the only middleware is
>   `NoContentCorsMiddleware` and `RequestIdMiddleware`. **No `Cache-Control`, no
>   `Referrer-Policy`, no CSP anywhere in `backend/src`.** Confirmed.
> - **Correction to the brief:** the SPA does not POST both tokens in a JSON
>   body. `backend/src/api/routers/invites.py:51` is
>   `POST /api/v1/invites/{token}/accept` — the invite token is a **path
>   parameter on the API request**, so it lands in the API's own access logs.
>   Reset does carry the token in the body. See §1.
> - `frontend/src/` contains **no** `/reset-password` or `/invite` route yet —
>   the landing pages are unbuilt, and no SPA hosting/header config exists in the
>   repo. This materially cheapens §6.
>
> Primary sources only: OWASP Cheat Sheet Series (Forgot Password, Session
> Management, Logging), NIST SP 800-63B, W3C Referrer Policy, RFC 3986,
> RFC 9110; MDN only for browser behaviour no spec pins down. Fetched 2026-08-03.

---

## TL;DR verdict

This round is **options with tradeoffs**, not prescriptions. What the sources
actually mandate is narrow:

- **Only one source names a placement at all.** OWASP Forgot Password says
  "Generate a token for the user and attach it in the **URL query string**" — a
  description of the standard pattern, not a SHOULD/MUST comparison against path
  or fragment. **No fetched source compares the three placements.** Anyone
  claiming a security ranking between path and query is going beyond the sources.
- **The single hard requirement in this area is the referrer mitigation.** OWASP
  Forgot Password: "Ensure that the reset password page adds the Referrer Policy
  tag with the `noreferrer` value in order to avoid referrer leakage." That is
  the only placement-adjacent instruction stated as an imperative — and it is
  aimed at the **page**, i.e. the SPA host, not our API.
- **The Referer threat is much smaller in 2026 than the folklore.** Browsers
  default to `strict-origin-when-cross-origin` (MDN), which sends origin-only
  cross-origin. Cross-origin analytics beacons and outbound links from the
  landing page therefore **already** leak no path and no query. What survives:
  same-origin subresource requests, and the landing page's own server logs.
- **Path vs query is cosmetic, security-wise.** The Referrer Policy `strip-url`
  algorithm removes fragment, username and password — **never** path or query, so
  both placements are equally exposed to every channel. Our inconsistency has no
  security significance at the email layer. It *does* have significance at the
  **API** layer, where the invite token is a path parameter (§1).
- **The fragment is genuinely stronger and genuinely unrecommended.** RFC 9110:
  "The target URI excludes the reference's fragment component" — it is never sent
  to any server, which kills the log and Referer channels outright. But **no
  primary source recommends it for emailed reset/invite links.** It is a real
  mechanism attached to a folkloric recommendation, and it carries real SPA costs
  (§2) plus an RFC-documented redirect hazard (§2).
- **Our TTLs have no source-based verdict.** OWASP requires expiry ("expire after
  an appropriate period") and gives no number. NIST 800-63B gives no number for
  this case. 60 minutes and 48 hours are neither endorsed nor condemned by any
  fetched source.
- **Migration is nearly free right now** because the landing pages do not exist.
  No source says anything about dual-format transitions.

---

## Findings

### 1. Path vs query vs fragment: the real exposure for our flow

**What the sources say about URLs and secrets, precisely.**

Source: RFC 3986 §7.5 Sensitive Information —
https://www.rfc-editor.org/rfc/rfc3986

> "URI producers should not provide a URI that contains a username or password
> that is intended to be secret. URIs are frequently displayed by browsers,
> stored in clear text bookmarks, and logged by user agent history and
> intermediary applications (proxies)."

Two honest caveats on this quote, because it is the one most often stretched:
its normative sentence is scoped to **userinfo** (`user:pass@host`), which the
next clause makes explicit ("A password appearing within the userinfo component
is deprecated"). The *rationale* clause — browsers display, bookmarks store,
history and proxies log — applies to the whole URI and is what actually
generalises. RFC 3986 §3.4 (query) and §3.5 (fragment) are purely syntactic and
draw **no** security distinction between components.

Source: OWASP Session Management Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html

> "The usage of specific session ID exchange mechanisms, such as those where the
> ID is included in the URL, might disclose the session ID (in web links and
> logs, web browser history and bookmarks, the Referer header or search
> engines)."

This is the canonical channel list. Note it says **"in the URL"** — undifferentiated
between path and query. It is also scoped to *session IDs*, a long-lived
credential, not a one-time token; the sheet's remedy ("A web application should
make use of cookies for session ID exchange management") is not available to an
emailed link, which has no prior browser state to attach a cookie to.

Source: OWASP Forgot Password Cheat Sheet —
https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html

> "Generate a token for the user and attach it in the URL query string. Send this
> token to the user via email."

and

> "URL tokens are passed in the query string of the URL, and are typically sent
> to the user via email."

This is the **only** fetched source that names a component for this exact use
case, and it names the **query string**. It is descriptive framing of the
standard pattern rather than a ranked recommendation — the sheet nowhere says
"query rather than path" or "not the fragment".

**Channel-by-channel, for our actual flow.** The SPA landing page is
`{app_base_url}/reset-password?token=…` or `{app_base_url}/invite/{token}`, on a
separate origin from the API.

| Channel | Path segment | Query string | Fragment | Fires for our SPA landing page? |
|---|---|---|---|---|
| Browser history / bookmarks | exposed | exposed | **exposed** | Yes — always, all three. The fragment is part of the history entry. |
| `Referer` on **cross-origin** subresources (CDN, fonts, analytics) | origin only | origin only | stripped | Yes, but harmless under the modern default — see §3 |
| `Referer` on **same-origin** subresources (our own JS/CSS chunks) | **leaked in full** | **leaked in full** | stripped | Yes — Vite's own chunks are same-origin. Goes to the SPA host's logs. |
| `Referer` on outbound link navigation from the page | origin only | origin only | stripped | Only if the landing page links out. Ours (unbuilt) need not. |
| SPA host access logs (the `GET` of the landing page itself) | **logged** | **logged** | **not sent** | Yes — this is the largest real channel |
| API access logs | **logged** (invite) / not sent (reset) | not sent | not sent | See below — this is our actual inconsistency |
| Shared/proxy caches | cacheable URL | cacheable URL | not part of cache key | Yes — no `Cache-Control` is set anywhere |
| Analytics payloads (`location.href`) | captured | captured | **captured** | Only if we add analytics. None today. |
| Copy-paste / forwarding by the user | exposed | exposed | exposed | Yes, all three equally |

The fragment column is where the folklore is right and also incomplete: it wins
decisively on every **server-visible** channel and wins **nothing** on
history, bookmarks, sharing, or client-side analytics.

**The API-side finding the brief missed.** `backend/src/api/routers/invites.py:51`
declares `POST /api/v1/invites/{token}/accept`. The invite token is therefore in
the **request line of the API call**, which means:

- it appears in Uvicorn/Gunicorn access logs, and in any reverse proxy, load
  balancer or CDN in front of the API;
- OWASP Logging Cheat Sheet
  (https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
  requires that **"Access tokens"** and **"Session identification values"** be
  "removed, masked, sanitized, hashed or encrypted" from logs — this is the one
  place in our stack where a live credential is currently written to a log line
  by default.

`POST /auth/reset-password` takes the token in the JSON body and has none of
this. So the invite/reset inconsistency is *cosmetic at the email layer* and
*substantive at the API layer* — the opposite of what the brief assumed. The
cheapest fix is orthogonal to the email-link question: move the accept token into
the request body so the two API routes match.

### 2. Is the fragment workable, and what does it cost?

**The mechanism is real and spec-backed.**

Source: RFC 9110 §7.1 — https://www.rfc-editor.org/rfc/rfc9110

> "A URI reference is resolved to its absolute form in order to obtain the
> 'target URI'. The target URI excludes the reference's fragment component, if
> any, since fragment identifiers are reserved for client-side processing"

Source: RFC 9110 §10.1.3 (Referer)

> "the user agent MUST NOT include the fragment and userinfo components of the
> URI reference"

Source: W3C Referrer Policy, `strip-url` — https://www.w3.org/TR/referrer-policy/

The algorithm removes **fragment, username and password** before a URL is used
as a referrer; with the origin-only flag it additionally removes path and query.
So the fragment is stripped from the referrer under **every** policy, including
`unsafe-url`.

That is three independent specs agreeing that a fragment never reaches a server.
No caveat needed on the mechanism.

**But no primary source recommends it here.** OWASP Forgot Password describes
only two delivery shapes — "URL tokens" in the query string, and "PINs" sent via
SMS or another mechanism. The fragment is not mentioned. Session Management does
not mention it. NIST 800-63B does not mention URLs at all (§4). **So: the
mechanism is spec-backed; the recommendation is folklore.** Say that plainly
rather than dressing the folklore in the specs' authority.

**Practical costs for our SPA, honestly stated.**

- **Router handling.** React Router in `BrowserRouter` mode does not surface the
  fragment as a route param; the landing component must read `location.hash`
  directly and parse it. Small, but it is bespoke code that the query-string form
  gets free from `useSearchParams`. (Inference from the router's API, not a
  source claim.)
- **The token still lives in `location.hash` and in the history entry.** MDN's
  `replaceState` docs (https://developer.mozilla.org/en-US/docs/Web/API/History/replaceState)
  confirm the scrub works — it "modifies the current history entry, replacing it
  with the state object and URL passed" and does not "cause the browser to load"
  anything — but you need the same `replaceState` call you would need for a query
  string. **The fragment does not save you the scrub.**
- **Redirects are a documented hazard.** RFC 9110 §17.11, *Disclosure of Fragment
  after Redirects*:

  > "when a redirect occurs and the original request's fragment identifier is
  > inherited by the new reference in Location (Section 10.2.2), this might have
  > the effect of disclosing one site's fragment to another site. If the first
  > site uses personal information in fragments, it ought to ensure that
  > redirects to other sites include a (possibly empty) fragment component in
  > order to block that inheritance."

  Concretely: any redirect on the way to the landing page — an apex-to-www
  normalisation, a trailing-slash rewrite, a hosting platform's canonical
  redirect — **carries the fragment along** unless the `Location` value itself
  carries a fragment. So a fragment token silently survives redirects we do not
  control, and the RFC's stated fix (append an empty fragment to every outbound
  redirect) is a config we would have to own on the SPA host.
- **Email client rewriting.** Link-scanning and click-tracking proxies rewrite
  emailed URLs. Whether a given proxy preserves a fragment is not specified by
  any source and varies by vendor — **unknown, and not resolvable from primary
  sources.** A fragment token that a scanner drops produces a link that lands on
  the page with no token at all.

**Net:** the fragment removes the server-log and Referer channels and removes
nothing else, at the cost of bespoke parsing, a redirect hazard we must configure
around, and an unquantifiable email-proxy risk. It is a legitimate option, not an
obvious win.

### 3. Does `Referrer-Policy` close the gap on its own?

**What OWASP mandates.** Forgot Password Cheat Sheet:

> "Ensure that the reset password page adds the Referrer Policy tag with the
> `noreferrer` value in order to avoid referrer leakage."

This is stated as an imperative, and it is the only imperative any fetched source
gives about URL-token exposure. Note it says the **page** — delivery is via a
`<meta name="referrer">` tag or the `Referrer-Policy` header, both of which are
emitted by whatever serves the SPA. **Our FastAPI app cannot set this**, and
verifiably does not set it today (`backend/src/api/middleware.py` adds only
`X-Request-Id` and CORS).

**How much the browser already does for us.** MDN, `Referrer-Policy`
(https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy):

> "This is the default policy if no policy is specified, or if the provided value
> is invalid (see spec revision November 2020). Previously the default was
> `no-referrer-when-downgrade`."

— referring to **`strict-origin-when-cross-origin`**, under which the browser
will:

> "Send the origin, path, and query string when performing a same-origin
> request."
>
> "For cross-origin requests send the origin (only) when the protocol security
> level stays same (HTTPS→HTTPS). Don't send the `Referer` header to less secure
> destinations (HTTPS→HTTP)."

> **Source conflict, flagged.** The W3C TR text at
> https://www.w3.org/TR/referrer-policy/ still states the default is
> `no-referrer-when-downgrade` ("This is a user agent's default behavior, if no
> policy is otherwise specified"). MDN documents the shipped behaviour as
> `strict-origin-when-cross-origin` since the November 2020 revision. The TR
> snapshot is stale relative to browsers; MDN is the accurate description of what
> actually happens. Both are cited above so the discrepancy is visible.

RFC 9110 §10.1.3 corroborates the direction as a UA-level SHOULD:

> "A user agent SHOULD NOT send a Referer header field if the referring resource
> was accessed with a secure protocol and the request target has an origin
> differing from that of the referring resource"

**So what actually remains after a strict policy?**

| Channel | Closed by `no-referrer` / `same-origin`? |
|---|---|
| Cross-origin subresource `Referer` | Already closed by the browser default; the policy makes it explicit |
| Same-origin subresource `Referer` (our own chunks) | `no-referrer` closes it; `same-origin` **does not** — it sends the full URL same-origin |
| Outbound link `Referer` | Already origin-only by default; `no-referrer` sends nothing |
| SPA host access log of the landing `GET` | **No.** The token is in the request line, before any policy applies |
| Browser history / bookmarks | **No** |
| User copy-pastes or forwards the link | **No** |
| Shared/proxy caches | **No** — that is `Cache-Control`'s job |
| Email client link-scanners fetching the URL | **No** — happens before any browser is involved |

The distinction between the two strict values matters for us: `same-origin`
still leaks the full URL to same-origin requests, and the SPA's own JS/CSS chunks
are same-origin. OWASP's prescribed value is `noreferrer`, the stronger one.

**Verdict for Q3:** a strict policy closes the referrer channel completely and
closes **nothing else**. It is necessary (OWASP states it imperatively) and
clearly insufficient. It is also, today, mostly redundant with the browser
default for the cross-origin case — the value it adds is against same-origin
subresource leakage and against browsers/proxies with non-default behaviour.

### 4. Do the sources differentiate path from query?

**No fetched source draws a security distinction.** The evidence:

- **RFC 3986** §3.3/§3.4 define path and query syntactically; §7.5's warning is
  about **userinfo**, and its rationale ("displayed by browsers, stored in clear
  text bookmarks, and logged by user agent history and intermediary
  applications") makes no component distinction.
- **OWASP Session Management** says "included in the URL" — undifferentiated.
- **W3C Referrer Policy** `strip-url` removes fragment, username and password.
  **Path and query are treated identically** — neither is ever stripped except
  together, via the origin-only flag. This is the strongest single piece of
  evidence that the two are equivalent: the one spec that mechanically
  discriminates between URL components puts path and query on the same side of
  the line.
- **RFC 9110 §10.1.3** likewise treats them together, suggesting intermediaries
  that want to reduce disclosure consider "truncating the query and/or path
  components" — a single remedy for both.
- **OWASP Forgot Password** names only the query string, but as the description
  of a pattern, never in contrast to a path segment.

**Assessment.** Our path/query inconsistency between `invite_link()` and
`reset_link()` is **cosmetic at the email layer** — every exposure channel in §1
treats them identically, and no source says otherwise. Two secondary
considerations that are real but not security-ranked by any source:

- The query form matches the only shape OWASP names, which is a weak argument for
  consistency in that direction.
- A path segment is marginally more likely to be treated as a cacheable static
  resource by a CDN with a default "cache by path, vary on query" rule — an
  inference about CDN configuration, **not a claim any source makes**, and moot
  until we set `Cache-Control` either way.

The inconsistency that *does* matter is the API-side one in §1, where the invite
token reaches server logs and the reset token does not.

### 5. Mitigations that keep the token in the URL — what we already satisfy

Source: OWASP Forgot Password Cheat Sheet. Token requirements:

> "Generated using a cryptographically secure random number generator"
> "Long enough to protect against brute-force attacks"
> "Invalidated after they have been used"
> "expire after an appropriate period"
> "Stored in a secure manner, as discussed in the Password Storage Cheat Sheet"

Plus: "Ensure that the URL is using HTTPS", "Don't rely on the Host header while
creating the reset URLs to avoid Host Header Injection attacks", the
`noreferrer` requirement from §3, "Implement protections against excessive
automated submissions such as rate-limiting on a per-account basis, requiring a
CAPTCHA, or other controls", and:

> "Don't automatically log the user in, as this introduces additional complexity
> to the authentication and session handling code, and increases the likelihood
> of introducing vulnerabilities."

Source: OWASP Session Management Cheat Sheet:

> "Session identifiers must never be cached. To prevent this, it is highly
> recommended to include the `Cache-Control: no-store` directive in responses
> containing session IDs."

Source: OWASP Logging Cheat Sheet: **"Session identification values"** and
**"Access tokens"** are in the list of data to be "removed, masked, sanitized,
hashed or encrypted" from logs.

**Scorecard against our code:**

| Mitigation | Source status | Us |
|---|---|---|
| CSPRNG token | MANDATED | ✅ `secrets.token_urlsafe(32)` |
| Long enough | MANDATED | ✅ 256 bits |
| Single-use | MANDATED | ✅ `consumed_at` |
| Expiry exists | MANDATED (no number) | ✅ `expires_at` |
| Hashed at rest | MANDATED | ✅ `services/tokens.py` |
| HTTPS link | MANDATED | ⚠️ depends on `app_base_url` config, not enforced in code |
| No Host-header-derived URL | MANDATED | ✅ built from `app_base_url` setting, not the request |
| `noreferrer` on the landing page | MANDATED | ❌ **absent** — and must be set by the SPA host, not the API |
| `Cache-Control: no-store` | "highly recommended" | ❌ **absent** — no middleware sets it |
| Token not in logs | MANDATED | ⚠️ **violated for invites** — token is in the API path (§1). Note `mailer.py:111` already carries a comment that nothing on those paths may log the token, so the intent exists |
| Rate limiting | MANDATED | Out of scope here; see `docs/research/auth-error-disclosure-and-invite-state.md` §5 |
| No auto-login after reset | MANDATED | ⚠️ **check**: `invites.py:59` returns `access_token, refresh_token, expires_in` from accept — that is auto-login on the invite path. OWASP's sentence is about the *reset* flow; whether it extends to invite acceptance is **not addressed by any fetched source** |
| `history.replaceState` scrub | **NOT mentioned by any fetched source** | ❌ absent (no landing page yet) |

Two entries deserve emphasis:

- **`history.replaceState` scrubbing is folklore too.** No fetched OWASP sheet,
  RFC or NIST document recommends it. MDN documents only the mechanism — that it
  replaces the current history entry and that the previous URL is not retained.
  It is a sound idea that the sources simply do not prescribe.
- **TTLs: no source-based verdict available.** OWASP requires expiry but says
  only "an appropriate period" and **"does not specify recommended token
  lifetimes"**. NIST SP 800-63B (https://pages.nist.gov/800-63-3/sp800-63b.html)
  gives no figure for this case either; its §6.1.1 temporary-secret language has
  no maximum validity, and its one adjacent clause is §5.1.3.1 — "Methods that do
  not prove possession of a specific device, such as voice-over-IP (VOIP) or
  email, SHALL NOT be used for out-of-band **authentication**" — which is about
  email as an *authentication factor*, not about account recovery links, and so
  does not govern our flow. **Therefore: our 60-minute reset TTL and 48-hour
  invite TTL are neither endorsed nor condemned by any primary source.** Anything
  I said about "minutes to an hour being standard" in
  `docs/research/opaque-token-generation-storage.md` was inference, and should not
  be re-read as a citation. What is defensible without a source: exposure is
  proportional to window × channels, so the 48-hour invite is 48× the reset's
  exposure window on every channel in §1 — a reason to be more careful with the
  invite link specifically, not a reason to claim 48h is out of spec.

### 6. Migration and compatibility

**No fetched source addresses this at all.** OWASP, NIST, RFC 3986 and RFC 9110
say nothing about changing an emailed link format or supporting two forms during
a transition. Everything below is mechanical reasoning about our code, flagged as
such.

- **Links already in inboxes are the only compatibility surface**, and they are
  bounded by the TTL: 60 minutes for reset, 48 hours for invites. A format change
  that ships without dual support breaks, at worst, the links sent in the
  preceding 48 hours.
- **Right now that surface is empty.** `frontend/src/` has no `/reset-password`
  or `/invite` route, so no user has ever successfully followed one of these
  links in this codebase. **This is the cheapest moment this decision will ever
  be** — a change made before the landing pages exist costs one edit to
  `mailer.py` and zero compatibility work.
- **If dual support were ever needed**, the landing component can read the token
  from all three locations (`useParams`, `useSearchParams`, `location.hash`) and
  take whichever is present — a few lines, no backend change, since the backend
  never sees the link format. Retire the old readers after one max-TTL window.
- **Fragment adds one migration-specific wrinkle** not present for path/query:
  RFC 9110 §17.11's inheritance rule means a redirect from an old link shape to a
  new one carries any fragment through, so a "redirect old links to the new form"
  strategy interacts with fragments in a way it does not with paths or queries.

---

## What this means for DMI-77

### The two things the sources actually settle

1. **Set a strict referrer policy on the SPA landing pages.** OWASP Forgot
   Password states it imperatively; it is the only placement mitigation stated
   that way. Use `noreferrer` (OWASP's named value), not `same-origin` — the
   latter still leaks the full URL to our own same-origin chunks. **This must be
   configured wherever the SPA is served**, which today is nowhere in this repo.
   This is a real gap regardless of which option below you pick.
2. **Get the invite token out of the API request line.**
   `POST /api/v1/invites/{token}/accept` writes a live single-use credential into
   every access log in front of the API, and OWASP Logging requires access tokens
   be removed or masked from logs. Moving it to the request body makes it match
   `POST /auth/reset-password` and costs one route signature. **My read: this is
   the highest-value change in this note, and it is independent of the email-link
   question.**

### The placement decision — three fitted options

**Option A — standardise on the query string (`?token=…`) for both links.**

- *Cost:* one line in `invite_link()`; the invite landing page uses
  `useSearchParams` instead of `useParams`.
- *Buys:* matches the only shape OWASP names for this use case; one code path
  across both landing pages; no bespoke parsing.
- *Leaves open:* SPA-host access logs, browser history, bookmarks, forwarding,
  same-origin `Referer` (until the policy from #1 is set).
- *Best when:* you want to be able to point at OWASP for the shape and keep the
  frontend boring.

**Option B — standardise on the path segment (`/invite/{token}`) for both.**

- *Cost:* one line in `reset_link()`.
- *Buys:* nothing security-wise — §4 shows every channel treats path and query
  identically, and the one spec that discriminates between URL components
  (`strip-url`) puts them on the same side.
- *Costs beyond A:* diverges from the only shape OWASP names, and (inference, not
  sourced) is marginally more likely to trip a CDN's cache-by-path default.
- *Best when:* you specifically prefer the URL aesthetics. There is no security
  argument here in either direction.

**Option C — move both to the fragment (`#token=…`).**

- *Buys:* genuinely removes the two largest server-side channels — the SPA host's
  access log of the landing `GET`, and every `Referer`-borne leak including
  same-origin. Backed by three specs (RFC 9110 §7.1, §10.1.3; W3C `strip-url`).
- *Costs:* bespoke `location.hash` parsing; the RFC 9110 §17.11 redirect
  inheritance hazard, which requires appending an empty fragment to outbound
  redirects on the SPA host; unquantifiable behaviour through email link-scanners
  (**no source resolves this**); and it still does **not** remove the token from
  history, bookmarks, forwarding, or client-side analytics, so it does not save
  you the `replaceState` scrub.
- *Critically:* **no primary source recommends this for emailed reset links.** If
  we adopt it, we adopt it as a reasoned local decision, not on OWASP's or NIST's
  authority.

**My read (clearly separated from the sources).** The sources support A over B
weakly and support neither over C at all. Given that (i) the landing pages do not
exist yet so all three cost about the same today, (ii) C's advantage is real but
its email-scanner behaviour is unverifiable from primary sources, and (iii) the
mitigations in #1 and #2 above close more actual exposure than any placement
choice does — I would take **Option A**, and spend the saved effort on the
referrer policy, `Cache-Control: no-store`, and the invite-route body change. If
the threat model later prioritises the SPA host's access logs specifically (e.g.
logs shipped to a third-party aggregator), **C becomes the right call** and the
migration stays cheap because the token never crosses the backend boundary in
URL form.

### Standing gaps, stated as gaps

- **TTLs (60 min reset / 48 h invite): no source-based verdict exists.** OWASP
  mandates expiry and declines to give a number; NIST gives none for this case.
  Do not let a reviewer read either value as spec-compliant *or* non-compliant.
  The only defensible statement is proportional: the invite's window is 48× the
  reset's, so if either deserves tightening it is the invite.
- **`history.replaceState` scrubbing: not prescribed by any fetched source.**
  Sound, cheap, and folklore.
- **Auto-login after invite acceptance:** OWASP says "Don't automatically log the
  user in" for the *reset* flow; `invites.py:59` returns a token pair on accept.
  **No fetched source says whether that guidance extends to invite acceptance.**
  Worth a deliberate decision, not an assumed one.
- **`Cache-Control` on these responses:** Session Management's `no-store` line is
  "highly recommended", not a MUST, and is written about responses containing
  session IDs rather than about a landing page whose *URL* contains a token —
  a near-fit, not an exact one. We set no cache headers at all today.
