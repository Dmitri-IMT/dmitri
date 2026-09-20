import type { Language } from './LanguageProvider'
import type { Catalog, MessageKey } from './messages/catalog.types'
import { catalog as en } from './messages/en'
import { catalog as pt } from './messages/pt-BR'
import { catalog as ru } from './messages/ru'

export type { MessageKey }

const catalog: Record<Language, Catalog> = { en, 'pt-BR': pt, ru }

export function getMessage(
  language: Language,
  key: MessageKey,
  variables: Record<string, string | number> = {},
) {
  const value = catalog[language][key]
  return typeof value === 'function' ? value(variables) : value
}
