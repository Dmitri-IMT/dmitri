import { createContext, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

export type Language = 'en' | 'pt-BR' | 'ru'

export const LANGUAGE_STORAGE_KEY = 'dmitri-language'

export const LANGUAGE_OPTIONS: ReadonlyArray<{
  value: Language
  label: string
}> = [
  { value: 'en', label: 'English' },
  { value: 'pt-BR', label: 'Português' },
  { value: 'ru', label: 'Русский' },
]

function readStoredLanguage(): Language {
  const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY)
  return LANGUAGE_OPTIONS.some((option) => option.value === stored)
    ? (stored as Language)
    : 'en'
}

type LanguageContextValue = {
  language: Language
  setLanguage: (language: Language) => void
}

const LanguageContext = createContext<LanguageContextValue>({
  language: 'en',
  setLanguage: () => undefined,
})

function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(readStoredLanguage)

  const value = useMemo<LanguageContextValue>(
    () => ({
      language,
      setLanguage: (nextLanguage) => {
        setLanguageState(nextLanguage)
        localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage)
      },
    }),
    [language],
  )

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  )
}

function useLanguage() {
  return useContext(LanguageContext)
}

export { LanguageProvider, useLanguage }
