import { useEffect, useState } from 'react'

// A fast read finishes before this, so its placeholder never flashes on screen.
export const SKELETON_DELAY_MS = 250

export function useSkeletonDelay(): boolean {
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), SKELETON_DELAY_MS)
    return () => clearTimeout(timer)
  }, [])

  return isVisible
}
