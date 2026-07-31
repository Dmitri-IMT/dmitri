import { Outlet } from 'react-router'
import TopBar from '@/components/TopBar'

function AppShell() {
  return (
    <div className="flex min-h-screen flex-col">
      <TopBar />
      <main className="mx-auto w-full min-w-0 max-w-[45rem] flex-1 px-4 py-12">
        <Outlet />
      </main>
    </div>
  )
}

export default AppShell
