import { useRef, useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Cog, Building2, Timeline, Grid3x3, Shuffle } from 'lucide-react'
import { type PipelineStatus, type FullStatus } from './types'
import CogitatorArray from './CogitatorArray'
import Construction from './Construction'
import PhaseTimeline from './PhaseTimeline'
import DataCanvas from './DataCanvas'

const VIZ_MODULES = [
  { key: 'cogitator-array', label: 'Cogitator Array', icon: Cog, component: CogitatorArray },
  { key: 'construction', label: 'Construction', icon: Building2, component: Construction },
  { key: 'phase-timeline', label: 'Phase Timeline', icon: Timeline, component: PhaseTimeline },
  { key: 'data-canvas', label: 'Data Canvas', icon: Grid3x3, component: DataCanvas },
] as const

type VizKey = (typeof VIZ_MODULES)[number]['key']

function pickRandomViz(lastKey: VizKey | null): VizKey {
  const available = VIZ_MODULES.map((m) => m.key).filter((k) => k !== lastKey)
  return available[Math.floor(Math.random() * available.length)]
}

interface Props {
  status: FullStatus | undefined
}

export default function PipelineProgress({ status }: Props) {
  const vizRef = useRef<VizKey | null>(null)
  const [currentViz, setCurrentViz] = useState<VizKey | null>(null)
  const wasRunningRef = useRef(false)

  useEffect(() => {
    const isRunning = status?.pipeline?.running ?? false
    const prevRunning = wasRunningRef.current

    if (isRunning && !prevRunning) {
      const chosen = pickRandomViz(vizRef.current)
      vizRef.current = chosen
      setCurrentViz(chosen)
    } else if (!isRunning && prevRunning) {
      setCurrentViz(null)
    } else if (!isRunning && currentViz === null) {
      const chosen = pickRandomViz(vizRef.current)
      vizRef.current = chosen
      setCurrentViz(chosen)
    }

    wasRunningRef.current = isRunning
  }, [status?.pipeline?.running])

  const handleReroll = useCallback(() => {
    const chosen = pickRandomViz(vizRef.current)
    vizRef.current = chosen
    setCurrentViz(chosen)
  }, [])

  if (!status) return null

  const pipeline = status.pipeline
  const isRunning = pipeline.running
  const activeModule = VIZ_MODULES.find((m) => m.key === currentViz)

  return (
    <div className="relative">
      {isRunning && (
        <AnimatePresence mode="wait">
          <motion.div
            key={currentViz}
            initial={{ opacity: 0, y: 10, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.97 }}
            transition={{ duration: 0.3 }}
          >
            {activeModule && (
              <activeModule.component status={pipeline} />
            )}
          </motion.div>
        </AnimatePresence>
      )}

      {!isRunning && activeModule && pipeline.last_run && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
        >
          <activeModule.component status={pipeline} />
        </motion.div>
      )}

      {!isRunning && !pipeline.last_run && (
        <div className="p-4 bg-40k-dark rounded-lg">
          <p className="text-xs text-gray-500 text-center">Run the pipeline to see progress visualization</p>
        </div>
      )}

      <button
        onClick={handleReroll}
        className="absolute top-2 right-2 p-1 rounded text-gray-600 hover:text-40k-gold hover:bg-40k-gold/10 transition-colors"
        title="Switch visualization"
      >
        <Shuffle className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}
