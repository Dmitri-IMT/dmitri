# TRUTH — Give a failed scan a readable reason

## Narrative

A scan that fails tells the operator nothing. The scan detail response carries a status of
`failed` and no reason at all. To learn why, a client must take the command id from the scan,
make a second request to the command endpoint, and read a machine code — and that path is
broken twice over: the scan detail response hardcodes a null command id, so the second request
cannot even be addressed, and the stale-command sweep marks commands `failed` without writing
any code at all. The most common real failure, a Pi that stops responding mid-scan, produces a
failed scan with no reason anywhere in the system.

The roadmap promised "scan failed → readable failure reason". Today that is unreachable. On the
scan detail screen the failure *is* the content: an org admin who is not technical opens a red
scan and must learn, in one sentence, what happened and what to do next.

This feature makes the reason reachable in one request and makes it legible. The API carries a
closed set of failure codes. The sentence an operator reads is client copy, the way an HTTP
client owns the phrase for a status code. The wire never carries prose.

## Business rules

- A scan whose status is `failed` always carries a failure code. There is no failed scan
  without a reason.
- A scan whose status is not `failed` never carries a failure code. A green scan shows no
  stale reason beside it.
- The reason is available from the scan itself, in one request. No second round trip.
- The set of failure codes is closed and published in the API contract. A client can enumerate
  every reason it may have to render.
- When the true reason cannot be established — no command record, no code recorded, or a code
  the contract does not know — the scan reports `unknown` rather than nothing. An honest
  admission beats silence.
- A field agent that reports a failure code the backend does not recognise is still believed:
  the failure report is accepted and stored, and the reader sees `unknown`. A newer field agent
  is never silenced by an older backend.
- The failure codes name the failures the system already has. This feature makes them legible; it
  does not invent, rename, or reorganise the failures themselves. Today only the backend emits
  codes — `device_offline` and `agent_disconnected`, from the delivery and sweep paths. The
  remaining six are the vocabulary the Pi reports into: `hardware-agent` already carries an
  `error_code: str | None` the whole way up its status path, but passes `None` on every branch.
  Publishing the set now is what lets the Pi start naming its failures without a contract change.
- The sentence shown to an operator names the Pi, states what happened, and ends with the next
  action. It never shows a code, a stack trace, or raw scanner output.

## User stories

1. As a non-technical org admin, I want a failed scan to tell me in one sentence what went
   wrong, so that I know whether to check the Pi, wait, or ask for help.
2. As an org admin, I want that sentence when I open the scan, so that I do not have to chase a
   second screen or read a machine code.
3. As an org admin, I want an honest message even when the system does not know why the scan
   failed, so that I am never left staring at a red badge with no explanation.
4. As a developer, I want the published set of failure codes and the client's sentences checked
   against each other automatically, so that a new code cannot ship without copy.

## Acceptance criteria (verifiable)

| Scenario | Given | When | Then |
|----------|-------|------|------|
| Reason on the scan | a scan that failed because its command failed with a known reason | the scan detail is requested | the response carries that failure code, in one request |
| Command is reachable | a scan created by a command | the scan detail is requested | the response carries the real command id, not null |
| No reason recorded | a failed scan whose command recorded no failure code | the scan detail is requested | the response carries `unknown` |
| No command at all | a failed scan with no command record | the scan detail is requested | the response carries `unknown` |
| Unrecognised code | a failed scan whose command recorded a code outside the published set | the scan detail is requested | the response carries `unknown` |
| Never bare | any failed scan | the scan detail is requested | the failure code is present and non-null |
| Never stale | a scan that is not failed | the scan detail is requested | no failure code is present |
| Sweep records a reason | a Pi that took a job and then stopped responding | the stale sweep marks the command failed | the command carries the "stopped responding" code, not a null |
| Sweep records abandonment | a command that was never taken by a Pi | the stale sweep expires it | the command carries the "Pi was not connected" code |
| Field agent ahead of backend | a field agent reporting a failure code the contract does not list | the report arrives | the report is accepted and stored, the connection stays open, and readers see `unknown` |
| Every code has a sentence | the published set of failure codes | the client copy is checked against it | every code maps to a sentence, and the check fails if one is missing |
| Copy is human | the client copy | it is read | no code names, scanner output, or stack traces appear; each sentence ends with the operator's next action |
| List untouched | the scan list | it is requested | it is unchanged — no failure code on list rows |

## Out of scope (v1)

- Retrying a scan from the scan detail. Retry belongs to the Agents surface.
- Redesigning, renaming, or reorganising the failure taxonomy. The codes name failures the
  system already has.
- Teaching the Pi to emit the six codes it does not yet report. The vocabulary ships here; the
  emitters are separate work.
- Any prose, sentence, or user-facing copy in the API payload.
- Stack traces, scanner output, or diagnostic detail in the operator's view.
- A scan detail screen. The client copy ships here; the screen that renders it is separate work.
- The failure code on scan list rows.
- Backfilling historical rows.
- Storing the reason on the scan record itself. It is derived from the command when read.

## Related specs

- Implementation: `ARCHITECTURE.md`
- Source issue: DMI-75 (closes contract ask C10 in `docs/ui/FLOWS.md`)
- Prior decisions: ADR-011 (Pi command channel — lifecycle, `expired` vs `failed`)

## Docs drift (docs-sync, 2026-08-13)

Reported, not patched — needs a human call:

- `docs/ui/SCREENS.md` failed-state copy table still shows `"The Pi reported: <error_code>."` and
  `"No reason was recorded."` Those strings contradict the approved copy deck (no codes on
  screen; `unknown` is a sentence). Left alone because that table is target-state for the unbuilt
  Scan Detail screen (DMI-88), not current-state code.
- `docs/architecture/ARCHITECTURE.md` §6 lists scan/command routes but does not mention
  `ScanDetailResponse.error_code`. No factual contradiction found; not patched.

