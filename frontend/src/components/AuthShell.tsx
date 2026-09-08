import type { ReactNode } from 'react'

function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center px-4 pt-24">
      <div className="flex w-full max-w-form flex-col items-center gap-6">
        <span className="text-title-md">Dmitri</span>
        <div className="w-full min-w-0 rounded-lg border border-rule bg-card p-6">
          {children}
        </div>
      </div>
    </div>
  )
}

export default AuthShell
