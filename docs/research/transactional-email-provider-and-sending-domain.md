# Research: transactional email provider and sending-domain setup

> **Scope.** Dmitri backend (Python 3.11+, FastAPI, SQLModel/Postgres), Linear
> issue DMI-71 "Send transactional email (invites + password reset)". A `Mailer`
> Protocol seam already exists at `backend/src/api/services/mailer.py` with
> `send_invite_link(email, token)` / `send_reset_link(email, token)`; the only
> implementation today is `LogMailer`, which logs raw tokens. This note picks the
> provider that replaces it and specifies the DNS work needed to send.
>
> Constraints taken as given from the issue:
> - **No new Python dependency.** `httpx` is already in `backend/pyproject.toml`,
>   so the provider must be driven over its plain HTTP API — no vendor SDK.
> - Plain-text email only, two templates (invite link, password-reset link).
> - Failure to send must be logged and must **not** 500 the invite request.
> - Low volume: invites + resets for a B2B security-appliance product.
>
> Primary sources only: `resend.com/docs` and `resend.com/pricing`;
> `postmarkapp.com/developer` and `postmarkapp.com/pricing`;
> `docs.aws.amazon.com/ses`; and the IETF RFCs that own the mechanisms —
> RFC 7208 (SPF), RFC 7489 (DMARC). **Fetched 2026-08-02.**
>
> **Pricing and free-tier numbers below are date-sensitive** — every provider
> here changes plan shapes without notice. Re-check the linked pricing page
> before committing; treat the figures as "as of 2026-08-02" only.

---

## TL;DR verdict

- **All three can send a plain-text email over HTTP, but only two can do it with
  `httpx` alone.** Resend and Postmark authenticate with a single static header.
  **Amazon SES requires AWS Signature Version 4** on every request — a canonical
  request, a scoped string-to-sign, a four-stage HMAC-SHA256 derived key, and a
  composed `Authorization` header
  (https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv4-signing-process.html).
  That is implementable with stdlib `hmac`/`hashlib`, but it is ~60–80 lines of
  security-critical code we would own and test ourselves, versus one header.
  Under a no-SDK constraint, SES is the *expensive* option, not the cheap one.
- **SES additionally has real approval friction.** New accounts are sandboxed
  *per AWS Region*: send only to verified addresses, 200 messages / 24h, 1
  msg/sec. Production access is a reviewed request; AWS states an initial support
  response "within 24 hours" and that they grant within that window "if we're
  able to," longer if they need more information
  (https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html).
- **Postmark is the strongest deliverability story for one-time links
  specifically**, because it enforces the transactional/bulk split
  architecturally: transactional and broadcast traffic "do not mix… including IP
  ranges" (https://postmarkapp.com/message-streams). Password-reset and invite
  mail never shares reputation with anyone's newsletter.
- **Cost is a non-issue at our volume for all three**, but the free tiers differ
  by 30×: Resend 3,000/month (100/day), Postmark **100/month**, SES has no
  general free tier for API sending in the sandbox sense — see Findings §1.

### Recommendation for this project: **Resend**

Judged against the four constraints that actually bind:

1. **No-SDK / httpx-only** — `POST https://api.resend.com/emails` with
   `Authorization: Bearer re_…` and a three-field JSON body. Nothing to
   implement beyond one `httpx.post`. Postmark ties on this; SES loses badly.
2. **Low volume** — 3,000 emails/month free covers invites + resets for a B2B
   appliance product with room to spare, and the paid step-up is $20/mo for
   50,000. Postmark's free tier is 100/month, which a single onboarding week
   could exhaust, pushing us to $15/mo immediately for volume we do not need.
3. **One-time-link deliverability** — Resend requires a verified domain with
   SPF + DKIM + a bounce MX before you can send at all, which is the property
   that actually drives inbox placement for reset links. Postmark's stream
   separation is *better*, but Resend is not a bulk-mail platform either, and we
   will be its only tenant on our own DKIM'd domain.
4. **Setup friction** — domain verification only, no human review gate. SES's
   production-access request is a hard blocker on shipping DMI-71 in one pass.

**What would change the answer:**
- **If deliverability of reset links ever becomes a support issue** — bounce to
  **Postmark**. Its transactional/broadcast IP separation and its narrower
  product focus are a genuinely stronger position, and $15/mo is noise. The
  `Mailer` Protocol makes this a one-class swap.
- **If we ever need EU data residency for email metadata** — neither Resend nor
  (unverified) Postmark clears it cleanly; Resend explicitly says region
  selection "does not control where customer data is stored" and account data
  stays in the US (https://resend.com/docs/dashboard/domains/regions). SES in
  `eu-west-1` becomes the answer, and the SigV4 cost gets paid.
- **If we adopt an AWS-native deployment with IAM roles anyway**, the SigV4
  objection weakens (though it is still hand-rolled without botocore).

### Recommended sending-domain shape: **a subdomain, not the apex**

Send from something like `no-reply@mail.dmitri.example` (or `send.` /
`notifications.`), not `@dmitri.example`. Reasons, all primary-sourced:

- Resend explicitly "advises sending emails from subdomains… instead of root
  domains" to isolate sending reputation
  (https://resend.com/docs/dashboard/domains/introduction).
- Postmark recommends keeping streams "on separate streams and subdomains with
  custom DKIM + Return-Path" (https://postmarkapp.com/message-streams).
- It keeps the apex's SPF record untouched — critical given the **one-SPF-record
  per domain** rule and the **10-lookup limit** (RFC 7208 §3.2/4.5, §4.6.4; see
  Findings §4). If the apex already carries Google Workspace or similar, adding
  the provider's `include:` there is exactly how you blow the lookup budget.
- The org domain's DMARC at `_dmarc.dmitri.example` still covers the subdomain
  by inheritance unless an `sp` tag says otherwise (RFC 7489), so you get
  policy coverage without touching the apex's mail flow.

---

## Findings

### 1. Provider comparison

#### 1a. Pricing at low volume

**All figures fetched 2026-08-02 and subject to change without notice.**

| | Free tier | First paid tier | Per-1,000 overage |
|---|---|---|---|
| **Resend** | 3,000 emails/month, **100/day**, 1 domain | Pro: **$20/mo** for 50,000 | **$0.90** (Pro); $0.80–$0.65 at Scale |
| **Postmark** | **100 emails/month**, no overage allowed | Basic: **$15.00/mo** for 10,000 | **$1.80** (Basic); $1.30 (Pro); $1.20 (Platform) |
| **Amazon SES** | See note below | Pay-as-you-go | See note below |

Sources: https://resend.com/pricing, https://postmarkapp.com/pricing.

Resend also offers 10 domains on Pro (1 on free), 1,000 on Scale. Postmark's
paid tiers all start at the same 10,000/month baseline and differ by features and
overage rate.

> **SES pricing is unverified in this note.** I did not fetch
> https://aws.amazon.com/ses/pricing/ as a primary source, so I am not going to
> state a per-1,000 figure for SES. What *is* primary-sourced is that the SES
> sandbox caps you at 200 messages per 24-hour period regardless of price
> (https://docs.aws.amazon.com/ses/latest/dg/quotas.html), so cost is not the
> gating factor for SES at our volume — the approval process is.

At Dmitri's volume (invites + resets, low tens to low hundreds per month),
**Resend is free and Postmark is $0 until ~100/month then $15/mo**. Postmark's
free tier explicitly disallows overage, so exceeding 100 means an immediate plan
change rather than a small bill.

#### 1b. HTTP API shape for one plain-text email

**Resend** — https://resend.com/docs/api-reference/emails/send-email

- Method/URL: `POST https://api.resend.com/emails`
- Auth: `Authorization: Bearer re_xxxxxxxxx`
- Content type: `application/json`
- Required body: `from` (plain or `Name <addr>`), `to` (string or array, max 50),
  `subject`. `text` is optional in the schema but is what we set for plain-text
  (`html` is the alternative; `text` is auto-generated from `html` if omitted).
- Optional and relevant: `Idempotency-Key` **header**, unique per request, 24-hour
  expiration, max 256 chars.
- Success: **HTTP 200**, body `{"id": "<uuid>"}`.

```python
import httpx

resp = httpx.post(
    "https://api.resend.com/emails",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "from": "Dmitri <no-reply@mail.dmitri.example>",
        "to": [email],
        "subject": "Reset your Dmitri password",
        "text": f"Open this link to reset your password:\n\n{reset_url}\n",
    },
    timeout=10.0,
)
resp.raise_for_status()
message_id = resp.json()["id"]
```

Errors a caller must handle (https://resend.com/docs/api-reference/errors) —
each carries an error-code string alongside the HTTP status:

| Status | Codes | Caller action |
|---|---|---|
| 400 | `validation_error`, `invalid_idempotency_key` | Bug in our payload; log, do not retry |
| 401 | `missing_api_key`, `restricted_api_key` | Config/permission error; log loudly |
| 403 | `invalid_api_key`, `validation_error` | Key expired/rotated; log loudly |
| 409 | `invalid_idempotent_request`, `concurrent_idempotent_requests` | Only if we use idempotency keys |
| 422 | `invalid_from_address`, `missing_required_field`, `invalid_region`, … | Bug in our payload or unverified `from` |
| 429 | `rate_limit_exceeded`, `daily_quota_exceeded`, `monthly_quota_exceeded` | Back off / alert on quota |
| 451 | `security_error` | Content flagged; log |
| 500 | `application_error`, `internal_server_error` | Transient; safe to retry once |

> The Resend docs page listing error codes does **not** publish the JSON error
> body schema. Treat the response body shape as unverified — parse defensively
> and key your handling off the HTTP status, logging the raw body.

**Postmark** — https://postmarkapp.com/developer/api/email-api

- Method/URL: `POST https://api.postmarkapp.com/email`
- Auth: `X-Postmark-Server-Token: <server token>` (not a Bearer token)
- Headers: also `Content-Type: application/json`, `Accept: application/json`
- Required body: `From` (must have a confirmed Sender Signature), `To`,
  `Subject`, and at least one of `TextBody` / `HtmlBody`. Field names are
  **PascalCase**.
- Optional: `"MessageStream": "outbound"` — omitted, it defaults to the outbound
  transactional stream.
- Success: **HTTP 200** with
  `{"To":…, "SubmittedAt":…, "MessageID":…, "ErrorCode":0, "Message":"OK"}`.

```python
import httpx

resp = httpx.post(
    "https://api.postmarkapp.com/email",
    headers={
        "X-Postmark-Server-Token": server_token,
        "Accept": "application/json",
    },
    json={
        "From": "no-reply@mail.dmitri.example",
        "To": email,
        "Subject": "Reset your Dmitri password",
        "TextBody": f"Open this link to reset your password:\n\n{reset_url}\n",
        "MessageStream": "outbound",
    },
    timeout=10.0,
)
resp.raise_for_status()
body = resp.json()
if body["ErrorCode"] != 0:
    raise RuntimeError(body["Message"])
```

**The `ErrorCode` check is not optional.** Postmark returns "200-level http
status" even when an individual message fails, so a caller that only checks the
HTTP status will silently swallow failures. Error body shape
(https://postmarkapp.com/developer/api/overview) is
`{"ErrorCode": 405, "Message": "details"}`. Status codes: 200 success, 401
missing/incorrect token, 422 validation, 429 rate limit, 500 internal, 503
unavailable. Notable codes: `10` bad or missing API token, `300` invalid email
request, `402` invalid JSON, `405` account out of credits, `406` inactive
recipient (prior hard bounce or spam complaint), `410` batch over 500 messages.

`406 / ErrorCode 406` is worth calling out for our use case: a recipient
suppressed by an earlier hard bounce will *fail* a password-reset send, and that
is exactly the failure the issue says must be logged and must not 500 the request.

**Amazon SES v2** —
https://docs.aws.amazon.com/ses/latest/APIReference-V2/API_SendEmail.html

- Method/URL: `POST /v2/email/outbound-emails` on the regional SES endpoint
  (e.g. `https://email.eu-west-1.amazonaws.com/v2/email/outbound-emails`).
- Auth: **AWS Signature Version 4** — no static header exists.
- Body for a simple text message:

```json
{
  "FromEmailAddress": "no-reply@mail.dmitri.example",
  "Destination": { "ToAddresses": ["user@example.com"] },
  "Content": {
    "Simple": {
      "Subject": { "Charset": "UTF-8", "Data": "Reset your Dmitri password" },
      "Body": { "Text": { "Charset": "UTF-8", "Data": "…link…" } }
    }
  }
}
```

- Success: **HTTP 200**, `{"MessageId": "string"}`. Note the docs' own caveat:
  "It's possible for Amazon SES to accept a message without sending it."
- Errors: `BadRequestException` 400, `MessageRejected` 400,
  `MailFromDomainNotVerifiedException` 400, `AccountSuspendedException` 400,
  `SendingPausedException` 400, `LimitExceededException` 400,
  `NotFoundException` 404, `TooManyRequestsException` 429.

An `httpx` snippet for SES is not a snippet — it is a SigV4 implementation. The
signing process requires, per
https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv4-signing-process.html:
a canonical request (method, canonical URI, canonical query string, canonical
headers, signed headers, hex-encoded payload hash); a string-to-sign
(`AWS4-HMAC-SHA256\n<timestamp>\n<credential_scope>\n<hashed_canonical_request>`);
a derived key from four chained HMAC-SHA256 rounds over `AWS4`+secret, date,
region, service, `aws4_request`; and an `Authorization: AWS4-HMAC-SHA256
Credential=…, SignedHeaders=…, Signature=…` header. Every one of those steps is
a place to introduce a subtle bug that manifests as an opaque 403. Doable with
stdlib `hmac`/`hashlib`, but it is code we would own, test, and maintain in
exchange for nothing this project needs.

#### 1c. Suitability for one-time login and reset links

- **Postmark — strongest, and architecturally so.** Message Streams separate
  Transactional (one-to-one, user-action-triggered: "password resets, receipts,
  shipping updates") from Broadcast (one-to-many). Postmark states transactional
  and broadcast traffic "do not mix in Postmark, including IP ranges," following
  the reputation-separation practice recommended by inbox providers like Gmail,
  and that bulk streams sit "on completely different servers and IP pools"
  (https://postmarkapp.com/message-streams). The stated rationale is that bulk
  mail's much lower engagement rate drags inbox placement down when it shares IPs
  with transactional mail. For a password-reset link — where the whole product
  experience dies if the mail lands in spam — this is the property that matters.
- **Resend — good, no explicit stream separation documented.** Resend requires a
  verified domain before you can send at all: you must "add and verify at least
  one domain," and it "requires your own domain rather than shared
  infrastructure" (https://resend.com/docs/dashboard/domains/introduction). It
  recommends subdomain sending to isolate reputation. I found **no primary-source
  statement** in the fetched Resend docs establishing separate IP pools for
  transactional vs marketing traffic — Resend does sell a Marketing product
  alongside the transactional API, so treat stream separation as **unverified**.
- **Amazon SES — neutral infrastructure, reputation is entirely yours.** SES asks
  at production-access time whether the majority of your mail is Marketing or
  Transactional, and the acknowledgement requires confirming "you have a process
  in place for handling bounce and complaint notifications"
  (https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html). SES
  gives you no managed reputation help on shared IPs; dedicated IP pools exist
  (max 50 per account) but are overkill and counterproductive at our volume.

#### 1d. Sandbox / approval friction

- **Resend:** domain verification only. Statuses progress `not_started` →
  `pending` → `verified` / `partially_verified` / `failed`; a domain that does not
  verify **within 72 hours** flips to `failed`
  (https://resend.com/docs/dashboard/domains/introduction). No human review gate.
- **Postmark:** Sender Signature confirmation plus domain DNS verification;
  Postmark says to allow up to 48 hours for DNS propagation and verification per
  record type, with a manual **Verify** button to trigger a re-check
  (https://postmarkapp.com/support/article/1046-how-do-i-verify-a-domain). No
  primary-sourced human approval gate found for standard accounts.
- **Amazon SES — the notable one.** Every new account is in the sandbox, and
  **sandbox status is per AWS Region**. Sandbox restrictions
  (https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html):
  - send **only** to verified email addresses and domains, or the SES mailbox
    simulator;
  - max **200 messages per 24-hour period**;
  - max **1 message per second**;
  - account-level suppression bulk actions and suppression-list API calls
    disabled.

  To leave the sandbox you submit a reviewed request from the SES console
  (Account dashboard → **View Get set up page** → **Request production access**),
  choosing Marketing or Transactional, supplying a website URL, up to 4 contact
  emails, a preferred language (EN or JA), and checking an acknowledgement that
  you will only mail people who explicitly requested it and that you handle
  bounces and complaints. The same request is available via the CLI:

  ```
  aws sesv2 put-account-details \
  --production-access-enabled \
  --mail-type TRANSACTIONAL \
  --website-url https://example.com \
  --additional-contact-email-addresses info@example.com \
  --contact-language EN
  ```

  **Stated turnaround:** "The AWS Support team provides an initial response to
  your request within 24 hours… If we're able to do so, we'll grant your request
  within this 24-hour period. However, if we need to obtain additional
  information from you, it might take longer to resolve your request." You cannot
  edit your details while the review is open. AWS also notes that verifying your
  domain *before* requesting production access "helps to get your production
  access request approved faster."

  Even after production access, you still must verify every identity used as
  From / Source / Sender / Return-Path.

#### 1e. Data residency and GDPR posture

- **Resend:** four sending regions — North Virginia (`us-east-1`), Ireland
  (`eu-west-1`), São Paulo (`sa-east-1`), Tokyo (`ap-northeast-1`). **Critical
  caveat, stated by Resend:** "Region selection controls where your emails are
  *routed and sent from*. It does not control where customer data is stored." All
  account information, including email metadata and API records, is retained in
  the **United States** regardless of sending region
  (https://resend.com/docs/dashboard/domains/regions). Resend publishes a DPA that
  incorporates the EU Standard Contractual Clauses (with UK and Swiss variants),
  references GDPR (Regulation (EU) 2016/679) for data-subject rights, DPIAs and
  breach notification, and states compliance with the EU-U.S. Data Privacy
  Framework (https://resend.com/legal/dpa).
- **Postmark:** **unverified.** I could not reach a primary Postmark page on EU
  data residency or DPA terms within this pass (the URLs tried 404'd). Do not
  assume EU residency is available; check with Postmark directly if it becomes a
  requirement.
- **Amazon SES:** region-scoped by construction — quotas, identities and sandbox
  status are all per-Region
  (https://docs.aws.amazon.com/ses/latest/dg/quotas.html), and you choose the
  Region endpoint you call. This is the only one of the three that gives genuine
  EU-region processing of the sending path. I did not fetch the AWS GDPR/DPA
  page, so the specific AWS DPA terms are **unverified here**.

#### 1f. Rate limits relevant at low volume

- **Resend:** "The default maximum rate limit is 10 requests per second per
  team," shared across all API keys for that team, increasable on request
  (https://resend.com/docs/api-reference/introduction). Quota errors surface as
  429 `rate_limit_exceeded` / `daily_quota_exceeded` / `monthly_quota_exceeded`.
  The free tier's **100 emails/day** cap is the one that could actually bite
  during a bulk onboarding.
- **Postmark:** returns 429 "Rate Limit Exceeded… we have detected that you are
  making requests at a rate that exceeds acceptable use of the API," but
  **publishes no numeric limit** in the API overview
  (https://postmarkapp.com/developer/api/overview). Treat the exact threshold as
  unverified; it is not a constraint at our volume. Paid tiers state unlimited
  daily sending.
- **Amazon SES** (https://docs.aws.amazon.com/ses/latest/dg/quotas.html): quotas
  are per-Region and counted **by recipient, not by message**. Sandbox: 200 per
  24h, 1/sec. Production: "varies based on your specific use case," adjustable.
  Max 50 recipients per message; max 10,000 verified identities per Region. All
  SES API actions *except* `SendEmail`/`SendRawEmail`/`SendTemplatedEmail` are
  throttled to one request per second.

None of these bind at Dmitri's volume except Resend's free-tier 100/day.

---

### 2. Creating and verifying a sending domain

**Resend** (https://resend.com/docs/dashboard/domains/introduction,
https://resend.com/docs/dashboard/domains/cloudflare)

1. Dashboard → **Domains** → **Add Domain**. Enter the sending domain — use a
   subdomain (`mail.dmitri.example`), which Resend explicitly advises over the
   root domain to isolate sending reputation. Each subdomain verifies
   independently.
2. Choose a **region** (`us-east-1`, `eu-west-1`, `sa-east-1`, `ap-northeast-1`).
   This sets where mail is routed from, not where data is stored.
3. Resend generates three records for you:
   - **MX** on `send` → `feedback-smtp.<region>.amazonses.com`, priority `10` —
     lets bounce and complaint feedback route back to your domain.
   - **TXT (SPF)** on `send` → `"v=spf1 include:amazonses.com ~all"`.
   - **TXT (DKIM)** on `resend._domainkey` → `p=<public key>`.
   (Values shown are the documented examples; use the exact ones the dashboard
   generates. Resend's docs note DKIM may be presented as TXT or CNAME and cite a
   1024-bit key.)
4. Publish them at your DNS provider. **Omit your own domain from the host
   field** — enter `send` and `resend._domainkey`, not
   `send.mail.dmitri.example`, if your provider auto-appends the zone.
5. Click **Verify**. Status walks `not_started` → `pending` → `verified`. If it
   has not verified **within 72 hours** the domain goes to `failed` and you start
   over.
6. Optional: enforce TLS, customise the Return-Path subdomain, enable
   open/click tracking. **Leave open and click tracking off for reset links** —
   rewriting a one-time-use URL through a tracking redirector is exactly the kind
   of thing that breaks single-use tokens and trips phishing heuristics. (That
   recommendation is my engineering judgement, not a Resend statement.)

**Postmark**
(https://postmarkapp.com/support/article/1046-how-do-i-verify-a-domain)

1. **Sender Signatures** page → add your domain → **DNS Settings**.
2. **DKIM:** Postmark provides a **TXT** record with a specific hostname and
   value. Publish it. Postmark typically verifies within 48 hours; the **Verify**
   button forces a re-check.
3. **Custom Return-Path:** add a **CNAME**, hostname typically `pm_bounces`,
   value `pm.mtasv.net`. Postmark states this "enables proper SPF alignment for
   bounce handling" — i.e. it is how you get an SPF-aligned envelope sender
   without publishing Postmark into your own apex SPF record.
4. **DMARC:** Postmark's own guidance is to configure DMARC and to "start with a
   permissive `p=none` policy for monitoring before implementing stricter
   enforcement."
5. Allow up to 48 hours for propagation and verification of each record type.
6. `From` must correspond to a confirmed Sender Signature or the send is
   rejected by the API.

> Postmark's exact SPF `include:` mechanism value is **unverified** here — the
> support articles I tried for it 404'd. The custom Return-Path CNAME is the
> documented SPF-alignment path, so publishing a Postmark `include:` in your own
> SPF record may not be required at all. Confirm in the DNS Settings page the
> dashboard renders for your domain before adding anything to an existing SPF
> record.

**Amazon SES**
(https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dkim-easy.html,
https://docs.aws.amazon.com/ses/latest/dg/mail-from.html)

1. SES console → **Configuration → Identities** → create a **Domain** identity.
2. **Easy DKIM:** on the identity's **Authentication** tab, DKIM container →
   **Edit** → **Advanced DKIM settings** → identity type **Easy DKIM**, key
   length **RSA_2048_BIT** (default; `RSA_1024_BIT` only if your DNS provider
   cannot handle 2048). Enable **DKIM signatures**, save. SES then "automatically
   adds a 2048-bit DKIM key to every email that you send from that identity."
   Publish the generated records with your DNS provider (Route 53 users can have
   SES publish them automatically).
   - Key-rotation guardrails: you cannot switch to the same length you already
     have, and you cannot change length more than once per 24 hours (except a
     first downgrade to 1024 in that period).
   - Migration warning: switching from BYODKIM to Easy DKIM leaves a window where
     mail may go out **unsigned** while verification is pending — do it on a
     throwaway subdomain first or during downtime.
3. **Custom MAIL FROM domain** (needed only if you want SPF-based DMARC
   alignment; SES's default MAIL FROM is a subdomain of `amazonses.com`, which
   passes SPF but does **not** align with your From domain). Requirements: it
   must be a subdomain of the verified identity's parent domain, must **not** be
   a subdomain you also send from, and must **not** be one you receive mail on.
   Identity → **Custom MAIL FROM domain** → Edit → tick **Use a custom MAIL FROM
   domain**, enter the subdomain, choose **Behavior on MX failure**:
   - *Use default MAIL FROM domain* — falls back to `amazonses.com` (fails
     forward, loses SPF alignment silently); or
   - *Reject message* — returns `MailFromDomainNotVerified` and drops the send.
4. Publish the generated **MX** and **SPF (type TXT)** records for the MAIL FROM
   subdomain. **Exactly one MX record** must exist on that subdomain — "if the
   MAIL FROM domain has multiple MX records, the custom MAIL FROM setup with
   Amazon SES will fail." The MX preference is `10`. SES may take up to 72 hours
   to detect the MX record; the setup state walks Pending → Success, or
   TemporaryFailure → Failed after 72 hours, at which point you restart.
5. **Request production access** (§1d) before you can mail anyone unverified.

---

### 3. The DNS records themselves

Three mechanisms, three separate jobs. Getting two of three right is the common
failure.

#### SPF — RFC 7208 (https://www.rfc-editor.org/rfc/rfc7208)

- **Type:** `TXT`. **Host:** the domain that appears in the **MAIL FROM /
  envelope-sender**, not necessarily the From domain.
- **Value shape:** must begin with exactly `v=spf1`, terminated by a space or end
  of record, followed by mechanisms and a final `all`:
  - Resend (documented example): `v=spf1 include:amazonses.com ~all` published on
    the `send` host.
  - SES custom MAIL FROM: a TXT record generated by the console for the MAIL FROM
    subdomain, published alongside a single MX.
  - Postmark: the custom Return-Path CNAME (`pm_bounces` → `pm.mtasv.net`) is the
    documented SPF-alignment path; the `include:` value is unverified here.
- **What it does:** tells receivers which servers may use your domain in the
  envelope sender. **If missing:** SPF returns `none`; you lose one of the two
  DMARC authentication paths, and you must then rely entirely on DKIM.
- **Qualifiers, per RFC 7208:** `-all` produces **fail** — "an explicit
  authorization denial." `~all` produces **softfail** — "a weak statement" that
  the host is "probably not authorized" but not definitively denied. Start with
  `~all`; move to `-all` only once DMARC aggregate reports show no legitimate
  sender missing from the record.
- **One record per domain (§3.2/4.5):** "A domain name MUST NOT have multiple
  records that would cause an authorization check to select more than one
  record." Two `v=spf1` TXT records on the same host is a **permerror**, which
  is a *worse* outcome than having none — you must merge them into one record
  with multiple mechanisms. This is the single most common way an SPF setup gets
  broken by adding a second vendor.
- **The 10-lookup limit (§4.6.4):** "SPF implementations MUST limit the total
  number of those terms to 10 during SPF evaluation." Counting toward the limit:
  `include`, `a`, `mx`, `ptr`, `exists`, and the `redirect` modifier. **Not**
  counting: `all`, `ip4`, `ip6`. Exceeding 10 is a permerror. This is the
  strongest structural argument for sending from a dedicated subdomain: the
  subdomain gets its own fresh SPF record with a single `include:`, and the
  apex's existing budget (Google Workspace, a CRM, a helpdesk) is untouched.

#### DKIM — RFC 6376

- **Type and host:** `<selector>._domainkey.<domain>`. Type depends on provider:
  - **Resend:** **TXT** at `resend._domainkey`, value `p=<public key>`. Resend's
    docs describe it as TXT/CNAME with a 1024-bit key
    (https://resend.com/docs/dashboard/domains/introduction and the Cloudflare
    walkthrough).
  - **Postmark:** **TXT**, hostname and value supplied on the DNS Settings page
    (https://postmarkapp.com/support/article/1046-how-do-i-verify-a-domain).
  - **Amazon SES Easy DKIM:** SES generates the records for you and signs with a
    **2048-bit** key by default (1024 selectable)
    (https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dkim-easy.html).
    SES's Easy DKIM is the CNAME-delegated style — SES holds the private key and
    rotates it, and your zone points at SES-hosted key records; this is why you
    can change key length from the console without re-publishing key material.
- **CNAME-delegated vs published TXT keys — why it matters:** with CNAME
  delegation (SES Easy DKIM) the provider can rotate keys without you touching
  DNS. With a published TXT key (Resend, Postmark as documented) you own a static
  public key in your zone and any rotation is a DNS change you must make. For a
  low-volume deployment either is fine; the TXT approach is simpler to reason
  about and to verify with `dig`.
- **What it does:** adds a cryptographic signature in the message header. Per
  AWS's summary, "the digital signature stays with the email message because it's
  part of the email header, DKIM works even when a message has been forwarded
  between mail servers (as long as the message content has not been modified)"
  (https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dmarc.html).
- **If missing:** the message has no forwarding-survivable authentication. Since
  SPF breaks on forwarding (the envelope is rewritten), a DKIM-less setup fails
  DMARC for any forwarded mail — and reset links get forwarded constantly inside
  companies. **DKIM is the more important of the two for our use case.**

#### DMARC — RFC 7489 (https://www.rfc-editor.org/rfc/rfc7489)

- **Type:** `TXT`. **Host:** `_dmarc.<domain>` — "the Domain Owner of example.com
  would post DMARC preferences in a TXT record at `_dmarc.example.com`."
- **Required tags:** `v`, which "MUST have the value of `DMARC1`" and must appear
  first; and `p`, "REQUIRED for policy records."
- **Value shape** (AWS's documented example):
  `"v=DMARC1;p=quarantine;rua=mailto:my_dmarc_report@example.com"`.
  Resend's suggested starting record:
  `"v=DMARC1; p=none; rua=mailto:dmarcreports@example.com;"`
  (https://resend.com/docs/dashboard/domains/dmarc).
- **What it does:** binds SPF and DKIM to the **From** header the user actually
  sees, and tells receivers what to do on failure. Per AWS: "Using SPF and DKIM
  alone does nothing to insure that the From address is authenticated… SPF only
  checks the domain specified in the MAIL FROM address (not seen by your
  recipient). DKIM only checks the domain specified in the DKIM signature (also,
  not seen by your recipient)."
- **If missing:** receivers have no stated policy, and increasingly major
  mailbox providers deprioritise or reject unauthenticated bulk-ish mail. You
  also get **no aggregate reports**, which means no visibility into whether your
  reset mail is authenticating in the wild.

---

### 4. DMARC rollout and alignment

#### Alignment: what "pass" actually requires

Per RFC 7489, identifier alignment occurs "when the domain in the RFC5322.From
address matches a domain validated by SPF or DKIM (or both)," because "merely
bearing a valid signature is not enough to infer authenticity of the Author
Domain." DMARC passes if **at least one** of aligned-SPF or aligned-DKIM passes,
and fails only if both fail
(https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dmarc.html).

Two alignment modes, set by `aspf` (SPF) and `adkim` (DKIM):

- **`r` — relaxed, the default when the tag is absent.** "The Organizational
  Domains of both the DKIM-authenticated signing domain and that of the
  RFC5322.From domain must be equal." So a From of `no-reply@mail.example.com`
  aligns with a DKIM `d=example.com` or a MAIL FROM of `bounce.example.com` —
  same org domain.
- **`s` — strict.** "Only an exact match between both of the Fully Qualified
  Domain Names (FQDNs) is considered."

Provider-specific traps:

- **SES + SPF alignment:** SES states that "in order to achieve SPF alignment
  with SES, the domain's DMARC policy must not specify a strict SPF policy
  (`aspf=s`)," and that SPF alignment requires a **custom MAIL FROM domain** —
  the default `amazonses.com` MAIL FROM passes SPF but never aligns.
- **SES + DKIM alignment:** "SES uses a strict DKIM policy by default" for its
  own signing; if you send from a subdomain of the From domain you need relaxed
  `adkim` (which is the default anyway — just do not set `adkim=s` casually).
- **Verify with:** `dig TXT _dmarc.example.com` and look for `aspf=` / `adkim=`
  in the `v=DMARC1` record. Absent tag = relaxed.

**For Dmitri:** leave `aspf` and `adkim` unset (relaxed). Relaxed alignment is
what makes a `mail.` subdomain sender work against an org-domain DMARC record.

#### The rollout: p=none → quarantine → reject

AWS's stated best practice, which matches RFC 7489's design intent and Resend's
guidance, is a phased rollout, doing **each step on subdomains first and the
top-level domain last**
(https://docs.aws.amazon.com/ses/latest/dg/send-email-authentication-dmarc.html):

**Stage 1 — `p=none` (monitoring).** Publish
`v=DMARC1; p=none; rua=mailto:dmarc@dmitri.example`. Nothing changes for
recipients; you start receiving aggregate reports.

*What to watch in the `rua` reports:* per AWS, the reports "give the numbers and
sources of messages that pass these checks, versus those that don't," letting you
"easily see how much of your legitimate traffic is or isn't covered." Concretely:
- enumerate every source IP/org sending as your domain and classify each as
  known-legitimate or not — a domain that has been live for a while usually has
  forgotten senders (invoicing, ATS, monitoring);
- confirm the Resend/Postmark/SES source shows both SPF and DKIM **aligned**, not
  merely passing;
- expect forwarding signal — AWS: "You'll see signs of forwarding, since
  forwarded messages will fail SPF and DKIM if the content is modified." A
  forwarded reset link failing SPF but passing DKIM is the *expected, healthy*
  pattern and is exactly why DKIM must be right;
- note fraudulent/spoofing volume and where it originates.

*Timeline:* Resend's guidance is that "spending a few [days] at this step is a
good rule of thumb" for testing, but that is testing your own new sender, not
discovering an existing domain's full sender inventory. Aggregate reports arrive
roughly **once per day** per receiver (AWS: "Email providers typically send these
aggregated reports once per day, although these policies differ from provider to
provider"), so a monitoring window shorter than a couple of weeks cannot see
monthly-cadence senders. **Realistically: 2–4 weeks minimum on an established
domain; a few days is defensible only on a brand-new subdomain with exactly one
sender.** (The "2–4 weeks" figure is my judgement from the once-per-day report
cadence, not a provider statement.)

**Stage 2 — `p=quarantine`.** Move here, per AWS, "when you believe that all or
most of your legitimate traffic is sending domain-aligned with either SPF or
DKIM, and you understand the impact." Failing mail goes to "the local equivalent
of a spam folder instead of your customers' inboxes." Optionally ramp with `pct`
(RFC 7489's percentage tag, 0–100) to enforce on a sample first.

*What to watch:* the same aggregate data, now with a sharper question — is the
aligned-pass rate for *legitimate* sources at or near 100%? Any remaining
legitimate source failing here is now landing in spam. AWS notes that under
quarantine "the aggregate data provides information about the percentages of
email passing or failing SPF, DKIM, and DMARC checks" — you infer impact
statistically rather than seeing hard failures.

**Stage 3 — `p=reject`.** "Usually the final step… they won't even be
quarantined to a spam or junk folder, but will be rejected outright." AWS notes
the diagnostic upside: "you'll know exactly which messages are failing the DMARC
policy as the rejection will result in an SMTP bounce." AWS characterises reject
as "best for new domains or existing domains that have gone through the prior two
steps."

AWS is blunt about the risk of skipping stages: "*using the wrong one at the
wrong time can cause your email to not be delivered.*"

#### Subdomain vs org domain, and how `sp` interacts

- Use a **sending subdomain** (`mail.dmitri.example`). Resend advises it for
  reputation isolation; Postmark advises separate subdomains per stream; SES
  *requires* a subdomain for a custom MAIL FROM domain and further requires that
  it not be used for sending-from or receiving.
- **Policy inheritance:** RFC 7489's `sp` tag "applies only to subdomains of the
  domain queried and not to the domain itself," and if `sp` is absent, "the
  policy specified by the `p` tag MUST be applied for subdomains." So publishing
  a single `_dmarc.dmitri.example` record with `p=none` covers
  `mail.dmitri.example` too — no separate record needed for the subdomain unless
  you want it to differ.
- **Useful consequence for the rollout:** you can advance the sending subdomain
  ahead of the org domain by publishing a *separate* `_dmarc.mail.dmitri.example`
  record at `p=quarantine`/`p=reject` while the apex sits at `p=none` — which is
  exactly the "do each step first with each of your sub-domains, and finally with
  the top-level domain" sequence AWS prescribes. The subdomain carries one known
  sender, so it can reach enforcement quickly and safely.
- **Conversely,** setting `sp=reject` on the apex early will hit your sending
  subdomain immediately. Do not set `sp` to something stricter than `p` until the
  subdomain's own reports are clean.
- **Relaxed alignment is what makes this work:** with `adkim=r` (default), a From
  of `no-reply@mail.dmitri.example` and a DKIM `d=` anywhere under
  `dmitri.example` align on the Organizational Domain. Setting strict alignment
  would force exact FQDN matching and is not needed here.

#### Concrete target records for Dmitri (Resend, `mail.dmitri.example`)

Using Resend's documented example values — **replace with the exact values the
Resend dashboard generates for your domain and region**:

| Host | Type | Value | Notes |
|---|---|---|---|
| `send.mail.dmitri.example` | MX | `feedback-smtp.<region>.amazonses.com` | priority 10; bounce/complaint feedback |
| `send.mail.dmitri.example` | TXT | `v=spf1 include:amazonses.com ~all` | one SPF record on this host only |
| `resend._domainkey.mail.dmitri.example` | TXT | `p=<public key>` | DKIM public key |
| `_dmarc.dmitri.example` | TXT | `v=DMARC1; p=none; rua=mailto:dmarc@dmitri.example;` | start here; covers the subdomain by inheritance |

The apex `dmitri.example` SPF record is **not touched** by this setup — which is
the point.
