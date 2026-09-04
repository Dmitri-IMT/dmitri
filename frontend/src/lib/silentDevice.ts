const DAY_MS = 24 * 60 * 60 * 1000
const WEEK_MS = 7 * DAY_MS

const SILENT_AFTER_MS = 14 * DAY_MS

function elapsed(lastSeenAt: string, now: Date): number {
  return now.getTime() - new Date(lastSeenAt).getTime()
}

export function isSilent(lastSeenAt: string, now: Date): boolean {
  return elapsed(lastSeenAt, now) > SILENT_AFTER_MS
}

export function weeksSince(lastSeenAt: string, now: Date): number {
  return Math.floor(elapsed(lastSeenAt, now) / WEEK_MS)
}
