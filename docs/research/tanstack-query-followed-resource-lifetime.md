# Research: keeping a followed resource on screen after its parent clears the id

> **Scope.** `specs/040-agents-scan-trigger/ARCHITECTURE.md` §§3–5.5. The Agents
> screen reads an agent (`GET /agents/{id}` → `AgentDetail`) and follows one command
> (`GET /commands/{id}` → `CommandDetail`) by `refetchInterval` until the status is
> terminal. The followed id is derived —
> `followedCommandId = startedCommandId ?? agent.active_command_id ?? null` — and the
> done-sweep invalidates `agents.detail`, which clears `active_command_id` on the
> server-side truth. For a run **adopted on mount**, `startedCommandId` is `null`, so
> the derivation collapses to `null` at the exact moment the run finishes and the
> terminal pill vanishes.
>
> **Source discipline.** Every behavioural claim below is checked against the
> installed `@tanstack/react-query` / `@tanstack/query-core` **5.101.4** source in
> `frontend/node_modules/@tanstack/query-core/src/`, and where a claim was worth
> proving rather than reading, against a **runnable probe** driving `QueryObserver`
> from the installed `build/modern/index.js` (probe transcripts inline, marked
> *Probe*). Type-level claims were checked by running the installed `tsc` over a
> throwaway file with the repo's `--strict` flags. Doc quotes are from
> tanstack.com/query/latest and react.dev only. Read 2026-08-28.

---

## TL;DR verdict

**Recommendation for spec 040: latch the followed id — adjust state during render —
so the query key never collapses. Do not reach for `placeholderData`.**

Five findings drive that, and three of them contradict what the spec currently says.

1. **The cache does not drop the command. The *key* does.** Retention in v5 is a
   property of the query key, not of `enabled` / `skipToken`. Flip `enabled: false`
   or swap `queryFn` for `skipToken` **on the same key** and `data` is fully retained
   in `status: 'success'` (§3, *Probe C*). The spec's `queryKey:
   queryKeys.commands.detail(followedCommandId ?? '')` is what loses the data — the
   `?? ''` sentinel routes the observer to a *different, empty* cache entry. The
   original entry survives for `gcTime` (5 min default) and is still readable via
   `getQueryData`, then is deleted (§1, *Probe B* line 3).
2. **`placeholderData: keepPreviousData` does work across the collapse** — proven,
   not assumed (*Probe A*) — but it buys the fix with a visible artifact: on the
   **next** trigger the screen shows the **previous** run's terminal data in
   `status: 'success'` for the whole pending window of the new command (*Probe B*
   line 4). Any use of it must gate on `isPlaceholderData` (§2).
3. **`skipToken` has no retention consequence.** It is a TypeScript convenience, and
   it does **not** narrow `data` — `d.data` is still `TData | undefined` under
   `--strict` (§3). Only `initialData` narrows. The spec's §4 rationale for choosing
   `skipToken` over `enabled` ("`enabled: false` does not narrow `data`") is true but
   not distinguishing: neither narrows. The real reason to keep `skipToken` is that it
   removes the `id!` non-null assertion in the `queryFn`.
4. **Adjusting state during render is React's own sanctioned replacement for the
   banned Effect**, is on the StrictMode double-invoke list *by design* (it is
   required to be pure and conditional, which makes the second invoke a no-op), and
   is documented as *"better than updating the same state in an Effect"* (§4). The
   spec's ban on "an Effect that copies `active_command_id` into state" is correct and
   **does not** extend to this pattern — react.dev presents the two as opposites.
5. **Not invalidating the agent would not fix anything.** With the repo's defaults
   (`staleTime: 0`, `refetchOnWindowFocus: true`) the agent detail refetches on the
   next focus regardless, and `active_command_id` goes `null` anyway. Dropping the
   agent from the done-sweep trades a real freshness guarantee for a delay, not a fix
   (§5).

**Two corrections to spec 040's own version-trap notes** (§6): `onSuccess` on
`useQuery` is a **type error**, not a silent no-op; and `refetchInterval: (data) =>
data.status` is a **type error** too, because `Query` has no `status` property. The
trap that *does* compile silently is `query.state.status` written where
`query.state.data?.status` was meant.

---

## Findings

### 1. Does the cache drop the data? `gcTime` semantics in 5.101.4

**No — and the mechanism is worth being precise about, because it is what makes the
"read it back out of the cache" family of fixes fragile.**

**What happens on the key change.** `QueryObserver.setOptions` builds the new query
from the new hash, calls `removeObserver` on the old one and `addObserver` on the
new. The old `Query` object stays in the `QueryCache`; losing its last observer only
*schedules* its collection:

```
removeObserver(observer) → if (!this.observers.length) { … this.scheduleGc() }
```
— `frontend/node_modules/@tanstack/query-core/src/query.ts:362-380`

`scheduleGc` arms a timer for `gcTime`, and only then does `optionalRemove` delete
the entry, and only if nothing re-subscribed and no fetch is in flight:

```
protected optionalRemove() {
  if (!this.observers.length && this.state.fetchStatus === 'idle') {
    this.#cache.remove(this)
  }
}
```
— `query.ts:226-230`, timer at `removable.ts:13-21`

**The default is 5 minutes, set in code, not merely in prose:**

```
this.gcTime = Math.max(
  this.gcTime || 0,
  newGcTime ?? (environmentManager.isServer() ? Infinity : 5 * 60 * 1000),
)
```
— `removable.ts:26-31`

Note the `Math.max`: `gcTime` is monotonically increasing per query — a second
observer asking for a *shorter* `gcTime` cannot shorten it.

The docs agree: *"Since there are no more active instances of this query, a garbage
collection timeout is set using `gcTime`"*, after which *"the cached data under the
`['todos']` key is deleted and garbage collected"* —
https://tanstack.com/query/latest/docs/framework/react/guides/caching

`getQueryData` reads that entry while it lives, and *"returns `undefined` if the
query does not exist"* —
https://tanstack.com/query/latest/docs/reference/QueryClient

**Probe B** (`QueryObserver` on `['commands','detail','abc']`, `gcTime: 100`, then
the key collapsed to `['commands','detail','']`):

```
1 fetched  -> {"command_id":"abc","status":"running"}
2 collapse -> {"command_id":"abc","status":"running"} placeholder= true
3 after gc, cache keys -> [["commands","detail",""]]
3 getQueryData(abc) -> undefined
3 observer data      -> {"command_id":"abc","status":"running"} placeholder= true
```

**Consequences for the fix space.**

- A fix built on `queryClient.getQueryData(queryKeys.commands.detail(id))` is
  **time-bombed**: correct for 5 minutes, silently empty afterwards. A ten-minute
  scan whose operator leaves the screen and returns is inside the failure window.
  Reject this family.
- Line 3 also shows something useful: the **observer** still renders the value after
  the cache entry is gone, because `placeholderData` reads
  `this.#lastQueryWithDefinedData?.state.data` (`queryObserver.ts:510`), a private
  field holding a direct reference to the old `Query` object
  (`queryObserver.ts:655-657`). Removal from the cache does not null that reference.
  So `placeholderData` retention outlives `gcTime` — but only for the life of that
  one observer. A component remount loses it.

---

### 2. `placeholderData` / `keepPreviousData` — does it apply to an *absent* key?

**Yes, and it is the one-line fix. Its cost is a wrong frame on the next run.**

**What the option is.** *"Placeholder data allows a query to behave as if it already
has data, similar to the `initialData` option, but **the data is not persisted to the
cache**."* Queries carry `isPlaceholderData: true` and start in `success` rather than
`pending` —
https://tanstack.com/query/latest/docs/framework/react/guides/placeholder-query-data

v5 removed the boolean option: *"use `placeholderData` with an identity function:
`placeholderData: keepPreviousData` or `placeholderData: (previousData) =>
previousData`"* —
https://tanstack.com/query/latest/docs/framework/react/guides/migrating-to-v5

`keepPreviousData` really is nothing more than that identity function:

```ts
export function keepPreviousData<T>(previousData: T | undefined): T | undefined {
  return previousData
}
```
— `utils.ts:427-431`

**Why "absent" behaves the same as "changed".** The whole branch is gated on the
*current* query's state, not on how the key changed:

```ts
if (options.placeholderData !== undefined && data === undefined && status === 'pending') {
```
— `queryObserver.ts:486-490`

A `skipToken` query is `enabled: false` (`queryClient.ts:604-606`) and therefore sits
at `status: 'pending'`, `fetchStatus: 'idle'`, `data: undefined` — which satisfies
the gate exactly as a genuinely-loading query would. The idiom is not
change-specific.

**Probe A** — the spec's exact shape, with and without the option:

```
PLAIN      after fetch  -> {"command_id":"abc","status":"done"} success
PLAIN      after collapse-> undefined pending fetchStatus= idle isPlaceholderData= false
PLAIN      getQueryData(old key) -> {"command_id":"abc","status":"done"}
PLAIN      cache keys -> [["commands","detail","abc"],["commands","detail",""]]

PLACEHOLDR after fetch  -> {"command_id":"abc","status":"done"} success
PLACEHOLDR after collapse-> {"command_id":"abc","status":"done"} success isPlaceholderData= true
```

The first block is the defect, reproduced outside React. The second is the fix
working.

**What it preserves, exactly.**

| | Preserved? |
|---|---|
| `data` | Yes — the previous query's `state.data`, run through `select` |
| `status` | **No.** Forced to `'success'`, always |
| `error` | **No.** *"`placeholderData` will always put you into success state, while `keepPreviousData` gave you the status of the previous query. That status could be `error` …"* (migration guide) |
| `dataUpdatedAt` | **No.** *"`dataUpdatedAt` will stay at `0`"* (migration guide) |
| Cache entry | **No** — never written to the cache |

**Cost.** One import, one line.

**Risk — this is the disqualifier.** *Probe B* line 4, immediately after the operator
triggers a **new** run:

```
4 new run pending -> {"command_id":"abc","status":"running"} success placeholder= true
5 new run settled -> {"command_id":"xyz","status":"running"} placeholder= false
```

The screen shows the **previous** command — including a terminal `done` pill and its
`[View scan]` link — for the entire pending window of the new command. On this screen
that is worse than the bug being fixed: the operator clicks *Scan now* and sees the
old run's "Done". Correct use therefore requires every consumer to gate on
`isPlaceholderData`, which pushes a query-implementation flag into `commandStatus.ts`
and the pill — the opposite of the spec's "one derivation, no second state machine".

**StrictMode:** unaffected. `placeholderData` is computed inside `createResult`, a
pure function of observer state; a second render recomputes the same value.
**Background refetch:** unaffected while the key is collapsed (the query is disabled,
so nothing refetches); on a live key a background refetch keeps `data` and never
enters the placeholder branch (`data !== undefined`).

---

### 3. `enabled` vs `skipToken` — retention and narrowing

**Neither affects retention. Neither narrows `data`. The difference is one non-null
assertion.**

**Retention follows the key.** *Probe C* holds the key fixed at
`['commands','detail','abc']` and changes only the disabling mechanism:

```
fetched               -> {"command_id":"abc","status":"done"}
enabled:false, SAME key -> {"command_id":"abc","status":"done"} success
skipToken,     SAME key -> {"command_id":"abc","status":"done"} success
```

This matches the docs: *"If the query has cached data, then the query will be
initialized in the `status === 'success'` or `isSuccess` state"*, and only *"if no
cached data is available … the query will start in the `status === 'pending'` and
`fetchStatus === 'idle'` state"* —
https://tanstack.com/query/latest/docs/framework/react/guides/disabling-queries

**They are the same mechanism.** `skipToken` is not a third mode; the client
rewrites it into `enabled: false` while defaulting the options:

```ts
if (defaultedOptions.queryFn === skipToken) {
  defaultedOptions.enabled = false
}
```
— `queryClient.ts:604-606`

**Narrowing: neither does it.** `useQuery`'s three overloads narrow on
`DefinedInitialDataOptions` only — i.e. on `initialData`
(`frontend/node_modules/@tanstack/react-query/src/useQuery.ts:15-32`). Compiling the
spec's own snippet under `--strict`:

```
error TS2322: Type 'NoInfer<{ status: "done" | "running"; }> | undefined'
  is not assignable to type '{ status: "done" | "running"; }'.
```

So spec 040 §4's *"`enabled: false` does not narrow `data`"* is true, but it is not a
reason to prefer `skipToken`, which does not narrow it either. **The real benefit** —
and it is a good one — is that `queryFn: id ? () => getCommand(id) : skipToken`
narrows `id` inside the closure, so no `getCommand(id!)`. Keep the convention; fix
the rationale.

**One `skipToken` caveat that matters if a retry button is ever added:** *"Calling
`refetch()` on a query that uses `skipToken` will result in a `Missing queryFn` error
because there is no valid query function to execute"* (disabling-queries). The
mechanism is `ensureQueryFn`, which returns
`() => Promise.reject(new Error(\`Missing queryFn: …\`))` and, in dev, first logs
*"Attempted to invoke queryFn when set to skipToken. This is likely a configuration
error."* — `utils.ts:446-476`. §4's `retry` in the `error` state must not blanket-
refetch the command query while it is skipped.

**Verdict for this defect:** the `skipToken`-vs-`enabled` axis is a red herring. The
`?? ''` in the key is the whole problem.

---

### 4. Latching a value in React 19 — the sanctioned pattern

**React documents *adjust state during render* as the replacement for exactly the
Effect spec 040 bans, and calls it better.**

From *You Might Not Need an Effect*, "Adjusting some state when a prop changes" —
the 🔴 example is `useEffect(() => { setSelection(null) }, [items])`, and the
prescription is:

> ```js
> // Better: Adjust the state while rendering
> const [prevItems, setPrevItems] = useState(items);
> if (items !== prevItems) {
>   setPrevItems(items);
>   setSelection(null);
> }
> ```
>
> Storing information from previous renders like this can be hard to understand, but
> **it's better than updating the same state in an Effect**. […] React will re-render
> the `List` *immediately* after it exits with a `return` statement. React has not
> rendered the `List` children or updated the DOM yet, so this lets the `List`
> children skip rendering the stale `selection` value.

> When you update a component during rendering, React throws away the returned JSX
> and immediately retries rendering. To avoid very slow cascading retries, React only
> lets you update the *same* component's state during a render. If you update another
> component's state during a render, you'll see an error. **A condition like `items
> !== prevItems` is necessary to avoid loops.** You may adjust state like this, but
> any other side effects (like changing the DOM or setting timeouts) should stay in
> event handlers or Effects.

— https://react.dev/learn/you-might-not-need-an-effect

The `useState` reference states the rules formally:

> Note that if you call a `set` function while rendering, it must be inside a
> condition like `prevCount !== count`, and there must be a call like
> `setPrevCount(count)` inside of the condition. Otherwise, your component would
> re-render in a loop until it crashes. Also, you can only update the state of the
> *currently rendering* component like this. […] This pattern can be hard to
> understand and is usually best avoided. However, **it's better than updating state
> in an effect.**

— https://react.dev/reference/react/useState

React also names the cheaper alternatives first, and they should be ruled out
honestly: compute from props/state if you can, or *"pass a different `key` to your
component"* to reset a subtree (same page). Neither applies here — the value we need
is precisely the one that is *no longer* derivable from props, and a `key` reset
destroys state rather than preserving it.

**Is it StrictMode-safe? Yes, and by construction.** StrictMode's double-invoke list
is explicitly the set of things that must be pure:

> Strict Mode calls some of your functions (only the ones that should be pure) **twice
> in development.** This includes:
> - Your component function body (only top-level logic …)
> - Functions that you pass to `useState`, `set` functions, `useMemo`, or `useReducer`
>
> […] React uses the result of one of the calls, and ignores the result of the other
> call. As long as your component, initializer, and updater functions are pure, this
> shouldn't affect your logic.

— https://react.dev/reference/react/StrictMode

A conditional, idempotent latch (`if (derived !== null && derived !== latched)
setLatched(derived)`) is pure: the second invoke either re-evaluates a condition that
is now false, or re-sets the same value. This is the crucial difference from the
Effect the spec bans — an Effect that *fetches* or that fires on a changing dependency
is not idempotent, so its double-invoke is observable.

**Does it survive a background refetch?** Yes, and this is the second reason to prefer
it over the Effect: the latch is **monotone**. It only ever moves to a *new non-null*
id. A poll or focus refetch that turns `active_command_id` into `null` does not
satisfy the condition, so nothing changes. The spec's stated objection to the Effect
— *"`active_command_id` changes under the poll"* — is exactly what the latch's guard
neutralises.

**Cost.** One `useState`, one three-line conditional. It also *collapses* the spec's
two variables into one: `startedCommandId` exists only to hold on after the server
moves on, which is what the latch does. `trigger()` sets the latch directly; the
render-time adjustment adopts a run this session did not start. One state, two
writers, same convergence point §5.1 was aiming for.

**Risk.** The latch never clears. On this screen there is exactly one agent, so that
is the desired behaviour (TRUTH rules 19–20: hold the terminal state until the next
trigger). If the screen is ever made multi-agent, the latch must be reset by keying
the subtree on `agent_id` — which is the `key` reset react.dev recommends, applied
where it belongs.

---

### 5. Should the parent be invalidated at all on completion?

**Yes, keep it. Removing it does not fix the defect and does cost freshness.**

**What invalidation does.** *"It is marked as stale. This stale state overrides any
`staleTime` configurations"*, and *"if the query is currently being rendered via
`useQuery` or related hooks, it will also be refetched in the background"* —
https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation

`refetchType` is `'active' | 'inactive' | 'all' | 'none'`, defaulting to `'active'`
(https://tanstack.com/query/latest/docs/reference/QueryClient), which the source
confirms:

```ts
if (filters?.refetchType === 'none') { … }
type: filters?.refetchType ?? filters?.type ?? 'active',
```
— `queryClient.ts:300-306`

**TanStack publishes no guidance about invalidating a parent whose field is a child's
key.** The closest first-party material is the Dependent Queries guide, which
establishes the shape (`enabled: !!userId` off a parent's field) and warns only about
latency — *"Dependent queries by definition constitutes a form of request waterfall,
which hurts performance"* —
https://tanstack.com/query/latest/docs/framework/react/guides/dependent-queries.
Nothing there addresses the parent field going *back* to null. **Marked explicitly:
this question has no primary-source answer; the reasoning below is mine.**

**Why `refetchType: 'none'` or dropping `agents.detail` from the sweep is not a fix.**
The repo runs TanStack's defaults, and the agent query is mounted and active. With
`staleTime: 0` and `refetchOnWindowFocus: true`, the very next tab focus refetches
`GET /agents/{id}`, `active_command_id` comes back `null`, and the pill disappears
anyway — later, and non-deterministically, which is strictly worse to debug than
disappearing immediately. Suppressing the invalidation converts a reproducible bug
into a flake.

It also costs something real: §5.4's justification for sweeping the agent is that
*"the agent's `last_seen_at` and `active_command_id` moved when the run finished, so
re-reading it is honest"*. That is right. The frontend should not keep a stale agent
row to protect a rendering decision.

**Conclusion.** The invalidation is correct; the screen's dependence on a *server*
field to decide what to *display* is the bug. Fix the display, not the sweep. Note
that §5.4 already keeps `['commands']` out of the sweep, which is what makes the
latched key safe — nothing re-activates the stopped poll.

---

### 6. v4→v5 traps relevant here, and two corrections to spec 040

Compiled with the installed `tsc` (`typescript@6.0.3`) at `--strict`,
`--moduleResolution bundler`, against the installed `@tanstack/react-query@5.101.4`
types.

| Idiom | Compiles? | Reality |
|---|---|---|
| `keepPreviousData: true` (v4 boolean option) | **No** — `TS2769`, *"'keepPreviousData' does not exist in type 'UseQueryOptions…'"* on all three overloads | Excess-property checking catches it. Use `placeholderData: keepPreviousData` (the imported function) |
| `onSuccess: () => {}` on `useQuery` | **No** — `TS2769`, *"'onSuccess' does not exist in type 'UseQueryOptions…'"* | **Correction to spec 040 §4**, which says these *"were removed and silently no-op"*. Removal is real — *"onSuccess, onError and onSettled have been removed from Queries"* (migration guide) — but the failure is loud at compile time in a typed object literal. The "silent" claim would only hold behind a spread or an `as` cast |
| `refetchInterval: (data) => data.status === 'done' ? …` (v4 `(data, query)` signature) | **No** — `TS2339`, *"Property 'status' does not exist on type 'Query<…>'"* | **Correction to spec 040 §5.2**, which claims this *"still compiles"* because *"`data` binds to the `Query` object"*. The binding is right; the compile is not — `Query` exposes `state`, not `status`. The v5 signature is `(query) => number \| false \| undefined` (migration guide) |
| `refetchInterval: (query) => isTerminal(query.state.status) ? false : 5000` | **Yes — clean, exit 0** | **This is the trap that actually bites.** `query.state.status` is the *query's* `'pending' \| 'error' \| 'success'`, never a `CommandStatus`. It is never `'done'`, so the poll never stops, and nothing warns. §5.2's `query.state.data?.status` is right; the note should point at `.state.status`, not at a one-argument callback |
| `cacheTime: 300_000` | **No** — excess property | Renamed: *"gc is referring to garbage collect time"* (migration guide) |
| `isLoading` used as "no data yet" | **Yes** | *"`isLoading` has been changed to `isPending` and `isInitialLoading` has now been renamed to `isLoading`"*; the new `isLoading` is `isPending && isFetching` (migration guide). §4 already has this right |
| `placeholderData: keepPreviousData` alongside `queryFn: … : skipToken` | **Yes — clean, exit 0** | Not a trap, a fact: the two compose, which is what makes §2's option available at all |

---

## Option comparison

| Option | Fixes the adopted-run case? | Cost | Risk | StrictMode | Background refetch |
|---|---|---|---|---|---|
| **Latch the followed id (adjust state during render)** — §4 | **Yes** | 1 `useState` + 3-line guard; *removes* `startedCommandId` as a separate variable | Latch never clears — correct for one agent, needs a `key` reset if the screen goes multi-agent | **Safe** — conditional + idempotent, on React's own pure-function list | **Safe** — monotone; a poll returning `null` does not satisfy the guard |
| **`placeholderData: keepPreviousData`** — §2 | Yes | 1 line | Shows the **previous** run's terminal pill through the whole pending window of the *next* run (*Probe B* line 4); forces `status: 'success'`, so a poll error renders as success; `dataUpdatedAt` stays `0`; retention dies on remount | Safe | Safe |
| **Latch + `placeholderData`** | Yes | 2 changes | The placeholder is dead weight once the key is latched; two mechanisms for one invariant | Safe | Safe |
| **`getQueryData` fallback for the cleared id** | For ≤ 5 min | Small | **Time-bombed** — the entry is deleted at `gcTime` (*Probe B* line 3); reads cache as if it were state | Safe | Safe |
| **`setQueryData` to freeze the terminal payload** | Yes | Small | Imperative write into a cache the poll also owns; the next real read overwrites it; nothing tells you which value is real | Safe | Fights it |
| **Drop `agents.detail` from the done-sweep / `refetchType: 'none'`** — §5 | **No** | 1 line | Focus refetch clears `active_command_id` anyway → turns a reproducible bug into a flake; loses honest `last_seen_at` | n/a | **Breaks** |
| **An Effect copying `active_command_id` into state** | Yes | Small | The thing §5.1 bans, correctly: fires on a dependency that changes under the poll, renders one stale frame first (react.dev), needs its own guard to be idempotent | Needs a guard | Fights it |
| **`initialData` on the command query** | No | — | Narrows the type but is *persisted to the cache* and needs a value at first render, which is exactly what is missing | n/a | n/a |

---

## Recommendation

**Latch the followed command id by adjusting state during render, and delete
`startedCommandId` as a separate variable.**

```ts
// §5.1, revised. One state, two writers, still one derivation.
const [followedCommandId, setFollowedCommandId] = useState<string | null>(
  agent.active_command_id ?? null,
)

// Adopt a run this session did not start — and hold it after the server clears the
// field. Monotone: only ever moves to a new non-null id, never back to null.
// react.dev, "Adjusting some state when a prop changes".
const adopted = agent.active_command_id ?? null
if (adopted !== null && adopted !== followedCommandId) {
  setFollowedCommandId(adopted)
}
```

`trigger()` and the `409 device_busy` adoption path (§5.3, §5.5) call
`setFollowedCommandId` instead of `setStartedCommandId`. Everything downstream is
unchanged: §5.2's key is `queryKeys.commands.detail(followedCommandId ?? '')` and the
`?? ''` sentinel is now genuinely unreachable after the first run, so the observer
never leaves the entry holding the terminal payload; `refetchInterval` has already
returned `false`; §5.4's ref-guarded sweep fires once.

**Why this one.**

- It fixes the *cause*. §3 and *Probe C* show retention is a property of the key, and
  the `?? ''` sentinel is what throws the data away. Every other option leaves that in
  place and compensates downstream.
- It is what §5.1 was already reaching for. "A command started in this session and a
  command adopted from the server are the same value in the same variable" is exactly
  the latch; `startedCommandId ?? active_command_id` is a latch that only works for
  one of the two sources. Fixing it removes a variable rather than adding a
  mechanism.
- It defeats both objections §5.1 raises against the banned Effect, on the record:
  react.dev presents adjust-during-render as the *alternative* to that Effect and
  calls it better; the double-invoke is harmless because the guard is conditional and
  the write idempotent; and the monotone guard is immune to `active_command_id`
  changing under the poll.
- It leaves the done-sweep honest (§5) — `agents.detail` still refetches, the row's
  `last_seen_at` is still true.

**Where a reader could reasonably disagree.**

- **"`placeholderData: keepPreviousData` is one line and this is three."** Fair on
  cost. The counter is *Probe B* line 4: it puts the previous run's "Done · [View
  scan]" on screen for the pending window of the *next* run, and defusing that means
  threading `isPlaceholderData` into `commandStatus.ts` and the pill. Three lines in
  one hook beats a query-implementation flag crossing two module boundaries. If
  someone takes this route anyway, gating on `isPlaceholderData` is not optional.
- **"Adjusting state during render is a code smell."** react.dev says so too —
  *"This pattern can be hard to understand and is usually best avoided."* But it names
  the two cheaper escapes explicitly, and neither exists here: the value cannot be
  computed from current props (it has been deleted from them), and a `key` reset
  destroys state instead of preserving it. What remains is the pattern react.dev
  reaches for next.
- **"Latching a server field is lying to the operator."** It is the product decision
  TRUTH rules 19–20 already made: hold the terminal state until the next trigger, and
  show nothing after a reload. The latch implements that rule; it does not invent it.

**Also worth landing while the file is open** (§6): change §5.2's version-trap note to
point at `query.state.status`, which compiles clean and silently disables the stop
condition, rather than at a one-argument callback, which does not compile. And soften
§4's "silently no-op" for `onSuccess` — it is a `TS2769`.

---

## Sources

**Installed source — `frontend/node_modules/@tanstack/query-core@5.101.4/src/`**

- `removable.ts:13-31` — `scheduleGc`, `updateGcTime`, the 5-minute default, the `Math.max` monotonicity
- `query.ts:189` — `scheduleGc()` in the constructor; `query.ts:226-230` — `optionalRemove`; `query.ts:351-380` — `addObserver` clears the gc timer, `removeObserver` arms it; `query.ts:286` — `isDisabled` treats `skipToken` as disabled; `query.ts:623` — gc rescheduled after every fetch
- `queryObserver.ts:486-524` — the `placeholderData` branch and its `data === undefined && status === 'pending'` gate; `queryObserver.ts:510-511` — `#lastQueryWithDefinedData`; `queryObserver.ts:655-657` — where that field is assigned
- `queryClient.ts:604-606` — `queryFn === skipToken` ⇒ `enabled = false`; `queryClient.ts:300-306` — `refetchType` default `'active'`
- `utils.ts:427-431` — `keepPreviousData` is the identity function; `utils.ts:443-476` — `skipToken` symbol and `ensureQueryFn`'s `Missing queryFn` rejection + dev error
- `frontend/node_modules/@tanstack/react-query@5.101.4/src/useQuery.ts:15-42` — the three overloads; narrowing keys off `DefinedInitialDataOptions` (i.e. `initialData`) only

**Probes** — `QueryObserver` driven directly against
`@tanstack/query-core/build/modern/index.js` (5.101.4), transcripts inline: A (§2)
collapse with and without `placeholderData`; B (§1, §2) `gcTime` expiry and the
next-run placeholder leak; C (§3) `enabled: false` vs `skipToken` on an unchanged key.
Type-level checks run with `frontend/node_modules/.bin/tsc` (6.0.3) at `--strict`.

**TanStack Query v5 docs**

- Caching (gc timeout on last-observer unmount, 5 min): https://tanstack.com/query/latest/docs/framework/react/guides/caching
- Disabling queries (`enabled: false` keeps cached data; `skipToken` as the TS alternative; `refetch()` ⇒ `Missing queryFn`; lazy queries): https://tanstack.com/query/latest/docs/framework/react/guides/disabling-queries
- Placeholder query data (not persisted to cache, `isPlaceholderData`, function form receiving `previousData`/`previousQuery`): https://tanstack.com/query/latest/docs/framework/react/guides/placeholder-query-data
- Migrating to v5 (`keepPreviousData` → `placeholderData`; always-success + `dataUpdatedAt: 0`; `refetchInterval` `(data, query)` → `(query)`; `onSuccess`/`onError`/`onSettled` removed from queries; `cacheTime` → `gcTime`; `isLoading` → `isPending`): https://tanstack.com/query/latest/docs/framework/react/guides/migrating-to-v5
- Query invalidation (marks stale, overrides `staleTime`, refetches what is rendered): https://tanstack.com/query/latest/docs/framework/react/guides/query-invalidation
- QueryClient reference (`getQueryData` returns `undefined` if absent; `setQueryData` creates the entry; `refetchType` values and default): https://tanstack.com/query/latest/docs/reference/QueryClient
- Dependent queries (`enabled: !!userId` off a parent field; `pending` + `idle`; waterfall cost): https://tanstack.com/query/latest/docs/framework/react/guides/dependent-queries

**React docs**

- You Might Not Need an Effect — "Adjusting some state when a prop changes", the `prevItems` pattern, the same-component rule, the loop-guard requirement, and "better than updating the same state in an Effect": https://react.dev/learn/you-might-not-need-an-effect
- `useState` — "Storing information from previous renders", the caveats on calling `set` during render: https://react.dev/reference/react/useState
- `StrictMode` — the exact double-invoke list (component bodies, `useState`/`set`/`useMemo`/`useReducer` functions; Effects setup→cleanup→setup; ref callbacks) and "React uses the result of one of the calls": https://react.dev/reference/react/StrictMode

**Dmitri**

- `specs/040-agents-scan-trigger/ARCHITECTURE.md` §§3–5.5 — the derivation, the poll, the trigger, the done-sweep, the `409` adoption
- `frontend/src/hooks/useHomeReview.ts:43-56`, `frontend/src/api/findings.ts:12` — the existing `skipToken` convention
- `docs/research/frontend-react19-vite-typescript-conventions.md` — the v5 rename table and the "no fetching in an Effect" rule this note builds on
