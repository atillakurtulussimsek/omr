import type { Detection, FieldSpec, FieldType } from '../types'

export const DIGITS = '0123456789'.split('')
export const TR_LETTERS = 'ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ'.split('')
export const EN_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('')

export interface Rect {
  x0: number
  y0: number
  x1: number
  y1: number
}

/** Sıralı değerleri `gap`ten yakın olanlar aynı kümede olacak şekilde gruplar; küme ortalamalarını döner. */
function cluster(values: number[], gap: number): { center: number; count: number }[] {
  const sorted = [...values].sort((a, b) => a - b)
  const groups: number[][] = []
  for (const v of sorted) {
    const last = groups[groups.length - 1]
    if (last && v - last[last.length - 1] < gap) last.push(v)
    else groups.push([v])
  }
  return groups.map((g) => ({ center: g.reduce((a, b) => a + b, 0) / g.length, count: g.length }))
}

function axisGrid(values: number[], gap: number): { start: number; step: number; count: number } {
  let groups = cluster(values, gap)
  const most = Math.max(...groups.map((g) => g.count))
  groups = groups.filter((g) => g.count >= Math.max(1, most * 0.3)) // tek tük yanlış çemberleri at
  const count = groups.length
  const start = groups[0].center
  const step = count > 1 ? (groups[count - 1].center - start) / (count - 1) : 0
  return { start, step, count }
}

export function defaultLabels(optionCount: number, type: FieldType): string[] {
  if (optionCount === 10) return DIGITS
  if (optionCount === 29) return TR_LETTERS
  if (optionCount === 26) return EN_LETTERS
  if (type === 'rows' && optionCount <= 26) return EN_LETTERS.slice(0, optionCount)
  return Array.from({ length: optionCount }, (_, i) => String(i + 1))
}

export function uniqueName(base: string, fields: FieldSpec[]): string {
  const names = new Set(fields.map((f) => f.name))
  let name = base
  for (let n = 2; names.has(name); n++) name = `${base}${n}`
  return name
}

/** Çizilen dikdörtgenin içindeki algılanmış baloncuklardan alan üretir; baloncuk yoksa null. */
export function fieldFromRect(rect: Rect, detection: Detection, fields: FieldSpec[], pitch: number): FieldSpec | null {
  // yarısından fazlası dikdörtgene giren baloncuklar dahil
  const pad = detection.bubbleRadius * 0.5
  const inside = detection.circles.filter(
    ([x, y]) => x >= rect.x0 - pad && x <= rect.x1 + pad && y >= rect.y0 - pad && y <= rect.y1 + pad,
  )
  if (inside.length === 0) return null
  const gap = Math.max(6, detection.bubbleRadius * 0.8)
  const gx = axisGrid(inside.map((c) => c[0]), gap)
  const gy = axisGrid(inside.map((c) => c[1]), gap)
  // seçenek sayısı az olan eksen "seçenek" eksenidir: 5 şıklı cevap satırı -> rows, 10 rakamlı sütun -> columns
  const type: FieldType = gx.count <= 6 && gy.count !== 10 && gy.count !== 29 && gx.count > 1 ? 'rows' : 'columns'
  const optionCount = type === 'rows' ? gx.count : gy.count
  const isAnswers = type === 'rows' && gy.count > 1
  const round = (v: number) => Math.round(v * 10) / 10
  return {
    name: uniqueName(isAnswers ? 'ders' : 'alan', fields),
    title: isAnswers ? 'Ders' : 'Alan',
    category: isAnswers ? 'answers' : 'info',
    type,
    x: round(gx.start),
    y: round(gy.start),
    stepX: round(gx.step || pitch),
    stepY: round(gy.step || pitch),
    rows: gy.count,
    cols: gx.count,
    labels: defaultLabels(optionCount, type),
    blank: isAnswers ? '-' : optionCount === 10 ? '_' : ' ',
  }
}

export const optionCount = (f: FieldSpec) => (f.type === 'rows' ? f.cols : f.rows)
export const groupCount = (f: FieldSpec) => (f.type === 'rows' ? f.rows : f.cols)

export function fieldBounds(f: FieldSpec, radius: number): Rect {
  const pad = radius + 5
  return {
    x0: f.x - pad,
    y0: f.y - pad,
    x1: f.x + (f.cols - 1) * f.stepX + pad,
    y1: f.y + (f.rows - 1) * f.stepY + pad,
  }
}

/** Satır/sütun sayısı veya tip değişince etiket sayısını seçenek sayısına uydurur. */
export function fitLabels(f: FieldSpec): FieldSpec {
  const count = optionCount(f)
  if (f.labels.length === count) return f
  const defaults = defaultLabels(count, f.type)
  const keep = f.labels.every((l, i) => l === defaultLabels(f.labels.length, f.type)[i]) ? [] : f.labels
  return { ...f, labels: Array.from({ length: count }, (_, i) => keep[i] ?? defaults[i]) }
}

export function estimatePitch(fields: FieldSpec[], detection: Detection | null): number {
  const steps = fields.flatMap((f) => [f.cols > 1 ? f.stepX : 0, f.rows > 1 ? f.stepY : 0]).filter((s) => s > 0)
  if (steps.length) return Math.min(...steps)
  return detection?.bubbleRadius ? detection.bubbleRadius * 2.5 : 40
}
