export function loginDestination(search: string): string {
  const request = new URLSearchParams(search).get('mcp_request')
  return request && /^[A-Za-z0-9_-]{43}$/.test(request)
    ? `/mcp/authorize?request=${request}`
    : '/'
}
