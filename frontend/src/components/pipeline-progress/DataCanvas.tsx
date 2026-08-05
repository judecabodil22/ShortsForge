import { useMemo, useRef } from 'react'
import { motion } from 'framer-motion'
import { type PipelineStatus, type Phase, getPhaseIndex, PHASE_LABELS, PHASES } from './types'
import { useThemeColors } from '@/hooks/useThemeColors'
import { themeRgb } from '@/lib/themeColors'

interface Props {
  status: PipelineStatus
}

const COLS = 16
const ROWS = 10
const TOTAL = COLS * ROWS

const CELL = 12
const GAP = 2

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

export default function DataCanvas({ status }: Props) {
  const colors = useThemeColors()
  const phaseColors = useMemo(() => {
    const palette = [colors.chart1, colors.chart3, colors.goldBright, colors.bronze, colors.chart2, colors.crimson, colors.goldDim]
    const map: Record<string, string> = {}
    PHASES.forEach((p, i) => {
      map[p] = palette[i % palette.length]
    })
    return map
  }, [colors])

  const getPhaseColor = (idx: number): string => {
    const keys = Object.keys(phaseColors)
    return phaseColors[keys[idx]] ?? colors.chart1
  }

  const currentIdx = getPhaseIndex(status.current_phase)
  const progress = status.progress / 100
  const idleBg = themeRgb('dark')

  const cells = useMemo(() => {
    const partition: number[] = []
    const numPhases = PHASES.length
    const perPhase = Math.floor(TOTAL / numPhases)
    for (let p = 0; p < numPhases; p++) {
      for (let i = 0; i < perPhase; i++) {
        partition.push(p)
      }
    }
    while (partition.length < TOTAL) partition.push(numPhases - 1)
    return partition
  }, [])

  const stableCells = useRef(shuffle(cells)).current

  const filled = currentIdx >= 0
    ? stableCells.map((phaseIdx) => phaseIdx < currentIdx || (phaseIdx === currentIdx))
    : stableCells.map(() => false)

  return (
    <div className="p-4 bg-40k-dark rounded-lg border border-40k-gold/10">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">
            Data Canvas
          </span>
          <span className="text-[10px] text-40k-gold-dim font-mono">
            {COLS}&times;{ROWS}
          </span>
        </div>
        <motion.div
          key={status.current_phase ?? 'idle'}
          initial={{ scale: 1.2, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="text-xs font-mono tabular-nums"
          style={{
            color: currentIdx >= PHASES.length
              ? colors.goldBright
              : currentIdx < 0
                ? colors.border
                : getPhaseColor(currentIdx),
          }}
        >
          {currentIdx >= 0 && currentIdx < PHASES.length
            ? `${PHASE_LABELS[Object.keys(phaseColors)[currentIdx] as Phase]} ${Math.round(progress * 100)}%`
            : currentIdx >= PHASES.length
              ? 'Complete'
              : 'Idle'}
        </motion.div>
      </div>

      <div
        className="grid mx-auto mb-3"
        style={{
          gridTemplateColumns: `repeat(${COLS}, ${CELL}px)`,
          gap: GAP,
          width: COLS * CELL + (COLS - 1) * GAP,
        }}
      >
        {stableCells.map((phaseIdx, i) => {
          const isFilled = filled[i]
          const baseColor = getPhaseColor(phaseIdx)
          const isCurrent = phaseIdx === currentIdx

          return (
            <motion.div
              key={i}
              style={{
                width: CELL,
                height: CELL,
                backgroundColor: isFilled ? baseColor : idleBg,
                borderRadius: Math.max(1, CELL / 6),
              }}
              animate={
                isFilled
                  ? {
                      opacity: isCurrent ? [0.6, 1, 0.6] : 1,
                      scale: isCurrent ? [1, 1.08, 1] : 1,
                      boxShadow: isCurrent
                        ? [`0 0 0px ${baseColor}00`, `0 0 6px ${baseColor}80`, `0 0 0px ${baseColor}00`]
                        : `0 0 2px ${baseColor}40`,
                    }
                  : { opacity: 0.04, scale: 0.85, boxShadow: 'none' }
              }
              transition={
                isCurrent
                  ? {
                      duration: 0.8 + (i % 5) * 0.3,
                      repeat: Infinity,
                      ease: 'easeInOut',
                      delay: (i % 7) * 0.1,
                    }
                  : { duration: 0.4, delay: isFilled ? (i % TOTAL) * 0.001 : 0 }
              }
            />
          )
        })}
      </div>

      <div className="relative h-1.5 bg-black/40 rounded-full overflow-hidden mb-3">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            background: `linear-gradient(90deg, ${getPhaseColor(0)}, ${getPhaseColor(Math.max(0, Math.min(PHASES.length - 1, currentIdx)))})`,
          }}
          animate={{ width: `${Math.min(100, Math.max(0, currentIdx) / (PHASES.length - 1) * 100)}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            background: currentIdx >= 0
              ? `linear-gradient(90deg, transparent, ${getPhaseColor(currentIdx)})`
              : 'none',
            width: `${progress * 100}%`,
            opacity: 0.6,
          }}
          animate={{
            left: `${Math.min(100, Math.max(0, currentIdx) / (PHASES.length - 1) * 100)}%`,
          }}
          transition={{ duration: 0.3 }}
        />
      </div>

      <div className="flex items-center justify-between gap-1 text-[9px]">
        {Object.entries(phaseColors).map(([key, color], i) => {
          const phaseLabel = PHASE_LABELS[key as Phase] ?? key
          const isActive = i === currentIdx
          const isPast = i < currentIdx
          return (
            <div
              key={key}
              className="flex items-center gap-1"
              style={{ opacity: isActive || isPast ? 1 : 0.35 }}
            >
              <motion.div
                className="w-1.5 h-1.5 rounded-[1px]"
                style={{ backgroundColor: color }}
                animate={isActive ? { scale: [1, 1.5, 1] } : {}}
                transition={isActive ? { duration: 1.2, repeat: Infinity } : {}}
              />
              <span
                className="truncate max-w-[5ch]"
                style={{ color: isActive ? color : undefined }}
              >
                {phaseLabel}
              </span>
            </div>
          )
        })}
      </div>

      <motion.p
        key={status.message}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-[10px] text-gray-500 text-center font-mono mt-2 truncate"
      >
        {status.message || 'Idle'}
      </motion.p>
    </div>
  )
}
