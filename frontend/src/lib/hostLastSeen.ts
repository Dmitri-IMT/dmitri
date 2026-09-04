const DAY_MS = 24 * 60 * 60 * 1000
const WEEK_MS = 7 * DAY_MS

const QUIET_AFTER_MS = 14 * DAY_MS

function elapsed(lastSeenAt: string, now: Date): number {
  return now.getTime() - new Date(lastSeenAt).getTime()
}

export function isQuietHost(lastSeenAt: string, now: Date): boolean {
  return elapsed(lastSeenAt, now) > QUIET_AFTER_MS
}

export function weeksSinceLastSeen(lastSeenAt: string, now: Date): number {
  return Math.floor(elapsed(lastSeenAt, now) / WEEK_MS)
}

export function partitionQuietHosts<Row extends { last_seen_at: string }>(
  rows: Row[],
  now: Date,
): { recent: Row[]; quiet: Row[] } {
  const recent: Row[] = []
  const quiet: Row[] = []
  for (const row of rows) {
    if (isQuietHost(row.last_seen_at, now)) quiet.push(row)
    else recent.push(row)
  }
  return { recent, quiet }
}
