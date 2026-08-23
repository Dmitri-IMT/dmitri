# Tasks — Email deliverability and domain alignment (`036-email-deliverability`)

4 tasks. **Unblocked now: #1, #2**

Source of truth is [PLAN.md](./PLAN.md), not a TRUTH/ARCHITECTURE/DESIGN set — this feature
adds no screen, no data and no contract.

## Batching

Deliberately few tasks: each one costs a coder plus a review cycle, so work is grouped to
the largest unit that still reviews cleanly. Tests live **inside** their code task rather
than in a task of their own — `backend/tests/test_mailer.py` already exists with a
`sent_emails` fixture (`conftest.py:229`) that runs a real `ResendMailer` behind a mock
transport, so the new coverage is a handful of assertions in an existing file, not a task.

Tasks 1 and 3 are independent and run in parallel. Task 2 cannot merge into task 1: it must
wait for the domains to be live.

## Agents and gate

Tasks 1 and 2 are Python. Spawn `agent-developer` + `test-engineer` + `code-reviewer`.

```
./database.sh --test          # or ./database.sh, then DATABASE_URL_TEST=… uv run pytest
cd backend && uv run ruff check src tests
```

**Never run `uv run ruff format`** — `backend/` is hand-formatted (CLAUDE.md §Formatting).
A non-zero skip count means the database was down; re-run rather than report green.

Task 3 is **ops**: it changes Railway and Cloudflare, produces no diff, and needs dashboard
access an agent does not have. Task 4 is human verification.

---

## Task 1: HTML part on both email templates
- **Description**: Send `multipart/alternative` per PLAN.md §A. Add `INVITE_BODY_HTML` and
  `RESET_BODY_HTML` beside the existing text constants in
  `backend/src/api/services/mailer.py`, add an `html` key to the `_send` payload, and give
  `_send` the parameter to carry it. The existing `text` field and both text constants stay
  exactly as they are — they become the fallback part, not a replacement.

  Bare semantic HTML: paragraphs and one anchor whose visible text is the full URL. No
  `<table>`, no `<img>`, no `<link>`, no inline colour, no tracking pixel. Copy is not
  rewritten.

  Also update `backend/.env.example` so the mail block documents `APP_BASE_URL` per
  environment — `http://localhost:5173` locally, `https://dmitri.peirce.dev` deployed.
  Comment only; no variable is added, removed or renamed.

  Tests belong to this task. Extend `backend/tests/test_mailer.py` using the existing
  `sent_emails` fixture. Do not re-cover what already passes there —
  `test_null_mailer_never_logs_the_token`, `test_resend_mailer_swallows_transport_failure`
  and `test_resend_mailer_swallows_provider_rejection` exist and must keep passing.
  `test_resend_mailer_posts_plain_text_invite` will need renaming, since it no longer
  describes what is sent.
- **Dependencies**: —
- **Target Files**: [`backend/src/api/services/mailer.py`, `backend/tests/test_mailer.py`,
  `backend/.env.example`]
- **Success Criteria**:
  - The posted payload carries **both** `text` and `html`, for invite and for reset, and the
    `text` value is byte-identical to today's.
  - Both parts carry the same link string, from a single `invite_link()` / `reset_link()`
    call per send — the URL is built once, not twice.
  - The HTML contains no `<img>`, no `<table>`, no `<link>`, and no external URL other than
    the invite/reset link.
  - A test asserts no emitted log record contains the raw token, on the success path, the
    `httpx.HTTPError` path and the `>=400` path.
  - `NullMailer` and `get_mailer` selection are unchanged.
  - Gate passes with a **zero** skip count.

## Task 2: Refresh cookie back to `SameSite=Lax`
- **Description**: Per PLAN.md §B, once both services share `peirce.dev` they are same-site
  and the cookie can return to `Lax`, closing the deviation from ADR-005 §cookie flags.
  Change `samesite="none"` to `"lax"` in both `set_refresh_cookie` and
  `clear_refresh_cookie` in `backend/src/api/session_response.py`, and rewrite the comment
  at `session_response.py:13` — it currently explains the cross-site situation that this
  change ends.

  Update the record too: `.claude/docs/backend/auth.md:81` and `:123` describe the deviation
  as live, and `docs/adr/ADR-005-security-model.md` carries it in both its summary and its
  body. The deviation is closing, so both must say so.

  **This task is why the old domain stops working for signed-in users** — PLAN.md
  §Consequences. Accepted, not a defect: the operator confirmed on 2026-08-22 that nobody
  uses `nspi.up.railway.app`.
- **Dependencies**: Task 3 (both domains must be live and proven first)
- **Target Files**: [`backend/src/api/session_response.py`,
  `docs/adr/ADR-005-security-model.md`, `.claude/docs/backend/auth.md`]
- **Success Criteria**:
  - Both cookie calls use `samesite="lax"`; no other cookie attribute changes.
  - The comment at `session_response.py:13` describes the same-site reality, not the old one.
  - ADR-005 no longer lists this as an open deviation, in summary and body alike.
  - Logging in at `https://dmitri.peirce.dev`, then hard-reloading, keeps the session — proof
    the cookie is sent on the refresh call.
  - Gate passes with a **zero** skip count.

## Task 3: Both services onto `peirce.dev` — OPS
- **Description**: PLAN.md §B and §Ordering, **in this exact order**:

  1. Add `dmitri.peirce.dev` to `frontend` and `api.peirce.dev` to `api`, both in `nspi`.
     Each needs **a CNAME and a TXT record** in Cloudflare — with the TXT missing the domain
     404s even after the CNAME resolves. Wait for ACTIVE with a certificate.
  2. Add `https://dmitri.peirce.dev` to `CORS_ALLOWED_ORIGINS` on `api`, keeping every
     existing origin.
  3. Set `VITE_API_URL=https://api.peirce.dev` on `frontend` and **redeploy it** — Vite
     inlines that value at build time, so a variable change alone does nothing.
  4. Set `APP_BASE_URL=https://dmitri.peirce.dev` on `api`. `backend/.env` keeps
     `http://localhost:5173`.

  Step 2 must precede step 4, or live emails carry links to a domain whose API calls are all
  rejected.
- **Dependencies**: — (needs Railway and Cloudflare dashboard access)
- **Target Files**: none — infrastructure only
- **Success Criteria**:
  - Both domains serve over a valid certificate and read ACTIVE in Railway.
  - `CORS_ALLOWED_ORIGINS` contains the new frontend origin **and** everything it contained
    before.
  - `VITE_API_URL` is the new API domain **and** the frontend has been rebuilt since.
  - `APP_BASE_URL` is `https://dmitri.peirce.dev`; deploy SUCCESS; no
    `RESEND_API_KEY is not set` in the logs.
  - Logging in at `https://dmitri.peirce.dev` works end to end — proof CORS and
    `VITE_API_URL` both landed.

## Task 4: End-to-end verification — OPS, gates the feature
- **Description**: Run the issue's test cases against production. Per PLAN.md §Definition of
  done, the structural criteria gate; inbox placement is recorded as an outcome and does not
  block. Needs a real Gmail account and a human reading which folder the mail landed in.
- **Dependencies**: Tasks 1, 2, 3
- **Target Files**: none
- **Success Criteria** (structural — these gate):
  - Raw source shows `multipart/alternative` with a `text/plain` and a `text/html` part.
  - The invite link reads `https://dmitri.peirce.dev/invite?token=…` and completes signup.
  - Password reset behaves the same at `https://dmitri.peirce.dev/reset-password?token=…`.
  - With HTML disabled, the text fallback is readable and the link usable.
  - A reset for an unknown address returns a response byte-for-byte identical to the
    known-address case, and Resend records no send.
  - Production logs contain no `rejected by provider with status`.
- **Reported, not gated**:
  - Which folder the invite landed in. If still spam, open a reputation issue and note that
    both structural causes are ruled out.

---

## Dependency graph

```
Task 1 ─────────────────────────┐
                                ├──> Task 4
Task 3 ──> Task 2 ──────────────┘
```

Tasks 1 and 3 start now and run in parallel. Task 2 waits on the domains being live.

## Status

| # | Task | Layer | Depends on | Status |
|---|---|---|---|---|
| 1 | HTML part + tests + `.env.example` | backend | — | COMPLETED |
| 2 | Refresh cookie back to `SameSite=Lax` | backend + docs | 3 | COMPLETED (code); hard-reload check pending deploy |
| 3 | Both services onto `peirce.dev` | ops | — | COMPLETED |
| 4 | End-to-end verification | ops | 1, 2, 3 | Not started |

## Review Rejections

| Task | Count | Rejection |
|---|---|---|
| 2 | 1 | 2026-08-23 — `docs/adr/ADR-005-security-model.md:146-147` still offered the same-domain move as an open alternative for closing the deviation, contradicting the criterion "no longer lists this as an open deviation, in summary and body alike". Gate itself was green (964 passed, 0 skipped, ruff clean). |
