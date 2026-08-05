import { motion } from 'framer-motion'
import { PHASES, type PipelineStatus, getPhaseIndex } from './types'

interface Props {
  status: PipelineStatus
}

interface StageDef {
  label: string
  height: number
  color: string
  borderColor: string
}

const STAGES: StageDef[] = [
  { label: 'Foundation', height: 12, color: 'from-40k-bronze/30 to-40k-bronze/10', borderColor: 'border-40k-bronze' },
  { label: 'Frame', height: 18, color: 'from-40k-gold-dim/30 to-40k-gold-dim/10', borderColor: 'border-40k-gold-dim' },
  { label: 'Walls', height: 22, color: 'from-40k-gold/30 to-40k-gold/10', borderColor: 'border-40k-gold' },
  { label: 'Roof', height: 16, color: 'from-40k-gold-bright/30 to-40k-gold-bright/10', borderColor: 'border-40k-gold-bright' },
  { label: 'Spire', height: 14, color: 'from-40k-crimson/30 to-40k-crimson/10', borderColor: 'border-40k-crimson' },
  { label: 'Aura', height: 18, color: 'from-40k-crimson-bright/20 to-transparent', borderColor: 'border-40k-crimson-bright' },
  { label: 'Crown', height: 16, color: 'from-40k-gold-bright/30 to-40k-crimson-bright/10', borderColor: 'border-40k-gold-bright' },
]

const PHASE_ICONS: Record<string, string> = {
  download: '⬇',
  transcribe: '📝',
  context: '🔍',
  scripts: '📄',
  clips: '✂',
  tts: '🎤',
  assemble: '🏗',
}

export default function Construction({ status }: Props) {
  const currentIdx = getPhaseIndex(status.current_phase)
  const builtCount = Math.max(0, currentIdx)
  const totalHeight = STAGES.reduce((s, st) => s + st.height, 0)

  return (
    <div className="p-4 bg-40k-dark rounded-lg">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">Construction</span>
        <span className="text-xs text-40k-gold-dim">
          Phase {Math.min(builtCount + 1, PHASES.length)}/{PHASES.length}
        </span>
      </div>

      <div className="flex gap-4 items-end justify-center mb-3">
        <div className="flex flex-col items-end justify-end relative" style={{ height: totalHeight }}>
          {STAGES.map((stage, i) => {
            const isBuilt = i < builtCount
            const isCurrent = i === builtCount && currentIdx < PHASES.length

            return (
              <motion.div
                key={i}
                initial={{ height: 0, opacity: 0 }}
                animate={
                  isBuilt || isCurrent
                    ? { height: stage.height, opacity: 1 }
                    : { height: 0, opacity: 0 }
                }
                transition={{ type: 'spring', stiffness: 100, damping: 20, delay: isBuilt ? i * 0.1 : 0 }}
                className={`w-24 bg-gradient-to-t ${stage.color} border-l border-r ${stage.borderColor} flex items-center justify-center relative`}
                style={{ minHeight: isBuilt || isCurrent ? stage.height : 0 }}
              >
                {isCurrent && (
                  <motion.div
                    className="absolute inset-0"
                    animate={{ opacity: [0, 1, 0] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    style={{ background: 'linear-gradient(to top, rgb(var(--40k-gold-rgb) / 0.3), transparent)' }}
                  />
                )}
                {(isBuilt || isCurrent) && (
                  <span className="text-[9px] text-white font-medium leading-tight text-center truncate px-1">
                    {isBuilt ? '✓' : isCurrent ? PHASE_ICONS[PHASES[i]] || stage.label : ''}
                  </span>
                )}
              </motion.div>
            )
          })}

          <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-40k-gold/50" />

          <motion.div
            className="absolute bottom-0 left-0 h-[2px] bg-gradient-to-r from-40k-gold to-40k-gold-bright"
            initial={{ width: 0 }}
            animate={{ width: `${status.progress}%` }}
            transition={{ type: 'spring', stiffness: 50, damping: 20 }}
          />
        </div>

        <div className="flex flex-col gap-1 text-[9px] text-gray-500">
          {STAGES.map((stage, i) => {
            const isBuilt = i < builtCount
            const isCurrent = i === builtCount && currentIdx < PHASES.length
            return (
              <div
                key={i}
                className={`flex items-center gap-1 leading-tight ${
                  isBuilt ? 'text-40k-gold' : isCurrent ? 'text-40k-gold-bright' : 'text-gray-600'
                }`}
                style={{ height: STAGES[i].height }}
              >
                <span>{isBuilt ? '✓' : isCurrent ? '◈' : '○'}</span>
                <span>{stage.label}</span>
              </div>
            )
          })}
        </div>
      </div>

      <motion.p
        key={status.message}
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-xs text-gray-500 text-center font-mono truncate"
      >
        {status.message || 'Idle'}
      </motion.p>
    </div>
  )
}
