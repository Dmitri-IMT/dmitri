import { cn } from '@/lib/utils'

type LoadingSkeletonProps = {
  rows: number
  columns: number
}

const BAR_WIDTHS = ['w-3/4', 'w-2/3', 'w-4/5'] as const

function LoadingSkeleton({ rows, columns }: LoadingSkeletonProps) {
  return (
    <tbody>
      {Array.from({ length: rows }, (_, row) => (
        <tr key={row} className="h-8 border-t border-border">
          {Array.from({ length: columns }, (_, column) => (
            <td key={column} className="h-8 pr-4 align-middle">
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
