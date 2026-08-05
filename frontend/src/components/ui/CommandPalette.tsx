import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, FileText, Network, BarChart3, Database, Settings, FileEdit,
  Zap, X, Brain, Castle, Play, RefreshCw,
} from 'lucide-react'
import clsx from 'clsx'
import { runPipeline, syncMetrics } from '@/lib/api'
import { useToast } from '@/contexts/ToastContext'

interface Command {
  id: string
  label: string
  icon: React.ReactNode
  action: () => void
  category: string
}

export default function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const { toast } = useToast()

  const commands: Command[] = useMemo(() => [
    { id: 'run-pipeline', label: 'Run Pipeline', icon: <Play className="w-4 h-4" />, action: async () => {
      try {
        await runPipeline()
        toast('success', 'Pipeline started')
      } catch (e: any) {
        toast('error', e?.message || 'Failed to start pipeline')
      }
    }, category: 'Actions' },
    { id: 'sync-metrics', label: 'Sync Metrics', icon: <RefreshCw className="w-4 h-4" />, action: async () => {
      try {
        await syncMetrics()
        toast('success', 'Metrics sync started')
      } catch (e: any) {
        toast('error', e?.message || 'Failed to sync metrics')
      }
    }, category: 'Actions' },
    { id: 'mempalace', label: 'Go to MemPalace', icon: <Castle className="w-4 h-4" />, action: () => navigate('/mempalace'), category: 'Actions' },
    { id: 'dashboard', label: 'Go to Dashboard', icon: <Zap className="w-4 h-4" />, action: () => navigate('/dashboard'), category: 'Navigation' },
    { id: 'graph', label: 'Go to Knowledge Graph', icon: <Network className="w-4 h-4" />, action: () => navigate('/graph'), category: 'Navigation' },
    { id: 'scripts', label: 'Go to Scripts', icon: <FileText className="w-4 h-4" />, action: () => navigate('/scripts'), category: 'Navigation' },
    { id: 'learning', label: 'Go to Learning Dashboard', icon: <Brain className="w-4 h-4" />, action: () => navigate('/learning'), category: 'Navigation' },
    { id: 'metrics', label: 'Go to Performance', icon: <BarChart3 className="w-4 h-4" />, action: () => navigate('/metrics'), category: 'Navigation' },
    { id: 'context', label: 'Go to Context', icon: <Database className="w-4 h-4" />, action: () => navigate('/context'), category: 'Navigation' },
    { id: 'settings', label: 'Go to Settings', icon: <Settings className="w-4 h-4" />, action: () => navigate('/settings'), category: 'Navigation' },
    { id: 'prompts', label: 'Go to Prompts', icon: <FileEdit className="w-4 h-4" />, action: () => navigate('/prompts'), category: 'Navigation' },
  ], [navigate, toast])

  const filteredCommands = commands.filter(cmd =>
    cmd.label.toLowerCase().includes(query.toLowerCase()) ||
    cmd.category.toLowerCase().includes(query.toLowerCase())
  )

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setIsOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isOpen])

  const close = () => {
    setIsOpen(false)
    setQuery('')
  }

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(prev => Math.min(prev + 1, filteredCommands.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(prev => Math.max(prev - 1, 0))
    } else if (e.key === 'Enter' && filteredCommands[selectedIndex]) {
      filteredCommands[selectedIndex].action()
      close()
    } else if (e.key === 'Escape') {
      close()
    }
  }, [filteredCommands, selectedIndex])

  return (
    <>
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="flex items-center gap-2 px-3 py-1.5 rounded bg-40k-card border border-40k-border text-gray-400 hover:text-40k-gold hover:border-40k-gold/30 transition-all corner-notch"
      >
        <Search className="w-4 h-4" />
        <span className="text-sm">Search</span>
        <kbd className="ml-2 px-1.5 py-0.5 text-xs bg-40k-black/50 rounded border border-40k-border">⌘K</kbd>
      </button>

      <AnimatePresence>
        {isOpen && (
          <>
            <motion.div
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={close}
            />
            <motion.div
              className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-lg z-50"
              initial={{ opacity: 0, y: -20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.95 }}
              transition={{ duration: 0.15 }}
            >
              <div className="bg-40k-dark border border-40k-border overflow-hidden corner-notch shadow-[var(--40k-shadow-gold)]">
                <div className="px-4 py-1.5 border-b border-40k-border bg-40k-card/40">
                  <span className="terminal-label text-40k-gold-dim">// ritual_command</span>
                </div>
                <div className="flex items-center gap-3 px-4 py-3 border-b border-40k-border">
                  <Search className="w-5 h-5 text-40k-gold" />
                  <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type a command or search..."
                    className="flex-1 bg-transparent text-white placeholder-stone-500 outline-none text-sm block-cursor"
                  />
                  <button type="button" onClick={close} className="text-stone-500 hover:text-40k-gold" aria-label="Close">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="max-h-64 overflow-y-auto py-2">
                  {filteredCommands.length === 0 ? (
                    <div className="px-4 py-6 text-center text-gray-500 text-sm">
                      No commands found
                    </div>
                  ) : (
                    filteredCommands.map((cmd, idx) => (
                      <button
                        type="button"
                        key={cmd.id}
                        onClick={() => { cmd.action(); close() }}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        className={clsx(
                          'w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                          idx === selectedIndex
                            ? 'bg-40k-crimson/15 text-40k-gold border-l-2 border-40k-crimson'
                            : 'text-gray-400 hover:bg-40k-card/50 hover:text-white border-l-2 border-transparent'
                        )}
                      >
                        {cmd.icon}
                        <span>{cmd.label}</span>
                        <span className="ml-auto text-xs text-gray-600 terminal-label normal-case">{cmd.category}</span>
                      </button>
                    ))
                  )}
                </div>

                <div className="px-4 py-2 border-t border-40k-border text-xs text-gray-600 flex items-center gap-4">
                  <span>↑↓ Navigate</span>
                  <span>↵ Select</span>
                  <span>ESC Close</span>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
