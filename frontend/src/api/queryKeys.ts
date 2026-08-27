import type { FindingListParams } from './findings'
import type { HostListParams } from './hosts'
import type { ScanListParams } from './scans'

export type { FindingListParams, HostListParams, ScanListParams }

export const queryKeys = {
  scans: {
    all: ['scans'] as const,
    latest: (scope: 'any' | 'completed') => ['scans', 'latest', scope] as const,
    list: (params: ScanListParams) => ['scans', 'list', params] as const,
    detail: (scanId: string) => ['scans', 'detail', scanId] as const,
  },
  hosts: {
    all: ['hosts'] as const,
    list: (params: HostListParams) => ['hosts', 'list', params] as const,
    detail: (hostId: string) => ['hosts', 'detail', hostId] as const,
  },
  findings: {
    all: ['findings'] as const,
    list: (params: FindingListParams) => ['findings', 'list', params] as const,
  },
} as const
