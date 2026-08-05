/**
 * Theme-aware color helpers — never hardcode Imperium hex in components.
 * Reads live CSS custom properties from the active data-theme.
 */

export type ThemeColorKey =
  | 'gold'
  | 'goldBright'
  | 'goldDim'
  | 'crimson'
  | 'crimsonBright'
  | 'bronze'
  | 'border'
  | 'dark'
  | 'black'
  | 'card'
  | 'chart1'
  | 'chart2'
  | 'chart3'
  | 'chartGrid'

const VAR_MAP: Record<ThemeColorKey, string> = {
  gold: '--40k-gold',
  goldBright: '--40k-gold-bright',
  goldDim: '--40k-gold-dim',
  crimson: '--40k-crimson',
  crimsonBright: '--40k-crimson-bright',
  bronze: '--40k-bronze',
  border: '--40k-border',
  dark: '--40k-dark',
  black: '--40k-black',
  card: '--40k-card',
  chart1: '--chart-1',
  chart2: '--chart-2',
  chart3: '--chart-3',
  chartGrid: '--chart-grid',
}

const FALLBACK_HEX: Record<ThemeColorKey, string> = {
  gold: '#c9a227',
  goldBright: '#e8c547',
  goldDim: '#8b7312',
  crimson: '#7a1029',
  crimsonBright: '#b71c3a',
  bronze: '#8b6914',
  border: '#4a2828',
  dark: '#140808',
  black: '#0a0505',
  card: '#1c0e0e',
  chart1: '#c9a227',
  chart2: '#b71c3a',
  chart3: '#8b6914',
  chartGrid: '#4a2828',
}

function readVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

/** Normalize CSS color (rgb/rgba/hex) to #rrggbb for canvas alpha-append patterns. */
export function toHex(color: string, fallback = '#c9a227'): string {
  const c = color.trim()
  if (c.startsWith('#')) {
    if (c.length === 4) {
      return `#${c[1]}${c[1]}${c[2]}${c[2]}${c[3]}${c[3]}`.toLowerCase()
    }
    return c.slice(0, 7).toLowerCase()
  }
  const m = c.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i)
  if (m) {
    const [r, g, b] = [Number(m[1]), Number(m[2]), Number(m[3])]
    return `#${[r, g, b].map((n) => n.toString(16).padStart(2, '0')).join('')}`
  }
  return fallback
}

/** Append 0–1 alpha to a hex/rgb color as #rrggbbaa (canvas-friendly). */
export function withAlpha(color: string, alpha: number): string {
  const hex = toHex(color)
  const a = Math.max(0, Math.min(1, alpha))
  return `${hex}${Math.floor(a * 255)
    .toString(16)
    .padStart(2, '0')}`
}

export function toRgba(color: string, alpha: number): string {
  const hex = toHex(color)
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

/** Snapshot of theme colors as #rrggbb hex (safe for Recharts + canvas). */
export function getThemeColors(): Record<ThemeColorKey, string> {
  const out = {} as Record<ThemeColorKey, string>
  for (const key of Object.keys(VAR_MAP) as ThemeColorKey[]) {
    out[key] = toHex(readVar(VAR_MAP[key], FALLBACK_HEX[key]), FALLBACK_HEX[key])
  }
  return out
}

/** Graph node palette derived from the active faction theme. */
export function getGraphNodeColors() {
  const c = getThemeColors()
  return {
    character: c.gold,
    location: c.goldDim,
    term: c.goldBright,
    relationship: c.crimsonBright,
    game: c.crimson,
    background: c.black,
  }
}

/** Stable game→color map from the active chart palette (no hardcoded game hex). */
export function gameColor(game: string | undefined | null, colors: Record<ThemeColorKey, string>): string {
  const palette = [colors.chart1, colors.chart2, colors.chart3, colors.goldBright, colors.goldDim, colors.bronze, colors.crimsonBright]
  const key = (game || 'unknown').toLowerCase()
  let hash = 0
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) >>> 0
  return palette[hash % palette.length]
}

/** RGB channel string for SVG fills that need rgb(var(--x-rgb)). */
export function themeRgb(channel: 'gold' | 'gold-bright' | 'crimson' | 'border' | 'dark'): string {
  const map = {
    gold: '--40k-gold-rgb',
    'gold-bright': '--40k-gold-bright-rgb',
    crimson: '--40k-crimson-rgb',
    border: '--40k-border-rgb',
    dark: '--40k-dark-rgb',
  } as const
  const raw = readVar(map[channel], '201 162 39')
  return `rgb(${raw})`
}

export function themeRgbAlpha(
  channel: 'gold' | 'gold-bright' | 'crimson' | 'border',
  alpha: number
): string {
  const map = {
    gold: '--40k-gold-rgb',
    'gold-bright': '--40k-gold-bright-rgb',
    crimson: '--40k-crimson-rgb',
    border: '--40k-border-rgb',
  } as const
  const raw = readVar(map[channel], '201 162 39')
  return `rgb(${raw} / ${alpha})`
}
