# Research: making revocation take effect on an already-established connection

> **Scope.** Spec 041 (DMI-97) makes `agents.revoked_at` bite on a WebSocket the Pi
> already holds. Today revocation is read exactly once, in
> `dependencies/agent_auth.authenticate_agent` at the WS upgrade; a Pi holds that
> socket for days (ADR-011 §1, single Railway replica), so a device revoked at
> 10:00 keeps receiving pushed commands and keeps writing command lifecycle
> transitions until it happens to disconnect. The spec adds two lazy re-check
> gates — one on every inbound frame, one in `commands.deliver()` — and
> explicitly rules out a proactive disconnect, because nothing in the codebase
> writes `revoked_at` yet, so there is no event to hook.
> Two questions: **(1)** is lazy re-checking a recognised, defensible pattern, and
> what vocabulary does the literature use for it; **(2)** the narrow engineering
> disagreements — `expire_on_commit`, stale cached authorization attributes, and
> blocking DB I/O on the event loop.
> **Sources fetched 2026-09-01.** Versions in `backend/.venv`: SQLAlchemy
> **2.0.51**, SQLModel **0.0.39**, FastAPI **0.139.0**, Starlette **1.3.1**,
> anyio **4.14.1**, psycopg **3.3.4**.
> Companion note: `docs/research/sync-vs-async-db-stack.md` (threadpool/event-loop
> ground rules) and `docs/research/ws-session-lifetime.md` (session-per-frame,
> whose §5.4 logged this exact gap as out of scope).

---

## TL;DR verdict

**Revocation-on-use is a recognised, named pattern — the literature calls it
*pull-based* revocation — and it is the *dominant* deployed pattern, not a
shortcut. Spec 041's two gates are defensible and correctly placed. But the
literature is equally clear about two things: pull-based revocation is only sound
when it is *hard-fail*, and its weakness is the idle case, which spec 041 already
names in its own out-of-scope section.**

Three findings carry the verdict:

1. **The design axis has standard names.** Smith, Dickinson & Seamons (NDSS 2020)
   classify every revocation strategy as **pull-based** ("synonymous with
   on-demand revocation validation… requests for a revocation status occur only
   at the time a certificate needs to be validated"), **push-based**, or
   network-assisted, and name **Timeliness** as one of six criteria a revocation
   strategy must meet
   (https://www.ndss-symposium.org/wp-content/uploads/2020/02/24084-paper.pdf, §II).
   Spec 041 is pull-based / revocation-on-use with a **zero-length staleness
   window on every checked path** — it reads the live row, not a cache, on each
   use. That is *stronger* than every deployed pull-based PKI system, which
   caches OCSP/CRL status "for up to 7 days" (ibid, §VIII-B).

2. **The gap is idleness, not staleness — and the biggest cloud IoT vendor has
   the same gap, only worse.** AWS IoT Core's own API reference states: "Within a
   few minutes of updating a certificate from the ACTIVE state to any other
   state, IoT disconnects all devices that used that certificate to connect"
   (https://docs.aws.amazon.com/cli/latest/reference/iot/update-certificate.html)
   — an explicitly *minutes-long*, vendor-promised window for a fleet product,
   and revocation-on-write at that. OpenSSH is pure revocation-on-use: `RevokedKeys`
   "may be consulted for each public key authentication attempt received by
   sshd(8)" (https://man.openbsd.org/sshd_config#RevokedKeys) — an already-open
   SSH session is untouched by revoking its key. Dmitri's revoked-but-silent Pi
   holds a socket it cannot act through; that is a strictly better position than
   AWS's few minutes of a device that still can.

3. **NIST is the one source that asks for more, and it asks for the thing spec
   041 defers.** SP 800-207 tenet 6: "All resource authentication and
   authorization are dynamic and strictly enforced before access is allowed. This
   is a constant cycle of obtaining access, scanning and assessing threats,
   adapting, and continually reevaluating trust in ongoing communication"
   (https://doi.org/10.6028/NIST.SP.800-207, §2.1). And on the Policy
   Administrator: "If the session is denied (**or a previous approval is
   countermanded**), the PA signals to the PEP to shut down the connection"
   (ibid, §3.1). That is revocation-on-write. It is the right eventual shape and
   the right thing to name as future work — it is not a reason to hold spec 041.

**On the engineering question, the disagreement is settled against the spec's
current text, twice.** `expire_on_commit` defaults to `True` (verified in the
installed SQLAlchemy 2.0.51 source, `orm/session.py:1510`), and SQLModel's
`Session` does not override it. `enqueue()` calls `session.commit()`, which
expires every instance — so the "served from the identity map, costs no extra
SELECT" reasoning in `ARCHITECTURE.md` §3 is **factually wrong**: the read emits a
fresh SELECT. Same defect in §1 for the status frame, where `apply_status()`
commits *or* rolls back before `touch_agent_last_seen` runs. This is good news for
security (the read is always fresh) and bad news for two sentences of
justification that need rewriting. Details and recommended edits in
"What this means for spec 041".

---

## Part 1 — the general problem

### 1.1 The vocabulary: pull-based vs push-based revocation

This is the term of art the spec should adopt. **Let's Revoke** (Smith, Dickinson
& Seamons, *NDSS 2020* — academic, peer-reviewed;
https://www.ndss-symposium.org/wp-content/uploads/2020/02/24084-paper.pdf,
DOI 10.14722/ndss.2020.24084):

> "These strategies for certificate revocation generally fall into one of three
> classifications: pull-based, push-based, or network-assisted."

> "**Pull-based revocation is synonymous with on-demand revocation validation.**
> Pull-based requests for a revocation status occur only at the time a
> certificate needs to be validated."

The same paper (§II) enumerates six criteria a universal revocation strategy
should meet — Efficiency, **Timeliness** ("Revocation status updates should be
sent frequently to ensure that they never become stale"), **Failure Model** ("The
strategy should enable clients to adopt a hard-failure policy"), Privacy,
Deployability, and (sixth) scalability. Timeliness and Failure Model are the two
that matter for spec 041.

Its measurement of the deployed window (§VIII-B) is the number to quote when
someone asks how big a revocation window the field tolerates:

> "Pull-based strategies, such as CRLs and OCSP, typically cache revocation
> status information and assume it is valid for **up to 7 days**. A 7-day period
> leaves a large window of time in which an adversary can exploit a compromised
> certificate, even after correctly revoking that certificate."

> "Push-based strategies generally use periodic updates. CRLset, OneCRL, and
> CRLite all push **daily** updates to clients, which drastically reduces an
> adversary's window of opportunity when compared to traditional pull-based
> methods."

**Read that against spec 041.** Dmitri's pull is not cached at all: each gate
reads the `agents` row inside a fresh per-frame session (see §2.1 below). The
window between "`revoked_at` is committed" and "the check sees it" is one
Postgres Read Committed statement — microseconds. The window that actually exists
in spec 041 is a different quantity: **the time until the revoked agent next uses
the connection.** That is unbounded for a silent agent, and bounded by the frame
interval for a talking one. The literature has no name for "unbounded for an idle
principal"; the closest framing is Timeliness applied to *use* rather than to
*status freshness*.

### 1.2 Continuous / re-evaluated authorization

#### NIST SP 800-207, Zero Trust Architecture (normative — US federal standard)

Fetched as PDF from https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-207.pdf
(DOI 10.6028/NIST.SP.800-207) and read locally. The relevant tenets, §2.1,
verbatim:

> "3. **Access to individual enterprise resources is granted on a per-session
> basis.** Trust in the requester is evaluated before the access is granted. …
> This could mean only 'sometime recently' for this particular transaction and
> may not occur directly before initiating a session or performing a transaction
> with a resource."

> "6. **All resource authentication and authorization are dynamic and strictly
> enforced before access is allowed.** This is a constant cycle of obtaining
> access, scanning and assessing threats, adapting, and continually reevaluating
> trust in ongoing communication. … **Continual monitoring with possible
> reauthentication and reauthorization occurs throughout user transactions**, as
> defined and enforced by policy (e.g., time-based, new resource requested,
> resource modification, anomalous subject activity detected) that strives to
> achieve a balance of security, availability, usability, and cost-efficiency."

Two things to notice. First, tenet 3's "only 'sometime recently'" is NIST
explicitly conceding that authorization need not be re-verified immediately
before every action — the standard does **not** demand a synchronous check per
operation. Second, tenet 6's parenthetical lists the acceptable *triggers* for
re-authorization, and **"new resource requested"** and **"resource
modification"** are exactly what spec 041's two gates are: a re-check triggered by
the principal's next act. This is the strongest normative endorsement available
for revocation-on-use.

NIST does also describe the push shape, in the component definitions (§3.1):

> "**Policy administrator (PA):** This component is responsible for establishing
> and/or shutting down the communication path between a subject and a resource
> (via commands to relevant PEPs). … If the session is denied (**or a previous
> approval is countermanded**), the PA signals to the PEP to shut down the
> connection."

> "**Policy enforcement point (PEP):** This system is responsible for enabling,
> monitoring, and eventually terminating connections between a subject and an
> enterprise resource."

and, in §3.3:

> "PAs may also place a hold or pause on a communication session to reauthenticate
> and reauthorize the connection in accordance with policy requirements. The PA is
> also responsible for **issuing the command to terminate the connection based on
> policy** (e.g., after a time-out, when the workflow has been completed, due to a
> security alert)."

In Dmitri's terms the backend is simultaneously PDP, PA and PEP: the same process
holds the socket and reads `revoked_at`. That collapse is why the push variant is
so cheap here — a future `POST /agents/{id}/revoke` can call
`agent_connections.close_revoked()` directly, in-process, with no signalling
protocol at all. Which is precisely why deferring it costs little and is easy to
add later.

#### OpenID Shared Signals Framework + CAEP (normative — OIDF final specs)

**SSF 1.0** (https://openid.net/specs/openid-sharedsignals-framework-1_0-final.html):

> "This Shared Signals Framework (SSF) enables sharing of signals and events
> between cooperating peers. It enables multiple applications such as Risk
> Incident Sharing and Coordination (RISC) and the Continuous Access Evaluation
> Profile."

**The model is not exclusively push.** SSF defines two delivery methods — Push
Delivery via RFC 8935 (transmitter HTTP-POSTs to the receiver) and **Poll
Delivery via RFC 8936** (receiver polls the transmitter's endpoint). A receiver
picks one when it creates the Event Stream. So the flagship "continuous
authorization" standard family explicitly blesses a *pull* transport for
revocation signals. Anyone arguing "the industry has moved to push" is
overstating it.

**CAEP 1.0** (https://openid.net/specs/openid-caep-1_0-final.html) is the profile
that defines the actual revocation event:

> "Transmitters may send continuous updates using which Receivers can **attenuate
> access** to shared human or robotic users, devices, sessions and applications."

The `session-revoked` event type (URI
`https://schemas.openid.net/secevent/caep/event-type/session-revoked`) "signals
that the session identified by the subject has been revoked", carries no
event-specific claims, and when `event_timestamp` is present its value "MUST
represent the time at which the session revocation occurred". Note what CAEP does
*not* specify: what the receiver must do on receipt, or how fast. It standardises
the signal, not the enforcement latency. **The "device" and "robotic user"
subjects in that abstract are the closest thing in the standards literature to
Dmitri's revoked Pi.**

#### Microsoft Entra Continuous Access Evaluation (vendor — Microsoft Learn)

https://learn.microsoft.com/en-us/entra/identity/conditional-access/concept-continuous-access-evaluation
is the most useful vendor writeup because it states the problem, the rejected
alternative, and hard numbers.

The problem (identical in shape to Dmitri's, at token granularity instead of
socket granularity):

> "Customers express concerns about the lag between when conditions change for a
> user, and when policy changes are enforced. **Microsoft experimented with the
> 'blunt object' approach of reduced token lifetimes but found they degrade user
> experiences and reliability without eliminating risks.**"

That sentence is worth keeping: shortening the credential lifetime — Dmitri's
equivalent would be forcing the Pi to redial hourly — is a documented **failed**
alternative, tried at scale by a vendor with every incentive to make it work.

The mechanism and its cost:

> "The goal for critical event evaluation is for response to be **near real time,
> but latency of up to 15 minutes might be observed because of event propagation
> time**; however, IP locations policy enforcement is instant."

> "Token lifetime increases to long-lived, **up to 28 hours**, in CAE sessions.
> Critical events and policy evaluation drive revocation, not just an arbitrary
> time period."

And the limits, which read as a catalogue of everything that goes wrong once you
build revocation-on-write:

> "Changes made to Conditional Access policies and group membership made by
> administrators could take **up to one day** to be effective."
> "SharePoint Online and Teams typically have a 15-minute delay. Exchange Online
> typically has a 35-40 minute delay." (re-enabling a disabled user)
> "**CAE doesn't support Guest user accounts.** CAE revocation events and IP
> based Conditional Access policies aren't enforced instantaneously."
> On coauthoring: "CAE might not revoke their access to the document immediately
> based on policy change events. In this case, the user loses access completely
> after: Closing the document / Closing the Office app / After 1 hour…"

That last one is the exact shape of spec 041's out-of-scope caveat — a live
session that keeps working until it next transacts — shipped as documented
behaviour in Microsoft's flagship continuous-authorization product.

#### Google's CAEP proposal (vendor — Google Cloud blog)

https://cloud.google.com/blog/products/identity-security/re-thinking-federated-identity-with-the-continuous-access-evaluation-protocol
states the problem cleanly:

> "These login sessions can last hours or even days—especially on mobile devices."

> "Today's technology determines access authorization **only at the time of
> authentication**, typically with the help of a federated identity provider… it's
> hard for cloud-based identity providers to signal a change in session
> authorization."

> "Our vision for continuous access evaluation is based on a publish-and-subscribe
> ('pub-sub') approach. … 1. It's complementary to federated or cert-based
> authentication 2. **It's not as chatty as WAM** 3. It doesn't impact latency for
> user access"

The rejected alternative — "the chatty WAM model", i.e. evaluating every access
against a central server — is the *synchronous re-check* design. Google rejects it
on volume grounds ("isn't viable with today's traffic volumes and distributed
environments"), which does not apply to Dmitri: one Postgres row read per frame,
in-process, is not chatty at Dmitri's scale. **Google's argument against
per-access evaluation is a scale argument, not a correctness argument, and Dmitri
is on the other side of the scale threshold.**

### 1.3 The PKI precedent, and what measurement showed

**Liu et al., "An End-to-End Measurement of Certificate Revocation in the Web's
PKI", *ACM IMC 2015*** — academic, peer-reviewed; verified by reading the paper
PDF at https://www.cs.umd.edu/~dml/papers/revocations_imc15.pdf (also
https://dl.acm.org/doi/10.1145/2815675.2815685; authors: Yabing Liu, Will Tome,
Liang Zhang, David Choffnes, Dave Levin, Bruce Maggs, Alan Mislove, Aaron
Schulman, Christo Wilson).

Abstract, verbatim:

> "Using 74 full IPv4 HTTPS scans, we find that a surprisingly large fraction (8%)
> of the certificates served have been revoked, and that obtaining certificate
> revocation information can often be expensive in terms of latency and bandwidth
> for clients. We then study the revocation checking behavior of 30 different
> combinations of web browsers and operating systems; **we find that browsers
> often do not bother to check whether certificates are revoked (including mobile
> browsers, which uniformly never check).** We also examine the CRLSet
> infrastructure built into Google Chrome…; we find that **CRLSet only covers
> 0.35% of all revocations.** Overall, our results paint a bleak picture of the
> ability to effectively revoke certificates today."

On fail-open, §2.2 — this is the finding that matters most for spec 041:

> "**Thus, browser developers often soft-fail by deciding to trust certificates
> when revocation information is unavailable**, so as not to rest their perceived
> reliability on the shoulders of a disparate set of third-party CAs."

> "Soft-failing when revocation information is unavailable may at first appear to
> be an innocuous trade-off for usability, but in practice it has surprisingly
> extensive implications on the security of the PKI. **Any attacker who can block
> a victim's access to specific domains … could leverage soft-failures to
> effectively turn off the victim's revocation checking.**"

Their conclusions, §6.4:

> "In summary, we observe that **no browser in its default configuration correctly
> checks all revocations** and rejects certificates if revocation information is
> unavailable… In fact, many browsers do not bother to check revocation
> information at all."
> "Perhaps most concerning is the fact that **no mobile browsers check for
> revocations at all.**"

And OCSP stapling deployment (§5): of the servers scanned, "337,856 (2.60%)
support OCSP stapling", with a correction of roughly +18% for servers that only
staple when a fresh response is cached.

**What this precedent actually teaches spec 041.** The PKI failure was *never*
that revocation was checked lazily — OCSP is lazy by construction and that is
fine. It failed on three axes Dmitri is not exposed to:

| PKI failure mode | Dmitri's exposure |
|---|---|
| Revocation status is **remote** (third-party OCSP responder, network round trip) | The revocation flag is a column in the same Postgres the checker already has a session on. No network, no third party. |
| Therefore checkers **soft-fail** when the responder is unreachable | There is no "unreachable" state distinct from "the whole backend is down". A failed DB read raises and the frame is not processed. Spec 041 must keep it that way — see the recommendation on fail-closed. |
| **Cached** status assumed valid up to 7 days | No cache. Fresh Read Committed read per gate (§2.1). |

The one PKI lesson that does transfer verbatim: **an unreadable or unavailable
revocation source must fail closed.** OpenSSH gets this right and says so
(https://man.openbsd.org/sshd_config#RevokedKeys): "Note that **if this file is
not readable, then public key authentication will be refused for all users.**"

### 1.4 Token revocation and bounding the window

**RFC 7009, OAuth 2.0 Token Revocation** (normative;
https://www.rfc-editor.org/rfc/rfc7009). The relevant admission is §2.1:

> "The invalidation takes place immediately, and the token cannot be used again
> after the revocation. **In practice, there could be a propagation delay, for
> example, in which some servers know about the invalidation while others do
> not.**"

and, same section:

> "A client compliant with [RFC6749] **must be prepared to handle unexpected token
> invalidation at any time.**"

RFC 7009 revokes at the authorization server; it says nothing about resource
servers that have already accepted a token, which is why CAEP exists. The three
industry answers to "how do you bound the window", with their costs:

| Strategy | Window | Cost | Who |
|---|---|---|---|
| Short TTL + refresh | ≤ TTL (1 h default) | "degrade user experiences and reliability without eliminating risks" — Microsoft, above | Classic OAuth |
| Revocation list consulted on use (**revocation-on-use**) | ≈ 0 if uncached; cache TTL if cached | one lookup per use | OCSP, `sshd` `RevokedKeys`, **spec 041** |
| Push an event (**revocation-on-write**) | propagation delay (≤ 15 min claimed, ≤ 1 day for some changes) | a whole signalling subsystem, plus per-receiver enforcement semantics | CAEP / Entra CAE / AWS IoT |

Spec 041 sits in row 2 with the smallest window of the three on every path it
covers. Its residual risk is entirely in *paths it does not cover* — i.e. an idle
socket — not in the size of any window.

### 1.5 Long-lived connection protocols: what the implementations actually do

**MQTT 5.0** (normative — OASIS standard;
https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html) adds an AUTH
packet (§3.15) and a re-authentication flow (§4.12.1) using Authenticate Reason
Code `0x19` (Re-authenticate), for enhanced (challenge-response) authentication.
**Not verified verbatim:** the fetch of §4.12.1 returned only a paraphrase and a
partial reproduction; treat the exact wording as unconfirmed. What is confirmed
from the fetched Table 2-6 is that reason code `0x87` "Not authorized" is valid on
DISCONNECT as well as CONNACK — i.e. **the protocol does provide a code for the
server to tear down an authenticated session on an authorization grounds.**
This is the direct analogue of spec 041's proposed `4001 revoked` close code, and
supports the spec's instinct that the *reason* belongs on the wire.

**EMQX** (vendor docs / project source). The authentication result cache has
"**Cache TTL**: Duration a cached entry remains valid. Default: `1 minute`"
(https://docs.emqx.com/en/emqx/latest/access-control/authn/authn.html) — a
one-minute authorization staleness budget in a production MQTT broker, applied to
freshly *connecting* clients. For already-connected clients, the banlist page
(https://docs.emqx.com/en/emqx/latest/access-control/blacklist.html) states that
"**Banning through regular expressions does not apply to clients that are already
connected**"; the docs read here are otherwise silent on direct (client-ID /
username / IP) bans. EMQX PR #9367, "feat(banned): kick session when it is banned
by clientid" (https://github.com/emqx/emqx/pull/9367), argues in its own title and
description that "a banned client shouldn't continue to publish/receive, so it's
better to kick its session when it is banned" — i.e. **EMQX shipped without
kicking live sessions, treated it as a gap, and closed it later with an explicit
kick.** That is the same trajectory spec 041 is on, and evidence that shipping the
lazy gates first is a normal sequencing, not a defect. *(Caveat: a PR title and
description are project source, not documentation; the exact released behaviour
per ban type was not verified.)*

**Mosquitto**: the `mosquitto(8)` man page (https://mosquitto.org/man/mosquitto-8.html)
documents SIGHUP config reload and that "Not all configuration parameters can be
reloaded without restarting", but **does not document** what happens to
already-connected clients when a password or ACL changes. Explicitly unverified —
do not claim Mosquitto behaviour either way.

**OpenSSH** (normative for the implementation — OpenBSD man page;
https://man.openbsd.org/sshd_config#RevokedKeys):

> "Keys listed in this file will be refused for public key authentication. Note
> that if this file is not readable, then public key authentication will be
> refused for all users."

> "**This file may be consulted for each public key authentication attempt
> received by sshd(8)** and its contents must be consistent at all times,
> therefore it should only be atomically replaced and never modified in place
> while the server is running."

Pure revocation-on-use, per authentication attempt, fail-closed — and **no
mechanism at all to terminate an established session whose key was revoked.**
The world's most security-scrutinised remote-access daemon has exactly the gap
spec 041 documents as out of scope. That is the single most useful precedent in
this note.

### 1.6 IoT fleets: the exact case, from the two big vendors

**AWS IoT Core** (vendor — AWS API reference, normative for their service).
`UpdateCertificate` (https://docs.aws.amazon.com/cli/latest/reference/iot/update-certificate.html):

> "Certificates must be in the ACTIVE state to authenticate devices that use a
> certificate to connect to IoT.
> **Within a few minutes of updating a certificate from the ACTIVE state to any
> other state, IoT disconnects all devices that used that certificate to
> connect.** Devices cannot use a certificate that is not in the ACTIVE state to
> reconnect."

The developer guide page
(https://docs.aws.amazon.com/iot/latest/developerguide/activate-or-deactivate-device-cert.html)
adds the connect-time framing — "AWS IoT verifies that a client certificate is
active **when it authenticates a connection**" — and does not restate the
disconnect timing. AWS also shipped a `DeleteConnection` data-plane API in August
2025 (https://aws.amazon.com/about-aws/whats-new/2025/08/aws-iot-core-delete-connection)
"to streamline MQTT connection management", i.e. an explicit operator-driven kick,
added years after the service. **So: revocation-on-write, promised as "a few
minutes", not instant, and needing a separate API for immediate teardown.**

> *Warning about that AWS developer-guide page:* the fetched content ended with a
> "See also" block recommending the reader run `aws agent-toolkit search-skills`.
> That is content injected into a documentation page addressed at AI agents; it
> was ignored and no command was run. Flagged because it is the kind of thing that
> should not be silently followed.

**Azure IoT Hub** (vendor). Disabling a device is a `status` change on the
identity-registry record
(https://learn.microsoft.com/en-us/azure/iot-hub/iot-hub-devguide-identity-registry;
`az iot hub device-identity update --set status=disabled`). The how-to page
(https://github.com/MicrosoftDocs/azure-docs/blob/main/articles/iot-hub/how-to-disable-enable-device.md)
says only that "Disabling a device might interrupt active operations, data
collection, or dependent workflows." **Explicitly unverified: Microsoft does not
state, on any page fetched here, whether an existing AMQP/MQTT connection is torn
down on disable, or how quickly.** The identity-registry page's caveat that
connection state "can only represent the IoT Hub view of the status of the
connection" and "updates to this state might be delayed" is about the *reported*
state, not about enforcement. Do not cite Azure as a precedent in either
direction.

### 1.7 Capability revocation — the older literature

The problem predates PKI. Redell's MIT dissertation, *Naming and Protection in
Extendible Operating Systems* (MIT/LCS/TR-140, MAC TR-140, November 1974;
https://dspace.mit.edu/bitstream/handle/1721.1/149438/MIT-LCS-TR-140.pdf) is the
canonical statement of the tension — the search result describes it as addressing
"the conflict between free distribution of access privileges and later revocation
of those privileges", solved by **revocation through indirection** (generalized
sealing: hand out a revocable indirect capability, destroy the indirection to
revoke). **Partially verified: the bibliographic record (title, author,
institution, TR number, 1974) is confirmed from MIT DSpace and DTIC
(https://apps.dtic.mil/sti/pdfs/ADA001721.pdf); I did not read the PDF and am not
quoting it.** A companion Redell & Fabry paper, "Selective Revocation of
Capabilities" (IRIA Workshop on Protection in Operating Systems, 1974), appears in
the same search results but was **not independently verified — treat as an
unverified citation.**

Why it matters here: indirection-based revocation is *also* revocation-on-use.
The capability holder keeps its capability; the check happens when it *uses* it,
by dereferencing an indirection that has been destroyed. Dmitri's `agents` row is
that indirection, and the two gates are the dereference. This is a fifty-year-old
pattern, not an improvisation.

### 1.8 Answering the design-axis question directly

**Is revocation-on-use recognised and defensible?** Yes, on three independent
grounds:

1. It is one of the three named classes of revocation strategy in the peer-reviewed
   taxonomy (Let's Revoke §II), and the one OCSP, CRLs and `sshd` all use.
2. NIST SP 800-207 tenet 6 names "new resource requested" and "resource
   modification" as legitimate re-authorization triggers — that *is* on-use.
3. The dominant deployed alternative (revocation-on-write / push) ships with
   documented multi-minute-to-multi-day windows at AWS and Microsoft, so it is
   not the strictly-better option it is often assumed to be.

**Is it inadequate?** Only in one respect, and the spec already names it: an idle
principal is never re-evaluated. The literature's answer to that is a *time-based*
trigger, which NIST lists first in its parenthetical ("e.g., time-based, new
resource requested…"). If spec 041 wants to close the idle hole without building
revocation-on-write, the cheapest complete answer is a **periodic sweep** — a
bounded staleness budget, stated as a number.

**What window size is acceptable?** The sources give these anchors, in
descending order of authority:

| Anchor | Window | Source class |
|---|---|---|
| OCSP/CRL cached status | **up to 7 days** — called out as "a large window" | academic (Let's Revoke §VIII-B) |
| CRLSet / OneCRL / CRLite push | **daily** | academic (ibid) |
| Entra CA policy & group changes | **up to 1 day** (2 h for some) | vendor (Microsoft) |
| Entra critical-event revocation | "near real time", **up to 15 min** | vendor (Microsoft) |
| AWS IoT certificate deactivation | "**within a few minutes**" | vendor (AWS) |
| EMQX authn cache | **1 minute** default | vendor (EMQX) |
| `sshd` `RevokedKeys` | zero, at each auth attempt; **unbounded** for an open session | implementation docs |
| **Spec 041 as written** | **zero on every checked path; unbounded for an idle socket** | — |

Dmitri's existing stale-command sweep and presence reconciliation already
establish that a periodic backstop is idiomatic in this codebase. **A revocation
sweep on the same cadence would put Dmitri's worst case at "one sweep interval",
which beats AWS's "a few minutes" if the interval is under that.** That is a
future-work recommendation, not a blocker.

---

## Part 2 — the narrow engineering questions

### 2.1 `expire_on_commit`: settled, and it settles against the spec's stated reasoning

**The default is `True`.** Verified three ways in the installed SQLAlchemy 2.0.51,
not from a blog:

1. **Signature**, `.venv/lib/python3.12/site-packages/sqlalchemy/orm/session.py:1510`:
   `expire_on_commit: bool = True,` — and `:1774`, `self.expire_on_commit = expire_on_commit`.
2. **Docstring**, same file `:1615`, verbatim:
   > ":param expire_on_commit: Defaults to ``True``. When ``True``, all instances
   > will be fully expired after each :meth:`~.commit`, so that all
   > attribute/object access subsequent to a completed transaction will load from
   > the most recent database state."
   (published as
   https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.params.expire_on_commit)
3. **The implementation**, `SessionTransaction._remove_snapshot` — the commit-time
   hook — same file `:1136-1141`:
   ```python
   if not self.nested and self.session.expire_on_commit:
       for s in self.session.identity_map.all_states():
           s._expire(s.dict, self.session.identity_map._modified)
   ```
   Every state in the identity map, unconditionally, at the transaction boundary.

**SQLModel does not change this.** `sqlmodel/orm/session.py` (SQLModel 0.0.39)
defines `class Session(_Session)` whose only additions are typed `exec()` overloads
and a deprecation shim on `execute()`; **there is no `__init__` override**, so
`Session(get_engine())` in `backend/src/api/db/session.py:23` inherits
`expire_on_commit=True`.

**And `Session.get()` really does skip SQL when not expired** — docstring in the
same installed file, verbatim:

> ":meth:`_orm.Session.get` is special in that it provides direct access to the
> identity map of the :class:`.Session`. If the given primary key identifier is
> present in the local identity map, the object is returned directly from this
> collection and no SQL is emitted, unless the object has been marked fully
> expired. If not present, a SELECT is performed in order to locate the object."

(https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.get)

#### Applying it to the two paths spec 041 changes

**Delivery path (`ARCHITECTURE.md` §3).** The spec says:

> "Why it costs no extra `SELECT`: `_claim_agent` already ran
> `session.get(Agent, agent_id)` on the **same** `session`, so the revocation read
> is served from the identity map."

**That is wrong.** Trace it in `backend/src/api/services/commands.py`:

```
_claim_agent()   :315  agent = session.get(Agent, agent_id)   → SELECT, Agent in identity map
                 :321  sweep_stale_commands(...)
                 :322  active_command_for(...)
                 :332  enqueue(...)  →  :68  session.commit()  ← expires EVERY instance
enqueue_for_agent:374  await deliver(session, command=command, now=now)
```

`enqueue()` commits. `_remove_snapshot` fires. The `Agent` instance is fully
expired. A later `session.get(Agent, agent_id)` in `deliver()` therefore takes the
*second* branch of the `Session.get()` docstring — "**a SELECT is emitted to
refresh the object as well as to ensure that the row is still present**" — and
also raises `ObjectDeletedError` if the row has since been deleted, which the
current text does not anticipate.

**Status-frame path (`ARCHITECTURE.md` §1).** Same defect:

> "`session.get` puts the row in the session identity map, so the later
> `touch_agent_last_seen` reuses it: still **one session and one `SELECT` per
> status frame**"

In `agent_ws._apply_status_frame.sync_work`, the sequence would be
`session.get(Agent)` → `apply_status(...)` → `touch_agent_last_seen(...)`.
`apply_status` ends its transaction on **both** branches —
`commands.py:157 session.commit()` on success, `commands.py:147 session.rollback()`
on a lost race — and rollback expires unconditionally, per SQLAlchemy's own
Session Basics ("**All objects not expunged are fully expired — this is regardless
of the `Session.expire_on_commit` setting**",
https://docs.sqlalchemy.org/en/20/orm/session_basics.html#rolling-back). So
`touch_agent_last_seen`'s `session.get(Agent, agent_id)` re-SELECTs. **Two
SELECTs per status frame, not one.**

**Verdict on the constraint "No second query on the hot path".** As written that
constraint is unsatisfiable by the design it accompanies, and an implementer who
takes it literally will be pushed toward `expire_on_commit=False` — which
`docs/research/ws-session-lifetime.md` §3 already warns is exactly wrong here.
The constraint should be restated as a *correctness* rule, not a query-count rule:
**reuse the one per-frame session; do not open a second session or a second
connection; accept the second SELECT, which is what makes the check fresh.**

The cost is genuinely small: a single-row primary-key lookup on an already
checked-out connection, inside a `run_in_threadpool` call that already exists. The
security value of that second SELECT is the entire point of the feature.

### 2.2 Is reading a stale cached authorization attribute ever acceptable?

**Yes, when the staleness is bounded and stated. No, when it is unbounded and
accidental.** That is the distinction every primary source draws.

**Open Policy Agent** is the clearest on the tradeoff. Its external-data page
(https://www.openpolicyagent.org/docs/external-data) frames the choice as
freshness versus availability:

> "**The lag between a data update and OPA having the update is the sum of the lag
> for an update between data replication and the central bundle server and the lag
> for an update between the central bundle server and OPA.**"

> "**External data is perfectly fresh. There is no lag between an update to the
> external data and when OPA sees that update**" — for the fetch-at-evaluation-time
> option.

and recommends the replicated/bundle approach "when the data is relatively
static", noting "the consistency of the data with the source of truth is worse
than the `input` case". OPA's bundle mechanism
(https://www.openpolicyagent.org/docs/management-bundles) is short-polling with
configurable `min_delay_seconds` / `max_delay_seconds`, with long polling offered
because "if the acceptable latency is low, then the polling frequency could add
unnecessary burden on the server and/or network". **Note the framing: latency is
a configured budget, not an accident.**

The same shape appears in every source above: EMQX's 1-minute authn cache TTL,
OCSP's 7-day cached validity, CAE's 15-minute propagation. All of them are *named
numbers*.

**An ORM identity map is none of those things.** It has no TTL, no invalidation
signal, no configured budget, and no place in the design document. If
`session.get(Agent, ...)` served a cached `revoked_at`, the staleness would be
"however long this session has been in a transaction" — a duration set by
unrelated code. That is CWE-367 (Time-of-check Time-of-use;
https://cwe.mitre.org/data/definitions/367.html), and
`docs/research/ws-session-lifetime.md` §5.2 already ranked this hazard on this
exact codebase.

**In practice, is spec 041 exposed?** No — twice over. (a) §2.1 shows every
intervening call ends its transaction, so the read is a fresh SELECT on both
paths. (b) Even if it were served from the map, the window would be a few
*microseconds* of one frame's transaction, in a Read Committed transaction that
began after the frame arrived. Compared with the 7-day and 15-minute windows the
literature considers workable, that is not a meaningful risk. **The correct
posture is therefore: the freshness is real and it is free, so do not trade it
away — do not set `expire_on_commit=False`, and do not restructure the code to
"save" a SELECT.**

The residual TOCTOU is not the identity map at all; it is that revocation could be
committed by another transaction *between* the check and the delivery `send_text`.
That window is unclosable without holding a lock across a network send, which
would be far worse. It is microseconds wide, and it is the same window every
system in Part 1 lives with.

### 2.3 Blocking DB I/O on the event loop

`docs/research/sync-vs-async-db-stack.md` already established the ground rules
(Caveat 2, §5): WS endpoints must be `async def` because Starlette does not
threadpool them, and sync DB work must go through
`starlette.concurrency.run_in_threadpool`, which is
`await anyio.to_thread.run_sync(...)` drawing on the default 40-token limiter.
`docs/research/ws-session-lifetime.md` §5.1(b) then ranked the violation as the
top hazard. **This section extends both rather than restating them: it names the
one place in spec 041 that would reintroduce the violation.**

The mechanism, from the Python standard library's own docs
(https://docs.python.org/3/library/asyncio-dev.html):

> "An event loop runs in a thread (typically the main thread) and executes all
> callbacks and Tasks in its thread. **While a Task is running in the event loop,
> no other Tasks can run in the same thread.** When a Task executes an `await`
> expression, the running Task gets suspended, and the event loop executes the
> next Task."

> "**Blocking (CPU-bound) code should not be called directly.** For example, if a
> function performs a CPU-intensive calculation for 1 second, all concurrent
> asyncio Tasks and IO operations would be delayed by 1 second. An executor can be
> used to run a task in a different thread… to avoid blocking the OS thread with
> the event loop."

Debug mode logs "Callbacks taking longer than 100 milliseconds" (same page), which
is a useful yardstick: a psycopg round trip through Supavisor is well inside that
for a warm connection, but a pool wait is `pool_timeout=30.0` s by default
(SQLAlchemy `QueuePool`, https://docs.sqlalchemy.org/en/20/core/pooling.html), and
30 s on the loop under ADR-011's single replica freezes **every** live agent
socket and every HTTP route.

**Where spec 041 is exposed.** The frame gate is safe: `agent_ws._apply_status_frame`
already wraps its whole `sync_work` in `run_in_threadpool` with a per-frame session
(`agent_ws.py:29-63`), which is exactly the shape `ws-session-lifetime.md` Option A
recommended, and the hello branch's `async_touch_unless_revoked` follows the same
`async_*` wrapper convention in `agent_presence`.

The **delivery gate is not**. `commands.deliver()` is `async def`
(`commands.py:269`) and runs on the event loop; its existing DB touches are all
`await run_in_threadpool(...)` (`:277`, `:294`, `:297`). `ARCHITECTURE.md` §3's
pseudocode is:

```
if socket is None or <agent revoked>:
```

If `<agent revoked>` is expanded inline as `agent_presence.agent_is_revoked(session, agent_id)`
— a plain sync function per the spec's own signature table, `(session, agent_id) -> bool`
— that is **a synchronous DB round trip evaluated directly on the event loop**,
inside the one boolean expression in the file that is not already offloaded. It
would be the single blocking DB call in the whole delivery path, in the module the
prior research notes specifically warned about.

It must be `await run_in_threadpool(agent_is_revoked, session, agent_id)`, or
folded into an existing offloaded call, and evaluated *before* the `or` so the
short-circuit does not hide it. Note that `run_in_threadpool` also satisfies
SQLAlchemy's concurrency rule — "Session per thread" — only because the delivery
session is used sequentially, never concurrently
(https://docs.sqlalchemy.org/en/20/orm/session_basics.html#is-the-session-thread-safe-is-asyncsession-safe-to-share-in-concurrent-tasks).

**Fail-closed, per §1.3.** If that read raises (pool timeout, dropped connection),
the exception must not be swallowed into "not revoked". Letting it propagate is
correct: `enqueue_for_agent` fails the operator's request rather than delivering a
command to a device whose revocation status could not be established. That is the
hard-fail policy Let's Revoke lists as criterion 3 and that Liu et al. showed the
browsers abandoned to their cost.

---

## What this means for spec 041

**1. The research endorses the design.** Revocation-on-use is a named, standard
pattern (*pull-based*, on-demand validation), it is what OpenSSH and OCSP do, and
NIST SP 800-207 tenet 6 explicitly lists "new resource requested" and "resource
modification" as legitimate re-authorization triggers. Spec 041's window on every
checked path is smaller than any deployed system found in Part 1, including AWS
IoT's promised "few minutes". **No design change is warranted. Proceed.**

**2. The out-of-scope caveat is stronger than it reads, and should say so.** The
current wording is defensive ("Nothing in the system currently *writes*
revocation, so there is no event to hook"). The defensible version is a positive
claim with citations: this is pull-based revocation, the dominant deployed class;
`sshd` cannot terminate a live session on key revocation either; EMQX shipped
banning without kicking live sessions and added the kick later
(https://github.com/emqx/emqx/pull/9367). *Recommended edit to `TRUTH.md`, "Out of
scope (v1)" — not applied.*

**3. The close code needs no change.** `4001 revoked` in the private range
(4000-4999) with "stay down" semantics is consistent with MQTT 5.0's use of a
distinct DISCONNECT reason code (`0x87` Not authorized) to convey *why* an
authenticated session was torn down. Nothing in the research argues for a
different value or for reusing `4000`.

**4. Consider naming a bounded window for the idle case — as future work, not in
this spec.** The only real gap is a revoked agent that never speaks and is never
sent a command. Every source that takes revocation seriously bounds this with a
*number*: 15 minutes (Entra), "a few minutes" (AWS IoT), 1 minute (EMQX authn
cache), 1 day (CRLite/OneCRL push). Dmitri already runs periodic sweeps
(`sweep_stale_commands`, presence reconciliation). *Recommended addition to
`TRUTH.md` "Out of scope" or a follow-up issue: state the idle window as
"unbounded in v1; a periodic sweep would bound it at one sweep interval" — not
applied.*

**5. `expire_on_commit` is settled, and two spec sentences are wrong.** Default is
`True` (SQLAlchemy 2.0.51 source `orm/session.py:1510`, `:1615`, `:1136-1141`);
SQLModel 0.0.39 does not override it; `Session(get_engine())` inherits it.
Therefore:

- **`ARCHITECTURE.md` §3** — "Why it costs no extra `SELECT`: `_claim_agent`
  already ran `session.get(Agent, agent_id)` on the **same** `session`, so the
  revocation read is served from the identity map." **Delete this justification.**
  `enqueue()` commits at `commands.py:68`, which fully expires the `Agent`; the
  read in `deliver()` emits a fresh SELECT (and can raise `ObjectDeletedError` if
  the row was deleted). Replace with: *the read reuses the same session and
  connection, and costs one primary-key SELECT — that SELECT is what makes the
  check fresh, and is the point.*
- **`ARCHITECTURE.md` §1** — "`session.get` puts the row in the session identity
  map, so the later `touch_agent_last_seen` reuses it: still one session and one
  `SELECT` per status frame." **Same correction.** `apply_status` commits
  (`commands.py:157`) or rolls back (`:147`) in between; rollback expires
  regardless of `expire_on_commit`. It is two SELECTs.
- **`ARCHITECTURE.md` "Constraints"** — "No second query on the hot path. Any
  implementation that adds a DB round trip to a well-formed `hello` or `status`
  frame is wrong — reuse the session and the identity map." **Restate.** As
  written it is unsatisfiable and it points an implementer at
  `expire_on_commit=False`, which `docs/research/ws-session-lifetime.md` §3
  identifies as the wrong move on this route. Proposed replacement: *reuse the
  one per-frame session and its connection; do not open a second session, a
  second connection, or a second threadpool hop. One extra primary-key SELECT is
  expected and required — do not set `expire_on_commit=False` to avoid it.*

**6. One concrete implementation hazard to add to the spec.**
`commands.deliver()` is `async def` on the event loop and every existing DB touch
in it goes through `run_in_threadpool`. The §3 pseudocode's inline
`<agent revoked>` would be the only blocking DB call in that function on the loop
thread — the precise defect `docs/research/sync-vs-async-db-stack.md` Caveat 2 and
`ws-session-lifetime.md` §5.1(b) both warn about, and under ADR-011's single
replica a pool wait there stalls every live agent socket. *Recommended addition to
`ARCHITECTURE.md` §3 and to Constraints: the delivery-path revocation read MUST be
`await run_in_threadpool(...)`, evaluated before the `or` so short-circuiting
cannot hide it — not applied.*

**7. Add a fail-closed rule.** The single clearest transferable lesson from the
PKI measurement literature is that soft-fail silently disables revocation
checking (Liu et al., IMC 2015, §2.2). If the revocation read raises, the frame
must not be processed and the command must not be delivered; the error must
propagate. *Recommended addition to `ARCHITECTURE.md` Constraints — not applied.*

None of the above changes the file/naming table, the close code, the test matrix,
or the gates.

---

## Sources

**Normative** (standards bodies, RFCs, library docs and installed source):

- NIST SP 800-207, *Zero Trust Architecture* — tenets §2.1, PE/PA/PEP §3.1, PA duties §3.3: https://doi.org/10.6028/NIST.SP.800-207 (PDF: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-207.pdf)
- OpenID Shared Signals Framework 1.0 (final) — transmitters/receivers, push (RFC 8935) and poll (RFC 8936) delivery: https://openid.net/specs/openid-sharedsignals-framework-1_0-final.html
- OpenID Continuous Access Evaluation Profile 1.0 (final) — `session-revoked` event, `event_timestamp`: https://openid.net/specs/openid-caep-1_0-final.html
- RFC 7009, *OAuth 2.0 Token Revocation* §2.1 — propagation delay, unexpected invalidation: https://www.rfc-editor.org/rfc/rfc7009
- OASIS MQTT 5.0 — AUTH packet §3.15, re-authentication §4.12.1, reason codes Table 2-6: https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html
- OpenSSH `sshd_config(5)` — `RevokedKeys`: https://man.openbsd.org/sshd_config#RevokedKeys
- SQLAlchemy 2.0 Session API — `expire_on_commit`, `Session.get`: https://docs.sqlalchemy.org/en/20/orm/session_api.html
- SQLAlchemy 2.0 Session Basics — rolling back expires regardless of `expire_on_commit`; thread-safety: https://docs.sqlalchemy.org/en/20/orm/session_basics.html
- SQLAlchemy 2.0 Connection Pooling — `pool_timeout` 30 s: https://docs.sqlalchemy.org/en/20/core/pooling.html
- **Installed source**, SQLAlchemy 2.0.51 `sqlalchemy/orm/session.py` lines 1136-1141 (`_remove_snapshot`), 1510 and 1774 (`expire_on_commit=True`), 1615 (docstring), `Session.get` docstring; SQLModel 0.0.39 `sqlmodel/orm/session.py` (no `__init__` override)
- Python asyncio developer guide — event loop single-task execution, "Running Blocking Code", 100 ms slow-callback threshold: https://docs.python.org/3/library/asyncio-dev.html
- CWE-367, Time-of-check Time-of-use: https://cwe.mitre.org/data/definitions/367.html

**Academic** (peer-reviewed, venue + year):

- Yabing Liu, Will Tome, Liang Zhang, David Choffnes, Dave Levin, Bruce Maggs, Alan Mislove, Aaron Schulman, Christo Wilson. *An End-to-End Measurement of Certificate Revocation in the Web's PKI.* **ACM IMC 2015.** https://dl.acm.org/doi/10.1145/2815675.2815685 — PDF read: https://www.cs.umd.edu/~dml/papers/revocations_imc15.pdf
- Trevor Smith, Luke Dickinson, Kent Seamons. *Let's Revoke: Scalable Global Certificate Revocation.* **NDSS 2020.** DOI 10.14722/ndss.2020.24084. PDF read: https://www.ndss-symposium.org/wp-content/uploads/2020/02/24084-paper.pdf
- David D. Redell. *Naming and Protection in Extendible Operating Systems.* MIT/LCS/TR-140 (MAC TR-140), **1974.** Bibliographic record verified; PDF not read: https://dspace.mit.edu/bitstream/handle/1721.1/149438/MIT-LCS-TR-140.pdf and https://apps.dtic.mil/sti/pdfs/ADA001721.pdf

**Vendor** (documentation and blogs — not peer-reviewed, and vendors describe
their own products):

- Microsoft Entra, *Continuous access evaluation*: https://learn.microsoft.com/en-us/entra/identity/conditional-access/concept-continuous-access-evaluation
- Google Cloud blog, *Re-thinking federated identity with the Continuous Access Evaluation Protocol*: https://cloud.google.com/blog/products/identity-security/re-thinking-federated-identity-with-the-continuous-access-evaluation-protocol
- AWS CLI reference, `iot update-certificate`: https://docs.aws.amazon.com/cli/latest/reference/iot/update-certificate.html
- AWS IoT Core developer guide, *Activate or deactivate a client certificate*: https://docs.aws.amazon.com/iot/latest/developerguide/activate-or-deactivate-device-cert.html
- AWS what's-new, *IoT Core introduces DeleteConnection API* (Aug 2025): https://aws.amazon.com/about-aws/whats-new/2025/08/aws-iot-core-delete-connection
- Azure IoT Hub, *Understand the identity registry*: https://learn.microsoft.com/en-us/azure/iot-hub/iot-hub-devguide-identity-registry ; *how-to-disable-enable-device*: https://github.com/MicrosoftDocs/azure-docs/blob/main/articles/iot-hub/how-to-disable-enable-device.md
- EMQX, *Authentication* (cache TTL 1 min): https://docs.emqx.com/en/emqx/latest/access-control/authn/authn.html ; *Banned Clients*: https://docs.emqx.com/en/emqx/latest/access-control/blacklist.html
- EMQX PR #9367, "feat(banned): kick session when it is banned by clientid" (project source, not documentation): https://github.com/emqx/emqx/pull/9367
- Eclipse Mosquitto, `mosquitto(8)`: https://mosquitto.org/man/mosquitto-8.html
- Open Policy Agent, *External Data*: https://www.openpolicyagent.org/docs/external-data ; *Bundles*: https://www.openpolicyagent.org/docs/management-bundles

**Internal** (this repo, secondary):

- `docs/research/sync-vs-async-db-stack.md` §5 Caveat 2 — WS handlers must be `async def`; sync DB via `run_in_threadpool`
- `docs/research/ws-session-lifetime.md` §3, §5.1, §5.2, §5.4 — identity-map staleness, blocking DB on the loop, and the original logging of this revocation gap
- `docs/adr/ADR-011-pi-command-channel.md` §1-§4; `specs/041-revoked-agent-live-socket-close/{TRUTH,ARCHITECTURE}.md`
- `backend/src/api/{db/session.py,services/commands.py,services/agent_ws.py,services/agent_presence.py}`

## Explicitly not verified

- **MQTT 5.0 §4.12.1 exact wording.** The fetch returned a paraphrase plus a
  partial reproduction, not the literal section text. The existence of the AUTH
  packet (§3.15), reason code `0x19` (Re-authenticate) and `0x87` (Not authorized,
  valid on DISCONNECT) is confirmed; the sentence-level quotes are not. Re-read
  the OASIS PDF before quoting §4.12.1 anywhere normative.
- **Azure IoT Hub behaviour on disabling a device with an open connection.** No
  page fetched states whether the existing connection is torn down, or how fast.
  Do not cite Azure as a precedent in either direction.
- **EMQX ban semantics per ban type in the shipped product.** The docs say regex
  bans do not apply to already-connected clients and are silent on client-ID /
  username / IP bans; the "kick on ban" behaviour is sourced from a PR title and
  description, not release documentation.
- **Mosquitto behaviour on credential change for connected clients.** The
  `mosquitto(8)` man page does not address it.
- **Google Cloud's *product* behaviour for continuous access evaluation.** Only
  the CAEP design blog post was read. No Google product documentation stating an
  enforcement latency was located.
- **Redell & Fabry, "Selective Revocation of Capabilities" (IRIA Workshop on
  Protection in Operating Systems, 1974).** Appeared in search results; the
  citation was **not** independently confirmed and no copy was read. Treat as
  unverified. Redell's MIT/LCS/TR-140 dissertation is bibliographically confirmed
  but was likewise not read — no quotations are taken from it.
- **Whether `commands.deliver()`'s revocation read can in fact raise
  `ObjectDeletedError` in production.** The code path follows from the
  `Session.get()` docstring; whether an `agents` row can be deleted between
  `_claim_agent` and `deliver` in this deployment was not established.
- **Any measurement of Dmitri's own per-frame SELECT cost.** The "cost is small"
  claim in §2.1 is reasoning from a single-row primary-key lookup on an
  already-checked-out connection, not a benchmark.
