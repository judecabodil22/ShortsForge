import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  Play,
  Network,
  FileText,
  BarChart3,
  Database,
  Activity,
  Zap,
  Wrench
} from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/pipeline', label: 'Pipeline', icon: Play },
  { path: '/graph', label: 'Knowledge Graph', icon: Network },
  { path: '/scripts', label: 'Scripts', icon: FileText },
  { path: '/metrics', label: 'Performance', icon: BarChart3 },
  { path: '/context', label: 'Context', icon: Database },
  { path: '/settings', label: 'Settings', icon: Wrench },
]

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Scanline overlay */}
      <div className="scanline-overlay" />
      
      {/* Sidebar */}
      <motion.aside 
        initial={false}
        animate={{ width: sidebarCollapsed ? 80 : 240 }}
        className="flex flex-col bg-cyber-dark border-r border-cyber-border"
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-cyber-border">
          <div className="w-10 h-10 rounded-lg bg-cyber-cyan/20 border border-cyber-cyan/30 flex items-center justify-center">
            <Zap className="w-6 h-6 text-cyber-cyan" />
          </div>
          {!sidebarCollapsed && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="font-display font-bold text-xl text-cyber-cyan"
            >
              SHORTS<span className="text-white">FORGE</span>
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
          className="p-4 border-t border-cyber-border text-gray-500 hover:text-cyber-cyan transition-colors"
        >
          {sidebarCollapsed ? '→' : '←'}
        </button>
      </motion.aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="flex items-center justify-between px-6 py-4 border-b border-cyber-border bg-cyber-dark/50">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyber-green animate-pulse" />
              <span className="text-sm text-gray-400">System Online</span>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-cyber-card border border-cyber-border">
              <span className="w-2 h-2 rounded-full bg-cyber-green animate-pulse" />
              <span className="text-xs text-gray-400">Auto-sync: Active</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-hidden relative bg-cyber-dark/30 grid-bg">
          {children}
        </div>

        {/* Footer */}
        <footer className="px-6 py-3 border-t border-cyber-border bg-cyber-dark/50 flex items-center justify-between text-xs text-gray-500">
          <span>ShortsForge v2.0.0 | Cyberpunk Edition</span>
          <span>Workspace: ~/ShortsForge</span>
        </footer>
      </main>
    </div>
  )
}