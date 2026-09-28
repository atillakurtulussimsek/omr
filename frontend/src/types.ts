export type GroupStatus = 'empty' | 'filled' | 'multi' | 'suspect'

export interface GroupResult {
  value: string
  status: GroupStatus
  fills: number[]
}

export interface FieldResult {
  title: string
  category: 'answers' | 'info'
  value: string
  groups: GroupResult[]
}

export interface Flag {
  field: string
  group: number
  status: string
  message: string
}

export interface PageResult {
  index: number
  ok: boolean
  error: string
  source: { file: string; page: number }
  fields: Record<string, FieldResult>
  flags: Flag[]
  hasAnnotated: boolean
}

export interface Job {
  id: string
  formId: string
  status: 'queued' | 'running' | 'done' | 'error'
  error: string
  total: number
  processed: number
  pages: PageResult[]
}

export interface FormInfo {
  id: string
  name: string
  fieldCount: number
  anchorCount: number
  alignment: Alignment
  timingCount: number
  hasReference: boolean
}

export type FieldType = 'rows' | 'columns'
export type Alignment = 'anchors' | 'timing'

export interface FieldSpec {
  name: string
  title: string
  category: 'answers' | 'info'
  type: FieldType
  x: number
  y: number
  stepX: number
  stepY: number
  rows: number
  cols: number
  labels: string[]
  blank: string
}

export interface ExportFieldItem {
  kind: 'field'
  field: string
  width: number
  align: 'left' | 'right'
  pad: string
  blankAs: string
  multiAs: string
  map: Record<string, string>
}

export type ExportItem = ExportFieldItem | { kind: 'text'; text: string } | { kind: 'space'; width: number }

export interface ExportSpec {
  encoding: 'utf-8' | 'windows-1254'
  items: ExportItem[]
}

export interface FormSpec {
  id: string
  name: string
  width: number
  height: number
  bubbleRadius: number
  anchorSize: number
  anchors: [number, number][]
  alignment?: Alignment
  timingMarks?: [number, number][]
  timingSize?: [number, number]
  fields: FieldSpec[]
  export?: ExportSpec | null
  hasReference: boolean
  rectified?: boolean
}

export interface Detection {
  circles: [number, number, number][]
  anchors: [number, number][]
  bubbleRadius: number
  anchorSize: number
  timingMarks: [number, number][]
  timingSize: [number, number]
}

export interface FmtImport {
  fields: FieldSpec[]
  export: ExportSpec
  report: { matchRatio: number; fieldCount: number; lineWidth: number; warnings: string[] }
}

export interface TestResult {
  ok: boolean
  error: string
  exportLine: string
  fields: Record<string, FieldResult>
  flags: Flag[]
}
