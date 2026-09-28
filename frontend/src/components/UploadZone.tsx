import { useRef, useState } from 'react'

const ACCEPT = '.jpg,.jpeg,.png,.tif,.tiff,.bmp,.pdf'

interface UploadZoneProps {
  files: File[]
  onChange: (files: File[]) => void
  disabled: boolean
}

export default function UploadZone({ files, onChange, disabled }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)

  function addFiles(list: FileList | null) {
    if (!list || disabled) return
    const allowed = ACCEPT.split(',')
    const added = Array.from(list).filter((f) => allowed.some((ext) => f.name.toLowerCase().endsWith(ext)))
    onChange([...files, ...added].sort((a, b) => a.name.localeCompare(b.name, 'tr', { numeric: true })))
  }

  const totalMb = files.reduce((sum, f) => sum + f.size, 0) / 1e6

  return (
    <div
      className={`uploadZone ${isDragging ? 'dragging' : ''} ${disabled ? 'disabled' : ''}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(e) => { e.preventDefault(); setIsDragging(false); addFiles(e.dataTransfer.files) }}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        hidden
        onChange={(e) => { addFiles(e.target.files); e.target.value = '' }}
      />
      <span className="bubbleRow" aria-hidden="true"><i>A</i><i>B</i><i className="on">C</i><i>D</i><i>E</i></span>
      {files.length === 0 ? (
        <p>Taramaları buraya sürükleyin veya seçmek için tıklayın<small>JPG, PNG, TIFF veya çok sayfalı PDF</small></p>
      ) : (
        <p>
          {files.length} dosya · {totalMb.toFixed(1)} MB
          <small>{files.slice(0, 4).map((f) => f.name).join(', ')}{files.length > 4 ? ' …' : ''}</small>
          <button
            className="link"
            onClick={(e) => { e.stopPropagation(); onChange([]) }}
            disabled={disabled}
          >
            Temizle
          </button>
        </p>
      )}
    </div>
  )
}
