export type VisualTheme = 'starchart' | 'brain' | 'circuit' | 'hologram' | 'code' | 'world'

export interface GraphSettings {
  linkDistance: number
  linkStrength: number
  chargeStrength: number
  collisionRadius: number
  centerStrength: number
  velocityDecay: number
  visualTheme: VisualTheme
}

export const DEFAULT_GRAPH_SETTINGS: GraphSettings = {
  linkDistance: 250,
  linkStrength: 1,
  chargeStrength: -500,
  collisionRadius: 60,
  centerStrength: 0.5,
  velocityDecay: 0.6,
  visualTheme: 'starchart',
}

export const THEME_PHYSICS: Record<VisualTheme, Partial<GraphSettings>> = {
  starchart: { linkDistance: 250, chargeStrength: -500, velocityDecay: 0.6 },
  brain: { linkDistance: 150, chargeStrength: -800, velocityDecay: 0.3 },
  circuit: { linkDistance: 200, chargeStrength: -400, velocityDecay: 0.7 },
  hologram: { linkDistance: 180, chargeStrength: -600, velocityDecay: 0.5 },
  code: { linkDistance: 120, chargeStrength: -1000, velocityDecay: 0.4 },
  world: { linkDistance: 300, chargeStrength: -350, velocityDecay: 0.8 },
}

const STORAGE_KEY = 'shortsforge_graph_settings'

export function loadGraphSettings(): GraphSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_GRAPH_SETTINGS }
    const parsed = JSON.parse(raw) as Partial<GraphSettings>
    return { ...DEFAULT_GRAPH_SETTINGS, ...parsed }
  } catch {
    return { ...DEFAULT_GRAPH_SETTINGS }
  }
}

export function saveGraphSettings(settings: GraphSettings): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    /* ignore quota errors */
  }
}

export const THEME_OPTIONS: { value: VisualTheme; label: string; icon: string }[] = [
  { value: 'starchart', label: 'Star Chart', icon: '⭐' },
  { value: 'brain', label: 'Brain Neurons', icon: '🧠' },
  { value: 'circuit', label: 'Digital Circuits', icon: '⚡' },
  { value: 'hologram', label: 'Hologram', icon: '🔮' },
  { value: 'code', label: 'Code Matrix', icon: '💻' },
  { value: 'world', label: 'World Map', icon: '🌍' },
]
