# PLAN — Email deliverability and domain alignment (DMI-108, rescoped)

**Issue:** [DMI-108](https://linear.app/dmitri-imt/issue/DMI-108) ·
**Branch:** `feature/dmi-108-invite-and-reset-emails-land-in-spam-html-part-and`

A plan, not a full spec. No new screen, no new data, no new API contract — this is one
backend module, one cookie attribute, and DNS. TRUTH / ARCHITECTURE / DESIGN would each
be a paragraph, so they are folded in here.

Refined with the operator on 2026-08-22. Decisions are recorded inline as **Decided:**.

## Goal

An invite sent from the deployed Users screen lands in a Gmail **inbox**.

## Why this is still DMI-108

The issue was opened to make invites and resets reach people. The configuration half
shipped on 2026-08-22 and mail now sends, authenticates and delivers — Resend reports
`last_event: delivered`. Gmail then files it as spam. An invite nobody sees fails the same
way an unsent invite does, so the reason for the issue is unchanged.

## Diagnosis

Both causes are confirmed, not suspected.

1. **Text-only mail.** `INVITE_BODY` / `RESET_BODY` in
   `backend/src/api/services/mailer.py` are plain strings and `_send` posts only a `text`
   field. A cold domain sending text-only mail is a strong filter signal.
2. **Sender/link domain mismatch.** Mail comes from `mail.peirce.dev`; links point at
   `nspi.up.railway.app`. Filters weigh linked-domain reputation, and an unrelated shared
   PaaS subdomain reads as a redirect.

Authentication is *not* a cause and needs no work: SPF, DKIM and DMARC all verify, and
`peirce.dev` is at `p=reject`.

## Approach

### A. HTML part (code)

Send `multipart/alternative`. Add an `html` sibling to each template and an `html` field to
the `_send` payload. Text stays, unchanged, as the fallback.

**Decided: bare semantic HTML.** Paragraphs and one anchor whose visible text *is* the full
URL. No colours, no container, no button, no images, no web fonts, no tracking pixel.
Marketing-looking HTML is itself a spam signal, and a visible URL is what a security-minded
recipient checks before clicking an invite. Copy is not rewritten — the HTML renders the
wording that already exists.

No HTML escaping is required on the link: tokens come from `secrets.token_urlsafe(32)`, so
they cannot contain `&`, `<`, `>` or `"`, and `app_base_url` is operator config rather than
user input. Stated here so a reviewer does not read its absence as an injection hole.

### B. Both services onto `peirce.dev` (infrastructure + one code change)

**Decided: move the API too, not just the frontend.**

| Service | From | To |
|---|---|---|
| `frontend` | `nspi.up.railway.app` | `dmitri.peirce.dev` |
| `api` | `api-nspi.up.railway.app` | `api.peirce.dev` |

Moving only the frontend would fix the email problem while locking in an open contradiction
with ADR-005. `up.railway.app` is on the Public Suffix List, so `nspi.` and `api-nspi.` are
today separate registrable domains and the refresh call is already cross-site — which is why
`f2836ba` (2026-08-18) moved the refresh cookie from `SameSite=Lax` to `None`.
`.claude/docs/backend/auth.md:81` records that as a deliberate deviation from ADR-005
§cookie flags.

With both services under `peirce.dev` they are same-site, `SameSite=Lax` becomes correct
again, and the deviation closes. This is the cheap moment to do it: later means a second DNS
change, a second CORS change and a second `APP_BASE_URL` change.

The operator accepted the widened scope — this issue now touches the security model, not
only email.

## Consequences to accept, not to fix

These follow from the decision above. None is a defect.

* **`nspi.up.railway.app` stops being usable for authenticated sessions.** Once the cookie
  is `Lax`, the old frontend domain is cross-site to `api.peirce.dev` and the refresh cookie
  is not sent. The old domain still serves pages; users cannot stay signed in on it. Keeping
  the old domain fully working and setting `SameSite=Lax` are mutually exclusive.

  **Operator confirmed 2026-08-22: nobody uses that URL.** So this costs nothing today. It
  is recorded because the old invite emails already sent carry links to it, and because a
  future reader finding a dead domain deserves to know it was deliberate.
* **Everyone is signed out once.** The existing cookie was set by `api-nspi.up.railway.app`
  and is never sent to `api.peirce.dev`. One admin account today, so this is a non-event —
  but it is not zero.
* **The frontend must be rebuilt.** `instances.ts:3` reads `VITE_API_URL`, which Vite inlines
  at *build* time. Changing the API domain requires a new build, not just a variable change.

## Ordering — this is the fragile part

The steps are not independent and a wrong order breaks production.

```
1. Add both custom domains (CNAME + TXT each), wait for ACTIVE + certificate
2. CORS: add https://dmitri.peirce.dev            ← before any link points there
3. VITE_API_URL = https://api.peirce.dev, rebuild frontend
4. APP_BASE_URL = https://dmitri.peirce.dev
5. Cookie SameSite=Lax                            ← last; invalidates the old domain
```

Step 2 before step 4, or real emails carry links to a domain whose every API call is
rejected. Step 5 last, because it is the step that makes the old domain unusable — do it
only once the new one is proven.

### Branch base

This branch is cut from `origin/main` at `30b6d29`. The CORS hardening
(`c640dc4`, "fail closed when CORS_ALLOWED_ORIGINS is unset") lives on `feat/dmi-107` and
is **not** on `main`, so it is absent here.

That is not a blocker: production sets `CORS_ALLOWED_ORIGINS` explicitly, so the default
never applies and step 2 below behaves identically either way. It also cannot conflict —
that commit touches `core/config.py`, which no task here goes near. Noted only so nobody
reads the permissive default in this branch and thinks it is the deployed behaviour.

**Railway requires both a CNAME and a TXT record per custom domain.** With the TXT missing,
the domain returns **404 even after the CNAME resolves** — it looks like propagation delay
and is not. Plan limits are Trial 1 / Hobby 2 / Pro 20 custom domains per service; each
service has zero today, since a Railway-provided domain is a different category.

## Out of scope

Dedicated IP; `List-Unsubscribe`; Google Postmaster Tools; retry/queue/bounce handling; copy
rewrite; DMARC policy change; the `_send` observability gap. Each is argued in the issue's
NOT-expected list.

## Definition of done

**Decided: structural criteria gate the merge; inbox placement is reported, not gated.**

Ship on what is verifiable — multipart present, links on `dmitri.peirce.dev`, CORS intact,
cookie `Lax` and sessions surviving refresh, suite green. Inbox placement is observed and
written into the issue as an outcome.

Spam placement is partly sender reputation, earned by mail people open, and the domain has
sent single-digit messages. These changes remove the structural causes; the remainder is
volume over weeks and no PR closes it. If mail still lands in spam with both fixes shipped,
that is a new issue about reputation — with the structural causes already ruled out.
