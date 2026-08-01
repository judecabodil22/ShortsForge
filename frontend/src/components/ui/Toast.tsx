import { motion, AnimatePresence } from 'framer-motion'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'
import { useToast } from '@/contexts/ToastContext'

const iconMap = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info,
}

const styles = {
  success: 'bg-green-900/80 border-green-700 text-green-200',
  error: 'bg-red-900/80 border-red-700 text-red-200',
  info: 'bg-blue-900/80 border-blue-700 text-blue-200',
}

export default function ToastContainer() {
  const { toasts, removeToast, pauseToast, resumeToast } = useToast()

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-3 pointer-events-none">
      <AnimatePresence>
        {toasts.map(t => {
          const Icon = iconMap[t.type]
          return (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -10, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              onMouseEnter={() => pauseToast(t.id)}
              onMouseLeave={() => resumeToast(t.id)}
              className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg min-w-[300px] max-w-[420px] ${styles[t.type]}`}
            >
              <Icon className="w-5 h-5 mt-0.5 flex-shrink-0" />
              <p className="text-sm flex-1">{t.message}</p>
              <button
                onClick={() => removeToast(t.id)}
                className="text-white/60 hover:text-white transition-colors flex-shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
