# DMI-110 — Settings screen research

**Status:** research output, 2026-09-06. **Phase 1 only — no code, no screen spec.**

**Inputs (read, not reopened):**
[`DESIGN-SYSTEM-RESEARCH.md`](DESIGN-SYSTEM-RESEARCH.md) (DMI-131, shipped as DMI-132/PR #133) ·
[`FOUNDATIONS.md`](FOUNDATIONS.md) + [`FOUNDATIONS-DECISIONS.md`](FOUNDATIONS-DECISIONS.md) ·
[`REFERENCE.md`](REFERENCE.md) · [`SCREENS.md`](SCREENS.md) §SETTINGS ·
[`ADR-016`](../adr/ADR-016-password-policy.md) · [`ADR-017`](../adr/ADR-017-account-removal.md) ·
current code (`frontend/src/pages/Settings.tsx`, `frontend/src/pages/settings/*`,
`frontend/src/components/{ConfirmByTyping,DialogShell,Disclosure,PageHeader}.tsx`,
`frontend/src/test/settingsHarness.tsx`).

**Settled before this note and not reopened here:** identity is read-only (no editable field, no
display name — open question C3 stays closed); password change is a modal; leave-organization is
last for both roles; the scan target network lives on the box detail screen. **What this note
decides:** arrangement, hierarchy, grouping, density.

**Next: human approval gate, then SCREENS.md §SETTINGS amendment, then code.**

**A note on source reach.** Apple's HIG and Material 3 are now JavaScript-only pages and returned
no body text to any fetch attempt (200 with "This page requires JavaScript"; the
`tutorials/data/...json` path 404s). Fluent 2's component pages 404 outside Microsoft sign-in. No
claim below rests on them. Microsoft's primary guidance is cited from `learn.microsoft.com`, which
is reachable and first-party. Every other claim is followed back to the source that owns it.

---

## 1. What a settings screen must carry

**F1 — A settings area is for the rarely changed; everything task-specific belongs on the screen
it affects.** This is the general rule behind the already-settled "scan target network is not
here" decision, and it is why this screen stays small. *Apple states this in the HIG Settings
pattern, but the page could not be read first-hand (see above) — treat the Apple attribution as
**weak**.* The reachable, first-party version of the same idea is progressive disclosure: "Initially,
show users only a few of the most important options. Offer a larger set of specialized options upon
request." ([NN/g, *Progressive Disclosure*, Jakob Nielsen, 2006-12-03](https://www.nngroup.com/articles/progressive-disclosure/))

**F2 — Grouping into labelled sections is the primary structural device, and headings are load-
bearing.** "At the form level, grouping related fields into sections makes long forms feel more
manageable because it: Allows users to focus on one information category at a time / Minimizes
context switching between unrelated topics"; and "adding clear, descriptive headings to each
section provides users with a helpful preview of the upcoming topic."
([NN/g, *Few Guesses, More Success: 4 Principles to Reduce Cognitive Load in Forms*, 2025-07-18](https://www.nngroup.com/articles/4-principles-reduce-cognitive-load/))

**F3 — A settings list may mix information rows and control rows, and the platform pattern for a
read-only fact is a named row type.** GNOME's boxed list — its preferences pattern — defines
**property rows** ("a property name and a value") alongside action, switch, combo and entry rows,
and says to "organize lists semantically… Multiple lists can be included in the same view, to act
as different sections. If necessary, each list can be given a heading." It also caps controls:
"Rows that include controls should generally just have one, and should have a maximum of two."
([GNOME HIG, *Boxed Lists*](https://developer.gnome.org/hig/patterns/containers/boxed-lists.html))

**F4 — A destructive account action is part of the screen's required content, not an omission to
be argued about.** GitHub ships it on the account settings page and documents its exact location:
"At the bottom of the Account Settings page, under 'Delete account', click **Delete your
account**." ([GitHub Docs, *Deleting your personal account*](https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-personal-account-on-github/managing-your-personal-account/deleting-your-personal-account))
This is the shipped-product confirmation of [`ADR-017`](../adr/ADR-017-account-removal.md) §2.

**F5 — Copy is short, neutral and sentence-shaped; headings take header capitalization, body and
field labels take sentence capitalization.** "User interface text should be short and to the
point… Try to find the fewest possible words to satisfactorily convey the necessary meaning."
Header capitalization for "headings… and short control labels"; sentence capitalization for "field
labels" and "explanatory or body text".
([GNOME HIG, *Writing Style*](https://developer.gnome.org/hig/guidelines/writing-style.html))
This agrees with [`FOUNDATIONS.md`](FOUNDATIONS.md) §Copy rules ("labels over paragraphs",
"explanatory copy under a control is deleted, not reworded") and with
[`REFERENCE.md`](REFERENCE.md) §6.

## 2. Structure and grouping — what mature products do

Read first-hand from each vendor's own documentation of its own product (none of these screens is
reachable without an account, so the vendor's own doc of that screen is the primary record):

| Product | Where identity sits | Password | Destructive account action | Grouping device |
| --- | --- | --- | --- | --- |
| **GitHub** | Separate `Account` page in a left sidebar of settings pages | Own page (`Password and authentication`) | **Bottom of the Account page**, own "Delete account" block, dialog requires typing username/email **and** a second typed phrase ([docs](https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-personal-account-on-github/managing-your-personal-account/deleting-your-personal-account)) | Sidebar of pages, one topic per page |
| **Google Account** | `Personal info` section; some facts editable, some not — "Some info can't be removed… you can edit, but not remove, your name and date of birth" ([help](https://support.google.com/accounts/answer/6304920)) | Nested two levels: `Security & sign-in` → "How you sign in to Google" → `Password`, with re-authentication ("You might need to sign in again") ([help](https://support.google.com/accounts/answer/41078)) | Under data/privacy, not on the identity page | Named top-level sections, each a page |
| **Notion** | `Settings → {your name}`, profile photo and preferred name at the top | Under `Account security` on the same personal page | `Settings → {your name} → Delete my account` — bottom of the same page ([help](https://www.notion.com/help/account-settings)) | One personal page, sub-headed groups |
| **Vercel** | Account `Settings`, reached from the avatar menu | `Authentication` section of account settings, listed in a left-hand list on the page ([docs](https://vercel.com/docs/accounts)) | Own section of account settings | List of sections down the left of one settings page |
| **Linear** | Account `Preferences`, grouped `General` / `Interface and theme` / `Automations and workflows` ([docs](https://linear.app/docs/account-preferences)) | Not on the preferences screen | Not on the preferences screen | Named groups down one scrolling page |
| **Stripe** | Account `Settings` index of tiles: Profile, Branding, Statement descriptors, Custom email domain, Single sign-on ([docs nav](https://docs.stripe.com/get-started/account/email-domain)) | Under user/security settings, off the business settings index | Off this surface | Index of named destinations |

**F6 — Two shapes exist, and the choice follows screen size, not taste.** Products with many
settings split them into a *list of destinations* (GitHub, Vercel, Stripe, Google). Products with
few settings put *named groups down one page* (Notion, Linear). Dmitri has three things on this
screen; the one-page grouped shape is the only one the content supports, and it is what ships
today.

**F7 — Identity is displayed at the top of the personal settings surface in every product read.**
Notion opens on the profile block; Google's `Personal info` is the first left-nav item; GitHub's
`Account` page opens on the username. This is the shipped-product agreement with
[`SCREENS.md`](SCREENS.md) §SETTINGS's epicenter — "*Who am I* comes before *change my password*,
always".

**F8 — Password change is consistently a separate, focused surface, never a set of fields on the
settings landing page.** Google nests it two levels deep behind a re-auth; GitHub gives it its own
page; Notion puts it behind `Account security`. No product read shows three password fields
sitting on the account page. This is external confirmation of the settled modal decision, not a
reopening of it.

## 3. Ordering and hierarchy

**F9 — Boundaries beat spacing when several kinds of element sit on one page.** "The principle of
common region says that items within a boundary are perceived as a group and assumed to share some
common characteristic or functionality"; a boundary "is a powerful tool to use when needing to
contain several different types of UI elements, or when adjusting the amount of whitespace between
objects isn't possible."
([NN/g, *The Principle of Common Region*, Aurora Harley, 2020-07-12](https://www.nngroup.com/articles/common-region/))
A settings screen is exactly that case: read-only facts, a disclosure, and a destructive trigger
on one page.

**F10 — Section headings are the reading order.** F2 above. A section whose title is not a heading
element is invisible to the heading-navigation that assistive-technology users rely on — see §9
for the live defect this creates in the current screen.

**F11 — The destructive action goes last, on its own.** GitHub documents it "at the bottom" (F4);
Notion places it last in the personal page. [`SCREENS.md`](SCREENS.md) §SETTINGS already states
the reason: "it is not what anyone came here to do."

## 4. Density

**F12 — Space groups; less inside a group than between groups.** [`FOUNDATIONS.md`](FOUNDATIONS.md)
§Spacing already fixes this ("Related elements sit closer than unrelated ones"; at most three
vertical steps per screen; the inter-section step is chosen once from `6`, `8` or `12`). The
research adds only *which* step: step `8` is defined in that table as "between cards in a list",
which is precisely the shape §9 recommends. Step `12` is reserved there for "sections of a
table-led screen" and for Home; Settings is neither.

**F13 — Label/value pairs read as a property row: name muted, value in ink, on one line.** GNOME's
property row (F3) is the platform name for it. [`FOUNDATIONS.md`](FOUNDATIONS.md) §Type gives both
sides `text-body-md`, and §Color gives `--ink-muted` to secondary text — the differentiation is
colour, not size, which is also GNOME's rule: "If a list row includes multiple text elements,
differentiate them using text size, weight and color." The current `AccountDetails` `<dl>` already
does this correctly and should not change.

**F14 — Controls stay generous.** [`FOUNDATIONS.md`](FOUNDATIONS.md) §Cards & sections: "Controls
are generous by default; density is zoned into tables, not applied app-wide." Settings has no
table, so nothing on it is dense.

## 5. Read-only identity display

**F15 — Read-only is signalled by the *absence of control chrome*, not by a disabled control.** A
property row (F3) has no input outline, no caret, no button; a row that can be acted on has one.
The signal is the contrast between the two row types on the same screen. This is also what
[`FOUNDATIONS.md`](FOUNDATIONS.md) §Interaction states already requires: "Disabled… **Only for
progress or not-yet-supplied input**", and "An affordance a role cannot use is not rendered."

**F16 — A disabled input would additionally fail the reason the screen exists.**
[`SCREENS.md`](SCREENS.md) §SETTINGS: "an input the user can type into but not submit is worse than
text." The `<dl>`/`<dt>`/`<dd>` markup already shipped states the same thing semantically — a
description list is data, not a form.

**F17 — Products do label the un-editable rather than hiding it.** Google's help text is explicit
that some fields are display-only: "Some info can't be removed from your Google Account. For
example, you can edit, but not remove, your name and date of birth."
([Google Account Help](https://support.google.com/accounts/answer/6304920)) Dmitri needs no such
sentence, because it shows no input at all — but it confirms that showing an identity fact you
cannot change is normal, not a gap.

## 6. Destructive actions

**F18 — WCAG 3.3.4 Error Prevention (Legal, Financial, Data), Level AA, applies to this screen.**
It covers pages "that modify or delete user-controllable data in data storage systems", and is met
by at least one of **Reversible / Checked / Confirmed**. Account deletion is irreversible
([ADR-017](../adr/ADR-017-account-removal.md) §1 — hard delete), so **Confirmed** is the only
route: "A mechanism is available for reviewing, confirming, and correcting information before
finalizing the submission."
([W3C, *Understanding SC 3.3.4*](https://www.w3.org/WAI/WCAG22/Understanding/error-prevention-legal-financial-data.html))
**3.3.6 Error Prevention (All)** is the Level AAA generalisation to every form that submits
information, met by the same techniques
([W3C, *Understanding SC 3.3.6*](https://www.w3.org/WAI/WCAG22/Understanding/error-prevention-all.html)).
Dmitri's typed-confirmation dialog satisfies both for the delete path.

**F19 — Where undo is impossible, a confirmation dialog is the correct fallback.** "Destructive
actions should always be accompanied by either a confirmation dialog or an offer to undo the
action… However, in cases where it is not possible to offer an undo feature, a confirmation dialog
is still recommended, to alert the user to the risk, to clarify which action will be taken, and to
give them the opportunity to cancel."
([GNOME HIG, *Dialogs*](https://developer.gnome.org/hig/patterns/feedback/dialogs.html))
Undo is not available here — the row and its sessions are gone.

**F20 — The typed confirmation is the documented pattern for the most dangerous actions.** NN/g,
guideline 7 of 8: "For particularly dangerous operations, require a nonstandard action from the
user to confirm… For example, type a word into a box, as MailChimp requires before deleting a
mailing list… Such nonstandard response options have to be reserved for the most dangerous and
rare actions."
([NN/g, *Confirmation Dialogs Can Prevent User Errors — If Not Overused*, Jakob Nielsen, 2018-02-18](https://www.nngroup.com/articles/confirmation-dialog/))
[`ADR-017`](../adr/ADR-017-account-removal.md) §5 is this guideline, with the target's email as the
typed value. **Reserved-for-the-rarest is a constraint on the rest of the screen**: nothing else in
Settings may borrow the pattern.

**F21 — Confirm-button labels summarize the outcome; there is no default affirmative.** NN/g:
"Instead of Yes/No answers, provide response options that summarize what will happen for each
possible response… **Avoid giving confirmation dialogs a default Yes answer.**" (same article).
Dmitri's "Delete my account" / "Cancel" pair complies, and matches
[`FOUNDATIONS.md`](FOUNDATIONS.md) §Copy rules ("Buttons: verb + noun. Never `Confirm`, `OK`, or a
bare verb").

**F22 — A dialog whose required input is not yet supplied may present an insensitive affirmative
button.** "Sometimes, the user may be required to choose options before an action can be carried
out. In these cases, the affirmative dialog button should be insensitive until the required options
have been selected."
([GNOME HIG, *Dialogs*](https://developer.gnome.org/hig/patterns/feedback/dialogs.html))
This is independent platform support for [`ADR-017`](../adr/ADR-017-account-removal.md) §5's 2026-08-17
amendment (a real, `disabled` button until the typed value matches) and for the carve-out in
[`FOUNDATIONS.md`](FOUNDATIONS.md) §Interaction states. It does **not** dissolve the accessibility
cost that ADR-017 §5 records and the operator accepted — GNOME's guidance predates it and does not
address screen-reader parity.

**F23 — Button order: cancel first.** "Always ensure that the cancel button appears first, before
the affirmative button. In left-to-right locales, this is on the left."
([GNOME HIG, *Dialogs*](https://developer.gnome.org/hig/patterns/feedback/dialogs.html))
**Conflict, recorded:** Microsoft's Windows guidance is the reverse — "The 'do it' action button(s)
should appear as the leftmost buttons. The safe, nondestructive action should appear as the
rightmost button."
([Microsoft, *Dialogs*](https://learn.microsoft.com/en-us/windows/apps/design/controls/dialogs-and-flyouts/dialogs))
Dmitri already ships GNOME's order in `ConfirmByTyping` and `PasswordDialog` (Cancel, then the
action, right-aligned), and the Users screen shares the same component. Consistency inside the
product decides it: **keep cancel-first**; do not adopt the Windows order for one screen.

**F24 — Destructive does not mean red here, and cannot.** [`FOUNDATIONS.md`](FOUNDATIONS.md)
§Color ships one accent and no severity hue; `local/no-raw-hex` forbids inventing one and the
issue forbids a foundation change. The outlined button already used for `Delete my account` is the
only compliant treatment. Its weight — outline, not filled — is itself the de-emphasis F11 asks
for.

## 7. Modal vs inline for the password change

**F25 — A modal is the right control for a blocking, self-contained task, and the wrong one for
routine work.** Microsoft: "dialogs should be reserved for situations where you want the user to
drop everything to focus on a specific bit of information or answer a question", and lists "When
the user's security might be compromised" among the cases for a dialog
([Microsoft, *Dialogs and flyouts*](https://learn.microsoft.com/en-us/windows/apps/design/controls/dialogs-and-flyouts/)).
GNOME's counterweight: "Since action dialogs obscure the parent window and require a context switch
on the part of a user, inline controls or actions are often preferable"
([GNOME HIG, *Dialogs*](https://developer.gnome.org/hig/patterns/feedback/dialogs.html)). Both hold
here, and the settled decision is defensible on Microsoft's ground plus F8: a password change is
rare, blocking, and needs an entry-point label rather than three fields camped on the page.

**F26 — APG modal-dialog requirements, all of them.** ([W3C, *Dialog (Modal) Pattern*, ARIA APG](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/))
Container has `role="dialog"` and `aria-modal="true"`; label via `aria-labelledby` pointing at a
visible title, or `aria-label`; Tab/Shift+Tab cycle inside the dialog; **Escape closes it**; on
open, "focus moves to an element contained in the dialog… Generally, focus is initially set on the
first focusable element", with judgement about which; on close, "focus returns to the element that
invoked the dialog"; and "the tab sequence of all dialogs include a visible element with role
button that closes the dialog, such as a close icon or cancel button." GNOME says the same about
initial focus: "provide initial keyboard focus to the component that you expect users to operate
first. This focus is especially important for users who must use a keyboard to navigate."

**F27 — Dmitri already satisfies F26, deliberately.** `DialogShell` sets `showCloseButton={false}`
and relies on the visible Cancel button (APG's stated alternative); it captures the opener itself
and restores focus on close, because every call site opens from state rather than a
`Dialog.Trigger`; `PasswordDialog` passes `initialFocusRef` so focus lands on **Current password**,
the field the user operates first. `locked` blocks Escape and overlay dismissal only while a
request is in flight. **Nothing in §9 changes any of this.**

**F28 — Validation errors stay inline in the dialog, never in a second dialog or a toast.** "Don't
use dialogs for errors that are contextual to a specific place on the page, such as validation
errors (in password fields, for example), use the app's canvas itself to show inline errors."
([Microsoft, *Dialogs*](https://learn.microsoft.com/en-us/windows/apps/design/controls/dialogs-and-flyouts/dialogs))
`PasswordDialog` already does this, with `role="alert"` per field and focus moved to the offending
field. [`SCREENS.md`](SCREENS.md) §SETTINGS states the same rule.

**F29 — The policy hint is stated up front, not discovered by failing.** NN/g's *Transparency*
principle — "Communicate requirements and set expectations upfront"
([NN/g, 4 Principles](https://www.nngroup.com/articles/4-principles-reduce-cognitive-load/)) — and
[`ADR-016`](../adr/ADR-016-password-policy.md)'s policy. The shipped `PASSWORD_HINT` under **New
password** is correct; it is the one place [`FOUNDATIONS.md`](FOUNDATIONS.md) §Copy rules'
"helper text on demand" yields, because the requirement is unguessable.

## 8. Recommendation for Dmitri

One scrolling page, `--container-frame`, no sidebar, no tabs. **Three groups, not four**, each a
white `Card` on the canvas, in this order:

| # | Group | Heading (`h2`, `text-title-sm`, inside the card) | Contents | From |
| --- | --- | --- | --- | --- |
| 1 | Identity + the action on it | **Your account** | Property rows `Email` / `Role`, then a `Password` row whose value slot holds the `Change password` button | F3, F7, F9, F13, F15 |
| 2 | What the org can see | **Activity** | `Disclosure` labelled "What's recorded?", note inside | F1, F2 |
| 3 | The way out | **Leave this organisation** | Body copy + outlined `Delete my account` trigger | F4, F11, F24 |

### 8.1 Section order and headings

- `PageHeader title="Settings"` unchanged — it already supplies the `h1` and the rule.
- **Merge the current `Your details` and `Password` sections into one card, "Your account"** (F2,
  F7, F9). Password acts on the identity shown two rows above it; a separate heading for a single
  button is a heading that carries no information. Inside the card, the password row is a
  property row *with a control* — GNOME's action row, one control, maximum two (F3). The contrast
  between rows with a control and rows without one is what marks Email and Role read-only (F15).
- **`Activity` second.** It is information about the identity above it and belongs next to it, and
  it is not an action.
- **`Leave this organisation` last, and alone in its card** (F11). Both roles see it
  ([ADR-017](../adr/ADR-017-account-removal.md) §2).
- Every group title is a real `<h2>` (F10). Sentence-cased body copy, header-cased headings and
  button labels (F5).

### 8.2 Density

| Decision | Value | Source |
| --- | --- | --- |
| Inter-section step (between cards) | **`gap-8` (32px)** — the scale's own "between cards in a list" | F12, [`FOUNDATIONS.md`](FOUNDATIONS.md) §Spacing |
| Inter-group step (inside a card: heading → rows, rows → button) | **`gap-4` (16px)** | F12 |
| Intra-group step (label ↔ value, row ↔ row) | **`gap-2` (8px)** | F12, F13 |
| Card padding | The `Card` primitive's own step `6` (24px) — untouched | [`FOUNDATIONS.md`](FOUNDATIONS.md) §Spacing |
| PageHeader → first card | **`gap-8`**, the same inter-section step (one step per screen) | F12 |
| Body copy measure | `max-w-prose` on the leave body and the activity note, as shipped | — |
| Label / value | `--ink-muted` label, `--ink` value, both `text-body-md`, one line, `break-words` on the email | F13 |

Three vertical steps total (2 / 4 / 8), which is the rhythm rule's ceiling. **This replaces the
current screen's `gap-12`**, twice nested.

### 8.3 Components — all existing, no new ones

| Part | Component | Change |
| --- | --- | --- |
| Title + rule | `PageHeader` | none |
| The three groups | `components/ui/card` (already used by `HostDetail`, `ScanDetail`) | new call site only |
| Email / Role / Password rows | `AccountDetails`'s `<dl>` | extend with the password row |
| Change password trigger | `Button` (default variant) | moves inside card 1 |
| Password form | `PasswordDialog` on `DialogShell` | none (F27) |
| Activity | `Disclosure` | none |
| Leave trigger | `Button variant="outline"` | none (F24) |
| Removal confirmation | `ConfirmByTyping` | none (F20–F23) |

`local/*` compliance: every value above is a scale step or a token — no arbitrary utility, no raw
hex, no raw type size, no `dark:` variant, and every interactive element is a shared primitive, so
`no-bare-interactive` holds.

### 8.4 States

- **Regular** — the three cards.
- **Loading** — `useSession` has no user yet. Today `AccountDetails` returns `null` and the leave
  section is gated on `user`, so the screen renders a title, an orphan `Password` heading and an
  `Activity` block: a half-page that looks finished. Recommend the whole content region render
  its three cards with the two property values as `LoadingSkeleton` lines, so the shape never
  changes under the reader.
- **Blank** — still deliberately not applicable ([`SCREENS.md`](SCREENS.md) §SETTINGS). A settings
  screen always has its own content.
- **Error (password)** — inline per field, in the dialog, focus moved to the field (F28).
- **Success (password)** — the existing `role="status"` line, which stays mounted and empty so the
  announcement fires on change. It now sits under the password row inside card 1.
- **Error (leave)** — inside `ConfirmByTyping`, `role="alert"` and focused, including the
  `409 last_admin` refusal. Unchanged.
- **Removed** — not a state of this screen; the SPA redirects to LOGIN
  ([ADR-017](../adr/ADR-017-account-removal.md) §6).

### 8.5 Where the research conflicts with the current screen

1. **Four equal `h2`s for three ideas.** Merge `Your details` + `Password` into **Your account**
   (F2, F9). *Changes `Settings.tsx` and `AccountDetails.tsx`.*
2. **`Leave this organisation` is a `<span className="text-title-sm">`, not an `<h2>`.** A section
   title that is not a heading is missing from heading navigation, and it is the one section a
   screen-reader user most needs to find deliberately. Make it an `<h2>` (F10). *Accessibility
   defect, not a taste change.*
3. **`gap-12` everywhere, and nested twice.** 48px is the scale's table-screen/Home step;
   Settings takes `gap-8` and the redundant inner wrapper `div` goes (F12).
4. **No containers.** Four bare stacked sections rely on whitespace alone to group; common region
   is the stronger cue when element kinds differ (F9). Move to three `Card`s — the treatment
   [`FOUNDATIONS.md`](FOUNDATIONS.md) §Cards & sections already assigns to a grouped section.
5. **The password trigger has no label of its own once its heading is gone.** It gains the row
   label `Password`, which is the property-row shape and reads better than a heading anyway (F3).
6. **Loading renders a partial screen** (see §8.4).

Not changed, and deliberately: `PasswordDialog`, `DialogShell`, `Disclosure`, `ConfirmByTyping`,
all copy in [`SCREENS.md`](SCREENS.md) §SETTINGS's copy table except the two heading strings the
merge retires, every route and every contract.

## 9. Owner decisions

Owner review, **2026-09-06**, in two passes. **All four open questions are closed** and §8 is
overturned on two points (grouping count, and card chrome). The review also settled the screen's
growth path (§10) and added the reveal toggle to the issue's scope.

**D1 — One page now, grow later.** The single scrolling page of §8 is approved as the shape to
build. Settings is expected to grow (§10); the restructure into a two-level screen is deferred
until a second populated section actually exists, not built speculatively now.

**D2 — Activity is demoted, not a peer section.** It is a privacy note, not a setting: it carries
no control and no state, and it does not belong at the same level as Password and Leave. It moves
**inside the "Your account" section** as a small disclosure — *"What's recorded about me?"* — and
loses its own `h2`. **This reduces §8's three groups to two** (Your account · Leave this
organisation). §8's table and §8.1 are superseded on this point; the SCREENS.md amendment carries
the two-section shape. Its long-term home is the org activity log, when that screen exists (§10).

**D3 — Heading string is "Your account".** Carried by the approved sketch.

**D4 — A reveal ("show password") toggle ships in this issue.** Owner decision, 2026-09-06: typing
a password you cannot see, twice, is the screen's worst moment. Scope and constraints are in §9.1.

**D5 — bare sections, not cards.** The two groups are separated by a hairline rule and `gap-8`,
not by `Card` containers. §8.1's card recommendation (F9) is overturned: Settings is mostly text,
and card chrome earns its place on HostDetail and ScanDetail because those carry dense data, not
here.

**D6 — the change-password button stands alone.** No `Password` label, no masked dots, no row of
its own: the button sits below the Email/Role list and carries its own meaning. **Reversed by the
owner later on 2026-09-06** — D6 first read "label + button, nothing between them", on the argument
that the row should keep the property rhythm of Email and Role. The owner's call went the other
way, and the reasoning is sound: changing a password is an *action*, and §8.1's own F3 (GNOME's
action row) is about a property that carries a control, not about a control with a label bolted on.
The parked `password_last_changed_at` field ([`IDEAS.md`](IDEAS.md) §Settings) would reopen this —
once there is a fact to show, `Password  <date>  [Change password]` becomes a real property row.

**D7 — the email stays on the screen** as well as in the top bar. It is the screen's subject, and
[`ADR-017`](../adr/ADR-017-account-removal.md)'s typed confirmation asks for that exact string;
making the reader copy it out of the chrome is worse than the duplication. Closes question 4 of the
original list.

**No open questions remain.** The direction is approved in full; the next step is the
[`SCREENS.md`](SCREENS.md) §SETTINGS and [`REFERENCE.md`](REFERENCE.md) amendment, then code.

### 9.1 The reveal toggle (D4)

**Why it is not a scope violation.** It touches `frontend/src/pages/settings/PasswordDialog.tsx`,
which DMI-110's **Expected** already names for rebuild. It adds no backend call, no contract change
and no dependency.

**What the constraints force.**

- `local/no-bare-interactive` allows interactive elements only in `components/ui/`, so the toggle
  cannot be an inline `<button>` in the dialog — it must be a primitive. That is also what makes
  applying it to the other five password fields nearly free.
- DMI-110 forbids a new icon set, so the eye is a hand-drawn **inline SVG**, following DMI-107's
  ruling on `Ornament`: inline SVG, never a Unicode glyph (`👁` renders in colour; the outline
  glyphs have poor font coverage).
- Chromium and Edge draw their own reveal control inside `input[type=password]`. Without
  `::-ms-reveal { display: none }` and `::-webkit-credentials-auto-fill-button` suppressed in
  `index.css`, the field shows two eyes.

**Behaviour.**

- A real `<button type="button">` — never inside the `<label>`, never a submit button, and in the
  tab order.
- The accessible name states the action and flips with state: *"Show password"* ↔ *"Hide password"*.
- Default is always hidden. State never persists — not across fields, not across dialog opens, not
  in storage. `PasswordDialog` resets it when `open` goes false.
- Each field toggles independently; there is no single control for the whole form.

**Scope — settled 2026-09-06.** There are eight password inputs in four screens: three here, and
five on `Login`, `ResetPassword` and `AcceptInvite`. **All eight get the toggle.** A reveal control
on Settings but not on Login reads as a bug, and the sharpest pain is on `ResetPassword` and
`AcceptInvite`, where a new password is typed blind and twice. DMI-110's **NOT expected** was
amended the same day with a narrow carve-out: those screens receive the toggle and nothing else
changes on them.

**Deliberately not built with it**, parked in [`IDEAS.md`](IDEAS.md) §Settings: a Caps Lock warning,
and dropping the "Confirm new password" field now that the value can be checked.

## 10. Growth path — what Settings does not yet carry

Recorded 2026-09-06 so the one-page decision (D1) is a deliberate choice rather than hidden debt.
**None of this is DMI-110 scope.** Every item is parked in [`IDEAS.md`](IDEAS.md) §Settings and
graduates through the create-issue gate. The list is here because it is the reason D1 needed
deciding at all.

The candidates, and what each would need, are in [`IDEAS.md`](IDEAS.md) §Settings: active sessions
and sign-out-everywhere, notification preferences, two-factor, organisation settings, organisation
deletion, password-last-changed, display name, and the email-change question.

**When the shape has to change.** The one-page form holds while Settings is about the account and
the way out of it. It stops holding when a second *populated* top-level section arrives — the first
of Notifications, Sessions or Organisation to be built. At that point Settings becomes a two-level
screen, and that restructure is its own issue, opened at that time. Nothing built for DMI-110 is
throwaway in the meantime: the sections, property rows, disclosure and dialogs all survive the move;
only the outer container changes.

## 11. Sources

All accessed **2026-09-06**.

**W3C / WAI**
- *Dialog (Modal) Pattern*, ARIA Authoring Practices Guide, W3C — https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
- *Disclosure (Show/Hide) Pattern*, ARIA APG, W3C — https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/
- *Understanding SC 3.3.4: Error Prevention (Legal, Financial, Data)*, WCAG 2.2, W3C — https://www.w3.org/WAI/WCAG22/Understanding/error-prevention-legal-financial-data.html
- *Understanding SC 3.3.6: Error Prevention (All)*, WCAG 2.2, W3C — https://www.w3.org/WAI/WCAG22/Understanding/error-prevention-all.html
- *Understanding SC 2.4.11: Focus Not Obscured (Minimum)*, WCAG 2.2, W3C — https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html — **note:** the brief names 2.4.11 as "focus appearance"; in WCAG 2.2, 2.4.11 is *Focus Not Obscured (Minimum)* (AA) and **Focus Appearance is 2.4.13** (AAA) — https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance.html . Neither is at risk on this screen: nothing is sticky, and the focus ring is `--ring` from [`FOUNDATIONS.md`](FOUNDATIONS.md).

**Platform design systems (vendor-authored)**
- *Boxed Lists*, GNOME Human Interface Guidelines, GNOME Project — https://developer.gnome.org/hig/patterns/containers/boxed-lists.html
- *Dialogs*, GNOME HIG, GNOME Project — https://developer.gnome.org/hig/patterns/feedback/dialogs.html
- *Writing Style*, GNOME HIG, GNOME Project — https://developer.gnome.org/hig/guidelines/writing-style.html
- *Dialogs and flyouts*, Windows app design, Microsoft Learn — https://learn.microsoft.com/en-us/windows/apps/design/controls/dialogs-and-flyouts/
- *Dialogs*, Windows app design, Microsoft Learn — https://learn.microsoft.com/en-us/windows/apps/design/controls/dialogs-and-flyouts/dialogs

**Nielsen Norman Group (original articles)**
- *Progressive Disclosure*, Jakob Nielsen, NN/g, 2006-12-03 — https://www.nngroup.com/articles/progressive-disclosure/
- *Confirmation Dialogs Can Prevent User Errors — If Not Overused*, Jakob Nielsen, NN/g, 2018-02-18 — https://www.nngroup.com/articles/confirmation-dialog/
- *The Principle of Common Region: Containers Create Groupings*, Aurora Harley, NN/g, 2020-07-12 — https://www.nngroup.com/articles/common-region/
- *Few Guesses, More Success: 4 Principles to Reduce Cognitive Load in Forms*, NN/g, 2025-07-18 — https://www.nngroup.com/articles/4-principles-reduce-cognitive-load/

**Shipped products (vendor documentation of their own screens)**
- *Deleting your personal account*, GitHub Docs — https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-personal-account-on-github/managing-your-personal-account/deleting-your-personal-account
- *Change or reset your password*, Google Account Help — https://support.google.com/accounts/answer/41078
- *Control what others see about you across Google services*, Google Account Help — https://support.google.com/accounts/answer/6304920
- *Account settings & preferences*, Notion Help Center — https://www.notion.com/help/account-settings
- *Account Management*, Vercel Docs — https://vercel.com/docs/accounts
- *Preferences*, Linear Docs — https://linear.app/docs/account-preferences
- *Custom email domain* (read for the account-settings navigation index), Stripe Docs — https://docs.stripe.com/get-started/account/email-domain

**Weak / could not be verified first-hand — marked, and no claim rests on them**
- Apple *Human Interface Guidelines — Settings* — https://developer.apple.com/design/human-interface-guidelines/settings — page returns 200 but renders only "This page requires JavaScript"; the documentation JSON endpoint 404s. Its guidance on rarely-changed options (F1) is attributed **weakly** and is independently carried by NN/g's *Progressive Disclosure*.
- Material Design 3 (*Lists*, *Dialogs*) — https://m3.material.io — JavaScript-only, no body text retrievable.
- Microsoft Fluent 2 component pages — https://fluent2.microsoft.design — 404 outside Microsoft sign-in. Microsoft Learn is used instead.

**Repo inputs (not external sources):** [`FOUNDATIONS.md`](FOUNDATIONS.md),
[`FOUNDATIONS-DECISIONS.md`](FOUNDATIONS-DECISIONS.md),
[`DESIGN-SYSTEM-RESEARCH.md`](DESIGN-SYSTEM-RESEARCH.md), [`REFERENCE.md`](REFERENCE.md),
[`SCREENS.md`](SCREENS.md) §SETTINGS, [`ADR-016`](../adr/ADR-016-password-policy.md),
[`ADR-017`](../adr/ADR-017-account-removal.md).
