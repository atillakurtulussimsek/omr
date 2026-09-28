import type { FieldSpec } from '../types'
import { DIGITS, EN_LETTERS, TR_LETTERS, fitLabels, optionCount } from './fieldUtils'

interface FieldPanelProps {
  field: FieldSpec
  onChange: (field: FieldSpec) => void
  onSnap: () => void
  onDuplicate: () => void
  onDelete: () => void
}

interface NumberInputProps {
  label: string
  value: number
  step?: number
  min?: number
  onChange: (value: number) => void
}

function NumberInput({ label, value, step = 1, min, onChange }: NumberInputProps) {
  return (
    <label>
      {label}
      <input
        type="number"
        value={value}
        step={step}
        min={min}
        onChange={(e) => { if (e.target.value !== '' && !Number.isNaN(e.target.valueAsNumber)) onChange(e.target.valueAsNumber) }}
      />
    </label>
  )
}

export default function FieldPanel({ field, onChange, onSnap, onDuplicate, onDelete }: FieldPanelProps) {
  const set = (patch: Partial<FieldSpec>) => onChange(fitLabels({ ...field, ...patch }))
  const count = optionCount(field)
  const presets: [string, string[]][] = [['0-9', DIGITS], ['A-Z', EN_LETTERS], ['TR alfabe', TR_LETTERS]]

  return (
    <div className="fieldPanel">
      <div className="inputGrid">
        <label>
          Başlık
          <input type="text" value={field.title} onChange={(e) => set({ title: e.target.value })} />
        </label>
        <label>
          Anahtar
          <input type="text" value={field.name} onChange={(e) => set({ name: e.target.value.trim() })} />
        </label>
        <label>
          Tür
          <select value={field.category} onChange={(e) => set({ category: e.target.value as FieldSpec['category'] })}>
            <option value="info">Bilgi</option>
            <option value="answers">Cevap</option>
          </select>
        </label>
        <label>
          Okuma yönü
          <select value={field.type} onChange={(e) => set({ type: e.target.value as FieldSpec['type'] })}>
            <option value="rows">Satır bazlı (her satır bir soru)</option>
            <option value="columns">Sütun bazlı (her sütun bir hane)</option>
          </select>
        </label>
        <NumberInput label="Satır" value={field.rows} min={1} onChange={(v) => set({ rows: Math.max(1, Math.round(v)) })} />
        <NumberInput label="Sütun" value={field.cols} min={1} onChange={(v) => set({ cols: Math.max(1, Math.round(v)) })} />
        <NumberInput label="X" value={field.x} step={0.5} onChange={(v) => set({ x: v })} />
        <NumberInput label="Y" value={field.y} step={0.5} onChange={(v) => set({ y: v })} />
        <NumberInput label="Adım X" value={field.stepX} step={0.1} min={1} onChange={(v) => set({ stepX: v })} />
        <NumberInput label="Adım Y" value={field.stepY} step={0.1} min={1} onChange={(v) => set({ stepY: v })} />
      </div>

      <label className="wide">
        Etiketler ({count} adet, virgülle)
        <input
          type="text"
          className={field.labels.length === count && field.labels.every(Boolean) ? '' : 'invalid'}
          value={field.labels.join(',')}
          onChange={(e) => onChange({ ...field, labels: e.target.value.split(',').map((l) => l.trim()) })}
        />
      </label>
      <div className="presets">
        {presets.map(([title, labels]) => (
          <button key={title} className="link" disabled={labels.length < count} onClick={() => set({ labels: labels.slice(0, count) })}>
            {title}
          </button>
        ))}
        <label className="blankInput">
          Boş karakteri
          <input type="text" maxLength={1} value={field.blank} onChange={(e) => set({ blank: e.target.value })} />
        </label>
      </div>

      <div className="fieldActions">
        <button onClick={onSnap} title="Alanın kapladığı bölgedeki algılanmış baloncuklara yeniden oturt">Baloncuklara oturt</button>
        <button onClick={onDuplicate}>Kopyala</button>
        <button className="danger" onClick={onDelete}>Sil</button>
      </div>
    </div>
  )
}
