import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'

export type ThemeId = 'imperium' | 'mechanicus' | 'chaos' | 'ork' | 'eldar'

export interface ThemeInfo {
  id: ThemeId
  name: string
  description: string
  icon: string
  swatches: [string, string, string]
}

export const themes: ThemeInfo[] = [
  { id: 'imperium', name: 'Imperium', description: 'Sacred metal, gothic grid', icon: '⬟', swatches: ['#c9a227', '#7a1029', '#140808'] },
  { id: 'mechanicus', name: 'Mechanicus', description: 'Cog-ritual, oily brass glow', icon: '⚙', swatches: ['#cd7f32', '#dc2626', '#120a0a'] },
  { id: 'chaos', name: 'Chaos', description: 'Unstable warp glow', icon: 'ꕤ', swatches: ['#84cc16', '#9333ea', '#0d0015'] },
  { id: 'ork', name: 'Ork', description: 'Rough scrap contrast', icon: '⚡', swatches: ['#eab308', '#84cc16', '#101408'] },
  { id: 'eldar', name: 'Eldar', description: 'Cool spiritstone elegance', icon: '✦', swatches: ['#a78bfa', '#14b8a6', '#081515'] },
]

interface ThemeContextValue {
  theme: ThemeId
  setTheme: (id: ThemeId) => void
  currentTheme: ThemeInfo
  atmosphere: boolean
  setAtmosphere: (on: boolean) => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

function getStoredTheme(): ThemeId {
  if (typeof window === 'undefined') return 'imperium'
  return (localStorage.getItem('cogitator-theme') as ThemeId) || 'imperium'
}

function getStoredAtmosphere(): boolean {
  if (typeof window === 'undefined') return true
  const v = localStorage.getItem('cogitator-atmosphere')
  return v === null ? true : v === 'on'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeId>(getStoredTheme)
  const [atmosphere, setAtmosphereState] = useState(getStoredAtmosphere)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  useEffect(() => {
    document.documentElement.setAttribute('data-atmosphere', atmosphere ? 'on' : 'off')
  }, [atmosphere])

  const setTheme = useCallback((id: ThemeId) => {
    setThemeState(id)
    localStorage.setItem('cogitator-theme', id)
  }, [])

  const setAtmosphere = useCallback((on: boolean) => {
    setAtmosphereState(on)
    localStorage.setItem('cogitator-atmosphere', on ? 'on' : 'off')
  }, [])

  const currentTheme = themes.find(t => t.id === theme)!

  return (
    <ThemeContext.Provider value={{ theme, setTheme, currentTheme, atmosphere, setAtmosphere }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
