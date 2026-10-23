# R6 delivery — 2026-10-23

Phases A and B were already committed in `0e96c75` and `37d4e7f`. C–E are now implemented.
The initial uncommitted explanation model, schemas, migration and writing rules were retained
and completed.

## Delivered

- Structured scan/host explanations with tenant checks before cache reads, language/version
  keys, host refresh on a newer scan, verified count labels and references, secret scrubbing,
  shared chat daily limits, usage persistence on failure, RLS and deletion integration.
- Shared term and risk hints, explanation sheet, vulnerability states, checked task links,
  expandable risk-sorted problems, evidence select, first five rows and Show more.
- Scan story, to-do, meaning, problems and counted IT sections. Running, failed, stopped,
  targeted/exposure deep links and evidence observations remain supported.
- Machine about/best-fix/problems/IT composition. Findings are filtered by host and latest
  scan and all pages load before task selection. The best task covers the most findings.
- Top-bar assistant, message bubbles and source links. Inline finding chats were removed.
- Owner follow-up: problem-table machine names cap at 24 characters including `...`;
  full names stay in hover text and accessible labels, and the link clips to the cell width.

## Verification

- Frontend: lint, format:check, typecheck, 748 tests and production build pass. Only the
  pre-existing LanguageProvider Fast Refresh warnings and bundle-size warning remain.
- `npm run gen:types` is reproducible; a second run produces identical bytes.
- Backend: `uv run ruff check src tests` passes. 269 focused migration/API/privacy/deletion/
  provider checks pass. The final contract check adds the published explanation auth/error
  assertion; all 154 contract checks pass.
- Required `./database.sh --test` ran against live `dmitri_test`. The full suite was also
  run on a separate PostgreSQL 17 test database named exactly `dmitri_test` to avoid
  conflicts with the other checkout's local stack: **1,840 passed, 1 skipped, 9 failed**.
  All nine failures are in unchanged `test_release_catalog.py`: GnuPG 2.5.21 returns from
  verification without the expected plaintext `Release` output file. The backend full
  suite is **not green**. No release-catalog code or tests were changed.
- Live OpenAI scan analysis completed with real copied scan data, including vendor
  research, two finding groups, one repair and synthesis. The first run hit the local
  30-second timeout; retry with a longer preview timeout completed. Successful synthesis
  took 37.2 seconds; successful finding calls took 28.9–36.2 seconds.
- Live scan explanations completed in 16.9–29.8 seconds, and a Portuguese machine
  explanation completed in 12.2 seconds. Count labels were validated before storage.
- The actual branch preview is `http://127.0.0.1:5174`, API port 8001. It uses the separate
  local database `dmitri_r6_review_20261023`, this branch's migration head and copied
  recorded scan/feed data. Its API now uses the repository's 120-second timeout default.
  The older `/Users/gui/Projects/dmitri` app remains on ports 5173/8000.
- Scan and machine pages were inspected in the app browser. The name truncation was
  visually checked. Captures: `/tmp/dmitri-r6-review/problems.png` and
  `/tmp/dmitri-r6-review/machine-explanation.png`.

## Remaining review limits

- The external Claude canvas URL was inaccessible to the web tool. The implementation
  was checked against the approved text in DESIGN 052 and 053 §1.2; an exact canvas
  comparison is not claimed.
- pt-BR/ru hint wording still needs owner review, as the design requires.
- EPSS display assumptions: 10% for Likely/high and 50% for very high. Task machine links
  open machine pages. The task ledger records the remaining verification limits.
- The PRD's separate organisation AI-language setting and future Home review work were
  not included in the owner-approved C–E plan.
