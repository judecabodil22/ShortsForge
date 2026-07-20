import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'

export type ThemeId = 'imperium' | 'mechanicus' | 'chaos' | 'ork' | 'eldar'

interface ThemeInfo {
  id: ThemeId
  name: string
  description: string
  icon: string
}

export const themes: ThemeInfo[] = [
  { id: 'imperium', name: 'Imperium', description: 'Gold & Crimson — Imperial Majesty', icon: '⬟' },
  { id: 'mechanicus', name: 'Mechanicus', description: 'Brass & Red — Adeptus Mechanicus', icon: '⚙' },
  { id: 'chaos', name: 'Chaos', description: 'Green & Purple — Warp Corruption', icon: 'ꕤ' },
  { id: 'ork', name: 'Ork', description: 'Yellow & Green — Waaagh! Energy', icon: '⚡' },
  { id: 'eldar', name: 'Eldar', description: 'Teal & Violet — Craftworld Elegance', icon: '✦' },
]

interface ThemeContextValue {
  theme: ThemeId
  setTheme: (id: ThemeId) => void
  currentTheme: ThemeInfo
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function getStoredTheme(): ThemeId {
  if (typeof window === 'undefined') return 'imperium'
  return (localStorage.getItem('cogitator-theme') as ThemeId) || 'imperium'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(getStoredTheme)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const setTheme = useCallback((id: ThemeId) => {
    setThemeState(id)
    localStorage.setItem('cogitator-theme', id)
  }, [])

  const currentTheme = themes.find(t => t.id === theme)!

  return (
    <ThemeContext.Provider value={{ theme, setTheme, currentTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
