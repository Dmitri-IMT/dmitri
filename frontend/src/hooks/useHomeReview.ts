import { skipToken, useQueries, useQuery } from '@tanstack/react-query'
import { getLatestScan, getLatestSuccessfulScan } from '@/api/scans'
import { HOME_SEVERITIES, listFindings } from '@/api/findings'
import { queryKeys } from '@/api/queryKeys'
import { deriveReview, type ScanItem, type CoverageItem } from '@/lib/review'
import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']
type FindingRecord = components['schemas']['FindingRecord']

interface HomeReviewData {
  reviewCount: number
  deckFindings: FindingRecord[]
  scanItem: ScanItem | null
  coverageItem: CoverageItem | null
  latestSuccessfulScan: ScanSummary | null
}

export type HomeReview =
  | { state: 'loading'; retry: () => void }
  | { state: 'blank'; retry: () => void }
  | ({ state: 'clear' } & HomeReviewData & { retry: () => void })
  | ({ state: 'pending' } & HomeReviewData & { retry: () => void })
  | { state: 'error'; retry: () => void }

export function useHomeReview(): HomeReview {
  const scanQuery = useQuery({
    queryKey: queryKeys.scans.latest('any'),
    queryFn: getLatestScan,
  })

  const successfulScanQuery = useQuery({
    queryKey: queryKeys.scans.latest('completed'),
    queryFn: getLatestSuccessfulScan,
  })

  const scanId = scanQuery.data?.scan_id

  // `skipToken` both disables the read until the scan id lands and narrows it away,
  // so the query function never has to assert the id is present.
  const [criticalQuery, highQuery] = useQueries({
    queries: HOME_SEVERITIES.map((severity) => ({
      queryKey: queryKeys.findings.list({ scan_id: scanId, severity }),
      queryFn:
        scanId === undefined
          ? skipToken
          : () => listFindings({ scan_id: scanId, severity }),
    })),
  })

  const retry = () => {
    scanQuery.refetch()
    successfulScanQuery.refetch()
    criticalQuery.refetch()
    highQuery.refetch()
  }

  if (scanQuery.isError) {
    return { state: 'error', retry }
  }
  if (scanQuery.isPending) {
    return { state: 'loading', retry }
  }

  const latestScan = scanQuery.data

  if (latestScan === null) {
    if (successfulScanQuery.isError) {
      return { state: 'error', retry }
    }
    if (successfulScanQuery.isPending) {
      return { state: 'loading', retry }
    }
    return { state: 'blank', retry }
  }

  if (
    successfulScanQuery.isError ||
    criticalQuery.isError ||
    highQuery.isError
  ) {
    return { state: 'error', retry }
  }
  if (
    successfulScanQuery.isPending ||
    criticalQuery.isPending ||
    highQuery.isPending
  ) {
    return { state: 'loading', retry }
  }

  const latestSuccessfulScan = successfulScanQuery.data
  const { reviewCount, deckFindings, scanItem, coverageItem } = deriveReview({
    latestScan,
    latestSuccessfulScan,
    criticalFindings: criticalQuery.data,
    highFindings: highQuery.data,
    now: new Date(),
  })

  const data: HomeReviewData = {
    reviewCount,
    deckFindings,
    scanItem,
    coverageItem,
    latestSuccessfulScan,
  }

  return reviewCount === 0
    ? { state: 'clear', ...data, retry }
    : { state: 'pending', ...data, retry }
}
