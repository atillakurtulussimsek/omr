import { useRef, useState } from 'react'
import type { Detection, FieldSpec, FormSpec, TestResult } from '../types'
import { fieldBounds } from './fieldUtils'
import type { Rect } from './fieldUtils'

interface EditorCanvasProps {
  spec: FormSpec
  detection: Detection | null
  imageUrl: string | null
  zoom: number
  selectedIndex: number | null
  isAnchorMode: boolean
  showDetected: boolean
  testResult: TestResult | null
  onSelect: (index: number | null) => void
  onDraw: (rect: Rect) => void
  onMove: (index: number, x: number, y: number) => void
  onToggleAnchor: (anchor: [number, number]) => void
}

type Drag =
  | { kind: 'draw'; startX: number; startY: number; x: number; y: number }
  | { kind: 'move'; index: number; offsetX: number; offsetY: number; moved: boolean }

const FIELD_COLORS = { info: '#2f6fe0', answers: '#d4246f' }
const sameAnchor = (a: [number, number], b: [number, number]) => Math.hypot(a[0] - b[0], a[1] - b[1]) < 8

function isFilled(field: FieldSpec, row: number, col: number, testResult: TestResult | null): boolean {
  const groups = testResult?.fields[field.name]?.groups
  if (!groups) return false
  const fill = field.type === 'rows' ? groups[row]?.fills[col] : groups[col]?.fills[row]
  return (fill ?? 0) >= 0.45
}

export default function EditorCanvas(props: EditorCanvasProps) {
  const { spec, detection, imageUrl, zoom, selectedIndex, isAnchorMode, showDetected, testResult } = props
  const svgRef = useRef<SVGSVGElement>(null)
  const [drag, setDrag] = useState<Drag | null>(null)

  function toCanvas(e: React.PointerEvent): [number, number] {
    const svg = svgRef.current!
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(svg.getScreenCTM()!.inverse())
    return [p.x, p.y]
  }

  function startDraw(e: React.PointerEvent) {
    if (isAnchorMode || e.button !== 0) return
    const [x, y] = toCanvas(e)
    svgRef.current!.setPointerCapture(e.pointerId)
    setDrag({ kind: 'draw', startX: x, startY: y, x, y })
  }

  function startMove(e: React.PointerEvent, index: number) {
    if (isAnchorMode || e.button !== 0) return
    e.stopPropagation()
    const [x, y] = toCanvas(e)
    svgRef.current!.setPointerCapture(e.pointerId)
    props.onSelect(index)
    setDrag({ kind: 'move', index, offsetX: x - spec.fields[index].x, offsetY: y - spec.fields[index].y, moved: false })
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!drag) return
    const [x, y] = toCanvas(e)
    if (drag.kind === 'draw') setDrag({ ...drag, x, y })
    else {
      props.onMove(drag.index, Math.round((x - drag.offsetX) * 2) / 2, Math.round((y - drag.offsetY) * 2) / 2)
      if (!drag.moved) setDrag({ ...drag, moved: true })
    }
  }

  function onPointerUp() {
    if (drag?.kind === 'draw') {
      const rect = {
        x0: Math.min(drag.startX, drag.x), y0: Math.min(drag.startY, drag.y),
        x1: Math.max(drag.startX, drag.x), y1: Math.max(drag.startY, drag.y),
      }
      if (rect.x1 - rect.x0 > 8 && rect.y1 - rect.y0 > 8) props.onDraw(rect)
      else props.onSelect(null)
    }
    setDrag(null)
  }

  const radius = spec.bubbleRadius
  const half = (spec.anchorSize || 32) / 2
  const unusedAnchors = (detection?.anchors ?? []).filter((d) => !spec.anchors.some((a) => sameAnchor(a, d)))

  return (
    <svg
      ref={svgRef}
      className={`editorCanvas ${isAnchorMode ? 'anchorMode' : ''}`}
      viewBox={`0 0 ${spec.width} ${spec.height}`}
      style={{ width: `${zoom * 100}%` }}
      onPointerDown={startDraw}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => setDrag(null)}
      onDragStart={(e) => e.preventDefault()}
    >
      <rect width={spec.width} height={spec.height} fill="#fff" />
      {imageUrl && <image href={imageUrl} width={spec.width} height={spec.height} pointerEvents="none" />}

      {showDetected && detection?.circles.map(([x, y, r], i) => (
        <circle key={i} cx={x} cy={y} r={r} className="detectedCircle" />
      ))}

      {spec.fields.map((f, index) => {
        const b = fieldBounds(f, radius)
        const color = FIELD_COLORS[f.category] ?? FIELD_COLORS.info
        const isSelected = index === selectedIndex
        return (
          <g key={index} className={`field ${isSelected ? 'selected' : ''}`} style={{ color }}>
            <rect
              x={b.x0} y={b.y0} width={b.x1 - b.x0} height={b.y1 - b.y0}
              className="fieldRect"
              onPointerDown={(e) => startMove(e, index)}
            />
            {Array.from({ length: f.rows }, (_, r) =>
              Array.from({ length: f.cols }, (_, c) => (
                <circle
                  key={`${r}-${c}`}
                  cx={f.x + c * f.stepX} cy={f.y + r * f.stepY} r={radius * 0.75}
                  className={`fieldCell ${isFilled(f, r, c, testResult) ? 'filled' : ''}`}
                />
              )),
            )}
            <g transform={`translate(${b.x0}, ${b.y0 - 6})`} className="fieldTag">
              <rect x={0} y={-30} width={(f.title.length + 8) * 13.5} height={30} rx={4} />
              <text x={8} y={-8}>{f.title} · {f.rows}×{f.cols}</text>
            </g>
          </g>
        )
      })}

      {spec.alignment === 'timing' && (spec.timingMarks ?? []).map((m, i) => {
        const [long, short] = spec.timingSize ?? [38, 14]
        const other = spec.timingMarks![i === 0 ? 1 : i - 1] ?? m
        const isVertical = Math.abs(m[1] - other[1]) >= Math.abs(m[0] - other[0])
        const [w, h] = isVertical ? [long, short] : [short, long]
        return <rect key={`t${i}`} x={m[0] - w / 2 - 4} y={m[1] - h / 2 - 4} width={w + 8} height={h + 8} className="anchor used" />
      })}
      {spec.alignment !== 'timing' && unusedAnchors.map((a, i) => (
        <rect
          key={`u${i}`} x={a[0] - half} y={a[1] - half} width={half * 2} height={half * 2}
          className="anchor unused" onClick={() => isAnchorMode && props.onToggleAnchor(a)}
        />
      ))}
      {spec.alignment !== 'timing' && spec.anchors.map((a, i) => (
        <rect
          key={`a${i}`} x={a[0] - half - 5} y={a[1] - half - 5} width={half * 2 + 10} height={half * 2 + 10}
          className="anchor used" onClick={() => isAnchorMode && props.onToggleAnchor(a)}
        />
      ))}

      {drag?.kind === 'draw' && (
        <rect
          x={Math.min(drag.startX, drag.x)} y={Math.min(drag.startY, drag.y)}
          width={Math.abs(drag.x - drag.startX)} height={Math.abs(drag.y - drag.startY)}
          className="drawRect"
        />
      )}
    </svg>
  )
}
