import { useMemo } from 'react'
import { useTheme } from '@/contexts/ThemeContext'
import { getThemeColors, getGraphNodeColors, type ThemeColorKey } from '@/lib/themeColors'

/** Re-read CSS vars whenever the active faction theme changes. */
export function useThemeColors(): Record<ThemeColorKey, string> {
  const { theme } = useTheme()
  return useMemo(() => getThemeColors(), [theme])
}

export function useGraphNodeColors() {
  const { theme } = useTheme()
  return useMemo(() => getGraphNodeColors(), [theme])
}
