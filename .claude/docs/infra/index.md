# Infra

Supabase-managed Postgres, dev/install infrastructure, the local Pi simulator, and the three-service Railway deployment.

* [Supabase (managed Postgres)](./supabase.md) — How Dmitri uses Supabase purely as arms-length managed Postgres 17 — not its Auth, Data API, or client SDK.
* [Deployment (install scripts + Railway)](./deployment.md) — Dev-environment installers, the local Pi simulator, and the three-service Railway + Supabase topology.
* [Local Pi simulator](./pi-simulator.md) — The ephemeral Docker harness that runs the real agent, backend, worker, Postgres, and a Samba scan target.
