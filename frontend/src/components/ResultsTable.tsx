import type { PageResult } from '../types'

interface ResultsTableProps {
  pages: PageResult[]
  selectedIndex: number | null
  onSelect: (index: number) => void
}

export default function ResultsTable({ pages, selectedIndex, onSelect }: ResultsTableProps) {
  // sütunlar formun bilgi alanlarından gelir (alan adları formdan forma değişir)
  const sample = pages.find((p) => p.ok)
  const columns = sample
    ? Object.entries(sample.fields).filter(([, f]) => f.category !== 'answers').map(([name, f]) => ({ name, title: f.title }))
    : []

  return (
    <div className="tableWrap">
      <table>
        <thead>
          <tr>
            <th>#</th><th>Dosya</th>
            {columns.map((c) => <th key={c.name}>{c.title}</th>)}
            <th>Durum</th>
          </tr>
        </thead>
        <tbody>
          {pages.map((p) => (
            <tr
              key={p.index}
              className={`${p.index === selectedIndex ? 'selected' : ''} ${p.ok ? '' : 'failed'}`}
              onClick={() => onSelect(p.index)}
            >
              <td>{p.index + 1}</td>
              <td className="fileCell" title={p.source.file}>
                {p.source.file}{p.source.page > 1 || p.source.file.toLowerCase().endsWith('.pdf') ? ` · s.${p.source.page}` : ''}
              </td>
              {p.ok ? (
                <>
                  {columns.map((c) => {
                    const text = (p.fields[c.name]?.value ?? '').replace(/_/g, '')
                    return <td key={c.name} className={/^\d+$/.test(text) ? 'mono' : ''}>{text}</td>
                  })}
                  <td>
                    {p.flags.length ? <span className="badge warn">{p.flags.length} uyarı</span> : <span className="badge ok">Tamam</span>}
                  </td>
                </>
              ) : (
                <td colSpan={columns.length + 1}><span className="badge fail">{p.error}</span></td>
              )}
            </tr>
          ))}
          {pages.length === 0 && (
            <tr><td colSpan={columns.length + 3} className="emptyCell">Sayfalar işleniyor…</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
