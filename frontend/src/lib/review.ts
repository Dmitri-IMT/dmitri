import type { components } from '@/types/openapi'

type ScanSummary = components['schemas']['ScanSummary']
type FindingRecord = components['schemas']['FindingRecord']
type FindingListResponse = components['schemas']['FindingListResponse']

export const STALE_COVERAGE_DAYS = 3

export interface ScanItem {
  scan: ScanSummary
}

export interface CoverageItem {
  latestSuccessfulScan: ScanSummary
  daysSinceLastSuccess: number
}

export interface DeriveReviewInput {
  latestScan: ScanSummary | null
  latestSuccessfulScan: ScanSummary | null
  criticalFindings: FindingListResponse
  highFindings: FindingListResponse
  now: Date
}

export interface DeriveReviewResult {
  reviewCount: number
  deckFindings: FindingRecord[]
  scanItem: ScanItem | null
  coverageItem: CoverageItem | null
}

function byNewestFirst(a: FindingRecord, b: FindingRecord): number {
  return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime()
}

export function deriveReview({
  latestScan,
  latestSuccessfulScan,
  criticalFindings,
  highFindings,
  now,
}: DeriveReviewInput): DeriveReviewResult {
  const deckFindings = [
    ...[...criticalFindings.data].sort(byNewestFirst),
    ...[...highFindings.data].sort(byNewestFirst),
  ]

  const scanItem: ScanItem | null =
    latestScan?.status === 'failed' ? { scan: latestScan } : null

  let coverageItem: CoverageItem | null = null
  if (latestSuccessfulScan !== null) {
    const daysSinceLastSuccess = Math.floor(
      (now.getTime() - new Date(latestSuccessfulScan.timestamp).getTime()) /
        (1000 * 60 * 60 * 24),
    )
    if (daysSinceLastSuccess >= STALE_COVERAGE_DAYS) {
      coverageItem = { latestSuccessfulScan, daysSinceLastSuccess }
    }
  }

  const reviewCount =
    criticalFindings.total +
    highFindings.total +
    (scanItem !== null ? 1 : 0) +
    (coverageItem !== null ? 1 : 0)

  return { reviewCount, deckFindings, scanItem, coverageItem }
}
