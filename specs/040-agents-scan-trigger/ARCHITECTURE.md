# ARCHITECTURE — Agents screen, the scan trigger, and the status pill

Frontend-only. React 19 + TypeScript 6 + Vite 8 + Tailwind v4 + TanStack Query v5 +
React Router v7, all under `frontend/`.

**No backend, no Pi, no contract change.** Every endpoint this feature calls is shipped and is
already present in `contracts/openapi/openapi.yaml` and the generated
`frontend/src/types/openapi.d.ts` (verified 2026-08-28: `AgentSummary`, `AgentDetail`,
`AgentListResponse`, `AvailableSubnet`, `UpdateAgentTargetSubnetRequest`, `CreateCommandRequest`,
`CommandSummary`, `CommandDetail`, `CommandStatus`, `ScanErrorCode` all exist). An implementer
editing either file, or `backend/**` or `hardware-agent/**`, has gone off-spec.

**No `INTEGRATION.md`.** Nothing crosses a layer boundary — this is one layer consuming a contract
that is already complete.

Behaviour is fixed by [`TRUTH.md`](TRUTH.md). Copy and layout come from `docs/ui/SCREENS.md`
§§ Foundations, AGENTS, and the blank-state rows of HOME / SCAN LIST / HOST INVENTORY —
**referenced, not transcribed**. The command flow is `docs/ui/FLOWS.md` B4; the lifecycle contract is
`docs/adr/ADR-011-pi-command-channel.md` §4. Divergences from SCREENS.md are listed in §10 and are
doc deliverables of this feature.

The query-lifetime decisions in §§4, 5.1 and 5.2 rest on
[`docs/research/tanstack-query-followed-resource-lifetime.md`](../../docs/research/tanstack-query-followed-resource-lifetime.md),
which verifies them against the installed `query-core@5.101.4` source. Read it before changing the
latch, the poll or the resolution order.

This spec **extends spec 039** ([`../039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md`](../039-frontend-scans-hosts-read-surfaces/ARCHITECTURE.md)).
Its decomposition — a page that composes, sections that own their own concern, pure mappings in
`src/lib/`, generated types only — is the pattern here. Do not reinvent it.

Load the **`frontend-conventions`** skill before writing any file under `frontend/src/`. It is
binding: the API-type rule, the version traps, the closed type scale, the nine-step spacing scale,
and the absent-not-disabled rule.

---

## 1. System context

This feature is the **only place in the product where a human causes a scan to happen**. It sits at
the head of the pipeline every other screen reads from the tail of:

```
   THIS FEATURE                            (already shipped)
        │
  POST /agents/{id}/commands
        │
        ▼
   backend enqueue ──► Pi over WS ──► nmap ──► ingest ──► persistence + CVE enrichment
        │                                                        │
  GET /commands/{id}  ◄── lifecycle ──────────────────────────────┘
   (poll, 5s)                                                     │
        │                                                         ▼
   status: done ──► invalidate ['scans'] ['hosts'] ['findings'] ──► spec 039's read surfaces
```

The app shell, the route table and the nav bar are **unchanged in shape**. `/agents` already exists
(spec 039) as a one-state read-only page inside `AppShell`, outside `RequireAdmin`, and it stays
there: **both roles read this screen** (TRUTH rule 1). No route is added, no route is guarded, and
`RequireAdmin` does not appear in any file this feature touches. The role split happens *inside* the
page, through `AdminOnly` (TRUTH rule 2).

**`pages/Agents.tsx` grows; it is not replaced.** Its permanent sentence — "Scanning is set up on
the Pi itself." — survives verbatim (TRUTH rule 27). **On `/agents` only:** the matching sentence in
`pages/home/HomeBlank.tsx`, and the same clause in the Scans and Hosts blank bodies, are **removed**
(§7). They were stand-ins for the button this feature ships; the guarantee was always about the
device destination, not about every screen that mentioned it.

Three things spec 039 deliberately left open close here:

| Left open by 039 | Closed by |
|---|---|
| `EmptyState` has no `action` prop; three blank states offer nothing | §7 |
| `queryKeys.ts` is prefix-shaped but nothing invalidates | §5.4 — the one call site |
| Nothing in the product refreshes itself | §5.1 — polling, on this screen only |

---

## 2. Data model and contracts

### 2.1 The five calls

| # | Method + path | Body sent | Response | Role |
|---|---|---|---|---|
| 1 | `GET /api/v1/agents` | — | `AgentListResponse` | both |
| 2 | `GET /api/v1/agents/{agent_id}` | — | `AgentDetail` | both |
| 3 | `PATCH /api/v1/agents/{agent_id}` | `UpdateAgentTargetSubnetRequest` | `AgentDetail` | admin |
| 4 | `POST /api/v1/agents/{agent_id}/commands` | `CreateCommandRequest` | `CommandSummary` | admin |
| 5 | `GET /api/v1/commands/{command_id}` | — | `CommandDetail` | both |

All five go over `apiClient` **imported from `@/api/client`** — never from `@/api/instances`, which
is the bare instance with no `Authorization` header and no 401-refresh. One HTTP layer; no second
client, no bespoke fetch.

**Call 1 exists to discover the id.** The MVP has exactly one agent; the list is not rendered as a
list. `agentId = list.data[0]?.agent_id`. `AgentListResponse` is `{ data: AgentSummary[] }` with
**no `total`** — the no-device blank state is `data.length === 0`, not `total === 0`, and this screen
therefore does **not** use `ListSurface` or `Pagination`. A second agent, if one ever appeared, is
ignored; multi-device management is out of scope.

**Call 3 needs no refetch.** It returns the full `AgentDetail`, so the response is written straight
into the agent-detail query cache with `setQueryData` (§5.3). Refetching after it would be a second
round trip for data already in hand.

### 2.2 Types — all generated

Every request and response type is read from `src/types/openapi.d.ts` via
`components['schemas'][…]`, and the aliases stay inside `src/api/`, exactly as `api/hosts.ts` and
`api/scans.ts` already do. **No hand-written API type, anywhere, for any reason.**

```ts
type AgentSummary        = components['schemas']['AgentSummary']
type AgentDetail         = components['schemas']['AgentDetail']
type AgentListResponse   = components['schemas']['AgentListResponse']
type AvailableSubnet     = components['schemas']['AvailableSubnet']
type UpdateAgentTargetSubnetRequest = components['schemas']['UpdateAgentTargetSubnetRequest']
type CreateCommandRequest = components['schemas']['CreateCommandRequest']
type CommandSummary      = components['schemas']['CommandSummary']
type CommandDetail       = components['schemas']['CommandDetail']
type CommandStatus       = components['schemas']['CommandStatus']
type ScanMode            = components['schemas']['ScanMode']
type ScanErrorCode       = components['schemas']['ScanErrorCode']
```

The shapes an implementer will otherwise guess at, recorded so nobody guesses:

- `AgentDetail`: `agent_id`, `display_name`, `online: boolean`, `last_seen_at: string | null`,
  `available_subnets: AvailableSubnet[]`, `target_subnet?: string | null`,
  `active_command_id?: string | null`.
- `AvailableSubnet`: `interface: string`, `cidr: string`, `is_default_route: boolean`. **There is no
  display name on the wire** — see §6.2.
- `CommandSummary` (the POST response): `command_id`, `scan_id?`, `agent_id`, `status`. It carries
  **no `error_code`** — only `CommandDetail` does.
- `CommandDetail`: adds `scan_mode`, `subnet`, `error_code?: ScanErrorCode | null`, `created_at`,
  `delivered_at?`, `started_at?`, `completed_at?`.
- `scan_id` is **nullable and optional** on both. ADR-011 §4: an `expired` command never got a
  `scan_id`, and a `queued` one does not have it yet. The "View scan" affordance therefore requires
  **both** `status === 'done'` **and** a non-null `scan_id`; it is never built from the command id.

### 2.3 Constants

```ts
// src/api/agents.ts
export const QUICK_SCAN_MODE = 'quick' satisfies ScanMode

// src/api/commands.ts
export const COMMAND_POLL_INTERVAL_MS = 5_000
```

`QUICK_SCAN_MODE` is a `satisfies`-checked literal, **not an `enum`** — `erasableSyntaxOnly` is on
and an enum emits runtime code. Scan mode is not a choice and is never rendered (TRUTH rule 11);
the constant exists so the one literal on the wire has a name and a contract check.

### 2.4 The refusals, and how they are read

`readApiError(err)` from `src/api/apiError.ts` returns `{ status, code }` and absorbs non-Axios
throws. **Branch on it; never inspect an `AxiosError` directly, and never match on a message
string.**

| Call | Status + code | Meaning | Handling |
|---|---|---|---|
| PATCH | `409` `device_offline` | the Pi is reporting nothing | §6.3 — toast; the chooser stays open, previous choice intact |
| PATCH | `422` `subnet_not_reported` | chosen network is no longer reported | §6.3 — same |
| POST | `503` `device_offline` | delivery attempted and failed | §6.4 — toast + re-read agent |
| POST | `409` `device_busy` | the Pi is already scanning | §5.5 — **adopt**, not an error |
| POST | `422` `subnet_not_reported` | stored target is stale | §6.4 — toast + reopen the chooser |

Both branches must check `status` **and** `code`. `409` means two different things across the two
endpoints, and `422` is a generic validation status; the code is what disambiguates.

---

## 3. Query keys — `src/api/queryKeys.ts` (extend)

Two groups are added to the existing object. Shape and discipline are unchanged: coarse→fine
arrays, so a prefix invalidates a family.

```ts
export const queryKeys = {
  scans:    { /* unchanged */ },
  hosts:    { /* unchanged */ },
  findings: { /* unchanged */ },
  agents: {
    all: ['agents'] as const,
    list: () => ['agents', 'list'] as const,
    detail: (agentId: string) => ['agents', 'detail', agentId] as const,
  },
  commands: {
    all: ['commands'] as const,
    detail: (commandId: string) => ['commands', 'detail', commandId] as const,
  },
} as const
```

- `agents.list()` is a **function taking no arguments**, not a bare array, so it reads like every
  other builder at the call site and gains params without a shape change. `GET /agents` takes no
  query params today.
- `commands` is a **separate top-level group, not nested under `agents`**, because
  `GET /commands/{id}` is a top-level resource on the wire and because the done-sweep must invalidate
  the three read domains **without** touching the command it is reading — a command nested under
  `['agents']` would be swept by any agent invalidation and would restart a poll that had stopped.
- The three existing groups are **not edited**. This feature adds keys and adds the first
  invalidation call site; it does not re-shape what 039 built.

---

## 4. The state machine — `src/hooks/useAgentScreen.ts`

The screen's read state is folded into one discriminated union, following `useOrgDirectory` and
`useHomeReview` exactly (error outranks loading; the page renders a state, never raw query flags):

```ts
export type AgentScreen =
  | { state: 'loading' }
  | { state: 'error'; retry: () => void }
  | { state: 'blank' }                       // no agent installed
  | { state: 'ready'; agent: AgentDetail }
```

Two queries inside it:

```ts
const listQuery = useQuery({
  queryKey: queryKeys.agents.list(),
  queryFn: listAgents,
})

const agentId = listQuery.data?.data[0]?.agent_id

const detailQuery = useQuery({
  queryKey: queryKeys.agents.detail(agentId ?? ''),
  queryFn: agentId ? () => getAgent(agentId) : skipToken,
})
```

- **`skipToken`, never `enabled`.** The reason is that `skipToken` removes the `agentId!` assertion
  from the `queryFn` — the token *is* the disabled state, so the narrowing happens where the closure
  is built. **It does not narrow `data`:** neither `skipToken` nor `enabled` does, and only
  `initialData` makes `data` non-optional (research note §3). This is the same rule 039 applied to
  Home's findings query. The `?? ''` placeholder in the key is never used to fetch, but it is **not**
  inert — see §5.1: a different key is a different cache entry, which is exactly the trap the
  command query's latch exists to avoid.
- **Resolution order:** `ready` **whenever `detailQuery.data` exists**, whatever the query flags say;
  then `isError` on either → `error` (with a `retry` that refetches both); `listQuery.isPending` →
  `loading`; empty list → `blank`; `detailQuery.isPending` → `loading`; otherwise `ready`. A fast
  failure must not sit behind a slow success.
- **Data outranks error, and this is load-bearing.** In v5 a *background refetch* failure sets
  `isError: true` while `data` is retained. The production client is `new QueryClient()`
  (`src/main.tsx:9`) — all defaults, so `staleTime: 0` and `refetchOnWindowFocus: true`. An operator
  who triggers a scan, switches tab and comes back causes an agent refetch on focus; if that one
  request fails, an `isError`-first order would replace the whole page with `ErrorRetry`, unmount
  `AgentCard`, and destroy the latched `followedCommandId` (§5.1) along with it. `[Retry]` would
  restore the agent but not the run — and if the scan completed meanwhile, `active_command_id` is
  already `null`, so **the operator would never see the result of the scan they started.** §8 states
  the governing principle for the poll: *a transient failure during a ten-minute run is not a reason
  to discard the run.* It binds this read too.
- **The page-level error state is therefore reserved for having nothing true to show** — the first
  read failing, before any agent has ever loaded. A background failure over good data is silent;
  the next successful refetch resolves it, and the operator's run is undisturbed.
- **No `refetchInterval` on either query.** The agent row does not poll. Only the command does
  (§5.1), and TRUTH's out-of-scope list is explicit that polling belongs to the run in progress and
  nowhere else. Agent freshness after an action is achieved by invalidating that one key (§6.4),
  which is an event, not a timer.
- **`onSuccess` / `onError` do not exist on `useQuery` in v5** — they were removed, and passing one
  is a **`TS2769`**, not a silent no-op (research note §6). Every derivation happens in render, as
  above.
- **`isPending`, never `isLoading`.** v5 renamed it and kept `isLoading` with a different meaning.

`blank` is TRUTH rule 25: the one blank state in the product with **no action**. It renders
`EmptyState` with **no `action` prop** — the prop this feature adds is deliberately not used here,
and a test asserts the absence (§11.4).

---

## 5. The command — `src/hooks/useScanCommand.ts`

This hook owns everything about the run: which command is followed, the poll, the done-sweep, and
the trigger. It is the answer to "one code path, not two".

```ts
export type ScanCommand = {
  command: CommandDetail | null
  triggering: boolean
  trigger: () => Promise<TriggerOutcome>
}

export type TriggerOutcome = 'followed' | 'subnet-stale' | 'refused'

export function useScanCommand(agent: AgentDetail): ScanCommand
```

### 5.1 The followed command — one query-key owner, explicit transitions

`followedCommandId` is the sole source of the command query key. A second value,
`lastObservedActiveCommandId`, records the last `agent.active_command_id` value this mounted hook
has processed. It is observation bookkeeping, never a second followed-command owner. Both values
initialize from the first `agent.active_command_id ?? null`.

| Source | Guard | `followedCommandId` result | `lastObservedActiveCommandId` result |
|---|---|---|---|
| Initial mount | — | Initial non-null active id, otherwise `null` | Initial active id or `null` |
| Later agent detail | Value equals the last observed value | Unchanged | Unchanged |
| Later agent detail | Value changed to a non-null id | Replace with that newly observed id | Record the new id |
| Later agent detail | Value changed to `null` | Unchanged; terminal state remains held | Record `null` |
| Successful POST | Response contains a new command id | Replace with the response id | Unchanged |
| User-triggered busy adoption | Fresh detail read contains an active id | Replace with that id | Record that freshly observed id |
| Any refusal without an id | — | Unchanged | Unchanged, except for a fresh detail value already processed above |

**Priority is explicit:** a successful POST response owns the new run immediately. Agent detail may
replace it only when the server's `active_command_id` makes a *newly observed* transition to a
non-null id. An unchanged cached id from the prior run cannot overwrite the command just accepted
by POST. Comparing `agent.active_command_id` directly with `followedCommandId` is forbidden: those
values answer different questions and recreates the retry regression this section resolves.

**One query-key state, three adoption sources.** Initial/later server observation, `trigger()`
(§5.3), and `409` adoption (§5.5) all transition the same `followedCommandId`, which feeds the same
query. There is no "resume" branch and no second command query.

- **Mount / return / reload** (TRUTH rule 18, acceptance rows *Run survives navigation* and
  *Adopting a run never started here*): the initializer, and then the render-time guard for an
  `active_command_id` that arrives on a later read. The pill renders mid-flight for a run this screen
  never started, and nothing in the code distinguishes the two cases because nothing distinguishes
  them behaviourally.
- **The followed id is never cleared in-session, and that is what keeps the terminal state on
  screen.** When a run reaches
  a terminal state the server clears `active_command_id` — and §5.4's sweep refetches the agent, so
  the clear lands immediately. The operator must still see "done" and the way into the scan
  (TRUTH rules 19–20). A newly observed `null` updates only the observation bookkeeping; it cannot
  pull the followed id back to `null`. The followed id is replaced only by a later accepted or
  newly observed non-null id.
- **A reload after a terminal state shows no pill.** Correct: TRUTH's out-of-scope list says this
  screen shows the current run, not a history of runs.

**Why the id must be latched rather than derived.** Retention in v5 follows the **query key**, not
`enabled` / `skipToken`: the same key keeps its data when a query is disabled, and a *different* key
is a different cache entry. So `followedCommandId ?? ''` (§5.2) is not an inert placeholder — the
moment the id goes null the observer moves to an empty entry and the terminal payload is gone from
the screen. A derivation of the form `started ?? agent.active_command_id` latches only a
self-started run and drops every adopted one at the instant it completes, which is the case
TRUTH rule 18 exists to serve. See
[`docs/research/tanstack-query-followed-resource-lifetime.md`](../../docs/research/tanstack-query-followed-resource-lifetime.md)
§§1–3, Probe C.

**Adjusting observation state during render is the sanctioned pattern here, not the banned Effect.** react.dev
presents it as the explicit alternative to an Effect that copies a prop into state, and it is
correct under StrictMode because the guard is conditional and the write idempotent — the double
invoke is a no-op. It also cannot fight the poll: a newly observed `null` updates only
`lastObservedActiveCommandId`, never the followed id. An Effect would additionally render one stale frame first.
`useState`'s initializer covers the first paint, so there is no frame without the adopted id.

**Do not reach for `placeholderData: keepPreviousData` instead.** It survives the key collapse, but
it then renders the *previous* run's terminal "Done · [View scan]" for the entire pending window of
the **next** run, and defusing that means threading `isPlaceholderData` through `commandStatus.ts`
and into the pill (research note §2, Probe B). Latching the key fixes the cause; this compensates
downstream for a cause left in place.

### 5.2 The poll

```ts
const commandQuery = useQuery({
  queryKey: queryKeys.commands.detail(followedCommandId ?? ''),
  queryFn: followedCommandId ? () => getCommand(followedCommandId) : skipToken,
  refetchInterval: (query) =>
    isTerminalCommandStatus(query.state.data?.status)
      ? false
      : COMMAND_POLL_INTERVAL_MS,
})
```

- **Verified against the installed version.** `@tanstack/react-query` **5.101.4**;
  `query-core`'s `_tsup-dts-rollup.d.ts:1675` types it as
  `refetchInterval?: number | false | ((query: Query<…>) => number | false | undefined)`.
  **Version trap:** in v4 the callback was `(data, query)`. Porting that shape does **not** fail
  loudly the way you would hope — `(data) => data.status` is a `TS2339` (`Query` has no `status`),
  but `(query) => query.state.status` **compiles clean** and is the real hazard: it reads the
  *query's* fetch status (`'pending' | 'error' | 'success'`), which is never a `CommandStatus`, so
  the terminal check never matches and the poll runs forever with no type error to say so
  (research note §6). **Read the command through `query.state.data`.**
- **Starting** is automatic: a non-null `followedCommandId` activates the query and the interval
  begins with the first successful read.
- **Stopping** is the callback returning `false` the moment the read comes back terminal
  (TRUTH rule 17, acceptance row *Terminal states stop the asking*). No `clearInterval`, no
  `setInterval`, no `useEffect` teardown to get wrong.
- `query.state.data` is `undefined` before the first result and after a failure; `isTerminalCommandStatus(undefined)`
  is `false`, so the interval persists. That is deliberate: a single failed poll must not silently
  abandon a ten-minute run.
- **`refetchIntervalInBackground` is left at its default (`false`).** A blurred tab stops asking and
  resumes on focus, which is the right behaviour for a ten-minute wait and costs nothing — the state
  lives on the server, so the first refetch on return is correct by construction.
- **This is the only `refetchInterval` in the app.** Scan list and scan detail keep the static reads
  039 gave them; TRUTH's out-of-scope list forbids widening it.

### 5.3 The trigger

`trigger()` is a plain `async` handler with local in-flight state, matching `pages/Users.tsx` — the
repo's established write pattern. **`useMutation` is not introduced**: there is no mutation anywhere
in `frontend/src/` today, and a single write does not justify importing a second write model
alongside the one already in use.

```ts
async function trigger() {
  if (!agent.target_subnet) return { outcome: 'refused' } // unreachable: the ready state gates the control
  setTriggering(true)
  try {
    const command = await createScanCommand(agent.agent_id, {
      scan_mode: QUICK_SCAN_MODE,
      subnet: agent.target_subnet,
    })
    setFollowedCommandId(command.command_id)
    return { outcome: 'followed', commandId: command.command_id, source: 'created' }
  } catch (error) {
    return await handleTriggerRefusal(error) // §5.5, §6.4
  } finally {
    setTriggering(false)
  }
}
```

Both body fields are supplied by the product (TRUTH rule 10, acceptance row *Trigger sends nothing
typed*): the mode is the constant, the subnet is the stored target. **No operator input reaches this
call**, and there is no free-text field anywhere on the screen.

`handleTriggerRefusal` returns `{ outcome: 'followed', commandId, source: 'busy-adopted' }` only
when its fresh detail read produces an id; every refusal that establishes no id returns
`{ outcome: 'refused' }`. Thus the control can distinguish an operator action that replaced itself
with a status region from a passive adoption or a refusal without inspecting hook internals.

`[Retry]` after a failed or expired run (TRUTH rule 20) calls **this same function**. There is no
retry path, only the trigger. The explicit outcome exists because old-id→new-id Retry is a
successful action even though a followed command existed before it.

### 5.4 The done-sweep — the one invalidation call site

TRUTH rule 21, acceptance row *Completion refreshes the product*. It must fire **once per completed
command**, not on every poll tick and not again after a re-render.

```ts
const sweptCommandId = useRef<string | null>(null)

useEffect(() => {
  const command = commandQuery.data
  if (command?.status !== 'done') return
  if (sweptCommandId.current === command.command_id) return
  sweptCommandId.current = command.command_id

  void queryClient.invalidateQueries({ queryKey: queryKeys.scans.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.hosts.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.findings.all })
  void queryClient.invalidateQueries({ queryKey: queryKeys.agents.detail(agent.agent_id) })
}, [commandQuery.data, queryClient, agent.agent_id])
```

- **An Effect is correct here and is not the banned Effect.** The conventions forbid *fetching* in an
  Effect (StrictMode double-invoke + a rotating refresh token). This is a cache instruction reacting
  to a state transition, it has no request of its own, and the ref guard makes the double-invoke a
  no-op — a `useRef` value survives StrictMode's second pass on the same component instance.
- **The ref holds the command id, not a boolean.** A boolean would suppress the sweep for the *next*
  run in the same session; keyed on the id, a second scan sweeps again.
- **The three prefixes are swept, not individual keys.** That is the entire reason 039 shaped the
  keys coarse→fine: `['scans']` sweeps the list, every page of it, the detail of every scan, and
  Home's two `latest` reads in one call.
- **`agents.detail` is swept too, and `commands` is not.** The agent's `last_seen_at` and
  `active_command_id` moved when the run finished, so re-reading it is honest; invalidating
  `['commands']` would refetch the command whose poll has just stopped, for no new information.
- Where it lives is deliberate: inside the hook that follows the command, so the transition is
  observed exactly once regardless of how many components render the pill.

### 5.5 `409 device_busy` — adoption

TRUTH rule 14, acceptance row *Already scanning*. The refusal is **not an error**: the operator's
intent is already being satisfied. But the frontend has no id for a command it did not create — the
`409` body carries a code, not a command. So it re-reads agent detail and takes the id from there:

```ts
if (status === 409 && code === 'device_busy') {
  const detail = await queryClient.fetchQuery({
    queryKey: queryKeys.agents.detail(agent.agent_id),
    queryFn: () => getAgent(agent.agent_id),
  })
  if (detail.active_command_id) {
    setFollowedCommandId(detail.active_command_id)
    setLastObservedActiveCommandId(detail.active_command_id)
    show(/* SCREENS.md § AGENTS — 409 toast copy */)
    return 'followed'
  }
  show(/* SCREENS.md § AGENTS — generic start-failure copy */)
  return 'refused'
}
```

- **`fetchQuery`, not `invalidateQueries`.** Adoption needs the *value* in hand to set the followed
  id, and `fetchQuery` both returns it and writes it into the same cache entry the agent query reads
  — so the row's online / last-seen / target line refresh from the same round trip. An invalidate
  would only schedule a refetch and hand back nothing.
- The id then flows into the **same** `followedCommandId` state as a self-started run (§5.1).
  Adoption is a `setState`, not a code path.
- **`active_command_id` may come back `null`** if the run finished between the POST and this read.
  **The followed id is not cleared** (§5.1); writing `null` here would discard a
  terminal pill the operator is still reading. With no id to follow, nothing is adopted and the
  screen stays on `[Scan now]`, so the toast is the **generic start failure** — the adopt copy
  ("Showing the scan in progress.") would describe a state the UI never enters. The `fetchQuery`
  above has already refreshed the row. No retry loop, no invented id.

---

## 6. The screen

### 6.1 Composition

`pages/Agents.tsx` composes and owns no read-state branch of its own — the same division 039 drew
between `HostDetail.tsx` and its sections:

```
Agents.tsx
├── PageHeader                       (title + subtitle, § AGENTS copy)
├── useAgentScreen()
│   ├── 'loading' → AgentsLoadingCard       (screen-specific three-bar card)
│   ├── 'error'   → ErrorRetry           (page-level copy + [Retry])
│   ├── 'blank'   → AgentsBlank          (EmptyState, no action prop)
│   └── 'ready'   → AgentCard(agent)
│                   ├── AgentIdentity        name · online/offline · last seen
│                   ├── target read line + [Change]
│                   └── exclusive lower mode, owned by AgentCard
│                       ├── choosing → SubnetChooser
│                       └── control/status → ScanControl ([Scan now] | CommandStatus)
└── the permanent note                (TRUTH rule 27 — kept verbatim)
```

`ErrorRetry`, `EmptyState`, `PageHeader`, `StatusPill`, `Timestamp`, `EmptyMark` and `AdminOnly` are
all shipped and are **reused as-is**. Only `EmptyState` changes, and only by gaining one optional
prop (§7).

**One owner, two exclusive card modes.** `AgentCard` owns whether the lower card is `choosing` or
`control/status`. While the chooser is open it replaces the *entire* `ScanControl` slot, including
an old terminal action or status for a command still being followed. Command polling continues in
data state; the latest status returns when the chooser closes. The chooser and scan control never
coexist, whether choosing began on first run, through `[Change]`, or after a stale-trigger refusal.

Within control/status mode, **one slot renders one control.** `ScanControl` renders the trigger
**or** the pill, never both:
no followed command → `[Scan now]`; a non-terminal command → the pill alone; a terminal command →
the pill plus its next step. This is TRUTH rule 22 — the run's state is the only thing on the row
that changes, and it changes in place.

### 6.2 Reading the networks — `src/lib/subnetLabel.ts`

A pure module, unit-tested without React, sibling to `scanStatus.ts` / `severity.ts`:

```ts
export function subnetLabel(subnet: AvailableSubnet): string
export function subnetOptionSuffix(subnet: AvailableSubnet): string | null
export function findAvailableSubnet(subnets: AvailableSubnet[], cidr: string): AvailableSubnet | null
```

- The label pairs a **human interface name** with the `cidr` (TRUTH rule 5: named by interface,
  never typed by the operator).
- **The mapping is by prefix, and it ships** — `SCREENS.md` § AGENTS is met verbatim, not diverged
  from. *Decided 2026-08-28 at the refine gate.*

  | Reported `interface` | Rendered |
  |---|---|
  | `eth*`, `en*` (`eth0`, `enp0s3`, `eno1`) | **Ethernet** |
  | `wl*` (`wlan0`, `wlp2s0`) | **Wi-Fi** |
  | anything else (`usb0`, `br0`, …) | the raw name, unchanged |

  The two prefixes are the whole of Linux interface naming for the two link types this product
  meets: `en*`/`wl*` are the predictable-names scheme, `eth*`/`wlan*` the legacy one. `enp0s3` is
  ethernet, so mapping it to "Ethernet" is correct, not a mislabel. The raw fallback means an
  unfamiliar link is never given a name the product had to guess.
- `is_default_route: true` gets the "internet connection" suffix (TRUTH rule 6). This is the second
  half of the disambiguation and it is contract-backed; the interface name is the first half, and
  the screen exists so a non-technical admin meets neither a CIDR nor a device node.
- `findAvailableSubnet` is how the stored `target_subnet` (a bare CIDR string) is rendered with its
  interface. **When it matches nothing reported, the raw CIDR is rendered alone** — the target
  outlives the report, and hiding it would lose the fact that a target is set.

### 6.3 Choosing the network — `pages/agents/TargetSubnetSection.tsx`

- **Wrapped in `AdminOnly` in its entirety.** A viewer sees the "Scanning: …" line from
  `AgentIdentity`'s sibling render and **no chooser and no [Change]** — absent, not disabled
  (TRUTH rule 2, acceptance row *Viewer sees state, not actions*). The read line is not inside
  `AdminOnly`; the controls are.
- Open when `target_subnet == null` (TRUTH rule 4 — online but unscannable, a designed state, not an
  error), and openable by `[Change]` when one is set (TRUTH rule 8). `AgentCard` owns this exclusive
  mode; the editable CIDR belongs to the mounted chooser session, not to the lifetime of the card.
- **Every opening starts a fresh edit session from the latest successful agent read.** Preselect
  `agent.target_subnet` only when that CIDR still exists in the latest `available_subnets`; otherwise
  begin with no valid selection and disable confirm. A closed A→B server update therefore opens on
  B, never on A retained from an earlier session.
- **While open, the operator owns the draft.** A background agent read may update the stored target
  and the option list, but it must not silently replace the selected draft. Draft validity is
  nevertheless derived from the latest `available_subnets` on every render. If the selected CIDR
  disappears, confirm becomes disabled and another activation cannot issue a PATCH until the
  operator selects a currently reported option.
- The options are a **radio group with a real `<label htmlFor>` per option** — a placeholder is never
  a label, and there is no free-text input on this screen at all (acceptance row *Networks read as
  words*).
- Confirm is a plain `async` handler calling `updateAgentTargetSubnet`, then
  `queryClient.setQueryData(queryKeys.agents.detail(agentId), updated)` — **no refetch**, because the
  PATCH returns the full `AgentDetail` (§2.1).
- **Refusals are visibly toasts, and the chooser session is left intact.** `409 device_offline`
  shows “Couldn't reach the Pi; nothing changed.” `422 subnet_not_reported` shows “The Pi doesn't
  report that network any more; nothing changed.” The chooser stays open with the operator's draft
  intact and the stored choice unchanged (TRUTH rule 9, acceptance row *Choice refused*). The stale
  `422` refusal re-reads agent detail so current options can invalidate the draft; the offline `409`
  refusal does not require that re-read. **Decided 2026-08-28 at the visual review, reversing an inline treatment.**
  An inline error reserves permanent space in the card for a message that is almost never present and
  shifts the confirm button down when it appears. The toast is the only visible refusal. The chooser
  retains the same sentence as local announcement state in a visually hidden node with a stable id,
  `role="status"`, and `aria-live="polite"`; after refusal the focused confirm button references it
  with `aria-describedby`. Focus stays on confirm. Selecting another option clears the stale
  description and relationship. This hidden string is not a second business-state authority.
- The confirm button is **disabled while the PATCH is in flight and until a currently reported
  option is selected** —
  the progress / incomplete-input carve-out of consistency rule 3, not the permission rule. Its
  cursor, opacity and tab-order treatment come from the shared `Button`.

### 6.4 Triggering — `pages/agents/ScanControl.tsx`

- The trigger and the terminal `[Retry]` are **inside `AdminOnly`**. The pill is **outside** it: a
  viewer sees the run's state (TRUTH rule 1) and no way to *act* on it.
- **`[View scan]` is outside `AdminOnly` too, and a viewer gets it.** It is navigation into a
  surface both roles already read, not an action on the device — withholding it would hide a
  destination the viewer is entitled to, which is not what consistency rule 3 asks for. So the
  viewer's absent set is exactly: `[Scan now]`, the hint, `[Change]`, the chooser and `[Retry]`.
  §11.4's viewer assertion is therefore "no button and no link" **only in states with no completed
  run**; the `done` state asserts the link is present for both roles.
- **The trigger is rendered when `target_subnet != null`, regardless of `online`** (TRUTH rule 12,
  acceptance row *Trigger stays put when offline*). `online` is derived from a socket registry and
  can be stale; the backend makes exactly one delivery attempt, so the operator pressing again is the
  only retry the system has. Hiding it on a flag that may be wrong denies a scan that would have
  worked. **This is not consistency rule 3** — that rule is about what a role may do.
- Disabled **only** while the POST is in flight (`triggering`).
- Toast copy is `SCREENS.md` § AGENTS. The two toast refusals:
  - `503 device_offline` → toast, then
    `void queryClient.invalidateQueries({ queryKey: queryKeys.agents.detail(agentId) })` —
    the "re-reads the device's state" half of TRUTH rule 13 and its acceptance row.
  - `422 subnet_not_reported` → toast, invalidate agent detail, and **reopen the chooser**
    (TRUTH rule 15, acceptance row *Stale network refused*). `AgentCard` supplies an
    `onSubnetStale` callback that moves its owned lower mode to `choosing`; `ScanControl` reports
    the outcome and does not own a second chooser-open flag.
- `409 device_busy` is handled in the hook (§5.5) and is not an error at this level.
- **Focus follows an accepted operator action, not the boolean presence of a followed command.**
  `ScanControl` consumes `TriggerOutcome` (or an equivalent user-action generation keyed to that
  outcome). Successful `[Scan now]`, successful terminal `[Retry]`, and user-triggered busy
  adoption each request focus once on `agents-command-status` as soon as that stable region replaces
  the action, including while its first GET reads `Starting…`. Passive mount, reload, focus refetch,
  and background adoption never move focus; neither do poll advancement or terminal arrival. A
  refusal that establishes no id leaves focus on the still-mounted action. The status root remains
  mounted from pending through every fetched lifecycle state and has `role="status"`,
  `aria-live="polite"`, and `tabindex="-1"`.
- Whenever a command id is followed in control/status mode, `agents-command-status` is the one
  stable region root and reads `Starting…` until data exists. `agents-pill` appears only once
  command data exists; `agents-view-scan` appears only for `done` with a non-null `scan_id`;
  `agents-retry` appears only for an admin at `failed | expired`; and `agents-scan-now` appears only
  for an admin-ready target with no followed command and no open chooser.

### 6.5 The pill and the terminal states — `src/lib/commandStatus.ts`

A **sibling of `scanStatus.ts`, not an extension of it.** Justification: `scanStatus.ts` maps
`ScanStatus` (five values, a different resource, with `isUnfinished` / `hidesCounts` predicates that
are meaningless for a command). One module switching on two unrelated enums would need every caller
to disambiguate and would make its predicates ambiguous by name. The code-map already documents
`scan-status.md` as `ScanStatus`-only. Same file shape, same `StatusPillTone` import, no shared
branch.

```ts
export function commandStatusPill(status: CommandStatus): { tone: StatusPillTone; label: string }
export function isTerminalCommandStatus(status: CommandStatus | undefined): boolean
```

| `CommandStatus` | Tone | Terminal | Next step rendered beside the pill |
|---|---|---|---|
| `queued` | `running` | no | — |
| `delivered` | `running` | no | — |
| `running` | `running` | no | — |
| `uploading` | `running` | no | — |
| `done` | `neutral` | yes | `[View scan]` → `/scans/{scan_id}` |
| `failed` | `failed` | yes | the failure sentence + `[Retry]` |
| `expired` | `failed` | yes | the never-picked-up sentence + `[Retry]` |

Labels are the § AGENTS copy table, one per state — all seven rendered (TRUTH rule 16).

**`StatusPill` gains height, but no tone.** The visual review (2026-08-28) sized the pill to match
the `Scan now` button — same height, same type size — so the control cell holds one height whatever
it contains. **This is a change to a shared component**: `StatusPill` also renders on the scan list
and scan detail (039), and both inherit the taller pill. That is intended — one pill, one size — but
it is a visual change to two screens this issue otherwise does not touch, and the visual gate should
look at all three. Its tones are untouched:

**No new tone, and the decision is deliberate.** TRUTH rule 16 and the acceptance row
*Expired is not failed* require the two to carry **different words and different next steps**; they
say nothing about colour. The existing tones are `border-input`, `border-sev-critical` and
`border-border` — a fourth would mean choosing a new colour, and `SCREENS.md` § Foundations is law on
colour. Reaching for `sev-high` would put severity ink on a lifecycle pill, competing with the
severity badge that appears on the same screens. So `failed` and `expired` share the tone and are
separated by copy and by what the operator is told to do next. `StatusPill.tsx` is therefore
**untouched** — spec 039 built it tone-and-label precisely so this feature could reuse it unchanged.
If the visual gate later wants a distinct ink, that is a `StatusPill` tone plus a Foundations token,
and it changes nothing here.

**The failure sentence reuses `scanFailureReason()`.** `CommandDetail.error_code` is a
`ScanErrorCode`, which is exactly the enum `src/lib/scanFailureReasons.ts` already maps to one
operator sentence, and the helper is total over `null` and `undefined`. SCREENS.md's
"Scan failed — `<error_code>`" renders a raw machine code at a non-technical admin; the shipped
mapping exists for that reason and 039 established that the raw code is never rendered. Divergence
recorded in §10. `scanFailureReasons.ts` is **imported as-is — not extended, not re-mapped.**

**`[View scan]` requires `status === 'done'` *and* a non-null `scan_id`** (§2.2, TRUTH rule 19,
acceptance row *Completion opens the scan*). It exists at no earlier state, even though the scan row
exists from delivery: sending an operator to an empty scan is worse than making them wait. And a
control that navigates nowhere is forbidden outright by the conventions — a `done` command with a
null `scan_id` renders the pill and no link.

### 6.6 Finite presentation contract

These authored choices are architecture-level inputs to the presentation task, not discretionary
styling:

| Element | Required contract |
|---|---|
| `agents-presence` | `text-body-md`; muted colour may remain |
| `agents-network` | `text-body-md` for chosen and viewer/no-target copy; muted colour may remain |
| `agents-note` | `text-body-md`; the permanent Pi sentence remains ordinary body copy |
| `agents-identity` | Wraps `agents-name` and `agents-presence` |
| `agents-loading` | A real bordered `bg-card` surface with step-6 padding and inter-group rhythm, step-2 identity/presence rhythm, and exactly three `aria-hidden` bars: one title-height identity bar and two body-height bars, with approved differing widths; no interactive descendant |

The loading card is screen-specific. The shared `LoadingSkeleton` renders table markup and is not
used or changed here. The real page header and permanent closing note remain readable during first
load, and polling/background refetch never restores this skeleton.

`agents-scans-link` and `agents-hosts-link` use the shared `Button` with `asChild` and
`variant="link"`, point to `/scans` and `/hosts`, and remain enabled. Their rendered class contract
must preserve pointer cursor, hover underline, focus-visible ring **and** underline, and the shared
active downward nudge. They have no custom click handler and remain in document order after the
card/status action.

---

## 7. `EmptyState` gains two slots, and the role split is an `AdminOnly` wrapper

TRUTH rule 26, acceptance rows *Blank screens lead to the scan* and *Blank screens for a viewer*.

```ts
type EmptyStateProps = {
  heading: string
  body: string
  testId: string
  action?: ReactNode          // a control, rendered between the body and the Ornament
  note?: ReactNode            // one muted line, same position
}
```

**Two slots, not one.** *Decided 2026-08-28.* They are not variants of one thing: `action` renders a
control, `note` renders a muted line, and they carry different type and colour. The deciding call
site is `AgentsBlank`, which needs **`note` with no `action`** — it is the one blank state in the
product that deliberately offers nothing (TRUTH rule 25), and its second paragraph ("Contact whoever
installed Dmitri…") is not a call to action in any sense. A single slot named `action` would have to
carry it and misname it. `SCREENS.md` also lists the two as separate copy rows on all four screens.

`ReactNode` on both, not `{ label, to }`: a typed CTA descriptor would have exactly one shape in the
whole app. Both are optional, so the no-action state is the default and needs nothing.

**`src/components/FirstScanCta.tsx` is an `AdminOnly` wrapper, and reads no session itself.** With a
`note` slot available, the viewer's line is copy passed by the call site rather than a branch inside
a component — so the component is one-way, which is exactly what `AdminOnly` already does:

```tsx
function FirstScanCta() {
  return (
    <AdminOnly>
      <Button asChild data-testid="first-scan-cta">
        <Link to="/agents">{/* copy per DESIGN.md */}</Link>
      </Button>
    </AdminOnly>
  )
}
```

Consistency rule 8 constrains the copy: the control *navigates*, so it must not be labelled with an
action its destination performs on arrival. **No new `ViewerOnly` primitive**, and no component in
this feature reads `useSession()` — that was only needed for the two-way split the `note` slot
removes.

The viewer's line is supplied as `note` and must not render for an admin. Each call site passes it
through the same one-way guard, inverted — a `<ViewerNote>` would be a second primitive, so instead
the note is simply the else-branch of the same session read the shell already performs. **Where the
branch lives is the one thing an implementer must not improvise: put it in `FirstScanCta`'s module
as a second export, `FirstScanNote`, wrapping the line in the inverse guard.** Two exports, one
module, one role concept in one file.

Three call sites, and `ListSurface` carries it for two of them:

| Screen | Wiring |
|---|---|
| `pages/home/HomeBlank.tsx` | renders `<FirstScanCta />` and `<FirstScanNote />` directly — it is bespoke markup, not an `EmptyState` |
| `pages/Scans.tsx` | `empty={{ heading, body, action: <FirstScanCta />, note: <FirstScanNote /> }}` |
| `pages/Hosts.tsx` | same |

`ListSurface`'s `empty` prop therefore widens to
`{ heading: string; body: string; action?: ReactNode; note?: ReactNode }` and passes both straight
through to `EmptyState`. That is the whole change to `ListSurface`; its state machine is untouched.

**The stand-in sentence retires on these three screens.** "Scanning is set up on the Pi itself." is
removed from the blank bodies of Home, Scans and Hosts (TRUTH rule 26). It was written as a
stand-in for the button that did not exist — `SCREENS.md` says so in both blank rows — and keeping
it beside `[Run first scan]` is not merely redundant but mildly contradictory: the button starts a
scan while the sentence says scanning is configured elsewhere. **It survives on `/agents` only**
(TRUTH rule 27), where it still explains what the installer did.

**No other rework of the read surfaces** (TRUTH out of scope). `DirectoryTable` and the tables are
not retrofitted; the blank bodies otherwise keep their 039 copy.

---

## 8. Error taxonomy (TRUTH rules 29–30)

| Failure | Treatment | Why |
|---|---|---|
| `GET /agents` or `GET /agents/{id}` fails | **Page-level:** `ErrorRetry` copy + `[Retry]`, refetching both | Nothing on the page can be true without the agent |
| `PATCH` refused (`409` / `422`) | **Toast**; the chooser stays open, selection and stored choice intact | §6.3 — the form must survive, and a toast never touches it |
| `POST` refused (`503` / `422`) | **Toast** naming what failed, plus a state re-read | Rule 27: a refused action must not discard what is on screen |
| `POST` refused (`409 device_busy`) | **Toast** + adoption. Not an error state | Rule 14 |
| A poll read fails | **Nothing page-level.** The last known pill stays; the interval keeps asking | A transient failure during a ten-minute run is not a reason to discard the run |
| A poll read fails and there is no data yet | The command slot renders as if no run were followed | The screen must not assert a state it has never read |

Three states everywhere (rule 26): the screen has a designed regular state, a designed blank state
(`AgentsBlank`) and a designed error state with a retry.

---

## 9. New files and naming (mandatory)

Every file an implementer creates or touches. **Paths not in this table are out of scope**, and no
file outside it may be invented.

### API layer

| Path | Change | Responsibility |
|---|---|---|
| `frontend/src/api/agents.ts` | **new** | `listAgents()`, `getAgent(agentId)`, `updateAgentTargetSubnet(agentId, body)`, `createScanCommand(agentId, body)`, `QUICK_SCAN_MODE`. Contract-typed aliases only; `apiClient` from `./client`. |
| `frontend/src/api/commands.ts` | **new** | `getCommand(commandId)` and `COMMAND_POLL_INTERVAL_MS`. Its own module because `GET /commands/{id}` is a top-level resource, matching the key group. |
| `frontend/src/api/queryKeys.ts` | **extend** | Add the `agents` and `commands` groups (§3). The three existing groups are untouched. |

### Hooks

| Path | Change | Responsibility |
|---|---|---|
| `frontend/src/hooks/useAgentScreen.ts` | **new** | The list + detail fold into `AgentScreen` (§4). No writes, no polling. |
| `frontend/src/hooks/useScanCommand.ts` | **new** | Followed-command derivation, the 5s poll, the done-sweep, `trigger()`, and the `409` adoption (§5). |

### Pure logic

| Path | Change | Responsibility |
|---|---|---|
| `frontend/src/lib/commandStatus.ts` | **new** | `commandStatusPill()` for all seven states + `isTerminalCommandStatus()` (§6.5). No React. |
| `frontend/src/lib/subnetLabel.ts` | **new** | `subnetLabel()`, `subnetOptionSuffix()`, `findAvailableSubnet()` (§6.2). No React. |
| `frontend/src/lib/scanFailureReasons.ts` | **untouched** | Imported as-is for the `failed` sentence. Do not extend, do not re-map. |
| `frontend/src/lib/scanStatus.ts` | **untouched** | The command lifecycle is a sibling module, not an extension (§6.5). |

### Shared components

| Path | Change | Responsibility |
|---|---|---|
| `frontend/src/components/EmptyState.tsx` | **extend** | Two optional slots, `action?: ReactNode` and `note?: ReactNode` (§7). No other change. |
| `frontend/src/components/ListSurface.tsx` | **extend** | `empty` widens by `action?` and `note?`, both passed through. State machine untouched. |
| `frontend/src/components/FirstScanCta.tsx` | **new** | Two exports — `FirstScanCta` (admin control) and `FirstScanNote` (viewer line), each a one-way role guard (§7). |
| `frontend/src/components/StatusPill.tsx` | **extend** | Height matched to the `Scan now` button (§6.5). Padding and type size only — **no new tone**. Ripples to the scan list and scan detail, which share it. |
| `frontend/src/components/AdminOnly.tsx` | **untouched** | Used as-is around the chooser and the trigger. |

### Screens

| Path | Change | Responsibility |
|---|---|---|
| `frontend/src/pages/Agents.tsx` | **extend** | **Grows, is not replaced.** Composes the state machine and the card; keeps the permanent "Scanning is set up on the Pi itself." note (TRUTH rule 27). |
| `frontend/src/pages/agents/AgentCard.tsx` | **new** | The row container: identity, target section, scan control. Owns no query. |
| `frontend/src/pages/agents/AgentIdentity.tsx` | **new** | `display_name`, online/offline, `last_seen_at` through `Timestamp` (`EmptyMark` when null). |
| `frontend/src/pages/agents/TargetSubnetSection.tsx` | **new** | The "Scanning: …" line + `[Change]`; owns the chooser's open flag and the PATCH; refusals are toasts, so it holds no error string (§6.3). Controls wrapped in `AdminOnly`. |
| `frontend/src/pages/agents/SubnetChooser.tsx` | **new** | The labelled radio group over `available_subnets` + confirm. No free-text field. |
| `frontend/src/pages/agents/ScanControl.tsx` | **new** | The one slot: `[Scan now]` or the pill + its terminal next step (§6.4). |
| `frontend/src/pages/agents/CommandStatus.tsx` | **new** | The pill, the failure/expired sentence, `[View scan]`, `[Retry]`. |
| `frontend/src/pages/agents/AgentsBlank.tsx` | **new** | The no-device blank: `EmptyState`, **no `action`** (TRUTH rule 25). |
| `frontend/src/pages/home/HomeBlank.tsx` | **extend** | Renders `<FirstScanCta />` + `<FirstScanNote />`; **drops** the `home-blank-note` Pi sentence (§7). |
| `frontend/src/pages/Scans.tsx` | **extend** | `empty.action` + `empty.note`; **drops** the Pi clause from the blank body. |
| `frontend/src/pages/Hosts.tsx` | **extend** | `empty.action` + `empty.note`; **drops** the Pi clause from the blank body. |

`src/pages/agents/` follows the existing `src/pages/home/`, `src/pages/scans/`, `src/pages/hosts/`
precedent. Screen-specific components do not go in `src/components/`.

### Tests and harness

| Path | Change | Responsibility |
|---|---|---|
| `frontend/src/test/mswHandlers.ts` | **extend** | Default handlers + fixtures for all five calls (§11.1). |
| `frontend/src/test/agentsHarness.ts` | **new** | Per-test overrides, following `scansHarness.ts` / `usersHarness.ts` exactly. |
| `frontend/src/lib/commandStatus.test.ts` | **new** | Pure. |
| `frontend/src/lib/subnetLabel.test.ts` | **new** | Pure. |
| `frontend/src/components/EmptyState.test.tsx` | **new** | Both slots, each present and absent, and the two independent of each other. |
| `frontend/src/components/FirstScanCta.test.tsx` | **new** | Both exports, both roles: exactly one renders per role, never both, never neither. |
| `frontend/src/pages/Agents.test.tsx` | **extend** | Rewritten around the real screen (§11.4). The 039 assertion "contains no button and no link" is **replaced**, not worked around. |
| `frontend/src/pages/Agents.command.test.tsx` | **new** | The lifecycle, polling, resume and adoption suite (§11.5) — split out because it owns fake timers. |
| `frontend/src/pages/Agents.invalidation.test.tsx` | **new** | The done-sweep suite (§11.5) — split out because it is the only case that mounts the product lists (`Scans`, `Hosts`, `HostFindings`) beside the agents card. |
| `frontend/src/pages/Scans.test.tsx` | **extend** | The blank state now carries a CTA for an admin and a line for a viewer. |
| `frontend/src/pages/Hosts.test.tsx` | **extend** | Same. |
| `frontend/src/pages/Home.test.tsx` | **extend** | Same, on `HomeBlank`. |

### Deliberately not touched

| Path | Why |
|---|---|
| `frontend/src/lib/scanStatus.ts`, `scanFailureReasons.ts` | Sibling and reuse, not extension. |
| `frontend/src/components/DataTable.tsx`, `Pagination.tsx`, `ReadDetailGate.tsx` | This screen is not a table and not a detail read. |
| `frontend/src/App.tsx`, `components/TopBar.tsx` | `/agents` and `nav-agents` already exist for both roles (039). No route and no nav change. |
| `frontend/src/api/instances.ts`, `client.ts` | One HTTP layer, already correct. |
| `contracts/openapi/openapi.yaml`, `frontend/src/types/openapi.d.ts` | Complete and generated. Hand-editing breaks `npm run gen:types`. |
| `backend/**`, `hardware-agent/**` | No work in this issue. |

---

## 10. Documentation deliverables

Amendments to `docs/ui/SCREENS.md` and `docs/ui/FLOWS.md` that are **part of this work**, not
follow-up:

1. **§ SCAN LIST and § HOST INVENTORY blank rows.** Both currently record "No `[Run first scan]` CTA
   and no viewer-only line — `/agents` has no trigger until DMI-89". The condition is now lifted:
   record the CTA and the viewer line as shipping, with the copy `DESIGN.md` settles. § HOME's blank
   row the same.
2. **§ AGENTS pill copy — `failed`.** The table specifies "Scan failed — `<error_code>`". The raw
   code is not rendered; `scanFailureReason(error_code)` supplies the operator sentence (§6.5).
   Record the new copy and the reason.
3. **§ AGENTS needs-network options — no divergence to record; record the mechanism.** The options
   ship exactly as the copy table writes them. "Ethernet" / "Wi-Fi" are *not* on the wire, so add a
   line noting they are derived from the reported `interface` by prefix (`eth*`/`en*`, `wl*`) with
   the raw name as the fallback (§6.2) — so a future reader knows the strings are computed, not
   sent, and knows what an unrecognised link renders as.
4. **§ AGENTS `409` toast copy** is marked "*FLOWS open decision #2 — this is the proposed copy*".
   Settle it and close the open decision in FLOWS B4.
5. **§ Shared components.** `EmptyState`'s row gains the optional `action` slot; add `FirstScanCta`
   and its three call sites. `StatusPill`'s row records that the seven-state `CommandStatus` reuses
   the existing three tones, and why `expired` and `failed` share one.
6. **§ AGENTS open question 1** (offline: keep `[Scan now]`) is now built as specified — mark it
   resolved rather than open.
7. The **screen index** row for Agents stops reading "read-only surface that DMI-89 grows".

`.claude/docs/frontend/` is updated by `/docs-sync` at the end of the pipeline: `api.md` (the two new
resource modules and the two new key groups, and that `queryKeys` now *has* an invalidation call
site), `scan-status.md` (its sibling `commandStatus`), `tables.md` (`EmptyState`'s action slot,
`ListSurface`'s widened `empty`), and a new concept page for the agents screen and the command poll.

---

## 11. Testing expectations

Vitest + Testing Library + MSW, mirroring the suites under `frontend/src/**/*.test.tsx`. Assert on
**user-visible text and `data-testid`**, never on query internals. Render through
`renderWithProviders(ui, { route })`, whose `QueryClient` already sets `retry: false` — a failed poll
therefore does not retry-storm inside a test.

`server.listen({ onUnhandledRequest: 'error' })` is on, so **every new endpoint needs a default
handler** in `mswHandlers.ts` or unrelated suites fail.

The finite presentation contract is tested directly; broad copy assertions do not substitute for
these authored tokens and structures:

| Contract | Required assertion |
|---|---|
| Ordinary read scale | `agents-presence`, `agents-network`, and `agents-note` each use `text-body-md` and not `text-body-sm` |
| Loading card | `agents-loading` is the bordered card with exactly three differently sized, `aria-hidden` bars: one title-height and two body-height; it has no interactive descendant |
| Identity wrapper | `agents-identity` contains `agents-name` and `agents-presence` |
| Closing links | `agents-scans-link` and `agents-hosts-link` have their correct href and accessible name and expose the shared link primitive's pointer, hover-underline, focus-visible ring plus underline, and active-nudge class contract |

### 11.1 MSW defaults

Added to `mswHandlers.ts`, all `satisfies`-checked against the generated types:

- `agentFixture: AgentDetail` — online, `last_seen_at` a couple of minutes ago, **two**
  `available_subnets` with exactly one `is_default_route: true`, a set `target_subnet`, and
  `active_command_id: null`. Exported, so a suite can spread a variant.
- `GET /agents` → `{ data: [agentSummaryFixture] }`; `GET /agents/:agentId` → `agentFixture`.
- `PATCH /agents/:agentId` → the request body merged into `agentFixture`, `200`.
- `POST /agents/:agentId/commands` → a `CommandSummary` with `status: 'queued'`, `201`.
- `GET /commands/:commandId` → a `CommandDetail`, default `status: 'queued'`.

`test/agentsHarness.ts` exports `baseURL` and small `server.use(...)` helpers, following
`scansHarness.ts`: `agentsFail()`, `noAgents()`, `agent(detail)`, `commandRefused(status, code)`,
`commandStatuses([...])` — the last returning the next status on each successive call, which is how
the lifecycle walk is driven. **Fixtures live in `mswHandlers.ts`; overrides live in the harness.**

Existing suites must stay green without edits. If `Home.test.tsx` or the scans/hosts suites need
changing for a reason other than the new CTA, the fixtures are wrong — not those screens.

### 11.2 Pure modules

- **`lib/commandStatus.test.ts`** — every one of the seven `CommandStatus` values maps to a tone and
  a label; `failed` and `expired` produce **different labels** (acceptance row *Expired is not
  failed*); `isTerminalCommandStatus` is true for exactly `done | failed | expired`, and false for
  `undefined`.
- **`lib/subnetLabel.test.ts`** — the label names the reported interface and the CIDR; the
  `is_default_route` option gets the suffix and the other does not (acceptance row *Networks read as
  words*); `findAvailableSubnet` returns `null` for a CIDR no longer reported.

### 11.3 Shared components

- **`EmptyState.test.tsx`** — the `action` node renders when given; **nothing extra renders when it
  is omitted**, which is the assertion protecting TRUTH rule 25.
- **`FirstScanCta.test.tsx`** — an admin gets a control whose `href` is `/agents`; a viewer gets the
  line and **no button and no link** in the rendered output.

### 11.4 `pages/Agents.test.tsx`

Mapped to TRUTH's acceptance rows:

| Acceptance row | Assertion |
|---|---|
| Unscannable until chosen | `target_subnet: null`, admin → the online line reads, **no [Scan now] in the DOM**, the chooser copy explains |
| Choosing enables the trigger | select an option, confirm → the "Scanning: …" line shows it and `[Scan now]` appears, **with no second `GET /agents/{id}`** (assert by having the PATCH return a subnet the GET handler never returns) |
| Networks read as words | both options name interface + CIDR, one carries the internet suffix, and **`queryAllByRole('textbox')` is empty** across the whole page |
| Choice can be changed | `[Change]` opens the chooser on an agent that already has a target |
| Choice refused | PATCH `409 device_offline` and `422 subnet_not_reported` → the approved short toast renders; the chooser stays open and the stored target is unchanged; confirm retains focus and its resolvable `aria-describedby` node contains the identical sentence with `role=status` and `aria-live=polite` |
| Latest target starts a chooser session | agent target A → successful background read reports B while closed → `[Change]` opens with B checked and A unchecked |
| Missing latest target | latest stored target is absent from latest options → opening checks no radio and confirm is disabled |
| Draft is session-owned | open chooser, select C, then complete a background read changing the stored target → C remains selected while the session stays open |
| Refetch revalidates a chooser draft | select a CIDR → background read removes it → confirm disables, and another activation issues no PATCH |
| Exclusive card modes | chooser open from first run, `[Change]`, or stale-trigger refusal → `agents-scan-now` and the complete old command-control slot are absent while polling may continue |
| Trigger stays put when offline | `online: false` → `[Scan now]` is present and enabled |
| Viewer sees state, not actions | viewer session → name, online line and target line present; **no button and no link** anywhere on the page |
| No device at all | `noAgents()` → the installer copy, and **no button and no link** |
| Read failure | `agentsFail()` → the error copy + `[Retry]`; retry re-reads and the card appears |
| Existing sentence survives | "Scanning is set up on the Pi itself." is present in every one of the above states |

**The testid rule** (settled 2026-08-28, and `DESIGN.md` §16 is the authoritative list):
**screen-scoped elements take the screen's prefix; genuinely shared components keep their own bare
name.** So everything on this screen is `agents-…`, matching the shipped `agents-page` and
`agents-note`; `toast` and `first-scan-cta` stay bare because four different screens' suites address
them. Names like `command-pill` or `subnet-confirm` are out — they read as if a third screen exists.

Testids: `agents-page`, `agents-note`, `agents-loading`, `agents-blank`, `agents-blank-note`,
`agents-error`, `agents-error-retry`, `agents-card`, `agents-identity`, `agents-name`,
`agents-presence`, `agents-network`, `agents-scans-link`, `agents-hosts-link`,
`agents-network-change`, `agents-chooser`, `agents-chooser-option-${interface}`,
`agents-chooser-confirm`, `agents-scan-now`.

**The 039 assertion that Agents contains no button and no link is replaced here**, and only for the
admin-ready state. It **remains** for the viewer state and the no-device state, where it is now
enforcing TRUTH rules 2 and 25 rather than the absence of an unbuilt feature.

### 11.5 `pages/Agents.command.test.tsx`

Split out because it owns fake timers, which must not leak into the suite above.

**Timer setup is a trap and is specified.** `vi.useFakeTimers()` freezes the clock user-event also
waits on, so the session must be created as
`userEvent.setup({ advanceTimers: vi.advanceTimersByTime })`; ticks are advanced with
`await vi.advanceTimersByTimeAsync(COMMAND_POLL_INTERVAL_MS)` so pending promises flush. Restore with
`vi.useRealTimers()` in teardown. `refetchIntervalInBackground` is left `false`, which is fine in
jsdom — `document.visibilityState` is `'visible'`.

| Acceptance row | Assertion |
|---|---|
| Trigger sends nothing typed | intercept the POST body in the handler and assert it is exactly `{ scan_mode: 'quick', subnet: <the stored target> }` — the one place asserting a request, because "the operator supplied neither" is a claim about the request |
| Pill walks the lifecycle | `commandStatuses(['queued','delivered','running','uploading','done'])`; advance 5s at a time and assert each label in turn, with no operator action between |
| Terminal states stop the asking | count handler invocations; after `done`, advance 15s and assert the count **did not grow** |
| Completion opens the scan | `[View scan]` links to `/scans/{scan_id}` on `done` — and assert it is **absent** at `queued`, `running` and `uploading` |
| Run survives navigation | `active_command_id` set on the agent fixture, nothing started in-session → the pill renders the polled state on first paint |
| Adopting a run never started here | same fixture, and the pill shows a state the test never triggered |
| **An adopted run reaches `done`** (§5.1 latch — the regression test for the defect this spec was refined to fix) | `active_command_id` set on the agent fixture and **nothing started in-session**; the agent handler returns `active_command_id: null` from its second call onward, so the done-sweep's refetch clears it exactly as the server would. Advance to `done` and assert `[View scan]` is present and links to `/scans/{scan_id}`. Without the latch the pill unmounts here and the assertion fails |
| **A background agent-read failure does not discard the run** (§4) | a run in flight; the `GET /agents/{id}` handler fails on its **second** call while the command handler keeps returning `running` → the page **stays on the card**, `agents-error` is absent, and the pill still shows the run |
| Already scanning | POST → `409 device_busy`, with the agent handler then returning an `active_command_id` → the toast copy renders, **no error state appears**, and the pill shows the in-progress run |
| Busy with nothing to adopt | POST → `409 device_busy` with the agent handler reporting no `active_command_id` → the **generic start-failure** toast renders, no status region appears, and `[Scan now]` is still on screen (§5.5) |
| Unreachable device | POST → `503 device_offline` → the toast copy renders **and** `GET /agents/{id}` is called again (assert through a handler whose second response changes the visible online line) |
| Stale network refused | POST → `422 subnet_not_reported` → the toast copy renders and the chooser is open again |
| Expired is not failed | one render at `expired`, one at `failed`; each carries its own sentence, and each sentence is absent from the other |
| Retry after a bad run | `[Retry]` present on both terminal failures; activating it issues a new POST and the pill returns to the first lifecycle label |
| Retry owns its replacement run | old failed/expired id is followed and unchanged agent cache still names it; Retry POST returns a new id → the new id remains the queried and rendered command, and the cached old id cannot overwrite it |
| Retry focus follows the action | focus `[Retry]`, accept a replacement id while following is already true → `agents-command-status` for the replacement has focus, `role=status`, `aria-live=polite`, and `tabindex=-1` |
| Scan-now focus | focus `[Scan now]`, accept an id while its first GET remains pending → the stable status region reads `Starting…` and has focus |
| Busy-adoption focus | activate a trigger, receive `409 device_busy`, and fetch an active id → that id is queried and the status region receives focus |
| Passive adoption | mount with an active id → status renders without programmatically displacing existing focus |
| Stable status region | pending `Starting…` resolves to queued and later poll states → the same `agents-command-status` root remains mounted and focus is not moved again |
| (rule 4, no raw codes) | on `failed` with `error_code: 'device_offline'`, the operator sentence renders and the string `"device_offline"` does **not** appear |

| Completion refreshes the product (`Agents.invalidation.test.tsx`) | render the scan, host and finding lists alongside, counting reads per family; reach `done` and assert each family is re-read exactly once **with no operator action**, and that further polls do not repeat the sweep |

Testids: `agents-pill`, `agents-command-status`, `agents-view-scan`, `agents-retry`, and the shared `toast`.

### 11.6 The three blank states

`Scans.test.tsx`, `Hosts.test.tsx`, `Home.test.tsx`, each in two roles (acceptance rows *Blank
screens lead to the scan* / *Blank screens for a viewer*): an admin's blank state carries a control
whose destination is `/agents`; a viewer's carries the line and **no control**. Testid
`first-scan-cta`.

### Not tested here

- `StatusPill`, `Timestamp`, `AdminOnly`, `scanFailureReason` — each already has its own suite. Test
  this feature's *use* of them, not the components again.
- The poll's internals. The assertions are the labels the operator sees and the request count after a
  terminal state; nothing asserts a `refetchInterval` value.

---

## 12. Gate

From `frontend/`:

```
npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

`npm run gen:types` is **not** run — the contract does not move, and a regenerated diff would mean
something went wrong. No `ruff`, no `pytest`, no `./database.sh`: nothing outside `frontend/`
changes.

## 13. `HUMAN_INFRA_REQUIRED`

None. No new hardware, daemon, service, environment variable or external tool. The feature runs
against the backend the frontend already talks to.
