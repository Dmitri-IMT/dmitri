# DR-0002 — Acceptance drops the confirm-your-address field, in this spec

**Status:** accepted
**Decided:** 2026-08-06, during `/refine-specs` on spec 027
**Widens:** DMI-86's "no change to `POST /invites/accept` semantics" fence, which was
human-validated 2026-07-28. Recorded here rather than done quietly.

## Decision

`POST /api/v1/invites/accept` takes `{token, password}`. The `email` field is removed, along
with the mismatch check, `InviteEmailMismatchError`, and the `invite_email_mismatch` error
code. This ships in spec 027 alongside the lookup, not as a follow-up issue.

## Why the field stops making sense

Acceptance asks the invitee to type the address the invitation was sent to, and rejects a
mismatch (`backend/src/api/services/invites.py:108`). That was a proof-of-knowledge step: it
was the only evidence the person held the right invitation, because the page had no way to
know the address.

The lookup destroys that property. It hands the address to anyone holding the token — which
is exactly the population that can accept — so submitting it back proves nothing. Its
residual value was catching a mis-paste when someone holds two invitations, and prefill
removes that path too.

The field never carried security weight in the first place. The token is the credential, and
the account has always been created from the invitation record (`email=invite.email`), never
from the submitted value.

## Why in this spec rather than its own issue

Considered and rejected: file a follow-up and sequence it before DMI-87.

The argument for splitting was that removing a field from a request model with
`extra="forbid"` is a breaking contract change. That argument assumes deployed clients and a
migration window. **There are none** — the only reference to the accept route outside
`backend/` is the generated `frontend/src/types/openapi.d.ts`; no accept screen, no API call,
no users. Verified 2026-08-06.

Without clients, the "breaking change" costs one more file in one more PR. Splitting it would
have meant two branches, two reviews, and a window where the contract carries a field that the
spec that created its redundancy already documented as pointless.

## Scope of the change

Removing the parameter is not the whole edit. `accept_invite` uses `email` in two further
places, and both must be **re-sourced from the invitation**, not deleted:

- the already-registered lookup (`services/invites.py:112`) → `invite.email`
- `validate_policy(password, email=email)` (`services/invites.py:117`) → `invite.email`

Deleting rather than re-sourcing the second would silently stop the password policy from
considering the address. `ARCHITECTURE.md` carries the full file list.

## What protects this change

`AcceptInviteRejected` is registered in `test_contract_fidelity.ERROR_RESPONSE_ROUTES`, so
the test asserts that the contract's `error.code` enum for acceptance's `400` equals the set
of codes the handler actually raises. Dropping `invite_email_mismatch` from one side without
the other fails the suite. The change cannot drift.

## Consequence

- `docs/ui/FLOWS.md` § B2 breadboard lists `400 invite_email_mismatch → inline error under
  the email field`; that line and the email field go.
- `docs/ui/SCREENS.md` ACCEPT INVITE describes a form of email + password + confirm; it
  becomes a greeting plus password + confirm.
- DMI-87 builds the simpler form — the reason this is worth doing before that issue starts.
- `frontend/src/types/openapi.d.ts` is generated; it is regenerated from the contract, not
  hand-edited.
- Historical specs 017 and 023 describe the old shape. They are history and are **not**
  rewritten.
