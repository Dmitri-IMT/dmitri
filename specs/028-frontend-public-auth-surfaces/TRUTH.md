# TRUTH — Frontend public auth surfaces

Domain language and verifiable behaviour only. No file paths, no code.

## Narrative

Login exists, but invited users cannot create their account, locked-out users cannot recover
access, and signed-in users cannot change their own password. The pilot needs these recovery and
onboarding paths so access does not depend on a single account that can never recover. This feature
adds invite acceptance, forgot-password, reset-password, and voluntary password change while
preserving the product's security boundaries and established screen language.

## Business rules

- An invite link identifies the invitation before any password form is shown. A live invitation
  shows the organisation and offered role. The lookup also returns the invited email, but the page
  neither renders it nor asks the user to retype or submit it.
- Accepting an invitation requires a password and confirmation. Success creates the account,
  signs the invitee in, and lands them on Home without a second login step.
- Unknown, expired, and already-used invite tokens are indistinguishable. A dead invite never
  shows a password form and tells the user to ask their administrator for a new link.
- Invite lookup does not consume the invitation.
- A visitor who already has a session cannot accept an invitation. The invite page tells them to
  sign out first and offers that action; the invitation is neither read nor consumed. Requesting and
  completing a password reset remain available to a signed-in visitor.
- Password policy failures remain on the active form and are shown beside the password field.
- If the invited address already has an account, acceptance keeps the form available, explains the
  conflict, and offers a path to sign in instead.
- Forgot-password reveals nothing about whether an email address has an account. Known and unknown
  addresses receive the same confirmation.
- A reset link is single-use. An absent, unknown, expired, or already-used reset token shows the
  same dead-link state and offers a path to request another link.
- Resetting a password does not sign the user in. Success returns the user to Login with confirmation
  that the new password is ready to use.
- A signed-in admin or viewer may change their own password. A wrong current password is a field
  error, not a session failure, and must not log the user out or navigate away from Settings.
- Successful voluntary password change keeps the user on Settings and confirms completion inline.
- Settings is available from the authenticated navigation to both admins and viewers.
- Passwords must contain at least 12 characters and must satisfy the established password policy.
- Every form has deliberate idle, submitting, validation-error, server/network-error, and success
  behaviour where that state is applicable.
- All interface wording comes from the approved screen specification; implementation does not
  invent replacement copy.

## User stories

1. As an invited user, I want to see which organisation invited me and at what role before choosing
   a password, so that I can trust the invitation and enter the product directly.
2. As a locked-out user, I want to request a reset link without revealing whether an account exists,
   so that I can recover access safely.
3. As a user with a live reset link, I want to choose a new password and return to sign in, so that I
   can regain access.
4. As a signed-in admin or viewer, I want to change my password without losing my session, so that I
   can maintain my account from Settings.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Live invite is identified | An unconsumed, unexpired invite link | The invite page opens | The organisation, offered role, and invited email are loaded; the page shows the org/role greeting plus password and confirmation fields, and does not render or submit the invited email |
| Invite lookup is non-consuming | A live invitation | The invitation is read more than once before acceptance | Each read succeeds and the invitation remains available for acceptance |
| Signed-in visitor cannot accept an invite | A signed-in user and a live invite link | The invite page opens | No invitation is read, no password form is rendered, the page explains that they must sign out first, and signing out from there returns them to Login with the invitation still usable |
| Invite acceptance signs in | A live invitation and a policy-compliant matching password | The invitee creates the account | The account is created, a session is established, and Home opens without showing Login |
| Dead invite is terminal | An absent, unknown, expired, or used invite token | The invite page opens or acceptance reports the dead token | The same dead-link explanation appears, no password form is rendered, and the only recovery guidance is to ask an administrator for a new invite |
| Invite password is rejected inline | A live invitation and a password that violates policy | The invitee submits the form | The form remains visible and the approved policy message appears beside the password field |
| Invite confirmation mismatch | A live invitation with different password and confirmation values | The invitee submits the form | No acceptance is attempted and the approved mismatch message appears inline |
| Invited address already has an account | A live invitation whose address is already registered | The invitee submits a valid password | The form remains available, the approved account-conflict message appears, and the user can go to Login |
| Forgot-password is non-enumerating | One known address and one unknown address | A reset is requested for each | Both requests replace the form with the same confirmation structure and wording |
| Reset succeeds without a session | A live reset link and a policy-compliant matching password | The user resets the password | Login opens with confirmation that the password was set; no authenticated session is created by the reset |
| Dead reset link is terminal | An absent, unknown, expired, or used reset token | The reset page opens or reset reports the dead token | The password form is removed and the user can request a new reset link |
| Reset password is rejected inline | A live reset link and a password that violates policy | The user submits the reset form | The form remains visible and the approved policy message appears beside the new-password field |
| Wrong current password preserves session | A signed-in admin or viewer on Settings | They submit an incorrect current password | The approved field error appears inline, Settings remains open, and no navigation to Login occurs |
| Voluntary password change succeeds in place | A signed-in admin or viewer with the correct current password and a compliant new password | They change their password | Settings remains open and the approved success confirmation appears inline |
| Settings is available to both roles | A signed-in admin or viewer | They use the authenticated navigation | A Settings destination is present and opens the voluntary password-change form |
| Settled messages survive editing | Any auth form showing a field error, form error, or success confirmation | The user edits a field without submitting | The message remains readable beside its field, and is cleared only when the next submission begins |
| Submitting state prevents duplicate work | Any auth form with a request in progress | The user submits it | The action communicates progress and cannot be submitted again until the request settles |
| Network or server failure is recoverable | Any auth request cannot reach the service or receives an unexpected server failure | The request settles | The relevant form or page remains available with approved retry guidance and no false success state |

## Out of scope (v1)

- Users and invitations administration.
- Profile viewing or editing in Settings.
- Password-strength meters.
- Multi-factor authentication.
- Session-management interfaces.
- Forced or periodic password rotation.
- New backend capabilities or alternate client-side representations of existing contracts.
- Changes to Login or Home beyond the navigation and confirmation edges required by these flows.

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`

## Docs drift (docs-sync, 2026-08-07)

Reported for a human call; **not** applied:

- **`format:check` fails repo-wide on this Windows working copy** — ~50 files, including ones no
  feature touched, because the checkout is CRLF and Prettier expects LF. It reproduces on a clean
  tree. The fix is a `.gitattributes` / `core.autocrlf` decision, not a formatter run (forbidden by
  `.claude/CLAUDE.md`), and it is a repo-hygiene task rather than part of this feature.
- **The Vitest forks pool cannot spawn workers on the same machine**, so the gate had to be run as
  `--pool=threads --maxWorkers=1 --no-file-parallelism` throughout. Whether to pin that in
  `vitest.config.ts` or leave it as a local workaround is a human call.
- **`AcceptInvite` fires one transient `/invites/lookup` on sign-out** — `signOut` clears the session,
  the page re-renders as `anonymous` (enabling its query) and is then unmounted by the navigation.
  Benign today because lookup is non-consuming; it becomes a bug if that ever changes. The reviewer
  ruled it acceptable rather than adding a suppression flag.
- **`docs/ui/status.md` and `docs/roadmap/FRONTEND.md` still describe invite/reset email delivery as
  unbuilt** — correct, and left alone: the screens exist but the provider and SPF/DKIM/DMARC
  decision (C17) is open, so these flows are not usable end to end.
