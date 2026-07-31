import Ornament from '@/components/Ornament'

function HomeBlank() {
  return (
    <div className="flex flex-col items-center gap-6 text-center">
      <p data-testid="home-verdict" className="font-title text-title-lg">
        No scans yet.
      </p>
      <p className="text-body-md text-muted-foreground">
        A scan looks at every machine on your network and reports what an
        attacker could see: which are exposed, and which are running software
        with known vulnerabilities. It takes about ten minutes and changes
        nothing on them.
      </p>
      <p
        data-testid="home-blank-note"
        className="text-body-md text-muted-foreground"
      >
        Scanning is set up on the Pi itself.
      </p>
      <Ornament />
    </div>
  )
}

export default HomeBlank
