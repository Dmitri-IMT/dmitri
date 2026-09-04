export type PathLocation = {
  pathname: string
  search: string
  state: unknown
}

export function fromHere(location: { pathname: string; search: string }): {
  from: string
} {
  return { from: location.pathname + location.search }
}

export function resolveBackTo(
  location: PathLocation,
  fallback: string,
): string {
  const from = readFrom(location.state)
  if (from === null) return fallback
  if (!isInAppPath(from)) return fallback
  const current = location.pathname + location.search
  if (from === current) return fallback
  return from
}

function readFrom(state: unknown): string | null {
  if (state === null || typeof state !== 'object' || !('from' in state)) {
    return null
  }
  const value = state.from
  return typeof value === 'string' ? value : null
}

function isInAppPath(path: string): boolean {
  if (!path.startsWith('/') || path.startsWith('//')) return false
  return (
    !path.startsWith('/login') &&
    !path.startsWith('/forgot-password') &&
    !path.startsWith('/reset-password') &&
    !path.startsWith('/invite')
  )
}
