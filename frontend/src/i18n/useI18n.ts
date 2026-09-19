import { useCallback } from 'react'
import { useLanguage } from './LanguageProvider'
import { getMessage, type MessageKey } from './messages'

function useI18n() {
  const { language } = useLanguage()
  const t = useCallback(
    (key: MessageKey, variables: Record<string, string | number> = {}) =>
      getMessage(language, key, variables),
    [language],
  )
  return { language, t }
}

export default useI18n
