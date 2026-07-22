# Research: scoping Axios `withCredentials` to auth routes only

> **Source-domain note:** the official Axios docs host `axios-http.com`
> 301-redirects to `axios.rest` as of 2026-07-21. To avoid anchoring claims on
> a host whose provenance may change, every Axios claim below is cited against
> the authoritative repository source
> (`raw.githubusercontent.com/axios/axios/v1.x/README.md`), which is the docs'
> upstream. The `axios.rest` pages were cross-checked and agree.

**Question.** In a React SPA using one central Axios instance, what is the
security-soundest, least-footgun way to scope `withCredentials` (which attaches
the httpOnly refresh cookie) to ONLY the auth routes so the cookie never rides
on business/API endpoints — (A) set `withCredentials: true` per-request inside
the individual auth call functions, or (B) a centralized request interceptor
that inspects the URL and adds `withCredentials` when the path matches
`/auth/*`? And, secondarily, what is the correct, robust shape of a
single-flight 401→refresh response interceptor?

**Project constraints assumed.** In-memory short-lived JWT sent as
`Authorization: Bearer` on all business endpoints; long-lived refresh token in
an httpOnly cookie the backend scopes to `/api/v1/auth/*`; one Axios instance
with `baseURL = http://localhost:8000/api/v1`; CORS `allowCredentials: true`
with an explicit Vite dev origin; ADR rule: the cookie must never reach a
business endpoint (CSRF avoidance), everything else is pure Bearer.

---

## TL;DR verdict

**Use approach (A): set `withCredentials: true` explicitly per-request in the
three auth functions (login, refresh, logout).** Prefer the strongest form of
A — a dedicated Axios instance for auth with `withCredentials: true` as its
*instance default* — over sprinkling the flag on individual `.post()` calls, if
you want it in one place without an interceptor.

Reasoning, grounded in the sources:

- **The authoritative control is server-side, not `withCredentials`.** The
  refresh cookie carries `Path=/api/v1/auth`. Per MDN/RFC 6265 path-matching,
  the browser will not attach that cookie to `GET /api/v1/hosts` regardless of
  `withCredentials`, because the path does not match. `withCredentials` is the
  *client-side* complement; the cookie `Path` attribute is the real, browser-
  enforced guarantee. Both should exist (defense in depth).
- **A fails closed; B's failure mode fails open and silently.** If you forget
  the flag on a new auth call under A, refresh simply doesn't send the cookie
  and auth breaks loudly and immediately. Under B, a URL-matching bug that
  *over-matches* (`/authors`, `/oauth`, a query string, an absolute URL)
  silently attaches credentials to a business endpoint — a latent violation of
  the ADR that is masked by the cookie `Path` scoping until the day someone
  also loosens the `Path`. Over-matching is the dangerous direction and it is
  invisible.
- **Three call sites do not justify an abstraction.** `withCredentials`
  defaults to `false` (Axios README; MDN `XMLHttpRequest.withCredentials`), so
  the instance default already keeps business endpoints clean. Per-request
  config wins the Axios merge precedence, so `withCredentials: true` on the
  auth calls is exact and local. This is the "Simplicity First / no
  single-use abstraction" path.
- **For the 401→refresh interceptor:** a module-scoped single-flight promise,
  a per-request `_retry` guard, an explicit exclusion of the refresh/login
  endpoints from the refresh logic, and rewriting the `Authorization` header
  before retry. Miss any one and you get an infinite loop, a refresh storm, or
  a retry replaying the stale token.

---

## Findings

### 1. `withCredentials` semantics and default

- **Default is `false`.** Axios README request-config table: `withCredentials:
  false, // default` — "indicates whether or not cross-site Access-Control
  requests should be made using credentials. This only controls whether the
  browser sends credentials." —
  https://raw.githubusercontent.com/axios/axios/v1.x/README.md
- **Same underlying flag, same default, at the platform level.** MDN: "The
  default is `false`." "cross-site `Access-Control` requests should be made
  using credentials such as cookies, authentication headers or TLS client
  certificates." "Setting `withCredentials` has no effect on same-origin
  requests." —
  https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest/withCredentials
- **Consequence for scoping:** because the default is `false`, an instance with
  no `withCredentials` set already sends *no* credentials on business
  endpoints. Scoping is therefore an **opt-in on the few auth calls**, not an
  opt-out everywhere else. This is what makes A minimal.
- **`withCredentials` governs more than the refresh cookie.** MDN lists
  cookies, auth headers, and TLS client certs; the flag also controls whether
  the browser exposes a cross-origin response body at all (see §4). So
  "credentials on a business endpoint" is broader than just the one cookie —
  another reason to keep the flag off everywhere it isn't needed.

### 2. The real guarantee is the cookie `Path`, not `withCredentials`

- **Path-match is browser-enforced.** MDN `Set-Cookie`: the `Path` attribute
  "Indicates the path that _must_ exist in the requested URL for the browser to
  send the `Cookie` header." For `Path=/docs`, requests to `/docs`, `/docs/`,
  `/docs/Web` match; `/`, `/docsets`, `/fr/docs` do **not**. —
  https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie
- **Therefore:** with the refresh cookie set to `Path=/api/v1/auth`, the
  browser does not send it to `/api/v1/hosts` *even if `withCredentials: true`
  were set globally*. The cookie-leak question the ADR cares about is settled
  server-side. `withCredentials` scoping is the client-side second barrier, and
  it is what stops *other* domain cookies / TLS certs from riding along and
  keeps the intent legible at the call site.
- **`HttpOnly` is orthogonal but relevant:** MDN: `HttpOnly` "Forbids
  JavaScript from accessing the cookie… Note that a cookie… created with
  `HttpOnly` will still be sent with JavaScript-initiated requests, for example
  … `fetch()`. This mitigates … XSS." So the SPA cannot read the refresh
  token, but Axios/`fetch` still transmits it when path- and credential-
  conditions are met — exactly the design here. (same MDN Set-Cookie page)
- **`SameSite` is defense-in-depth, not the CSRF defense** (see §5).

### 3. Config-merge precedence makes A exact and B unnecessary

- **Merge order, low→high precedence:** Axios merges "library defaults from
  `lib/defaults/index.js`, the instance defaults property, and the request
  config argument. Later values take precedence over earlier ones." —
  https://raw.githubusercontent.com/axios/axios/v1.x/README.md
- **What this buys A:** instance default `withCredentials` is (unset →) `false`;
  a per-call `client.post('/auth/refresh', body, { withCredentials: true })`
  overrides it for that one request only. No other request is affected. This is
  the entire mechanism — no interceptor, no URL parsing.
- **Strongest form of A — a dedicated auth instance:** create
  `authClient = axios.create({ baseURL, withCredentials: true })` and
  `apiClient = axios.create({ baseURL })` (withCredentials `false` by default).
  The three auth functions use `authClient`; everything else uses `apiClient`.
  The flag then lives in exactly one place (instance default) with zero
  per-call repetition and zero URL matching. This satisfies "one place" DRY
  concerns without B's fragility. (README "Creating an instance" +
  precedence, same source.)

### 4. CORS-with-credentials preconditions (both A and B need these)

- **Browsers send no credentials cross-origin by default.** MDN CORS: "By
  default, in cross-origin `fetch()` or `XMLHttpRequest` calls, browsers will
  _not_ send credentials." Setting `withCredentials`/`credentials:'include'` is
  what opts in. —
  https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS
- **The server must echo an explicit origin, never `*`.** MDN CORS, credentialed
  requests: the server "**must not** specify the `*` wildcard for the
  `Access-Control-Allow-Origin` response-header value, but must instead specify
  an explicit origin." And `Access-Control-Allow-Credentials: true` "indicates
  whether or not the response to the request can be exposed when the
  `credentials` flag is true"; if that header is absent "the response is
  ignored by the browser and not returned to web content." (same MDN CORS page)
- **Project fit:** `localhost:8000` (API) vs the Vite dev origin (e.g.
  `localhost:5173`) differ in port, so these are cross-origin requests and the
  above applies. The backend's `allowCredentials: true` + explicit origin is
  correct and necessary for `/auth/*`. It does **not** force credentials onto
  business endpoints — the browser only sends them when the *client* sets
  `withCredentials` (which under A/B it does only for auth).

### 5. Why the Bearer-everywhere design is CSRF-immune (validates the ADR)

- **CSRF exists because cookies are auto-attached.** OWASP CSRF Prevention
  Cheat Sheet: "Since browser requests automatically include all cookies
  including session cookies, this attack works unless proper authorization is
  used." —
  https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
- **A header the browser does not auto-send is the fix.** OWASP: "it is more
  secure to insert the CSRF token in a custom HTTP request header via
  JavaScript than adding a CSRF token in the hidden field form parameter,"
  because "requests with custom headers are automatically subject to the
  same-origin policy." The `Authorization: Bearer` header is exactly such a
  script-set, non-auto-attached header — an attacker's forged cross-site
  request cannot add it. (same OWASP page)
- **`SameSite` is not a substitute.** OWASP treats SameSite as "a
  defense-in-depth control [that] does not replace a proper CSRF defense in
  most deployments." (same OWASP page) So the ADR's posture — Bearer for
  business endpoints (structurally CSRF-immune), cookie only for the tiny
  `/auth/*` surface — is the recommended shape, and keeping `withCredentials`
  off business endpoints preserves that immunity.

### 6. Approach A vs B — direct comparison

| Axis | (A) per-request / dedicated auth instance | (B) URL-matching request interceptor |
|---|---|---|
| **Correctness** | Exact: request config overrides instance default (§3). Only the 3 auth calls carry the flag. | Depends on a URL predicate against `config.url` — which in a request interceptor is the *unmerged* relative path, separate from `config.baseURL`. Must handle query strings, absolute URLs, case. |
| **Security exposure** | Minimal, static surface. Flag visible at the call site. | A substring/regex bug that over-matches (`/authors`, `/oauth`, `/api/v1/hosts?tab=auth`) attaches credentials to a business endpoint — an ADR violation masked by cookie `Path` (§2) until `Path` is ever loosened. Fails **open**, silently. |
| **Failure direction** | Forgetting the flag → cookie not sent → auth breaks immediately and loudly (fail **closed**). | Under/over-match both possible; the over-match is silent and dangerous. |
| **Maintainability / footgun** | 3 call sites, or 1 instance default. No hidden control flow. Matches "Simplicity First — no single-use abstraction." | Centralized/DRY, but adds implicit behavior far from the call site, plus a matching function that must be kept correct and tested against every new route name forever. More code + more test surface for 3 call sites. |
| **When B would win** | — | Only if auth endpoints were numerous and dynamically named such that per-call/instance selection were genuinely unwieldy. Not the case here. |

- **Interceptor mechanics confirm B's fragility.** A request interceptor's
  success handler "receives the `config` object and must return it (potentially
  modified)"; Axios has not yet merged `baseURL` into `config.url` at that
  point, so a naive `config.url.includes('/auth')` both misses the `baseURL`
  and matches `/authors`/`/oauth`. Getting B right requires anchored matching
  and normalization — effort spent solving a problem A does not have. —
  https://raw.githubusercontent.com/axios/axios/v1.x/README.md (Interceptors)

**Recommendation for this project:** approach **A**, in its dedicated-instance
form. Keep the server-side `Path=/api/v1/auth` on the refresh cookie as the
authoritative control, and treat client-side `withCredentials` scoping as the
second, legible barrier. Do not introduce interceptor B for credential
scoping.

---

## Secondary: the single-flight 401→refresh response interceptor

**Goal shape.** On a 401 from a business call: perform *exactly one*
`POST /auth/refresh`; concurrent 401s await the *same* in-flight refresh
promise (not N refreshes); retry each original request *once* with the new
token; on refresh failure, clear in-memory state and redirect to `/login`.

### Interceptor contract (from the docs)

- **Response interceptor signature.** `instance.interceptors.response.use(
  onFulfilled(response) => response, onRejected(error) => Promise.reject(error)
  )`; the error handler fires for "status codes outside the 2xx range." —
  https://raw.githubusercontent.com/axios/axios/v1.x/README.md (Interceptors)
- **Retrying = returning a new request promise from the error handler.**
  Returning `client(config)` from `onRejected` makes the original awaited call
  resolve with the retried result; returning `Promise.reject(error)` propagates
  the failure. (same source)
- **Recovery must be on the same instance**, so the retried request re-runs the
  *request* interceptors (re-attaching the fresh `Authorization`). Execution
  order: request interceptors LIFO, response interceptors FIFO. (same source)

### Correct robust shape (pseudocode)

```js
let refreshPromise = null;               // module scope = single-flight gate

apiClient.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;   // guard: network errors have no .response

    // Only handle 401s, and never try to refresh the refresh/login calls themselves.
    if (status !== 401 || original._retry || isAuthEndpoint(original.url)) {
      return Promise.reject(error);
    }
    original._retry = true;                  // one retry per request, ever

    try {
      // First 401 starts the refresh; concurrent 401s await the SAME promise.
      refreshPromise ??= authClient
        .post('/auth/refresh')               // withCredentials via authClient (§3)
        .then((res) => res.data.accessToken)
        .finally(() => { refreshPromise = null; });

      const newToken = await refreshPromise;
      setAccessToken(newToken);              // in-memory store
      original.headers.Authorization = `Bearer ${newToken}`;  // rewrite stale header
      return apiClient(original);            // retry once
    } catch (refreshErr) {
      clearAccessToken();
      redirectToLogin();
      return Promise.reject(refreshErr);
    }
  }
);
```

### Pitfalls (each maps to a line above)

1. **Infinite retry loop.** Without the per-request `_retry` flag, a retry that
   also 401s re-enters the handler forever. The flag caps it at one retry.
2. **The refresh call itself 401ing → recursion.** If `/auth/refresh` (expired
   refresh token) is not excluded, its 401 triggers another refresh → loop.
   Exclude auth endpoints (`isAuthEndpoint`) and route a refresh 401 straight
   to logout. Use `authClient` (which need not carry this response interceptor)
   for the refresh call to keep it out of the loop entirely.
3. **Refresh storm / request queue.** N concurrent business calls 401 at once.
   A naive handler fires N refreshes (rotating the token N times — most
   rotations invalidate the others, cascading failures). The module-scoped
   `refreshPromise` makes call #2..N await the single in-flight refresh; the
   `.finally` reset re-arms the gate for the next expiry window. (This is the
   shared-promise form of the `axios-auth-refresh` subscriber-queue pattern;
   the shared promise is the minimal correct version.)
4. **Retrying with the stale token.** The original request's `Authorization`
   header still holds the expired token; you must overwrite
   `original.headers.Authorization` with the new token before
   `apiClient(original)`, or the retry 401s again.
5. **Non-401 / network errors.** `error.response` is `undefined` for network
   failures and timeouts — guard with `error.response?.status` so those reject
   normally instead of triggering a refresh.
6. **Losing the original request config.** Retry off `error.config` (the fully
   populated request config), not a hand-rebuilt request, so method, body,
   params, and other headers survive the retry.

### Notes

- Keep the refresh call on the credentialed `authClient` (§3), so the httpOnly
  cookie is sent to `/auth/refresh` and nowhere else, consistent with approach
  A. The business `apiClient` stays `withCredentials: false`.
- Redirect-on-failure should clear in-memory token state first, then navigate,
  so no further business call re-triggers the interceptor mid-teardown.

---

## Decision inputs (concrete)

| Input | Value | Source |
|---|---|---|
| `withCredentials` default | **`false`** ("This only controls whether the browser sends credentials") | axios v1.x README (request config) |
| Platform-level default | `XMLHttpRequest.withCredentials` "default is `false`"; no effect on same-origin | MDN XMLHttpRequest.withCredentials |
| Config merge precedence | lib defaults < **instance defaults** < **request config** (later wins) | axios v1.x README (config precedence) |
| Cookie send rule | browser sends cookie only if request path **path-matches** the cookie `Path` (`/docs` matches `/docs/Web`, not `/docsets`) | MDN Set-Cookie (Path) |
| `HttpOnly` | JS cannot read it, but `fetch`/XHR still transmit it; mitigates XSS | MDN Set-Cookie (HttpOnly) |
| Cross-origin credentials | not sent by default; server must return explicit origin (not `*`) + `Access-Control-Allow-Credentials: true` | MDN CORS (Requests with credentials) |
| CSRF root cause / fix | cookies auto-attached → CSRF; script-set custom headers (Bearer) are not auto-sent → immune; SameSite is defense-in-depth only | OWASP CSRF Prevention Cheat Sheet |
| Interceptor retry mechanism | error handler returning `client(config)` retries; returning `Promise.reject` propagates | axios v1.x README (Interceptors) |
| Single-flight gate | module-scoped shared `refreshPromise`, reset in `.finally` | derived; matches axios-auth-refresh subscriber pattern |
