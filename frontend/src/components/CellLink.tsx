import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router'
import { fromHere } from '@/lib/navFrom'

function CellLink({ to, children }: { to: string; children: ReactNode }) {
  const location = useLocation()

  return (
    <Link
      to={to}
      state={fromHere(location)}
      className="block max-w-full cursor-pointer truncate underline-offset-4 outline-none hover:underline focus-visible:underline focus-visible:ring-3 focus-visible:ring-ring/50 active:decoration-2"
    >
      {children}
    </Link>
  )
}

export default CellLink
