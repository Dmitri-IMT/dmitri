import { useQuery } from '@tanstack/react-query'
import { listAgents } from '@/api/agents'
import { queryKeys } from '@/api/queryKeys'
import ListSurface from '@/components/ListSurface'
import PageHeader from '@/components/PageHeader'
import { deviceListColumns } from '@/pages/agents/deviceListColumns'
import useI18n from '@/i18n/useI18n'

function Devices() {
  const now = new Date()
  const { t } = useI18n()
  const query = useQuery({
    queryKey: queryKeys.agents.list(),
    queryFn: listAgents,
  })

  return (
    <div data-testid="devices-page" className="flex flex-col gap-12">
      <PageHeader title={t('nav.devices')} subtitle={t('devices.subtitle')} />
      <ListSurface
        testId="devices"
        query={query}
        columns={deviceListColumns(now)}
        rowId={(agent) => agent.agent_id}
        caption={t('devices.caption')}
        errorMessage={t('devices.error')}
        empty={{
          heading: t('devices.emptyHeading'),
          body: t('devices.emptyBody'),
          note: (
            <p
              data-testid="devices-blank-note"
              className="text-body-sm text-muted-foreground"
            >
              {t('devices.emptyNote')}
            </p>
          ),
        }}
        rowAction={{
          kind: 'link',
          to: (agent) => `/devices/${agent.agent_id}`,
          label: (agent) => t('devices.open', { name: agent.display_name }),
        }}
        rowTone={(agent) => (agent.online ? undefined : 'muted')}
      />
    </div>
  )
}

export default Devices
