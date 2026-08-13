import type { components } from '@/types/openapi'

type ScanErrorCode = components['schemas']['ScanErrorCode']

// Approved copy (DMI-75). Every sentence names the Pi, says what happened, and ends with the
// operator's next action. No codes, no scanner output.
export const SCAN_FAILURE_REASONS: Record<ScanErrorCode, string> = {
  device_offline:
    "The Pi wasn't connected when the scan was requested. Check that it's powered on and online, then try again.",
  device_busy:
    'The Pi was already running another scan. Wait for it to finish, then try again.',
  agent_disconnected:
    "The Pi stopped responding while the scan was running. Check that it's powered on and online, then try again.",
  scan_failed:
    "The scan didn't finish on the Pi. Try again — if it keeps failing, contact support.",
  invalid_command:
    "The Pi couldn't read the scan request. Try again — if it keeps failing, contact support.",
  result_unavailable:
    'The scan ran but produced no results to upload. Try again.',
  ingest_failed:
    "The Pi finished the scan but couldn't upload the results. Check its network connection, then try again.",
  unknown: 'The scan failed. No further detail was reported.',
}

// `error_code` is an optional property on the generated response types, so callers
// can hand us `undefined` as readily as `null`. Both mean "no reason reported".
export function scanFailureReason(code: string | null | undefined): string {
  if (code === null || code === undefined) return SCAN_FAILURE_REASONS.unknown
  const reasons: Record<string, string | undefined> = SCAN_FAILURE_REASONS
  return reasons[code] ?? SCAN_FAILURE_REASONS.unknown
}
