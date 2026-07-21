# Code-map update log

Newest first. Entry conventions: `## YYYY-MM-DD`, then `* **Creation** / **Update** / **Deletion**: …`.
The [`docs-sync`](../skills/docs-sync/SKILL.md) skill appends here after code changes land.

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
