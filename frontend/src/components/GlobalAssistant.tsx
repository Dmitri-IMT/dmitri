import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { BotIcon } from 'lucide-react'
import ContextChat from '@/components/ContextChat'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

type AssistantContext = {
  scope: 'scan' | 'host'
  contextId: string
  label: string
}

function GlobalAssistant() {
  const location = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const context = useMemo<AssistantContext | null>(() => {
    const scanMatch = location.pathname.match(/^\/scans\/([^/]+)$/)
    if (scanMatch) {
      return { scope: 'scan', contextId: scanMatch[1], label: 'este scan' }
    }
    const hostMatch = location.pathname.match(/^\/network\/([^/]+)$/)
    if (hostMatch) {
      return {
        scope: 'host',
        contextId: hostMatch[1],
        label: 'este equipamento',
      }
    }
    return null
  }, [location.pathname])

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          className="fixed right-6 bottom-6 z-40 shadow-lg"
          aria-label="Abrir assistente de segurança"
        >
          <BotIcon />
          Assistente IA
        </Button>
      </DialogTrigger>
      <DialogContent className="max-h-screen overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Pergunte ao DMITRI</DialogTitle>
        </DialogHeader>
        {context ? (
          <ContextChat
            scope={context.scope}
            contextId={context.contextId}
            title={`Pergunte sobre ${context.label}`}
          />
        ) : (
          <div className="flex flex-col gap-4">
            <p className="text-body-md text-muted-foreground">
              Selecione qual scan você quer tirar suas dúvidas!
            </p>
            <Button
              type="button"
              onClick={() => {
                setOpen(false)
                navigate('/scans')
              }}
            >
              Ver scans
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default GlobalAssistant
