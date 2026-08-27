import { Button } from '@/components/ui/button'

type PaginationProps = {
  page: number
  perPage: number
  total: number
  onPageChange: (page: number) => void
  testId: string
}

function Pagination({
  page,
  perPage,
  total,
  onPageChange,
  testId,
}: PaginationProps) {
  if (total <= perPage) return null

  const first = (page - 1) * perPage + 1
  const last = Math.min(page * perPage, total)
  const atFirstPage = page === 1
  const atLastPage = page * perPage >= total

  return (
    <nav
      aria-label="Pagination"
      data-testid={`${testId}-pagination`}
      className="flex items-center justify-between gap-4"
    >
      <p
        data-testid={`${testId}-range`}
        className="text-caption-md text-muted-foreground"
      >
        Showing {first}–{last} of {total}
      </p>
      <div className="flex items-center gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={atFirstPage}
          tabIndex={atFirstPage ? -1 : undefined}
          data-testid={`${testId}-previous`}
          className="border-input text-body-sm"
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={atLastPage}
          tabIndex={atLastPage ? -1 : undefined}
          data-testid={`${testId}-next`}
          className="border-input text-body-sm"
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </nav>
  )
}

export default Pagination
