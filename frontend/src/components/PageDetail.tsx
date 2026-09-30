import { useEffect, useState } from 'react'
import { annotatedUrl, editPage, getForm } from '../api'
import type { FieldResult, FieldSpec, PageResult } from '../types'

interface PageDetailProps {
  jobId: string
  formId: string
  page: PageResult
  pageCount: number
  onNavigate: (index: number) => void
  onClose: () => void
  onEdited: (page: PageResult) => void
}

type Edits = Record<string, Record<string, string>>

const specLabels = (spec: FieldSpec) => spec.labels
const isSingleChar = (spec: FieldSpec) => spec.labels.every((l) => l.length === 1)

/** Tek grup için seçenek listesi: boş + etiketler. Bilgi alanında değerin ilk grubu vs. */
function GroupPicker({ spec, value, onPick, onClose }: { spec: FieldSpec; value: string; onPick: (v: string) => void; onClose: () => void }) {
  return (
    <span className="groupPicker" onClick={(e) => e.stopPropagation()}>
      <button className={`pick blank ${value === spec.blank ? 'current' : ''}`} onClick={() => onPick(spec.blank)} title="Boş">∅</button>
      {specLabels(spec).map((l) => (
        <button key={l} className={`pick ${value === l ? 'current' : ''}`} onClick={() => onPick(l)}>{l}</button>
      ))}
      <button className="pick close" onClick={onClose} title="Kapat">✕</button>
    </span>
  )
}

interface AnswerRowProps {
  field: FieldResult
  spec: FieldSpec | undefined
  isEditing: boolean
  pending: Record<string, string>
  onChange: (groupIndex: number, value: string) => void
}

function AnswerRow({ field, spec, isEditing, pending, onChange }: AnswerRowProps) {
  const [open, setOpen] = useState<number | null>(null)
  return (
    <div className="answerRow">
      <span className="answerTitle">{field.title}</span>
      <span className="answerCells">
        {field.groups.map((g, i) => {
          const value = pending[i] ?? g.value
          const status = pending[i] !== undefined ? 'pending' : g.status
          return (
            <span key={i} className="answerCellWrap">
              <button
                className={`answerCell ${status} ${isEditing ? 'editable' : ''}`}
                title={`${i + 1}. soru`}
                disabled={!isEditing || !spec}
                onClick={() => setOpen(open === i ? null : i)}
              >
                {value}
              </button>
              {isEditing && spec && open === i && (
                <GroupPicker spec={spec} value={value} onPick={(v) => { onChange(i, v); setOpen(null) }} onClose={() => setOpen(null)} />
              )}
            </span>
          )
        })}
      </span>
    </div>
  )
}

interface InfoFieldProps {
  field: FieldResult
  spec: FieldSpec | undefined
  isEditing: boolean
  pending: Record<string, string>
  onChange: (groupIndex: number, value: string) => void
}

function InfoField({ field, spec, isEditing, pending, onChange }: InfoFieldProps) {
  const [open, setOpen] = useState<number | null>(null)
  const groups = field.groups.map((g, i) => ({ value: pending[i] ?? g.value, status: pending[i] !== undefined ? 'pending' : g.status }))
  const flagged = groups.some((g) => g.status === 'multi' || g.status === 'suspect')
  const display = groups.map((g) => g.value).join('').replace(/_/g, '').trim() || '—'

  if (!isEditing || !spec) {
    return (
      <div>
        <dt>{field.title}</dt>
        <dd className={flagged ? 'flagged' : ''}>{display}{groups.some((g) => g.status === 'manual') && <small className="manualTag">elle</small>}</dd>
      </div>
    )
  }

  // tek karakterli etiketler (rakam/harf ızgarası): her hane bir metin kutusu, yazınca sonrakine geçer
  if (isSingleChar(spec)) {
    return (
      <div className="infoEdit">
        <dt>{field.title}</dt>
        <dd className="digitRow">
          {groups.map((g, i) => (
            <input
              key={i} type="text" maxLength={1} className={`digit ${g.status}`}
              value={g.value === spec.blank ? '' : g.value}
              title={`${i + 1}. hane`}
              onChange={(e) => {
                const ch = e.target.value.toLocaleUpperCase('tr').slice(-1)
                if (ch === '' ) { onChange(i, spec.blank); return }
                if (!spec.labels.includes(ch)) return
                onChange(i, ch)
                const next = e.target.parentElement?.querySelectorAll<HTMLInputElement>('input')[i + 1]
                next?.focus()
              }}
              onKeyDown={(e) => {
                if (e.key === 'Backspace' && !e.currentTarget.value) {
                  const prev = e.currentTarget.parentElement?.querySelectorAll<HTMLInputElement>('input')[i - 1]
                  prev?.focus()
                }
              }}
            />
          ))}
        </dd>
      </div>
    )
  }

  // çok karakterli etiketler (SINIF: 9/10/11/12/MEZUN, ALAN: SAY/EA…): seçenek listesi
  return (
    <div className="infoEdit">
      <dt>{field.title}</dt>
      <dd className="pickRow">
        {groups.map((g, i) => (
          <span key={i} className="answerCellWrap">
            <button className={`answerCell wide ${g.status} editable`} onClick={() => setOpen(open === i ? null : i)}>
              {g.value === spec.blank ? '—' : g.value}
            </button>
            {open === i && <GroupPicker spec={spec} value={g.value} onPick={(v) => { onChange(i, v); setOpen(null) }} onClose={() => setOpen(null)} />}
          </span>
        ))}
      </dd>
    </div>
  )
}

export default function PageDetail({ jobId, formId, page, pageCount, onNavigate, onClose, onEdited }: PageDetailProps) {
  const [specs, setSpecs] = useState<Record<string, FieldSpec>>({})
  const [isEditing, setIsEditing] = useState(false)
  const [edits, setEdits] = useState<Edits>({})
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getForm(formId).then((s) => setSpecs(Object.fromEntries(s.fields.map((f) => [f.name, f])))).catch(() => setSpecs({}))
  }, [formId])

  useEffect(() => { setIsEditing(false); setEdits({}); setError('') }, [page.index])

  const fields = Object.values(page.fields)
  const info = fields.filter((f) => f.category !== 'answers')
  const answers = fields.filter((f) => f.category === 'answers')
  const hasPrev = page.index > 0
  const hasNext = page.index < pageCount - 1
  const editCount = Object.values(edits).reduce((n, g) => n + Object.keys(g).length, 0)
  const nameOf = (f: FieldResult) => Object.keys(page.fields).find((k) => page.fields[k] === f) ?? ''

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement) return
      if (e.key === 'Escape') (isEditing ? cancelEdit() : onClose())
      else if (!isEditing && e.key === 'ArrowLeft' && hasPrev) onNavigate(page.index - 1)
      else if (!isEditing && e.key === 'ArrowRight' && hasNext) onNavigate(page.index + 1)
    }
    window.addEventListener('keydown', onKeyDown)
    document.body.classList.add('modalOpen')
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      document.body.classList.remove('modalOpen')
    }
  })

  function setEdit(name: string, groupIndex: number, value: string) {
    setEdits((e) => ({ ...e, [name]: { ...(e[name] ?? {}), [groupIndex]: value } }))
  }

  function cancelEdit() { setIsEditing(false); setEdits({}); setError('') }

  async function startManualEntry() {
    // okunamayan sayfa: sunucuda boş alanlar oluşturulur, sonra düzenleme moduna geçilir
    setIsSaving(true)
    try {
      onEdited(await editPage(jobId, page.index, {}))
      setIsEditing(true)
    } catch (e) { setError((e as Error).message) } finally { setIsSaving(false) }
  }

  async function save() {
    setIsSaving(true)
    setError('')
    try {
      onEdited(await editPage(jobId, page.index, edits))
      setIsEditing(false)
      setEdits({})
    } catch (e) { setError((e as Error).message) } finally { setIsSaving(false) }
  }

  return (
    <div className="modalBackdrop" onClick={isEditing ? undefined : onClose}>
      <div className="modal detailModal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <header className="modalHead">
          <div className="modalTitle">
            <span className="pageNo">{page.index + 1} / {pageCount}</span>
            <strong title={page.source.file}>{page.source.file}{page.source.file.toLowerCase().endsWith('.pdf') ? ` · s.${page.source.page}` : ''}</strong>
            {page.ok
              ? (page.flags.length ? <span className="badge warn">{page.flags.length} uyarı</span> : <span className="badge ok">Tamam</span>)
              : <span className="badge fail">Okunamadı</span>}
            {page.edited && <span className="badge manual">Düzeltildi</span>}
          </div>
          <div className="modalActions">
            {isEditing ? (
              <>
                <span className="muted">{editCount ? `${editCount} değişiklik` : 'Değiştirmek için hücreye tıklayın'}</span>
                <button onClick={cancelEdit} disabled={isSaving}>Vazgeç</button>
                <button className="primary small" onClick={save} disabled={isSaving || editCount === 0}>{isSaving ? 'Kaydediliyor…' : 'Kaydet'}</button>
              </>
            ) : (
              <>
                <button onClick={() => onNavigate(page.index - 1)} disabled={!hasPrev} title="Önceki (←)">← Önceki</button>
                <button onClick={() => onNavigate(page.index + 1)} disabled={!hasNext} title="Sonraki (→)">Sonraki →</button>
                {page.ok
                  ? <button onClick={() => setIsEditing(true)} disabled={!Object.keys(specs).length}>Düzelt</button>
                  : <button onClick={startManualEntry} disabled={isSaving || !Object.keys(specs).length}>Elle gir</button>}
                {page.hasAnnotated && <a className="button" href={annotatedUrl(jobId, page.index, true)}>Görseli indir</a>}
                <button className="closeButton" onClick={onClose} title="Kapat (Esc)" aria-label="Kapat">✕</button>
              </>
            )}
          </div>
        </header>

        <div className="modalBody">
          <section className={`detailInfo ${isEditing ? 'editing' : ''}`}>
            {!page.ok && <p className="errorText">{page.error}</p>}
            {error && <p className="errorText">{error}</p>}

            {page.flags.length > 0 && (
              <ul className="flagList">
                {page.flags.map((f, i) => <li key={i}>{f.message}</li>)}
              </ul>
            )}

            {page.ok && (
              <>
                <h3>Bilgiler</h3>
                <dl className="infoGrid">
                  {info.map((f) => {
                    const name = nameOf(f)
                    return <InfoField key={name} field={f} spec={specs[name]} isEditing={isEditing} pending={edits[name] ?? {}} onChange={(gi, v) => setEdit(name, gi, v)} />
                  })}
                </dl>
                <h3>Cevaplar</h3>
                <div className="answers">
                  {answers.map((f) => {
                    const name = nameOf(f)
                    return <AnswerRow key={name} field={f} spec={specs[name]} isEditing={isEditing} pending={edits[name] ?? {}} onChange={(gi, v) => setEdit(name, gi, v)} />
                  })}
                </div>
                <p className="muted legend">
                  <span className="answerCell filled">A</span> okundu · <span className="answerCell suspect">A</span> şüpheli ·
                  <span className="answerCell multi">*</span> çift işaret · <span className="answerCell manual">A</span> elle düzeltildi
                </p>
              </>
            )}
          </section>

          <section className="detailImage">
            {page.hasAnnotated ? (
              <a href={annotatedUrl(jobId, page.index)} target="_blank" rel="noreferrer" title="Yeni sekmede aç">
                <img key={page.index} className="annotated" src={annotatedUrl(jobId, page.index)} alt="İşaretleme sonucu" />
              </a>
            ) : (
              <p className="muted">Bu sayfa için işaretleme görseli yok.</p>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
