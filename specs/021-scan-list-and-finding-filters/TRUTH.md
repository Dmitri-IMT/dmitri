# TRUTH — Scan list and finding filters (DMI-82)

Domain language and verifiable behaviour only. No file paths, no code, no SQL. The response
shapes are already frozen in `contracts/openapi/openapi.yaml`; `ARCHITECTURE.md` turns this
behaviour into paths and queries.

## Narrative

The product can already answer "tell me about *this* scan" and "tell me about this network's
machines". It cannot answer **"what happened most recently?"** — there is no way to list scans
at all. And it cannot answer **"what is wrong right now?"** without downloading every finding
ever recorded, because the only filter that works on findings is by machine.

Both gaps are the leftovers of the read-path work, which deliberately fenced them out: it
delivered the durable host model, the host list and detail, scan *detail*, and an unfiltered
finding list, and explicitly deferred the scan list and the filtering behaviour.

Nothing about them is an open question. **Both are already specified in the frozen API
contract** — the query parameters, the sort options, the response envelopes and every field are
defined and unchanged. This feature implements what was agreed and never built. It is the last
thing standing between the product and its first real screen: Home cannot state a verdict
without knowing the latest scan and that scan's serious findings.

The work is deliberately narrow. No new concepts enter the domain. No shape changes. If the
implementation appears to need one, that is a signal to stop and raise it, not to widen the
contract.

## Business rules

- **An organisation sees only its own data.** Every scan and every finding returned belongs to
  the asking user's organisation. This holds under every combination of filters — a filter is
  never a way around the boundary.
- **The most recent scan comes first by default.** Callers who ask for one scan get the newest.
- **Empty is a valid answer, not a failure.** An organisation with no scans, or a filter that
  matches nothing, gets an empty page — never an error and never a "not found".
- **A filter narrows; it never widens.** Filters combine conjunctively: asking for a severity
  *and* a scan returns only findings that are both.
- **Asking for nothing in particular returns everything.** An omitted filter is not a filter.
- **The stated total counts everything that matched, not everything on the page.** A caller
  reading page one of a large result learns how many results exist.
- **A page beyond the end is empty, not an error.** The total still reflects the full match.
- **Paging is stable.** Two callers paging the same unchanged data see every matching record
  exactly once. No record is repeated on two pages and none is skipped between them, even when
  many records tie on whatever they are ordered by. This is a property of paging, not a
  sorting feature — callers still cannot choose how findings are ordered.
- **A finding's severity is one of the four known severities.** The store itself refuses any
  other value, so a record that cannot be described to a caller cannot exist.
- **A scan summarises itself honestly.** When a scan is listed, the number of machines it
  covered, the number of findings it produced, and the most serious severity among them
  describe *that* scan — not the organisation's running totals.
- **A scan with no findings has no most-serious severity.** That is an absence, not a zero and
  not a lowest-severity value.
- **Requests that violate the contract's limits are refused, not clamped.** A page size beyond
  the permitted maximum, a page below one, or an unknown sort field is a bad request.

## User stories

1. As the Home screen, I want the single most recent scan, so that I can state a verdict about
   what the network looks like now.
2. As the Home screen, I want only the critical findings of that scan, and then only the high
   ones, so that I can list what needs attention without downloading everything else.
3. As the Home screen, I want to know that an organisation has never scanned, so that I can
   show first-run guidance instead of an empty verdict.
4. As the Scans screen (later), I want to page through an organisation's scan history newest
   first, so that an operator can find a scan from last week.
5. As the Scans screen (later), I want to list only failed scans, so that an operator can see
   what went wrong without reading every successful run.
6. As any authenticated caller, I want to be certain I can never see another organisation's
   scans or findings, whatever I pass.

## Acceptance criteria (verifiable)

| # | Scenario | Given | When | Then |
|---|----------|-------|------|------|
| 1 | Latest scan | An organisation with several scans | One scan is requested | Exactly one scan returns, and it is the most recent by time |
| 2 | Default order | An organisation with several scans | Scans are listed with no ordering asked for | They come back newest first |
| 3 | Reversed order | An organisation with several scans | Scans are listed oldest-first | The oldest comes back first |
| 4 | Sort by another field | An organisation with scans of differing status and mode | Scans are listed sorted by that field | The order follows that field, in the requested direction |
| 5 | No scans | An organisation that has never scanned | Scans are listed | An empty page returns with a total of zero — not an error, not a "not found" |
| 6 | Scan paging | An organisation with 25 scans, listed 20 at a time | The second page is requested | 5 scans return, none repeated from the first page, and the total says 25 |
| 7 | Page past the end | An organisation with 3 scans, listed 20 at a time | The fifth page is requested | No scans return and the total still says 3 |
| 8 | Filter scans by status | An organisation with successful and failed scans | Only failed scans are listed | Only the failed ones return |
| 9 | Scan summary is per-scan | A scan covering 12 machines with 4 findings, the worst of them critical, and an older scan with different numbers | Scans are listed | That scan reports 12 machines, 4 findings and a most-serious severity of critical; the older scan reports its own |
| 10 | A scan with no findings | A scan that produced nothing | Scans are listed | It reports zero findings and no most-serious severity at all |
| 11 | Scan isolation | Two organisations, each with scans | One organisation lists scans | Only its own return, under every filter, sort and page |
| 12 | Findings by severity | A scan with findings across every severity | Only critical findings are requested | Only the critical ones return |
| 13 | Findings by scan | Two scans, each with findings | Findings of one scan are requested | Only that scan's findings return |
| 14 | Filters combine | Two scans, each with critical and lower findings | Critical findings of one scan are requested | Only findings that are both return |
| 15 | Existing filter still works | Findings across several machines | Findings of one machine are requested | Only that machine's findings return, exactly as before this feature |
| 16 | Machine and scan together | A machine with findings in two scans | That machine's findings in one scan are requested | Only findings matching both return |
| 17 | No filter | Findings of several severities | Findings are requested with no severity named | Findings of every severity return |
| 18 | Finding paging and total | 25 findings matching a filter, listed 20 at a time | The first page is requested | 20 return and the total says 25 — the total counts matches, not the page |
| 19 | Empty filter result | A scan with no critical findings | Its critical findings are requested | An empty page returns with a total of zero |
| 20 | Finding isolation | Two organisations with findings | One organisation requests findings | Only its own return, under every filter combination — including when it names another organisation's scan or machine |
| 21 | Unauthenticated | No credentials | Either list is requested | The request is rejected as unauthenticated, in the product's standard error shape |
| 22 | Invalid paging | Any organisation | A page size beyond the permitted maximum, or a page below one, is requested | The request is refused as a bad request — the value is not silently clamped |
| 23 | Invalid sort | Any organisation | An unknown sort field or direction is requested | The request is refused as a bad request |
| 24 | Contract fidelity | The implemented endpoints | Their published schema is compared to the frozen contract | They match — no field added, renamed, or missing |
| 25 | Stable finding paging | 25 findings that all tie on severity and time, listed 10 at a time | Every page is requested in turn | The pages together contain all 25 exactly once — none repeated, none missing |
| 26 | Stable scan paging under ties | Several scans sharing one status, listed by status, a page at a time | Every page is requested in turn | The pages together contain every scan exactly once |
| 27 | Severity domain enforced | The finding store | A finding is written with a severity outside the four known values | The store refuses it |
| 28 | Existing data survives | An existing database with findings already recorded | The upgrade is applied | It succeeds, every existing finding is unchanged, and the upgrade is reversible |
| 29 | Quality gates | The feature's branch | The backend test suite and linter run | Both pass on the touched scope |

## Out of scope (v1)

- **Any contract change.** No new field, no widened parameter, no new endpoint. If the frozen
  shapes prove insufficient, that is raised, not patched here.
- **The agents surface** — listing agents, agent detail, the Pi's target network. Owned by
  DMI-78.
- **A readable reason for a failed scan.** A listed scan says it failed; it does not say why.
  Owned by DMI-75.
- **Scan detail.** The existing single-scan read is finished and is not touched.
- **Free-text search** over scans or findings, and any sort or filter the contract does not
  already declare.
- **Caller-chosen sorting of findings.** The contract declares no sort for findings and none is
  invented. Findings come back in one fixed, unspecified-but-stable order; a caller cannot
  request another. The stability required above is a paging correctness property, not a feature
  a caller can see or control.
- **Filtering findings by severity range or by multiple severities in one request.** The
  contract takes one severity; a caller wanting two asks twice.
- **Scan lifecycle behaviour** — how a scan comes to be failed or pending. This feature reads
  what is already recorded.
- **Any frontend work.** DMI-81 consumes these endpoints and owns every pixel.
- **Performance work** beyond not being gratuitously wasteful — no caching layer, no
  denormalised counters, no new indexes unless a criterion above cannot otherwise be met.
- **Schema change beyond the severity constraint.** One reversible upgrade enforcing the
  severity domain is in scope (criteria 27–28). Nothing else about the store changes.
- **Paginating the machine list.** The machine list ignores the paging the contract declares
  and silently returns at most the first page. Real, pre-existing, and filed separately — not
  fixed here, and not to be mistaken for something this feature broke.

## Dependencies

| Depends on | State |
|---|---|
| The durable host model, scan detail, and the unfiltered finding list (DMI-74) | ✅ Done |
| Authenticated callers and the standard error shape (DMI-60, DMI-72) | ✅ Done |

No blockers. This feature is buildable today, and **DMI-81 is blocked until it lands**.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Contract (authoritative shapes): `contracts/openapi/openapi.yaml`
- The consumer this unblocks: `specs/020-frontend-vertical-slice-login-home/`
- Execution ledger: `POOP.md` (written during orchestration)
- Product brief: Linear DMI-82

No `DESIGN.md`: this feature has no user-facing screen.
