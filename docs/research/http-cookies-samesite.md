# Research: HTTP cookies & SameSite for a browser SPA + API

> **Scope.** Dmitri backend (FastAPI) sets an `httpOnly` **refresh-token**
> cookie via `Set-Cookie`; a browser SPA (Vite dev on `localhost:5173`, prod
> served from its own domain) consumes the API through `fetch`/axios with
> `credentials: 'include'`. This note covers exactly what governs whether that
> cookie is **stored** by the browser and **sent back** on subsequent requests.
> Spec: `specs/016-sessions-auth-routes/`. Primary sources only (MDN, WHATWG
> Fetch, web.dev, Public Suffix List). Fetched 2026-07-23.

---

## TL;DR verdict

- **A refresh cookie for a *same-site* SPA+API works with `SameSite=Lax` (or
  even the browser default).** "Same-site" is decided by the **registrable
  domain (eTLD+1) + scheme**, and **the port is ignored**. So
  `localhost:5173` (SPA) ↔ `localhost:8000` (API) is **same-site**, and
  `app.example.com` ↔ `api.example.com` is **same-site**. A credentialed
  `fetch` to a same-site host carries a `Lax` cookie fine — Lax gates on
  *site*, not *origin*, so different subdomain/port does not strip it.
- **What breaks it: a genuinely cross-site deployment.** If the SPA and API are
  on different registrable domains (e.g. `dmitri-app.com` SPA →
  `dmitri-api.com` API), a `fetch`/XHR is a **cross-site subresource** request.
  `Lax`/`Strict` cookies are **not sent**, so the refresh cookie must be
  `SameSite=None` — which **requires `Secure`** (HTTPS). That rules out plain
  `http://` cross-site dev.
- **CORS and SameSite are independent gates.** CORS
  (`Access-Control-Allow-Credentials: true` + a non-wildcard
  `Access-Control-Allow-Origin` + `credentials:'include'`) decides whether JS
  may *send credentials and read the response*. SameSite decides whether the
  browser *attaches the cookie at all*. A request can satisfy CORS and still
  drop the cookie (cross-site + `Lax`), or attach the cookie and still have the
  response hidden from JS (CORS misconfigured). You must pass **both**.
- **Local HTTP dev caveat:** `SameSite=None` needs `Secure`, and `Secure`
  cookies are only accepted over `https:` — **except on `localhost`**, where
  the `Secure` requirement is ignored. So cross-site-style local dev over
  `http://localhost` can still set a `Secure` cookie; a non-localhost `http://`
  origin cannot.

---

## Findings

### 1. The `Set-Cookie` header and its attributes

Source: MDN — *Set-Cookie* —
https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie

The `Set-Cookie` response header is "used to send a cookie from the server to
the user agent, so that the user agent can send it back to the server later."

- **`HttpOnly`** — "Forbids JavaScript from accessing the cookie, for example,
  through the `Document.cookie` property. Note that a cookie that has been
  created with `HttpOnly` will still be sent with JavaScript-initiated
  requests, for example, when calling `XMLHttpRequest.send()` or `fetch()`.
  This mitigates attacks against cross-site scripting (XSS)." → **A refresh
  token in an `HttpOnly` cookie is unreadable by SPA JS but still rides along
  on `fetch` calls.**
- **`Secure`** — "Indicates that the cookie is sent to the server only when a
  request is made with the `https:` scheme (except on localhost)... Insecure
  sites (`http:`) cannot set cookies with the `Secure` attribute. The `https:`
  requirements are ignored when the `Secure` attribute is set by localhost."
- **`Path`** — "Indicates the path that _must_ exist in the requested URL for
  the browser to send the `Cookie` header." Subdirectories match: with
  `Path=/docs`, `/docs`, `/docs/`, `/docs/Web` match but `/`, `/docsets`,
  `/fr/docs` do not. If omitted, "defaults to the path component of the request
  URL."
- **`Domain`** — "Defines the host to which the cookie will be sent. Only the
  current domain can be set as the value, or a domain of a higher order, unless
  it is a public suffix." Host-only behavior: "If omitted, the cookie is
  returned only to the host that sent them (i.e., it becomes a 'host-only
  cookie'). This is more restrictive than setting the host name, as the cookie
  is not made available to subdomains of the host." Conversely, from the MDN
  Cookies guide: setting `Domain=mozilla.org` from `mozilla.org` makes the
  cookie "available on that domain and subdomains like
  `developer.mozilla.org`... **specifying `Domain` is less restrictive than
  omitting it.**"
- **`Expires`** — "Indicates the maximum lifetime of the cookie as an HTTP-date
  timestamp." "If unspecified, the cookie becomes a **session cookie**," removed
  when the client shuts down.
- **`Max-Age`** — "Indicates the number of seconds until the cookie expires. A
  zero or negative number will expire the cookie immediately." Precedence: "If
  both `Expires` and `Max-Age` are set, `Max-Age` has precedence."
- **`SameSite`** — "Controls whether or not a cookie is sent with cross-site
  requests: that is, requests originating from a different **site, including the
  scheme**, from the site that set the cookie. This provides some protection
  against certain cross-site attacks, including cross-site request forgery
  (CSRF)." Values below.

**`SameSite` values** (MDN *Set-Cookie*):

- **`Strict`** — "Send the cookie only for requests originating from the same
  site that set the cookie."
- **`Lax`** — "Send the cookie only for requests originating from the same
  site that set the cookie, and for cross-site requests that meet **both** of
  the following criteria: [1] The request is a top-level navigation... which
  causes the URL shown in the browser's address bar to change... This **would
  exclude, for example, requests made using the `fetch()` API, or requests for
  subresources from `<img>` or `<script>` elements, or navigations inside
  `<iframe>` elements.** [2] The request uses a safe method: in particular,
  this excludes `POST`, `PUT`, and `DELETE`."
- **`None`** — "Send the cookie with both cross-site and same-site requests.
  The `Secure` attribute must also be set when using this value."

**Default:** "Some browsers use `Lax` as the default value if `SameSite` is not
specified." (MDN Cookies guide: "If no `SameSite` attribute is set, the cookie
is treated as `Lax` by default.") web.dev notes Chrome's default-`Lax` is
slightly *more permissive* than an explicit `Lax`: MDN — "When `Lax` is applied
as a default, a more permissive version is used. In this more permissive
version, cookies are also included in `POST` requests, as long as they were set
no more than two minutes before the request was made." **Recommendation: set
`SameSite` explicitly rather than rely on the default.**

### 2. "Site" vs "origin" — registrable domain, ports, subdomains

Source: MDN — *Site* glossary —
https://developer.mozilla.org/en-US/docs/Glossary/Site

- **Site** = registrable domain (eTLD+1): "a site is determined by the
  *registrable domain* portion of the domain name. The registrable domain
  consists of an entry in the [Public Suffix List](https://publicsuffix.org/list/)
  plus the portion of the domain name just before it."
- **Origin** is stricter: "a more restrictive concept than the site,
  encompassing **the scheme, the whole domain, and the port**."
- **Port is IGNORED for site:** "These are considered the same site because the
  port number is ignored when determining the site: `https://example.com:8080`
  / `https://example.com`."
- **Scheme matters (schemeful same-site):** "This would make `http://vpl.ca`
  and `https://vpl.ca` different sites... A definition that considers the scheme
  is sometimes called a *schemeful same-site*. **This stricter definition is
  applied in the rules for handling `SameSite` cookies.**"
- **Subdomains share a site:** "These are the same site because the registrable
  domain of `mozilla.org` is the same: `https://developer.mozilla.org/...` /
  `https://support.mozilla.org/...`."
- **Different registrable domain = cross-site:** `developer.mozilla.org` vs
  `example.com` "are not the same site."

**Concrete cases for Dmitri:**

| Pair | Same origin? | Same site? | Why |
|---|---|---|---|
| `http://localhost:5173` ↔ `http://localhost:8000` | No (port differs) | **Yes** | Port ignored; same registrable domain + scheme |
| `https://app.example.com` ↔ `https://api.example.com` | No (host differs) | **Yes** | Same registrable domain `example.com` |
| `https://dmitri-app.com` ↔ `https://dmitri-api.com` | No | **No** | Different registrable domains → cross-site |
| `http://example.com` ↔ `https://example.com` | No | **No, for cookies** | Schemeful same-site treats http/https as different |

### 3. When `SameSite=Lax` cookies ARE and ARE NOT sent

Sources: MDN *Set-Cookie* (above); web.dev — *SameSite cookies explained* —
https://web.dev/articles/samesite-cookies-explained

A `Lax` cookie is sent when **either** (a) the request is **same-site**
(same registrable domain + scheme — regardless of origin/port/subdomain), **or**
(b) it is a **cross-site top-level navigation using a safe method** (GET link
click, `document.location` assignment, or a GET form).

It is **NOT** sent when:

- The request is **cross-site AND a subresource** — i.e. `fetch`/XHR, `<img>`,
  `<script>`, `<iframe>` loads. web.dev: Lax is "❌ NOT sent on subresource
  requests (images, fetch, XHR)" cross-site, and "❌ NOT sent on POST requests
  from other sites."
- A cross-site `POST`/`PUT`/`DELETE`, even top-level (unsafe method).

**The load-bearing answer for the SPA question:** a `fetch`/XHR is a
subresource request, so the "top-level navigation" exception never applies to
it. But that exception only *matters cross-site*. **A same-site cross-*origin*
`fetch` (different subdomain, or different port like
`localhost:5173`→`localhost:8000`) is not a cross-site request at all, so the
`Lax` cookie IS attached** — the origin/port difference is invisible to
SameSite, which keys on *site*. This is the crux: **SameSite tests site, CORS
tests origin.**

### 4. CORS `credentials: include` vs SameSite — two independent gates

Sources: MDN — *Request.credentials* —
https://developer.mozilla.org/en-US/docs/Web/API/Request/credentials ;
MDN — *CORSNotSupportingCredentials* —
https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS/Errors/CORSNotSupportingCredentials

**Fetch `credentials`** (WHATWG Fetch, per MDN):

- `omit` — "Never send credentials in the request or include credentials in the
  response."
- `same-origin` — "Only send and include credentials for same-origin requests.
  **This is the default.**"
- `include` — "Always include credentials, even for cross-origin requests."
  Credentials = "cookies, TLS client certificates, or authentication headers."

> **Default trap:** `fetch`'s default is `same-origin`. A **cross-origin**
> request (which includes same-site-but-different-port like
> `5173`→`8000`, and different subdomains) **will not send cookies unless you
> set `credentials:'include'`.** axios needs `withCredentials: true`.

**Credentialed CORS server rules** (MDN):

- With the credentials flag set, the server **must not** use a wildcard:
  "The CORS request was attempted with the credentials flag set, but the server
  is configured using the wildcard (`"*"`) as the value of
  `Access-Control-Allow-Origin`, which doesn't allow the use of credentials."
- Fix is to "change the value of `Access-Control-Allow-Origin` to grant access
  to the origin from which the client is loaded" (a **specific** origin), and
  the server must return `Access-Control-Allow-Credentials: true`.

**The two gates are orthogonal:**

- **CORS** governs whether the browser lets **JavaScript** send credentials on
  a cross-origin request and read the response. It is about *origin* and about
  the *JS-visible response*.
- **SameSite** governs whether the browser **attaches the cookie** to the
  outgoing request in the first place. It is about *site*.
- Therefore: a cross-**site** `fetch` can be perfectly CORS-configured
  (`Allow-Credentials: true`, exact origin, `credentials:'include'`) and the
  browser will **still omit a `Lax` cookie** — CORS can't override SameSite.
  Conversely a cookie can be attached (same-site) yet the response blocked from
  JS if CORS is wrong. **For FastAPI, set `allow_credentials=True` with explicit
  `allow_origins` (never `["*"]` with credentials).**

### 5. `SameSite=None` REQUIRES `Secure` → implications for local HTTP dev

Sources: MDN *Set-Cookie* & Cookies guide; web.dev *SameSite explained*.

- MDN: for `SameSite=None`, "The `Secure` attribute must also be set when using
  this value." web.dev: "Cookies with `SameSite=None` must also specify
  `Secure`, meaning they require a secure context." A `None` cookie without
  `Secure` is rejected by the browser.
- `Secure` cookies are only stored/sent over `https:` — MDN: "Insecure sites
  (`http:`) cannot set cookies with the `Secure` attribute." So a **genuinely
  cross-site** deployment forces `SameSite=None; Secure`, i.e. **HTTPS on both
  ends**.
- **Localhost exception:** MDN — "The `https:` requirements are ignored when the
  `Secure` attribute is set by localhost." So `SameSite=None; Secure` **can** be
  set over `http://localhost` in dev, but **not** over any other plain-`http`
  origin (e.g. a LAN IP or a real `http://` staging host). Real cross-site
  staging/prod must be HTTPS.

### 6. CSRF: why Lax/Strict help, and residual risk

Source: MDN *Set-Cookie* / *Cookies* (SameSite "provides some protection
against ... cross-site request forgery (CSRF)"); web.dev *SameSite explained*.

- Classic CSRF relies on a cross-site request (a form auto-POST or an image GET
  from the attacker's page) **silently carrying the victim's cookies**.
  `SameSite=Strict`/`Lax` **withholds the cookie from cross-site subresource and
  unsafe-method requests**, so the forged request arrives unauthenticated. Lax
  specifically still allows cross-site **top-level GET navigation**, so it
  preserves normal "click a link into the app" UX while blocking cross-site
  POST/`fetch`.
- **Residual risk with `Lax`:** because Lax *does* send the cookie on
  cross-site **top-level GET navigations**, any **state-changing GET endpoint**
  remains CSRF-exploitable (an attacker can trigger a top-level GET). Mitigation:
  keep mutations on `POST`/`PUT`/`DELETE` (which Lax withholds cross-site).
  `Strict` closes even the top-level-GET gap but breaks "arriving from an
  external link already logged in."
- web.dev's standing caveat: "Neither `Strict` nor `Lax` is a complete solution
  for your site's security. Cookies are sent as part of the user's request and
  you should sanitize and validate them in the same way as any other user
  input." SameSite is a **defense-in-depth** layer, not a replacement for CSRF
  tokens where the threat model needs them (notably if any cross-site `None`
  cookie is in play, or for the residual GET vector).

---

## What this means for the Dmitri refresh cookie

**If the SPA and API share a registrable domain (recommended):** e.g. dev
`localhost:5173`→`localhost:8000`, prod `app.dmitri.com`→`api.dmitri.com` (or
same host under `/api`). These are **same-site**, so a refresh cookie set as:

```
Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=...
```

is **attached to the SPA's credentialed `fetch`** to the API — Lax does not
strip it because the request isn't cross-site (port/subdomain don't count).
Requirements: the SPA must send `credentials:'include'` (axios
`withCredentials:true`), and if the API host differs in origin (different port
or subdomain) FastAPI must set `allow_credentials=True` with the **exact** SPA
origin in `allow_origins` (not `*`). In pure local `http://localhost` dev,
`Secure` is tolerated; for real deployments both ends must be HTTPS for the
`Secure` flag. **`SameSite=Lax` is the right default here**, and it retains
CSRF protection against cross-site POST/`fetch`.

**What breaks it:** deploying the SPA and API on **different registrable
domains** (a truly cross-site split). Then the API `fetch` is a cross-site
subresource, `Lax`/`Strict` cookies are **not sent**, and you must switch to
`SameSite=None; Secure` — which mandates **HTTPS on both origins** (localhost
excepted), a specific-origin credentialed CORS config, and **reintroduces CSRF
exposure** (a `None` cookie rides all cross-site requests), so pair it with CSRF
tokens / origin checks. Prefer the same-site layout to avoid all of this.
</content>
</invoke>
