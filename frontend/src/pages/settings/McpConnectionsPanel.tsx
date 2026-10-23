import { useEffect, useId, useState } from 'react'
import { X } from 'lucide-react'
import { Dialog } from 'radix-ui'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { disconnectMcp, getMcpConnections, getMcpInfo } from '@/api/mcp'
import { queryKeys } from '@/api/queryKeys'
import { useSession } from '@/auth/useSession'
import DialogShell from '@/components/DialogShell'
import { Button } from '@/components/ui/button'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'
import McpSetupGuide from './McpSetupGuide'

export default function McpConnectionsPanel() {
  const { t } = useI18n()
  const { show } = useToast()
  const { user } = useSession()
  const titleId = useId()
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const info = useQuery({
    queryKey: queryKeys.mcp.info(),
    queryFn: getMcpInfo,
    retry: false,
  })
  const connections = useQuery({
    queryKey: queryKeys.mcp.connections(user?.user_id ?? ''),
    queryFn: getMcpConnections,
    enabled: info.data?.enabled === true && user !== null,
    retry: false,
  })
  const disconnect = useMutation({
    mutationFn: disconnectMcp,
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: queryKeys.mcp.connections(user?.user_id ?? ''),
      }),
    onError: () => show(t('mcp.disconnectError')),
  })
  const turnOff = useMutation({
    mutationFn: async () => {
      const results = await Promise.allSettled(
        (connections.data?.data ?? []).map((connection) =>
          disconnectMcp(connection.id),
        ),
      )
      if (results.some((result) => result.status === 'rejected')) {
        throw new Error('MCP disconnect failed')
      }
    },
    onSuccess: () => show(t('mcp.turnedOff')),
    onError: () => show(t('mcp.turnOffError')),
    onSettled: () =>
      queryClient.invalidateQueries({
        queryKey: queryKeys.mcp.connections(user?.user_id ?? ''),
      }),
  })

  useEffect(() => {
    if (info.isError || connections.isError) show(t('mcp.loadError'))
  }, [info.isError, connections.isError, show, t])

  if (!info.data?.enabled || !info.data.url || !user) return null

  const isConnected = (connections.data?.data.length ?? 0) > 0
  const isBusy = disconnect.isPending || turnOff.isPending

  return (
    <section
      className="flex min-w-0 flex-col gap-4"
      data-testid="mcp-connections"
      aria-labelledby={titleId}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-2">
          <h2 id={titleId} className="text-title-sm">
            {t('mcp.title')}
          </h2>
          <p className="max-w-prose text-body-md text-muted-foreground">
            {t('mcp.description')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span role="status" className="text-body-sm text-muted-foreground">
            {connections.isPending
              ? t('mcp.loading')
              : connections.isError
                ? null
                : t(isConnected ? 'mcp.on' : 'mcp.off')}
          </span>
          {(isConnected || connections.isError) && (
            <Button variant="outline" onClick={() => setIsOpen(true)}>
              {t('mcp.configure')}
            </Button>
          )}
          {!connections.isError && (
            <Button
              variant={isConnected ? 'outline' : 'default'}
              disabled={isBusy || connections.isPending}
              onClick={() => (isConnected ? turnOff.mutate() : setIsOpen(true))}
            >
              {turnOff.isPending
                ? t('mcp.turningOff')
                : t(isConnected ? 'mcp.turnOff' : 'mcp.turnOn')}
            </Button>
          )}
        </div>
      </div>
      {connections.isError && (
        <Button
          variant="outline"
          className="self-start"
          onClick={() => void connections.refetch()}
        >
          {t('mcp.retry')}
        </Button>
      )}
      <DialogShell
        open={isOpen}
        onOpenChange={setIsOpen}
        testId="mcp-setup-dialog"
        size="wide"
        locked={isBusy}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-2">
            <Dialog.Title className="text-title-sm">
              {t('mcp.title')}
            </Dialog.Title>
            <Dialog.Description className="text-body-md text-muted-foreground">
              {t('mcp.description')}
            </Dialog.Description>
          </div>
          <Dialog.Close asChild>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t('mcp.close')}
              disabled={isBusy}
            >
              <X aria-hidden="true" />
            </Button>
          </Dialog.Close>
        </div>
        <McpSetupGuide url={info.data.url} />
        <div className="flex flex-col gap-4 border-t border-rule pt-6">
          <div className="flex flex-col gap-2">
            <h3 className="text-title-xs">{t('mcp.connectionsTitle')}</h3>
            <p className="text-body-sm text-muted-foreground">
              {t('mcp.connectionsHelp')}
            </p>
            <p className="text-body-sm text-muted-foreground">
              {t('mcp.turnOffHelp')}
            </p>
          </div>
          {connections.data?.data.length === 0 && (
            <p className="text-body-md text-muted-foreground">
              {t('mcp.empty')}
            </p>
          )}
          <ul className="flex flex-col gap-4">
            {connections.data?.data.map((connection) => (
              <li
                key={connection.id}
                className="flex flex-wrap items-center justify-between gap-4"
              >
                <div className="flex min-w-0 flex-col gap-1">
                  <span className="break-words text-body-md">
                    {connection.client_name}
                  </span>
                  <span className="text-body-sm text-muted-foreground">
                    {t('mcp.expires')}{' '}
                    {new Date(connection.expires_at).toLocaleDateString()}
                  </span>
                </div>
                <Button
                  variant="outline"
                  aria-label={`${t('mcp.disconnect')} ${connection.client_name}`}
                  disabled={isBusy}
                  onClick={() => disconnect.mutate(connection.id)}
                >
                  {t('mcp.disconnect')}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      </DialogShell>
    </section>
  )
}
