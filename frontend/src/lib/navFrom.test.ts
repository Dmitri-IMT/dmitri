import { describe, expect, it } from 'vitest'
import { fromHere, resolveBackTo, type PathLocation } from '@/lib/navFrom'

function at(path: string, state: unknown = null): PathLocation {
  const q = path.indexOf('?')
  if (q === -1) return { pathname: path, search: '', state }
  return { pathname: path.slice(0, q), search: path.slice(q), state }
}

describe('fromHere', () => {
  it('records the current path and query', () => {
    expect(fromHere({ pathname: '/scans/abc', search: '?finding=1' })).toEqual({
      from: '/scans/abc?finding=1',
    })
  })
})

describe('resolveBackTo', () => {
  it.each([
    {
      name: 'uses the recorded origin',
      location: at('/scans/abc?finding=1', { from: '/' }),
      fallback: '/scans',
      want: '/',
    },
    {
      name: 'returns to the scan that opened a machine',
      location: at('/network/host-1', { from: '/scans/abc' }),
      fallback: '/network',
      want: '/scans/abc',
    },
    {
      name: 'falls back when nothing was recorded',
      location: at('/scans/abc'),
      fallback: '/scans',
      want: '/scans',
    },
    {
      name: 'falls back when origin is the current screen',
      location: at('/scans/abc', { from: '/scans/abc' }),
      fallback: '/scans',
      want: '/scans',
    },
    {
      name: 'rejects a protocol-relative path',
      location: at('/scans/abc', { from: '//evil.example' }),
      fallback: '/scans',
      want: '/scans',
    },
    {
      name: 'rejects an auth screen',
      location: at('/scans/abc', { from: '/login' }),
      fallback: '/scans',
      want: '/scans',
    },
    {
      name: 'rejects a non-string from',
      location: at('/scans/abc', { from: 12 }),
      fallback: '/scans',
      want: '/scans',
    },
  ])('$name', ({ location, fallback, want }) => {
    expect(resolveBackTo(location, fallback)).toBe(want)
  })
})
