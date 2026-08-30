# TASKS — Agents screen, the scan trigger, and the status pill

Execution agents: `agent-developer` → `frontend-test-engineer` → `frontend-code-reviewer`.

## Task 1: Add typed agent APIs, query keys, and pure mappings
- **Description**: Add the contract-typed agent and command API functions, quick-mode and polling constants, hierarchical query keys, and the pure command-status and subnet-label helpers that the Agents screen will consume. Keep command status separate from scan status, use generated API types only, and leave contracts and generated types untouched.
- **Dependencies**: —
- **Target Files**: [`frontend/src/api/agents.ts`, `frontend/src/api/commands.ts`, `frontend/src/api/queryKeys.ts`, `frontend/src/lib/commandStatus.ts`, `frontend/src/lib/subnetLabel.ts`, `frontend/src/lib/commandStatus.test.ts`, `frontend/src/lib/subnetLabel.test.ts`]
- **Success Criteria**: All five API calls use `apiClient` with generated request/response types; `QUICK_SCAN_MODE` and `COMMAND_POLL_INTERVAL_MS` have the specified values and homes; agent and command query keys preserve prefix invalidation; all seven command states map to the specified label/tone and exactly `done | failed | expired` are terminal; subnet helpers map Ethernet/Wi-Fi/default-route/raw-interface labels and locate a reported CIDR; focused tests cover the pure helpers; no contract, generated type, backend, hardware-agent, `scanStatus.ts`, or `scanFailureReasons.ts` file changes.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 2: Add reusable first-scan blank-state affordances
- **Description**: Extend the shared blank-state pipeline with independent action and note slots, add the role-aware first-scan CTA/note pair, resize the shared status pill as approved, and wire the new admin/viewer empty states into Home, Scans, and Hosts while retiring their temporary Pi sentence.
- **Dependencies**: 1
- **Target Files**: [`frontend/src/components/EmptyState.tsx`, `frontend/src/components/ListSurface.tsx`, `frontend/src/components/FirstScanCta.tsx`, `frontend/src/components/StatusPill.tsx`, `frontend/src/pages/home/HomeBlank.tsx`, `frontend/src/pages/Scans.tsx`, `frontend/src/pages/Hosts.tsx`, `frontend/src/components/EmptyState.test.tsx`, `frontend/src/components/FirstScanCta.test.tsx`, `frontend/src/pages/Home.test.tsx`, `frontend/src/pages/Scans.test.tsx`, `frontend/src/pages/Hosts.test.tsx`]
- **Success Criteria**: `EmptyState` and `ListSurface` independently support optional action and note content without component-owned outer margins; `FirstScanCta` renders only for admins and links to `/agents`, while `FirstScanNote` renders only for viewers; Home, Scans, and Hosts show the CTA to admins and the admin-direction note to viewers and remove the retired Pi sentence; `StatusPill` changes only padding/type sizing to match the trigger height and adds no tone; focused component and screen tests cover both roles and slot presence/absence.
- **Status**: COMPLETED
- **Review Rejections**: 1

Structural history: the original Task 3 was marked `BLOCKED_STRUCTURAL` after 4 review rejections. The human approved `STRUCTURAL_REEVAL.md` on 2026-08-29, including the exclusive chooser mode, canonical short refusal copy, and replacement Tasks 3A–3C below.

## Task 3A: Make followed-command transitions explicit
- **Description**: Correct the followed-command authority and focus model without changing the screen's business scope. Keep one followed command id as the query source, distinguish newly observed server ids from unchanged cached ids, give accepted user actions priority, and drive focus from accepted action outcomes rather than a boolean following transition.
- **Dependencies**: 1, 2
- **Target Files**: [`frontend/src/hooks/useScanCommand.ts`, `frontend/src/pages/agents/ScanControl.tsx`, `frontend/src/pages/Agents.command.test.tsx`, `frontend/src/test/mswHandlers.ts`, `frontend/src/test/agentsHarness.ts`]
- **Success Criteria**: A newly observed non-null active command may be adopted, but unchanged cached agent state never overwrites a newer locally accepted command; successful Scan now, Retry, and user-triggered busy adoption each follow the accepted command and move focus exactly once to the stable `agents-command-status` region; passive mount/refetch adoption never steals focus; POST success keeps `Starting…` mounted until the first command GET resolves and duplicate POSTs remain impossible; null server state never clears the latched command in-session; existing polling, terminal stop, done invalidation, refusal, role, and lifecycle tests continue to pass; focused regressions cover every ARCHITECTURE.md §5 transition row and DESIGN.md §14 focus row.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3B: Give the chooser an explicit edit-session boundary
- **Description**: Make choosing and command control exclusive card modes and scope editable network selection to one open chooser session. Initialize each session from the latest valid server target, preserve the operator's draft while open, and revalidate it against every refreshed subnet list.
- **Dependencies**: 3A
- **Target Files**: [`frontend/src/pages/agents/AgentCard.tsx`, `frontend/src/pages/agents/TargetSubnetSection.tsx`, `frontend/src/pages/agents/SubnetChooser.tsx`, `frontend/src/pages/Agents.test.tsx`, `frontend/src/test/mswHandlers.ts`, `frontend/src/test/agentsHarness.ts`]
- **Success Criteria**: Opening the chooser always replaces the entire lower command/status mode while polling may continue; reopening initializes from the latest successfully read target only when currently reported; an A→B background refetch while closed opens with B selected and A unselected; while open, background reads do not silently replace the operator's draft, but removing its CIDR disables confirmation and prevents a second PATCH; both PATCH refusals preserve the stored target and draft, keep focus on confirm, show the canonical short toast, and expose identical copy through a resolvable polite `aria-describedby` region; changing selection clears stale refusal description; success closes the session and the next open starts fresh.
- **Status**: COMPLETED
- **Review Rejections**: 0

## Task 3C: Close the presentation and interaction contract
- **Description**: Verify and correct the finite visual, role, accessibility, copy, and test-id contract for the completed Agents screen without changing API or command semantics.
- **Dependencies**: 3A, 3B
- **Target Files**: [`frontend/src/pages/Agents.tsx`, `frontend/src/pages/agents/AgentIdentity.tsx`, `frontend/src/pages/agents/TargetSubnetSection.tsx`, `frontend/src/pages/agents/ScanControl.tsx`, `frontend/src/pages/agents/CommandStatus.tsx`, `frontend/src/pages/agents/AgentsBlank.tsx`, `frontend/src/pages/Agents.test.tsx`, `frontend/src/pages/Agents.command.test.tsx`]
- **Success Criteria**: First load renders the inert bordered Agents card with exactly three aria-hidden bars at the approved identity/presence/network heights and no interactive descendant; `agents-presence`, `agents-network`, and `agents-note` use `text-body-md` and not compact/title tokens; `agents-identity` wraps name and presence; Scans and Hosts closing links use the shared link primitive with correct names/hrefs and complete cursor, hover, focus-visible, active class contract; the stable status region, pill/link/retry/scan-now testids, role omissions, exact copy, blank/error/regular states, all lifecycle states, and the complete DESIGN.md §16.1 acceptance matrix are covered by focused tests; no API/hook semantics or out-of-scope files change.
- **Status**: COMPLETED
- **Review Rejections**: 1
