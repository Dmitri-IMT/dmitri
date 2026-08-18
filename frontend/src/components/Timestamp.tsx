const RELATIVE_WINDOW_MS = 7 * 24 * 60 * 60 * 1000
const MINUTE_MS = 60 * 1000
const DAY_MS = 24 * 60 * 60 * 1000

function pad(value: number): string {
  return value.toString().padStart(2, '0')
}

function formatClock(date: Date): string {
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function isSameCalendarDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

function formatTimestamp(value: string, now: Date = new Date()): string {
  const date = new Date(value)
  const diffMs = now.getTime() - date.getTime()

  if (diffMs >= RELATIVE_WINDOW_MS) {
    const month = date.toLocaleString('en-US', { month: 'short' })
    return `${month} ${date.getDate()}, ${formatClock(date)}`
  }

  const diffMinutes = Math.round(diffMs / MINUTE_MS)
  if (diffMinutes < 1) return 'just now'
  if (diffMinutes < 60) return `${diffMinutes} min ago`

  if (isSameCalendarDay(date, now)) return `today ${formatClock(date)}`

  const yesterday = new Date(now.getTime() - DAY_MS)
  if (isSameCalendarDay(date, yesterday))
    return `yesterday ${formatClock(date)}`

  const diffDays = Math.round(diffMs / DAY_MS)
  return `${diffDays} days ago`
}

function Timestamp({ value, now }: { value: string; now?: Date }) {
  const date = new Date(value)
  return (
    <time dateTime={value} title={date.toLocaleString()}>
      {formatTimestamp(value, now)}
    </time>
  )
}

export default Timestamp
