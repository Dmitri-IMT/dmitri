import { Link } from 'react-router'
import { Button } from '@/components/ui/button'

type NotFoundNoticeProps = {
  message: string
  backTo: string
  backLabel: string
  testId: string
}

function NotFoundNotice({
  message,
  backTo,
  backLabel,
  testId,
}: NotFoundNoticeProps) {
  return (
    <div className="flex flex-col items-center gap-6 py-16 text-center">
      <p data-testid={`${testId}-not-found`} className="text-title-sm">
        {message}
      </p>
      <Button asChild variant="outline">
        <Link to={backTo} data-testid={`${testId}-back`}>
          {backLabel}
        </Link>
      </Button>
    </div>
  )
}

export default NotFoundNotice
