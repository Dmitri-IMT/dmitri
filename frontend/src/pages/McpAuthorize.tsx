import { useEffect } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router'
import { useMutation, useQuery } from '@tanstack/react-query'
import { decideMcpAuthorization, getMcpAuthorization } from '@/api/mcp'
import { queryKeys } from '@/api/queryKeys'
import { useSession } from '@/auth/useSession'
import AuthShell from '@/components/AuthShell'
import ToastProvider from '@/components/Toast'
import { Button } from '@/components/ui/button'
import { useToast } from '@/hooks/useToast'
import useI18n from '@/i18n/useI18n'

function AuthorizationContent() {
  const [search] = useSearchParams()
  const requestToken = search.get('request') ?? ''
  const valid = /^[A-Za-z0-9_-]{43}$/.test(requestToken)
  const { status } = useSession()
  const { show } = useToast()
  const { t } = useI18n()
  const query = useQuery({
    queryKey: queryKeys.mcp.authorization(requestToken),
    queryFn: () => getMcpAuthorization(requestToken),
    enabled: valid && status === 'authenticated',
    retry: false,
    refetchOnWindowFocus: false,
    gcTime: 0,
  })
  const decision = useMutation({
    mutationFn: (approve: boolean) =>
      decideMcpAuthorization({ request_token: requestToken, approve }),
    onSuccess: (result) => window.location.assign(result.redirect_url),
    onError: () => show(t('mcp.connectError')),
  })

  useEffect(() => {
    if (!valid || query.isError) show(t('mcp.requestError'))
  }, [valid, query.isError, show, t])

  if (status === 'booting') return null
  if (status === 'anonymous' && valid) {
    return <Navigate to={`/login?mcp_request=${requestToken}`} replace />
  }

  return (
    <AuthShell>
      <meta name="referrer" content="no-referrer" />
      <div className="flex flex-col gap-6" data-testid="mcp-authorization">
        <h1 className="text-title-sm">{t('mcp.connectTitle')}</h1>
        {!valid || query.isError ? (
          <Button asChild variant="outline">
            <Link to="/settings">{t('mcp.back')}</Link>
          </Button>
        ) : query.isPending ? (
          <p role="status" className="text-body-md text-muted-foreground">
            {t('mcp.loading')}
          </p>
        ) : (
          <>
            <dl className="flex flex-col gap-4 text-body-md">
              <div>
                <dt className="text-muted-foreground">{t('mcp.client')}</dt>
                <dd className="break-words">{query.data.client_name}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">{t('mcp.account')}</dt>
                <dd className="break-words">{query.data.email}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">
                  {t('mcp.organization')}
                </dt>
                <dd className="break-words">{query.data.organization}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">{t('mcp.callback')}</dt>
                <dd className="break-all">{query.data.redirect_uri}</dd>
              </div>
            </dl>
            <p className="text-body-md">{t('mcp.consent')}</p>
            <p className="text-body-sm text-muted-foreground">
              {t('mcp.disclosure')}
            </p>
            <div className="flex flex-col gap-2">
              <Button
                onClick={() => decision.mutate(true)}
                disabled={decision.isPending}
              >
                {decision.isPending ? t('mcp.connecting') : t('mcp.allow')}
              </Button>
              <Button
                variant="outline"
                onClick={() => decision.mutate(false)}
                disabled={decision.isPending}
              >
                {t('mcp.deny')}
              </Button>
            </div>
          </>
        )}
      </div>
    </AuthShell>
  )
}

export default function McpAuthorize() {
  return (
    <ToastProvider>
      <AuthorizationContent />
    </ToastProvider>
  )
}
