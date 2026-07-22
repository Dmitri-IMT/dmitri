# Code-map update log

Newest first. Entry conventions: `## YYYY-MM-DD`, then `* **Creation** / **Update** / **Deletion**: …`.
The [`docs-sync`](../skills/docs-sync/SKILL.md) skill appends here after code changes land.

## 2026-07-22

* **Creation**: Added the `frontend/**` code-map section (`overview`, `api`, `app`, `index`) for the
  greenfield SPA scaffold shipped by spec 014 (frontend/): the two-Axios-instance auth client with
  the single-flight 401→refresh interceptor, the in-memory token store, the contract-typed API
  layer, and the boot-refresh + stub login/placeholder UI. Linked from the root `index.md` under a
  new "Frontend (scaffold only)" section; noted the new `frontend` CI job in `.github/workflows/ci.yml`.

## 2026-07-21

* **Update**: Corrected the README scan-modes table (Quick is default top-1000 + `vulners`, not
  `-F`) to match `discovery_arguments()`; removed the now-resolved divergence note from `overview.md`.
* **Initialization**: Created the OKF code-map bundle mapping the whole repo — top-level
  `overview` / `glossary` / `contracts`, the `hardware-agent/**` set (overview, cli, discovery,
  normalize, utils, tui, and the split `scanner/` package), the `backend/**` set (overview, api,
  models, schemas, services, migrations), the `infra/**` set (supabase, deployment), plus
  `MAINTAINING.md` and per-directory `index.md` files.
* **Note**: Corrected the scan-modes table in `overview.md` to match `discovery_arguments()` —
  Quick/Standard use the default top-1000 port set (not `-F`, as the README's product table states).
