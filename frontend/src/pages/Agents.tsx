import Ornament from '@/components/Ornament'
import PageHeader from '@/components/PageHeader'

function Agents() {
  return (
    <div data-testid="agents-page" className="flex flex-col">
      <PageHeader
        title="Agents"
        subtitle="The Dmitri box on your network."
      />
      <div className="flex flex-col items-center gap-6 py-16 text-center">
        <div className="flex max-w-prose flex-col items-center gap-4">
          <p data-testid="agents-note" className="font-title text-title-lg">
            Scanning is set up on the Pi itself.
          </p>
          <p className="text-body-md text-muted-foreground">
            The Dmitri box is installed and configured on site. It scans the
            network it is connected to and uploads what it finds here.
          </p>
          <p className="text-body-md text-muted-foreground">
            Every scan it runs appears under Scans, and every device it finds
            appears under Hosts.
          </p>
        </div>
        <div className="w-24">
          <Ornament />
        </div>
      </div>
    </div>
  )
}

export default Agents
