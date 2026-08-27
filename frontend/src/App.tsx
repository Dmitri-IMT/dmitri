import { Route, Routes } from 'react-router'
import { RequireAdmin } from '@/auth/RequireAdmin'
import { RequireSession } from '@/auth/RequireSession'
import AppShell from '@/components/AppShell'
import Login from '@/pages/Login'
import ForgotPassword from '@/pages/ForgotPassword'
import ResetPassword from '@/pages/ResetPassword'
import AcceptInvite from '@/pages/AcceptInvite'
import Home from '@/pages/Home'
import Scans from '@/pages/Scans'
import ScanDetail from '@/pages/ScanDetail'
import Hosts from '@/pages/Hosts'
import HostDetail from '@/pages/HostDetail'
import Agents from '@/pages/Agents'
import Settings from '@/pages/Settings'
import Users from '@/pages/Users'
import NotFound from '@/pages/NotFound'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/invite" element={<AcceptInvite />} />
      <Route element={<RequireSession />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Home />} />
          <Route path="/scans" element={<Scans />} />
          <Route path="/scans/:scanId" element={<ScanDetail />} />
          <Route path="/hosts" element={<Hosts />} />
          <Route path="/hosts/:hostId" element={<HostDetail />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/settings" element={<Settings />} />
          <Route element={<RequireAdmin />}>
            <Route path="/users" element={<Users />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
