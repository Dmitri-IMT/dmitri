# Demo Script (Draft)

Use this outline to prepare future demos once functionality exists.

1. **Setup**
   - Introduce project goals and architecture slide (see `docs/architecture.md`).
   - Show Raspberry Pi hardware agent, backend container stack, and Flutter app running in an emulator.
2. **Configuration Preview**
   - Walk through `hardware-agent/src/agent/config.py` to highlight environment-driven settings.
   - Display `infra/docker-compose.yml` to explain local services.
3. **Scan Workflow (Future)**
   - Trigger a scan from the agent CLI placeholder (actual scan logic to be added in later phases).
   - Show how payloads would appear by referencing `contracts/examples/scan_result.example.json`.
4. **Reporting Experience (Future)**
   - Outline the planned mobile UI screens and backend endpoints described in `docs/api.md`.
5. **Wrap-up**
   - Summarize roadmap: implement scanning, persistence, analytics, and user-facing insights.

Update this script as soon as functional milestones are delivered.
