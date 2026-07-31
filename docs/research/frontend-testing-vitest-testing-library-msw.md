# Research: frontend testing with Vitest 4 + Testing Library + MSW 2 (React 19 / TS / Vite SPA)

> **Scope.** The stack pinned in `frontend/package.json`: `vitest@^4.1.10`,
> `@testing-library/react@^16.3.2`, `@testing-library/dom@^10.4.1`,
> `@testing-library/jest-dom@^7.0.0`, `@testing-library/user-event@^14.6.1`,
> `msw@^2.15.0`, `jsdom@^29.1.1`, `react@19.2.7`, `typescript@~6.0.2`,
> `@tanstack/react-query@^5.101.4`. The existing suite is two files —
> `frontend/src/api/client.test.ts` and `frontend/src/pages/LoginStub.test.tsx` —
> wired by `frontend/vitest.config.ts`, `frontend/src/test/setup.ts` and
> `frontend/src/test/mswHandlers.ts`. The test plan this research informs is
> `specs/020-frontend-vertical-slice-login-home/ARCHITECTURE.md` §7 (21 acceptance
> criteria across ~12 new test files).
>
> **Source discipline.** Every claim below is cited against the project that owns
> it: the Vitest repo/docs (pinned to the **v4.1.10 tag**, because `main` now
> documents v5 and several defaults differ), the `testing-library-docs` repo and
> the Testing Library packages' own source, `mswjs.io`, TanStack's docs repo,
> React's docs, MDN and the WHATWG/W3C specs. Where the only authority is a
> maintainer's blog, it is labelled as such and only used for guidance the
> official docs explicitly link to. Read 2026-07-28.

---

## TL;DR verdict

- **Keep jsdom.** Vitest 4 dropped the "experimental" tag from Browser Mode but its
  own *Why Browser Mode* page still says the feature "is still in its early stages,"
  "may not yet be fully optimized," and "can result in longer initialization times."
  `environment: 'jsdom'` remains a documented first-class option with no deprecation
  notice. Nothing in §7 needs a real browser.
- **Two real defects in the current setup, both caused by `globals` being false.**
  `frontend/vitest.config.ts` does not set `globals`, and Vitest's default is
  `false`. Consequently (a) React Testing Library's **auto-cleanup never registers**
  — RTL guards it behind `typeof afterEach === 'function'` — so every `render()` in a
  multi-test file will pile up in `document.body`; and (b) `waitFor`/`findBy*` cannot
  see Vitest fake timers, because DOM Testing Library's detector is
  `typeof jest !== 'undefined' && …`. (a) is currently masked because each of the two
  test files renders exactly once. §7 adds files with many renders per file; it will
  break there, as duplicate-element errors from `getByRole`/`getByText`.
  **Fix: add `cleanup()` to an explicit `afterEach` in `src/test/setup.ts`** (cheaper
  and more legible than flipping `globals: true`, and it keeps the explicit-import
  posture the suite already has).
- **MSW's maintainers explicitly discourage the assertion style §7 leans on.** Their
  *Avoid request assertions* page: "We highly discourage against such assertions as
  they represent implementation detail testing." The sanctioned exception is a
  one-way request with no UI consequence — which is exactly `POST /auth/logout`
  (AC 20). For that one case use `server.events.on('request:match', …)`, not a
  hand-rolled Axios interceptor counter. The existing
  `authClient.interceptors.request.use(...)` spies in `client.test.ts` and
  `LoginStub.test.tsx` are both implementation-detail assertions **and** leaks: an
  interceptor added inside a test is never ejected.
- **§7's AC 7 query is the wrong tool.** `container.querySelectorAll('[disabled]')`
  violates two rules the Testing Library org ships and enables by default
  (`no-container`, `no-node-access`), and it is *unsound* for the invariant it
  claims: an attribute selector misses `fieldset[disabled]` inheritance and misses
  `aria-disabled="true"` entirely. Assert `toBeEnabled()` over
  `screen.queryAllByRole(...)` plus an explicit `aria-disabled` check.
- **`retry: false` is mandatory for the per-test `QueryClient`**, in TanStack's own
  words: "The library defaults to three retries with exponential backoff, which means
  that your tests are likely to timeout if you want to test an erroneous query."
  The `gcTime: Infinity` advice in the same doc is **Jest-specific** and does not
  apply here.
- **The highest-leverage change for "stop writing low-value tests":** delete the
  planned per-component tests for pure presentational leaves (`ReviewItemCard`,
  `SignedInPlaceholder`, `HomeBlank`, `HomeError`) and let the page test cover them
  through the rendered output, and move AC 8's "no `jwt-decode` in `package.json`"
  out of Vitest into ESLint `no-restricted-imports`. A Vitest test that reads a
  config file asserts nothing about behaviour and fails at the wrong time.
- **`user-event` must be awaited and must be `setup()`.** All v14 APIs "always return
  a Promise" (v14.0.0 breaking-changes list), and Testing Library ships an ESLint rule
  (`await-async-events`) whose whole purpose is catching the un-awaited case. The
  repo already does this correctly.
- **Never combine fake timers with `user-event`/`waitFor` in this repo.** Use MSW's
  `delay()` in a per-test handler to create the in-flight window AC 3 needs, and
  `findBy*` to leave it. No `setTimeout`, no arbitrary `waitFor(…, {timeout})`.

---

## Findings

### 1. Vitest 4 — what actually changed, and what it means for authoring

**Prerequisites.** "Vitest 4.0 requires **Vite >= 6.0.0** and **Node.js >= 20.0.0**."
The repo satisfies both (`vite@^8.1.1`, `engines.node: 22.x`). —
https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/guide/migration.md

**Coverage is the biggest config-level change, and it is opt-in-shaped now.**
`coverage.all` and `coverage.extensions` were **removed**; v4 "defaulted to include
only covered files in the report," and the migration guide says: "When upgrading to
v4 it is recommended to define `coverage.include` in your configuration, and then
start applying simple `coverage.exclude` patterns if needed." If `coverage.include`
is left undefined, "coverage report will include only files that were loaded during
test run" — i.e. a file with no test that imports it is silently invisible.
Separately, V8 coverage now uses AST-based remapping (`v8-to-istanbul` is gone),
`coverage.ignoreEmptyLines` and `coverage.experimentalAstAwareRemapping` are removed,
and "It is expected for users to see changes in their coverage reports when updating
from Vitest v3." — same source.

**`exclude` was simplified and this is a live trap for this repo.** "By default,
Vitest now only excludes tests from `node_modules` and `.git` folders. This means
that Vitest no longer excludes: `dist` and `cypress` folders …". `frontend/dist/`
exists (gitignored build output). It currently holds only `index.html` and `assets/`,
so nothing matches the default test glob — but any future build artifact named
`*.test.js` would be collected. The migration guide's own preferred remedy is
`test.dir` ("use the `test.dir` option instead because it is more performant than
excluding files"). — same source.

**Mock/spy semantics moved.** `vi.spyOn` now supports constructors, and "all mocks
called with a `new` keyword construct the instance instead of calling `mock.apply`" —
so a mock implementation must use `function` or `class`, never an arrow function.
`vi.restoreAllMocks` "no longer resets the state of spies and only restores spies
created manually with `vi.spyOn`"; automocks are unaffected by it. `vi.fn()`'s default
mock name changed from `spy` to `vi.fn()`, which changes snapshot output.
`mock.invocationCallOrder` now starts at `1`. — same source. None of this bites the
current suite (it uses zero `vi.fn`/`vi.spyOn` — the network is mocked at the wire by
MSW, which is the better posture anyway; see §4 and §6).

**Defaults worth pinning down at v4** (they differ on `main`, which now documents v5 —
notably `clearMocks` flips to `true` in v5):

| Option | v4.1 default | Source |
|---|---|---|
| `globals` | **`false`** | https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/config/globals.md |
| `environment` | `'node'` | https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/config/environment.md |
| `clearMocks` | **`false`** | https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/config/clearmocks.md |
| `restoreMocks` | `false` | https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/config/restoremocks.md |

**Pools, reporters, deprecations.** `poolOptions` is gone (all options are top-level);
`maxThreads`/`maxForks` → `maxWorkers`; `singleThread`/`singleFork` →
`maxWorkers: 1, isolate: false`; `workspace` → `projects`; the `basic` reporter and the
`onCollected`/`onTaskUpdate`/`onFinished` reporter hooks were removed; and test options
as a **third** argument to `test()`/`describe()` are no longer supported
(`test('x', { retry: 2 }, fn)` is the surviving form; a bare trailing timeout number is
still fine). — same source.

**Browser Mode vs jsdom — what the team actually says.** Vitest 4 "removed the
experimental tag from Browser Mode" (https://vitest.dev/blog/vitest-4) and reworked
the provider API (`provider: playwright({…})` object instead of the string
`'playwright'`; `@vitest/browser` folded into the provider packages; context import
moved from `@vitest/browser/context` to `vitest/browser`). But the *Why Browser Mode*
page is unchanged in its hedging: simulated environments "only simulate a browser
environment and not an actual browser, which may result in some discrepancies" and can
produce "false positives or negatives," **while** browser mode "is still in its early
stages," "may not yet be fully optimized," may contain bugs, and "can result in longer
initialization times compared to other testing patterns." The team recommends
augmenting it with a standalone runner (WebdriverIO/Cypress/Playwright) rather than
replacing jsdom wholesale. — https://vitest.dev/guide/browser/why

The `environment` doc still lists `'jsdom'` as a supported first-class value with a
per-file `@vitest-environment` docblock override and no deprecation note; Browser Mode
appears only as a `::: tip`. **Read: jsdom remains the default recommendation for
component tests; browser mode is the escape hatch for things jsdom cannot do.**
https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/config/environment.md

What jsdom cannot do, from jsdom's own README: **layout** — "the ability to calculate
where elements will be visually laid out as a result of CSS, which impacts methods like
`getBoundingClientRects()` or properties like `offsetTop`" — and **navigation** — "the
ability to change the global object … when clicking a link or assigning
`location.href`." Both are "outside the current scope"; jsdom stubs them (zeros for
layout, a "not implemented" virtual-console error for navigation). —
https://github.com/jsdom/jsdom

**`globals`: the explicit-import posture is right, but it has a cost.** "By default,
`vitest` does not provide global APIs for explicitness." The same page carries the
warning that matters here: "*Note that some libraries, e.g., `@testing-library/react`,
rely on globals being present to perform auto cleanup.*" See §2 for exactly what
breaks. — https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/config/globals.md

**`expect` in v4.1.** Two additions worth knowing:
`expect.assert(cond)` (re-exported Chai `assert`) for **type narrowing**, which
`expect(...).to*` cannot do; and `expect.schemaMatching(schema)`, an asymmetric matcher
against any [Standard Schema v1](https://standardschema.dev/) implementation (Zod,
Valibot, ArkType). `expect.poll(fn)` retries the *assertion* until it passes — and
since Vitest 3, forgetting to await it fails the test. There is also an **experimental**
`toMatchAriaSnapshot` / `toMatchAriaInlineSnapshot` (v4.1.4+), which snapshots the
accessibility tree rather than the DOM: "This catches accessibility regressions:
missing labels, broken roles, incorrect heading levels … Even if the underlying HTML
structure changes, the assertion would not fail as long as content matches
semantically." —
https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/api/expect.md,
https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/guide/browser/aria-snapshots.md

### 2. Testing Library principles, queries, and act() under React 19

**The principle, verbatim.** "The more your tests resemble the way your software is
used, the more confidence they can give you." The three inclusion criteria: (1) "it
should deal with DOM nodes rather than component instances, and it should not encourage
dealing with component instances"; (2) "It should be generally useful for testing the
application components in the way the user would use it"; (3) "Utility implementations
and APIs should be simple and flexible." —
https://github.com/testing-library/testing-library-docs/blob/main/docs/guiding-principles.mdx

That is what "testing behaviour, not implementation" *means concretely*: assert on what
is in the accessibility tree and the visible text after a user-shaped interaction; never
on props, state, hook internals, CSS class names, DOM structure, or which functions were
called. The org encodes it as lint rules, which is the most citable form of the
guidance:

- **`no-container`** — "By using `container` methods like `.querySelector` you may lose
  a lot of the confidence that the user can really interact with your UI. Also, the
  test becomes harder to read, and it will break more frequently." Enabled in the
  `react` config.
- **`no-node-access`** — "Disallow direct access or manipulation of DOM nodes in favor
  of Testing Library's user-centric APIs," covering traversal (`closest`, `lastChild`)
  and direct actions (`.click()`, `.select()`). Notable carve-out: `focus()`/`blur()`
  are **not** reported, "because imperative usage … is recommended over
  `fireEvent.focus()`."
- **`prefer-screen-queries`** — use `screen`, or `within(subtree)` when scoping; only
  reach for the `render` return value for `rerender()`/`container`/`baseElement`.
- **`prefer-user-event`**, **`prefer-user-event-setup`**, **`await-async-events`**,
  **`await-async-queries`**, **`prefer-find-by`**, **`no-wait-for-multiple-assertions`**,
  **`no-wait-for-side-effects`**, **`no-unnecessary-act`**, **`prefer-presence-queries`**.
  — https://github.com/testing-library/eslint-plugin-testing-library (rules list and
  `docs/rules/*.md`)

**Query priority, as stated.** In order: (1) *Queries Accessible to Everyone* —
`getByRole` ("This should be your top preference for just about everything. There's not
much you can't get with this (if you can't, it's possible your UI is inaccessible)"),
then `getByLabelText`, `getByPlaceholderText` ("A placeholder is not a substitute for a
label. But if that's all you have, then it's better than alternatives"), `getByText`,
`getByDisplayValue`; (2) *Semantic Queries* — `getByAltText`, `getByTitle` ("The title
attribute is not consistently read by screenreaders"); (3) *Test IDs* — `getByTestId`:
"The user cannot see (or hear) these, so this is only recommended for cases where you
can't match by role or text or it doesn't make sense (e.g. the text is dynamic)." —
https://github.com/testing-library/testing-library-docs/blob/main/docs/queries/about.mdx

So `getByTestId` **is** legitimate, narrowly: dynamic/localised text, a container with
no role and no stable text (a chart, a canvas, a card wrapper you need `within()` on),
or an element whose role is `generic`. It is illegitimate as a shortcut past an element
that *has* a role and an accessible name — that is the case the priority list exists to
prevent.

A specific gotcha for the login screen: "the spec defines that `<input type="password" />`
has no implicit role. This means that in order to query this type of element we must
fallback to a less powerful query such as `ByLabelText`." — same source. (`ByLabelText`,
not `ByPlaceholderText`, which is where `LoginStub.test.tsx` currently sits.)

**get vs query vs find, from the summary table:**

| Query | 0 matches | 1 match | >1 matches | Retries (async) |
|---|---|---|---|---|
| `getBy…` | throws | element | throws | no |
| `queryBy…` | returns `null` | element | throws | no |
| `findBy…` | throws | element | throws | **yes** |
| `getAllBy…` | throws | array | array | no |
| `queryAllBy…` | returns `[]` | array | array | no |
| `findAllBy…` | throws | array | array | **yes** |

`queryBy` exists for one purpose: "This is useful for asserting an element that is
**not** present." `findBy` "methods are a combination of `getBy*` queries and
`waitFor`" and take `waitFor` options as the last argument. — same source.

**act() and React 19.** React's own guidance: "We recommend using `act` with `await` and
an `async` function. Although the sync version works in many cases, it doesn't work in
all cases … We will deprecate and remove the sync version in the future." Using `act`
requires `global.IS_REACT_ACT_ENVIRONMENT = true`, and "Libraries like React Testing
Library set this automatically for you." — https://react.dev/reference/react/act

React 19 moved `act` from `react-dom/test-utils` to `react` ("`ReactDOMTestUtils.act` is
deprecated in favor of `React.act`") and **removed every other `test-utils` export**:
"These utilities were uncommon, and made it too easy to depend on low level
implementation details of your components and React. In React 19, these functions will
error when called." `react-test-renderer` is deprecated in the same guide, which
recommends migrating to `@testing-library/react`. —
https://react.dev/blog/2024/04/25/react-19-upgrade-guide

RTL 16 is the version that makes this work: v16.0.0 moved `@testing-library/dom` to a
**peer dependency** (which the repo correctly declares) and v16.1.0 added React 19
support. — https://github.com/testing-library/react-testing-library/releases/tag/v16.0.0

**The practical rule about act warnings** is the one the lint rule states: "All Testing
Library utils are already wrapped in `act`. Most of the time, if you're seeing an `act`
warning, it's not just something to be silenced, but it's actually telling you that
something unexpected is happening in your test." Wrapping RTL utils, or an empty
callback, in `act()` is the wrong fix. —
https://github.com/testing-library/eslint-plugin-testing-library/blob/main/docs/rules/no-unnecessary-act.md

**How RTL wires act, and why `globals: false` matters.** RTL's `act-compat.js` wraps
every internal `act` call in `withGlobalActEnvironment`, which sets
`IS_REACT_ACT_ENVIRONMENT = true` around the call and restores it after — so `render()`
and `user.click()` are always in an act environment regardless of config. But `src/index.js`
registers the *global* act environment and, critically, **auto-cleanup** only when the
runner injects globals:

```js
// react-testing-library/src/index.js
if (typeof afterEach === 'function') {
  afterEach(() => { cleanup() })
} else if (typeof teardown === 'function') { … }

if (typeof beforeAll === 'function' && typeof afterAll === 'function') {
  beforeAll(() => { setReactActEnvironment(true) })
  …
}
```

— https://github.com/testing-library/react-testing-library/blob/main/src/index.js,
https://github.com/testing-library/react-testing-library/blob/main/src/act-compat.js

With `globals: false` neither branch runs. The docs say the same thing in prose:
cleanup "is called automatically if your testing framework … injects a global
`afterEach()` function into the testing environment. If not, you will need to call
`cleanup()` after each test. … Failing to call `cleanup` when you've called `render`
could result in a memory leak." —
https://github.com/testing-library/testing-library-docs/blob/main/docs/react-testing-library/api.mdx

The second-order effect is the one that will actually bite: without cleanup, the
previous test's tree is still in `document.body`, so `screen.getByRole('button', …)`
in test #2 finds two matches and throws.

### 3. `user-event` v14 — await, setup(), and when `fireEvent` is still right

**Why it must be awaited.** v14.0.0's breaking-changes list is explicit: "**APIs always
return a Promise.**" — https://github.com/testing-library/user-event/releases/tag/v14.0.0
The mechanism is the `delay` option: "Between some subsequent inputs like typing a
series of characters the code execution is delayed per `setTimeout` for (at least)
`delay` milliseconds. This moves the next changes at least to the next macro task and
allows other (asynchronous) code to run between events." Default `0`, not `null`. —
https://github.com/testing-library/testing-library-docs/blob/main/docs/user-event/options.mdx
A dropped promise means the interaction is still mid-flight when your assertions run,
and React state updates land outside any act scope. `await-async-events` is the lint
rule for it.

**`setup()` vs direct calls.** "We recommend invoking `userEvent.setup()` before the
component is rendered," in the test body or a small `setup(jsx)` helper — and
explicitly *not* in a `before`/`after` hook. Direct calls like `userEvent.click()`
"will trigger `setup` internally" and remain supported, but "this option exists to ease
the migration from v13 to v14, and for simple tests. We recommend using the methods on
the instances returned by `userEvent.setup()`." The reason `setup()` is better is state:
"Methods on this instance share one input device state, e.g. which keys are pressed" —
so `[ShiftLeft>]` followed by `user.click(el)` produces a click with `shiftKey: true`.
`setup()` also stubs `navigator.clipboard`, and `writeToClipboard` defaults to `true`
for instances but `false` for direct calls. —
https://github.com/testing-library/testing-library-docs/blob/main/docs/user-event/intro.mdx,
.../user-event/setup.mdx

**Difference from `fireEvent`.** "`fireEvent` dispatches *DOM events*, whereas
`user-event` simulates full *interactions*, which may fire multiple events and do
additional checks along the way." `fireEvent` is "a lightweight wrapper around the
browser's low-level `dispatchEvent` API"; a real click is
`mouseOver → mouseMove → mouseDown → focus → mouseUp → click`, and user-event "adds
visibility and interactability checks along the way … it factors in that the browser
e.g. wouldn't let a user click a hidden element or type in a disabled text box." The
DOM Testing Library events page carries the standing note: "Most projects have a few use
cases for `fireEvent`, but the majority of the time you should probably use
`@testing-library/user-event`." —
.../user-event/intro.mdx, .../dom-testing-library/api-events.mdx

**When `fireEvent` is still correct**, per the docs:

1. Interactions user-event does not model yet — "In these cases you can use `fireEvent`
   to dispatch the concrete events that your software relies on," with the caveat that
   "this makes your component and/or test reliant upon your assumptions about the
   concrete aspects of the interaction being correct."
2. Non-user-originated events: `scroll`, `animationEnd`, `transitionEnd`, a `message`
   from a worker, a synthetic `error` on an `<img>`.
3. `focus`/`blur` — and here the docs prefer **neither**: use imperative
   `element.focus()`, because "any assertion on fired focus events will fail if the
   element is not focusable." Same for keydown: focus the element, then
   `fireEvent.keyDown(document.activeElement)`. This is why `no-node-access`
   deliberately exempts `focus()`/`blur()`. —
   https://github.com/testing-library/testing-library-docs/blob/main/docs/guide-events.mdx

### 4. MSW v2 — handlers, overrides, unhandled requests, and what not to assert

**`http` + `HttpResponse`.** The namespace exposes `http.get/head/post/put/patch/delete/options`
plus `http.all()`; the resolver receives `{ request, params, cookies }`; paths accept
relative or absolute URLs, `:param` segments, and RegExp predicates; and each handler
takes an options object supporting `{ once: true }`. —
https://mswjs.io/docs/api/http

`HttpResponse` is "a drop-in replacement for the Fetch API Response designed to allow
for more convenient response declaration and support otherwise unavailable features,
like mocking response cookies," built "on top of the standard request and response
primitives." `HttpResponse.json(body, init)`, `HttpResponse.text()`, and
`new HttpResponse(body, init)` all mirror the Fetch constructor. —
https://mswjs.io/docs/api/http-response

**Network failure vs HTTP error — the distinction AC 4 is about.** `HttpResponse.error()`
is "a static method that creates a new network error response instance." It is not a
status code; it is the transport failing, which is what an offline browser produces and
what makes `error.response` `undefined` in Axios. Note the constraint: "neither
`HttpResponse.error()` nor `Response.error()` allow customizing the network error
response" — you get a generic failure, not a chosen message. — same source.

**Per-test overrides.** `server.use()` "prepend[s] request handlers to the current
server instance," and prepended handlers "persist … as long as the current Node.js
runtime exists" — which is precisely why `resetHandlers()` in `afterEach` is not
optional. The recommended lifecycle is the one `src/test/setup.ts` already implements:

```js
beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())   // "ensuring isolated network behavior"
afterAll(() => server.close())
```

For a fail-then-succeed sequence (AC 16's retry case) use the one-time form: with
`{ once: true }`, "only *the first* `GET /resource` request will receive the override
response. Any subsequent requests will use the initial handler as fallback." —
https://mswjs.io/docs/api/setup-server/use,
https://mswjs.io/docs/best-practices/network-behavior-overrides

**`onUnhandledRequest`.** Values and MSW's own descriptions: `"warn"` (**the default**) —
"Print a warning but perform the request as-is"; `"error"` — "Print an error and halt
request execution"; `"bypass"` — "Does not print anything and perform the request
as-is." A custom callback `(request, print) => {}` is also accepted, but "providing a
custom callback opts you out of the default behavior that ignores common static
assets" (restorable via `isCommonAssetRequest()`). —
https://mswjs.io/docs/api/setup-server/listen

MSW recommends `'error'` **for tests specifically**, and for a reason directly relevant
to §7: "To make sure your tested code doesn't perform any unknown HTTP requests, use the
`onUnhandledRequest` option … setting it to `'error'` to throw an error whenever MSW
encounters a request without a matching handler." —
https://mswjs.io/docs/recipes/request-assertions
`src/test/setup.ts:9` already does this. That single line is what makes AC 18's "no
request is issued while stepping" a real assertion rather than a hope.

**Request assertions: MSW says don't.** The page is literally titled *Avoid request
assertions*: "We highly discourage against such assertions as they represent
implementation detail testing and sway you into testing how your application is written
instead of what it does." The recommended alternative is to encode the contract in the
handler — return a 400 when a required field is missing — and then assert the UI's
reaction, which "aligns testing with production behavior." The stated exception:
"There are scenarios when a performed request has no indication in the application that
can be asserted. These are usually one-way requests against third-party services, like
analytics or monitoring," for which they point at the life-cycle events API. — same source.

**Life-cycle events, for that exception.** `server.events.on(...)` exposes
`'request:start'`, `'request:match'`, `'request:unhandled'`, `'request:end'`,
`'response:mocked'`, `'response:bypass'`, `'unhandledException'`, with listener payloads
like `({ request, requestId })` and `({ request, requestId, response })`, plus
`removeListener` / `removeAllListeners`. The documented uses are "transparently monitor
requests/responses" and "explicitly wait for a certain request/response." —
https://mswjs.io/docs/api/life-cycle-events

**Simulating a slow response** (AC 3's in-flight window): `await delay(1000)` inside the
resolver, or `delay('infinite')` to make the request "pend forever" — which is the
cleanest way to hold a screen in its loading state for the duration of an assertion.
Bare `delay()` applies a realistic 100–400 ms, but "this implicit delay is negated in
Node.js test environments to avoid impacting test performance." —
https://mswjs.io/docs/api/delay

**Typing.** HTTP handlers take four generics — `Params`, `RequestBodyType`,
`ResponseBodyType`, `Path` — so a handler's response body can be pinned to the
generated OpenAPI type and drift becomes a typecheck failure rather than a runtime
surprise. — https://mswjs.io/docs/best-practices/typescript

### 5. TanStack Query v5 components under test

TanStack's testing guide is short and prescriptive:

- **Per-test `QueryClient` inside a wrapper.** "Note that we provide a custom wrapper
  that builds the `QueryClient` and `QueryClientProvider`. This helps to ensure that
  our test is completely isolated from any other tests. It is possible to write this
  wrapper only once, but if so we need to ensure that the `QueryClient` gets cleared
  before every test, and that tests don't run in parallel otherwise one test will
  influence the results of others."
- **`retry: false`, and why.** "The library defaults to three retries with exponential
  backoff, which means that your tests are likely to timeout if you want to test an
  erroneous query. The easiest way to turn retries off is via the
  `QueryClientProvider`." The caveat: "this will only work if your actual `useQuery` has
  no explicit retries set. If you have a query that wants 5 retries, this will still
  take precedence, because defaults are only taken as a fallback."
- **`gcTime: Infinity` is Jest-only advice.** "If you use Jest, you can set the `gcTime`
  to `Infinity` to prevent 'Jest did not exit one second after the test run completed'
  error message." Not applicable to Vitest, and not needed.
- **Await the state transition, don't sleep.**
  `await waitFor(() => expect(result.current.isSuccess).toBe(true))` — and for a
  component (rather than a hook) the equivalent is `await screen.findBy…` on the text
  that only the success state renders.
- **`renderHook` comes from `@testing-library/react`** on React 18+;
  `@testing-library/react-hooks` "is no longer required."
- The guide's own *Further reading* link is TkDodo's *Testing React Query* — TkDodo is a
  TanStack Query maintainer and the article is endorsed from the official docs, which is
  the only reason it is cited here. Its load-bearing points restate the docs: create "a
  new `QueryClient` for each test," and sharing state across tests gives "unexpected and
  flaky results if you run your tests in parallel." —
  https://github.com/TanStack/query/blob/main/docs/framework/react/guides/testing.md,
  https://tkdodo.eu/blog/testing-react-query

**Testing the three states without flakiness**, composed from the above plus §4:

| State | How to get there | How to assert |
|---|---|---|
| loading | default handler + `await delay('infinite')` in a `server.use()` override | `screen.getByRole(...)` on the skeleton/disabled control — synchronous, because the request never resolves |
| error | `server.use(http.get(url, () => new HttpResponse(null, {status: 500})))`, client with `retry: false` | `await screen.findByText(/couldn't load/i)` + `expect(screen.queryByText(verdict)).not.toBeInTheDocument()` |
| success | the baseline handler in `mswHandlers.ts` | `await screen.findByText(...)` |

The error case is the one that *requires* `retry: false`: with the default three
retries and exponential backoff, the failure never surfaces inside `findBy`'s 1000 ms
window.

### 6. Valuable tests vs noise — the maintainers' own lines

This is the question the team cares most about, so here is the evidence, each item
traced to the project that owns the opinion.

**a. Don't assert implementation details — four independent statements of the same rule.**
Testing Library's guiding principle ("deal with DOM nodes rather than component
instances"); `no-container` ("you may lose a lot of the confidence that the user can
really interact with your UI … it will break more frequently"); `no-node-access`; and
MSW's "such assertions … represent implementation detail testing and sway you into
testing how your application is written instead of what it does." React 19's upgrade
guide removes `react-dom/test-utils` for the same stated reason: those utilities "made
it too easy to depend on low level implementation details."

**b. Over-mocking.** MSW's positioning is that the *network* is the seam worth mocking,
because a handler is a description of the contract that survives refactors of the client
code. TanStack's testing guide mocks the network (nock in the doc, MSW in the linked
article) rather than mocking `useQuery`. Mocking your own modules — `vi.mock('./api/client')`
— couples the test to the file layout and proves nothing about the request that is
actually sent. The current repo suite is already on the right side of this: it drives
**real** Axios instances against MSW.

**c. Snapshots.** Vitest's framing is narrow and worth quoting because it defines the
legitimate use: "Snapshot tests are a very useful tool whenever you want to make sure
the output of your functions does not change unexpectedly." *Functions*, not component
trees. The docs add that snapshots should be committed and reviewed like code, and that
CI fails on mismatch rather than auto-updating. A serialized React tree fails this test
on both counts: it changes on every cosmetic edit (so it gets `-u`'d without reading,
which converts the assertion into a rubber stamp), and it asserts nothing a human chose
to care about. Where a whole-tree assertion genuinely helps, v4.1.4's **experimental**
`toMatchAriaSnapshot` is the strictly better form — it snapshots the accessibility tree,
so "Even if the underlying HTML structure changes, the assertion would not fail as long
as content matches semantically." —
https://vitest.dev/guide/snapshot,
https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/guide/browser/aria-snapshots.md

**d. Trivial presentational components.** There is no doc page that says "don't test
`<Badge/>`," so the honest form of the argument is a derivation from the guiding
principle rather than a quotation: a component with no state, no branching and no
handlers has no *behaviour*, so a test of it can only assert its markup — which is
exactly what `no-container` calls low-confidence and change-fragile. The same output is
asserted for free, in a user-shaped way, by the page test that renders it. The value of
a test is the class of regression it can catch that no other test catches; for a props-in,
markup-out leaf, that class is empty.

**e. Config files.** A Vitest test that reads `package.json` runs in the wrong phase and
reports in the wrong place. Dependency and import constraints belong in ESLint
(`no-restricted-imports`) or in CI, where they fail at lint time with an actionable
message. This is the same "one changed line per request" discipline `.claude/CLAUDE.md`
§3 asks for, applied to the test suite.

**f. `waitFor` hygiene, since it is the most common source of slow-failing noise.**
`no-wait-for-multiple-assertions`: "If you use multiple assertions against the **same
asynchronous target** inside `waitFor`, you may have to wait for a timeout before seeing
a test failure, which is inefficient." `no-wait-for-side-effects`: don't put the *action*
inside the waiter — it will be re-run on every poll. `prefer-find-by`: `waitFor(() =>
screen.getByRole(...))` should just be `await screen.findByRole(...)`.

### 7. Cheap accessibility assertions worth automating

These cost nothing extra because they *are* the queries — choosing `getByRole` over
`getByTestId` makes the accessibility assertion a side effect of finding the element.

- **Role + accessible name in one query.** `getByRole('button', { name: /submit/i })` is
  "the top preference for just about everything"; if it cannot find the element, "it's
  possible your UI is inaccessible." By default `getByRole` respects
  https://www.w3.org/TR/wai-aria-1.2/#tree_exclusion — `aria-hidden` subtrees are
  invisible to it unless you pass `{ hidden: true }`. Roles "are matched literally by
  string equality, without inheriting from the ARIA role hierarchy." —
  https://github.com/testing-library/testing-library-docs/blob/main/docs/queries/byrole.mdx
- **Direct assertions**, when you already hold the element:
  `toHaveAccessibleName()` — "assert that an element has the expected accessible name.
  It is useful, for instance, to assert that form elements and buttons are properly
  labelled"; `toHaveRole('button')`; `toHaveAccessibleDescription()`;
  `toHaveAccessibleErrorMessage()`; `toHaveFocus()`; `toBeVisible()`. —
  https://github.com/testing-library/jest-dom/blob/main/README.md
  (v7.0.0's only breaking changes: "@testing-library/dom is now a required peer
  dependency. The minimum supported Node.js version is now 22." —
  https://github.com/testing-library/jest-dom/releases/tag/v7.0.0)
- **`aria-live` regions.** The testable invariant is structural, and MDN states it
  precisely: the live region "must be present in the DOM before content changes occur" —
  "The `aria-live` attribute is set on an **empty** element. When an update to the page
  occurs, the empty element with that `aria-live` attribute should be updated with a
  brief announcement." So the assertion is *not* "the announcement was announced"
  (jsdom has no screen reader); it is: the container with `aria-live="polite"` is in the
  document **before** the interaction, and the same node's text content changes after it.
  Values: `off` (default), `polite`, `assertive` — and "Avoid `assertive` unless
  interruption is imperative." —
  https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live
- **Focus order.** Assert with `toHaveFocus()` after `await user.tab()`. Two caveats:
  imperative `element.focus()` is the documented way to *set* focus in a test (and is
  exempt from `no-node-access`), and jsdom has **no layout**, so anything that depends on
  visual order or `getBoundingClientRect` is unavailable — tab order in jsdom follows DOM
  order and `tabindex`, which is the thing worth asserting anyway. —
  guide-events.mdx; https://github.com/jsdom/jsdom
- **"Nothing renders disabled."** `toBeDisabled()` "considers an element as disabled if
  the element is among the types of elements that can be disabled (`button`, `input`,
  `select`, `textarea`, `optgroup`, `option`, `fieldset`, and custom elements) and the
  `disabled` attribute is present. It will also consider the element as disabled if it's
  inside a parent `form` element that supports being disabled and has the `disabled`
  attribute present." And the caveat that matters: "This custom matcher does **not** take
  into account the presence or absence of the `aria-disabled` attribute
  ([#144](https://github.com/testing-library/jest-dom/issues/144))." `toBeEnabled()` is
  documented as the exact negation. —
  https://github.com/testing-library/jest-dom/blob/main/README.md

  Consequence: a complete "nothing is disabled" invariant needs **two** checks — the
  native one via `toBeEnabled()`, and an explicit `aria-disabled` check — and `getByRole`
  has no `disabled` filter option, so the set has to come from the role queries
  themselves (see §"What this means for Dmitri", item 3).

### 8. Async and flakiness

**`findBy` over `waitFor`** whenever you are waiting for an element: `findBy*` is
"a combination of `getBy*` queries and `waitFor`" and accepts the same options
(`await screen.findByText('text', queryOptions, waitForOptions)`); `prefer-find-by` is
the auto-fixable lint rule. Reach for `waitFor` only when the condition is not "an
element exists" — e.g. `await waitFor(() => expect(mockAPI).toHaveBeenCalledTimes(1))`. —
https://github.com/testing-library/testing-library-docs/blob/main/docs/dom-testing-library/api-async.mdx

**`waitFor` semantics you need to know to avoid writing it wrong:** "Returning *a falsy
condition is not sufficient* to trigger a retry, the callback must throw an error in
order to retry"; default `timeout` 1000 ms, default `interval` 50 ms (callback runs
immediately first); the default container is `document`, so "Make sure the elements you
wait for are descendants of `container`"; the MutationObserver watches
`{subtree, childList, attributes, characterData}` and re-runs the callback on any of
them. — same source.

**Never use an arbitrary timeout.** The failure mode of `await new Promise(r => setTimeout(r, 500))`
is that it is simultaneously too slow (paid on every green run) and too short (flakes on a
loaded CI box). Every wait in this suite has a *condition* available: an element appears
(`findBy`), an element disappears (`waitForElementToBeRemoved` — which throws
immediately if the element was never there: "The element(s) given to
`waitForElementToBeRemoved` are already removed"), or a query state flips
(`waitFor(() => expect(...))`). Raising `timeout` is a diagnosis, not a fix.

**Fake timers + user-event/`waitFor`: avoid in this repo.** Testing Library's own guide
says fake timers make "*all* of the code inside your test" use them, that you must
`runOnlyPendingTimers()` before `useRealTimers()`, and carries the note: "Combining fake
timers with `user-event` may cause test timeouts. Refer to the `advanceTimers` option to
prevent this issue" — i.e. `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`.
The options page adds: "You may find suggestions to set `delay: null` to prevent test
timeouts when using fake timers. That is not recommended, as it may cause unexpected
behaviour." —
https://github.com/testing-library/testing-library-docs/blob/main/docs/guides-using-fake-timers.mdx,
.../user-event/options.mdx

**But under Vitest there is a deeper problem than the `user-event` delay.** DOM Testing
Library detects fake timers like this:

```ts
// dom-testing-library/src/helpers.ts
function jestFakeTimersAreEnabled() {
  if (typeof jest !== 'undefined' && jest !== null) {
    return (setTimeout as any)._isMockFunction === true ||
           Object.prototype.hasOwnProperty.call(setTimeout, 'clock')
  }
  return false
}
```

— https://github.com/testing-library/dom-testing-library/blob/main/src/helpers.ts

The guard is `typeof jest !== 'undefined'`. Vitest exposes `vi`, not `jest`, so under
Vitest this **always returns `false`**, `waitFor`/`findBy*` take the real-timer path, and
their internal `setTimeout` is itself faked and never fires — the test hangs to the
5000 ms limit. This is a long-standing, well-reported interaction
(https://github.com/vitest-dev/vitest/issues/3117,
https://github.com/testing-library/react-testing-library/issues/1198); the circulating
workaround is `globalThis.jest = vi` in a setup file, which is a lie to a third-party
library and should be a last resort.

The clean alternatives, in order of preference:

1. **Don't fake time.** Produce the timing you need at the network layer with MSW's
   `delay()` / `delay('infinite')` (§4) and leave it with `findBy*`. This covers every
   async case in §7.
2. If a component genuinely owns a timer, test the *pure* time function separately
   (`src/lib/review.test.ts` is already the right home for the 3-day staleness boundary —
   pass the clock in as an argument and no fake timers are needed at all).
3. Only if 1 and 2 fail: fake timers plus `vi.waitFor` (Vitest's own waiter, which
   "automatically calls `vi.advanceTimersByTime(interval)`") or `expect.poll`, and
   `userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`. —
   https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/api/vi.md,
   https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/api/expect.md

---

## What this means for Dmitri

### 1. Add explicit `cleanup()` to `src/test/setup.ts` before writing any multi-test render file

`frontend/vitest.config.ts` sets `environment`, `setupFiles` and `env` but not `globals`,
so it is `false` (§1). RTL therefore never registers its auto-cleanup `afterEach` (§2).
Today this is invisible: `client.test.ts` never renders, and `LoginStub.test.tsx` has one
test. §7 plans `Home.test.tsx`, `Login.test.tsx`, `App.test.tsx`, `TopBar.test.tsx`,
`FindingDeck.test.tsx`, `SessionProvider.test.tsx` — every one of them renders in several
tests in the same file, and the second render will make `screen.getByRole('button', …)`
throw "found multiple elements."

`ARCHITECTURE.md` §3 says `src/test/setup.ts` is "keep — Unchanged." **That line should
change.** The minimal edit:

```ts
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
  server.resetHandlers()
  clearAccessToken()
})
```

`globals: true` in `vitest.config.ts` is the alternative and would also restore RTL's
`beforeAll`-set act environment, but it contradicts the suite's current explicit-import
style and Vitest's stated default rationale ("does not provide global APIs for
explicitness"). Three lines in the setup file is the smaller change. Note the setup file
already imports `@testing-library/jest-dom/vitest` — the correct, globals-free entry
point — so that half is right.

### 2. Rewrite the two Axios-interceptor spies

`LoginStub.test.tsx` and the fourth case in `client.test.ts` both do:

```ts
authClient.interceptors.request.use((config) => { requests.push(...); return config })
```

Three problems. First, it is exactly the implementation-detail assertion MSW's docs warn
against — `LoginStub.test.tsx`'s real subject is "typing credentials and clicking Log in
lands the user on the signed-in screen," which the `findByText('Signed in')` line already
proves; the `expect(requests).toEqual([true])` line asserts an Axios config field.
Second, `interceptors.request.use` returns an id and is **never ejected** — the handler
survives for the rest of the file, and every later test in that module accumulates
another one. Third, `withCredentials` scoping is already covered, correctly and in one
place, by `client.test.ts`'s dedicated case (which is the right home: there the client
*is* the subject under test).

Recommendation: drop the interceptor spy from `LoginStub.test.tsx` (and from its
successor `Login.test.tsx`); keep exactly one credential-scoping test in `client.test.ts`
and give it an explicit `interceptors.request.eject(id)` in a `finally`/`afterEach`.

Keep the request **counters** in the other three `client.test.ts` cases. They look like
the thing MSW discourages, but they are not: "exactly one refresh" and "single-flight"
*are* the behaviour under test — the count is the specification, not a proxy for it. That
is the same file's strongest asset and §7 correctly says it "must still pass unchanged."

### 3. Replace `container.querySelectorAll('[disabled]')` (AC 7)

§7 specifies, for `TopBar.test.tsx` and `Home.test.tsx`, that each "asserts
`container.querySelectorAll('[disabled]')` is empty for both roles." This should change
on two grounds:

- **It is banned by the lint rules Testing Library ships** — `no-container` and
  `no-node-access`, both enabled in the `react` config. (`frontend/eslint.config.js` does
  not currently include `eslint-plugin-testing-library`; adding it would be a cheap,
  permanent enforcement of most of §2 and §6 across the suite.)
- **It does not prove the invariant.** `[disabled]` misses an input disabled by an
  ancestor `fieldset[disabled]` (which `toBeDisabled()` does catch), and misses
  `aria-disabled="true"` entirely (which `toBeDisabled()` also misses — jest-dom #144).
  A greyed-out control implemented the ARIA way would sail past this assertion, and that
  is the exact regression AC 7 exists to catch.

A role-based replacement that is both lint-clean and strictly stronger — `getByRole` has
no `disabled` option, so the candidate set comes from the interactive roles the screen
can render:

```ts
const interactive = [
  ...screen.queryAllByRole('button'),
  ...screen.queryAllByRole('link'),
  ...screen.queryAllByRole('textbox'),
]
for (const el of interactive) {
  expect(el).toBeEnabled()
  expect(el).not.toHaveAttribute('aria-disabled', 'true')
}
```

`queryAllByRole` returns `[]` rather than throwing when a screen has none of a role, so
this is safe on `HomeBlank` as well as `Home`. The property §7 wants — "both roles render
identically" — is better served by rendering twice and comparing the accessible-name
lists, or by the experimental `toMatchAriaSnapshot` (§1), than by an attribute sweep.

The one legitimate `disabled` (`Login.test.tsx`, AC 3) is straightforward:
`server.use()` a handler with `await delay('infinite')`, assert
`expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled()` while it
hangs, and assert `toBeEnabled()` before submit. No fake timers, no `waitFor` timeout.

### 4. `renderWithProviders.tsx` — the exact `QueryClient` §7 needs

§3 of ARCHITECTURE.md specifies "One helper wrapping `MemoryRouter` + a per-test
`QueryClient` + `SessionProvider`." Per-test is correct (§5). Two additions:

- **`defaultOptions: { queries: { retry: false } }` is required**, or AC 15/16's error
  paths will exceed `findBy`'s 1000 ms window under React Query's three-retry
  exponential backoff. Equally: no `useQuery` in `src/hooks/` may set an explicit
  `retry`, because "defaults are only taken as a fallback."
- **No `gcTime: Infinity`** — that guidance is Jest-specific in TanStack's own doc and
  adds nothing under Vitest.

The helper must construct the client *inside* the function, not at module scope, or
every test in a file shares a cache and AC 20 ("query cache empty" after sign-out) starts
passing or failing depending on test order.

### 5. `mswHandlers.ts` and `onUnhandledRequest: 'error'`

§7 is right that adding `/users/me`, `/scans`, `/findings`, `/agents/:agentId` "is not
optional" given `setup.ts:9`. Three refinements:

- The `/scans` branch on `status` and the `/findings` branch on `severity` should read
  `new URL(request.url).searchParams` from the resolver's `request` (§4) rather than
  registering multiple handlers for the same path — `server.use()` **prepends**, so
  overlapping handlers resolve by registration order and become order-dependent.
- Type the handlers with MSW's `ResponseBodyType` generic bound to the generated
  `src/types/openapi.d.ts` types. Fixtures then break at `npm run typecheck` when the
  contract moves, which is a far better signal than a runtime assertion — and it makes
  the "no hand-written API types" constraint (§6 of ARCHITECTURE.md) enforceable in
  tests too.
- AC 4 needs `HttpResponse.error()`, not a 5xx: only a network error leaves
  `error.response` undefined, which is what distinguishes "network down" from "bad
  credentials" in `client.ts`.

### 6. AC 20's logout assertion — use MSW life-cycle events

"asserts `POST /auth/logout` fired" is a request assertion. It happens to fall inside
MSW's stated exception (a one-way request whose only UI consequence — navigation to
`/login` — also happens when the call *fails*, per §5 of ARCHITECTURE.md: "whether or not
the call succeeds"). So assert it, but with the sanctioned mechanism:

```ts
const seen: string[] = []
server.events.on('request:match', ({ request }) => { seen.push(request.url) })
// … sign out …
expect(seen.some((u) => u.endsWith('/auth/logout'))).toBe(true)
server.events.removeAllListeners()
```

The `removeAllListeners()` is not optional — `server.events` listeners are not cleared by
`resetHandlers()`.

### 7. Which planned test files earn their keep — and which do not

Against §6, the §7 file list splits cleanly:

**High value, keep as planned.** `src/lib/review.test.ts` (pure derivation, many
branches, the 3-day boundary, `latestSuccessfulScan: null` — the cheapest and most
durable tests in the plan); `src/api/client.test.ts` (already exists, protocol-level
behaviour); `src/auth/SessionProvider.test.tsx` (a real state machine: booting →
authenticated → anonymous, plus AC 8's role-from-server); `src/App.test.tsx` (routing and
the no-flash-on-reload guarantee — genuinely integration-shaped);
`src/pages/Login.test.tsx`, `src/pages/Home.test.tsx` (the four/five states each);
`src/pages/home/FindingDeck.test.tsx` (stepping, end-stops, focus-scoped arrow keys,
`aria-live` — real interaction logic).

**Low value as separate files.** Per-component tests for `ReviewItemCard`, `HomeBlank`,
`HomeError`, `HomeFooter`, `SignedInPlaceholder`: props in, markup out, no branching. §7
does not explicitly list test files for most of these, and it should stay that way —
their output is asserted through `Home.test.tsx` in the state that produces them, which
is both a user-shaped assertion and one fewer file to update when the copy changes.
`HomeError`'s `[Retry]` is behaviour, but it is Home's behaviour and AC 15/16 already
place it in `Home.test.tsx` / `useHomeReview.test.ts`.

**Wrong tool.** AC 8's "no token-decoding dependency exists in `package.json`" — move it
to `eslint.config.js` as `no-restricted-imports` on `jwt-decode`/`jose`. It then fails at
lint time, in the file that caused it, with a message that says what to do. A Vitest test
that reads `package.json` fails after the dependency is already installed and tells you
nothing about the code. AC 21 ("Quality gates") is already correctly excluded from Vitest
by §7 itself.

### 8. Smaller items

- **`vitest.config.ts` duplicates `vite.config.ts`.** Vitest reads `vite.config.ts`
  automatically, but "`vitest.config.ts` … will **override** the configuration from
  `vite.config.ts` … it means all options in your `vite.config` will be **ignored**"
  (https://github.com/vitest-dev/vitest/blob/v4.1.10/docs/config/index.md). The current
  duplication of `plugins` and the `@` alias is therefore necessary, not redundant —
  worth a comment so nobody "cleans it up."
- **If coverage is ever turned on**, `coverage.include` must be set explicitly
  (`['src/**/*.{ts,tsx}']`) or v4 reports only files that a test happened to import — the
  untested files disappear instead of showing 0% (§1).
- **`frontend/dist/`** is no longer excluded by Vitest's defaults in v4. Harmless today
  (no `*.test.*` in it), but `test.dir: './src'` or an explicit `exclude` would close it
  permanently and is the migration guide's own recommendation.
- **Adopt `eslint-plugin-testing-library`** (`react` config) in `frontend/eslint.config.js`.
  It mechanically enforces most of §2, §3 and §8 — `no-container`, `no-node-access`,
  `prefer-screen-queries`, `prefer-find-by`, `await-async-events`, `await-async-queries`,
  `no-wait-for-multiple-assertions`, `no-unnecessary-act` — which is a far cheaper way to
  hold the line on test quality across ~12 new files than review discipline.
- **`LoginStub.test.tsx`'s `getByPlaceholderText`** is third in the priority list, and
  its successor `Login.test.tsx` should use `getByLabelText` — mandatory for the password
  field, since `<input type="password">` has no implicit role (§2).

---

## Decision inputs (concrete)

| Input | Value | Source |
|---|---|---|
| Vitest `globals` default | `false`; "some libraries, e.g. `@testing-library/react`, rely on globals being present to perform auto cleanup" | vitest v4.1.10 `docs/config/globals.md` |
| RTL auto-cleanup trigger | registered only if `typeof afterEach === 'function'` | `react-testing-library/src/index.js` |
| Vitest `clearMocks` / `restoreMocks` at v4 | `false` / `false` (`clearMocks` becomes `true` in v5) | vitest v4.1.10 `docs/config/*.md` |
| Browser Mode status | no longer experimental in 4.0, but "still in its early stages", slower init; jsdom still a documented environment | vitest.dev/blog/vitest-4; vitest.dev/guide/browser/why |
| Coverage in v4 | `coverage.all`/`extensions` removed; define `coverage.include` explicitly; AST-based V8 remapping | vitest v4.1.10 `docs/guide/migration.md` |
| Query priority | role+name → label → placeholder → text → display value → alt → title → **testid last** | testing-library-docs `queries/about.mdx` |
| `getByTestId` legitimacy | "only recommended for cases where you can't match by role or text or it doesn't make sense (e.g. the text is dynamic)" | same |
| `findBy` timeout | 1000 ms; `waitFor` interval 50 ms | testing-library-docs `dom-testing-library/api-async.mdx` |
| user-event v14 | "APIs always return a Promise"; `setup()` recommended over direct calls | user-event v14.0.0 release notes; `user-event/intro.mdx` |
| `fireEvent` still correct for | events user-event doesn't model; non-user events (scroll, transitionend); focus via imperative `.focus()` | `guide-events.mdx`, `api-events.mdx` |
| MSW `onUnhandledRequest` | default `'warn'`; `'error'` recommended for tests | mswjs.io `setup-server/listen`, `recipes/request-assertions` |
| MSW on request assertions | "We highly discourage against such assertions as they represent implementation detail testing"; exception = one-way requests with no UI signal | mswjs.io `recipes/request-assertions` |
| MSW lifecycle | `listen()` / `resetHandlers()` per test / `close()`; `use()` prepends and persists until reset | mswjs.io `setup-server/use`, `best-practices/network-behavior-overrides` |
| Network failure | `HttpResponse.error()`; not customizable | mswjs.io `api/http-response` |
| TanStack test client | new `QueryClient` per test + `retry: false`; `gcTime: Infinity` is Jest-only | TanStack `docs/framework/react/guides/testing.md` |
| jest-dom `toBeDisabled` | covers native `disabled` + ancestor `fieldset`/`form`; **ignores** `aria-disabled` | jest-dom README; issue #144 |
| `aria-live` | region must exist in the DOM before the content change | MDN aria-live |
| Fake timers under Vitest | DTL's detector requires a global `jest`; `waitFor` will not advance Vitest fake timers | `dom-testing-library/src/helpers.ts`; vitest#3117, RTL#1198 |
| jsdom limits | no layout (`getBoundingClientRect`, `offsetTop` return zeros), no navigation | jsdom README |
