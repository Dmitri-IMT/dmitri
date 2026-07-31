import { Link } from 'react-router'

function NotFound() {
  return (
    <div className="flex flex-col items-center gap-6 text-center">
      <p data-testid="not-found" className="font-title text-title-lg">
        That page doesn&apos;t exist.
      </p>
      <Link
        to="/"
        data-testid="not-found-home"
        className="text-accent underline"
      >
        Go to Home
      </Link>
    </div>
  )
}

export default NotFound
