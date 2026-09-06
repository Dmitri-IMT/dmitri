import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Pagination as PaginationRoot,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
} from '@/components/ui/pagination'
import { pageWindow } from '@/lib/pageWindow'

type PaginationProps = {
  page: number
  perPage: number
  total: number
  onPageChange: (page: number) => void
  testId: string
  label: string
}

function Pagination({
  page,
  perPage,
  total,
  onPageChange,
  testId,
  label,
}: PaginationProps) {
  if (total <= perPage) return null

  const pageCount = Math.ceil(total / perPage)
  const atFirstPage = page === 1
  const atLastPage = page >= pageCount

  return (
    <PaginationRoot aria-label={label} data-testid={`${testId}-pagination`}>
      <PaginationContent>
        <PaginationItem>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Previous page"
            disabled={atFirstPage}
            tabIndex={atFirstPage ? -1 : undefined}
            data-testid={`${testId}-previous`}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft aria-hidden="true" />
          </Button>
        </PaginationItem>
        {pageWindow(page, pageCount).map((item, index) =>
          item === 'ellipsis' ? (
            <PaginationItem key={`ellipsis-${index}`}>
              <PaginationEllipsis />
            </PaginationItem>
          ) : (
            <PaginationItem key={item}>
              <Button
                type="button"
                variant={item === page ? 'outline' : 'ghost'}
                size="icon"
                aria-current={item === page ? 'page' : undefined}
                data-testid={`${testId}-page-${item}`}
                className="text-body-sm"
                onClick={() => onPageChange(item)}
              >
                {item}
              </Button>
            </PaginationItem>
          ),
        )}
        <PaginationItem>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Next page"
            disabled={atLastPage}
            tabIndex={atLastPage ? -1 : undefined}
            data-testid={`${testId}-next`}
            onClick={() => onPageChange(page + 1)}
          >
            <ChevronRight aria-hidden="true" />
          </Button>
        </PaginationItem>
      </PaginationContent>
    </PaginationRoot>
  )
}

export default Pagination
