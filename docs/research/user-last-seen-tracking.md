# Research: tracking a per-user "last seen / last active" timestamp

> **Scope.** Dmitri backend (Python 3.11+, FastAPI, SQLModel/Postgres on
> Supabase). We want a per-user activity timestamp to render in the admin
> **Users** table (and possibly sort on it). Auth context is already decided:
> 15-minute access tokens, rotating 7-day refresh tokens with strict reuse
> detection (`refresh_tokens` in `backend/src/api/models/session.py`,
> `/api/v1/auth/refresh` in `backend/src/api/routers/auth.py`). Realistic
> scale is a **single-org pilot: a handful of users**.
>
> Questions: is an `UPDATE users` per refresh acceptable; where to stamp;
> what to call the column; the GDPR/ICO angle of showing one user's activity
> to their org admin; and the Postgres storage behaviour (HOT, bloat,
> autovacuum, indexing).
>
> Primary sources only: PostgreSQL official docs, the actual source of
> Django `django.contrib.auth`, Devise (`trackable` / `timeoutable`), and
> Supabase's own `supabase/auth` (GoTrue); OWASP Session Management Cheat
> Sheet; NIST SP 800-63B; GDPR text (EUR-Lex) and UK ICO monitoring-workers
> guidance. Fetched 2026-08-08.

---

## TL;DR verdict

- **Yes, `UPDATE users SET last_seen_at` on every refresh is fine at our
  scale — and would still be fine two orders of magnitude up.** Five users
  refreshing every 15 minutes is **~20 updates/hour**, ~480/day. Postgres
  autovacuum on a table that size triggers at **50 + 0.2 × rows** dead
  tuples (§5.3); the table never leaves single-digit pages.
- **The single decision that actually matters is the index.** PostgreSQL:
  HOT applies only when "the update does not modify any columns referenced
  by the table's indexes", and "Indexes can also prevent the creation of
  heap-only tuples" (§5.1, §5.5). **Indexing `last_seen_at` converts every
  stamp from a cheap in-page HOT update into a heap write + index write +
  index bloat** — and at five rows the planner will seq-scan and sort
  anyway. **Do not index it.**
- **Stamp on the refresh path, not in middleware.** This is what every
  framework we read actually does. **No mainstream auth stack writes a
  per-request activity timestamp to the user row** — Django writes
  `last_login` once per login (§3.1), Devise's `:trackable` writes only on
  sign-in and its `:timeoutable` keeps last-request time **in the session,
  not the database** (`required_fields` is literally `[]`, §3.2), and
  Supabase GoTrue keeps `users.last_sign_in_at` for sign-in but puts
  activity on `sessions.refreshed_at` at **refresh granularity** (§3.3).
- **Naming: `last_seen_at`.** Not because a framework says so — none of
  them use that name — but because this repo already uses `last_seen_at`
  for exactly this concept on `agents` and `hosts` (§3.4). Keep the
  semantics honest: it means "last refresh", i.e. accurate to ~15 minutes.
- **Privacy: yes, this is noteworthy, and no, it is not scary.** Showing an
  employee's activity to their employer's admin is worker monitoring under
  UK GDPR. The ICO names "checking the times workers log onto the computer
  system" as its *example of the less intrusive alternative* to endorse
  (§4.1) — so we are at the mild end. Requirements that still bite:
  a documented lawful basis, transparency (workers "must" be informed), and
  data minimisation (§4).
- **Do not build:** Redis write-behind, a batching buffer, a separate
  `user_activity` table, a lowered `fillfactor`, or per-request middleware.
  Every one of those is a mitigation for a write rate we are ~4 orders of
  magnitude below (§1.4).

---

## Findings

### 1. Write amplification: what an `UPDATE` per refresh actually costs

#### 1.1 The mechanical cost of one `UPDATE`

PostgreSQL does not update rows in place. From *Routine Vacuuming*:

> "In PostgreSQL, an `UPDATE` or `DELETE` of a row does not immediately
> remove the old version of the row. This approach is necessary to gain the
> benefits of multiversion concurrency control (MVCC): the row version must
> not be deleted while it is still potentially visible to other
> transactions."
> — https://www.postgresql.org/docs/current/routine-vacuuming.html

So each stamp costs: one new heap tuple, one dead tuple left behind, WAL for
the change, and — if any index covers the changed column — one index entry
per index (§5.1).

WAL cost is not uniform. `full_page_writes` (default `on`):

> "When this parameter is on, the PostgreSQL server writes the entire content
> of each disk page to WAL during the first modification of that page after a
> checkpoint… Storing the full page image guarantees that the page can be
> correctly restored, but at the price of increasing the amount of data that
> must be written to WAL."
> — https://www.postgresql.org/docs/current/runtime-config-wal.html

This is the real amplification term at scale: a wide fan-out of updates
across many pages generates one 8 kB full-page image *per page per
checkpoint*. For a `users` table whose rows all live on **one or two pages**,
this is one FPI per checkpoint cycle regardless of how many times we stamp.

#### 1.2 The numbers at Dmitri's scale

5 active users × 1 refresh / 15 min = **20 updates/hour**, ~480/day,
~175,000/year. Autovacuum's trigger for a 5-row table is
`50 + 0.2 × 5 ≈ 51` dead tuples (§5.3), so autovacuum fires roughly every
2–3 hours and the table returns to steady state. There is no bloat problem
to solve here; there is barely a table.

#### 1.3 The standard mitigations, and what each actually buys

| Mitigation | Mechanism (primary-source backed?) | What it buys | When it earns its keep |
|---|---|---|---|
| **Coalesce with a conditional `WHERE`** | Yes — the write is *skipped* only if the row is not matched; see §1.5 | Turns N stamps/interval into ≤1 | Middleware stamping, or refresh intervals under ~1 min |
| **Write-behind buffer / Redis** | **No primary source prescribes this.** Nearest documented analogue is Django's `cached_db` session backend, which is *write-through* — "session writes are applied to both the database and cache, in that order" — so it does **not** remove the DB write. Django's pure `cache` backend does, but Django itself flags the cost: "you will have to consider what happens when cache data is evicted." (https://docs.djangoproject.com/en/stable/topics/http/sessions/) | Removes the synchronous DB write from the request path | Thousands of writes/sec, and only if losing recent timestamps on a cache eviction is acceptable |
| **Separate narrow table** (`user_activity(user_id, last_seen_at)`) | Inference from the HOT + `fillfactor` docs, not a documented recommendation | Narrower tuples → more versions per page → higher HOT hit rate; lets you set `fillfactor` and index it without touching `users` | When `users` is wide (large `password_hash`, JSON columns) **and** the write rate keeps the table permanently dirty |
| **Lower `fillfactor`** | Yes — "For tables whose entries are never updated, complete packing is the best choice, but in heavily updated tables smaller fillfactors are appropriate" (https://www.postgresql.org/docs/current/sql-createtable.html); default is **100** | Reserves in-page space so HOT succeeds more often | "Heavily updated" — not 20 updates/hour |
| **Don't store it at all; derive it** | See §2.3 | Zero writes | Always worth considering first |

#### 1.4 Where the crossover actually is

Working the same autovacuum arithmetic upward: at **10,000** users refreshing
every 15 minutes you get ~40,000 updates/hour (~11/sec), against a threshold
of `50 + 0.2 × 10,000 = 2,050` dead tuples — autovacuum every ~3 minutes,
permanently. That is the regime where the narrow-table split and `fillfactor`
tuning start to pay. Dmitri's pilot is roughly **three orders of magnitude**
below it. Anything from the table above other than "don't index it" is
premature here.

#### 1.5 A correctness note on coalescing

The coalescing idiom is a conditional `UPDATE`:

```sql
UPDATE users
   SET last_seen_at = now()
 WHERE id = :user_id
   AND (last_seen_at IS NULL OR last_seen_at < now() - interval '5 minutes');
```

The saving comes entirely from the `WHERE` clause not matching. **A
same-value `UPDATE` is not free**: the docs describe `UPDATE` as producing a
new row version unconditionally, and no PostgreSQL documentation describes an
elision when the new values equal the old. Assume `SET last_seen_at =
last_seen_at` still writes a dead tuple. (Widely repeated to the contrary;
unsupported by any primary source we found.)

### 2. Where to stamp: refresh path vs. per-request middleware

#### 2.1 What the frameworks do

Every auth stack examined stamps on an **authentication event**, never on
every request:

- **Django** — `update_last_login` is wired to the `user_logged_in` signal
  (`django/contrib/auth/apps.py`), so it fires once per login.
- **Devise** — `update_tracked_fields!` runs from a Warden hook that is
  explicitly scoped away from session fetches: "This is only triggered when
  the user is explicitly set (with `set_user`) and on authentication.
  Retrieving the user from session (`:fetch`) does not trigger it."
  — https://github.com/heartcombo/devise/blob/main/lib/devise/hooks/trackable.rb
- **Supabase GoTrue** — `UpdateOnlyRefreshInfo` writes `refreshed_at`,
  `user_agent`, `ip` on the **session** row, on token refresh.

Django even makes the general point for its *session* store, where the same
tradeoff appears. `SESSION_SAVE_EVERY_REQUEST` **defaults to `False`**:

> "By default, Django only saves to the session database when the session has
> been modified… To change this default behavior, set the
> `SESSION_SAVE_EVERY_REQUEST` setting to `True`. When set to `True`, Django
> will save the session to the database on every single request."
> — https://docs.djangoproject.com/en/stable/topics/http/sessions/

Per-request DB writes are the opt-in, not the default.

#### 2.2 The tradeoff, stated plainly

| | Refresh path only | Middleware on every authenticated request |
|---|---|---|
| **Accuracy** | Bounded by the refresh interval: **≤15 min stale** for us | Sub-second |
| **Writes** | 4/user/hour, fixed and predictable | 1 per request unless coalesced (§1.5) |
| **Complexity** | One line in `refresh_session()` | A middleware, a coalescing guard, and a session/transaction lifecycle decision on a path that currently may not touch the DB at all |
| **Failure blast radius** | Refresh already writes (rotation) — same transaction, no new failure mode | Every request now depends on a write; a slow write slows every endpoint |
| **Correct semantics** | "Last time this user's client was alive" | "Last request" |

There is a further gotcha specific to us: a middleware write on *every*
authenticated request would put a DB write on read-only endpoints that
currently need no write transaction, and `docs/research/ws-session-lifetime.md`
already documents this repo's sensitivity to transaction scope on hot paths.

#### 2.3 Accuracy is bounded by the auth design anyway

A 15-minute access token means an idle-but-open client refreshes every 15
minutes; a closed client stops refreshing. So refresh-path stamping already
answers "is this person still using the product?" to a 15-minute resolution,
which is finer than an admin Users table can meaningfully display. NIST's
own session-management thresholds work at this granularity: AAL2 requires
reauthentication "following any period of inactivity lasting 30 minutes or
longer" (https://pages.nist.gov/800-63-3/sp800-63b.html) — and Supabase
GoTrue implements exactly that check against `refreshed_at`, i.e. inactivity
measured at refresh granularity (`CheckValidity` →
`config.InactivityTimeout` vs `s.LastRefreshedAt(...)`).

**The zero-write option.** Dmitri already `INSERT`s a `refresh_tokens` row on
every rotation, with `created_at` and `rotated_at`. `MAX(created_at)` over a
user's refresh tokens *is* a last-seen signal with no new write at all. It
costs a subquery/join on the Users list and breaks if we ever prune the
table — but it is worth naming, because "the cheapest write is the one you
don't do."

### 3. Naming and modelling: what the frameworks actually record

#### 3.1 Django — `last_login`, login only

`AbstractBaseUser` (`django/contrib/auth/base_user.py`):

```python
last_login = models.DateTimeField(_("last login"), blank=True, null=True)
```

The docs define it as "A datetime of the user's last login."
(https://docs.djangoproject.com/en/stable/ref/contrib/auth/). It is written
by a signal receiver in `django/contrib/auth/models.py`:

```python
def update_last_login(sender, user, **kwargs):
    """
    A signal receiver which updates the last_login date for
    the user logging in.
    """
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
```

wired in `AuthConfig.ready()` as
`user_logged_in.connect(update_last_login, dispatch_uid="update_last_login")`.
Note `update_fields=["last_login"]` — Django narrows the `UPDATE` to the one
column, which is precisely what keeps it HOT-eligible (§5.1).

**Django has no activity column at all.** There is no `last_active`,
`last_seen`, or equivalent in `django.contrib.auth`.

#### 3.2 Devise — five sign-in columns, and activity deliberately *not* in the DB

`lib/devise/models/trackable.rb` documents its columns verbatim:

> ```
> # * sign_in_count      - Increased every time a sign in is made (by form, openid, oauth)
> # * current_sign_in_at - A timestamp updated when the user signs in
> # * last_sign_in_at    - Holds the timestamp of the previous sign in
> # * current_sign_in_ip - The remote ip updated when the user sign in
> # * last_sign_in_ip    - Holds the remote ip of the previous sign in
> ```

Note the semantics, which are commonly misread: `last_sign_in_at` is the
**previous** sign-in, not the most recent one. `update_tracked_fields` sets
`self.last_sign_in_at = old_current || new_current` then
`self.current_sign_in_at = new_current`. If you want "when did this user last
authenticate", the Devise column is **`current_sign_in_at`**.

The decisive data point is `:timeoutable`, which is the module that *does*
care about activity:

```ruby
def self.required_fields(klass)
  []
end
```

It requires **no database columns**. Its hook keeps last-request time in the
session store:
`warden.session(scope)['last_request_at'] = Time.now.utc.to_i`
(https://github.com/heartcombo/devise/blob/main/lib/devise/hooks/timeoutable.rb).
Devise's authors had exactly our problem — per-request activity tracking —
and explicitly chose not to put it in the database.

#### 3.3 Supabase GoTrue — split across user and session

Since we run on Supabase, its own auth service is the closest analogue:

- `users.last_sign_in_at` (`internal/models/user.go`), written by
  `UpdateLastSignInAt` → `tx.UpdateOnly(u, "last_sign_in_at")`.
- `sessions.refreshed_at`, plus `user_agent` and `ip`
  (`internal/models/sessions.go`), written by `UpdateOnlyRefreshInfo` →
  `tx.UpdateOnly(s, "refreshed_at", "user_agent", "ip")`.

So GoTrue **does** keep login and activity as separate columns, on separate
tables, with the churny one on the per-session row rather than the user row.
It also uses `UpdateOnly` in both places — same single-column narrowing as
Django.

#### 3.4 So what do we call it?

| Candidate | Framework precedent | Verdict |
|---|---|---|
| `last_login_at` | Django `last_login`, Devise `current_sign_in_at`, GoTrue `last_sign_in_at` | Correct name **only if** we stamp at login and never after. Then it is nearly useless for an admin "is this person using it?" column — it can be weeks stale for a continuously-active user. |
| `last_active_at` | None found | Implies per-request accuracy we will not have. Misleading against a refresh-path write. |
| `last_seen_at` | **None of the three auth frameworks.** But it is this repo's existing house term: `agents.last_seen_at` (`backend/src/api/models/command.py`), `HostRecord.last_seen_at`, and the `HostSortBy` API enum already exposes `"last_seen_at"`. | **Pick this.** Internal consistency beats external precedent when external precedent is split three ways. |

**Separate columns or collapsed?** All three frameworks keep them separate,
and none collapses them — so "collapse into one column" has **no framework
precedent**, and anyone claiming it is standard is wrong. That said, the
frameworks separate them because they record *different events* (a login,
vs. session activity), not because a single column is unsound. For Dmitri,
one `last_seen_at` stamped at both login and refresh answers the admin's
actual question with one column. Adding a second `last_login_at` later is a
cheap, non-breaking migration if a real use case appears — **this is our
inference, not a sourced recommendation.**

### 4. Privacy: showing a user's activity to their org's admin

⚠️ Not legal advice. Sourced from the GDPR text and ICO guidance; a real
lawful-basis determination belongs with whoever owns Dmitri's DPA.

#### 4.1 Is this "monitoring workers"? Yes — and the ICO treats it as the mild case

The ICO defines the scope broadly:

> "We use the term 'monitoring workers' to mean any form of monitoring of
> people who carry out work on your behalf."
> — https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/employment/monitoring-workers/data-protection-and-monitoring-workers/

A last-seen timestamp surfaced to an employer's admin is inside that. But
note where the ICO puts login timestamps on its own intrusiveness scale. In
its worked example of *disproportionate* monitoring (webcam images to check
start times), the remedy it endorses is:

> "The employer can achieve the same purpose by checking the times workers
> log onto the computer system, and then give workers the opportunity to
> explain any discrepancies."

Login/last-seen timestamps are the ICO's own example of the **less intrusive
alternative**. That is a materially better starting position than most
"monitoring" features.

#### 4.2 What is still required

- **A lawful basis.** "To lawfully collect and process information from
  monitoring workers, you must identify a lawful basis." **Legitimate
  interests** (GDPR Art. 6(1)(f): processing "necessary for the purposes of
  the legitimate interests pursued by the controller or by a third party,
  except where such interests are overridden by the interests or fundamental
  rights and freedoms of the data subject" —
  https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A32016R0679)
  is the realistic candidate, documented via the ICO's three-part test:
  "Purpose test… Necessity test… Balancing test". **Consent is not
  available** here: "consent is not usually appropriate in the employment
  context, due to the imbalance of power between you and your workers."
  The ICO's caveat is the one to watch: legitimate interests "may not be the
  most appropriate lawful basis if… you are monitoring in ways workers do
  not understand and would not reasonably expect." A last-active column in a
  product's own admin panel is squarely within reasonable expectation.
- **Transparency — this is the operative obligation.** "Apart from in very
  exceptional circumstances where covert monitoring is justified, you must
  inform workers about any monitoring." GDPR Art. 13 requires the purposes of
  processing to be given at collection time. Practically: one line in the
  privacy notice / in-product, e.g. *"Your organisation's administrators can
  see when you last used Dmitri."* Silently shipping it is the failure mode.
- **Purpose limitation.** "You must document why you are monitoring workers
  and what you intend to do with the information you collect." And: "you
  should not monitor workers 'just in case'." If the purpose is seat
  management / offboarding stale accounts, write that down.
- **Data minimisation.** Art. 5(1)(c): personal data shall be "adequate,
  relevant and limited to what is necessary for the purposes for which they
  are processed." ICO: "you must not collect more information than is
  necessary, just in case it might prove useful to you in the future." This
  is the direct argument against also storing IP and user-agent per refresh
  the way Devise and GoTrue do — we have no stated purpose for those.
- **Storage limitation.** Art. 5(1)(e): kept "for no longer than necessary."
  A single overwritten timestamp satisfies this trivially; an append-only
  activity *log* would need a retention policy. Another reason to prefer one
  column over a history table.
- **DPIA.** Not mandatory on the face of it: the ICO's high-risk examples are
  biometrics, keystroke monitoring, monitoring that may cause financial loss,
  and profiling/special-category-based access decisions — a last-seen column
  is none of these. But the ICO adds: "You should carry out a DPIA even if
  there is no specific high risk… If you decide to proceed without carrying
  out a DPIA, you should document your decision." **The cheap correct move is
  a short documented decision, not a full DPIA.**

#### 4.3 Does coarse granularity change the analysis?

Partly, and less than people assume.

- **Coarse granularity does not change the lawful basis or the transparency
  duty.** A date is still personal data; monitoring is still monitoring. The
  ICO gives no threshold below which its guidance stops applying.
- **It does help the necessity and balancing tests, and data minimisation.**
  If the admin's purpose is "is this seat still in use", a *date* is adequate
  and a *second* is more than necessary — which is the Art. 5(1)(c) argument
  in one line. The ICO also warns about "function creep, where information is
  used for wider purposes than the original intention": a second-precision
  timestamp invites "were they working at 23:40?" in a way a date does not.
- **No primary source states that a date is acceptable and a second is
  not.** That inference is ours, from Art. 5(1)(c) plus the ICO's
  proportionality framing. Anyone presenting a specific granularity
  threshold as a legal rule is inventing it.

**Practical resolution:** store full precision (you cannot recover it later,
and it is needed for correct sorting and for support/debugging), but
**render coarsely** in the admin table — "Today", "3 days ago", or a date.
Precision lives in the database; the human-facing surface is the one the ICO
cares about.

#### 4.4 Controller vs. processor

In B2B, the customer org is typically the controller for employment
monitoring and Dmitri is the processor — meaning the lawful-basis and
worker-transparency obligations largely sit with **the customer**, while
ours is to describe the feature accurately in the DPA/sub-processor
documentation so the customer *can* discharge them. That allocation depends
on the actual contracts and is not something the ICO guidance settles for
us. Flagging it as the question to route to whoever owns Dmitri's DPA, not
as a settled conclusion.

### 5. Postgres specifics

#### 5.1 HOT: the whole game is the index

> "This optimization is possible when:
> - The update does not modify any columns referenced by the table's indexes,
>   not including summarizing indexes. The only summarizing index method in
>   the core PostgreSQL distribution is BRIN.
> - There is sufficient free space on the page containing the old row for the
>   updated row."
>
> "In such cases, heap-only tuples provide two optimizations:
> - New index entries are not needed to represent updated rows…
> - When a row is updated multiple times, row versions other than the oldest
>   and the newest can be **completely removed during normal operation,
>   including `SELECT`s, instead of requiring periodic vacuum operations**."
> — https://www.postgresql.org/docs/current/storage-hot.html

That second bullet is the important one: **a HOT-updated hot row largely
cleans up after itself**, without waiting for autovacuum. It is precisely the
behaviour a `last_seen_at` column wants.

`users` currently has these indexes (`backend/src/api/models/identity.py`):
the `id` primary key and `ix_users_email` on `lower(email)`. Neither
references `last_seen_at`, so a `last_seen_at`-only `UPDATE` is HOT-eligible
today. **Adding an index on `last_seen_at` destroys that** for every stamp.

#### 5.2 `fillfactor`

> "The `fillfactor` for a table is a percentage between 10 and 100. 100
> (complete packing) is the default… This gives `UPDATE` a chance to place
> the updated copy of a row on the same page as the original… and makes
> heap-only tuple updates more likely… For tables whose entries are never
> updated, complete packing is the best choice, but in heavily updated tables
> smaller fillfactors are appropriate."
> — https://www.postgresql.org/docs/current/sql-createtable.html

The HOT page adds that leaving `fillfactor` alone is usually fine: "If you
don't, HOT updates will still happen because new rows will naturally migrate
to new pages and existing pages with sufficient free space for new row
versions." **Leave it at 100.** Twenty updates an hour is not "heavily
updated", and a five-row table has an almost empty page to work with anyway.

#### 5.3 Autovacuum on a small hot table

> vacuum threshold = Minimum(vacuum max threshold, vacuum base threshold +
> vacuum scale factor × number of tuples)
> — https://www.postgresql.org/docs/current/routine-vacuuming.html

Defaults (https://www.postgresql.org/docs/current/runtime-config-autovacuum.html):

| Parameter | Default |
|---|---|
| `autovacuum_vacuum_threshold` | 50 tuples |
| `autovacuum_vacuum_scale_factor` | 0.2 |
| `autovacuum_vacuum_max_threshold` | 100,000,000 tuples |
| `autovacuum_naptime` | 1 minute |

The **fixed 50-tuple base term dominates on small tables** — this is the
counter-intuitive bit. A 5-row table needs ~51 dead tuples before autovacuum
looks at it, i.e. it tolerates being ~10× its live size before cleanup. That
sounds bad and is completely irrelevant: 10× of "one page" is still under
100 kB. And the docs are explicit that steady state, not minimum size, is the
goal:

> "the idea is not to keep tables at their minimum size, but to maintain
> steady-state usage of disk space: each table occupies space equivalent to
> its minimum size plus however much space gets used up between vacuum runs."

Combined with §5.1 (HOT prunes intermediate versions during ordinary
`SELECT`s), the "frequent updates bloat your users table" worry is a **folk
belief in this shape**. It is true for wide rows, indexed hot columns, or
long-running transactions that hold back the vacuum horizon — not for a
narrow, unindexed, HOT-eligible column on a tiny table.

Monitoring, if we ever want to check rather than assume — `pg_stat_all_tables`
(https://www.postgresql.org/docs/current/monitoring-stats.html):

- `n_tup_upd` — "Total number of rows updated."
- `n_tup_hot_upd` — "Number of rows HOT updated. These are updates where no
  successor versions are required in indexes."
- `n_tup_newpage_upd` — "…These are always non-HOT updates."
- `n_dead_tup` — "Estimated number of dead rows"
- `last_autovacuum` — "Last time at which this table was vacuumed by the
  autovacuum daemon"

The health check is one query: `n_tup_hot_upd / n_tup_upd` on `users` should
stay near 1.

#### 5.4 Narrow the `UPDATE` to one column

Both Django (`save(update_fields=["last_login"])`) and GoTrue
(`tx.UpdateOnly(u, "last_sign_in_at")`) narrow the statement to the single
column. This matters for the HOT condition in §5.1: an ORM that writes back
every column will touch `email`, which **is** indexed via
`ix_users_email` — defeating HOT even though the email value did not change.
In SQLModel/SQLAlchemy, assigning only the one attribute on a loaded object
produces a single-column `UPDATE`; an explicit
`update(User).where(User.id == ...).values(last_seen_at=...)` guarantees it.

#### 5.5 Should we index `last_seen_at` for sorting? No.

> "After an index is created, the system has to keep it synchronized with the
> table. This adds overhead to data manipulation operations. **Indexes can
> also prevent the creation of heap-only tuples.** Therefore indexes that are
> seldom or never used in queries should be removed."
> — https://www.postgresql.org/docs/current/indexes-intro.html

Every factor points the same way at pilot scale:

1. The planner "will use the index in queries when it thinks doing so would
   be more efficient than a sequential table scan" — for a handful of rows on
   one page it will not. The index would be built, maintained, and never
   read.
2. It converts our cheapest possible write into the most expensive version of
   itself: non-HOT heap update **plus** an index insert **plus** index bloat
   on the churniest column in the table.
3. Sorting a handful of rows is free — and the admin Users list is already
   filtered to one org, so the query is bounded by org size, not table size.

Sort in SQL without an index (`ORDER BY last_seen_at DESC NULLS LAST`); the
sort node costs nothing at this cardinality. Revisit only if a single org
reaches tens of thousands of users **and** `EXPLAIN` shows the sort actually
hurting — and even then, prefer a narrow separate table (§1.3) so the index
lives away from `users`.

---

## Recommendation for Dmitri

**Do this:**

1. **Column.** Add `last_seen_at: datetime | None` to `User`
   (`backend/src/api/models/identity.py`), `TIMESTAMPTZ`, nullable, **no
   index**, `fillfactor` left at the default 100. Nullable because existing
   users have never been seen — `None` renders as "Never", which is real
   information for an admin.
2. **Write point.** Stamp inside `refresh_session()`
   (`backend/src/api/services/auth.py`) and in `login()`, in the **same
   transaction** that already rotates/issues the refresh token. No middleware,
   no background task, no new failure mode. Effective granularity: **~15
   minutes**, set by the access-token TTL.
3. **Narrow the UPDATE.** Set only `last_seen_at` (or use an explicit
   `update(User).values(last_seen_at=...)`). Writing back `email` too would
   touch `ix_users_email` and defeat HOT (§5.4) — the single easiest way to
   accidentally make this expensive.
4. **Rendering.** Full precision in the DB; **coarse in the UI** — relative
   ("2 hours ago", "3 days ago") or a date. Cheaper on the eye and the
   stronger data-minimisation position (§4.3).
5. **Sorting.** `ORDER BY last_seen_at DESC NULLS LAST` with a stable
   tiebreak (`id ASC`), matching the existing `read.py` pattern for
   `HostRecord.last_seen_at`. No index (§5.5).
6. **Privacy paperwork.** One sentence in the privacy notice / in-product
   telling users their org admins can see when they last used Dmitri, plus a
   short documented note on purpose + lawful basis (legitimate interests,
   three-part test). ~30 minutes of writing; it is the one obligation here
   that is genuinely non-optional (§4.2).

**Explicitly do NOT do, and why it would be premature:**

- **Do not index `last_seen_at`.** At five rows the index is never read and
  it converts every stamp into a non-HOT heap+index write (§5.1, §5.5). This
  is the one decision with a real wrong answer.
- **Do not add Redis, a write-behind buffer, or a background flusher.** ~20
  writes/hour. No primary source recommends this pattern; the closest
  documented analogue (Django `cached_db`) is write-through and does not even
  remove the DB write (§1.3).
- **Do not split into a `user_activity` table** — the mechanism is sound but
  needs a wide `users` row and a permanently-dirty table to pay for the join
  and the extra model (§1.3).
- **Do not lower `fillfactor`.** PostgreSQL reserves that for "heavily
  updated" tables (§5.2).
- **Do not add per-request middleware.** It buys sub-second accuracy nobody
  reads off a Users table, and puts a write on read-only endpoints (§2.2).
- **Do not also store IP / user-agent** the way Devise and GoTrue do. We have
  no stated purpose for them, which makes them an Art. 5(1)(c) minimisation
  problem rather than a feature (§4.2). Add them later *with* a purpose if a
  security-audit requirement appears.
- **Do not add a second `last_login_at` column yet.** One column answers the
  admin's question; splitting later is a trivial additive migration (§3.4).

**What would have to change to revisit:**

| Trigger | Then adopt |
|---|---|
| Sorting/filtering on `last_seen_at` becomes slow in `EXPLAIN` for a real org (~10k+ users in one org) | Split to a narrow `user_activity` table and index it *there*, keeping `users` HOT-clean |
| We move to per-request stamping (e.g. an accurate idle-timeout feature) | The conditional-`WHERE` coalescing idiom at 1–5 min granularity (§1.5) — that mitigation is genuinely required in that regime, not optional |
| `n_tup_hot_upd / n_tup_upd` on `users` drops well below 1 | Something added an index over a churned column, or the ORM widened the `UPDATE`. Fix the cause; don't tune vacuum (§5.3, §5.4) |
| The feature grows into activity *history* rather than one timestamp | Retention policy required under Art. 5(1)(e), and re-run the DPIA screening — a log is a materially different privacy proposition from an overwritten timestamp (§4.2) |
| An org asks for per-second activity reporting on named employees | Stop and get legal input. That is the ICO's "function creep" scenario and a different lawful-basis conversation (§4.3) |
