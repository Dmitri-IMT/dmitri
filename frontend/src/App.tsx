import { Route, Routes } from 'react-router'
import { RequireSession } from '@/auth/RequireSession'
import AppShell from '@/components/AppShell'
import Login from '@/pages/Login'
import Home from '@/pages/Home'
import NotFound from '@/pages/NotFound'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<RequireSession />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Home />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
