# TRUTH — Operating-system inventory

## Narrative

Dmitri already asks the scanner to identify operating systems, but that evidence disappears
before the scan result reaches operators. An operator needs the detected operating system and
its confidence to survive the scan lifecycle, so the local result, terminal interface, cloud
inventory, and API all describe the same host consistently.

Operating-system identification is probabilistic. Dmitri must distinguish a supported detection
from missing evidence and must never present a guess as a confirmed fact.

## Business rules

- A host may have one best operating-system detection or no operating-system detection.
- A detection records the most specific available name plus its confidence as a percentage.
- When available, a detection also records vendor, family, generation, device type, and one or
  more platform identifiers.
- The best detection is the candidate with the highest confidence reported for that host.
- Missing optional attributes remain absent; they are not replaced with invented values such as
  `unknown`.
- Absence of a detection is a valid result and must not cause a scan, ingestion, persistence, or
  display failure.
- Operating-system evidence must remain associated with the same host in local results, cloud
  ingestion, persisted inventory, API responses, and the terminal interface.
- Existing scan results and clients that do not contain operating-system evidence remain valid.
- A later scan with supported operating-system evidence updates the host inventory; a later scan
  without such evidence does not erase the last supported inventory value.
- The interfaces label the value as detected, including confidence, rather than asserting it as
  certain.

## User stories

1. As a network operator, I want to see the detected operating system for each host in the
   terminal interface, so that I can understand the estate and prioritise investigation.
2. As a security analyst, I want the confidence and structured operating-system attributes, so
   that I can judge whether a detection is reliable and correlate it with exposure.
3. As an integrator, I want the same optional operating-system object in local and cloud scan
   contracts, so that information is not lost between collection and presentation.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Best detection retained | A host has multiple operating-system candidates with different confidence values | The scan result is produced | The highest-confidence candidate and its available structured attributes belong to that host |
| Detection in local result | A host has supported operating-system evidence | A scan is saved locally | The host's structured operating-system detection and confidence are present in the JSON result |
| Detection in terminal interface | A completed scan contains a host with operating-system evidence | The operator views that host in the terminal interface | The detected name and confidence are visible |
| Detection ingested | A local result containing operating-system evidence is submitted | The cloud accepts and processes the scan | The same evidence is persisted for the corresponding scan host and inventory host |
| Detection in read API | A persisted scan or inventory host has operating-system evidence | A client reads that host through the API | The same structured detection is returned |
| Missing detection | A host has no supported operating-system evidence | The result passes through every layer | The host remains valid and interfaces communicate that no operating system was detected |
| Backward compatibility | An older result omits operating-system evidence | It is loaded or ingested | Validation and processing succeed without fabricating a detection |
| Inventory preservation | A host inventory entry has a supported detection and a later scan of the same host has none | The later scan is materialised | The scan records the absence while the inventory retains its last supported detection |
| Inventory refresh | A host inventory entry has an older detection and a later scan supplies a supported detection | The later scan is materialised | The inventory stores the newer supported detection |

## Out of scope (v1)

- Guaranteeing that an operating-system detection is correct.
- Storing raw fingerprint payloads or every lower-ranked candidate.
- Inferring an operating system solely from a service or application platform identifier.
- Adding a new operating-system detection engine or external fingerprint database.
- Filtering, sorting, risk scoring, or vulnerability matching by operating system.
- Displaying operating-system information in the web frontend or modifying generated frontend
  API types.

## Related specs

- Implementation: `ARCHITECTURE.md`, `DESIGN.md`, `INTEGRATION.md`

## Docs drift

- The `.claude/docs/` code-map could not be synchronized because the complete tree is already
  deleted in the operator's working copy; those pre-existing deletions were preserved.
- Direct runtime OpenAPI generation could not import the backend without the required
  `DATABASE_URL` and `JWT_SIGNING_SECRET` environment variables. Contract-fidelity tests passed
  during implementation review.
