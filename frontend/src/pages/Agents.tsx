import Ornament from '@/components/Ornament'
import PageHeader from '@/components/PageHeader'
import ErrorRetry from '@/components/ErrorRetry'
import { Button } from '@/components/ui/button'
import { Link } from 'react-router'
import { useAgentScreen } from '@/hooks/useAgentScreen'
import AgentCard from '@/pages/agents/AgentCard'
import AgentsBlank from '@/pages/agents/AgentsBlank'

function Agents() {
  const screen = useAgentScreen()

  return (
    <div data-testid="agents-page" className="flex flex-col gap-12">
      <PageHeader title="Agents" subtitle="The Dmitri box on your network." />
      {screen.state === 'loading' && (
        <div
          data-testid="agents-loading"
          className="flex animate-pulse flex-col gap-6 border border-border bg-card p-6"
        >
          <div className="flex flex-col gap-2">
            <span aria-hidden="true" className="block h-6 w-1/3 bg-border" />
            <span aria-hidden="true" className="block h-4 w-2/5 bg-border" />
          </div>
          <span aria-hidden="true" className="block h-4 w-1/2 bg-border" />
        </div>
      )}
      {screen.state === 'error' && (
        <ErrorRetry
          message="Couldn't load the agents."
          testId="agents-error"
          onRetry={screen.retry}
        />
      )}
      {screen.state === 'blank' && <AgentsBlank />}
      {screen.state === 'ready' && <AgentCard agent={screen.agent} />}
      {screen.state !== 'blank' && (
        <div className="flex flex-col items-center gap-6 text-center">
          <div className="flex max-w-prose flex-col items-center gap-4">
            <p data-testid="agents-note" className="text-body-md">
              Scanning is set up on the Pi itself.
            </p>
            <p className="text-body-md text-muted-foreground">
              The Dmitri box is installed and configured on site. It scans the
              network chosen above and uploads what it finds here.
            </p>
            <p className="text-body-md text-muted-foreground">
              Every scan it runs appears under{' '}
              <Button
                asChild
                variant="link"
                className="h-auto p-0 font-normal focus-visible:underline"
              >
                <Link
                  to="/scans"
                  data-testid="agents-scans-link"
                  className="text-body-md text-primary"
                >
                  Scans
                </Link>
              </Button>
              , and every device it finds appears under{' '}
              <Button
                asChild
                variant="link"
                className="h-auto p-0 font-normal focus-visible:underline"
              >
                <Link
                  to="/hosts"
                  data-testid="agents-hosts-link"
                  className="text-body-md text-primary"
                >
                  Hosts
                </Link>
              </Button>
              .
            </p>
          </div>
          <div className="w-24">
            <Ornament />
          </div>
        </div>
      )}
    </div>
  )
}

export default Agents
