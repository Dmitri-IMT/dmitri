# POOP — Frontend scaffold (spec 014)

Append-only execution ledger. Each subagent (coder, test-engineer, reviewer) appends one
section before returning. The orchestrator appends only `STRUCTURAL_REEVAL` blocks.

---

## Task 1: Scaffold the Vite + React + TypeScript project and tooling baseline

**Order Given**: Create the greenfield `frontend/` Vite + React 19 + TypeScript project and the
CI-runnable tooling baseline per ARCHITECTURE.md §§ System context, Config constants, and New
files and naming (Root config + `package.json` scripts). Implement every Task 1 success
criterion. Do not add the API client/tokenStore/auth modules, openapi-typescript/gen:types,
Tailwind/shadcn, or Vitest/MSW/tests — those are dedicated later tasks. `App.tsx` must stay a
trivial placeholder.

**What, How, and Why**: Scaffolded with `npm create vite@latest frontend -- --template
react-ts`, then trimmed the generated template down to exactly the Target Files list: removed
the demo `README.md`, `src/App.css`, `src/assets/*`, `public/*`, and the `oxlint` linter the
current Vite template ships by default (the task requires `eslint.config.js`/`.prettierrc`
instead). Replaced `App.tsx`/`index.css`/`index.html` with trivial placeholder content (no
demo hero/counter markup). Added `.nvmrc` (`22`), `.env.example`
(`VITE_API_URL=http://localhost:8000`), `engines.node: "22.x"` in `package.json`, and a flat
ESLint 9 config (`typescript-eslint` + `eslint-plugin-react-hooks`/`react-refresh`, matching the
current official Vite React-TS template's recommended config) plus a minimal `.prettierrc`.
Added `.env` to `.gitignore` (the template's default only ignored `*.local`, `node_modules`,
`dist`).

Discovered the vanilla Vite template's `typecheck` idiom (`tsc --noEmit` against the root
solution `tsconfig.json`, which has `"files": []` and only project references) silently
type-checks nothing — confirmed by injecting a deliberate type error and getting exit 0.
Switched the `typecheck` script to `tsc -b --noEmit`, which walks the project references and
does report errors (verified non-zero exit on the same injected error). This is a root-cause
fix in the shared script, not a workaround.

**Decisions Made**:
- Used the official `create-vite react-ts` template as the base (matches ADR-008's Vite +
  React 19 + TypeScript decision) rather than hand-rolling config from scratch.
- Swapped the template's default `oxlint` for ESLint 9 flat config + Prettier, since the task's
  Target Files explicitly name `eslint.config.js` and `.prettierrc`.
- Kept `App.tsx` to a single trivial `<div>Dmitri</div>` — no router, no API calls, per the hard
  boundary in the task prompt.
- `typecheck` uses `tsc -b --noEmit` (not bare `tsc --noEmit`) so it actually type-checks the
  app/node project references instead of a no-op against an empty root config.

**Code Changed** (all created, under `frontend/`, greenfield):
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/.nvmrc`
- `frontend/.env.example`
- `frontend/.gitignore`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/tsconfig.app.json`
- `frontend/tsconfig.node.json`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/index.css`
- `frontend/eslint.config.js`
- `frontend/.prettierrc`

---

## Task 1: test-engineer

**Order Given**: Task 1 is the greenfield tooling baseline only. Vitest/MSW and all behavioral
tests are explicitly deferred to Task 7. Verify the tooling scripts (`build`, `typecheck`,
`lint`, `format:check`) act as real, non-interactive, non-zero-on-failure gates; confirm no
`test` script or test files were added prematurely; add no test files or dependencies.

**What, How, and Why**: Task 1 has no unit-test surface — it produces a placeholder `App` and
tooling config, not application behavior, so there is nothing for Vitest to exercise (that
harness lands in Task 7 per TASKS.md). Verification therefore targeted the tooling gates
themselves, run headless from `frontend/`:
- `npm run build`, `npm run typecheck`, `npm run lint`, `npm run format:check` each ran clean
  (exit 0) on the current tree.
- Each gate was then proven to actually fail: a type error in `App.tsx` made `typecheck` exit 2
  and `build` exit 2; an unused variable made `lint` exit 1; an unformatted line made
  `format:check` exit 1. Each injected fault was reverted immediately after observing the
  failing exit code, and all four commands were re-run clean to confirm the tree was restored.
- Confirmed no `test` script exists in `package.json`, no `*.test.*`/`*.spec.*` files exist
  under `src/`, and no `vitest`/`msw` references exist in `package.json` — the Task 7 boundary
  is intact.

**Decisions Made**: No test files or dependencies were added, per the task's explicit scope
boundary (Vitest + MSW + all behavioral tests belong to Task 7). Verification was done by
transient fault injection (temp-edit, observe non-zero exit, revert) rather than by adding
permanent negative-path fixtures, since Task 1 is a tooling task with no application logic to
regression-test and no test harness exists yet to house such fixtures.

**Code Changed**: None. No test files were created or modified for Task 1.

## Task 1: reviewer

**Order Given**: Review the `frontend/` scaffold (Task 1) against every success criterion,
scoped npm gates (`npm ci`, `build`, `typecheck`, `lint`, `format:check`), verify the
`tsc -b --noEmit` vs bare `tsc --noEmit` claim, verify scope boundaries (no API client/
tokenStore/auth, no openapi-typescript/gen:types, no Tailwind/shadcn, no Vitest/MSW/test
script, trivial `App.tsx`, no react-router, dev port 5173, `.env.example`/`.gitignore`/
`engines.node`/`.nvmrc` content), and confirm exactly the Task 1 Target Files exist.

**What, How, and Why**: Ran `rm -rf node_modules && npm ci` (installed clean from the
committed `package-lock.json`, exit 0). Ran `npm run build`, `typecheck`, `lint`,
`format:check` — all exit 0. Verified each gate is a real, non-zero-on-failure check by
injecting transient faults and reverting: a type error made `build`/`typecheck` exit 2 via
`tsc -b --noEmit`, while the same error under bare `npx tsc --noEmit` (root composite config)
exited 0 — confirms the coder's stated root-cause fix is correct and necessary. An unused var
made `lint` exit 1; unformatted code made `format:check` exit 1. Started the dev server and
confirmed it serves on `http://localhost:5173` unmodified. Inspected `App.tsx` (trivial
`<div>Dmitri</div>`, no router/API/auth), `main.tsx` (mounts `App`, no `QueryClientProvider` —
correctly deferred, not part of Task 1's criteria), `.env.example`
(`VITE_API_URL=http://localhost:8000`), `.gitignore` (covers `.env`, `node_modules`, `dist`),
`.nvmrc` (`22`), `package.json` (`engines.node: "22.x"`, scripts named exactly `dev`, `build`,
`typecheck`, `lint`, `format:check`, no `test`/`gen:types` yet). Grepped `src/` and
`package.json` for `axios`, `react-router`, `tailwind`, `shadcn`, `vitest`, `msw`, `openapi` —
no hits. `find src -type f` shows exactly `App.tsx`, `main.tsx`, `index.css`. `git status
--porcelain frontend` shows the whole directory untracked (new feature, nothing committed yet)
with no target-file omissions. No `# ponytail:` markers present in touched files.

**Decisions Made**: APPROVE. Every Task 1 success criterion is met, all five gate commands are
real (proven via fault injection) and pass, scope boundaries are respected (no
Task 2/3/4/5/7 work pulled forward), and the Target Files list matches exactly. The
`tsc -b --noEmit` deviation from the vanilla template's bare `tsc --noEmit` is justified and
verified as a genuine bug fix, not scope creep.

**Code Reviewed**:
- frontend/package.json
- frontend/.nvmrc
- frontend/.env.example
- frontend/.gitignore
- frontend/vite.config.ts
- frontend/tsconfig.json
- frontend/tsconfig.app.json
- frontend/tsconfig.node.json
- frontend/index.html
- frontend/src/main.tsx
- frontend/src/App.tsx
- frontend/src/index.css
- frontend/eslint.config.js
- frontend/.prettierrc

## Task 2 — Generate and commit the OpenAPI types from the frozen contract

**Order Given**: Wire `openapi-typescript` type generation against the frozen contract at
`../contracts/openapi/openapi.yaml` (relative to `frontend/`), add a `gen:types` script writing
into `frontend/src/types/`, run it, commit the generated file, verify idempotency, and confirm
`npm run typecheck` passes with no hand-written interface duplicating a contract body. No API
client / tokenStore / auth modules (Task 5), no contract edits.

**What, How, and Why**: Added `openapi-typescript` as a devDependency via
`npm install -D openapi-typescript --legacy-peer-deps` (the project's TypeScript `~6.0.2` is
newer than the tool's declared `^5.x` peer range; `--legacy-peer-deps` accepts the mismatch
without downgrading TypeScript, since openapi-typescript works fine against TS 6 in practice).
Added the `gen:types` script to `frontend/package.json` exactly as specified in
`ARCHITECTURE.md`'s script table: `openapi-typescript ../contracts/openapi/openapi.yaml -o
src/types/openapi.d.ts`. Ran it to produce `frontend/src/types/openapi.d.ts`. Verified
idempotency by diffing a copy of the first-run output against a second run on the unchanged
contract — no diff. Ran `npm run typecheck` (passes) and `npm run lint` (passes) with the
generated file present. No new hand-written interfaces were added since Task 2 only touches the
generation pipeline.

**Decisions Made**:
- Used `--legacy-peer-deps` for the `npm install` rather than downgrading TypeScript, since
  Task 1's TS version choice is out of this task's scope and openapi-typescript's generated
  output type-checks cleanly under TS 6.
- Left `package.json`/`package-lock.json`/`src/types/openapi.d.ts` staged-but-uncommitted in git
  (per repo convention: only commit when explicitly asked); all of `frontend/` remains untracked
  from a prior Task 1 state, so "commit" here is interpreted as "materialize the file on disk in
  its final, verified form," with the actual `git commit` left to the user/orchestrator.
- Did not touch TASKS.md task-status table; left Status as-is for the reviewer gate to update.

**Code Changed**:
- Modified: `/Users/gui/Projects/dmitri/frontend/package.json`
- Modified: `/Users/gui/Projects/dmitri/frontend/package-lock.json`
- Created: `/Users/gui/Projects/dmitri/frontend/src/types/openapi.d.ts`

## Task 2 — test-engineer

**Order Given**: No unit tests to write for Task 2 (Vitest/MSW harness is Task 7, out of
scope). Instead verify, as gates: (a) clean `npm ci` reproducibility from the committed
lockfile with no special flags, (b) `gen:types` idempotency, (c) `npm run typecheck` passes
with the generated file present. Do not modify code or add test files.

**What, How, and Why**: Ran `rm -rf node_modules && npm ci` with no flags — exit code 1,
ERESOLVE conflict: `openapi-typescript@7.13.0` declares `peer typescript@^5.x` but the root
project pins `typescript@~6.0.2` (resolved `6.0.3`), which also collides with
`@typescript-eslint/eslint-plugin`'s `<6.1.0` peer ceiling. This reproduces exactly what the
coder's POOP entry described working around with `--legacy-peer-deps`. Re-ran
`npm ci --legacy-peer-deps` to unblock the remaining checks (exit 0). Ran `npm run gen:types`
twice and compared `md5` of `src/types/openapi.d.ts` before/after the second run — identical
hash, confirming idempotent output. Noted `git diff --stat -- src/types` is empty but
uninformative here since the entire `frontend/` tree is currently untracked in git (nothing to
diff against); the md5 comparison is the load-bearing idempotency check. Ran
`npm run typecheck` (`tsc -b --noEmit`) with the generated file present — exit 0, no errors.

**Decisions Made**: No test files added — this task's deliverable is a generation script and
a committed artifact, not application logic; Task 7 owns all Vitest/MSW behavioral coverage
for the API layer that will consume these types. Treated the `npm ci` ERESOLVE failure purely
as a verification finding for the reviewer, not something to fix here (per task instructions):
**Task 8's CI will break** the moment it runs a plain `npm ci` (per its own success criteria,
"no special flags"), because the committed `package.json`/`package-lock.json` require
`--legacy-peer-deps` to install cleanly. This is a real conflict between TypeScript `~6.0.2`
(a Task 1 decision) and `openapi-typescript@^7.13.0`'s peer range, and needs to be resolved
before Task 8 lands — either by pinning a TypeScript version openapi-typescript's peer range
accepts, upgrading openapi-typescript if a newer major supports TS 6, or some other approach
the reviewer/architect should decide on.

**Code Changed**: None. No test files were created or modified for Task 2 (deferred to
Task 7 per scope).

## Task 2 — reviewer

**Order Given**: Review `frontend/` Task 2 work (openapi-typescript type generation) against
every Task 2 success criterion. Run scope gates in `frontend/`: clean `npm ci` (no flags),
`gen:types` twice for idempotency (hash comparison), `typecheck`, `lint`. Adjudicate the known
`--legacy-peer-deps` / ERESOLVE concern the test-engineer flagged, and if `npm ci` fails plain,
REJECT with a concrete least-invasive fix direction.

**What, How, and Why**: Reproduced the test-engineer's finding independently: `cd frontend &&
rm -rf node_modules && npm ci` (no flags) fails with `ERESOLVE` — `openapi-typescript@7.13.0`
declares `peer typescript@"^5.x"` but the root project pins `typescript@~6.0.2` (resolved
`6.0.3`); `@typescript-eslint/eslint-plugin@8.65.0` additionally caps `typescript@<6.1.0`,
so downgrading isn't clean either. Checked whether a newer `openapi-typescript` major relaxes
the peer range (`npm view openapi-typescript versions`) — `7.13.0` is latest, no version bump
available that accepts TS 6. Tested the least-invasive fix candidate: committing
`frontend/.npmrc` with `legacy-peer-deps=true` — `rm -rf node_modules && npm ci` then succeeds
with exit 0 and no special flags on the command line, which satisfies Task 8's "plain `npm ci`"
CI requirement. Reverted the test `.npmrc` afterward (reviewer does not modify application
code); `frontend/` remains untracked so nothing was actually left behind either way — the fix
still needs to be applied by a coder.
Did not proceed to `gen:types`/`typecheck`/`lint` gates as blocking further review is moot: the
first gate (clean `npm ci`) already fails the success criterion, so the task cannot be approved
regardless of downstream gate results.

**Decisions Made**: REJECT. The success criterion (and Task 8's CI, which the test-engineer
correctly flagged as broken by this) requires `npm ci` to install cleanly from the committed
lockfile with standard commands. It does not. The coder's `POOP.md` decision to use
`--legacy-peer-deps` only at `npm install` time, without persisting that behavior anywhere
`npm ci` reads, means the escape hatch used to generate the lockfile isn't available to anyone
(including CI) who runs `npm ci` afterward. Recommended fix: commit a `frontend/.npmrc`
containing `legacy-peer-deps=true` — this is the least invasive of the three options in scope
(no newer `openapi-typescript` major exists that declares a TS 6-compatible peer range, so
bumping the tool isn't available; downgrading `typescript` to `^5.x` would reopen Task 1's
already-reviewed and approved TypeScript version decision, which is out of Task 2's scope and a
bigger blast radius). Verified experimentally that committing `.npmrc` makes plain `npm ci`
succeed end-to-end.

**Code Reviewed**:
- /Users/gui/Projects/dmitri/frontend/package.json
- /Users/gui/Projects/dmitri/frontend/package-lock.json
- /Users/gui/Projects/dmitri/frontend/src/types/openapi.d.ts

---

## Task 2 (redo after rejection): Fix `npm ci` ERESOLVE failure

**Order Given**: Fix the review rejection — a clean `npm ci` (no flags, matching Task 8's CI) fails
with ERESOLVE because `openapi-typescript@7.13.0` peers on `typescript@^5.x` and
`@typescript-eslint/eslint-plugin@8.65.0` caps `typescript@<6.1.0`, while the scaffold pins
`typescript@~6.0.2`. Reviewer-verified fix: commit `frontend/.npmrc` with
`legacy-peer-deps=true`. Do not downgrade TypeScript or bump openapi-typescript.

**What, How, and Why**: Created `frontend/.npmrc` containing `legacy-peer-deps=true` so `npm ci`
honors legacy peer resolution without requiring a CLI flag (npm reads `.npmrc` automatically,
including in CI). Verified with `rm -rf node_modules && npm ci` (no flags) — exit 0. The existing
`package-lock.json` was already consistent under this setting (no ERESOLVE, no lockfile rewrite
needed), so it was left untouched. Re-ran all Task 2 success criteria: `npm run gen:types` twice
produced byte-identical `src/types/openapi.d.ts` (same sha1 both runs), `npm run typecheck` exit
0, `npm run lint` exit 0. Confirmed `.npmrc` is not matched by `frontend/.gitignore`
(`git check-ignore -v .npmrc` exit 1, not ignored).

**Decisions Made**: Used the reviewer-verified fix exactly as specified (`.npmrc` with
`legacy-peer-deps=true`) rather than any lockfile regeneration, since `npm ci` already succeeded
without needing `npm install` to rewrite `package-lock.json`. Left TypeScript version and
openapi-typescript version untouched per explicit instruction.

**Code Changed**:
- Created: `frontend/.npmrc`

## Task 2 (re-review after fix) — reviewer

**Order Given**: Re-review (authoritative gate) for Task 2 after fix for prior REJECT
(`frontend/.npmrc` with `legacy-peer-deps=true` committed to resolve `npm ci` ERESOLVE). Verify
every Task 2 success criterion by running gates directly in `frontend/`.

**What, How, and Why**: Confirmed `frontend/.npmrc` exists, contains `legacy-peer-deps=true`,
and is not gitignored (`git check-ignore -v .npmrc` → exit 1, not ignored). Ran
`rm -rf node_modules && npm ci` with no flags — exit 0, clean install (this is exactly what
Task 8's CI will run). Ran `npm run gen:types` twice and compared MD5 of
`src/types/openapi.d.ts` before/after — identical hash (`3c08bec2c20f49bd908e1a440f200b5d`),
confirming idempotent generation. Ran `npm run typecheck` (`tsc -b --noEmit`) — exit 0. Ran
`npm run lint` (`eslint src`) — exit 0. Grepped `src/` for hand-written `interface *Request`/
`interface *Response` outside `openapi.d.ts` — none found, satisfying the "no duplicate
hand-written body models" criterion. `hardware-agent/` (`uv run pytest` / `uv run ruff check`)
is not applicable to this frontend-only task — no Python files were touched; noted explicitly
rather than silently skipped, per review instructions.

**Decisions Made**: APPROVE. All three Task 2 success criteria are met: (1) `package.json` has
`openapi-typescript` devDependency and the exact `gen:types` script reading the frozen contract
and writing into `src/types/`; (2) `npm run gen:types` is idempotent (byte-identical second
run) and the file is present on disk; (3) `npm run typecheck` passes with the file present, and
no hand-written interface duplicates a contract body. The previously rejected blocker — plain
`npm ci` failing with ERESOLVE — is resolved by the committed `.npmrc`, which is tracked (not
gitignored) and applies automatically in CI with no special flags needed on the command line,
satisfying Task 8's "no special flags" requirement. No `# ponytail:` marker comments were found
in the touched files, so no stripping was needed.

**Code Reviewed**:
- /Users/gui/Projects/dmitri/frontend/package.json
- /Users/gui/Projects/dmitri/frontend/package-lock.json
- /Users/gui/Projects/dmitri/frontend/src/types/openapi.d.ts
- /Users/gui/Projects/dmitri/frontend/.npmrc

## Task 3: Initialize Tailwind CSS v4 and shadcn/ui with button + input

**Order Given**: Configure Tailwind CSS v4 via its Vite-first integration and initialize
shadcn/ui, adding exactly the `button` and `input` components; keep light-only per ADR-008
locked decision 7; app must still build and type-check with a Tailwind-styled element
rendering; do not build the API client, tokenStore, auth, pages, or tests.

**What, How, and Why**: Installed `tailwindcss` + `@tailwindcss/vite` and wired the plugin into
`vite.config.ts`; made `src/index.css` the Tailwind entry (`@import 'tailwindcss';`, plus what
`shadcn init` appended). Added the `@/*` path alias (`tsconfig.app.json` `paths`, matching
`resolve.alias` in `vite.config.ts`) since the current shadcn CLI requires it to resolve
`components.json` aliases. Ran `npx shadcn@latest init -t vite -b radix -p nova -y` — the
current shadcn CLI (v4.13) replaced the old single `init` flow with a base-library
(`radix`/`base`/`aria`) and visual-preset (`nova`/`vega`/...) selection; picked `radix` (the
long-standing shadcn primitive base) and `nova` (the CLI's own default preset) rather than
inventing a custom theme, keeping this a stock, unopinionated init. The CLI wrote its output
under a literal `./@/...` directory (alias not resolved to a real filesystem path by the
installed CLI version) — moved `button.tsx`/`utils.ts` into `src/components/ui/` and
`src/lib/` and deleted the stray `@/` directory. Added exactly `input` via
`npx shadcn@latest add input -y`, same move/cleanup. Gave `App.tsx` one Tailwind utility class
(`p-4 text-xl font-semibold text-primary`) on the existing placeholder div to prove Tailwind is
live, without adding any API/auth/routing logic. Removed `"baseUrl": "."` that I had first added
alongside `paths` in `tsconfig.app.json` — TS flagged it as deprecated (TS5101) under
`moduleResolution: bundler`, and `paths` resolves fine without it.

**Decisions Made**: Kept the CLI's default `.dark` CSS variables and `dark:` Tailwind variants
in the generated `index.css`/`button.tsx`/`input.tsx` rather than stripping them — no dark-mode
toggle or `.dark` class is wired anywhere in the app, so the app renders light-only in practice
(per locked decision 7); fighting the stock generated output to remove inert CSS custom
properties was judged not worth the diff. Left `shadcn` itself and its preset deps
(`@fontsource-variable/geist`, `tw-animate-css`, `lucide-react`, `radix-ui`,
`class-variance-authority`, `tailwind-merge`) as installed by `shadcn init` — these are the
CLI's own baseline for the `button`/`input` components and preset, not hand-added extras.
Left `frontend/src/types/openapi.d.ts` prettier-failing as-is (pre-existing, generated by Task
2's `gen:types`, outside this task's target files) rather than reformatting a file this task
doesn't own.

**Code Changed**:
- /Users/gui/Projects/dmitri/frontend/vite.config.ts (modified — `@tailwindcss/vite` plugin, `@` alias)
- /Users/gui/Projects/dmitri/frontend/tsconfig.app.json (modified — `paths` alias)
- /Users/gui/Projects/dmitri/frontend/src/index.css (modified — Tailwind entry + shadcn theme tokens)
- /Users/gui/Projects/dmitri/frontend/src/App.tsx (modified — Tailwind class on placeholder)
- /Users/gui/Projects/dmitri/frontend/components.json (created — shadcn init)
- /Users/gui/Projects/dmitri/frontend/src/components/ui/button.tsx (created)
- /Users/gui/Projects/dmitri/frontend/src/components/ui/input.tsx (created)
- /Users/gui/Projects/dmitri/frontend/src/lib/utils.ts (created — shadcn `cn` helper)
- /Users/gui/Projects/dmitri/frontend/package.json (modified — tailwindcss, @tailwindcss/vite, shadcn CLI + preset deps)
- /Users/gui/Projects/dmitri/frontend/package-lock.json (modified)

## Task 3: Test-engineer scope — tooling gate verification

**Order Given**: Verify Task 3's build/lint/format gates directly (`npm ci`, `build`,
`typecheck`, `lint`, `format:check`) and confirm exactly `button.tsx`/`input.tsx` under
`src/components/ui/`. The Vitest/MSW harness is Task 7's scope — no `test` script, no MSW, no
`*.test.tsx` files here.

**What, How, and Why**: Task 3 adds no runtime logic (config files, generated shadcn
components, a CSS import) — there is no unit-testable behavior surface for this task; the
project's own test harness doesn't exist yet (Task 7). So instead of writing tests, ran the
gates the task's success criteria name, in `frontend/`, and report results as findings:
- `rm -rf node_modules && npm ci` (no flags) — exit 0.
- `npm run build` — exit 0 (Vite build succeeds, Tailwind CSS emitted in
  `dist/assets/index-*.css`).
- `npm run typecheck` (`tsc -b --noEmit`) — exit 0.
- `npm run lint` (`eslint src`) — exit 0, 1 warning: `react-refresh/only-export-components` on
  stock generated `src/components/ui/button.tsx:67` (the `buttonVariants` export alongside the
  component — standard shadcn output, a warning not an error, acceptable per task instructions).
- `npm run format:check` (`prettier --check src`) — **exit 1**. Flags exactly one file:
  `src/types/openapi.d.ts` (Task 2's generated output; Task 3 did not touch it). No file under
  Task 3's target list (`components.json`, `src/index.css`, `button.tsx`, `input.tsx`,
  `package.json`, `vite.config.ts`) is flagged.
- `ls src/components/ui/` — exactly `button.tsx` and `input.tsx`, no other shadcn component.

**Decisions Made**: This is a reportable finding for the reviewer, not something to fix here
(scope forbids touching production/generated files, and Task 8's CI runs `format:check`
verbatim). `format:check` is currently non-zero in `frontend/` solely because of
`src/types/openapi.d.ts` — a Task 2 artifact outside Task 3's target files — not because of
anything Task 3 added. Task 8 (CI job) as currently scoped runs `npm run format:check` as a
required step; if `openapi.d.ts` remains unformatted, that step will fail CI once Task 8 lands,
regardless of Task 3's own changes. Flagging for the reviewer/orchestrator to decide the fix
owner (most likely: either add a `.prettierignore` entry for generated types, or have Task 2 /
the `gen:types` step run `prettier --write` on its output). Did not add Vitest/MSW/a `test`
script or any `*.test.tsx` file — that harness is explicitly Task 7's scope per task
instructions; Task 3 has no other unit-testable behavior to cover.

**Code Changed**: None (test files). No source or config files were modified; this task
produced no test artifacts, only gate-verification results reported above.

## Task 3 (authoritative gate) — reviewer

**Order Given**: Authoritative review gate for Task 3 (Tailwind CSS v4 + shadcn/ui, button+input
only). Verify every Task 3 success criterion by running gates directly in `frontend/`; adjudicate
(1) `src/lib/utils.ts` not being in Target Files, and (2) `format:check` exit 1 on
`src/types/openapi.d.ts`.

**What, How, and Why**: Ran `rm -rf node_modules && npm ci` (no flags) — exit 0. Ran
`npm run build` — exit 0, Tailwind CSS emitted into `dist/assets/index-*.css`. Ran
`npm run typecheck` (`tsc -b --noEmit`) — exit 0. Ran `npm run lint` (`eslint src`) — exit 0,
one `react-refresh/only-export-components` warning on stock generated
`src/components/ui/button.tsx:67` (acceptable, stock shadcn output, warning not error). Ran
`npm run format:check` — exit 1, flags exactly `src/types/openapi.d.ts` only; no Task 3 target
file is flagged. Confirmed `vite.config.ts` wires `@tailwindcss/vite` and `src/index.css` is the
Tailwind entry (`@import 'tailwindcss';` plus shadcn theme tokens). Confirmed `components.json`
exists (shadcn init, style `radix-nova`). Confirmed `ls src/components/ui/` shows exactly
`button.tsx` and `input.tsx`, no other shadcn component. Confirmed no dark-mode toggle,
`ThemeProvider`, or `.dark` class application exists anywhere in `src/` (`grep -rn
"ThemeProvider|dark-mode|toggleDark|useDarkMode" src/` — no hits); the generated `.dark {}` CSS
variable block in `index.css` is inert dead CSS, never applied, so the app is light-only in
practice per ADR-008 locked decision 7. Confirmed `App.tsx` stays a trivial placeholder
(`<div className="p-4 text-xl font-semibold text-primary">Dmitri</div>`) — a Tailwind-styled
element renders, no API/auth/routing added. Confirmed no stray `@/` literal directory was left
by the shadcn CLI move (`find . -maxdepth 2 -name "@*"` outside `node_modules` — none). Grepped
touched files for `# ponytail:` markers — none found.

**Decisions Made**:
1. `src/lib/utils.ts` (the shadcn `cn()` helper) is standard, unavoidable shadcn CLI output —
   `npx shadcn add button`/`add input` always generates this file as the components' shared
   dependency. It is expected scope, not creep; ARCHITECTURE.md's own component table implies a
   `lib/` helper is part of a stock shadcn init. Not flagged.
2. `format:check` exit 1 is caused solely by `src/types/openapi.d.ts`, a Task 2 artifact Task 3
   never touches and Task 3's success criteria never mention `format:check`. All Task 3 target
   files are prettier-clean. This does not block Task 3. It is a tracked cross-task item: Task 8's
   CI will run `format:check` and fail on this generated file unless resolved first — recommend a
   committed `.prettierignore` covering `src/types/` (or equivalent generated-output exclusion),
   owned by a small Task 2 follow-up or folded into Task 8 before that job lands. Recording here so
   the orchestrator does not lose the thread.

APPROVE. All three Task 3 success criteria are met: Tailwind v4 via `@tailwindcss/vite` with
`src/index.css` as entry; `components.json` present with exactly `button.tsx`/`input.tsx` under
`src/components/ui/`; build/typecheck pass with a Tailwind-styled element rendering. Light-only
foundation confirmed (no dark-mode wiring). No CLAUDE.md orchestrator-parameter integration rule
applies to this frontend-only task (no `ScanRunner`/`ScanProgressScreen` involved). No
over-engineering found — the diff is stock CLI output plus the minimal wiring the task required.

**Code Reviewed**:
- /Users/gui/Projects/dmitri/frontend/vite.config.ts
- /Users/gui/Projects/dmitri/frontend/tsconfig.app.json
- /Users/gui/Projects/dmitri/frontend/src/index.css
- /Users/gui/Projects/dmitri/frontend/src/App.tsx
- /Users/gui/Projects/dmitri/frontend/components.json
- /Users/gui/Projects/dmitri/frontend/src/components/ui/button.tsx
- /Users/gui/Projects/dmitri/frontend/src/components/ui/input.tsx
- /Users/gui/Projects/dmitri/frontend/src/lib/utils.ts
- /Users/gui/Projects/dmitri/frontend/package.json
- /Users/gui/Projects/dmitri/frontend/package-lock.json

## Task 4: Implement the in-memory access-token store

- **Order Given**: Implement ONLY `frontend/src/api/tokenStore.ts` per ARCHITECTURE.md § In-memory
  token store contract and TRUTH.md's "access token lives in memory only" rule: expose
  `getAccessToken()`, `setAccessToken(token)`, `clearAccessToken()` over module-scoped state,
  never `localStorage`/`sessionStorage`/cookies/React state. No client.ts, auth.ts,
  interceptors, pages, or tests.

- **What, How, and Why**: Created `tokenStore.ts` holding a single module-level
  `let accessToken: string | null = null`, with the three named functions reading/writing/
  clearing it. Did not add `expires_in` metadata storage: ARCHITECTURE.md notes the store "may
  also hold" it, but no consumer in this task (or Task 5/6's stated criteria) reads it yet, and
  the task instructions explicitly cap the public surface at the three named functions —
  YAGNI, add it in Task 5 if the refresh/login flow actually needs to read it.

- **Decisions Made**:
  - Single-argument `setAccessToken(token: string)` matching the task's exact signature; no
    expiry metadata field, no getters/setters beyond the three named functions.
  - No exported types/interfaces — the store's shape is an implementation detail, not part of
    the module's contract.

- **Code Changed**:
  - Created: `frontend/src/api/tokenStore.ts`
  - Modified: `specs/014-frontend-scaffold/TASKS.md` (Task 4 status IN_PROGRESS -> DONE)

## Task 4 (test-engineer): Verification of tokenStore.ts

- **Order Given**: Verify `frontend/src/api/tokenStore.ts` satisfies Task 4 criteria via static
  inspection and typecheck/lint; no test files, since the Vitest+MSW harness is Task 7 and is out
  of scope to pull forward. Runnable unit coverage for this module is deferred to Task 7's
  `client.test.ts`, which exercises the token store transitively through the axios interceptor
  (reads via `getAccessToken`, writes via `setAccessToken`/`clearAccessToken` on
  login/refresh/logout paths).

- **What, How, and Why**: Read `src/api/tokenStore.ts` and confirmed via `grep -n export` it
  exports exactly `getAccessToken`, `setAccessToken`, `clearAccessToken`, backed by a single
  module-scoped `let accessToken: string | null = null` with no exported types. Ran
  `grep -niE "localStorage|sessionStorage|document\.cookie|useState|axios"` against the file —
  zero matches (grep exit 1), confirming no localStorage/sessionStorage/cookie/React-state/axios
  usage. Ran `npm run typecheck` (exit 0) and `npm run lint` (exit 0; the one warning present is
  in `src/components/ui/button.tsx`, an unrelated Task 3 file, not tokenStore.ts).

- **Decisions Made**: No test files created — vitest/msw are not installed and no `test` script
  exists yet (Task 7 scope); adding either would be out-of-scope harness work, not test authoring
  for this task. Verification relied on grep evidence plus the existing typecheck/lint scripts
  rather than new tooling.

- **Code Changed**: None. No test files created or modified.

## Task 4 (reviewer): Review gate for tokenStore.ts

- **Order Given**: Authoritative review gate for Task 4 (in-memory token store). Read TASKS.md
  Task 4, ARCHITECTURE.md § In-memory token store contract, TRUTH.md "Access token lives in
  memory only", and prior Task 4 POOP.md entries. Review `frontend/src/api/tokenStore.ts` against
  every success criterion; run `npm run typecheck` and `npm run lint`; verify exact exports,
  module-variable-only storage (grep for localStorage/sessionStorage/cookie/React
  state/axios), minimalism, and no hand-written contract types. Runnable tests legitimately
  deferred to Task 7.

- **What, How, and Why**: Read the file (13 lines: one module-scoped `let accessToken: string |
  null = null` plus `getAccessToken`/`setAccessToken`/`clearAccessToken`). Ran `grep -n "^export"`
  confirming exactly the three required exports. Ran
  `grep -niE "localStorage|sessionStorage|document\.cookie|useState|axios|interface|type "` —
  zero matches, confirming module-variable-only storage and no hand-written contract types. Ran
  `npm run typecheck` (exit 0) and `npm run lint` (exit 0 overall; one pre-existing warning in
  `src/components/ui/button.tsx`, a Task 3 file, unrelated to this task). Checked for
  `# ponytail:` markers in the file — none present.

- **Decisions Made**: APPROVE. All three Task 4 success criteria are met exactly: the three named
  functions over module-scoped state, no localStorage/sessionStorage/cookie/React-state/axios
  usage, and both gate commands pass. The implementation is maximally minimal — no speculative
  `expires_in` field, no exported types/interfaces, matching the ARCHITECTURE.md contract's
  required surface without adding anything the task didn't ask for. No CLAUDE.md
  orchestrator-parameter integration rule applies (frontend-only change, no
  ScanRunner/ScanProgressScreen involved). No over-engineering findings. No `# ponytail:` markers
  present to strip.

- **Code Reviewed**:
  - /Users/gui/Projects/dmitri/frontend/src/api/tokenStore.ts

## Task 5: Build the two Axios instances, auth resource module, and single-flight 401→refresh interceptor

- **Order Given**: Implement `frontend/src/api/client.ts` and `frontend/src/api/auth.ts` per
  ARCHITECTURE.md §§ Two-Axios-instance contract, Single-flight 401→refresh interceptor
  contract, and Auth endpoints consumed: two Axios instances (`apiClient` bare `withCredentials`
  default, `authClient` with `withCredentials: true`), a request interceptor attaching the
  Bearer token, a single-flight 401→refresh response interceptor on `apiClient` only, and
  `login`/`refresh`/`logout` in `auth.ts` as the sole callers of `authClient`. No
  `withCredentials` path-matching interceptor. No pages, no tests (Tasks 6/7).

- **What, How, and Why**: Installed `axios` (`npm install axios`, no flags needed — no peer
  conflict). `client.ts` creates `apiClient = axios.create({ baseURL })` and
  `authClient = axios.create({ baseURL, withCredentials: true })` where
  `baseURL = \`${import.meta.env.VITE_API_URL}/api/v1\``. `apiClient`'s request interceptor
  reads `getAccessToken()` from the Task 4 token store and sets the `Authorization` header.
  `apiClient`'s response interceptor implements single-flight refresh: on a 401 whose config
  isn't already `_retry`-marked, it awaits a module-scoped `refreshPromise` (created once per
  refresh window via `performRefresh()`, reset in `.finally`), rewrites the failed request's
  `Authorization` header with the refreshed token, and retries once through `apiClient(config)`;
  on refresh failure it clears the token store and does `window.location.href = '/login'` with
  no second refresh attempt. To satisfy "auth.ts is the only caller of authClient" literally
  (ARCHITECTURE.md explicitly restricts `authClient` callers to `login`/`refresh`/`logout`),
  `performRefresh()` calls `refresh()` imported from `./auth` rather than calling
  `authClient.post('/auth/refresh')` directly — this creates a client.ts ↔ auth.ts circular
  import, which resolves cleanly under ESM/Vite because `refresh` is only invoked lazily inside
  the response-interceptor callback, never at module-eval time. `auth.ts` defines `login`,
  `refresh`, `logout`, each a thin `authClient.post(...)` call using `LoginRequest`/
  `LoginResponse` from the generated `components['schemas']` types (Task 2); `login` and
  `refresh` write the returned `access_token` into the token store, `logout` clears it after the
  server-side revoke call.

- **Decisions Made**:
  - Resolved the "authClient has only 3 callers" vs. "interceptor needs to trigger refresh"
    tension by having the interceptor import and call `auth.ts`'s `refresh()` (not
    `authClient.post` inline), keeping the caller restriction literally true rather than treating
    it as a soft guideline. Verified the resulting circular import doesn't break typecheck/lint/
    build.
  - No `expires_in`/token-metadata handling added to the token store or client — no consumer in
    this task's success criteria reads it (matches Task 4's YAGNI note; still true here).
  - Redirect on refresh failure uses `window.location.href = '/login'` per the task prompt's
    explicit instruction ("redirect via `window.location`") — no `react-router` navigation, since
    Task 6 explicitly defers routing.
  - Did not add a `/login` route or guard — out of Task 5's scope (Task 6).

- **Code Changed**:
  - Created: `frontend/src/api/client.ts`
  - Created: `frontend/src/api/auth.ts`
  - Modified: `frontend/package.json` (added `axios` dependency)
  - Modified: `frontend/package-lock.json`

---

## Task 5 (test-engineer pass): Static verification of two-Axios-instance interceptor + auth.ts

**Order Given**: Test-engineer step for Task 5 (`frontend/src/api/client.ts`, `frontend/src/api/auth.ts`) — two Axios instances, single-flight 401→refresh interceptor, auth endpoints. Explicitly scoped to static verification only: run typecheck/lint, read the two files, confirm the interceptor contract structurally matches TASKS.md Task 5 criteria, flag structural concerns. Behavioral tests (one-refresh-on-401, refresh-failure→login, concurrent single-flight, cookie scoping) are Task 7's deliverable (`client.test.ts`) per TASKS.md, which also owns bringing in the Vitest+MSW harness. No test files, no new deps, no `client.test.ts` created here.

**What, How, and Why**: Ran `npm run typecheck` (tsc -b --noEmit) and `npm run lint` (eslint src) from `frontend/` — both exit 0 (lint has one pre-existing unrelated warning in `button.tsx` about react-refresh export shape, not touched by Task 5). Read `client.ts` and `auth.ts` in full and checked each structural criterion by inspection:
- Two instances: `apiClient = axios.create({ baseURL })` (withCredentials defaults false) and `authClient = axios.create({ baseURL, withCredentials: true })` — correct split.
- Bearer request interceptor registered only on `apiClient` (`apiClient.interceptors.request.use`), reads `getAccessToken()`, sets `Authorization` header when present.
- Module-scoped `let refreshPromise: Promise<string> | null = null` with `performRefresh()` guarding against concurrent creation (single-flight) and clearing itself in `.finally()`.
- Per-request `_retry` guard via a `RetryableRequestConfig` interface extending `InternalAxiosRequestConfig`; response interceptor bails on non-401 or already-retried requests.
- Retry-once: sets `config._retry = true` before awaiting refresh, then replays via `apiClient(config)` with the new token.
- Refresh failure path: `clearAccessToken()` + `window.location.href = '/login'`, then rejects — no second refresh attempt triggered (catch block does not call `performRefresh()` again).
- Grepped `interceptors` usage across `src/api/*.ts` — only `client.ts` registers any; `authClient` has zero interceptors (no 401 handling on it), matching the criterion that refresh/login calls on `authClient` must not recurse into the interceptor.
- `auth.ts` exports exactly `login`, `refresh`, `logout`, all calling `authClient` (never `apiClient`); `login` and `refresh` both call `setAccessToken()` on success, `logout` calls `clearAccessToken()` after the network call.
- No URL/path-based `withCredentials` toggling anywhere — it's fixed per-instance at construction, not branched per-request.

**Decisions Made**: Treated this as a read-only verification step, not a test-writing step, per explicit orchestrator scope — did not create `client.test.ts`, did not install vitest/msw, did not add a `test` script, to avoid colliding with Task 7's target files. No production code changed.

**Structural flag for reviewer**: `client.ts` imports `refresh` from `./auth`, and `auth.ts` imports `authClient` from `./client` — a circular import (resolves at runtime because `authClient` is defined and exported before `refresh` is invoked, and ESM handles this cycle fine, confirmed by typecheck/lint passing and no runtime-order issue since `performRefresh()` only calls `refresh()` lazily inside a response-interceptor callback, well after both modules have finished initializing). Token-store write path: `auth.ts::refresh()` calls `setAccessToken(response.data.access_token)` directly; `client.ts::performRefresh()` only reads the resolved `access_token` off `refresh()`'s return value to set the retried request's `Authorization` header — it does not call `setAccessToken()` itself. So there is exactly one token-store write per refresh, not two. Similarly only one refresh call: `performRefresh()` is the sole caller of `refresh()`, single-flighted via the module-scoped promise. No double-write or double-refresh risk observed from static reading. Flagging the circular import itself as worth the reviewer's attention regardless (it works, but is a coupling smell between the two modules that Task 7's behavioral tests should exercise, e.g. import-order edge cases under test bundling/mocking).

**Code Changed**: None — no test files created or modified in this pass (out of scope per orchestrator instructions; behavioral coverage deferred to Task 7's `client.test.ts`).

## Task 5 (reviewer/gate pass): Two-Axios-instance client, single-flight refresh, auth.ts

**Order Given**: Authoritative review gate for Task 5 — verify every success criterion, run gates in `frontend/`, and adjudicate the client.ts↔auth.ts circular-import structural flag raised by the test-engineer pass.

**What, How, and Why**: Read `TASKS.md` Task 5, `ARCHITECTURE.md` §§ Two-Axios-instance contract / Single-flight 401→refresh interceptor contract / Auth endpoints consumed, the research doc, and both prior POOP.md Task 5 entries. Read `frontend/src/api/client.ts`, `frontend/src/api/auth.ts`, and `frontend/src/api/tokenStore.ts` in full. Ran `rm -rf node_modules && npm ci` (exit 0, no flags needed), `npm run typecheck` (exit 0), `npm run lint` (exit 0, only the pre-approved Task 3 `button.tsx` react-refresh warning), and `npx prettier --check src/api/client.ts src/api/auth.ts` (clean). Verified by inspection: `apiClient = axios.create({ baseURL })` (withCredentials default false) vs `authClient = axios.create({ baseURL, withCredentials: true })`, both with `baseURL = \`${VITE_API_URL}/api/v1\``; Bearer request interceptor on `apiClient` only, reading `getAccessToken()`; module-scoped `refreshPromise` with `performRefresh()` single-flighting concurrent 401s, `.finally` reset; per-request `_retry` flag via `RetryableRequestConfig`; success path rewrites `Authorization` and retries once via `apiClient(config)`; failure path clears the token store and hard-redirects to `/login` with no second refresh; `authClient` carries zero interceptors (grepped `interceptors` usage — only `client.ts`); `auth.ts` exports exactly `login`/`refresh`/`logout` hitting `/auth/login`, `/auth/refresh`, `/auth/logout` using `components['schemas']` generated types, and grep confirms no other file calls `authClient`; no URL/path-based `withCredentials` branching anywhere (fixed per-instance at construction).

Adjudicated the circular import: `client.ts` imports `refresh` from `auth.ts`; `auth.ts` imports `authClient` from `client.ts`. Traced module-eval order — neither side uses the imported binding at top level, only inside functions invoked later (the response interceptor callback, and the exported `login`/`refresh`/`logout` functions), so ESM's live-binding semantics resolve the cycle safely; `typecheck`/`lint`/`npm ci` all confirm no build-time breakage. Traced the write path: `auth.ts::refresh()` is the sole `setAccessToken` caller in the refresh flow; `client.ts::performRefresh()` only reads the resolved token off `refresh()`'s return to rewrite the retried request's header — one write, one refresh call per single-flight window, matching the contract. This delegation is what keeps "auth.ts is the only caller of authClient" literally true per the ARCHITECTURE.md contract, so it is a deliberate, correct structural choice, not a defect — Task 7's MSW behavioral tests are the right place to additionally prove it at runtime, not a reason to reject here.

No `# ponytail:` markers present in either file.

**Decisions Made**: APPROVE. Every Task 5 success criterion is met, the Target Files list matches exactly (`client.ts`, `auth.ts`), all required gates pass, and the circular import is adjudicated as acceptable/deliberate rather than a defect since it doesn't break single-flight, no-double-refresh, or the caller-restriction criterion.

**Code Reviewed**:
- frontend/src/api/client.ts
- frontend/src/api/auth.ts
- frontend/src/api/tokenStore.ts

## Task 6: Wire boot-time silent refresh, stub login form, signed-in placeholder

**Order Given**: Implement Task 6 from TASKS.md — app-root boot-time silent `refresh()`, a
`LoginStub` page with two shadcn `Input`s + one shadcn `Button` calling `auth.ts`'s `login()`,
a trivial `SignedInPlaceholder`, and `main.tsx` mounting `App` inside `QueryClientProvider`. No
router, no route guards, no `AppShell`. Target files: `frontend/src/App.tsx`,
`frontend/src/main.tsx`, `frontend/src/pages/LoginStub.tsx`,
`frontend/src/pages/SignedInPlaceholder.tsx`.

**What, How, and Why**: Added `@tanstack/react-query` as a dependency and wrapped `App` in
`QueryClientProvider` in `main.tsx` per the New-files table, even though no query hooks are used
yet (scaffold-only requirement, per ARCHITECTURE.md's "no real routes yet" note). Rewrote `App`
to hold a tri-state (`loading` / `signedIn` / `signedOut`) local `useState`, firing the existing
`refresh()` from `auth.ts` once in a `useEffect` on mount and rendering a plain-text loading
placeholder while in flight, then `LoginStub` or `SignedInPlaceholder` based on outcome — this is
the single app-root enforcement point the spec calls for, deliberately not a route guard. Built
`LoginStub` as a controlled form using the existing shadcn `Input`/`Button` components, calling
`login()` from `auth.ts` (which already threads through `authClient` and populates the token
store on success); a thrown rejection (401 or otherwise) is caught and shown as a generic
"Invalid email or password" message, with no forced-password-change branch per the explicit
out-of-scope note. `SignedInPlaceholder` is a one-line trivial component with no navigation.

**Decisions Made**:
- Used local component state (`useState`/`useEffect`) rather than a `useQuery` call for the boot
  refresh, since `QueryClientProvider` is only required for future wiring and TASKS.md doesn't
  ask for the refresh itself to go through React Query.
- Collapsed all auth failure modes (401 vs. network/other) into one generic error message in
  `LoginStub`, since only success/401 are in scope and the UI is a throwaway stub.
- `LoginStub` receives an `onSuccess` callback prop from `App` rather than reading/writing any
  shared auth-state store, keeping the state machine entirely inside `App` per "enforced at the
  app-root level only."

**Code Changed**:
- Modified: `frontend/src/App.tsx`
- Modified: `frontend/src/main.tsx`
- Modified: `frontend/package.json`, `frontend/package-lock.json` (added `@tanstack/react-query`)
- Created: `frontend/src/pages/LoginStub.tsx`
- Created: `frontend/src/pages/SignedInPlaceholder.tsx`

## Task 6 (test-engineer pass): Static verification of boot refresh, LoginStub, SignedInPlaceholder, main.tsx wiring

**Order Given**: Test-engineer step for Task 6. Static verification + structural read only — no
test files, no deps installed. `LoginStub.test.tsx` and the Vitest+MSW harness are explicitly
Task 7's target files; do not install vitest/msw, do not add a `test` script, do not create
`LoginStub.test.tsx`.

**What, How, and Why**: Read TASKS.md Task 6, ARCHITECTURE.md §§ Boot-time silent refresh and
Pages, and the prior Task 6 coder POOP.md entry. Read all four changed files
(`App.tsx`, `main.tsx`, `LoginStub.tsx`, `SignedInPlaceholder.tsx`) in full.

Ran the three required gates from `frontend/`:
- `npm run build` — exit 0.
- `npm run typecheck` (`tsc -b --noEmit`) — exit 0.
- `npm run lint` (`eslint src`) — exit 0 (one pre-existing unrelated warning on
  `src/components/ui/button.tsx:67`, a Task 3 file, not touched by Task 6).

Confirmed each structural criterion by inspection:
- `App.tsx` holds one boot-time `refresh()` call inside a single `useEffect` with an empty
  dependency array (fires once per mount), tri-state `loading`/`signedIn`/`signedOut` local
  state; renders a loading placeholder while `loading`, `SignedInPlaceholder` on `signedIn`,
  `LoginStub` on `signedOut`. No `react-router`, no route array, no guard component — enforcement
  is the single `useEffect` + conditional render at the app root, matching "app-root level only."
- `LoginStub.tsx` renders exactly two shadcn `Input`s (`email`, `password`, both controlled) and
  one shadcn `Button` (`type="submit"`), imports `login` from `@/api/auth` (which per Task 5's
  reviewed implementation is the sole path through `authClient`), calls it in the form's
  `onSubmit`, and on success invokes the `onSuccess` prop (wired by `App.tsx` to
  `setStatus('signedIn')`, transitioning to `SignedInPlaceholder`). The `catch` block collapses
  every rejection (401 or otherwise) into one generic "Invalid email or password" message — no
  forced-password-change branch, matching the explicit out-of-scope note; only success/401 are
  handled, per Task 6's criteria.
- `SignedInPlaceholder.tsx` is a single trivial `<div>` with no navigation, no data fetching, no
  props.
- `main.tsx` wraps `<App />` in `<QueryClientProvider client={queryClient}>` inside
  `<StrictMode>`; grepped for `react-router`, `Route`, `BrowserRouter`, `AppShell` across
  `main.tsx`/`App.tsx` — no hits, confirming no router and no `AppShell` were introduced.

**Decisions Made**: Wrote no test files — `LoginStub.test.tsx` and the Vitest+MSW harness
(`vitest.config.ts`, `src/test/setup.ts`, `src/test/mswHandlers.ts`, the `test` script) are
Task 7's explicit target files per TASKS.md; creating any of them here would collide with and
pre-empt that task. No vitest/msw dependencies were installed. Verification relied on the three
existing tooling gates (`build`, `typecheck`, `lint`) plus direct code reading, matching the
orchestrator's static-verification-only scope for this pass.

**Structural flags for reviewer**:
1. **StrictMode double-invoke**: `main.tsx` wraps `App` in `<StrictMode>`, and React 18's
   StrictMode double-invokes effects in development (mount → cleanup → mount again). `App.tsx`'s
   boot `useEffect` has no cleanup/abort guard, so in dev it will fire `refresh()` twice on every
   page load (two `/auth/refresh` network calls), though this does not happen in a production
   build (`StrictMode`'s double-effect behavior is dev-only). This is not caught by `npm run
   build`/`typecheck`/`lint` and won't surface until Task 7's `client.test.ts` (jsdom, StrictMode
   off by default under `@testing-library/react`'s `render`) or manual `npm run dev` testing —
   flagging for the reviewer/Task 7 test-engineer to decide whether it needs a guard (e.g. a
   `useRef` ignore-flag) or is acceptable as a known dev-only cosmetic double-call.
2. **Unhandled-rejection safety**: the boot `refresh()` call in `App.tsx` is chained with both
   `.then()` and `.catch()`, so refresh failure (expected on first-ever visit, no cookie yet) is
   fully handled — no unhandled promise rejection. Confirmed by reading the `.then().catch()`
   chain; no gap here.
3. Confirmed no double-token-store-write risk from `LoginStub`: `login()` (Task 5, `auth.ts`) is
   the only place `setAccessToken` is called on the login path; `LoginStub` never touches the
   token store directly, only calls `onSuccess()` to flip `App`'s render branch.

**Code Changed**: None. No test files were created or modified for this Task 6 pass —
`LoginStub.test.tsx` and the full Vitest+MSW harness remain Task 7's deliverable.

## Task 6 (reviewer pass): Approval of boot-time silent refresh + LoginStub + SignedInPlaceholder + main.tsx wiring

**Order Given**: Authoritative review gate for Task 6 — verify all success criteria, run
required gates (`npm ci` clean install, `build`, `typecheck`, `lint`, `format:check`), check
CLAUDE.md integration rule (N/A here — no orchestrator/runner parameter involved), apply ultra
ponytail strictness against over-engineering, and adjudicate the test-engineer's StrictMode
double-refresh flag.

**What, How, and Why**: Read TASKS.md Task 6, ARCHITECTURE.md §§ Boot-time silent refresh and
Pages, TRUTH.md stub rules, and both prior Task 6 POOP.md entries (coder + test-engineer). Read
`frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/pages/LoginStub.tsx`,
`frontend/src/pages/SignedInPlaceholder.tsx`, and `frontend/src/api/auth.ts` in full.

Ran gates from `frontend/`:
- `rm -rf node_modules && npm ci` — exit 0 (559 packages; audit warnings are pre-existing/
  unrelated to this task).
- `npm run build` — exit 0.
- `npm run typecheck` — exit 0.
- `npm run lint` — exit 0, one pre-existing warning on `src/components/ui/button.tsx:67`
  (Task 3 file, acceptable per task instructions).
- `npx prettier --check` on the four changed files — all Prettier-clean.

Verified each success criterion by inspection:
- `App.tsx`: single `useEffect([])` calls `refresh()` once, tri-state local `useState`
  (`loading`/`signedIn`/`signedOut`), renders loading placeholder / `SignedInPlaceholder` /
  `LoginStub` accordingly. No route guard, no `react-router` import. Enforcement is app-root
  only, matching the spec.
- `LoginStub.tsx`: exactly two shadcn `Input`s (email, password, controlled) + one shadcn
  `Button`; `onSubmit` calls `login()` from `@/api/auth`, which goes through `authClient` and
  writes the token store (Task 5, not touched here); success calls `onSuccess` prop, flipping
  `App` to `SignedInPlaceholder`. `catch` collapses all failures (401 or otherwise) into one
  generic message — no forced-password-change branch, matching TRUTH.md/ARCHITECTURE.md's
  explicit out-of-scope note for the 403 rotation flow.
- `SignedInPlaceholder.tsx`: single trivial `<div>`, no props, no navigation.
- `main.tsx`: wraps `App` in `QueryClientProvider` inside `StrictMode`; grepped — no
  `react-router`, `Route`, `AppShell` anywhere in the touched files.
- Grepped touched files for `# ponytail:` markers — none present, nothing to strip.
- CLAUDE.md integration rule (ScanRunner/ScanProgressScreen threading) is not applicable — this
  task adds no orchestrator/runner parameter; it is frontend UI wiring only.
- No duplicate scan/auth paths: `LoginStub` and boot refresh both route exclusively through the
  single `auth.ts` module from Task 5 (`login()`, `refresh()`); no copied client logic.

**StrictMode double-refresh adjudication**: `main.tsx` wraps `App` in `<StrictMode>`, and
`App`'s boot `useEffect` has no double-invoke guard, so in React 18 dev mode `refresh()` fires
twice per mount (mount → cleanup → remount). Judged **acceptable, not a criterion violation**:
the success criterion is "attempts one boot-time `refresh()` before rendering protected
content" — this describes the app's logical behavior (one `useEffect`, one `refresh()` call
site, no loop/interval/duplicate call path), not a guarantee against React's dev-only
double-invoke semantics, which apply to every effect in every StrictMode app regardless of
guard code. Production builds (`createRoot(...).render` without `StrictMode`, or any real
production bundle) fire it exactly once. Adding a `useRef` ignore-flag purely to suppress a
dev-only double network call on a throwaway stub component (explicitly "replaced wholesale by
the first real-screens feature" per ARCHITECTURE.md) is unrequested defensive complexity —
ponytail-ultra would flag the guard itself as yagni. Recorded as a known dev-only cosmetic
double-call; no fix required. Task 7's `LoginStub.test.tsx` behavioral test does not use
`StrictMode` (per test-engineer's note on `@testing-library/react`'s default `render`), so it
is unaffected.

**Decisions Made**: APPROVE. All success criteria met, all required gates pass, no
over-engineering found (component set is minimal: one `useEffect`, one tri-state, two files of
~20-40 lines each), no CLAUDE.md integration-rule violation applicable, StrictMode double-fire
judged acceptable dev-only behavior per above. No `# ponytail:` markers were present to strip.

**Code Reviewed**:
- frontend/src/App.tsx
- frontend/src/main.tsx
- frontend/src/pages/LoginStub.tsx
- frontend/src/pages/SignedInPlaceholder.tsx
- frontend/src/api/auth.ts

## Task 7: Add the Vitest + MSW harness and the client/stub behavioral tests

**Order Given**: Implement Task 7 — establish Vitest + MSW test harness and write
`client.test.ts` (one-refresh-on-401, refresh-failure→login, concurrent-401 single-flight,
cookie scoping) and `LoginStub.test.tsx` (stub wiring proof) per `ARCHITECTURE.md` § Testing
expectations and `TRUTH.md`'s acceptance rows. Target files: `vitest.config.ts`,
`src/test/setup.ts`, `src/test/mswHandlers.ts`, `src/api/client.test.ts`,
`src/pages/LoginStub.test.tsx`, `package.json`.

**What, How, and Why**: Added `vitest`, `msw`, `jsdom`, and the testing-library trio
(`@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, plus the
transitive `@testing-library/dom` peer that `npm ci` with legacy-peer-deps does not auto-hoist)
as devDependencies, and a `test: "vitest run"` script. `vitest.config.ts` reuses the same Vite
plugins/alias as `vite.config.ts`, sets `environment: 'jsdom'`, points `setupFiles` at
`src/test/setup.ts`, and injects `VITE_API_URL` via `test.env` since no `.env` file is committed
(only `.env.example`) and `import.meta.env.VITE_API_URL` would otherwise be undefined in tests.
`src/test/setup.ts` wires MSW's `setupServer` lifecycle (`beforeAll` listen with
`onUnhandledRequest: 'error'` / `afterEach` resetHandlers / `afterAll` close) and additionally
clears the in-memory token store in `afterEach` for test isolation across the shared `client.ts`
module within a file. `src/test/mswHandlers.ts` defines the three shared handlers named in the
task (`/auth/login`, `/auth/refresh`, and `/hosts` as the business-endpoint stand-in) plus an
exported `validLoginResponse` fixture reused by both test files; each behavioral test overrides
the relevant handler(s) with `server.use(...)` for its failure/counting variant rather than
duplicating handler bodies.

`client.test.ts` proves all four interceptor rows by importing the real `apiClient`/`authClient`
and letting MSW intercept at the network layer (nothing axios-related is mocked):
- **One refresh on 401**: `/hosts` handler returns 401 on its first call then 200; refresh
  returns 200 once; asserts `refreshCallCount === 1`, `hostsCallCount === 2` (original + retry),
  and the token store reflects the refreshed token.
- **Refresh failure → login**: `/hosts` always 401, `/auth/refresh` always 401; asserts the
  token store is cleared, `window.location.href === '/login'`, and `refreshCallCount === 1` (no
  second attempt). `window.location` is a real jsdom `Location` object whose `href` setter
  throws jsdom's "not implemented: navigation" error, so the test replaces
  `window.location` for its duration via `Object.defineProperty` with a plain object seeded from
  the real `href` (not an empty string — an empty base URL made MSW's XHR interceptor throw
  `Invalid URL` on the *next* request in the suite, since jsdom's `Location` accessors are
  prototype-defined and don't survive an object spread), then restores the original reference
  afterward. This is a test-only seam — no application code (`client.ts`) was touched.
- **Concurrent 401s single-flight**: three concurrent `apiClient.get('/hosts')` calls all 401
  initially (counted via a shared call counter), one 401 `/auth/refresh` response, then all
  three retries return 200; asserts `refreshCallCount === 1` and all three responses succeed.
  Verified this is deterministic, not racy: `performRefresh()` in `client.ts` assigns
  `refreshPromise` synchronously (before its first `await`), so however many 401 responses
  arrive first, JS's single-threaded execution guarantees the check-and-set in `performRefresh`
  never interleaves.
- **Cookie scoping**: temporary request interceptors on both `apiClient` and `authClient` (added
  and left registered only for that test, which runs last in the file) capture
  `Boolean(config.withCredentials)` per call; asserts the business call is `false` and the auth
  call is `true` — exercising the real two-instance split per the architecture's locked
  decision, per the task's explicit allowance to "inspect the request config."

`LoginStub.test.tsx` renders a tiny local `TestApp` wrapper (mirroring the tri-state toggle
`App.tsx` already implements, without re-testing `App.tsx`'s boot-time `refresh()` call) so
`LoginStub`'s `onSuccess` prop drives a transition to the real `SignedInPlaceholder` component;
fills both shadcn `Input`s via `user-event`, submits, and asserts (a) the rendered text flips to
"Signed in" and (b) a request interceptor confirms the request went out through `authClient`
with `withCredentials: true`.

**Why this approach**: The task is explicitly a proof task — MSW at the network layer plus the
real client modules is the only way to prove the interceptor's actual behavior (mocking axios
directly, which the task explicitly forbids, would prove nothing about the real code path). No
speculative test utilities were added; `mswHandlers.ts` holds exactly the three endpoints named
in the task with no extra business-endpoint stand-ins.

**Decisions Made**:
- `VITE_API_URL` injected via Vitest's `test.env` rather than a committed `.env.test` file —
  simplest option, no new file, matches the single constant the architecture doc names.
- Redirect assertion via a scoped `Object.defineProperty(window, 'location', ...)` override
  local to one test (restored immediately after), rather than editing `client.ts` to inject a
  redirect function — Task 7's target files exclude app source, and the task instructions
  explicitly directed reporting rather than editing app code for this kind of seam; this override
  proved sufficient without any src change.
- Added `@testing-library/dom` explicitly as a devDependency (not just implied by
  `@testing-library/react`) because `npm ci` under the project's `legacy-peer-deps=true` did not
  install it transitively, causing a hard import failure (`Cannot find package
  '@testing-library/dom'`) until pinned directly.
- Token store cleared in the shared `afterEach` (in `setup.ts`) rather than per test file, since
  `client.ts`'s module-level `accessToken`/`refreshPromise` state is shared across tests within
  the same file and needs resetting for isolation; scoped to the test harness only, no app code
  touched.

**Code Changed**:
- frontend/vitest.config.ts (created)
- frontend/src/test/setup.ts (created)
- frontend/src/test/mswHandlers.ts (created)
- frontend/src/api/client.test.ts (created)
- frontend/src/pages/LoginStub.test.tsx (created)
- frontend/package.json (modified: `test` script, testing devDependencies)
- frontend/package-lock.json (modified: `npm install` refresh for new devDependencies)

## Task 7 (AUDIT) — Test-engineer audit of the Vitest + MSW harness

**Order Given**: Audit that each Task 7 test genuinely PROVES its acceptance row (strong
assertions over real behavior, not trivial passes) and strengthen coverage if shallow. Scope:
`frontend/src/api/client.test.ts`, `frontend/src/pages/LoginStub.test.tsx`,
`frontend/src/test/mswHandlers.ts`, `frontend/src/test/setup.ts`, `frontend/vitest.config.ts`.

**What, How, and Why**: Ran `npm run test` (5/5 passing) and read all five target files plus the
source they exercise (`client.ts`, `auth.ts`, `tokenStore.ts`, `LoginStub.tsx`,
`SignedInPlaceholder.tsx`). For each of the five acceptance rows, verified assertion strength by
temporarily breaking the corresponding behavior in `client.ts` (never a test file), re-running
`npm run test`, confirming the relevant test failed with a meaningful diff, then restoring the
original file (verified via `git diff --stat client.ts` showing no diff after restore).

Mutations tried and results:
1. **One refresh on 401**: not mutated separately — already covers exact `refreshCallCount === 1`,
   `hostsCallCount === 2` (retry happened), response status 200, and the token store updated to
   the new token. PROVEN as-is.
2. **Refresh failure → login**: removed the `window.location.href = '/login'` assignment from the
   catch branch. Test failed (`expected 'http://localhost:3000/' to be '/login'`), proving the
   redirect assertion is real, not a no-op. `refreshCallCount === 1` and `getAccessToken() ===
   null` were already asserted. PROVEN as-is.
3. **Concurrent 401s single-flight**: removed the `refreshPromise` memoization in
   `performRefresh()` (made every call start its own refresh). Test failed
   (`expected 3 to be 1`), proving the three `Promise.all`-fired requests are genuinely concurrent
   in MSW/jsdom without needing an artificial delay in the refresh handler — no strengthening
   needed. PROVEN as-is.
4. **Cookie scoping**: swapped `withCredentials: true` from `authClient` to `apiClient` in
   `client.ts`. Both `client.test.ts`'s scoping test and `LoginStub.test.tsx` failed
   simultaneously (`expected [true] to deeply equal [false]` and vice versa), confirming both
   inspect the interceptor-observed request config rather than trusting the client construction
   code. PROVEN as-is.
5. **Stub proves wiring**: `LoginStub.test.tsx` was hit by the mutation above too (fails when
   `authClient` loses `withCredentials`), and independently renders, fills both `Input`s via
   `user-event`, submits, and asserts the `SignedInPlaceholder` text plus that the request that
   fired carried `withCredentials: true`. PROVEN as-is.

**Decisions Made**: No test files were edited — every mutation-based check showed the existing
assertions were already strong enough to fail on the corresponding regression, so no
strengthening was warranted per the ultra-minimal bar (don't add assertions that don't catch a
real bug the current ones miss). Confirmed via `git diff --stat` that `client.ts` was byte-identical
to its pre-audit state after each restore. Re-ran `npm run test`, `npm run typecheck`,
`npm run lint`, `npm run format:check` on the restored tree: test (5/5 pass), typecheck (clean),
lint (0 errors, 1 pre-existing unrelated warning in `src/components/ui/button.tsx`), format:check
(clean except the pre-existing, already-tracked `src/types/openapi.d.ts` drift that Task 8 is
scoped to fix via `.prettierignore`).

**Code Changed**: None. No test files were modified; `frontend/src/api/client.ts` was mutated
locally during the audit and fully reverted before this entry.

## Task 7 (reviewer pass): Approval of Vitest + MSW harness and client/stub behavioral tests

**Order Given**: Authoritative review gate for Task 7 — verify every success criterion, run
`rm -rf node_modules && npm ci`, `npm run test`, `npm run typecheck`, `npm run lint` (Task 3
button.tsx warning acceptable), confirm prettier-clean on the new test files (format:check not a
blocker for openapi.d.ts drift, tracked to Task 8), check MSW intercepts at the network layer
with no direct axios mock, verify the CLAUDE.md orchestrator/runner threading rule (N/A for this
frontend task), and spot-check the test-engineer's mutation-audit credibility.

**What, How, and Why**: Read TASKS.md Task 7, ARCHITECTURE.md § Testing expectations / Two-Axios
contract / interceptor contract, TRUTH.md acceptance rows, and both Task 7 POOP.md entries
(coder + test-engineer audit). Read all six target files in full: `vitest.config.ts`,
`src/test/setup.ts`, `src/test/mswHandlers.ts`, `src/api/client.test.ts`,
`src/pages/LoginStub.test.tsx`, `package.json`, plus `src/api/client.ts` to verify the tests
exercise real interceptor logic.

Ran gates from `frontend/`:
- `rm -rf node_modules && npm ci` — exit 0 (683 packages).
- `npm run test` — 2 files, 5/5 tests passed.
- `npm run typecheck` — exit 0.
- `npm run lint` — exit 0, one pre-existing warning on `src/components/ui/button.tsx:67` (Task 3
  file, acceptable per instructions).
- `npx prettier --check` on the touched test/harness files — "All matched files use Prettier
  code style!" (clean).

Verified each success criterion:
- `package.json`: `vitest`, `msw`, `jsdom`, `@testing-library/react`, `@testing-library/dom`,
  `@testing-library/jest-dom`, `@testing-library/user-event` added as devDependencies; `test`
  script is `vitest run` (non-watch, exits non-zero on failure — confirmed via the mutation run
  below, which failed loudly).
- `vitest.config.ts`: `environment: 'jsdom'`, `setupFiles: ['./src/test/setup.ts']`.
- `src/test/setup.ts`: `setupServer(...handlers)` with `beforeAll` (`listen`,
  `onUnhandledRequest: 'error'`), `afterEach` (`resetHandlers` + `clearAccessToken`), `afterAll`
  (`close`) — full MSW lifecycle plus test isolation for the shared token-store module state.
- `src/test/mswHandlers.ts`: shared handlers for `/auth/login`, `/auth/refresh`, and `/hosts`
  (business stand-in), each test overriding via `server.use(...)` for its failure/counting
  variant — no duplicated handler bodies.
- `src/api/client.test.ts` imports the real `apiClient`/`authClient` from `./client` and
  `refresh`/`login` transitively through them; grepped for `vi.mock`/`jest.mock` across all test
  files — no hits, confirming MSW intercepts at the network layer only, axios itself is never
  mocked. All four rows present and correctly asserted: one-refresh-on-401
  (`refreshCallCount === 1`, `hostsCallCount === 2`, token store updated), refresh-failure→login
  (token store cleared, `window.location.href === '/login'`, `refreshCallCount === 1`, no second
  attempt), concurrent single-flight (three parallel 401s, `refreshCallCount === 1`, all three
  retries return 200), cookie scoping (business interceptor sees `false`, auth interceptor sees
  `true`).
- `src/pages/LoginStub.test.tsx`: renders `LoginStub` via a tiny local `TestApp` state wrapper,
  fills both shadcn `Input`s with `user-event`, submits, asserts the real `SignedInPlaceholder`
  text appears and the fired request carried `withCredentials: true` — proves a genuine
  `authClient` round-trip, not a stubbed call.
- CLAUDE.md integration rule (orchestrator/runner param threaded through `ScanRunner`/
  `ScanProgressScreen`): not applicable — this task is a frontend test harness with no scanner/
  orchestrator involvement.
- No duplicate scan/test paths: handlers are defined once in `mswHandlers.ts` and reused by both
  test files via `server.use` overrides; no copied client logic.

**Mutation spot-check**: Flipped `authClient`'s `withCredentials: true` to `false` in
`src/api/client.ts` (never touching test files), re-ran `npm run test`: both the cookie-scoping
test in `client.test.ts` and `LoginStub.test.tsx` failed with `expected [false] to deeply equal
[true]`, exactly as the test-engineer's audit claimed. Reverted the edit, confirmed
`git diff --stat src/api/client.ts` showed no diff, and re-ran `npm run test` — 5/5 passing
again. This corroborates the test-engineer's mutation-audit findings as credible, not tautological.

Grepped all touched files for `# ponytail:` markers — none present, nothing to strip.

**Decisions Made**: APPROVE. Every Task 7 success criterion is met, all required gates pass
(clean install, tests, typecheck, lint, prettier on the new files), MSW correctly intercepts at
the network layer with real axios instances (no direct mock), the CLAUDE.md integration rule is
inapplicable to this frontend-only task, and the test-engineer's mutation-audit claims were
independently corroborated via a fresh spot-check mutation on `client.ts` that was fully
reverted afterward. No over-engineering found: `mswHandlers.ts` holds exactly the three named
endpoints, `setup.ts` is a minimal MSW lifecycle plus one necessary token-store reset, both test
files use direct, unabstracted assertions with no speculative test-utility layer.

**Code Reviewed**:
- frontend/vitest.config.ts
- frontend/src/test/setup.ts
- frontend/src/test/mswHandlers.ts
- frontend/src/api/client.test.ts
- frontend/src/pages/LoginStub.test.tsx
- frontend/package.json
- frontend/src/api/client.ts (read-only, plus temporary spot-check mutation, fully reverted)

## Task 8: Add the frontend CI job with the gen:types drift check

**Order Given**: Add a `frontend` job to `.github/workflows/ci.yml`, mirroring the `backend`
job's per-layer shape (checkout, setup, `working-directory: frontend`), running on the same
`push`/`pull_request` to `main` triggers, using `actions/setup-node` pinned to Node 22. Steps in
order, job fails if any fails: `npm ci` → `npm run gen:types` → `git diff --exit-code -- src/types`
(drift check) → `npm run lint` → `npm run format:check` → `npm run typecheck` → `npm run test` →
`npm run build`. Existing `validate`/`lint`/`tests`/`backend` jobs unchanged, no deployment steps.
Also resolve the Task 3-review-tracked item: commit `frontend/.prettierignore` covering
`src/types/` so `format:check` exits 0 against the unformatted generated `openapi.d.ts`.

**What, How, and Why**: Added a `frontend` job to `.github/workflows/ci.yml` after the existing
`backend` job, reusing the same trigger block (top-level `on.push`/`on.pull_request` to `main`
already covers all jobs) and mirroring `backend`'s `working-directory: frontend` pattern per step
rather than a job-level default, matching how `backend` scopes each step individually. Used
`actions/checkout@v4` (same version as every other job) and `actions/setup-node@v4` with
`node-version: "22"`, matching `frontend/.nvmrc` and `package.json`'s `engines.node: "22.x"`
(ADR-008 locked decision 5: Node 22 LTS everywhere). Added the eight steps in the exact required
order as separate named steps (one shell command each) so a failure at any step fails the job and
is individually attributable in the Actions log, consistent with how `backend`'s job is broken
into named steps rather than one multi-line script block.

Created `frontend/.prettierignore` with a single `src/types/` entry, scoping prettier's exclusion
to only the generated-types directory (not test files or the rest of `src/`). Verified this does
not conflict with the drift check: `.prettierignore` only affects what `prettier --check` walks;
the drift check (`git diff --exit-code -- src/types`) compares two `gen:types` outputs against
each other via git, which is orthogonal to prettier entirely. Confirmed no interaction by running
the full step sequence locally in order.

**Decisions Made**:
- One step per pipeline stage (not a combined shell script) to match the `backend` job's existing
  style and give each CI failure a distinct, readable step name.
- `.prettierignore` scoped narrowly to `src/types/` rather than a broader exclusion (e.g. all of
  `src/`), since only the generated types file is known to be unformatted and the task's tracked
  item names `src/types/` specifically.
- Did not run `prettier --write` on `openapi.d.ts` or modify `gen:types`, per the explicit
  instruction not to fight `gen:types`' own idempotency.
- Left the `frontend/` directory's overall git-tracked state alone (it remains untracked as a
  whole pending the human tail's commit) — this task's target files are exactly `ci.yml` (edit)
  and the new `.prettierignore`.

**Verification (run locally in `frontend/`, simulating CI in order)**:
- `npm ci` — exit 0
- `npm run gen:types` — exit 0 (regenerated `src/types/openapi.d.ts`)
- `git diff --exit-code -- src/types` — exit 0 (no drift; note: `frontend/` is currently untracked
  as a whole in this repo, so this `git diff` has nothing tracked to compare against yet — it is
  vacuously clean rather than a positive idempotency proof from this run alone. Task 2's reviewer
  already proved gen:types is byte-idempotent via MD5 hash comparison across two runs. The CI
  check itself is correct for the eventual committed state: once `src/types/openapi.d.ts` is
  committed by the human tail, this step will genuinely catch future drift between the committed
  file and a fresh `gen:types` run.)
- `npm run lint` — exit 0 (1 pre-existing warning, `button.tsx`, unrelated to this task)
- `npm run format:check` — exit 0 (previously exit 1 on `src/types/openapi.d.ts` before
  `.prettierignore` was added; confirmed fixed)
- `npm run typecheck` — exit 0
- `npm run test` — exit 0 (2 test files, 5 tests passed)
- `npm run build` — exit 0
- YAML well-formedness: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` — parsed without error.

**Code Changed**:
- Modified: `/Users/gui/Projects/dmitri/.github/workflows/ci.yml` (added `frontend` job)
- Created: `/Users/gui/Projects/dmitri/frontend/.prettierignore`

## Task 8 (test-engineer pass): CI job structural + step-sequence verification

**Order Given**: Test-engineer verification for Task 8 (frontend CI job + gen:types drift check
+ `.prettierignore` fix). Explicitly a CI-config task with no unit-test surface — do not add test
files. Simulate the CI job's 8 steps in exact order from `frontend/`, reporting exit codes;
confirm `.prettierignore` (which scopes `prettier`/`format:check` only) is a separate mechanism
from the `git diff --exit-code -- src/types` drift gate and does not blind that gate to real
drift; read `ci.yml`'s `frontend` job for trigger/checkout/setup-node/working-directory/step-order/
no-continue-on-error and confirm `validate`/`lint`/`tests`/`backend` are unchanged and no deploy
steps were added; validate the YAML.

**What, How, and Why**: Ran the 8 steps from `frontend/` in the exact CI order:
1. `npm ci` (no flags) — exit 0.
2. `npm run gen:types` — exit 0, regenerates `src/types/openapi.d.ts` from the frozen contract.
3. `git diff --exit-code -- src/types` — exit 0 on the clean tree.
4. `npm run lint` — exit 0 (1 pre-existing `react-refresh/only-export-components` warning on
   `src/components/ui/button.tsx:67`, a Task 3 file, not a failure).
5. `npm run format:check` — exit 0 (previously failed on `src/types/openapi.d.ts` before the
   coder's `.prettierignore`; confirmed the fix holds).
6. `npm run typecheck` (`tsc -b --noEmit`) — exit 0.
7. `npm run test` (`vitest run`) — exit 0, 2 test files / 5 tests passed.
8. `npm run build` (`tsc -b && vite build`) — exit 0.

All 8 steps green, in order, matching the workflow exactly.

Investigated whether `.prettierignore` excluding `src/types/` could blind the drift check to a
real regenerated-but-different file: found the entire `frontend/` directory is currently
untracked in git in this working tree (nothing under `frontend/` has ever been committed on
`main`), so a bare `git diff --exit-code -- src/types` run against the working tree trivially
exits 0 regardless of content — it isn't comparing against any baseline. To get a meaningful
signal, staged `frontend/src/types/openapi.d.ts` into the index
(`git add frontend/src/types/openapi.d.ts`), then reran the drift check from `frontend/`: clean
staged file → exit 0; appended a fake line to the file → `git diff --exit-code -- src/types`
correctly reported exit 1 with the appended line shown in the diff; reverted
(`git checkout -- src/types/openapi.d.ts`) and unstaged
(`git reset frontend/src/types/openapi.d.ts` from repo root) to leave the tree as found. This
confirms the drift check is a genuine, independent guard on the generated file's *content*
(via `git diff`), completely orthogonal to `.prettierignore` (which only affects what `prettier`
itself scans for `format:check`/`lint`-adjacent formatting, not `git diff`). The two mechanisms
do not interact and neither masks the other.

Read the `frontend` job in `ci.yml`: triggers are the top-level `on: push/pull_request` to
`branches: ["main"]`, shared by every job (no per-job override) — matches `validate`/`lint`/
`tests`/`backend`. Uses `actions/checkout@v4` and `actions/setup-node@v4` with
`node-version: "22"`. Every step after checkout/setup-node sets `working-directory: frontend`.
Parsed the workflow with `PyYAML` (`yaml.safe_load`) and walked `jobs.frontend.steps` — the 8
steps appear in exactly the order above, each a `run:` step with no `continue-on-error` key
present on any step (confirmed via direct field inspection, all `None`), so a failure in any
step fails the job by GitHub Actions' default behavior. `git diff .github/workflows/ci.yml`
against the pre-Task-8 tree shows the change is a pure append — the `validate`, `lint`, `tests`,
and `backend` jobs have zero lines touched; no `deploy`/`hosting`/`release` job or step exists
anywhere in the file.

Validated YAML well-formedness with `PyYAML`'s `safe_load` — parsed cleanly; the parser's
`True`/`'on'` key quirk (YAML 1.1 boolean-key interpretation of the bare `on:` mapping key) is a
`PyYAML` idiosyncrasy, not a defect in the workflow file, and does not affect GitHub Actions'
own YAML 1.2 parser.

**Decisions Made**: No test files created or modified — this is a CI-config task with no
application code to unit-test, per explicit orchestrator instruction. Verification consisted of
(a) literally executing the 8-step command sequence locally, in order, from `frontend/`, and
(b) static/structural reading plus `PyYAML` parsing of `ci.yml`. Used a transient `git add`/
`git checkout`/`git reset` cycle (no commit) to get a meaningful signal on the drift-check step,
since the working tree's `frontend/` is entirely untracked and a bare `git diff` against nothing
would otherwise be a false-positive-pass with no diagnostic value; reverted immediately so the
repo state is unchanged from before this pass.

**Flag for reviewer**: Not a defect in the workflow itself, but worth the reviewer's awareness —
the entire `frontend/` directory (all of Tasks 1–8's output) is currently untracked in this
working tree (`git status --porcelain` shows `?? frontend/`; `git ls-files frontend/` returns
nothing). Until `frontend/` is actually committed, the drift-check step's real-world behavior in
CI cannot be observed end-to-end locally by a plain `git diff` — my staged-index workaround above
demonstrates the mechanism works correctly once the file is tracked, but this repo needs an
actual commit of `frontend/` before Task 8's CI job runs for real (presumably the orchestrator's
job, not this task's).

**Code Changed**: None. No test files were created or modified for Task 8 (CI-config task, no
unit-test surface, per explicit scope).

## Task 8: Reviewer verdict — frontend CI job + gen:types drift check + .prettierignore fix

**Order Given**: Authoritative review gate for Task 8 (final task) of 014-frontend-scaffold —
the frontend CI job, gen:types drift check, and tracked `.prettierignore` fix. Verify every
success criterion, simulate the 8 CI steps in order, confirm existing jobs unchanged, confirm the
drift check and `.prettierignore` are independent mechanisms, confirm YAML well-formedness.

**What, How, and Why**: Read `TASKS.md` Task 8 (including the tracked sub-item), `ARCHITECTURE.md`
§ Exit codes/CI gate, `.github/workflows/ci.yml`, `frontend/.prettierignore`, and both Task 8
POOP.md entries (coder + test-engineer). Independently re-ran the full 8-step sequence from
`frontend/` in order: `npm ci`, `npm run gen:types`, `git diff --exit-code -- src/types`,
`npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run test`, `npm run build` — all
exited 0 (lint produced one pre-existing warning only, on `button.tsx`, not a failure). Read the
`frontend` job in `ci.yml`: shares the top-level `push`/`pull_request`-to-`main` triggers with
every other job, uses `actions/checkout@v4` + `actions/setup-node@v4` pinned `node-version: "22"`,
each step scoped `working-directory: frontend`, the 8 steps appear in the exact required order,
no `continue-on-error` anywhere in the file. Ran `git diff --stat .github/workflows/ci.yml` — 41
insertions, 0 deletions, confirming `validate`/`lint`/`tests`/`backend` are untouched and the
change is a pure addition; no deploy/hosting job present. Validated YAML with
`python3 -c "import yaml; yaml.safe_load(...)"` — parsed cleanly, `jobs` keys are exactly
`validate, lint, tests, backend, frontend`. Confirmed `frontend/.prettierignore` contains
`src/types/`, matching the tracked item; confirmed by reasoning (and by the test-engineer's
independent git-add/append/reset spot-check already on record) that `.prettierignore` only scopes
`prettier`'s file walk and cannot blind `git diff --exit-code -- src/types`, which operates on git
content independent of prettier — the two mechanisms are orthogonal and neither can mask the
other. Grepped `ci.yml` and `.prettierignore` for `# ponytail:` markers — none found.
`uv run pytest` / `uv run ruff check` were attempted per the gate's standing instructions but are
not applicable: this task's target file is `.github/workflows/ci.yml` only (plus the new
`frontend/.prettierignore`), no backend/hardware-agent files were touched, and `pytest` is not
installed in this environment's PATH for the hardware-agent context — noted explicitly rather than
silently skipped, and immaterial since Task 8 has no backend/hardware-agent surface.

**Decisions Made**: APPROVE. Every Task 8 success criterion is met: correct job structure and
trigger parity, correct step order with no `continue-on-error`, existing jobs are a pure-addition
diff, the tracked `.prettierignore` fix resolves `format:check` without defeating the drift check.
The known-context caveat (frontend/ currently untracked, so the local drift-check run is
vacuously clean) was treated as instructed — not a rejection ground, since the mechanism's
correctness against real content was already proven via the test-engineer's staged-git spot-check
and independently reasoned through above. No over-engineering: the job is a flat, single-purpose
step list mirroring the existing `backend` job's shape, `.prettierignore` is a one-line file
scoped exactly to the tracked item, nothing speculative added.

**Code Reviewed**:
- /Users/gui/Projects/dmitri/.github/workflows/ci.yml
- /Users/gui/Projects/dmitri/frontend/.prettierignore
- /Users/gui/Projects/dmitri/specs/014-frontend-scaffold/TASKS.md
- /Users/gui/Projects/dmitri/specs/014-frontend-scaffold/ARCHITECTURE.md
- /Users/gui/Projects/dmitri/docs/adr/ADR-008-frontend-stack.md
- /Users/gui/Projects/dmitri/specs/014-frontend-scaffold/POOP.md

---

## docs-sync (orchestrator, 2026-07-22)

**`.claude/docs/` (fully owned) — applied:**
- Created `frontend/overview.md`, `frontend/api.md`, `frontend/app.md`, `frontend/index.md`
  mapping the new SPA scaffold (two-Axios auth client + single-flight 401→refresh, in-memory
  token store, contract-typed API layer, boot-refresh + stub UI).
- Updated root `index.md` with a "Frontend (scaffold only)" section.
- Appended a 2026-07-22 entry to `log.md`.

**`docs/` (curated) — REPORTED, not edited (need a human/decision call):**
- `docs/roadmap/TASKS.md:66` — **T9 · Scaffold `frontend/`** is still an unchecked box. The
  scaffold shipped, BUT the T9 line lists "Router" which was intentionally descoped (ADR-008
  revised 2026-07-10 / DMI-54; no react-router in this feature). Marking it done is not an
  unambiguous factual patch — recommend `roadmap-sync` reconcile T9's scope vs. what landed.
- **Standing fact drift (`.claude/docs/MAINTAINING.md:71-73`)** asserts "the frontend do not
  exist." That is now partially false (the scaffold exists; the agent→backend link and Pi
  hardware still don't). Left unedited — MAINTAINING.md standing facts are human-owned; recommend
  a human update that line to "frontend scaffold exists (stub UI only); not yet wired to real
  screens."
