import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { login } from '@/api/auth'

function LoginStub({ onSuccess }: { onSuccess: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    try {
      await login({ email, password })
      onSuccess()
    } catch {
      setError('Invalid email or password')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex max-w-xs flex-col gap-2 p-4">
      <Input
        type="email"
        placeholder="Email"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
      />
      <Input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit">Log in</Button>
    </form>
  )
}

export default LoginStub
