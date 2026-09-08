import { Link } from 'react-router'

function NotFound() {
  return (
    <div className="flex flex-col items-center gap-6 pt-24 text-center">
      <p data-testid="not-found" className="text-title-lg">
        That page doesn&apos;t exist.
      </p>
      <Link
        to="/"
        data-testid="not-found-home"
        className="cursor-pointer text-body-md text-accent underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        Go to Home
      </Link>
    </div>
  )
}

export default NotFound
