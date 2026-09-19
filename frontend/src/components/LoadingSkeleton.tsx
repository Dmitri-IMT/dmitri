import { useSkeletonDelay } from '@/hooks/useSkeletonDelay'
import { cn } from '@/lib/utils'
import { UI_COPY } from '@/lib/copy'
import { useLanguage } from '@/i18n/LanguageProvider'

type LoadingSkeletonProps = {
  rows: number
  columns: number
  id?: string
  testId?: string
}

const BAR_WIDTHS = ['w-3/4', 'w-2/3', 'w-4/5'] as const

function LoadingSkeleton({ rows, columns, id, testId }: LoadingSkeletonProps) {
  const isVisible = useSkeletonDelay()
  const { language } = useLanguage()

  return (
    <tbody
      id={id}
      data-testid={testId}
      aria-label={UI_COPY[language].loadingData}
      aria-busy={!isVisible}
    >
      {isVisible &&
        Array.from({ length: rows }, (_, row) => (
          <tr key={row} className="h-row border-t border-border">
            {Array.from({ length: columns }, (_, column) => (
              <td key={column} className="h-row pr-4 align-middle">
                <span
                  className={cn(
                    'block h-3 bg-border',
                    BAR_WIDTHS[column % BAR_WIDTHS.length],
                  )}
                />
              </td>
            ))}
          </tr>
        ))}
    </tbody>
  )
}

export default LoadingSkeleton
