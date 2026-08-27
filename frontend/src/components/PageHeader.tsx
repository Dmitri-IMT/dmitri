import type { ReactNode } from 'react'

type PageHeaderProps = {
  title: ReactNode
  subtitle?: ReactNode
  testId?: string
}

function PageHeader({ title, subtitle, testId }: PageHeaderProps) {
  return (
    <div data-testid={testId} className="flex flex-col gap-4">
      <div className="flex flex-col gap-3">
        <h1 className="font-title text-title-md">{title}</h1>
        {subtitle !== undefined && (
          <p className="text-body-md text-muted-foreground">{subtitle}</p>
        )}
      </div>
      <hr className="border-border" />
    </div>
  )
}

export default PageHeader
