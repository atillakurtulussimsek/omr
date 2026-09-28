import type { ExportFieldItem, ExportItem, ExportSpec, FieldSpec } from '../types'
import { defaultExport, fieldItem, itemWidth, mapToText, textToMap } from './exportUtils'

interface ExportEditorProps {
  fields: FieldSpec[]
  exportSpec: ExportSpec
  isDefault: boolean
  previewLine: string | null
  previewNote: string
  onChange: (exportSpec: ExportSpec) => void
}

const intOr = (value: number, fallback: number) => (Number.isFinite(value) && value >= 1 ? Math.round(value) : fallback)

function Preview({ line, items }: { line: string; items: ExportItem[] }) {
  const chars = Array.from(line)
  const tens = chars.map((_, i) => ((i + 1) % 10 === 0 ? String(((i + 1) / 10) % 10) : ' ')).join('')
  const ones = chars.map((_, i) => String((i + 1) % 10)).join('')
  let at = 0
  return (
    <pre className="exportPreview">
      <span className="ruler">{tens}{'\n'}{ones}{'\n'}</span>
      {items.map((item, i) => {
        const part = chars.slice(at, at + itemWidth(item)).join('')
        at += itemWidth(item)
        return <span key={i} className={`seg ${item.kind} ${i % 2 ? 'odd' : ''}`}>{part}</span>
      })}
    </pre>
  )
}

export default function ExportEditor({ fields, exportSpec, isDefault, previewLine, previewNote, onChange }: ExportEditorProps) {
  const { items } = exportSpec
  const setItems = (next: ExportItem[]) => onChange({ ...exportSpec, items: next })
  const setItem = (index: number, item: ExportItem) => setItems(items.map((it, i) => (i === index ? item : it)))
  const move = (index: number, by: number) => {
    const next = [...items]
    const [item] = next.splice(index, 1)
    next.splice(index + by, 0, item)
    setItems(next)
  }
  const titleOf = (name: string) => fields.find((f) => f.name === name)?.title ?? name
  const unusedFields = fields.filter((f) => !items.some((it) => it.kind === 'field' && it.field === f.name))
  const total = items.reduce((sum, it) => sum + itemWidth(it), 0)
  let column = 1

  return (
    <div className="exportEditor">
      <div className="exportHead">
        <div>
          <strong>TXT çıktı düzeni</strong>
          <span className="muted"> · sabit genişlik · satır uzunluğu {total} karakter{isDefault ? ' · varsayılan düzen' : ''}</span>
        </div>
        <label className="inline">
          Kodlama
          <select value={exportSpec.encoding} onChange={(e) => onChange({ ...exportSpec, encoding: e.target.value as ExportSpec['encoding'] })}>
            <option value="utf-8">UTF-8</option>
            <option value="windows-1254">Windows-1254 (Türkçe ANSI)</option>
          </select>
        </label>
      </div>

      <h3>Önizleme <span className="muted">(referans görselin okunmasıyla)</span></h3>
      {previewLine !== null ? <Preview line={previewLine} items={items} /> : <p className="muted">{previewNote}</p>}

      <h3>Öğeler</h3>
      <table className="exportTable">
        <thead>
          <tr>
            <th>#</th><th>Öğe</th><th>Kolon</th><th>Genişlik</th><th>Hizalama</th><th>Dolgu</th>
            <th title="İşaretlenmemiş soru / hane yerine yazılacak">Boş →</th>
            <th title="Çift işaretli soru / hane yerine yazılacak">Çift →</th>
            <th title="Okunan değeri başka koda çevir. Örn. SAY=2, SÖZ=1">Dönüşüm</th><th />
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => {
            const start = column
            column += itemWidth(item)
            const field = item.kind === 'field' ? (item as ExportFieldItem) : null
            return (
              <tr key={i} className={item.kind}>
                <td className="muted">{i + 1}</td>
                <td>
                  {field ? (
                    <select value={field.field} onChange={(e) => setItem(i, { ...fieldItem(fields.find((f) => f.name === e.target.value)!) })}>
                      {fields.map((f) => <option key={f.name} value={f.name}>{f.title}</option>)}
                    </select>
                  ) : item.kind === 'text' ? (
                    <input type="text" className="mono" placeholder="Sabit metin" value={item.text} onChange={(e) => setItem(i, { ...item, text: e.target.value })} />
                  ) : (
                    <span className="muted">Boşluk</span>
                  )}
                </td>
                <td className="mono muted">{itemWidth(item) ? `${start}–${column - 1}` : '—'}</td>
                <td>
                  {item.kind === 'text' ? <span className="muted">{item.text.length}</span> : (
                    <input type="number" min={1} value={item.width} onChange={(e) => setItem(i, { ...item, width: intOr(e.target.valueAsNumber, item.width) })} />
                  )}
                </td>
                {field ? (
                  <>
                    <td>
                      <select value={field.align} onChange={(e) => setItem(i, { ...field, align: e.target.value as ExportFieldItem['align'] })}>
                        <option value="left">Sola</option>
                        <option value="right">Sağa</option>
                      </select>
                    </td>
                    <td><input type="text" className="mono tiny" maxLength={1} value={field.pad} onChange={(e) => setItem(i, { ...field, pad: e.target.value || ' ' })} /></td>
                    <td><input type="text" className="mono tiny" value={field.blankAs} onChange={(e) => setItem(i, { ...field, blankAs: e.target.value })} /></td>
                    <td><input type="text" className="mono tiny" value={field.multiAs} onChange={(e) => setItem(i, { ...field, multiAs: e.target.value })} /></td>
                    <td>
                      <input
                        key={mapToText(field.map)} type="text" className="mono" placeholder="örn. SAY=2, SÖZ=1"
                        defaultValue={mapToText(field.map)} onBlur={(e) => setItem(i, { ...field, map: textToMap(e.target.value) })}
                      />
                    </td>
                  </>
                ) : <td colSpan={5} />}
                <td className="rowActions">
                  <button className="link" disabled={i === 0} onClick={() => move(i, -1)} title="Yukarı">↑</button>
                  <button className="link" disabled={i === items.length - 1} onClick={() => move(i, 1)} title="Aşağı">↓</button>
                  <button className="link danger" onClick={() => setItems(items.filter((_, k) => k !== i))} title="Kaldır">✕</button>
                </td>
              </tr>
            )
          })}
          {items.length === 0 && <tr><td colSpan={10} className="emptyCell">Öğe yok. Aşağıdan alan ekleyin.</td></tr>}
        </tbody>
      </table>

      <div className="exportAdd">
        <select value="" onChange={(e) => { const f = fields.find((x) => x.name === e.target.value); if (f) setItems([...items, fieldItem(f)]) }} disabled={fields.length === 0}>
          <option value="">+ Alan ekle…</option>
          {unusedFields.length > 0 && <optgroup label="Eklenmemiş">{unusedFields.map((f) => <option key={f.name} value={f.name}>{f.title}</option>)}</optgroup>}
          <optgroup label="Tümü">{fields.map((f) => <option key={f.name} value={f.name}>{titleOf(f.name)}</option>)}</optgroup>
        </select>
        <button onClick={() => setItems([...items, { kind: 'text', text: '' }])}>+ Sabit metin</button>
        <button onClick={() => setItems([...items, { kind: 'space', width: 1 }])}>+ Boşluk</button>
        <button className="link" onClick={() => onChange(defaultExport(fields))}>Varsayılan düzene dön</button>
      </div>
    </div>
  )
}
