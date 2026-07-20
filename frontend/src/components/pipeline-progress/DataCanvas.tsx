import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { type PipelineStatus, getPhaseIndex } from './types'

interface Props {
  status: PipelineStatus
}

const GRID_COLS = 16
const GRID_ROWS = 10

const PALETTES = [
  ['#c9a227', '#e8c547', '#8b7312', '#7a1029', '#b71c3a', '#d45555'],
  ['#cd7f32', '#daa06d', '#8b5a2b', '#9b1b30', '#dc2626', '#ef4444'],
  ['#84cc16', '#a3e635', '#526a0a', '#6b1a8b', '#9333ea', '#a855f7'],
  ['#eab308', '#facc15', '#9a7a00', '#5c7a1a', '#84cc16', '#a3e635'],
]

function seededRandom(seed: number): () => number {
  let s = seed
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff
    return (s >>> 0) / 0xffffffff
  }
}

export default function DataCanvas({ status }: Props) {
  const currentIdx = getPhaseIndex(status.current_phase)

  const { cells, palette } = useMemo(() => {
    const seed = Date.now()
    const rng = seededRandom(seed)
    const pal = PALETTES[Math.floor(rng() * PALETTES.length)]
    const totalCells = GRID_COLS * GRID_ROWS
    const cellsPerPhase = Math.ceil(totalCells / 6)

    const cellData: Array<{ phaseIdx: number; order: number }> = []
    for (let i = 0; i < totalCells; i++) {
      const phaseIdx = Math.min(Math.floor(i / cellsPerPhase), 5)
      cellData.push({ phaseIdx, order: i })
    }

    for (let i = cellData.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1))
      ;[cellData[i], cellData[j]] = [cellData[j], cellData[i]]
    }

    return { cells: cellData, palette: pal }
  }, [])

  const filledCount = cells.filter((c) => c.phaseIdx < currentIdx).length
  const fillingCellCount = currentIdx >= 0 && currentIdx < 6
    ? cells.filter((c) => c.phaseIdx === currentIdx).length
    : 0
  const fillProgress = fillingCellCount > 0
    ? (status.progress % 100) / 100
    : 0
  const visibleCount = filledCount + Math.floor(fillingCellCount * fillProgress)

  return (
    <div className="p-4 bg-40k-dark rounded-lg">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">Data Canvas</span>
        <span className="text-xs text-40k-gold-dim">{status.progress}%</span>
      </div>

      <div
        className="grid gap-0.5 mx-auto mb-3"
        style={{
          gridTemplateColumns: `repeat(${GRID_COLS}, 1fr)`,
          maxWidth: GRID_COLS * 16,
        }}
      >
        {cells.map((cell, i) => {
          const isFilled = i < visibleCount
          const phaseColor = palette[Math.min(cell.phaseIdx, palette.length - 1)]

          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, scale: 0 }}
              animate={
                isFilled
                  ? { opacity: 1, scale: 1 }
                  : { opacity: 0.05, scale: 0.8 }
              }
              transition={{ duration: 0.3, delay: isFilled ? (i - filledCount) * 0.003 : 0 }}
              className="aspect-square rounded-sm"
              style={{
                backgroundColor: isFilled ? phaseColor : 'rgb(20, 8, 8)',
                boxShadow: isFilled ? `0 0 4px ${phaseColor}40` : 'none',
              }}
            />
          )
        })}
      </div>

      <div className="flex items-center justify-center gap-3 text-[10px]">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-1">
            <div
              className="w-2 h-2 rounded-sm"
              style={{ backgroundColor: palette[Math.min(i, palette.length - 1)] }}
            />
            <span className={i <= currentIdx ? 'text-40k-gold' : 'text-gray-600'}>
              Phase {i + 1}
            </span>
          </div>
        ))}
      </div>

      <motion.p
        key={status.message}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-xs text-gray-500 text-center font-mono mt-2 truncate"
      >
        {status.message || 'Idle'}
      </motion.p>
    </div>
  )
}
