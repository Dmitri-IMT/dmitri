export function formatScanDuration(
  seconds: number | null | undefined,
): string | null {
  if (seconds == null) return null
  if (seconds < 60) return `${seconds}s`
  return `${Math.floor(seconds / 60)} min`
}
