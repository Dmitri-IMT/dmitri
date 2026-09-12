const DAY_MS = 24 * 60 * 60 * 1000
const WEEK_MS = 7 * DAY_MS

export function weeksSinceLastSeen(lastSeenAt: string, now: Date): number {
  return Math.floor((now.getTime() - new Date(lastSeenAt).getTime()) / WEEK_MS)
}
