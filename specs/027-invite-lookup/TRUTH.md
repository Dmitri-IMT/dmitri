# TRUTH — Read an invite before accepting, and stop asking for the address

Domain language and verifiable behaviour only. No file paths, no code.

Closes contract ask **C14** (`docs/ui/FLOWS.md` § Contract asks, restated in
`docs/roadmap/BACKEND.md` § B11). Linear: **DMI-86**, under epic DMI-70.

**Two deliverables, one branch.** The lookup is what C14 asked for. Dropping acceptance's
confirm-your-address field is the direct consequence of it, folded in here by decision on
2026-08-06 — see [`decisions/DR-0002-accept-drops-email.md`](decisions/DR-0002-accept-drops-email.md).
This widens DMI-86's original "no change to acceptance" fence, deliberately and on the
record.

## Narrative

Someone is invited to an organisation and receives a single-use link by email. The page
that link opens knows nothing about the invitation it is rendering — not the organisation
that sent it, not the role being offered, not even the address it was sent to.

Two consequences, both bad:

1. **It cannot prove it is legitimate.** A security product asking a stranger to choose a
   password on an unlabelled page is shaped exactly like a phishing page. The one sentence
   that would settle it — *"You've been invited to Acme as a viewer"* — cannot be written.
2. **The invitee must type their own address from memory** so it matches the invitation
   exactly. A typo fails identically to a dead link, so the page cannot even word its own
   error honestly.

A public, read-only lookup on the invitation token fixes both. The invitation is a
credential, so reading one must not spend it, must not reveal anything beyond what the
invitee is about to be told anyway, and must not become a way to discover which addresses
or organisations exist.

**And it retires a step that only made sense while the page was blind.** Acceptance
currently asks the invitee to confirm their own address, because typing it was the only
evidence they knew which invitation they held. Once the lookup hands that address to the
page, submitting it back proves nothing: anyone holding the token can read it. The account
was always created from the invitation record regardless of what was typed. So acceptance
should ask for the token and a password, and nothing else — one fewer field, one fewer way
to fail, and one fewer error state the first screen of the product has to word.

Both halves ship together because the second is only safe once the first exists, and
because nothing consumes either yet: there is no accept screen and no client of any kind
today, so the request shape can still be changed for free.

## Business rules

- Reading an invitation requires **no authentication** — the reader has no account yet;
  that is the whole point of the invitation.
- Possession of the token is the only authorisation. Nothing else identifies the reader.
- **Reading does not consume the invitation.** It stays single-use for acceptance, and it
  may be read any number of times before then.
- A readable invitation discloses exactly three things: the invited address, the offered
  role, and the organisation's name. Nothing else about the organisation, the inviter, any
  user record, or the token itself is disclosed.
- An invitation that is **expired, already accepted, or unknown** is reported as *gone* —
  the same answer in all three cases. The response must not let a caller distinguish an
  address that was never invited from one whose invitation lapsed.
- The failure answer is worded identically to the one acceptance already gives for the same
  conditions, so the page renders one dead-link state rather than two.
- Reading an invitation never changes any stored state.
- **The lookup is advisory display data, never authority.** The organisation, the role, and
  the address a new account receives are read from the invitation record at the moment it is
  accepted. They are never taken from the accepting request, so nothing a caller sends — or
  rewrites in a proxied response — can alter the privileges granted. A request that tries to
  supply them is rejected outright rather than quietly ignored.
- Guessing an invitation token is not a practical attack: tokens carry 256 bits of entropy.
  That, not throttling, is what protects the lookup — there is no rate limiting in the
  service today.
- **Accepting an invitation requires the token and a chosen password, and nothing else.**
  The invitee is never asked to confirm their own address. Supplying one is rejected rather
  than ignored.
- The address the new account is created with, the password rules it is checked against, and
  the test for whether that address already has an account are all taken from the invitation
  record. Removing the confirmation step changes what a caller *sends*; it changes nothing
  about what the service *does*.
- Acceptance no longer has a mismatched-address failure, because there is no address to
  mismatch. Its other failures — dead token, address already registered, password rejected
  by policy — are unchanged.

## User stories

1. As an invited person, I want the page to name the organisation that invited me and the
   role I am being offered, so that I can tell the link is genuine before I choose a
   password.
2. As an invited person, I want my email address filled in from the invitation rather than
   typed from memory, so that I cannot fail acceptance over a typo.
3. As an invited person following a stale link, I want to be told plainly that the
   invitation is no longer usable, so that I know to ask for a new one instead of retrying.
4. As the person running the organisation, I want a leaked or guessed token to reveal
   nothing about who else was invited, so that the invitation flow is not an enumeration
   oracle.
5. As an invited person, I want to choose a password and be done, without being asked to
   retype an address the page already shows me, so that accepting takes one decision
   instead of two.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Reads a live invitation | A pending, unexpired invitation exists | Its token is looked up with no credentials of any kind | The invited address, the offered role, and the organisation name are returned |
| Needs no authentication | No session, no bearer token, no cookie | A live token is looked up | The lookup succeeds; it is never rejected for being unauthenticated |
| Read is non-consuming | A pending invitation exists | Its token is looked up twice in a row | Both reads succeed and return identical content |
| Read leaves acceptance intact | An invitation has been read one or more times | The same token is then used to accept | Acceptance succeeds exactly as if the invitation had never been read |
| Accepted invitation is gone | An invitation has been accepted | Its token is looked up | The lookup reports the invitation gone, using the same failure the acceptance flow already uses for a spent token |
| Expired invitation is gone | An invitation's expiry has passed without acceptance | Its token is looked up | The lookup reports the invitation gone |
| Unknown token is gone | No invitation exists for the token | It is looked up | The lookup reports the invitation gone, indistinguishable — status, failure code, and body — from the expired and accepted cases |
| No enumeration signal | Both an expired invitation and a fabricated token are available | Each is looked up | The two responses are identical in status, failure code, and body; neither reveals which case occurred |
| Discloses nothing extra | A live invitation exists | Its token is looked up | The response carries no password hash, no user identifier, no organisation identifier, no token material, and no timestamps beyond what the three disclosed fields require |
| Acceptance still issues a session | A live invitation and a policy-compliant password | The invitation is accepted | A created session is returned exactly as before — the success shape is unchanged |
| Acceptance takes token and password only | A live invitation | It is accepted with just the token and a password | It succeeds; no address is required |
| A supplied address is rejected | A live invitation | Acceptance is attempted with an address included alongside the token and password | The request is rejected as malformed — not accepted-and-ignored |
| The account still comes from the invitation | A live invitation for a given address, role and organisation | It is accepted | The created account carries that address, that role and that organisation, sourced from the invitation record |
| Password rules still see the address | A live invitation | Acceptance is attempted with a password that the policy rejects on the basis of the invited address | It is rejected by policy exactly as before, proving the address is still supplied to the check internally |
| Duplicate detection still works | An address that already has an account, and a live invitation for it | It is accepted | It fails as already-registered, exactly as before |
| Mismatched-address failure is gone | The acceptance flow after this ships | Its failure modes are enumerated | Dead token, already-registered and policy-rejected remain; mismatched-address no longer exists, in the code or in the published contract |
| Contract is published | The feature is implemented | The published API contract is inspected | The lookup appears with its success shape and its gone-failure; acceptance's request no longer carries an address and its failure list no longer offers a mismatched-address code; the contract-fidelity check passes |

## Out of scope (v1)

- **Any further change to acceptance.** Its success shape (a created session), its remaining
  failures, its single-use semantics, and the invitation lifetime all stay exactly as they
  are. The *only* change is that the invitee no longer supplies an address.
- Invitation resend, revoke, or listing — those belong to the admin surface (C4 / DMI-76).
- The ACCEPT INVITE screen itself. This spec delivers the read capability and the simplified
  acceptance request; the page that consumes both is DMI-87.
- **Rate limiting.** There is none in the service today — not on this route, not on any
  route — and this feature does not add it. Token entropy is the protection; see the business
  rule above. If throttling is ever wanted it is a service-wide concern, not this endpoint's.
- Any change to invitation lifetime, token generation, or single-use semantics.
- Removing the token from the browser's address bar or history on the accept page. The
  emailed link already carries it there; that is a frontend concern, not this one.

## Open questions

None — see [`open-questions/to-define.md`](open-questions/to-define.md). The one question
that was open (the lookup's transport shape) was settled on 2026-08-06 and is recorded in
[`decisions/DR-0001-invite-lookup-transport.md`](decisions/DR-0001-invite-lookup-transport.md).

## Related specs

- Implementation: `ARCHITECTURE.md`
- Decisions: `decisions/DR-0001-invite-lookup-transport.md`,
  `decisions/DR-0002-accept-drops-email.md`
- No `DESIGN.md` — this feature changes no screen. The screen that consumes it is DMI-87,
  whose form loses a field as a result.
- Prior art: `specs/017-auth-middleware-invite-flow/`, `specs/023-auth-invite-contract-edges/`

## Docs drift (docs-sync, 2026-08-06 — RESOLVED)

`.claude/docs` is fully synced. The `docs/` claims below were flagged as stale and deliberately
left for a human call; **all were patched on 2026-08-06** before the feature was pushed.

**The distinction that governed the patch:** C14's *endpoint* is built. The *screen* that consumes
it (ACCEPT INVITE, DMI-87) is not. So ACCEPT INVITE keeps its `◐`, but for a new reason — the
endpoint exists and nothing consumes it, not "there is no endpoint".

| File | Stale claim | Resolution |
|---|---|---|
| `docs/roadmap/BACKEND.md` | C14 row ended "**Specced, not yet built** (DMI-86)" | Row struck through and marked ✅ RESOLVED; notes the endpoint is unconsumed pending DMI-87. |
| `docs/roadmap/BACKEND.md` | C15 row: "*once* the invite lookup lands, `invite_email_mismatch` is removed" | Rewritten in past tense; the two surviving `400` codes are named. |
| `docs/ui/FLOWS.md` | C14 row: "Specced in `specs/027-invite-lookup/` (DR-0001); **not yet built**" | Row struck through and marked ✅ RESOLVED. |
| `docs/ui/FLOWS.md` | B2 breadboard: "Decided 2026-08-06, not yet built" | Now "Built 2026-08-06"; the lookup call and its 410 were added to the breadboard. |
| `docs/ui/SCREENS.md` | "**The `email` field is being removed** … not yet built" | Now past tense, plus a `POST /invites/lookup` data row; the copy table, the field list and the ASCII mockup lost the email field and gained the org/role greeting. |
| `docs/ui/SCREENS.md` | "There is **no invite-lookup endpoint yet**" | Replaced with "the screen can now greet you", noting the endpoint is unconsumed. |
| `docs/ui/SCREENS.md` | Open question 1: "**not yet built**, so this screen stays `◐`" | Struck through and resolved; the screen-status row now reads `◐ (C14 resolved; endpoint unconsumed — DMI-87)`. |
| `docs/ui/status.md` | "accept invite C14" / "B1/B2 wait on C14, C15, C16" | Both corrected — B2 no longer waits on a contract ask. |

**Not patched (pre-existing, out of scope):** `docs/ui/status.md`'s "Fourteen contract asks" tally
was already stale before this feature — C9, C11, C15 and C18 all resolved without it being
recounted. It needs a full recount, not a decrement.
