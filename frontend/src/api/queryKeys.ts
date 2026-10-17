import type { FindingListParams } from './findings'
import type { HomePages } from './home'
import type { HostListParams } from './hosts'
import type { ScanListParams } from './scans'

export type { FindingListParams, HostListParams, ScanListParams }

export const queryKeys = {
  home: {
    all: ['home'] as const,
    snapshot: (pages: HomePages) =>
      [
        'home',
        'snapshot',
        pages.attentionPage,
        pages.eventsPage,
        pages.activityPage,
      ] as const,
  },
  scans: {
    all: ['scans'] as const,
    latest: (scope: 'any' | 'completed') => ['scans', 'latest', scope] as const,
    list: (params: ScanListParams) => ['scans', 'list', params] as const,
    detail: (scanId: string) => ['scans', 'detail', scanId] as const,
    analysis: (scanId: string, language: string) =>
      ['scans', 'analysis', scanId, language] as const,
  },
  ai: {
    usage: (limit: number) => ['ai', 'usage', limit] as const,
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
  agents: {
    all: ['agents'] as const,
    list: () => ['agents', 'list'] as const,
    detail: (agentId: string) => ['agents', 'detail', agentId] as const,
  },
  commands: {
    all: ['commands'] as const,
    detail: (commandId: string) => ['commands', 'detail', commandId] as const,
  },
} as const
