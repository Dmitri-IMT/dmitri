import { useState } from 'react'
import { MoonIcon, SunIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'

const THEME_STORAGE_KEY = 'dmitri-theme'

function initialDarkMode() {
  return document.documentElement.classList.contains('dmitri-dark')
}

function ThemeToggle() {
  const [isDark, setIsDark] = useState(initialDarkMode)

  function toggleTheme() {
    const next = !isDark
    document.documentElement.classList.toggle('dmitri-dark', next)
    localStorage.setItem(THEME_STORAGE_KEY, next ? 'dark' : 'light')
    setIsDark(next)
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      aria-label={isDark ? 'Ativar modo claro' : 'Ativar modo noturno'}
      title={isDark ? 'Modo claro' : 'Modo noturno'}
      onClick={toggleTheme}
    >
      {isDark ? <SunIcon /> : <MoonIcon />}
    </Button>
  )
}

export { THEME_STORAGE_KEY }
export default ThemeToggle
