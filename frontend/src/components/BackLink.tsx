import { ArrowLeft } from 'lucide-react'
import { Link, useLocation } from 'react-router'
import { Button } from '@/components/ui/button'
import { resolveBackTo } from '@/lib/navFrom'

function BackLink({ fallback, testId }: { fallback: string; testId?: string }) {
  const location = useLocation()

  return (
    <Button
      asChild
      variant="link"
      className="h-auto w-fit gap-2 px-0 py-0 text-body-md text-muted-foreground no-underline"
    >
      <Link to={resolveBackTo(location, fallback)} data-testid={testId}>
        <ArrowLeft aria-hidden="true" className="size-4" />
        Back
      </Link>
    </Button>
  )
}

export default BackLink
