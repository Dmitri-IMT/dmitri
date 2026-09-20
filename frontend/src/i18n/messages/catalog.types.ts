import type { catalog as en } from './en'

export type MessageKey = keyof typeof en
export type Value = string | ((v: Record<string, string | number>) => string)
export type Catalog = Record<MessageKey, Value>
