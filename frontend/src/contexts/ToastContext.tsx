import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from 'react'

export interface Toast {
  id: string
  type: 'success' | 'error' | 'info'
  message: string
}

interface ToastContextValue {
  toasts: Toast[]
  toast: (type: Toast['type'], message: string) => void
  removeToast: (id: string) => void
  pauseToast: (id: string) => void
  resumeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())
  const remaining = useRef<Map<string, number>>(new Map())
  const DURATION = 4000

  const removeToast = useCallback((id: string) => {
    timers.current.delete(id)
    remaining.current.delete(id)
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const pauseToast = useCallback((id: string) => {
    const timer = timers.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.current.delete(id)
    }
  }, [])

  const resumeToast = useCallback((id: string) => {
    const rem = remaining.current.get(id)
    if (rem !== undefined && rem > 0) {
      const timer = setTimeout(() => removeToast(id), rem)
      timers.current.set(id, timer)
    }
  }, [removeToast])

  const toast = useCallback((type: Toast['type'], message: string) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    setToasts(prev => [...prev, { id, type, message }])
    remaining.current.set(id, DURATION)
    const timer = setTimeout(() => removeToast(id), DURATION)
    timers.current.set(id, timer)
  }, [removeToast])

  return (
    <ToastContext.Provider value={{ toasts, toast, removeToast, pauseToast, resumeToast }}>
      {children}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
