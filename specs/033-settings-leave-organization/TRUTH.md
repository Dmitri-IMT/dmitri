# TRUTH — Leave the organization from Settings

> Source issue: [DMI-103](https://linear.app/dmitri-imt/issue/DMI-103/frontend-leave-the-organization-in-settings-confirm-by-typing) ·
> Epic DMI-48 · Milestone "MVP — Control" · Validated by @guilhermeronca on 2026-08-08.
> Decision record: `docs/adr/ADR-017-account-removal.md`. Screen spec: `docs/ui/SCREENS.md`
> § SETTINGS and § LOGIN. Flow: `docs/ui/FLOWS.md` B5.

## Narrative

Dmitri has a way in and no way out. A member is created by an invite; nothing removes them.
Someone who leaves the company keeps a working account — their password still authenticates and
they still read every scan, host and finding in the organization. The backend half of the fix
already shipped: an account can be deleted, and deleting it destroys its sessions.

What is missing is the way a person asks for it. Settings is where it belongs, and it must be
there for **both roles**. A viewer never sees the Users screen, so Settings is their only exit;
an admin's own row on the Users screen deliberately carries no Remove action, so Settings is
their only exit too. This is the single self-service path out of the organization for everyone.

Leaving is irreversible and it kills a live session, so a single click is not proportionate to
it. The person confirms by typing their own email address. That same confirmation — type the
address of the account being removed — is what an admin will use to remove somebody else on the
Users screen, so it is built once here as a shared capability with two named callers.

One case cannot be answered before the attempt: an organization's only admin may not leave,
because an organization with no admin can invite nobody and manage nothing. The application
cannot know it is the last admin without asking, so this is a refusal explained after the
attempt, never a control shown greyed-out in advance.

## Business rules

- Leaving the organization is offered to **every** signed-in member, admin and viewer alike.
- The leaving section is the **last** thing on Settings and is visually separated from the rest.
  It is not what anyone came to Settings to do.
- The confirmation is a modal. Its confirming action is greyed out and not clickable until the
  person has typed their own email address exactly, and becomes live the instant it matches. A
  mistyped address can never trigger the request.
- The confirmation is the only gate. There is no second "are you sure?" after it.
- On success the person's session no longer exists: the application discards its in-memory access
  token and sends them to the sign-in screen, which greets them with a confirmation that the
  account was deleted. It is a confirmation, not an error, and reads as one.
- That confirmation line **does not survive a reload**. A stale "your account was deleted" on a
  shared machine is confusing and a small disclosure.
- When the person is their organization's only admin, the request is refused. They stay on
  Settings with their session intact and are told what to do first: make someone else an admin.
- The confirming behaviour is a **shared capability**, not a control private to this screen.
  Whether its action is greyed out is decided by the capability itself, from the typed value and
  from whether a request is outstanding — a caller cannot ask for a different variant, greyed or
  live. Both call sites get the same behaviour: greyed out and not clickable until the typed value
  matches exactly, then live.
- An action a role cannot perform is absent from the page, never greyed out — the viewer never
  learns what they're missing. The confirming action is a different case: it is an action the
  person **is** allowed to take, but has not yet supplied the required input for. It is greyed
  out and not clickable until the typed address matches exactly, at which point it becomes live —
  continuous feedback, so the person watches the action come alive as they finish typing rather
  than pressing it and being told no. The one further exception is the moment a submitted request
  is outstanding: the control that sent it is greyed out and not clickable until the answer
  arrives, exactly as every other submitting control in the product already behaves. Both are a
  report of the person's own progress or the product's own work in progress — never a statement
  that the action itself is off-limits.
- The organization's name is **not available** to a signed-in member (the profile a member reads
  carries their id, email and role only). The leaving copy therefore names the organization
  generically rather than by name, and no new request is made to discover it.

## User stories

1. As a viewer, I want to delete my own account, so that I can leave without asking an admin to
   do it for me.
2. As an admin, I want to leave the organization after handing over to another admin, so that my
   access ends when my involvement does.
3. As the only admin, I want to be told plainly why I cannot leave yet and what to do first, so
   that a refusal is a next step rather than a dead end.
4. As anyone about to leave, I want the irreversible action to take a deliberate act of typing,
   so that I cannot destroy my access with a single stray click.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Viewer sees the exit | a signed-in viewer | they open Settings | the leaving section is present, last on the page, with its explanation and its trigger |
| Admin sees the same exit | a signed-in admin | they open Settings | the same section appears, with the same copy and the same behaviour |
| Typing gates the action | the confirmation is open | the typed value is empty, partial, or a different address | the confirming action is greyed out and not clickable, and no removal is requested |
| Exact match releases the action | the confirmation is open | the person types their own email address exactly, then confirms | the removal is requested once |
| Successful removal | the removal succeeds | the response arrives | the access token is discarded and the person lands on the sign-in screen showing "Your account has been deleted." |
| Confirmation is transient | the person is on the sign-in screen after removal | they reload the page | the deletion confirmation is no longer shown |
| Only admin refused | the person is their organization's only admin | they complete the confirmation | they stay on Settings, their session is intact, and they read "You're the only admin. Make someone else an admin first, then you can leave." |
| Server failure | the removal request fails for any other reason | the response arrives | the person stays on Settings and reads a failure message that offers another attempt |
| Cancelling | the confirmation is open | the person cancels or dismisses it | nothing is requested, and Settings is unchanged |
| Nothing is unavailable, except the confirming action | either role | the page renders at rest, or the confirmation is open at any typed value — empty, partial, or exact — or a removal request is outstanding | at rest, no element on the page is greyed out or announced as unavailable; inside the confirmation, every element is live except the confirming action, which is greyed out and not clickable until the typed address matches exactly, and again while the removal request is outstanding |

## Out of scope (v1)

- Any change to the Users screen, including removing other people (DMI-90).
- Account recovery, undo, or a grace period.
- A pre-refused "you are the last admin" state shown before the attempt.
- **Making somebody else an admin.** The refusal tells the only admin to do this first, and in v1
  there is no screen where they can: the operation exists, the screen that offers it is the Users
  screen (DMI-90). Until it ships, an organization's only admin cannot leave. This is accepted, not
  overlooked — the refusal states the true precondition rather than a channel that does not exist,
  and it gains a link the day the screen does.
- The profile section on Settings (blocked — no self-profile update operation exists).
- Clearing the refresh cookie from the browser. Deleting the account already destroys the
  sessions behind it, so the residual cookie authenticates nothing.
- Naming the organization in the leaving copy (no member-readable source for it).
- Any email or notification to the removed person.

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`
- Backend counterpart, already delivered: `specs/029-account-removal-api/`
