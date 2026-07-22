import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import LoginStub from './LoginStub'
import SignedInPlaceholder from './SignedInPlaceholder'
import { authClient } from '@/api/client'

function TestApp() {
  const [signedIn, setSignedIn] = useState(false)
  if (signedIn) {
    return <SignedInPlaceholder />
  }
  return <LoginStub onSuccess={() => setSignedIn(true)} />
}

describe('LoginStub', () => {
  it('submits credentials through authClient and transitions to SignedInPlaceholder', async () => {
    const user = userEvent.setup()
    const requests: boolean[] = []
    authClient.interceptors.request.use((config) => {
      requests.push(Boolean(config.withCredentials))
      return config
    })

    render(<TestApp />)

    await user.type(screen.getByPlaceholderText('Email'), 'agent@example.com')
    await user.type(screen.getByPlaceholderText('Password'), 'correct-horse')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('Signed in')).toBeInTheDocument()
    expect(requests).toEqual([true])
  })
})
