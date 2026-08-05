import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { motion, useReducedMotion } from 'framer-motion'
import {
  LayoutDashboard,
  Network,
  FileText,
  BarChart3,
  Database,
  Activity,
  Zap,
  Wrench,
  FileEdit,
  Brain,
  Castle,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react'
import clsx from 'clsx'
import { useTheme } from '@/contexts/ThemeContext'
import { springGentle } from '@/lib/animations'
import { APP_VERSION } from '@/lib/utils'
import CommandPalette from '@/components/ui/CommandPalette'
import { getStatus } from '@/lib/api'

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/graph', label: 'Knowledge Graph', icon: Network },
  { path: '/scripts', label: 'Scripts', icon: FileText },
  { path: '/learning', label: 'Learning', icon: Brain },
  { path: '/metrics', label: 'Performance', icon: BarChart3 },
  { path: '/context', label: 'Context', icon: Database },
  { path: '/mempalace', label: 'MemPalace', icon: Castle },
  { path: '/settings', label: 'Settings', icon: Wrench },
  { path: '/prompts', label: 'Prompts', icon: FileEdit },
]

const SIDEBAR_STORAGE_KEY = 'cogitator_sidebar_collapsed'
const DENSITY_STORAGE_KEY = 'cogitator_density'

type Density = 'default' | 'compact'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY)
    return stored ? JSON.parse(stored) : false
  })
  const [density, setDensity] = useState<Density>(() => {
    return (localStorage.getItem(DENSITY_STORAGE_KEY) as Density) || 'default'
  })
  const [scanlinePos, setScanlinePos] = useState(0)
  const [apiOnline, setApiOnline] = useState(false)
  const { currentTheme, atmosphere } = useTheme()
  const reduced = useReducedMotion()

  useEffect(() => {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, JSON.stringify(sidebarCollapsed))
  }, [sidebarCollapsed])

  useEffect(() => {
    localStorage.setItem(DENSITY_STORAGE_KEY, density)
    document.documentElement.setAttribute('data-density', density)
  }, [density])

  useEffect(() => {
    if (!atmosphere || reduced) return
    const interval = setInterval(() => {
      setScanlinePos((prev) => (prev + 1) % 100)
    }, 80)
    return () => clearInterval(interval)
  }, [atmosphere, reduced])

  useEffect(() => {
    let cancelled = false
    const ping = async () => {
      try {
        await getStatus()
        if (!cancelled) setApiOnline(true)
      } catch {
        if (!cancelled) setApiOnline(false)
      }
    }
    ping()
    const interval = setInterval(ping, 15000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  return (
    <div className="flex h-screen overflow-hidden">
      {atmosphere && (
        <motion.div
          className="scanline-overlay"
          animate={reduced ? undefined : { opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
        >
          {!reduced && (
            <div
              className="absolute left-0 right-0 h-px bg-40k-gold-dim/20"
              style={{ top: `${scanlinePos}%` }}
            />
          )}
        </motion.div>
      )}

      {atmosphere && (
        <div className="fixed inset-0 pointer-events-none overflow-hidden z-0 data-stream-bg" />
      )}

      <motion.aside
        initial={false}
        animate={{ width: sidebarCollapsed ? 80 : 240 }}
        transition={springGentle}
        className="flex flex-col bg-40k-dark/95 border-r border-40k-border relative z-10 backdrop-blur-sm"
      >
        <motion.div
          className="flex items-center gap-3 px-4 py-5 border-b border-40k-border"
          whileHover={{ backgroundColor: 'rgb(var(--40k-gold-rgb) / 0.05)' }}
        >
          <motion.div
            className="w-10 h-10 rounded-lg bg-40k-crimson/30 border border-40k-gold/40 flex items-center justify-center"
            animate={reduced || !atmosphere ? undefined : { rotate: [0, 5, -5, 0] }}
            transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
          >
            <Zap className="w-6 h-6 text-40k-gold-bright" />
          </motion.div>
          {!sidebarCollapsed && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="font-display font-bold text-xl"
            >
              <span className="text-40k-gold">COGIT</span>
              <span className="text-40k-crimson-bright">ATOR</span>
            </motion.div>
          )}
        </motion.div>

        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          {navItems.map((item, idx) => (
            <motion.div
              key={item.path}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.04, ...springGentle }}
            >
              <NavLink
                to={item.path}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 glitch-text',
                    isActive && !sidebarCollapsed
                      ? 'bg-40k-gold/10 text-40k-gold border-l-2 border-40k-crimson'
                      : isActive && sidebarCollapsed
                        ? 'bg-40k-gold/10 text-40k-gold'
                        : 'text-stone-400 hover:text-40k-gold hover:bg-40k-card/50',
                    sidebarCollapsed && 'justify-center px-2'
                  )
                }
              >
                <item.icon className="w-5 h-5 flex-shrink-0" />
                {!sidebarCollapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-sm font-medium"
                  >
                    {item.label}
                  </motion.span>
                )}
              </NavLink>
            </motion.div>
          ))}
        </nav>

        <div className="border-t border-40k-border">
          {!sidebarCollapsed && (
            <div className="px-3 py-2 border-b border-40k-border/50">
              <div className="flex items-center gap-1 bg-40k-black/50 rounded-lg p-0.5">
                {(['compact', 'default'] as const).map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setDensity(d)}
                    className={`flex-1 text-xs py-1.5 rounded-md transition-all duration-200 ${
                      density === d
                        ? 'bg-40k-gold/20 text-40k-gold'
                        : 'text-stone-500 hover:text-stone-300'
                    }`}
                  >
                    {d === 'compact' ? 'Compact' : 'Default'}
                  </button>
                ))}
              </div>
            </div>
          )}
          <motion.button
            type="button"
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="w-full p-4 text-gray-500 hover:text-40k-gold transition-colors flex items-center justify-center"
            whileHover={{ backgroundColor: 'rgb(var(--40k-gold-rgb) / 0.08)' }}
          >
            {sidebarCollapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
          </motion.button>
        </div>
      </motion.aside>

      <main className="flex-1 flex flex-col overflow-hidden relative z-10">
        <header className="flex items-center justify-between px-6 py-4 border-b border-40k-border bg-40k-dark/50 backdrop-blur-sm">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className={apiOnline ? 'pulse-glow' : ''}>
                <Activity className={`w-4 h-4 ${apiOnline ? 'text-40k-gold-dim' : 'text-stone-600'}`} />
              </div>
              <span className="text-sm text-gray-400">
                {apiOnline ? 'System Online' : 'API Offline'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <CommandPalette />
          </div>
        </header>

        <div className="flex-1 flex flex-col overflow-hidden relative bg-40k-dark/30 grid-bg">
          {children}
        </div>

        <motion.footer
          className="px-6 py-3 border-t border-40k-border bg-40k-dark/50 backdrop-blur-sm flex items-center justify-between text-xs text-gray-500"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
        >
          <span>Cogitator v{APP_VERSION} | {currentTheme.name} Edition</span>
          <span className="terminal-label normal-case opacity-60">{currentTheme.description}</span>
        </motion.footer>
      </main>
    </div>
  )
}
