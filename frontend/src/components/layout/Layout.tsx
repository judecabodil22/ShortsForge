import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  Network,
  FileText,
  BarChart3,
  Database,
  Activity,
  Zap,
  Wrench,
  FileEdit
} from 'lucide-react'
import clsx from 'clsx'
import { useTheme } from '@/contexts/ThemeContext'

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/graph', label: 'Knowledge Graph', icon: Network },
  { path: '/scripts', label: 'Scripts', icon: FileText },
  { path: '/metrics', label: 'Performance', icon: BarChart3 },
  { path: '/context', label: 'Context', icon: Database },
  { path: '/settings', label: 'Settings', icon: Wrench },
  { path: '/prompts', label: 'Prompts', icon: FileEdit },
]

const SIDEBAR_STORAGE_KEY = 'cogitator_sidebar_collapsed'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY)
    return stored ? JSON.parse(stored) : false
  })
  const { currentTheme } = useTheme()

  useEffect(() => {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, JSON.stringify(sidebarCollapsed))
  }, [sidebarCollapsed])

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Scanline overlay */}
      <div className="scanline-overlay" />
      
      {/* Sidebar */}
      <motion.aside 
        initial={false}
        animate={{ width: sidebarCollapsed ? 80 : 240 }}
        className="flex flex-col bg-40k-dark border-r border-40k-border"
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-40k-border">
          <div className="w-10 h-10 rounded-lg bg-40k-crimson/30 border border-40k-gold/40 flex items-center justify-center">
            <Zap className="w-6 h-6 text-40k-gold-bright" />
          </div>
          {!sidebarCollapsed && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="font-display font-bold text-xl"
            >
              <span className="text-40k-gold">COGIT</span>
              <span className="text-40k-crimson-bright">ATOR</span>
            </motion.div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                clsx(
                  isActive ? 'nav-item-active' : 'nav-item',
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
          ))}
        </nav>

        {/* Collapse Button */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="p-4 border-t border-40k-border text-gray-500 hover:text-40k-gold transition-colors"
        >
          {sidebarCollapsed ? '→' : '←'}
        </button>
      </motion.aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-40k-border bg-40k-dark/50">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-40k-gold-dim animate-pulse" />
              <span className="text-sm text-gray-400">System Online</span>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-40k-card border border-40k-border">
              <span className="w-2 h-2 rounded-full bg-40k-gold-dim animate-pulse" />
              <span className="text-xs text-gray-400">Auto-sync: Active</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-hidden relative bg-40k-dark/30 grid-bg">
          {children}
        </div>

        {/* Footer */}
        <footer className="px-6 py-3 border-t border-40k-border bg-40k-dark/50 flex items-center justify-between text-xs text-gray-500">
          <span>Cogitator v2.0.0 | {currentTheme.name} Edition</span>
          <span>Workspace: ~/Cogitator</span>
        </footer>
      </main>
    </div>
  )
}