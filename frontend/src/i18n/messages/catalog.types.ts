export type Value = string | ((v: Record<string, string | number>) => string)
export type Catalog = Record<string, Value>
