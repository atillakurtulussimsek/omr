import type { ExportFieldItem, ExportItem, ExportSpec, FieldSpec } from '../types'
import { groupCount } from './fieldUtils'

/** Alanın dönüşümsüz değerinin kapladığı karakter sayısı. */
export const fieldWidth = (f: FieldSpec) => groupCount(f) * Math.max(...f.labels.map((l) => l.length), 1)

export const fieldItem = (f: FieldSpec): ExportFieldItem => ({
  kind: 'field', field: f.name, width: fieldWidth(f), align: 'left', pad: ' ', blankAs: ' ', multiAs: '*', map: {},
})

/** Backend'deki defaultExport ile aynı: alanlar şablon sırasıyla, aralarında birer boşluk. */
export function defaultExport(fields: FieldSpec[]): ExportSpec {
  const items: ExportItem[] = []
  fields.forEach((f) => {
    if (items.length) items.push({ kind: 'space', width: 1 })
    items.push(fieldItem(f))
  })
  return { encoding: 'utf-8', items }
}

export const itemWidth = (item: ExportItem) => (item.kind === 'text' ? item.text.length : item.width)

export const mapToText = (map: Record<string, string>) =>
  Object.entries(map).map(([k, v]) => `${k}=${v}`).join(', ')

export function textToMap(text: string): Record<string, string> {
  const map: Record<string, string> = {}
  text.split(',').forEach((pair) => {
    const at = pair.indexOf('=')
    if (at > 0) map[pair.slice(0, at).trim()] = pair.slice(at + 1).trim()
  })
  return map
}
