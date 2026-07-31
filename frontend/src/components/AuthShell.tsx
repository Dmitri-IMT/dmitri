import type { ReactNode } from 'react'
import Ornament from '@/components/Ornament'

function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-4">
      <div className="flex w-full max-w-[45rem] flex-col items-center gap-4">
        <span className="font-title text-title-md tracking-wide">DMITRI</span>
        <Ornament />
        <div className="w-full min-w-0 border border-rule bg-card p-6">
          {children}
        </div>
      </div>
    </div>
  )
}

export default AuthShell
