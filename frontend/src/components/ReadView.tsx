import { useCallback, useEffect, useState } from 'react'
import { addManualPage, annotatedZipUrl, createJob, createManualJob, exportTxtUrl, getForms, getJob, removeLastPage } from '../api'
import type { FormInfo, Job } from '../types'
import UploadZone from './UploadZone'
import ResultsTable from './ResultsTable'
import PageDetail from './PageDetail'

const POLL_MS = 700

interface ReadViewProps {
  isActive: boolean
}

export default function ReadView({ isActive: isViewActive }: ReadViewProps) {
  const [forms, setForms] = useState<FormInfo[]>([])
  const [formId, setFormId] = useState('optik129')
  const [files, setFiles] = useState<File[]>([])
  const [job, setJob] = useState<Job | null>(null)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    if (!isViewActive) return
    getForms().then(setForms).catch((e: Error) => setError(e.message))
  }, [isViewActive])

  useEffect(() => {
    // sayfa yenilenince sonuçlar kaybolmasın: iş kimliği adres çubuğunda tutulur
    const savedJobId = new URLSearchParams(location.hash.slice(1)).get('job')
    if (savedJobId) {
      getJob(savedJobId)
        .then((saved) => { setJob(saved); setFormId(saved.formId) })
        .catch(() => history.replaceState(null, '', location.pathname))
    }
  }, [])

  const jobId = job?.id
  useEffect(() => {
    // Form Tanımları sekmesinden dönünce iş kimliğini adrese geri yaz
    if (isViewActive && jobId) history.replaceState(null, '', `#job=${jobId}`)
  }, [isViewActive, jobId])

  const isActive = job?.status === 'queued' || job?.status === 'running'
  useEffect(() => {
    if (!jobId || !isActive) return
    const timer = setInterval(() => {
      getJob(jobId).then(setJob).catch((e: Error) => setError(e.message))
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [jobId, isActive])

  async function startJob() {
    setError('')
    setUploading(true)
    setSelectedIndex(null)
    try {
      const created = await createJob(files, formId)
      history.replaceState(null, '', `#job=${created.id}`)
      setJob(created)
      setFiles([])
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setUploading(false)
    }
  }

  const closeDetail = useCallback(() => setSelectedIndex(null), [])
  async function startManual() {
    setError('')
    setUploading(true)
    try {
      const created = await createManualJob(formId)
      const first = await addManualPage(created.id)
      history.replaceState(null, '', `#job=${created.id}`)
      setJob({ ...created, pages: [first], total: 1 })
      setSelectedIndex(0)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setUploading(false)
    }
  }

  async function addPage() {
    if (!job) return
    const page = await addManualPage(job.id)
    setJob((j) => j && { ...j, pages: [...j.pages, page], total: j.pages.length + 1 })
    setSelectedIndex(page.index)
  }

  async function removeLast() {
    if (!job || !confirm('Son form silinsin mi?')) return
    setJob(await removeLastPage(job.id))
    setSelectedIndex(null)
  }

  const pages = job?.pages ?? []
  const okCount = pages.filter((p) => p.ok).length
  const flaggedCount = pages.filter((p) => p.ok && p.flags.length > 0).length
  const failedCount = pages.length - okCount
  const hasAnnotated = pages.some((p) => p.hasAnnotated)
  const selectedPage = selectedIndex === null ? null : pages[selectedIndex] ?? null

  return (
    <div hidden={!isViewActive}>
      <header className="pageHead">
        <div>
          <p className="eyebrow">Okuma</p>
          <h1>Taramaları <em>oku</em>, sonuçları <em>aktar</em></h1>
        </div>
        <label className="formSelect">
          Form
          <select value={formId} onChange={(e) => setFormId(e.target.value)} disabled={isActive}>
            {forms.map((f) => (
              <option key={f.id} value={f.id}>{f.name}</option>
            ))}
          </select>
        </label>
      </header>

      <UploadZone files={files} onChange={setFiles} disabled={uploading || isActive} />
      <div className="actions">
        <button className="primary" onClick={startJob} disabled={files.length === 0 || uploading || isActive}>
          {uploading ? 'Yükleniyor…' : 'Oku'}
        </button>
        <button onClick={startManual} disabled={uploading || isActive} title="Taramasız: seçili formun alanlarını klavyeden kodlayın, TXT çıktısı o formun düzeninde üretilir">
          Elle kodla
        </button>
        {error && <span className="errorText">{error}</span>}
      </div>

      {job && (
        <section className="results">
          <div className="resultsBar">
            {job.manual ? (
              <div className="progress manualBar">
                <span className="badge manual">Elle kodlama</span>
                <span>{pages.length} form</span>
                <button className="small" onClick={addPage}>+ Form ekle</button>
                <button className="small danger" onClick={removeLast} disabled={pages.length === 0}>Son formu sil</button>
              </div>
            ) : (
            <div className="progress">
              <div className="progressTrack">
                <div
                  className="progressFill"
                  style={{ width: `${job.total ? (job.processed / job.total) * 100 : isActive ? 5 : 100}%` }}
                />
              </div>
              <span>
                {job.status === 'error' ? `Hata: ${job.error}` : `${job.processed} / ${job.total || '…'} sayfa`}
              </span>
            </div>
            )}
            <div className="stats">
              <span className="stat ok">{okCount} okundu</span>
              <span className="stat warn">{flaggedCount} uyarılı</span>
              <span className="stat fail">{failedCount} hatalı</span>
            </div>
            <div className="downloads">
              <a className={`button ${okCount ? '' : 'disabled'}`} href={exportTxtUrl(job.id)}>TXT indir</a>
              <a className={`button ${hasAnnotated ? '' : 'disabled'}`} href={annotatedZipUrl(job.id)}>
                İşaretleme sonuçları (ZIP)
              </a>
            </div>
          </div>

          <div className="resultsBody">
            <ResultsTable pages={pages} selectedIndex={selectedIndex} onSelect={setSelectedIndex} />
          </div>
          {selectedPage && isViewActive && (
            <PageDetail
              jobId={job.id}
              formId={job.formId}
              page={selectedPage}
              pageCount={pages.length}
              onNavigate={setSelectedIndex}
              onClose={closeDetail}
              onEdited={(edited) => setJob((j) => j && { ...j, pages: j.pages.map((p) => (p.index === edited.index ? edited : p)) })}
              onAddPage={job.manual ? addPage : undefined}
            />
          )}
        </section>
      )}
    </div>
  )
}
