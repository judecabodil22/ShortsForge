import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Download, FileText, Search, FileEdit, Scissors, Mic,
} from 'lucide-react'
import { getLogs } from '@/lib/api'
import { PHASES, PHASE_LABELS, type PipelineStatus, getPhaseIndex } from './types'

interface Props {
  status: PipelineStatus
}

const PHASE_ICONS = [Download, FileText, Search, FileEdit, Scissors, Mic]

export default function PhaseTimeline({ status }: Props) {
  const currentIdx = getPhaseIndex(status.current_phase)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  const { data: logsData } = useQuery({
    queryKey: ['logs'],
    queryFn: () => getLogs(100),
    refetchInterval: 3000,
  })

  const logs = logsData?.logs || []

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs.length, autoScroll])

  return (
    <div className="p-4 bg-40k-dark rounded-lg">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">Timeline</span>
        <span className="text-xs text-40k-gold-dim">{status.progress}%</span>
      </div>

      <div className="relative flex items-start justify-between mb-4 px-1">
        <div className="absolute top-4 left-6 right-6 h-0.5 bg-40k-border">
          <motion.div
            className="h-full bg-gradient-to-r from-40k-gold to-40k-crimson-bright"
            initial={{ width: 0 }}
            animate={{
              width: `${currentIdx >= 0 ? ((currentIdx) / (PHASES.length - 1)) * 100 : 0}%`,
            }}
            transition={{ type: 'spring', stiffness: 50, damping: 20 }}
          />
        </div>

        {PHASES.map((phase, i) => {
          const Icon = PHASE_ICONS[i]
          const isComplete = i < currentIdx
          const isActive = i === currentIdx

          return (
            <div key={phase} className="flex flex-col items-center relative z-10">
              <motion.div
                initial={false}
                animate={
                  isActive
                    ? { scale: [1, 1.15, 1], transition: { duration: 2, repeat: Infinity } }
                    : { scale: 1 }
                }
                className={`w-8 h-8 rounded-full flex items-center justify-center ${
                  isComplete
                    ? 'bg-40k-gold/20 border-2 border-40k-gold'
                    : isActive
                    ? 'bg-40k-gold-bright/20 border-2 border-40k-gold-bright'
                    : 'bg-40k-black border-2 border-40k-border'
                }`}
              >
                {isComplete ? (
                  <motion.span
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className="text-40k-gold text-xs font-bold"
                  >
                    ✓
                  </motion.span>
                ) : (
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-40k-gold-bright' : 'text-gray-600'}`} />
                )}
              </motion.div>
              <span
                className={`text-[9px] mt-1 font-medium leading-tight text-center ${
                  isComplete
                    ? 'text-40k-gold'
                    : isActive
                    ? 'text-40k-gold-bright'
                    : 'text-gray-600'
                }`}
              >
                {PHASE_LABELS[phase]}
              </span>
              {isActive && (
                <motion.div
                  className="w-1 h-1 rounded-full bg-40k-gold-bright mt-0.5"
                  animate={{ opacity: [0, 1, 0] }}
                  transition={{ duration: 1, repeat: Infinity }}
                />
              )}
            </div>
          )
        })}
      </div>

      <div className="flex items-center gap-2 mb-2">
        <div className="flex-1 h-1 bg-40k-black rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-40k-gold to-40k-crimson-bright"
            initial={{ width: 0 }}
            animate={{ width: `${status.progress}%` }}
            transition={{ type: 'spring', stiffness: 50, damping: 20 }}
          />
        </div>
        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className={`text-[9px] px-1.5 py-0.5 rounded ${
            autoScroll ? 'text-40k-gold bg-40k-gold/10' : 'text-gray-600'
          }`}
        >
          auto
        </button>
      </div>

      <motion.p
        key={status.message}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-xs text-40k-gold-dim text-center font-mono truncate mb-2"
      >
        {status.message || 'Idle'}
      </motion.p>

      <div className="h-24 bg-40k-black border border-40k-border rounded overflow-y-auto px-2 py-1.5 font-mono text-[10px] leading-tight">
        <AnimatePresence mode="popLayout">
          {logs.length > 0 ? (
            logs.slice(-40).map((log: string, i: number) => {
              const lower = log.toLowerCase()
              const color = lower.includes('error') || lower.includes('failed')
                ? 'text-red-400'
                : lower.includes('warn')
                ? 'text-yellow-400'
                : lower.includes('complete') || lower.includes('success')
                ? 'text-green-400'
                : 'text-40k-gold-dim/70'
              return (
                <motion.div
                  key={`${i}-${log.slice(0, 20)}`}
                  initial={{ opacity: 0, x: -4 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  className={`${color} whitespace-pre-wrap mb-0.5`}
                >
                  {log}
                </motion.div>
              )
            })
          ) : (
            <div className="text-gray-600 italic">Waiting for logs...</div>
          )}
        </AnimatePresence>
        <div ref={logsEndRef} />
      </div>
    </div>
  )
}
