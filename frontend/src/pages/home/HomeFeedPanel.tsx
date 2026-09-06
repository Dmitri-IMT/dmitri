import type { ReactNode } from 'react'
import Pagination from '@/components/Pagination'

/** The panel card: shared with Home's loading skeleton so the two cannot drift. */
export const HOME_PANEL_CHROME =
  'flex flex-col gap-4 rounded-lg border border-rule bg-card p-6'

type HomeFeedPanelProps = {
  testId: string
  title: string
  emptyText: string
  isBlank: boolean
  total: number
  page: number
  perPage: number
  onPageChange: (page: number) => void
  label: string
  children?: ReactNode
}

function HomeFeedPanel({
  testId,
  title,
  emptyText,
  isBlank,
  total,
  page,
  perPage,
  onPageChange,
  label,
  children,
}: HomeFeedPanelProps) {
  return (
    <section
      id={`${testId}-panel`}
      className={HOME_PANEL_CHROME}
    >
      <h2 data-testid={`${testId}-heading`} className="text-title-xs font-semibold">
        {title}
      </h2>
      {isBlank ? (
        <p
          data-testid={`${testId}-blank`}
          className="text-body-md text-muted-foreground"
        >
          {emptyText}
        </p>
      ) : (
        <ul data-testid={`${testId}-list`} className="flex flex-col">
          {children}
        </ul>
      )}
      <Pagination
        page={page}
        perPage={perPage}
        total={total}
        onPageChange={onPageChange}
        testId={testId}
        label={label}
      />
    </section>
  )
}

export default HomeFeedPanel
