# Research: build/stack/code conventions for the React 19 + TypeScript + Vite SPA

> **Version-drift note:** this stack moved fast in the first half of 2026. Three
> of the versions pinned in `frontend/package.json` are no longer the newest
> major of their line as of 2026-07-28: **TypeScript 6.0 → TypeScript 7.0 is now
> npm `latest`**, **React Router 7 → v8 is now `latest`**, and Vite 8 replaced
> its entire bundler. Every version claim below was verified against the npm
> registry (`npm view <pkg> dist-tags|time`) on 2026-07-28 rather than taken
> from documentation prose, because doc sites silently track `latest`.

**Question.** What are the correct build, config, and code conventions for a
React 19 + TypeScript + Vite SPA at *the versions this repo actually pins* — and
which widely-repeated practices are now wrong at those versions?

**Stack under study** (`frontend/package.json`, resolved via `npm ls`):
react/react-dom `19.2.8`, typescript `6.0.3`, vite `8.1.5`,
`@vitejs/plugin-react` `^6.0.3`, tailwindcss `4.3.3` + `@tailwindcss/vite`,
`@tanstack/react-query` `5.101.4`, axios `^1.18.1`, eslint `^9.39` (flat),
typescript-eslint `^8.48`, eslint-plugin-react-hooks `7.1.1`,
openapi-typescript `^7.13`, Node `22.x`. React Router is about to be added.

---

## TL;DR verdict

**The repo's config is in good shape and is already on the correct side of most
of the version traps. Five things need a decision, and one is a real bug risk.**

1. **`strict` is not set anywhere in `tsconfig.app.json` — it is only on because
   TypeScript 6.0 flipped the default to `true`.** That is correct behaviour
   today but it is an *invisible* dependency on a version default. Set it
   explicitly (§2.1).
2. **React Router: install `react-router`, never `react-router-dom` — confirmed.
   But "library mode" is dead terminology.** The current docs name three modes:
   *declarative*, *data*, *framework*. ADR-008's "modo library" maps to
   *declarative*; the docs recommend *data mode* for an SPA like this one (§4).
3. **React Router v8 shipped 2026-06-17 and requires `react >= 19.2.7` — which
   this repo already has.** Adding v7 now is a deliberate one-major-behind
   choice, not the default. v7 is still actively released (7.18.2 shipped
   2026-07-28). Decide consciously (§4.1).
4. **TypeScript 7.0 (the Go-native compiler) became npm `latest` on 2026-07-08.**
   The `~6.0.2` pin is a supported position, but `npm install typescript` in a
   fresh checkout of any sibling tool now pulls 7.x. TS 6 was explicitly built
   as the migration runway to 7 (§2).
5. **`App.tsx` currently does session bootstrap in a `useEffect` with a
   three-state `useState`, and `LoginStub.tsx` hand-rolls form pending state.**
   React 19's `useActionState` collapses the login form's
   pending/error/submit triple; the boot-refresh belongs in TanStack Query
   rather than `useEffect` — and under `StrictMode` that effect fires twice in
   dev, meaning **two `POST /auth/refresh` calls with a rotating refresh token**
   (§1.5, §7.4). This is the one item with a correctness edge.

**Highest-value outdated practices to unlearn** — collected in §8.

---

## Findings

### 1. React 19 — what actually changed for app code

Installed: `react@19.2.8`. Baseline features are from the 19.0 release; 19.2
added `<Activity>`, `useEffectEvent`, and DevTools performance tracks.

#### 1.1 Actions, `useActionState`, `useFormStatus`

React 19 promotes "Actions" — async functions run inside a transition — to a
first-class primitive. Per the release post, Actions "automatically manage
submitting data for you", providing pending state that "starts at the beginning
of a request and automatically resets when the final state update is committed",
plus error handling and automatic form reset —
https://react.dev/blog/2024/12/05/react-19

`useActionState(action, initialState, permalink?)` returns
`[state, dispatchAction, isPending]`. The action receives
`(previousState, actionPayload)`; when wired to `<form action={dispatchAction}>`
React wraps the submission in a transition automatically. Caveats from the
reference: `dispatchAction` "must be called within `startTransition` or through
an Action prop, or it logs an error in development"; React "queues multiple
`dispatchAction` calls and executes them in order"; and "the return type of
`reducerAction` must match the type of `initialState`" —
https://react.dev/reference/react/useActionState

`useFormStatus` has one caveat that bites everyone exactly once: it "must be
called from a component that is rendered inside a `<form>`" and "will not return
status information for any `<form>` rendered in that same component or children
components." A submit button that reads `pending` must therefore be its own
child component —
https://react.dev/reference/react-dom/hooks/useFormStatus

**Relevance to the login screen: high.** A login form is precisely the
Actions-shaped case — one async submit, one pending flag, one error string.

#### 1.2 `use()` — and why it is *not* the data-fetching answer here

`use()` reads a Promise or a context and, unlike a Hook, "can be called within
loops and conditional statements". But the documented pitfall is disqualifying
for ad-hoc fetching: *"Promises passed to `use` in Client Components must be
cached so the same Promise instance is reused across re-renders. If a new Promise
is created directly in render, React will display the Suspense fallback on every
re-render."* The docs explicitly mark `use(fetch('/albums'))` as 🔴, and say
promises should come from "a cache", "a Suspense-enabled framework", or "a Server
Component". `use()` also cannot appear inside try/catch — rejections must go to
an Error Boundary —
https://react.dev/reference/react/use

**Relevance alongside TanStack Query: use `use()` for context, not for data.**
TanStack Query already *is* the cache. Reading context with `use()` after an
early return is the one genuinely useful application in this app.

#### 1.3 `ref` as a prop — `forwardRef` is obsolete

Function components now accept `ref` directly: `function MyInput({placeholder, ref})`.
"`forwardRef` is deprecated and will be removed." Ref callbacks may also return a
cleanup function. `element.ref` is deprecated in favour of `element.props.ref` —
https://react.dev/blog/2024/12/05/react-19

Also: `<Context value={...}>` renders as the provider; `<Context.Provider>` is
being phased out (same source).

#### 1.4 Removed APIs (hard removals, not warnings)

From the upgrade guide — https://react.dev/blog/2024/04/25/react-19-upgrade-guide

| Removed | Replacement |
|---|---|
| `propTypes` (silently ignored), `defaultProps` on function components | TypeScript types; ES6 default parameters |
| Legacy context (`contextTypes` / `getChildContext`) | modern Context API |
| String refs (`ref="input"`) | ref callbacks |
| Module pattern factories, `React.createFactory` | plain functions / JSX |
| `react-dom/test-utils` — all of it | `import {act} from 'react'` |
| `ReactDOM.render`, `ReactDOM.hydrate`, `unmountComponentAtNode` | `createRoot` / `hydrateRoot` / `root.unmount()` |
| `ReactDOM.findDOMNode` | DOM refs |
| UMD builds | ESM CDN (e.g. esm.sh) |
| `react-test-renderer` (deprecated) | `@testing-library/react` |

Error reporting changed too: uncaught errors go to `window.reportError`, caught
errors to `console.error` (not re-thrown), with new `onUncaughtError` /
`onCaughtError` / `onRecoverableError` root options (same source).

#### 1.5 StrictMode double-invocation

`<StrictMode>` in development calls twice: component function bodies (top-level
logic only, not event handlers); functions passed to `useState`, set functions,
`useMemo`, `useReducer`; and runs **setup → cleanup → setup** for both Effects
and ref callbacks. *"All of these checks are development-only and do not impact
the production build."* —
https://react.dev/reference/react/StrictMode

React 19 softened one edge: "when double rendering in Strict Mode in development,
`useMemo` and `useCallback` will reuse the memoized results from the first render
during the second render" —
https://react.dev/blog/2024/04/25/react-19-upgrade-guide

**Consequence for this repo:** the double *Effect* invocation is not softened.
`App.tsx`'s bootstrap `useEffect` calling `refresh()` will fire twice in dev.
Because ADR-008 specifies a **rotating** refresh token on every
`POST /auth/refresh`, the second dev call consumes a token the first call just
rotated — a dev-only phantom logout that looks like a backend bug. This is not a
reason to remove StrictMode; it is StrictMode doing its job. The fix is to move
the bootstrap into a deduplicating cache (TanStack Query, §5.5).

#### 1.6 React 19.2 additions worth knowing

`useEffectEvent` extracts "event" logic out of an Effect so that "Effect Events
always 'see' the latest props and state" without joining the dependency array —
the sanctioned fix for the stale-closure/`exhaustive-deps` fight. `<Activity>`
pre-renders and preserves state for hidden subtrees. `useId`'s prefix changed
from `:r:` to `_r_` so IDs are valid CSS selectors —
https://react.dev/blog/2025/10/01/react-19-2

The `useId` change matters for a11y testing: `useId` output is now safe to use in
`querySelector` and in `htmlFor`/`aria-describedby` wiring.

---

### 2. TypeScript 6.0 — status, and what it newly enforces

#### 2.1 Status: released, superseded, still supported

Verified from the npm registry on 2026-07-28:

| Version | Published | Note |
|---|---|---|
| `6.0.2` | 2026-03-23 | first stable 6.0 |
| `6.0.3` | 2026-04-16 | what `~6.0.2` resolves to here |
| `7.0.2` | 2026-07-08 | **npm `latest`** |

TypeScript 6.0 is real, and it is explicitly a bridge: it is *"the last release
based on the current JavaScript codebase"*, and *"most changes in TypeScript 6.0
are meant to help align and prepare for adopting TypeScript 7.0"* —
https://devblogs.microsoft.com/typescript/announcing-typescript-6-0/

TypeScript 7.0 is the Go-native port, "a 10x faster native port of TypeScript"
with "speedups between 8x and 12x on full builds", released 2026-07-08. It
installs under the same `typescript` package name with the same `tsc` binary.
7.0 does **not** yet expose a stable programmatic API, so embedded-language
tooling (Vue/Svelte/Astro/MDX) and webpack loaders must wait for 7.1. TypeScript
6.0 remains supported, and `@typescript/typescript6` allows side-by-side
installation —
https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/

**Verdict for Dmitri:** staying on `~6.0.2` is defensible and low-risk today.
The migration path is explicitly "upgrade to 6.0 first", which this repo has
already done — the hard part is behind it.

#### 2.2 Changed defaults in 6.0 vs 5.x — the ones that bite

From the 6.0 announcement (same source):

| Option | 5.x default | **6.0 default** |
|---|---|---|
| `strict` | `false` | **`true`** |
| `module` | `commonjs` | `esnext` |
| `target` | `es5`/`es3` | `es2025` |
| `types` | auto-enumerates `node_modules/@types` | **`[]`** |
| `noUncheckedSideEffectImports` | `false` | `true` |
| `libReplacement` | `true` | `false` |
| `rootDir` | inferred from inputs | `.` (the tsconfig dir) |

The `types: []` change is the loudest one — the docs warn that projects should
explicitly set `"types": ["node"]` or similar and that "many will encounter type
errors otherwise."

**This repo is already compliant:** `tsconfig.app.json` sets
`"types": ["vite/client"]` and `tsconfig.node.json` sets `"types": ["node"]`.

**But `strict` is nowhere in either file.** It is on solely because of the 6.0
default. Nothing breaks today; the risk is that the strictness posture is
invisible to a reader and silently inverts if any tool in the chain resolves an
older `typescript`. Set `"strict": true` explicitly — it is a one-line no-op that
converts an implicit guarantee into an explicit one.

#### 2.3 Deprecations and removals in 6.0

Deprecated but still usable with `"ignoreDeprecations": "6.0"`: `target: es5`
(minimum is now ES2015), `--downlevelIteration`, **`--moduleResolution node`
(node10)**, `--module amd|umd|systemjs|none`, **`--baseUrl`**,
`--esModuleInterop false`, `--allowSyntheticDefaultImports false`,
`--alwaysStrict false`, the legacy `module` keyword for namespaces, and `assert`
on import attributes (use `with`).

Fully removed: `--outFile`, `--moduleResolution classic`, AMD/UMD/SystemJS emit.

Per the 7.0 post, "several deprecated flags (like `target: es5`, `baseUrl`) now
produce hard errors" in 7.0.

⚠️ **`baseUrl` deprecation vs. shadcn/ui's own install docs.** The shadcn Vite
guide still instructs you to "add `baseUrl` and `paths` properties to both
`tsconfig.json` and `tsconfig.app.json`" —
https://ui.shadcn.com/docs/installation/vite — but `baseUrl` has not been
*required* for `paths` since TypeScript 4.1
(https://www.typescriptlang.org/tsconfig/) and is deprecated in 6.0 / a hard
error in 7.0. **This repo already does the right thing** (`paths` without
`baseUrl` in `tsconfig.app.json`). Do not "fix" it by following the shadcn docs
literally.

#### 2.4 Recommended tsconfig posture for a Vite SPA

The repo's split — a solution-style root `tsconfig.json` with `"files": []` and
two `references` to `tsconfig.app.json` (browser, `include: ["src"]`) and
`tsconfig.node.json` (config files, `include: ["vite.config.ts"]`) — is the
create-vite scaffold shape and remains correct. It exists because the two
environments have genuinely different `lib`/`types`/`module` needs, which a
single config cannot express. `npm run build` runs `tsc -b` (build mode, required
for project references) before `vite build`; `npm run typecheck` runs
`tsc -b --noEmit`. That is the right wiring.

The flags that matter, and why:

- **`moduleResolution: "bundler"`** — *"'bundler' for use with bundlers. Like
  `node16` and `nodenext`, this mode supports package.json `imports` and
  `exports`, but unlike the Node.js resolution modes, `bundler` never requires
  file extensions on relative paths in imports."* —
  https://www.typescriptlang.org/tsconfig/ . 6.0 additionally allows combining
  `bundler` with `--module commonjs` and supports `#/`-prefixed subpath imports.
- **`verbatimModuleSyntax: true`** — forces `import type` / `export type` to be
  written explicitly, so emit is a pure syntactic erasure. This is what makes
  `import { AxiosError, type InternalAxiosRequestConfig } from 'axios'` in
  `src/api/client.ts` mandatory rather than stylistic. Keep it on: it is the flag
  that prevents type-only imports from accidentally surviving into runtime
  side-effect imports.
- **`erasableSyntaxOnly: true`** — bans TS syntax that has runtime semantics
  (enums, parameter properties, namespaces with values, `declare` class fields).
  It exists to guarantee the file can be stripped by a type-erasing transform.
  Since Vite 8 strips types with Oxc, not `tsc` (§3.1), **this flag is what makes
  the Vite pipeline sound**, not a style preference. It is set in both configs
  here. Practical rule for the team: **no `enum` — use `as const` objects and
  union types.**
- **`isolatedModules`** — *"forces TypeScript to treat each file as a module by
  ensuring that certain constructs can be properly compiled in isolation"*
  (https://www.typescriptlang.org/tsconfig/). Not set explicitly here; largely
  subsumed by `verbatimModuleSyntax` + `erasableSyntaxOnly` + `moduleDetection:
  "force"`, all of which are set. Adding it is cheap insurance.
- **`noEmit: true`** with `allowImportingTsExtensions` — correct; Vite owns emit.
- **`noUnusedLocals` / `noUnusedParameters` / `noFallthroughCasesInSwitch`** —
  already on; these are the cheap ones that catch real bugs.

Worth adding beyond `strict` (none are on by default even under 6.0):
`noUncheckedIndexedAccess` (makes `arr[i]` `T | undefined` — the single highest
value-per-character flag for list-rendering code) and `exactOptionalPropertyTypes`
(matters when hand-writing request bodies against generated OpenAPI types).

---

### 3. Vite 8 — config posture, env, build/preview

#### 3.1 What changed from Vite 7: the bundler was replaced

*"Vite 8 uses Rolldown and Oxc based tools instead of esbuild and Rollup."* —
https://vite.dev/guide/migration

Consequences that show up in real configs:

- **Dependency optimizer** now uses Rolldown. `optimizeDeps.esbuildOptions` is
  auto-converted to `optimizeDeps.rolldownOptions` "for backward compatibility",
  but that layer is deprecated.
- **JS transformation** is Oxc, not esbuild. The `esbuild` config key still
  works but is deprecated. **Oxc does not support lowering native decorators.**
- **Minification** — Oxc Minifier for JS, **Lightning CSS for CSS by default**.
- **CommonJS `default`-import interop** is now consistent between dev and build,
  where it previously used a heuristic — a real (if rare) behaviour change.
- **Removed:** `system` and `amd` output formats; Rollup hooks
  `resolveImportMeta`, `renderDynamicImport`.

The announcement claims "up to 10-30x faster builds while maintaining full plugin
compatibility" and that "most projects will work without any config changes" —
https://vite.dev/blog/announcing-vite8

**Node requirement is unchanged from Vite 7:** `^20.19.0 || >=22.12.0` (verified
via `npm view vite@8.1.5 engines`). The repo's `"node": "22.x"` engines pin
satisfies this.

**Default browser target** rose to the "Baseline Widely Available feature sets as
of 2026-01-01" — Chrome ≥111, Edge ≥111, Firefox ≥114, Safari ≥16.4 —
https://vite.dev/guide/build . For an internal security dashboard this is a
non-issue; it is worth knowing before anyone files a bug about an old Safari.

#### 3.2 `@vitejs/plugin-react` v6 — Babel is gone

Breaking changes in 6.0.0, from the changelog
(https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react/CHANGELOG.md):

- **Babel is no longer a dependency.** *"Vite 8+ can handle React Refresh
  Transform by Oxc and doesn't need Babel for it."*
- The **`babel` option was removed**. Babel transforms now require
  `@rolldown/plugin-babel` alongside the plugin.
- **React Compiler setup changed**: use `reactCompilerPreset` with
  `@rolldown/plugin-babel`; the `runtimeModule` option is gone. (Confirmed by the
  v6.0.4 peer deps: `@rolldown/plugin-babel` and `babel-plugin-react-compiler`,
  both optional peers, plus `vite: ^8.0.0`.)
- **Requires Vite 8+**; Vite 7 and below are dropped.
- **No longer auto-adds `react`/`react-dom` to `resolve.dedupe`** — add manually
  if you hit duplicate-React symptoms.

⚠️ **Outdated advice to reject:** every "add a Babel plugin to
`@vitejs/plugin-react`" snippet on the internet targets v4/v5. Under v6 the
`babel:` key does not exist.

#### 3.3 Env vars

From https://vite.dev/guide/env-and-mode :

- Built-ins on `import.meta.env`: `MODE`, `BASE_URL`, `PROD`, `DEV`, `SSR`.
- *"Variables prefixed with `VITE_` will be exposed in client-side source code
  after Vite bundling."* Anything unprefixed stays out of the bundle.
  `envPrefix` can change the prefix.
- **Load order / priority:** `.env` → `.env.local` → `.env.[mode]` →
  `.env.[mode].local`. *"An env file for a specific mode (e.g. `.env.production`)
  will take higher priority than a generic one."* And crucially:
  *"environment variables that already exist when Vite is executed have the
  highest priority and will not be overwritten by `.env` files."*
- **Gitignore:** *"You should add `*.local` to your `.gitignore` to avoid them
  being checked into git."*
- **Security:** *"VITE_\* variables should **not** contain sensitive information
  such as API keys"* — the value is inlined into the bundle at build time.

Repo status: `frontend/.gitignore` already carries both `*.local` and `.env`, and
a committed `.env.example` documents the shape. `VITE_API_URL` is the only
consumer (`src/api/instances.ts`) and is a public base URL, so the
no-secrets rule holds. ✅

One gap: `import.meta.env.VITE_API_URL` is typed `string` by `vite/client`'s
catch-all index signature, so a missing var yields the literal string
`"undefined/api/v1"` rather than a type error. Declaring the var in a
`src/vite-env.d.ts` `ImportMetaEnv` interface and asserting at module load turns
a silent 404 storm into a startup failure.

#### 3.4 Build vs preview

`vite build` produces "an application bundle that is suitable to be served over a
static hosting service" (https://vite.dev/guide/build). `vite preview` serves
`dist` locally, and the CLI docs are unambiguous: ***"Do not use this as a
production server as it's not designed for it."*** —
https://vite.dev/guide/cli

For an SPA behind client-side routing, the production host must rewrite unknown
paths to `index.html`, or a hard refresh on `/scans/123` 404s. `vite preview`
does this for you based on `appType` (default `'spa'`), which is exactly why
"it worked in preview" is not evidence the deployment is correct.

---

### 4. React Router — version choice, packages, and route shape

#### 4.1 Versions: v8 is current; v7 is one major behind but alive

Verified from the npm registry, 2026-07-28:

| Tag | Version | Published |
|---|---|---|
| `latest` | **8.3.0** | 2026-07-22 |
| `version-7` | 7.18.2 | **2026-07-28** (same day) |
| — | 8.0.0 | 2026-06-17 |
| — | 7.0.0 | 2024-11-22 |

Peer requirements (`npm view react-router@<v> peerDependencies`):

- v7.18.2 → `react >=18`, `react-dom >=18`
- **v8.3.0 → `react >=19.2.7`, `react-dom >=19.2.7`**

The v8 changelog lists "Update minimum React version to 19.2.7" as a major
change — https://raw.githubusercontent.com/remix-run/react-router/main/CHANGELOG.md

**This repo already resolves `react@19.2.8`, so v8's peer floor is met.** ADR-008
chose v7 on 2026-07-10, seven days *before* v8's 2026-06-17… actually after it —
so the v8 option may simply not have been evaluated. The ADR's own reasoning
against v6 ("choosing v6 in a greenfield scaffold in 2026 assumes a known
migration on day one, with no upside") now applies verbatim to v7. Whether that
outweighs v8's youth is a judgement call, but it should be a *recorded* one.

#### 4.2 The package question: `react-router`, confirmed

The task's premise is correct, with a nuance worth stating precisely.

Per the v7 changelog: *"In v7, we collapsed the DOM APIs into `react-router/dom`,
but to ease the v6->v7 upgrade we continued re-exporting everything through
`react-router-dom`."* Per v8: *"React Router v8 removes the `react-router-dom`
re-export package."* —
https://reactrouter.com/upgrading/v7 and the CHANGELOG above.

Verified empirically against an actual v7.18.2 install: `react-router` exports
`BrowserRouter`, `createBrowserRouter`, **and** `RouterProvider` from the main
entry; the `react-router/dom` subpath also exists. And `react-router-dom@7.18.2`
is a 1-dependency shim whose entire `dependencies` block is
`{"react-router": "7.18.2"}`. **No `react-router-dom@8` was ever published.**

So:

| | v7 | v8 |
|---|---|---|
| install | `react-router` (`react-router-dom` is a live-but-pointless shim) | `react-router` only |
| `BrowserRouter`, `Link`, `Outlet`, `Navigate`, hooks | `react-router` | `react-router` |
| `RouterProvider` | `react-router` (also `react-router/dom`) | **`react-router/dom`** |

On `RouterProvider` specifically, the current API docs say: *"this component is
exported both from `react-router` and `react-router/dom` with the only difference
being that the latter automatically wires up `react-dom`'s `flushSync`
implementation. You almost always want to use the version from `react-router/dom`
unless you're running in a non-DOM environment."* —
https://reactrouter.com/api/data-routers/RouterProvider

**Convention: import `RouterProvider` from `react-router/dom` and everything else
from `react-router`, on either major.** That import shape is forward-compatible
with v8 and correct on v7.

#### 4.3 "Library mode" is not a current term

The docs define exactly three modes —
https://reactrouter.com/start/modes :

| Mode | Top-level API | Gets you |
|---|---|---|
| **Declarative** | `<BrowserRouter>` + `<Routes>`/`<Route>` | URL matching, `Link`, `useNavigate`, `useLocation` |
| **Data** | `createBrowserRouter()` + `<RouterProvider>` | + `loader`, `action`, `useFetcher`, pending states |
| **Framework** | `@react-router/dev` Vite plugin, `routes.ts` | + file routing, typed params, SSR/SSG, code splitting |

ADR-008's "modo library / declarativo" maps to **Declarative**. The docs
recommend **Data mode** for "apps needing data features but wanting control over
bundling and server abstractions" — i.e. an SPA like this one.

**But** ADR-008's rejection of framework mode rests on a real argument that
partially applies to data mode too: *"loaders would compete with TanStack Query
for ownership of data-fetching."* That concern is about `loader`/`action`, not
about `createBrowserRouter` itself. You can adopt data mode's **object route
table** and simply not define loaders — keeping TanStack Query as the sole data
owner while gaining a declarative, testable, statically-analysable route config.
That is the recommendation here.

#### 4.4 Route table shape

Data mode (https://reactrouter.com/start/data/routing):

```js
import { createBrowserRouter } from "react-router";

const router = createBrowserRouter([
  {
    Component: RequireAuth,          // pathless layout route = the guard
    children: [
      {
        Component: AppShell,         // pathless layout route = the chrome
        children: [
          { index: true, Component: Home },
          { path: "scans", children: [
            { index: true, Component: ScanList },
            { path: ":scanId", Component: ScanDetail },
          ]},
        ],
      },
    ],
  },
  { path: "login", Component: Login },
]);
```

Declarative mode (https://reactrouter.com/start/declarative/routing) uses the
same nesting semantics with JSX. In both, the primitives are identical:

- **A route with `children` and no `path`** is a *layout route* — it nests
  without adding a URL segment. This is the mechanism for both `AppShell` and the
  auth guard.
- **`<Outlet />`** in the parent renders the matched child. Imported from
  `react-router`.
- **`{ index: true }`** renders at the parent's own URL.
- **`:param`** dynamic segments, read with `useParams()`; `?` optional segments;
  `/*` splats.

#### 4.5 Route guards, idiomatically

There is **no built-in `<PrivateRoute>` and no official guard API** in
declarative/data mode. The documented server-side mechanism is *middleware*
(`throw redirect("/login")` from an `authMiddleware`) —
https://reactrouter.com/how-to/middleware — which is a framework-mode/server
concept and does not apply to a static SPA talking to FastAPI.

For a client-only SPA the idiomatic shape is a **pathless layout route whose
component renders either `<Outlet />` or a redirect.** The `<Navigate>` component
exists for this, and its docs carry a caveat worth heeding: it is *"a
component-based version of `useNavigate` designed for use in `React.Component`
class[es] where hooks cannot be used"*, and *"it's recommended to avoid using
this component in favor of `useNavigate`"* —
https://reactrouter.com/api/components/Navigate

That recommendation is aimed at **event handlers** (where calling `navigate()` is
correct and rendering a component is not). Rendering `<Navigate replace to="/login" />`
as the *entire output of a render* is the redirect-as-render case and is fine —
it is declarative, it works during the render pass, and `replace` keeps the
protected URL out of the history stack.

```tsx
function RequireAuth() {
  const { status } = useSession()          // TanStack Query, §5.5
  const location = useLocation()
  if (status === 'pending') return <FullPageSpinner />
  if (status === 'error') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  return <Outlet />
}
```

Two details that are easy to get wrong:

- **`replace`** — without it, "back" from `/login` returns to the protected URL
  and bounces again.
- **`state={{ from: location }}`** — the only supported way to round-trip the
  intended destination so login can send the user back. `state` is documented as
  "State to pass to the new `Location` to store in `history.state`"
  (`Navigate` API docs above).

Role gating (`admin` vs `viewer`, per ADR-008) is the same pattern one level
deeper — a second pathless route that checks the JWT claim. ADR-008 is right that
this is UX only; the backend is the authority.

---

### 5. TanStack Query v5

Installed: `5.101.4`.

#### 5.1 v4 → v5 API changes

From https://tanstack.com/query/latest/docs/framework/react/guides/migrating-to-v5 :

| v4 | v5 |
|---|---|
| `useQuery(key, fn, options)` overloads | **single object only**: `useQuery({ queryKey, queryFn, ...opts })` |
| `status: 'loading'` | `status: 'pending'` |
| `isLoading` | **`isPending`** |
| `isInitialLoading` | `isLoading` (now means `isPending && isFetching`) |
| `cacheTime` | `gcTime` |
| `onSuccess` / `onError` / `onSettled` **on queries** | **removed** (still exist on mutations) |
| `keepPreviousData: true` | `placeholderData: keepPreviousData` (imported helper) |
| `useErrorBoundary` | `throwOnError` |

Two of these are silent traps rather than errors: `isLoading` still *exists* in
v5 with a **different meaning**, so v4-era code compiles and misbehaves. And
`onSuccess` on a query simply does nothing — no warning.

#### 5.2 Query key conventions

Keys "have to be an Array at the top level"; hashing is deterministic and
**object key order does not matter** (`{status, page}` ≡ `{page, status}`) while
**array element order does** (`['todos', status, page]` ≠ `['todos', page, status]`).
The core rule: *"If your query function depends on a variable, include it in your
query key"* — because *"adding dependent variables to your query key will ensure
that queries are cached independently, and that any time a variable changes,
queries will be refetched automatically."* —
https://tanstack.com/query/latest/docs/framework/react/guides/query-keys

Invalidation is **prefix-based by default**: invalidating `['todos']` also
invalidates `['todos', {page: 1}]`; `exact: true` narrows it; a `predicate`
function gives full control —
https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation

**Convention that follows from those two facts:** order keys
*coarsest-to-finest* (`['scans']` → `['scans', 'list', filters]` →
`['scans', 'detail', id]`) so that the ADR-008 "Scan now" flow can invalidate
`['scans']`, `['agents']`, `['findings']` with three prefix calls. Centralise the
keys in one factory module per domain so no string literal is ever typed twice —
the prefix relationships are load-bearing and a typo degrades silently into "the
list just doesn't refresh."

#### 5.3 Derived union vs raw booleans

The official guidance is the boolean ladder: *"for most queries, it's usually
sufficient to check for the `isPending` state, then the `isError` state, then
finally, assume that the data is available"* — and the reason it works is
type-level: *"TypeScript will also narrow the type of `data` correctly if you've
checked for `pending` and `error` before accessing it"* —
https://tanstack.com/query/latest/docs/framework/react/guides/queries

The query result **is already a discriminated union** on `status`. So:

- **Do not** build a hand-rolled `type ViewState = {kind:'loading'} | ...`
  wrapper around a query result. It re-implements a union the library already
  gives you, and it throws away the narrowing.
- **Do** use the ladder (or `switch (query.status)`) at the component boundary.
- **Do** reach for an explicit derived union when a screen composes *several*
  queries plus local state into states the individual queries don't express
  (e.g. the "Scan now" polling machine: `idle | queued | running | done |
  device_offline | device_busy` — the last two being 503/409 contract errors, not
  query states).

#### 5.4 QueryClient config: tests vs production

Defaults (https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults):
`staleTime: 0` (data is stale immediately), `gcTime` 5 minutes, **failed queries
"are silently retried 3 times, with exponential backoff delay"**, and stale
queries refetch on mount / window refocus / network reconnect. Results are
structurally shared so unchanged data keeps referential identity.

The testing guide is emphatic about the retry default: set `retry: false` in
`defaultOptions.queries`, because otherwise *testing an error path waits out
three exponential-backoff retries and times out*. It also recommends a **fresh
`QueryClient` per test** via a wrapper factory — *"It is possible to write this
wrapper only once, but if so we need to ensure that the `QueryClient` gets cleared
before every test, and that tests don't run in parallel"* —
https://tanstack.com/query/latest/docs/framework/react/guides/testing

```ts
// test helper
export function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  )
}
```

⚠️ **Two outdated test snippets to reject:** `logger: { error: () => {} }` — the
`logger` option was **removed in v5** and does not appear in the current testing
guide. And `gcTime: Infinity` is documented specifically as a *Jest* workaround
for "Jest did not exit one second after the test run completed"; this repo uses
**Vitest 4**, so it is unnecessary noise.

#### 5.5 Logout, and the session bootstrap

`queryClient.clear()` — *"The `clear` method clears all connected caches"*,
removing both the query cache and the mutation cache —
https://tanstack.com/query/latest/docs/reference/QueryClient . `removeQueries()`
"removes matching queries from the cache instead of refetching them";
`resetQueries()` returns queries to initial state and refetches active ones;
`invalidateQueries()` marks stale and refetches (default `refetchType: 'active'`).

**Logout convention:** `clear()`, not `invalidateQueries()`. Invalidation
*refetches* — which, mid-logout with the token already cleared, fires a burst of
401s straight into the refresh interceptor in `src/api/client.ts`, which then
redirects to `/login` and possibly races the intentional navigation. Order
matters: `await logout()` → `clearAccessToken()` → `queryClient.clear()` →
navigate.

**Bootstrap convention:** move `App.tsx`'s `useEffect(() => refresh()...)` into a
`useQuery({ queryKey: ['session'], queryFn: refresh, retry: false, staleTime:
Infinity })`. This buys three things at once: TanStack Query deduplicates
concurrent identical queries, so the **StrictMode double-invocation (§1.5) fires
one network request, not two** — eliminating the phantom refresh-token rotation;
`retry: false` prevents three retries against a legitimately-expired refresh
cookie; and `status` becomes the exact `pending | error | success` union the
`RequireAuth` guard (§4.5) needs, replacing the hand-rolled
`'loading' | 'signedIn' | 'signedOut'` `useState`.

---

### 6. Tailwind v4

Installed: `4.3.3` with `@tailwindcss/vite`.

#### 6.1 CSS-first config replaces `tailwind.config.js`

Theme configuration in v4 is entirely CSS-based through `@theme`, and the default
theme ships as `tailwindcss/theme.css`. There is no JS config object —
https://tailwindcss.com/docs/theme

The key insight, in the docs' own words: *"Theme variables aren't just CSS
variables — they also instruct Tailwind to create new utility classes that you
can use in your HTML."* And on why the special syntax exists: *"Since they do more
than regular CSS variables, Tailwind uses special syntax so that defining theme
variables is always explicit."*

`@theme` **must be top-level** — "not nested under other selectors or media
queries."

#### 6.2 Tokens → utilities, by namespace

| Namespace | Generated utilities |
|---|---|
| `--color-*` | `bg-*`, `text-*`, `fill-*`, `border-*` |
| `--font-*` | `font-sans`, `font-heading` |
| `--text-*` | `text-xl` (font size) |
| `--spacing-*` | `px-4`, `max-h-16` |
| `--radius-*` | `rounded-sm` |
| `--breakpoint-*` | `sm:`, `md:` variants |
| `--shadow-*`, `--animate-*`, `--tracking-*`, `--leading-*`, `--font-weight-*` | correspondingly |

*"You can name your theme variables whatever you want within these namespaces,
and a corresponding utility with the same name will become available to use in
your HTML."*

`--*: initial` inside `@theme` wipes the entire default theme; `--color-*: initial`
wipes one namespace: *"all of the default utilities that use that namespace (like
`bg-red-500`) will be removed, and only your custom values will be available."*

#### 6.3 `@theme inline` — the part that is genuinely subtle

*"Using the `inline` option, the utility class will use the theme variable value
instead of referencing the actual theme variable"* — required when a theme
variable **references another variable**, because without it, resolution can fail
under CSS cascade rules where variables resolve at their definition point rather
than their use site.

**This is exactly the pattern in `frontend/src/index.css`.** Raw design tokens
(`--background`, `--primary`, `--destructive`, …) live in `:root` as plain CSS
custom properties — correct, since they should *not* each mint a utility — and
the `@theme inline { --color-primary: var(--primary); ... }` block maps them into
Tailwind's namespaces. `inline` is load-bearing here: the `:root` values get
overridden under `.dark`, and without `inline` the indirection would resolve
against the wrong scope. **Do not remove `inline` from that block.**

Docs' own rule of thumb: `@theme` for design tokens that should become
utilities, `:root` for regular CSS variables that should not.

#### 6.4 Custom variants

```css
@custom-variant theme-midnight (&:where([data-theme="midnight"] *));
```

or the nested form with `@slot` for multi-rule variants —
https://tailwindcss.com/docs/adding-custom-styles

The repo's `@custom-variant dark (&:is(.dark *));` is exactly this mechanism:
class-based dark mode in v4 is a *custom variant*, not a config key.

⚠️ **Outdated:** `darkMode: 'class'` in `tailwind.config.js`. That option, and
the file, do not exist in v4. Every v3-era dark-mode tutorial is wrong here.

The same page also documents `@utility` (including functional `tab-*` utilities
that pull from `--value(--tab-size-*)`), arbitrary values `top-[117px]`,
arbitrary properties `[mask-type:luminance]`, the CSS-variable shorthand
`fill-(--my-brand-color)`, and underscores for whitespace
`grid-cols-[1fr_500px_2fr]`.

---

### 7. Code conventions worth enforcing

#### 7.1 File and component organisation

The repo's current shape — `src/api`, `src/components/ui`, `src/pages`,
`src/lib`, `src/types`, `src/test` — is the shadcn/create-vite convention and is
fixed by `components.json` aliases (`@/components`, `@/components/ui`, `@/lib`,
`@/hooks`). `components/ui` is *generated* territory: shadcn writes into it, so
hand-authored components belong in `components/` proper or beside their feature.

**Colocation rule that scales:** a module is shared only after the *second*
consumer exists. Until then it lives next to its single consumer. This is the
"no abstractions for single-use code" rule from `CLAUDE.md` applied to file
layout. As the screen inventory in ADR-008 grows past ~10 routes, the natural
next step is `src/features/<domain>/` holding that domain's components, hooks,
query-key factory, and API functions together — with `src/api`, `src/lib`, and
`src/components/ui` staying as the genuinely cross-cutting layers.

Tests already colocate (`api/client.test.ts`, `pages/LoginStub.test.tsx`). Keep
that; it makes the "delete the feature, delete the folder" property hold.

#### 7.2 The typed API layer over generated OpenAPI types

openapi-typescript "turns OpenAPI 3.0 & 3.1 schemas into TypeScript quickly",
generating `paths`, `components`, `operations`, and `webhooks` as
"runtime-free types that outperform old school codegen" — types only, no runtime
—  https://openapi-ts.dev/introduction . It recommends pairing with
`openapi-fetch`.

`src/types/openapi.d.ts` is generated by `npm run gen:types` from
`contracts/openapi/openapi.yaml` and is committed, which (per ADR-008) makes
contract drift visible in PR diffs. The pattern in `src/api/auth.ts` is the right
one and should be the house style:

```ts
import type { components } from '../types/openapi'
type LoginRequest = components['schemas']['LoginRequest']
type LoginResponse = components['schemas']['LoginResponse']
```

Conventions to hold the line on:

- **Never edit `openapi.d.ts`.** It is regenerated; edits vanish.
- **Never let `components['schemas'][...]` indexing leak past `src/api/`.**
  Alias once at the module top, export the alias. Components import the alias,
  never the raw index — so a schema rename is a one-line fix per API module.
- **`import type`, always** — `verbatimModuleSyntax` (§2.4) enforces this.
- **The `paths` type is the under-used half.** `paths['/auth/login']['post']`
  ties a URL+method to its request and response types, which is what catches a
  handler calling the right types against the wrong endpoint.
- **ADR-008 deliberately rejected `orval`/`openapi-generator`** because the
  central Axios client already covers the client role. `openapi-fetch` is
  upstream's recommendation but would duplicate the interceptor machinery in
  `src/api/client.ts` (single-flight 401→refresh) that ADR-008 and the axios
  research note specify. **Keep Axios; use openapi-typescript for types only.**
  Note the split-instance design (`apiClient` / `authClient` in
  `src/api/instances.ts`) matches the recommendation in
  [`axios-withcredentials-auth-scoping.md`](./axios-withcredentials-auth-scoping.md).

#### 7.3 Lint config

`eslint-plugin-react-hooks` changed shape twice recently. From the changelog
(https://raw.githubusercontent.com/facebook/react/main/packages/eslint-plugin-react-hooks/CHANGELOG.md):

- **6.1.0** — "Flat config is now the default `recommended` preset. Legacy config
  moved to `recommended-legacy`." Added rules banning `use` inside try/catch and
  `useEffectEvent` in arbitrary closures.
- **7.0.0** — removed `recommended-latest-legacy` and **`flat/recommended`**;
  presets reduced to `recommended` and `recommended-latest`; "all compiler rules
  are enabled by default."

Verified against the installed `7.1.1` in this repo:
`Object.keys(plugin.configs)` → `['recommended', 'recommended-latest', 'flat']`,
with `recommended` carrying **16 rules** and `recommended-latest` 17. So
`recommended` is no longer just `rules-of-hooks` + `exhaustive-deps` — it now
includes the React Compiler rule family (`immutability`, `purity`, `refs`,
`set-state-in-effect`, `set-state-in-render`, `static-components`,
`preserve-manual-memoization`, `error-boundaries`, …).

The repo's `eslint.config.js` spreads `...reactHooks.configs.recommended.rules`,
which does pick all 16 up. Two notes: the plugin README's
`reactHooks.configs.flat.recommended` still resolves (a `flat` namespace object
survives), but `flat/recommended` as a *string* preset name is gone as of 7.0 —
so any `extends: ['plugin:react-hooks/flat/recommended']` string is now dead.
And since compiler rules are on, expect new findings on existing code; they are
usually pointing at real render-purity violations.

⚠️ **Outdated:** every `.eslintrc.json` + `extends: ["plugin:react-hooks/recommended"]`
snippet. ESLint 9 flat config plus plugin v7 uses object config only.

#### 7.4 Accessibility — the testable subset

For a form-heavy login screen these four are objectively checkable in
`@testing-library/react` without a human:

1. **Every input has a programmatic label.** WAI-ARIA APG: *"Whenever possible,
   rely on HTML naming techniques, such as the HTML `label` element for form
   elements"*, and *"When a user interface includes visible text that could be
   used to provide an appropriate accessible name, using the visible text for the
   accessible name simplifies maintenance, prevents bugs, and reduces language
   translation requirements."* Preference order: native `<label>` →
   `aria-labelledby` → `aria-label` —
   https://www.w3.org/WAI/ARIA/apg/practices/names-and-descriptions/
   **Test:** `getByLabelText(/email/i)` — it fails if the label is missing or
   unassociated.
   ⚠️ `placeholder` is **not** a label. `LoginStub.tsx` currently uses
   `placeholder="Email"` / `placeholder="Password"` with no `<label>`: the
   placeholder vanishes on input, is skipped by some screen readers, and fails
   WCAG 3.3.2. This is the concrete a11y gap in the current code.
2. **Errors are identified in text.** WCAG 2.2 SC **3.3.1 Error Identification
   (Level A)**: *"If an input error is automatically detected, the item that is in
   error is identified and the error is described to the user in text."* —
   https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html
   Colour alone (`text-destructive`) does not satisfy it; the text must exist and
   the erroring field must be identifiable, which means `aria-invalid` +
   `aria-describedby` pointing at the message.
   **Test:** assert the message node exists and that the input's
   `aria-describedby` resolves to it.
3. **Async status changes are announced.** MDN on `aria-live`: `polite`
   "should be presented at the next graceful opportunity"; `assertive` updates
   "have the highest priority and should be presented to the user immediately",
   with the warning *"don't use the `assertive` value unless the interruption is
   imperative."* Critically, *"the `aria-live` attribute is set on an **empty**
   element. When an update to the page occurs, the empty element with that
   `aria-live` attribute should be updated"* — **the region must already be in the
   DOM before the content changes**, or nothing is announced. `role="status"` is
   an implicit polite region; `role="alert"` is implicitly assertive, and "if the
   updated information is an `alert`, the `aria-live` attribute is not needed" —
   https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-live
   **Convention:** render the login error container *always*, empty when there is
   no error — conditional `{error && <p>}` mounts a fresh node and is the single
   most common reason live regions silently do nothing.
   **Test:** `getByRole('alert')` / `getByRole('status')`.
4. **Focus management on route transitions.** SPA navigation does not move focus,
   so a redirect through the `RequireAuth` guard (§4.5) strands the screen reader
   at the old position. Move focus to the new view's heading (`tabIndex={-1}` +
   `.focus()`), and on failed login return focus to the first invalid field.
   **Test:** assert `document.activeElement`.

Note the `useId` prefix change in React 19.2 (§1.6) makes generated IDs valid CSS
selectors, which is convenient for the `aria-describedby`/`htmlFor` wiring above.

---

### 8. Outdated practices — the carry-over risk list

Ranked by likelihood the team writes it from muscle memory.

| # | Habit from | Now wrong because | Do instead |
|---|---|---|---|
| 1 | `tailwind.config.js`, `darkMode: 'class'`, `content: [...]` | Tailwind v4 has no JS config; theme is `@theme` in CSS, dark mode is `@custom-variant` | §6.1, §6.4 |
| 2 | `isLoading` from a query | v5 renamed it to `isPending`; `isLoading` **still exists with a new meaning** (`isPending && isFetching`) — compiles, misbehaves | `isPending` (§5.1) |
| 3 | `onSuccess`/`onError` on `useQuery` | removed in v5, **silently no-ops** | derive in render, or use `useEffect` on `data` (§5.1) |
| 4 | `npm i react-router-dom` | v7 made it a 1-dep re-export shim; **no v8 was ever published** | `react-router`; `RouterProvider` from `react-router/dom` (§4.2) |
| 5 | `forwardRef` wrapper on every leaf component | React 19 passes `ref` as an ordinary prop; `forwardRef` is deprecated | `function C({ ref, ...p })` (§1.3) |
| 6 | `import { act } from 'react-dom/test-utils'` | `react-dom/test-utils` was **removed** in React 19 | `import { act } from 'react'` (§1.4) |
| 7 | `babel: { plugins: [...] }` in `@vitejs/plugin-react` | v6 dropped Babel entirely; the option does not exist | `@rolldown/plugin-babel` (§3.2) |
| 8 | `baseUrl` + `paths` in tsconfig (shadcn's own docs still say this) | `baseUrl` deprecated in TS 6, hard error in TS 7; unnecessary with `paths` since TS 4.1 | `paths` alone (§2.3) |
| 9 | `logger: {...}` on a test `QueryClient` | removed in v5 | `retry: false` only (§5.4) |
| 10 | `"moduleResolution": "node"` | deprecated in TS 6 | `"bundler"` (§2.4) |
| 11 | `.eslintrc` + `plugin:react-hooks/flat/recommended` | `flat/recommended` removed in plugin 7.0; ESLint 9 is flat-config-only | `reactHooks.configs.recommended` (§7.3) |
| 12 | `propTypes` / `defaultProps` on function components | removed in React 19; `propTypes` **silently ignored** | TS types + default params (§1.4) |
| 13 | `optimizeDeps.esbuildOptions` | Vite 8 auto-converts but deprecates it | `optimizeDeps.rolldownOptions` (§3.1) |
| 14 | `enum` in TS | `erasableSyntaxOnly: true` is set — enums emit runtime code | `as const` object + union type (§2.4) |
| 15 | `placeholder` as the only label | fails WCAG 3.3.2; placeholder disappears on input | `<label htmlFor>` (§7.4) |
| 16 | `{error && <p role="alert">…}` | live region must pre-exist in the DOM to be announced | always-rendered, empty when no error (§7.4) |
| 17 | React Router "library mode" | not a term in current docs | declarative / data / framework (§4.3) |
| 18 | `vite preview` as a smoke-test for prod hosting | *"Do not use this as a production server"*; it also masks missing SPA fallback | test the real host's rewrite rule (§3.4) |

---

## What this means for Dmitri

Mapped to files that exist today.

| Area | Current state | Recommendation |
|---|---|---|
| `frontend/tsconfig.app.json` | no `strict`; on only via the TS 6.0 default. `types`, `paths`-without-`baseUrl`, `erasableSyntaxOnly`, `verbatimModuleSyntax` all correct | **Add `"strict": true` explicitly.** Consider `noUncheckedIndexedAccess`, `isolatedModules` (§2.2, §2.4) |
| `frontend/package.json` | `typescript: ~6.0.2` → resolves 6.0.3; TS 7.0.2 is npm `latest` | Fine to stay. Record the pin as deliberate so a future `npm install typescript` doesn't jump majors silently (§2.1) |
| `frontend/vite.config.ts` | minimal: `react()`, `tailwindcss()`, `@` alias | Correct and idiomatic for Vite 8. Nothing to change. The `@` alias duplicates `tsconfig.app.json`'s `paths` — Vite 8 added tsconfig-paths support, but the explicit alias is unambiguous; keep it (§3.1) |
| `frontend/vitest.config.ts` | duplicates plugins/alias, injects `VITE_API_URL` | Works. The duplication is the standard cost of a separate Vitest config; leaving it is the surgical choice |
| `frontend/src/App.tsx` | `useEffect` + 3-state `useState` for boot refresh | **Move to `useQuery({ queryKey: ['session'], retry: false })`.** Fixes the StrictMode double-refresh against a rotating refresh token, and yields the `pending/error/success` union the route guard needs (§1.5, §5.5) |
| `frontend/src/pages/LoginStub.tsx` | manual `useState` for email/password/error; no labels; conditional error `<p>` | **`useActionState` + `<form action={...}>`** for pending/error/submit. **Add `<label htmlFor>`** (placeholders are not labels). **Always render the error container** with `role="alert"`, empty when clean (§1.1, §7.4) |
| `frontend/src/api/instances.ts` | split `apiClient` / `authClient`, `withCredentials` only on auth | Matches the axios research note's recommendation. Keep. Consider typing `ImportMetaEnv.VITE_API_URL` and asserting at load so a missing var fails loudly (§3.3) |
| `frontend/src/api/client.ts` | single-flight 401→refresh, `_retry` guard, `window.location.href = '/login'` | Correct shape per ADR-008. Once React Router lands, the hard `window.location.href` full-page reload should stay — it is the deliberate teardown on refresh failure — but it must be paired with `queryClient.clear()` so no cache survives into the next session (§5.5) |
| `frontend/src/index.css` | `:root` raw tokens + `@theme inline` mapping + `@custom-variant dark` | Textbook-correct Tailwind v4. **`inline` is load-bearing — do not remove it** (§6.3) |
| `frontend/eslint.config.js` | spreads `reactHooks.configs.recommended.rules` (16 rules incl. compiler) | Working and current. Be aware the compiler rules are now in `recommended` and will flag render-purity issues in new code (§7.3) |
| `frontend/src/types/openapi.d.ts` + `src/api/auth.ts` | generated, committed; aliased at the API module top | Exactly the right pattern. Enforce: aliases never leak past `src/api/` (§7.2) |
| **Router decision** | ADR-008 (2026-07-10) picked v7 "modo library" | **Two things to record:** (a) v8 shipped 2026-06-17 and its `react >= 19.2.7` floor is already met here; (b) "library mode" isn't current terminology — the ADR's intent maps to *declarative*, but the docs (and this note) recommend *data mode*'s object route table **without loaders**, which preserves the ADR's "TanStack Query owns fetching" constraint (§4.1, §4.3) |
| **Route guards** | not yet written | Pathless layout route rendering `<Outlet />` or `<Navigate replace state={{from: location}} />`. `replace` and `state` are both non-optional in practice (§4.5) |
| **Query keys** | not yet established | Coarse→fine arrays from a per-domain factory module, so ADR-008's "Scan now" flow invalidates `['scans']` / `['agents']` / `['findings']` by prefix (§5.2) |
| **Test QueryClient** | none yet | Fresh client per test, `retry: false`. No `logger`, no `gcTime: Infinity` (Vitest, not Jest) (§5.4) |

---

## Decision inputs (concrete)

| Input | Value | Source |
|---|---|---|
| TypeScript `latest` on npm | **7.0.2** (2026-07-08); 6.0.3 is the repo's resolved version | npm registry, verified 2026-07-28; devblogs "Announcing TypeScript 7.0" |
| TS 6.0 changed defaults | `strict: true`, `module: esnext`, `target: es2025`, `types: []`, `noUncheckedSideEffectImports: true`, `rootDir: "."` | devblogs "Announcing TypeScript 6.0" |
| TS 6.0 deprecations | `baseUrl`, `moduleResolution node`, `target es5`, `downlevelIteration`, AMD/UMD/SystemJS; hard errors in 7.0 | same |
| Vite 8 bundler | **Rolldown + Oxc** replace Rollup + esbuild; Lightning CSS for CSS minification | vite.dev/guide/migration |
| Vite 8 Node engines | `^20.19.0 \|\| >=22.12.0` (unchanged from v7) | `npm view vite@8.1.5 engines` |
| Vite 8 default browsers | Chrome/Edge ≥111, Firefox ≥114, Safari ≥16.4 (Baseline WA @ 2026-01-01) | vite.dev/guide/build |
| `@vitejs/plugin-react` v6 | **no Babel dependency, `babel` option removed**, requires Vite ^8.0.0, no auto `resolve.dedupe` | plugin-react CHANGELOG; `npm view` peerDeps |
| Vite env exposure | only `VITE_`-prefixed vars reach the client; `*.local` must be gitignored; **no secrets in `VITE_*`** | vite.dev/guide/env-and-mode |
| `vite preview` | *"Do not use this as a production server as it's not designed for it"* | vite.dev/guide/cli |
| React Router `latest` | **8.3.0** (v8.0.0 → 2026-06-17); v7 branch alive at 7.18.2 (2026-07-28) | npm registry, verified 2026-07-28 |
| React Router v8 peer | **`react >= 19.2.7`** — met by this repo's `react@19.2.8` | `npm view react-router@8.3.0 peerDependencies` |
| `react-router-dom` | v7: 1-dependency re-export shim. **v8: never published** | `npm view react-router-dom@7.18.2 dependencies`; react-router CHANGELOG |
| Router modes | declarative / data / framework — **"library mode" is not a current term** | reactrouter.com/start/modes |
| Route guard idiom | pathless layout route → `<Outlet />` or `<Navigate replace state>`; no built-in guard API in a client SPA | reactrouter.com/api/components/Navigate; /start/data/routing |
| TanStack Query v5 renames | `isLoading`→`isPending`, `cacheTime`→`gcTime`, `useErrorBoundary`→`throwOnError`; query `onSuccess`/`onError` **removed**; object-only signature | tanstack.com migrating-to-v5 |
| TanStack Query defaults | `staleTime: 0`, `gcTime` 5 min, **3 retries with exponential backoff**, refetch on mount/focus/reconnect | tanstack.com important-defaults |
| Test QueryClient | `retry: false`, **fresh client per test**; `gcTime: Infinity` is a Jest-only workaround | tanstack.com testing guide |
| Logout | `queryClient.clear()` — *"clears all connected caches"* (not `invalidateQueries`, which refetches) | tanstack.com QueryClient reference |
| Query keys | array at top level; object key order irrelevant, **array order significant**; invalidation is prefix-based by default | tanstack.com query-keys, query-invalidation |
| Tailwind v4 config | `@theme` in CSS replaces `tailwind.config.js`; `@theme inline` required when a token references another variable; `@custom-variant` for class-based dark mode | tailwindcss.com/docs/theme, /adding-custom-styles |
| React 19 removals | `propTypes`/`defaultProps` (fn), legacy context, string refs, `createFactory`, `react-dom/test-utils`, `ReactDOM.render`/`hydrate`/`findDOMNode`, UMD builds | react.dev 19 upgrade guide |
| React 19 `ref` | ordinary prop; **`forwardRef` deprecated and will be removed** | react.dev/blog/2024/12/05/react-19 |
| `use()` caveat | promises **must be cached**; a promise created in render re-suspends every render; no try/catch | react.dev/reference/react/use |
| `useFormStatus` caveat | must be called from a component rendered **inside** the `<form>`, not the one rendering it | react.dev useFormStatus reference |
| StrictMode dev double-invoke | render bodies, `useState`/`useMemo`/`useReducer` initialisers & updaters, Effects (setup→cleanup→setup), ref callbacks. Dev only | react.dev/reference/react/StrictMode |
| `eslint-plugin-react-hooks` 7 | flat `recommended` is default and now carries 16 rules incl. React Compiler rules; `flat/recommended` and `recommended-latest-legacy` removed in 7.0 | plugin CHANGELOG; verified against installed 7.1.1 |
| a11y: labels | native `<label>` preferred over `aria-label`; use visible text for the accessible name | W3C WAI ARIA APG, names-and-descriptions |
| a11y: errors | WCAG 2.2 **3.3.1 (Level A)** — "the item that is in error is identified and the error is described to the user **in text**" | w3.org WCAG22 error-identification |
| a11y: live regions | region must **pre-exist empty** in the DOM; `role="status"` = polite, `role="alert"` = assertive (no `aria-live` needed) | MDN aria-live |
| openapi-typescript | types only, zero runtime; emits `paths`/`components`/`operations`/`webhooks` | openapi-ts.dev/introduction |
