export interface PipelineStatus {
  running: boolean
  current_phase: string | null
  progress: number
  message: string
  error: string | null
  last_run: string | null
}

export interface FullStatus {
  pipeline: PipelineStatus
  oauth_configured: boolean
  workspace: string
  game_title: string
  parent_franchise: string
}

export const PHASES = [
  'download',
  'transcribe',
  'context',
  'scripts',
  'clips',
  'tts',
] as const

export type Phase = (typeof PHASES)[number]

export const PHASE_LABELS: Record<Phase, string> = {
  download: 'Download',
  transcribe: 'Transcribe',
  context: 'Context',
  scripts: 'Scripts',
  clips: 'Clips',
  tts: 'TTS',
}

export function getPhaseIndex(current_phase: string | null): number {
  if (!current_phase) return -1
  const lower = current_phase.toLowerCase()
  const idx = PHASES.indexOf(lower as Phase)
  if (idx !== -1) return idx
  if (lower.includes('complete')) return PHASES.length
  return -1
}
