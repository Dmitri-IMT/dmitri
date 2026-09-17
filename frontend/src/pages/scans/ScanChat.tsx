import { useState } from 'react'
import { askScanAI } from '@/api/scans'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'

function ScanChat({ scanId }: { scanId: string }) {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<string | null>(null)
  const [uncertainties, setUncertainties] = useState<string[]>([])
  const [error, setError] = useState(false)
  const [isSending, setIsSending] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = question.trim()
    if (trimmed.length < 3 || isSending) return
    setIsSending(true)
    setError(false)
    try {
      const response = await askScanAI(scanId, trimmed)
      setAnswer(response.answer)
      setUncertainties(response.uncertainties)
    } catch {
      setError(true)
    } finally {
      setIsSending(false)
    }
  }

  return (
    <Card data-testid="scan-chat">
      <CardHeader>
        <h2 className="text-title-sm">Pergunte sobre este scan</h2>
        <p className="text-body-sm text-muted-foreground">
          A resposta usa somente os dados deste scan e pode indicar quando não
          há evidência suficiente.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
          <label className="text-body-sm" htmlFor="scan-question">
            Sua pergunta
          </label>
          <Textarea
            id="scan-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="O que devo corrigir primeiro?"
            maxLength={1000}
          />
          <Button
            type="submit"
            size="sm"
            disabled={isSending || question.trim().length < 3}
          >
            {isSending ? 'Analisando...' : 'Perguntar'}
          </Button>
        </form>
        {answer && (
          <div
            className="rounded-md border border-border p-4"
            aria-live="polite"
          >
            <p className="text-body-md">{answer}</p>
            {uncertainties.length > 0 && (
              <div className="mt-3 text-body-sm text-muted-foreground">
                <p className="font-medium">Limitações</p>
                <ul className="list-disc pl-4">
                  {uncertainties.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {error && (
          <p className="text-body-sm text-destructive" role="alert">
            Não foi possível obter uma resposta agora. Tente novamente.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export default ScanChat
