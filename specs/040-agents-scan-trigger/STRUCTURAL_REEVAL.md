# STRUCTURAL RE-EVALUATION — Spec 040, Task 3

Date: 2026-08-29  
Scope: frontend only  
Gate state: **BLOCKED_STRUCTURAL — human approval required before more application-code work**

## Evidence reviewed

This re-evaluation is based on the complete current frontend working-tree diff, including the
untracked Task 3 implementation and tests, plus `TRUTH.md`, `ARCHITECTURE.md`, `DESIGN.md`, and
`TASKS.md`. The relevant current implementation is distributed across:

- the agent and command API/query-key additions;
- `useAgentScreen` and `useScanCommand`;
- the Agents page and all seven `pages/agents/` components;
- the shared blank-state and first-scan changes;
- the Agents screen, command-lifecycle, shared-component, and Home/Scans/Hosts tests and MSW
  harness.

No backend, hardware-agent, contract, generated-type, or application-code change is proposed or
made by this document.

## 1. Symptom inventory

The reviewer findings below are reproduced verbatim.

### Round 1

> (P1) adopted failed/expired Retry can be overwritten by cached old active_command_id; (P1) stale-subnet refusal can leave enabled submit for CIDR no longer reported; (P2) trigger reappears enabled between POST success and first command GET; (P2) loading is one pulsing rectangle instead of card-shaped three-bar skeleton; (P2) chooser refusal lacks aria-describedby relationship.

This round exposed five different kinds of defect in one task: followed-command authority,
refetch-driven form validity, an async control-state gap, loading composition, and an accessibility
relationship. The current diff contains reactive repairs for each: an additional
`lastAdoptedCommandId`, availability-derived submit disabling, a `following` state with a
`Starting…` slot, three skeleton bars, and a visually hidden refusal region. Those repairs cover the
reported examples, but the command and chooser rules they depend on still are not stated as
complete transition contracts in the approved specs.

### Round 2

> (P1) chooser open still renders ScanControl/[Scan now], allowing old target scan; (P2) Agents closing-note links lack complete cursor/hover/focus-visible/active states.

The first finding was an ownership conflict: the chooser and scan control were independently
renderable even though they are mutually exclusive modes of the same card. The current
`AgentCard` now gates `ScanControl` with `!chooserOpen`. The second finding was a shared-control
conformance miss. The current links are now rendered through the shared `Button` link variant, but
the Agents tests assert only `data-variant="link"`, not the complete interaction-state contract.

### Round 3

> (P2) permanent Pi note remains font-title text-title-lg instead of text-body-md; (P2) AgentIdentity lacks data-testid=agents-identity.

Both requirements were explicit in `DESIGN.md`: the Pi sentence is demoted to `text-body-md`, and
`agents-identity` is listed in the test-id contract. The current diff contains both repairs. Their
late discovery shows that the implementation and tests were not checked against a finite
presentation-contract checklist before review.

### Round 4

> (P1) chooser preselects stale server state after A→B background refetch because selected initializes once; (P2) retry terminal command loses focus because ScanControl only focuses false→true transition; (P3) AgentIdentity and TargetSubnetSection use text-body-sm where DESIGN requires text-body-md.

All three findings are still directly visible in the current frontend code:

- `TargetSubnetSection.tsx` initializes `selected` from `agent.target_subnet` once. The component
  remains mounted while agent detail refetches, so an A→B server update changes the displayed target
  prop but not the chooser draft.
- `ScanControl.tsx` focuses only when `following` changes from `false` to `true`. A retry changes the
  followed command identity from old to new while `following` remains `true`, so the retry button
  unmounts without the specified focus transfer.
- `AgentIdentity.tsx` and `TargetSubnetSection.tsx` author the presence and network lines with
  `text-body-sm`; `DESIGN.md` plate 6 explicitly marks both as `body-md`.

## 2. Root-cause analysis

### 2.1 Followed-command identity is richer than a boolean

The screen needs to distinguish at least three facts:

1. the command identity currently being followed;
2. the last active command identity actually observed from agent detail; and
3. whether a new followed identity came from the operator's just-completed action, which requires a
   focus transfer.

The original architecture reduces this to one comparison:

```ts
if (adopted !== null && adopted !== followedCommandId) {
  setFollowedCommandId(adopted)
}
```

That comparison is not safe after retry. If agent detail still contains the old failed/expired
`active_command_id`, a successful POST can set the new command id and a later render can immediately
restore the old one merely because the two differ. The current `lastAdoptedCommandId` repair
introduces the missing server-observation watermark, but this rule is absent from the spec and is
not presented as a source-priority transition table.

The focus defect has the same root cause. `following: boolean` can describe null→id, but it cannot
describe old-id→new-id. Retry is an identity transition and a user-intent transition even though it
is not a boolean transition. Focus therefore cannot be keyed to `following` alone.

### 2.2 Chooser draft lifetime does not match chooser-session lifetime

`selected` is editable draft state, while `agent.target_subnet` and `agent.available_subnets` are
server state. The current component keeps the draft for the lifetime of `AgentCard`, but the actual
editing session lasts only while the chooser is open. This creates two stale-state paths:

- a background refetch changes the stored target A→B while the chooser is closed, then reopening
  still preselects A;
- a refusal refetch removes a selected CIDR from `available_subnets`, so validity must be recomputed
  from the new list even though the operator's draft remains visible.

The second path is now guarded by render-time availability validation. The first cannot be fixed
reliably by another unconditional prop-to-state synchronization: doing that while the chooser is
open would overwrite a selection the operator is actively making. The missing rule is the draft's
lifetime and authority boundary: initialize from the latest server target at the beginning of each
chooser session, then preserve the operator's draft for that session while revalidating it against
every new subnet list.

### 2.3 Card modes were decomposed as siblings instead of one exclusive state

The chooser and scan control act on the same target and cannot safely coexist. Their initial
independent rendering allowed a scan of the old target while a replacement target was being
chosen. `AgentCard` now enforces exclusivity, but neither the architecture's composition tree nor
Task 3's success criteria originally named `choosing` and `control` as mutually exclusive card
modes. That omission made an invalid combined state representable.

### 2.4 Accessibility and visual rules were specified, but not converted into local contracts

The approved design already requires:

- three distinct loading bars inside the card;
- `aria-describedby` from a refused chooser submit to a polite live region;
- complete interactive states for links;
- `agents-identity`;
- `text-body-md` on the presence line, network line, and permanent Pi note.

The implementation missed these in separate rounds because the Task 3 success criteria compress
them into broad phrases such as "focus, accessibility, and testid contracts." The tests primarily
assert copy and behavior. They do not currently assert the two remaining body-scale tokens, and the
closing-link test checks the variant marker rather than the complete authored state contract.
Lint can reject a raw type size, but it cannot decide whether `text-body-sm` or `text-body-md` is
correct for a particular node.

### 2.5 The specs contain contradictions or underspecified transitions

The implementation was also being reviewed against documents that disagree at important edges:

- `ARCHITECTURE.md` §6.3 says the chooser holds no local refusal string, while `DESIGN.md` §14
  requires the focused confirm button to reference a persistent polite region with
  `aria-describedby`. A toast alone cannot provide that relationship.
- `ARCHITECTURE.md` §11.4 still says a refusal renders inside the chooser, while the approved visual
  decision says the visible refusal is a toast.
- `DESIGN.md` §14 says "After triggering" and names `[Scan now]`, but does not explicitly include a
  terminal `[Retry]` that starts a replacement command.
- `ARCHITECTURE.md` §5.1 prescribes the stale overwrite comparison described above and does not
  define the priority of unchanged cached agent state versus a newly accepted POST response.

These are specification defects, not reasons to add more compensating component state.

### 2.6 The execution unit is too broad for one coder/test/reviewer loop

Task 3 spans fifteen target paths and combines four independent axes:

- query lifetime and command ownership;
- chooser mutation/refetch behavior;
- card composition, roles, and presentation;
- timers, invalidation, focus, and accessibility integration.

The four rounds show serial discovery by axis: the first round found transition and accessibility
defects, the second found composition and interaction defects, the third found presentation/test-id
defects, and the fourth found a second-order refetch transition, a second-order focus transition,
and remaining typography drift. The tests were expanded after findings rather than derived first
from transition tables. This is a decomposition and test-design gap, not four unrelated coding
mistakes.

## 3. Revised implementation and decomposition plan

Do not resume Task 3 as one unit. After the spec changes in §4 are approved, replace it with the
following sequential frontend tasks. Each task keeps the existing complete implementation shape;
none is a temporary implementation or a partial replacement scheduled for immediate removal.

### Task 3A — Make followed-command transitions explicit

Target files:

- `frontend/src/hooks/useScanCommand.ts`
- `frontend/src/pages/agents/ScanControl.tsx`
- `frontend/src/pages/Agents.command.test.tsx`
- the existing agent MSW harness files only if a new transition fixture is required

Implementation contract:

1. Keep one `followedCommandId` as the sole query-key source.
2. Track the last `active_command_id` value observed from agent detail separately. Adopt only a
   newly observed non-null server id. An unchanged cached old id must never overwrite a locally
   accepted replacement id.
3. A successful POST and a successful busy adoption both replace `followedCommandId`; `null` never
   clears it in-session.
4. Make `trigger()` report whether the operator action established a followed command. Key the
   focus request to that completed user action or to a user-start generation, not to the boolean
   presence of any followed command.
5. Keep the followed slot mounted immediately after POST success while the first command GET is
   pending, and keep duplicate POST protection.
6. Do not focus on passive mount/background adoption. Do focus the status region after successful
   `[Scan now]` and after successful terminal `[Retry]`.

Required tests, written before the implementation adjustment:

- adopted old terminal id → Retry POST returns new id → unchanged cached old id remains present →
  new id is still queried and rendered;
- false→id `[Scan now]` focuses the status region;
- old-id→new-id `[Retry]` focuses the status region;
- passive adoption does not steal focus;
- POST success with pending first GET keeps `Starting…` and prevents a second POST.

### Task 3B — Give the chooser an explicit edit-session boundary

Target files:

- `frontend/src/pages/agents/AgentCard.tsx`
- `frontend/src/pages/agents/TargetSubnetSection.tsx`
- `frontend/src/pages/agents/SubnetChooser.tsx`
- `frontend/src/pages/Agents.test.tsx`
- the existing agent MSW harness files only if a refetch sequence fixture is required

Implementation contract:

1. `AgentCard` owns one exclusive card mode: chooser open or scan control visible, never both.
2. The editable selection belongs to the mounted chooser session, not the lifetime of
   `AgentCard`. Every opening initializes it from the latest `agent.target_subnet` if that CIDR is
   currently reported; otherwise it begins with no valid selection.
3. While the chooser remains open, preserve the operator's draft across a refusal/refetch, but
   derive validity from the latest `agent.available_subnets` on every render. A removed CIDR stays
   visible as the refused draft if needed, but confirm is disabled and cannot issue another PATCH.
4. Both documented PATCH refusals keep the chooser open, retain the stored target, leave focus on
   confirm, show the toast, and expose the same sentence through the confirm button's
   `aria-describedby` polite region. The stale-network refusal re-reads agent detail before the
   next submission is possible.
5. Closing and reopening discards the old draft and starts a new chooser session from current
   server state.

Required tests, written before the implementation adjustment:

- server target A → background refetch target B while chooser is closed → `[Change]` opens with B
  checked and A unchecked;
- operator selects a draft → refusal refetch removes it from the subnet list → confirm disables
  and a second click performs no PATCH;
- chooser open → no `[Scan now]`, `[Retry]`, or command control from the old target is present;
- refused submit keeps focus and has a resolvable `aria-describedby` target with the refusal copy.

### Task 3C — Close the finite presentation and interaction contract

Target files:

- `frontend/src/pages/Agents.tsx`
- `frontend/src/pages/agents/AgentIdentity.tsx`
- `frontend/src/pages/agents/TargetSubnetSection.tsx`
- `frontend/src/pages/agents/ScanControl.tsx`
- `frontend/src/pages/agents/CommandStatus.tsx`
- `frontend/src/pages/agents/AgentsBlank.tsx`
- `frontend/src/pages/Agents.test.tsx`
- `frontend/src/pages/Agents.command.test.tsx`

Implementation contract:

1. The first-load placeholder is the bordered card at real padding with exactly the three designed
   identity, presence, and network bars; it is not a single undifferentiated pulse block.
2. The exact authored type contract is:
   - `agents-presence`: `text-body-md`;
   - `agents-network`: `text-body-md`;
   - `agents-note`: `text-body-md`.
3. `agents-identity` remains on the identity group.
4. The Scans and Hosts closing-note links use a shared interactive primitive and expose cursor,
   hover, focus-visible, active, and accessible-name behavior required by the frontend conventions.
5. Preserve the complete role omission, copy, test-id, terminal-control, and live-region contracts
   already specified; do not alter API or hook semantics in this task.

Required tests, written before the implementation adjustment:

- assert the three loading bars and their distinct designed heights within the card;
- assert `agents-identity` and the exact `text-body-md` classes on presence, network, and Pi note;
- assert the closing links resolve to `/scans` and `/hosts` and carry the shared control's complete
  interaction-state contract;
- retain the full admin/viewer presence/absence matrix.

### Review sequence

Run the normal frontend coder → frontend test engineer → frontend code reviewer loop separately
for 3A, 3B, and 3C. The reviewer for each unit runs the complete frontend gate, but approval is
based first on that unit's explicit transition/presentation matrix. Do not defer a failed matrix
row to a later task.

## 4. Exact spec changes required before implementation resumes

### `TRUTH.md`

Add these acceptance rows without changing existing business scope:

| Scenario | Given | When | Then |
|---|---|---|---|
| Latest target starts a chooser session | A device target was A and a later agent read reports B | The admin opens Change after that read | B is preselected; the stale A value is not |
| Refetch revalidates a chooser draft | A selected chooser CIDR is removed from the newly reported networks | The agent read completes while the chooser remains open | The draft is not submitted again; confirm is disabled until a currently reported network is selected |
| Retry owns its replacement run | A followed failed or expired command and agent cache that still names it | Retry accepts a new command | The new command is followed; unchanged cached old state cannot restore the prior command |
| Retry focus follows the action | Focus is on Retry for a terminal command | Retry accepts a replacement command | Focus moves to the status region for that replacement command |

Clarify rule 23 with one sentence: holding a followed run does not allow unchanged cached
`active_command_id` from that run to overwrite a newer command accepted in the same screen
session.

### `ARCHITECTURE.md`

Make the following section-level edits:

1. **§5.1:** replace the `adopted !== followedCommandId` render-time recipe with a transition table
   containing `followedCommandId`, `lastObservedActiveCommandId`, source, guard, and result. State
   explicitly that only a newly observed non-null agent id may adopt and that a POST response has
   priority over an unchanged cached agent id.
2. **§5.3:** change the public trigger contract from `Promise<void>` to an explicit outcome that
   tells the control whether this operator action established a followed command. Include success,
   busy-with-id adoption, and refusal outcomes.
3. **§6.1:** declare chooser and scan-control rendering mutually exclusive card modes.
4. **§6.3:** move editable selection ownership to the chooser session; define initialization on
   every opening, draft preservation while open, render-time validity against current subnets, and
   invalid-draft submit suppression. Replace "no local error string" with: no visible inline error,
   but a visually hidden polite refusal string exists to satisfy `aria-describedby` while the
   visible treatment remains the toast. State which refusals re-read agent detail.
5. **§6.4:** specify focus through the trigger outcome/user-action generation so both Scan now and
   Retry work and passive adoption does not steal focus.
6. **§11.4:** replace "the refusal renders inside the chooser" with the approved toast plus hidden
   described-live-region assertion. Add the A→B reopening and removed-CIDR validity regressions.
7. **§11.5:** add the unchanged-old-active-id retry regression and explicit Retry focus assertion.
8. **§11:** add a small presentation-contract table covering the three body-md nodes, the
   three-bar skeleton, `agents-identity`, and closing-link interactive states.

### `DESIGN.md`

Make these clarifications:

1. **§5.1:** "current network preselected" means the latest successfully read target at the start
   of each chooser session, not the value from the card's first mount.
2. **§5.3:** the visible refusal remains a toast; a visually hidden polite description is retained
   solely to keep the focused confirm button's refusal announcement and `aria-describedby`
   relationship. A refetch may invalidate the draft and disable confirm without closing the form.
3. **§14:** replace "After triggering" with two explicit rows: after successful Scan now and after
   successful terminal Retry. Both move focus to the status region. Add a row stating passive
   adoption never moves focus.
4. **§2/§13:** add a normative element-to-token table for presence, network, and permanent Pi note;
   all three are `text-body-md`.

### `TASKS.md`

After human approval:

1. replace blocked Task 3 with Tasks 3A, 3B, and 3C from §3, preserving dependencies on Tasks 1
   and 2;
2. give each task its exact target files and matrix-based success criteria;
3. keep Task 3 blocked and its rejection history intact until the replacement tasks are approved;
4. only then reset the active replacement task's review count to zero and start with a fresh coder.

## 5. Human approval gate

No further frontend coding, test editing, or review-remediation loop should begin until a human
approves all of the following decisions:

1. unchanged cached agent state cannot overwrite a newly accepted command;
2. a chooser draft is scoped to one open session and is reinitialized from the latest server target
   on every reopening;
3. a refetch may invalidate, but not silently replace, an in-progress chooser draft;
4. successful Retry has the same focus-transfer obligation as successful Scan now, while passive
   adoption never steals focus;
5. the visible refusal remains a toast and the hidden described live region exists only for the
   focused form-control announcement;
6. Task 3 is replaced by the three reviewable units in §3.

Approval means the human accepts the spec edits in §4 and the revised task decomposition. It does
not approve the current application diff.

## 6. Acceptance criteria for leaving structural block

The structural block may be cleared only when:

- the four spec files are revised as listed in §4 and human-approved;
- `TASKS.md` contains the three replacement tasks with separate review loops;
- the stale active-command retry regression follows the new command;
- successful Scan now and successful Retry both focus `agents-command-status`, and passive adoption
  does not move focus;
- an A→B agent refetch followed by opening Change preselects B;
- a removed subnet disables chooser confirmation and cannot produce a second PATCH;
- chooser mode and scan-control mode never coexist;
- presence, network, and permanent Pi note all use `text-body-md`;
- the loading card, identity test id, refusal description, and closing-link interaction contracts
  are covered by focused tests;
- every original Task 3 success criterion still passes; and
- the frontend reviewer runs the full project gate and returns `[APPROVE]` for each replacement
  task.

Until then, Task 3 remains `BLOCKED_STRUCTURAL` with four recorded rejections.

---

## 7. Frontend-design addendum — visual and accessibility contract

Review role: `frontend-design-agent`  
Review date: 2026-08-29  
Disposition: **the structural direction in §§2–6 is sound, but it is not design-complete without
this addendum. Human approval is still required.**

This addendum converts the visual, interaction, focus, and test-id requirements implicated by the
four rejection rounds into finite contracts. It does not approve the current frontend diff and it
does not authorize application-code or test changes. If approved, this section is normative for
the replacement Tasks 3A–3C and must be reflected in `DESIGN.md` as listed in §7.9.

### 7.1 Chooser ownership and chooser-session lifetime

The card has one owner for its lower interactive mode: `AgentCard`. The two modes are exclusive:

| Card mode | Visible below the identity/target read lines | Must be absent |
|---|---|---|
| **Choosing** | The chooser form | `agents-scan-now` and the complete `ScanControl` slot, including an old terminal action |
| **Control/status** | `[Scan now]`, `Starting…`, or the followed-command status/terminal control | The chooser form |

Opening `[Change]` begins a new chooser session. The session contract is:

1. On every opening, initialize the draft from the **latest successfully read**
   `agent.target_subnet`, not from the value present when `AgentCard` first mounted.
2. Preselect that target only when it still exists in the latest `available_subnets`. If it is no
   longer reported, no option is checked and confirm is disabled.
3. After opening, the operator owns the draft. A background agent read may update the displayed
   stored target and option list, but it must not silently replace the draft selection.
4. Draft validity is nevertheless derived from the latest option list on every render. If a
   refetch removes the selected CIDR, the draft is not submitted again; confirm becomes disabled
   until the operator selects a currently reported option.
5. A PATCH refusal keeps the same chooser session open, preserves the draft for explanation,
   preserves the stored target, and keeps focus on confirm. Closing after success destroys the
   draft; the next opening starts a new session from current server state.

The A→B regression is therefore exact: agent detail first reports target A; while the chooser is
closed, a later successful read reports target B; activating `[Change]` checks B and does not check
A. This is a session-boundary requirement, not prop-to-state synchronization while editing.

The exclusive-mode decision has a visible consequence: opening the chooser temporarily replaces
the command slot even if an earlier command is being followed; polling may continue in data state,
but the slot returns only when the chooser closes. This consequence was not explicit in the
original approved plates and requires the human decision in §7.10.

### 7.2 Refusal announcement while focus stays in the chooser

The visible refusal treatment remains the approved bottom-right toast. It is not duplicated as
visible inline copy and it does not resize the card. Accessibility requires a second, visually
hidden representation of the **same sentence** inside the chooser:

- the hidden node has a stable id, `role="status"`, and `aria-live="polite"`;
- after refusal, `agents-chooser-confirm` references that id with `aria-describedby`;
- the referenced node is present and contains exactly the toast sentence;
- focus remains on `agents-chooser-confirm`; the toast is never focused;
- choosing a different option clears the stale description and relationship;
- a refetch that invalidates the draft disables confirm without closing the form.

This hidden text is local refusal state for announcement only. It is not an inline visual error and
must not be used as a second business-state authority.

### 7.3 Focus transition is keyed to the accepted user action

`following: boolean` is insufficient for focus because terminal Retry is an old-id→new-id
transition. The accessible focus contract is:

| Transition | Focus result |
|---|---|
| Successful `[Scan now]` POST establishes a command | Move focus once to `agents-command-status` as soon as the accepted command replaces the trigger, including while its first GET still reads `Starting…` |
| Successful terminal `[Retry]` POST establishes a replacement command | Move focus once to `agents-command-status`, even though a followed command existed before the click |
| User-triggered `device_busy` refusal successfully adopts an active id | Move focus once to `agents-command-status`, because the acted-on control is replaced by the adopted status |
| Passive mount, reload, focus refetch, or background adoption | Do not move focus |
| POST refusal that establishes no followed id | Keep focus on the still-mounted action control |
| Poll advances or reaches a terminal state | Do not move focus |

The focus request must therefore be driven by the completed action outcome or a user-action
generation, never solely by false→true `following`. The focused region is the same region for
`Starting…` and every fetched lifecycle state, so focus does not bounce when the first command GET
resolves.

### 7.4 Status region and test-id contract

Whenever a command id is being followed and the control/status mode is visible:

- `agents-command-status` is the single status-region root;
- it has `role="status"`, `aria-live="polite"`, and `tabindex="-1"`;
- it renders `Starting…` while the first command read is pending and remains mounted when that read
  resolves;
- it is not in sequential tab order, but is programmatically focusable after the user actions in
  §7.3;
- `agents-pill` exists only after command data exists and wraps the pill in all seven lifecycle
  states;
- `agents-view-scan` exists only for `done` with a non-null `scan_id`;
- `agents-retry` exists only for an admin at `failed | expired`;
- `agents-scan-now` exists only for an admin-ready target with no followed command and no open
  chooser.

Screen-owned test ids retain the `agents-` prefix. The required presentation ids are
`agents-loading`, `agents-card`, `agents-identity`, `agents-presence`, `agents-network`,
`agents-note`, `agents-scans-link`, and `agents-hosts-link`. Shared `toast` remains unprefixed.
No replacement alias or component-local id is acceptable.

### 7.5 Normative type scale

The three ordinary read lines implicated by rounds 3 and 4 have one exact authored scale:

| Element | Token | Notes |
|---|---|---|
| `agents-presence` | `text-body-md` | Muted colour remains; it is a device value, not compact helper copy |
| `agents-network` | `text-body-md` | Muted colour remains; both chosen and viewer no-target sentences use this size |
| `agents-note` | `text-body-md` | The permanent Pi sentence is demoted from title treatment but remains default body copy |

`text-body-sm`, `text-caption-md`, title tokens, and raw Tailwind type utilities fail this contract on
these three nodes. Terminal helper/reason copy and the no-device secondary note are not changed by
this addendum.

### 7.6 Loading card contract

The first-load state is a screen-specific, inert preview of the Agents card, not the shared
table-body `LoadingSkeleton` and not one undifferentiated pulsing rectangle.

- `agents-loading` is the real bordered card surface with `bg-card`, step-6 padding, and the card's
  step-6 inter-group rhythm.
- It contains exactly three bars: one identity bar at the title-line height and two body-line bars
  at the presence and network heights. The identity/presence pair uses step-2 intra-group rhythm.
- The bars have visibly different approved widths so they read as three content lines, not a block.
- Every bar is `aria-hidden="true"`; there is no button, link, radio, status pill, or focusable
  placeholder.
- The page header and permanent closing note remain real and readable during loading.
- Command polling and background agent refetches never restore this skeleton or flicker the card.

The current shared `LoadingSkeleton` renders `<tbody>/<tr>/<td>` and is table-only. `DESIGN.md`'s
statement that it is reused here is incorrect and must be amended; changing that shared component
to accommodate this card is outside Task 3C.

### 7.7 Closing-note link states

`agents-scans-link` and `agents-hosts-link` are inline navigation, implemented through the shared
`Button` primitive with `asChild` and `variant="link"`. Each must meet the complete Foundations
interaction contract:

| State | Required visible/semantic result |
|---|---|
| Rest | Accessible name `Scans` / `Hosts`, correct `href` (`/scans` / `/hosts`), primary link colour, and inline body-md typography |
| Hover | Pointer cursor and visible underline |
| Focus-visible | Visible ring **and** underline; the outline is not removed |
| Active | The shared button's pressed downward nudge |
| Disabled | Not applicable; these readable destinations are always enabled and no disabled styling/attribute is authored |

The rendered nodes must expose the shared primitive's authored `cursor-pointer`, hover,
focus-visible, and active state classes. Merely asserting `data-variant="link"` is not enough: the
focused underline is an explicit Foundations requirement for a control that underlines on hover.
Both links remain in document order after the card/status action and have no custom click handler.

### 7.8 Exact frontend acceptance matrix

The replacement tasks are not complete until focused tests prove every row below. Assertions on
pseudo-class behavior may inspect the shared primitive's rendered class contract because jsdom
cannot visually activate CSS pseudo-classes.

| Contract | Given / action | Required assertion |
|---|---|---|
| Latest target owns opening | Closed chooser; server target changes A→B | Click Change; B checked, A unchecked |
| Missing latest target | Closed chooser; latest target is not in latest options | Open; no radio checked and confirm disabled |
| Draft is session-owned | Open chooser; operator selects C; background read changes stored target | C remains selected while open |
| Refetch revalidates draft | Selected C disappears from refreshed options | Confirm disabled; another activation causes no PATCH |
| Modes are exclusive | Chooser open from first run, Change, or stale-trigger refusal | Chooser present; `agents-scan-now` and the complete old command-control slot absent |
| Refusal is perceivable | PATCH 409 and 422 | Toast visible; confirm focused; resolvable `aria-describedby` target has identical copy, `role=status`, `aria-live=polite` |
| Scan-now focus | Scan now accepts id; first GET pending | `agents-command-status` reads `Starting…`, has focus, `role=status`, `aria-live=polite`, `tabindex=-1` |
| Retry focus | Failed and expired old ids; Retry accepts new id | New id is queried; status region has focus although following was already true |
| Busy adoption focus | User action gets 409 and detail returns active id | Adopted id is queried and status region receives focus |
| Passive adoption | Page mounts with active id | Status renders and previously focused element/body is not programmatically displaced |
| Stable status region | Starting resolves to queued and poll advances | Same test-id region remains; no further focus call/movement |
| Body scale | Ready admin and viewer/no-target render | Presence, network, and permanent note each contain `text-body-md` and not `text-body-sm` |
| Loading geometry | Initial list/detail read pending | Bordered `agents-loading`; exactly three aria-hidden bars: one title-height and two body-height; no interactive descendant |
| Identity contract | Ready state | `agents-identity` wraps `agents-name` and `agents-presence` |
| Scans link states | Ready/blank/error page states where permanent note renders | Accessible `Scans` link to `/scans`; shared link rest/hover/focus-visible/active class contract present |
| Hosts link states | Same | Accessible `Hosts` link to `/hosts`; same complete interaction contract |
| Test-id authority | Every state above | Only the names in §§7.4 and approved `DESIGN.md` §16 are used for these elements |

These tests supplement, rather than replace, every existing Task 3 behavior, role-omission,
lifecycle, refusal, and cache-invalidation assertion.

### 7.9 Required `DESIGN.md` amendments before coding resumes

The human-approved design must be made internally consistent before replacement Task 3A starts:

1. **§2 and §5.1 — ownership:** state that `AgentCard` owns mutually exclusive choosing and
   control/status modes, record the visible consequence for a followed run, and define chooser
   draft lifetime by open session. Define “current network preselected” as the latest successfully
   read and still-reported target on each opening.
2. **§3 — loading:** replace “`LoadingSkeleton` is reused” with the screen-specific three-bar card
   contract in §7.6. The shared table skeleton remains unchanged.
3. **§5.3 — refusal:** keep the toast as the only visible refusal and add the hidden polite
   described region, focus retention, draft revalidation, and description clearing rules. Reconcile
   §12's longer refusal sentences with §5.3 and the current approved short toast sentences; one
   exact pair must appear everywhere.
4. **§7 — scanning:** remove the stale sentence “the hint stays.” §6, §12, and the settled visual
   decision already say the ten-minute hint is removed.
5. **§13 — typography:** add the normative element-to-token table from §7.5.
6. **§14 — focus:** replace the single “After triggering” row with separate successful Scan now,
   successful Retry, user-triggered busy adoption, passive adoption, refusal, and poll/terminal
   rows from §7.3. Define the stable status-region attributes from §7.4.
7. **§14 or the closing-note subsection — link states:** record all five interaction states from
   §7.7, including focus-visible underline as well as the ring.
8. **§16 — test ids:** retain `agents-identity`; make `agents-command-status` the one stable
   live-region/focus target from first pending read through terminal state; retain the exact ids in
   §7.4 without aliases.

`TRUTH.md`, `ARCHITECTURE.md`, and `TASKS.md` still require the changes already listed in §4. This
addendum adds precision to those edits; it does not replace them.

### 7.10 Explicit human approval decision

Implementation must not resume until the human explicitly approves **this complete UI contract**,
including the following visible decision that the earlier plates did not settle:

> **When the network chooser is open, it owns the card's lower mode and temporarily replaces the
> entire scan control/status slot, even if a command is already being followed; polling continues
> and the latest status returns when the chooser closes.**

Approval must also select the one chooser-refusal copy pair to normalize in `DESIGN.md`. The
frontend-design recommendation is the short, already-rendered pair from §5.3 — “Couldn't reach the
Pi; nothing changed.” and “The Pi doesn't report that network any more; nothing changed.” — because
the toast and hidden description must be identical and concise.

An acceptable approval is explicit agreement with §§7.1–7.9, the exclusive-mode sentence above,
and the recommended short refusal copy. General approval of “the approach” is not sufficient. If
the human wants the active command status to remain visible beside an open chooser, the exclusive
mode, composition, plates, and acceptance matrix must be redesigned before any coder resumes.
