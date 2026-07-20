import { motion, useMotionValue, useTransform, animate } from 'framer-motion'
import { useEffect } from 'react'
import { PHASES, PHASE_LABELS, type PipelineStatus, getPhaseIndex } from './types'

interface Props {
  status: PipelineStatus
}

const GEAR_COUNT = 6

function GearSvg({
  index,
  phase,
  isActive,
  isComplete,
  progress,
}: {
  index: number
  phase: string
  isActive: boolean
  isComplete: boolean
  progress: number
}) {
  const cx = 50
  const cy = 50
  const r = 32
  const teeth = 8
  const toothLen = 8

  const pathData = (() => {
    const pts: string[] = []
    for (let i = 0; i < teeth * 2; i++) {
      const angle = (Math.PI * i) / teeth - Math.PI / 2
      const isTooth = i % 2 === 0
      const radius = isTooth ? r + toothLen : r
      const x = cx + radius * Math.cos(angle)
      const y = cy + radius * Math.sin(angle)
      pts.push(`${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`)
    }
    pts.push('Z')
    return pts.join(' ')
  })()

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative w-16 h-16">
        <svg viewBox="0 0 100 100" className="w-full h-full">
          <motion.g
            animate={
              isActive
                ? { rotate: 360 }
                : isComplete
                ? { rotate: 0 }
                : undefined
            }
            transition={
              isActive
                ? { duration: 4, repeat: Infinity, ease: 'linear' }
                : { duration: 0.5 }
            }
            style={{ originX: '50%', originY: '50%' }}
          >
            <motion.path
              d={pathData}
              fill={isComplete ? 'rgba(201,162,39,0.2)' : isActive ? 'rgba(201,162,39,0.1)' : 'rgba(255,255,255,0.03)'}
              stroke={isComplete ? 'rgb(201,162,39)' : isActive ? 'rgb(232,197,71)' : 'rgb(74,40,40)'}
              strokeWidth={2}
              initial={false}
              animate={{
                strokeOpacity: isActive ? [0.5, 1, 0.5] : isComplete ? 1 : 0.3,
                transition: isActive ? { duration: 2, repeat: Infinity } : {},
              }}
            />
            <circle
              cx={cx} cy={cy} r={6}
              fill={isComplete ? 'rgb(201,162,39)' : isActive ? 'rgb(232,197,71)' : 'rgb(74,40,40)'}
            />
          </motion.g>
          {isComplete && (
            <motion.text
              x={cx} y={cy + 1}
              textAnchor="middle" dominantBaseline="central"
              fill="rgb(201,162,39)" fontSize={28} fontWeight="bold"
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 15 }}
            >
              ✓
            </motion.text>
          )}
        </svg>
        {isActive && (
          <motion.div
            className="absolute inset-0 rounded-full"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 0.3, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
            style={{
              boxShadow: '0 0 20px rgba(201,162,39,0.4), 0 0 40px rgba(201,162,39,0.2)',
            }}
          />
        )}
      </div>
      <span
        className={`text-[10px] font-medium leading-tight text-center ${
          isComplete
            ? 'text-40k-gold'
            : isActive
            ? 'text-40k-gold-bright'
            : 'text-gray-600'
        }`}
      >
        {PHASE_LABELS[phase as keyof typeof PHASE_LABELS] || phase}
      </span>
    </div>
  )
}

export default function CogitatorArray({ status }: Props) {
  const currentIdx = getPhaseIndex(status.current_phase)

  return (
    <div className="p-4 bg-40k-dark rounded-lg">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">Cogitator Array</span>
        <span className="text-xs text-40k-gold-dim">{status.progress}%</span>
      </div>

      <div className="flex items-center justify-between gap-1 px-2">
        {PHASES.map((phase, i) => (
          <GearSvg
            key={phase}
            index={i}
            phase={phase}
            isActive={i === currentIdx}
            isComplete={i < currentIdx}
            progress={status.progress}
          />
        ))}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-40k-black rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-40k-gold to-40k-gold-bright"
            initial={{ width: 0 }}
            animate={{ width: `${status.progress}%` }}
            transition={{ type: 'spring', stiffness: 50, damping: 20 }}
          />
        </div>
      </div>

      <motion.p
        key={status.message}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-xs text-gray-500 mt-2 text-center font-mono truncate"
      >
        {status.message || 'Idle'}
      </motion.p>
    </div>
  )
}
