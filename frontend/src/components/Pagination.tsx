import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Pagination as PaginationRoot,
  PaginationContent,
  PaginationItem,
} from '@/components/ui/pagination'
import { dotWindow } from '@/lib/dotWindow'
import useI18n from '@/i18n/useI18n'

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
  const { t } = useI18n()
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
            aria-label={t('common.previousPage')}
            disabled={atFirstPage}
            tabIndex={atFirstPage ? -1 : undefined}
            data-testid={`${testId}-previous`}
            onClick={() => onPageChange(page - 1)}
          >
            <ChevronLeft aria-hidden="true" />
          </Button>
        </PaginationItem>
        {dotWindow(page, pageCount).map((item) => (
          <PaginationItem key={item}>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label={t('common.pageNumber', { page: item })}
              aria-current={item === page ? 'page' : undefined}
              data-testid={`${testId}-page-${item}`}
              onClick={() => onPageChange(item)}
              className="size-9 rounded-full"
            >
              <span
                aria-hidden="true"
                className={`rounded-full transition-all ${
                  item === page
                    ? 'size-2.5 bg-primary'
                    : 'size-2 bg-muted-foreground/40'
                }`}
              />
            </Button>
          </PaginationItem>
        ))}
        <PaginationItem>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={t('common.nextPage')}
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
