import { useEffect, useId } from 'react'
import { LockKeyhole, Plug } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { disconnectMcp, getMcpConnections, getMcpInfo } from '@/api/mcp'
import { queryKeys } from '@/api/queryKeys'
import { useSession } from '@/auth/useSession'
import { Button } from '@/components/ui/button'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'
import McpSetupGuide from './McpSetupGuide'

export default function McpConnectionsPanel() {
  const { t } = useI18n()
  const { show } = useToast()
  const { user } = useSession()
  const titleId = useId()
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

  useEffect(() => {
    if (info.isError || connections.isError) show(t('mcp.loadError'))
  }, [info.isError, connections.isError, show, t])

  if (!info.data?.enabled || !info.data.url || !user) return null

  return (
    <section
      className="flex min-w-0 flex-col gap-6 border-t border-rule pt-6"
      data-testid="mcp-connections"
      aria-labelledby={titleId}
    >
      <div className="flex items-start gap-4">
        <div className="flex size-12 shrink-0 items-center justify-center rounded-lg border border-rule bg-card">
          <Plug className="size-5" aria-hidden="true" />
        </div>
        <div className="flex flex-col gap-2">
          <h2 id={titleId} className="text-title-sm">
            {t('mcp.title')}
          </h2>
          <p className="max-w-prose text-body-md text-muted-foreground">
            {t('mcp.description')}
          </p>
        </div>
      </div>
      <p className="flex items-start gap-2 text-body-sm text-muted-foreground">
        <LockKeyhole className="size-4 shrink-0" aria-hidden="true" />
        <span>{t('mcp.scope', { organization: user.org_name })}</span>
      </p>
      <McpSetupGuide url={info.data.url} />
      <div className="flex flex-col gap-4 border-t border-rule pt-6">
        <div className="flex flex-col gap-2">
          <h3 className="text-title-xs">{t('mcp.connectionsTitle')}</h3>
          <p className="text-body-sm text-muted-foreground">
            {t('mcp.connectionsHelp')}
          </p>
        </div>
        {connections.isPending && (
          <p role="status" className="text-body-md text-muted-foreground">
            {t('mcp.loading')}
          </p>
        )}
        {connections.isError && (
          <Button
            variant="outline"
            className="self-start"
            onClick={() => void connections.refetch()}
          >
            {t('mcp.retry')}
          </Button>
        )}
        {connections.data?.data.length === 0 && (
          <p className="text-body-md text-muted-foreground">{t('mcp.empty')}</p>
        )}
        <ul className="flex flex-col gap-4">
          {connections.data?.data.map((connection) => (
            <li
              key={connection.id}
              className="flex items-center justify-between gap-4"
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
                disabled={disconnect.isPending}
                onClick={() => disconnect.mutate(connection.id)}
              >
                {t('mcp.disconnect')}
              </Button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
