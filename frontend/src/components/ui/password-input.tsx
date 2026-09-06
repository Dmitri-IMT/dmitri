import * as React from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

function EyeMark({ revealed }: { revealed: boolean }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d="M1.6 10S4.9 4.8 10 4.8 18.4 10 18.4 10 15.1 15.2 10 15.2 1.6 10 1.6 10Z" />
      <circle cx="10" cy="10" r="2.6" />
      {revealed && <path d="M4 16 16 4" />}
    </svg>
  )
}

function PasswordInput({
  className,
  ...props
}: Omit<React.ComponentProps<'input'>, 'type'>) {
  const [revealed, setRevealed] = React.useState(false)

  return (
    <div className="relative">
      <Input
        {...props}
        type={revealed ? 'text' : 'password'}
        className={cn('pr-9', className)}
      />
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={revealed ? 'Hide password' : 'Show password'}
        onClick={() => setRevealed((current) => !current)}
        className="absolute inset-y-0 right-1 my-auto text-muted-foreground hover:text-foreground"
      >
        <EyeMark revealed={revealed} />
      </Button>
    </div>
  )
}

export { PasswordInput }
