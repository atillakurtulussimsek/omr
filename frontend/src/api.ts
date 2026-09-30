import type { Detection, FmtImport, FormInfo, FormSpec, Job, PageResult, TestResult } from './types'

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(body?.detail ?? `Sunucu hatası (${res.status})`)
  }
  return res.json()
}

export const getForms = () => fetch('/api/forms').then((r) => parse<FormInfo[]>(r))

export const getJob = (jobId: string) => fetch(`/api/jobs/${jobId}`).then((r) => parse<Job>(r))

export function createJob(files: File[], formId: string): Promise<Job> {
  const body = new FormData()
  files.forEach((f) => body.append('files', f))
  body.append('formId', formId)
  return fetch('/api/jobs', { method: 'POST', body }).then((r) => parse<Job>(r))
}

export const editPage = (jobId: string, index: number, edits: Record<string, Record<string, string>>) =>
  fetch(`/api/jobs/${jobId}/pages/${index}`, json('PUT', edits)).then((r) => parse<PageResult>(r))

export const exportTxtUrl = (jobId: string) => `/api/jobs/${jobId}/export.txt`
export const annotatedZipUrl = (jobId: string) => `/api/jobs/${jobId}/annotated.zip`
export const annotatedUrl = (jobId: string, index: number, download = false) =>
  `/api/jobs/${jobId}/pages/${index}/annotated.jpg${download ? '?download=true' : ''}`

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

function fileBody(file: File, extra: Record<string, string> = {}): FormData {
  const body = new FormData()
  body.append('file', file)
  Object.entries(extra).forEach(([k, v]) => body.append(k, v))
  return body
}

export const getForm = (formId: string) => fetch(`/api/forms/${formId}`).then((r) => parse<FormSpec>(r))
export const getDetection = (formId: string) =>
  fetch(`/api/forms/${formId}/detection`).then((r) => parse<Detection>(r))
export const createForm = (name: string, file: File) =>
  fetch('/api/forms', { method: 'POST', body: fileBody(file, { name }) }).then((r) => parse<FormSpec>(r))
export const saveForm = (spec: FormSpec) =>
  fetch(`/api/forms/${spec.id}`, json('PUT', spec)).then((r) => parse<FormSpec>(r))
export const deleteForm = (formId: string) =>
  fetch(`/api/forms/${formId}`, { method: 'DELETE' }).then((r) => parse<{ deleted: string }>(r))
export const uploadReference = (formId: string, file: File) =>
  fetch(`/api/forms/${formId}/reference`, { method: 'POST', body: fileBody(file) }).then((r) => parse<Detection>(r))
export const importFmt = (formId: string, file: File) =>
  fetch(`/api/forms/${formId}/fmt`, { method: 'POST', body: fileBody(file) }).then((r) => parse<FmtImport>(r))
export const testForm = (spec: FormSpec) =>
  fetch(`/api/forms/${spec.id}/test`, json('POST', spec)).then((r) => parse<TestResult>(r))
export const referenceUrl = (formId: string, version: number) => `/api/forms/${formId}/reference.jpg?v=${version}`

export interface AuthStatus {
  required: boolean
  authenticated: boolean
}

export const getAuth = () => fetch('/api/auth').then((r) => parse<AuthStatus>(r))
export const login = (password: string) =>
  fetch('/api/auth/login', json('POST', { password })).then((r) => parse<{ authenticated: boolean }>(r))
export const logout = () => fetch('/api/auth/logout', { method: 'POST' }).then((r) => parse<{ authenticated: boolean }>(r))
