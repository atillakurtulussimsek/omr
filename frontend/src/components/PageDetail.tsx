import { useEffect } from 'react'
import { annotatedUrl } from '../api'
import type { FieldResult, PageResult } from '../types'

interface PageDetailProps {
  jobId: string
  page: PageResult
  pageCount: number
  onNavigate: (index: number) => void
  onClose: () => void
}

function AnswerRow({ field }: { field: FieldResult }) {
  return (
    <div className="answerRow">
      <span className="answerTitle">{field.title}</span>
      <span className="answerCells">
        {field.groups.map((g, i) => (
          <span key={i} className={`answerCell ${g.status}`} title={`${i + 1}. soru`}>
            {g.value}
          </span>
        ))}
      </span>
    </div>
  )
}

export default function PageDetail({ jobId, page, pageCount, onNavigate, onClose }: PageDetailProps) {
  const fields = Object.values(page.fields)
  const info = fields.filter((f) => f.category !== 'answers')
  const answers = fields.filter((f) => f.category === 'answers')
  const hasPrev = page.index > 0
  const hasNext = page.index < pageCount - 1

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowLeft' && hasPrev) onNavigate(page.index - 1)
      else if (e.key === 'ArrowRight' && hasNext) onNavigate(page.index + 1)
    }
    window.addEventListener('keydown', onKeyDown)
    document.body.classList.add('modalOpen')
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      document.body.classList.remove('modalOpen')
    }
  }, [page.index, hasPrev, hasNext, onNavigate, onClose])

  return (
    <div className="modalBackdrop" onClick={onClose}>
      <div className="modal detailModal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <header className="modalHead">
          <div className="modalTitle">
            <span className="pageNo">{page.index + 1} / {pageCount}</span>
            <strong title={page.source.file}>{page.source.file}{page.source.file.toLowerCase().endsWith('.pdf') ? ` · s.${page.source.page}` : ''}</strong>
            {page.ok
              ? (page.flags.length ? <span className="badge warn">{page.flags.length} uyarı</span> : <span className="badge ok">Tamam</span>)
              : <span className="badge fail">Okunamadı</span>}
          </div>
          <div className="modalActions">
            <button onClick={() => onNavigate(page.index - 1)} disabled={!hasPrev} title="Önceki (←)">← Önceki</button>
            <button onClick={() => onNavigate(page.index + 1)} disabled={!hasNext} title="Sonraki (→)">Sonraki →</button>
            {page.hasAnnotated && <a className="button" href={annotatedUrl(jobId, page.index, true)}>Görseli indir</a>}
            <button className="closeButton" onClick={onClose} title="Kapat (Esc)" aria-label="Kapat">✕</button>
          </div>
        </header>

        <div className="modalBody">
          <section className="detailInfo">
            {!page.ok && <p className="errorText">{page.error}</p>}

            {page.flags.length > 0 && (
              <ul className="flagList">
                {page.flags.map((f, i) => <li key={i}>{f.message}</li>)}
              </ul>
            )}

            {page.ok && (
              <>
                <h3>Bilgiler</h3>
                <dl className="infoGrid">
                  {info.map((f, i) => (
                    <div key={i}>
                      <dt>{f.title}</dt>
                      <dd className={f.groups.some((g) => g.status === 'multi' || g.status === 'suspect') ? 'flagged' : ''}>
                        {f.value.replace(/_/g, '') || '—'}
                      </dd>
                    </div>
                  ))}
                </dl>
                <h3>Cevaplar</h3>
                <div className="answers">
                  {answers.map((f, i) => <AnswerRow key={i} field={f} />)}
                </div>
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
