import type { ReactNode } from 'react'
import ErrorRetry from '@/components/ErrorRetry'
import NotFoundNotice from '@/components/NotFoundNotice'
import PageHeader from '@/components/PageHeader'
import type { DetailState } from '@/lib/detailState'

type ReadDetailGateProps<T> = {
  testId: string
  title: string
  notFoundMessage: string
  errorMessage: string
  backTo: string
  backLabel: string
  detail: DetailState<T>
  children: (data: T) => ReactNode
}

function ReadDetailGate<T>({
  testId,
  title,
  notFoundMessage,
  errorMessage,
  backTo,
  backLabel,
  detail,
  children,
}: ReadDetailGateProps<T>) {
  return (
    <div data-testid={testId} className="flex flex-col gap-12">
      {detail.state === 'ready' ? (
        children(detail.data)
      ) : (
        <>
          <PageHeader title={title} />
          {detail.state === 'notFound' && (
            <NotFoundNotice
              testId={testId}
              message={notFoundMessage}
              backTo={backTo}
              backLabel={backLabel}
            />
          )}
          {detail.state === 'error' && (
            <ErrorRetry
              testId={`${testId}-error`}
              message={errorMessage}
              onRetry={detail.retry}
            />
          )}
        </>
      )}
    </div>
  )
}

export default ReadDetailGate
