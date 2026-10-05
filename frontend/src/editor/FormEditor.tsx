import { useCallback, useEffect, useRef, useState } from 'react'
import { deleteForm, deleteReference, exportFormUrl, getDetection, getForm, importFmt, referenceUrl, saveForm, testForm, uploadReference } from '../api'
import type { Detection, ExportSpec, FieldSpec, FormSpec, TestResult } from '../types'
import EditorCanvas from './EditorCanvas'
import ExportEditor from './ExportEditor'
import { defaultExport } from './exportUtils'
import FieldPanel from './FieldPanel'
import { estimatePitch, fieldBounds, fieldFromRect, uniqueName } from './fieldUtils'
import type { Rect } from './fieldUtils'

interface FormEditorProps {
  formId: string
}

const ZOOMS = [0.5, 0.75, 1, 1.5, 2]
const isTyping = (el: EventTarget | null) => el instanceof HTMLInputElement || el instanceof HTMLSelectElement

export default function FormEditor({ formId }: FormEditorProps) {
  const [spec, setSpec] = useState<FormSpec | null>(null)
  const [detection, setDetection] = useState<Detection | null>(null)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [isDirty, setIsDirty] = useState(false)
  const [isBusy, setIsBusy] = useState(false)
  const [isAnchorMode, setIsAnchorMode] = useState(false)
  const [showDetected, setShowDetected] = useState(true)
  const [zoom, setZoom] = useState(1)
  const [imageVersion, setImageVersion] = useState(1)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [tab, setTab] = useState<'fields' | 'export'>('fields')
  const [preview, setPreview] = useState<{ line: string | null; note: string }>({ line: null, note: '' })
  const [message, setMessage] = useState<{ kind: 'ok' | 'fail'; text: string } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const fmtRef = useRef<HTMLInputElement>(null)
  const [fmtWarnings, setFmtWarnings] = useState<string[]>([])

  const fail = (e: unknown) => setMessage({ kind: 'fail', text: (e as Error).message })

  useEffect(() => {
    getForm(formId).then(setSpec).catch(fail)
    getDetection(formId).then(setDetection).catch(fail)
  }, [formId])

  const update = useCallback((change: (s: FormSpec) => FormSpec) => {
    setSpec((s) => (s ? change(s) : s))
    setIsDirty(true)
    setTestResult(null)
  }, [])

  // alan anahtarı değişince / alan silinince TXT düzenindeki göndermeler eşitlenir
  const updateField = useCallback((index: number, field: FieldSpec) => {
    update((s) => {
      const oldName = s.fields[index].name
      const items = s.export?.items.map((it) => (it.kind === 'field' && it.field === oldName ? { ...it, field: field.name } : it))
      return { ...s, fields: s.fields.map((f, i) => (i === index ? field : f)), export: s.export && items ? { ...s.export, items } : s.export }
    })
  }, [update])

  const removeField = useCallback((index: number) => {
    update((s) => {
      const name = s.fields[index].name
      const items = s.export?.items.filter((it) => !(it.kind === 'field' && it.field === name))
      return { ...s, fields: s.fields.filter((_, i) => i !== index), export: s.export && items ? { ...s.export, items } : s.export }
    })
    setSelectedIndex(null)
  }, [update])

  // TXT sekmesinde önizleme: taslak, referans görsel üzerinde sunucuda okunur
  const previewKey = spec && tab === 'export' ? JSON.stringify([spec.export, spec.fields, spec.anchors]) : null
  useEffect(() => {
    if (!previewKey || !spec) return
    if (!spec.hasReference) {
      setPreview({ line: null, note: 'Önizleme için referans görsel gerekli.' })
      return
    }
    const timer = setTimeout(() => {
      testForm(spec)
        .then((r) => setPreview(r.ok ? { line: r.exportLine, note: '' } : { line: null, note: r.error }))
        .catch((e: Error) => setPreview({ line: null, note: e.message }))
    }, 400)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewKey])

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (selectedIndex === null || !spec || tab !== 'fields' || isTyping(e.target)) return
      const field = spec.fields[selectedIndex]
      const delta = e.shiftKey ? 10 : 1
      const moves: Record<string, [number, number]> = {
        ArrowLeft: [-delta, 0], ArrowRight: [delta, 0], ArrowUp: [0, -delta], ArrowDown: [0, delta],
      }
      if (moves[e.key]) {
        e.preventDefault()
        updateField(selectedIndex, { ...field, x: field.x + moves[e.key][0], y: field.y + moves[e.key][1] })
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault()
        removeField(selectedIndex)
      } else if (e.key === 'Escape') setSelectedIndex(null)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [selectedIndex, spec, tab, updateField, removeField])

  if (!spec) return <p className="muted">{message?.text ?? 'Yükleniyor…'}</p>

  const pitch = estimatePitch(spec.fields, detection)
  const alignment = spec.alignment ?? 'anchors'
  // eski şablonlarda zamanlama işaretleri kayıtlı değilse referans görselde algılananlar kullanılır
  const timingMarks = spec.timingMarks?.length ? spec.timingMarks : detection?.timingMarks ?? []
  const canAlign = alignment === 'timing' ? timingMarks.length >= 10 : spec.anchors.length >= 4
  const selectedField = selectedIndex === null ? null : spec.fields[selectedIndex] ?? null

  function addFromRect(rect: Rect) {
    if (!detection || !spec) return
    const field = fieldFromRect(rect, detection, spec.fields, pitch)
    if (!field) {
      setMessage({ kind: 'fail', text: 'Seçilen bölgede baloncuk algılanmadı' })
      return
    }
    setMessage(null)
    update((s) => ({ ...s, fields: [...s.fields, field] }))
    setSelectedIndex(spec.fields.length)
  }

  function snapSelected() {
    if (selectedIndex === null || !selectedField || !detection || !spec) return
    const others = spec.fields.filter((_, i) => i !== selectedIndex)
    const snapped = fieldFromRect(fieldBounds(selectedField, spec.bubbleRadius), detection, others, pitch)
    if (!snapped) return
    const { x, y, stepX, stepY, rows, cols } = snapped
    const sameShape = rows === selectedField.rows && cols === selectedField.cols
    updateField(selectedIndex, { ...selectedField, x, y, stepX, stepY, rows, cols, labels: sameShape ? selectedField.labels : snapped.labels })
  }

  function duplicateSelected() {
    if (!selectedField || !spec) return
    const copy: FieldSpec = {
      ...selectedField,
      name: uniqueName(selectedField.name, spec.fields),
      x: selectedField.x + selectedField.cols * selectedField.stepX + pitch,
    }
    update((s) => ({ ...s, fields: [...s.fields, copy] }))
    setSelectedIndex(spec.fields.length)
  }

  function toggleAnchor(anchor: [number, number]) {
    update((s) => {
      const has = s.anchors.some((a) => Math.hypot(a[0] - anchor[0], a[1] - anchor[1]) < 8)
      return { ...s, anchors: has ? s.anchors.filter((a) => Math.hypot(a[0] - anchor[0], a[1] - anchor[1]) >= 8) : [...s.anchors, anchor] }
    })
  }

  async function run(action: () => Promise<void>) {
    setIsBusy(true)
    setMessage(null)
    try {
      await action()
    } catch (e) {
      fail(e)
    } finally {
      setIsBusy(false)
    }
  }

  const save = () => run(async () => {
    setSpec(await saveForm(spec))
    setIsDirty(false)
    setMessage({ kind: 'ok', text: 'Kaydedildi' })
  })

  const runTest = () => run(async () => {
    const result = await testForm(spec)
    setTestResult(result)
    setMessage(result.ok ? { kind: 'ok', text: 'Deneme okuması tamam' } : { kind: 'fail', text: result.error })
  })

  const replaceReference = (file: File) => run(async () => {
    setDetection(await uploadReference(spec.id, file))
    setSpec((s) => (s ? { ...s, hasReference: true } : s))
    setImageVersion((v) => v + 1)
    setMessage({ kind: 'ok', text: 'Referans görsel güncellendi' })
  })

  const applyFmt = (file: File) => run(async () => {
    const result = await importFmt(spec.id, file)
    if (spec.fields.length > 0 && !confirm(`Mevcut ${spec.fields.length} alan ve TXT düzeni FMT'den gelenlerle değiştirilsin mi?`)) return
    update((s) => ({ ...s, fields: result.fields, export: result.export }))
    setSelectedIndex(null)
    setFmtWarnings(result.report.warnings)
    setMessage({
      kind: 'ok',
      text: `FMT'den ${result.report.fieldCount} alan ve ${result.report.lineWidth} karakterlik TXT düzeni alındı (baloncuk örtüşmesi %${Math.round(result.report.matchRatio * 100)}). Kontrol edip kaydedin.`,
    })
  })

  const removeReference = () => {
    if (!confirm('Referans görsel kaldırılsın mı? Okuma etkilenmez; deneme okuması ve TXT önizlemesi için yeniden görsel yüklemeniz gerekir.')) return
    run(async () => {
      await deleteReference(spec.id)
      setSpec((s) => (s ? { ...s, hasReference: false } : s))
      setTestResult(null)
      setMessage({ kind: 'ok', text: 'Referans görsel kaldırıldı' })
    })
  }

  const remove = () => {
    if (!confirm(`"${spec.name}" formu silinsin mi? Bu işlem geri alınamaz.`)) return
    run(async () => {
      await deleteForm(spec.id)
      location.hash = '#forms'
    })
  }

  const back = () => {
    if (!isDirty || confirm('Kaydedilmemiş değişiklikler var. Çıkılsın mı?')) location.hash = '#forms'
  }

  return (
    <div className="editor">
      <aside className="editorPanel">
        <button className="link backLink" onClick={back}>← Formlar</button>
        <label className="wide">
          Form adı
          <input type="text" value={spec.name} onChange={(e) => update((s) => ({ ...s, name: e.target.value }))} />
        </label>

        <div className="editorActions">
          <button className="primary" onClick={save} disabled={isBusy || !isDirty}>Kaydet</button>
          <button onClick={runTest} disabled={isBusy || !spec.hasReference || spec.fields.length === 0}>Deneme oku</button>
          <button className="danger" onClick={remove} disabled={isBusy}>Formu sil</button>
        </div>
        {message && <p className={message.kind === 'ok' ? 'okText' : 'errorText'}>{message.text}</p>}
        {!canAlign && (
          <p className="errorText">
            {alignment === 'timing'
              ? `Okuma için en az 10 zamanlama işareti gerekli (şu an ${timingMarks.length}).`
              : `Okuma için en az 4 hizalama karesi gerekli (şu an ${spec.anchors.length}).`}
          </p>
        )}

        <nav className="tabs panelTabs">
          <a className={tab === 'fields' ? 'active' : ''} onClick={() => setTab('fields')}>Alanlar</a>
          <a className={tab === 'export' ? 'active' : ''} onClick={() => setTab('export')}>TXT çıktısı</a>
        </nav>

        {tab === 'fields' && (<>
        <h3>Kaynaklar</h3>
        <div className="sources">
          <input ref={fileRef} type="file" hidden accept=".jpg,.jpeg,.png,.tif,.tiff,.bmp,.pdf"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) replaceReference(f) }} />
          <button onClick={() => fileRef.current?.click()} disabled={isBusy || !canAlign}
            title={canAlign ? '' : 'Görselin şablona hizalanması için hizalama işaretleri gerekli'}>
            Referans görsel yükle
          </button>
          <span className="muted">{spec.hasReference ? `${detection?.circles.length ?? 0} baloncuk algılandı` : 'referans görsel yok'}</span>
          <input ref={fmtRef} type="file" hidden accept=".fmt,.FMT"
            onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) applyFmt(f) }} />
          <button onClick={() => fmtRef.current?.click()} disabled={isBusy || !(detection?.circles.length)}
            title="Sekonic .FMT dosyasından alanları ve TXT düzenini al">
            FMT'den içe aktar
          </button>
          {spec.hasReference && (
            <button className="danger" onClick={removeReference} disabled={isBusy} title="Demo / örnek görseli sunucudan sil">
              Referans görseli kaldır
            </button>
          )}
        </div>
        <div className="sources exportRow">
          <a className={`button ${isDirty ? 'disabled' : ''}`} href={exportFormUrl(spec.id)} title={isDirty ? 'Önce kaydedin' : 'Form tanımını indir (.json)'}>Dışa aktar</a>
          {spec.hasReference && (
            <a className={`button ${isDirty ? 'disabled' : ''}`} href={exportFormUrl(spec.id, true)} title="Tanım + referans görsel (.zip)">Görselle dışa aktar</a>
          )}
        </div>
        {fmtWarnings.length > 0 && (
          <ul className="flagList fmtWarnings">{fmtWarnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
        )}

        <h3>Hizalama</h3>
        <label className="wide">
          Yöntem
          <select value={alignment} onChange={(e) => { setIsAnchorMode(false); update((s) => ({ ...s, alignment: e.target.value as 'anchors' | 'timing', timingMarks, timingSize: s.timingSize ?? detection?.timingSize })) }}>
            <option value="anchors">Hizalama kareleri ({spec.anchors.length})</option>
            <option value="timing">Zamanlama işaretleri ({timingMarks.length})</option>
          </select>
        </label>
        {alignment === 'anchors' ? (
          <label className="check">
            <input type="checkbox" checked={isAnchorMode} onChange={(e) => setIsAnchorMode(e.target.checked)} />
            Kareleri düzenle (tıklayarak ekle / çıkar)
          </label>
        ) : (
          <p className="muted hint">Kenardaki işaret dizisi referans görselden algılandı; kaba hizalama bunlardan, ince düzeltme baloncuklardan yapılır.</p>
        )}

        <h3>Alanlar ({spec.fields.length})</h3>
        <p className="muted hint">Yeni alan: görsel üzerinde baloncukları içine alan bir dikdörtgen çizin.</p>
        <ul className="fieldList">
          {spec.fields.map((f, i) => (
            <li key={i} className={i === selectedIndex ? 'selected' : ''} onClick={() => setSelectedIndex(i)}>
              <span className={`dot ${f.category}`} />
              <span className="fieldTitle">
                {f.title}
                {testResult?.fields[f.name] && <small className="mono">{testResult.fields[f.name].value || '—'}</small>}
              </span>
              <span className="muted">{f.rows}×{f.cols}</span>
            </li>
          ))}
        </ul>

        {selectedField && selectedIndex !== null && (
          <>
            <h3>Seçili alan</h3>
            <FieldPanel
              field={selectedField}
              onChange={(f) => updateField(selectedIndex, f)}
              onSnap={snapSelected}
              onDuplicate={duplicateSelected}
              onDelete={() => removeField(selectedIndex)}
            />
          </>
        )}
        </>)}
      </aside>

      {tab === 'export' && (
        <div className="editorStage">
          <ExportEditor
            fields={spec.fields}
            exportSpec={spec.export ?? defaultExport(spec.fields)}
            isDefault={!spec.export}
            previewLine={preview.line}
            previewNote={preview.note || 'Önizleme hazırlanıyor…'}
            onChange={(exportSpec: ExportSpec) => update((s) => ({ ...s, export: exportSpec }))}
          />
        </div>
      )}

      <div className="editorStage" hidden={tab !== 'fields'}>
        <div className="stageBar">
          <label className="check">
            <input type="checkbox" checked={showDetected} onChange={(e) => setShowDetected(e.target.checked)} />
            Algılanan baloncuklar
          </label>
          <span className="zoom">
            {ZOOMS.map((z) => (
              <button key={z} className={`link ${z === zoom ? 'active' : ''}`} onClick={() => setZoom(z)}>%{z * 100}</button>
            ))}
          </span>
        </div>
        <div className="stageScroll">
          <EditorCanvas
            spec={spec}
            detection={detection}
            imageUrl={spec.hasReference ? referenceUrl(spec.id, imageVersion) : null}
            zoom={zoom}
            selectedIndex={selectedIndex}
            isAnchorMode={isAnchorMode}
            showDetected={showDetected}
            testResult={testResult}
            onSelect={setSelectedIndex}
            onDraw={addFromRect}
            onMove={(i, x, y) => updateField(i, { ...spec.fields[i], x, y })}
            onToggleAnchor={toggleAnchor}
          />
        </div>
      </div>
    </div>
  )
}
