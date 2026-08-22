import { useLocation } from 'react-router'

/** Renders the current route and its state so tests can assert on navigation. */
function LocationProbe() {
  const location = useLocation()
  return (
    <>
      <div data-testid="location-probe">{location.pathname}</div>
      <div data-testid="location-state">{JSON.stringify(location.state)}</div>
    </>
  )
}

export default LocationProbe
