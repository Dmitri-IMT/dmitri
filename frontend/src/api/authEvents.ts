type Handler = () => void

const handlers = new Set<Handler>()

export function onSessionExpired(handler: Handler): () => void {
  handlers.add(handler)
  return () => handlers.delete(handler)
}

export function emitSessionExpired(): void {
  handlers.forEach((handler) => handler())
}
