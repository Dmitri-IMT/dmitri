import { useEffect, useState } from 'react'
import { refresh } from '@/api/auth'
import LoginStub from '@/pages/LoginStub'
import SignedInPlaceholder from '@/pages/SignedInPlaceholder'

function App() {
  const [status, setStatus] = useState<'loading' | 'signedIn' | 'signedOut'>(
    'loading',
  )

  useEffect(() => {
    refresh()
      .then(() => setStatus('signedIn'))
      .catch(() => setStatus('signedOut'))
  }, [])

  if (status === 'loading') {
    return (
      <div className="p-4 text-xl font-semibold text-primary">Loading...</div>
    )
  }

  if (status === 'signedIn') {
    return <SignedInPlaceholder />
  }

  return <LoginStub onSuccess={() => setStatus('signedIn')} />
}

export default App
