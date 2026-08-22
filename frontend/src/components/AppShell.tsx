import { Outlet } from 'react-router'
import ToastProvider from '@/components/Toast'
import TopBar from '@/components/TopBar'

function AppShell() {
  return (
    <ToastProvider>
      <div className="flex min-h-screen flex-col">
        <TopBar />
        <main className="mx-auto w-full min-w-0 max-w-frame flex-1 px-4 py-12">
          <Outlet />
        </main>
      </div>
    </ToastProvider>
  )
}

export default AppShell
