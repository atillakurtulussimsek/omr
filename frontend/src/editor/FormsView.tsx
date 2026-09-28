import { useEffect, useState } from 'react'
import { createForm, getForms } from '../api'
import type { FormInfo } from '../types'
import FormEditor from './FormEditor'

const formIdFromHash = () => location.hash.match(/^#forms\/([a-z0-9-]+)/)?.[1] ?? null

export default function FormsView() {
  const [formId, setFormId] = useState<string | null>(formIdFromHash)
  const [forms, setForms] = useState<FormInfo[]>([])
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const onHashChange = () => setFormId(formIdFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  useEffect(() => {
    if (!formId) getForms().then(setForms).catch((e: Error) => setError(e.message))
  }, [formId])

  async function create() {
    if (!file) return
    setError('')
    setIsCreating(true)
    try {
      const spec = await createForm(name, file)
      setName('')
      setFile(null)
      location.hash = `#forms/${spec.id}`
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setIsCreating(false)
    }
  }

  if (formId) return <FormEditor key={formId} formId={formId} />

  return (
    <div className="formsList">
      <header className="pageHead">
        <div>
          <p className="eyebrow">Form Tanımları</p>
          <h1>Optik formları <em>tanımla</em></h1>
        </div>
      </header>
      <section className="card">
        <h2>Tanımlı formlar</h2>
        <table>
          <thead>
            <tr><th>Form</th><th>Alan</th><th>Hizalama</th><th>Referans görsel</th></tr>
          </thead>
          <tbody>
            {forms.map((f) => (
              <tr key={f.id} onClick={() => { location.hash = `#forms/${f.id}` }}>
                <td><strong>{f.name}</strong></td>
                <td>{f.fieldCount}</td>
                <td>
                  {f.alignment === 'timing'
                    ? (f.timingCount < 10 ? <span className="badge fail">{f.timingCount} zamanlama işareti · en az 10 gerekli</span> : `${f.timingCount} zamanlama işareti`)
                    : (f.anchorCount < 4 ? <span className="badge fail">{f.anchorCount} kare · en az 4 gerekli</span> : `${f.anchorCount} kare`)}
                </td>
                <td>{f.hasReference ? 'Var' : <span className="muted">Yok</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="card">
        <h2>Yeni form tanımla</h2>
        <p className="muted">
          Boş formun düz bir taramasını yükleyin. Eğim ve perspektif otomatik düzeltilir; baloncuklar,
          hizalama kareleri ve zamanlama işaretleri algılanır. Kare yoksa zamanlama işaretleriyle hizalanır.
        </p>
        <div className="newForm">
          <input type="text" placeholder="Form adı" value={name} onChange={(e) => setName(e.target.value)} />
          <input
            type="file"
            accept=".jpg,.jpeg,.png,.tif,.tiff,.bmp,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <button className="primary" onClick={create} disabled={!name.trim() || !file || isCreating}>
            {isCreating ? 'Oluşturuluyor…' : 'Oluştur'}
          </button>
        </div>
        {error && <p className="errorText">{error}</p>}
      </section>
    </div>
  )
}
