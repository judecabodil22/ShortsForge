export const API_BASE = import.meta.env.VITE_API_BASE || ''

const API_KEY_STORAGE_KEY = 'cogitator_api_key'

export function getStoredApiKey(): string | null {
  return localStorage.getItem(API_KEY_STORAGE_KEY)
}

function setStoredApiKey(key: string): void {
  localStorage.setItem(API_KEY_STORAGE_KEY, key)
}

export async function fetchApiKey(): Promise<string | null> {
  try {
    const response = await fetch(`${API_BASE}/api/auth/key`)
    if (response.ok) {
      const data = await response.json()
      if (data.api_key) {
        setStoredApiKey(data.api_key)
        return data.api_key
      }
    }
  } catch (e) {
    console.warn('Could not fetch API key:', e)
  }
  return getStoredApiKey()
}

interface FetchOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  skipAuth?: boolean
}

async function fetchAPI<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { method = 'GET', body, skipAuth = false } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (!skipAuth) {
    let apiKey = getStoredApiKey()
    if (!apiKey) {
      apiKey = await fetchApiKey()
    }
    if (apiKey) {
      headers['X-API-Key'] = apiKey
    }
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  // On 403 (Invalid API key), re-fetch the key and retry once
  if (response.status === 403 && !skipAuth) {
    const freshKey = await fetchApiKey()
    if (freshKey) {
      headers['X-API-Key'] = freshKey
      const retry = await fetch(`${API_BASE}${endpoint}`, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      })
      if (retry.ok) {
        return retry.json()
      }
    }
  }

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`API Error: ${response.status} - ${errorText}`)
  }

  return response.json()
}

export const getStatus = () => fetchAPI<{ pipeline: any; oauth_configured: boolean; workspace: string; game_title: string; parent_franchise: string }>('/api/status')

export const runPipeline = (source: string = 'youtube', videoUrl: string = '', phases?: number[]) =>
  fetchAPI<{ status: string }>('/api/pipeline/run', {
    method: 'POST',
    body: { source, video_url: videoUrl, ...(phases?.length ? { phases } : {}) },
  })
export const stopPipeline = () => fetchAPI<{ status: string }>('/api/pipeline/stop', { method: 'POST' })


export const getMetricsSummary = () => fetchAPI<any>('/api/metrics/summary')
export const getVideoMetrics = () => fetchAPI<any>('/api/metrics/videos')
export const getContentPerformance = () => fetchAPI<any>('/api/metrics/content-performance')
export const syncMetrics = () => fetchAPI<any>('/api/metrics/sync', { method: 'POST' })

export const getScripts = () => fetchAPI<any>('/api/scripts')
export const getScriptMetadata = (id: string) => fetchAPI<any>(`/api/scripts/${id}/metadata`)
export const analyzeScript = (id: string) => fetchAPI<any>(`/api/scripts/${id}/analyze`, { method: 'POST' })
export const reviewScript = (id: string, status: 'approved' | 'quarantined' | 'pending') =>
  fetchAPI<any>(`/api/scripts/${id}/review`, { method: 'POST', body: { status } })

export const getMemPalaceStatus = () => fetchAPI<any>('/api/mempalace/status')
export const clearMemPalace = (game: string) =>
  fetchAPI<any>('/api/mempalace/clear', { method: 'POST', body: { game } })
export const getPublishChecklist = (video: string) =>
  fetchAPI<any>(`/api/publish/checklist?video=${encodeURIComponent(video)}`)
export const autoImportTikTok = () =>
  fetchAPI<any>('/api/metrics/tiktok/auto-import', { method: 'POST' })
export const searchGraph = (game: string, q: string) =>
  fetchAPI<any>(`/api/context/${encodeURIComponent(game)}/graph/search?q=${encodeURIComponent(q)}`)
export const getGraphStats = (game: string) =>
  fetchAPI<any>(`/api/context/${encodeURIComponent(game)}/graph/stats`)
export const createABTest = (data: any) =>
  fetchAPI<any>('/api/learning/ab-test', { method: 'POST', body: data })

export const getLearningWeights = () => fetchAPI<any>('/api/learnings/weights')
export const getLearningDashboard = () => fetchAPI<any>('/api/learning/dashboard')
export const getActiveABTests = () => fetchAPI<any>('/api/learning/ab-tests')
export const getTikTokLearningSignals = () => fetchAPI<any>('/api/learning/tiktok-signals')
export const getCurrentABTest = () => fetchAPI<any>('/api/learning/ab-current')

export const getGames = () => fetchAPI<any>('/api/context/games')
export const getGameContext = (game: string) => fetchAPI<any>(`/api/context/${game}`)
export const getGraphData = (game: string) => fetchAPI<any>(`/api/context/${game}/graph`)
export const getAllGamesGraph = () => fetchAPI<any>('/api/context/all/graph')
export const updateContextItem = (game: string, itemType: string, itemId: string, data: any) =>
  fetchAPI<any>(`/api/context/${game}/${itemType}/${itemId}`, { method: 'PUT', body: data })
export const deleteContextItem = (game: string, itemType: string, itemId: string) =>
  fetchAPI<any>(`/api/context/${game}/${itemType}/${itemId}`, { method: 'DELETE' })

export const getConfig = () => fetchAPI<any>('/api/config')
export const updateConfig = (data: any) => fetchAPI<any>('/api/config', { method: 'POST', body: data })
export const cleanupFiles = () => fetchAPI<any>('/api/system/cleanup', { method: 'POST' })
export const downloadFromUrl = (url: string) => fetchAPI<any>('/api/pipeline/download', { method: 'POST', body: { url } })
export const getLogs = (lines: number = 100) => fetchAPI<any>(`/api/logs?lines=${lines}`)
export const createGameContext = (game: string) => fetchAPI<any>('/api/context/create_game', { method: 'POST', body: { game } })
export const clearContext = (game: string) => fetchAPI<any>('/api/context/clear', { method: 'POST', body: { game } })
export const getSegmentRefs = (game: string) => fetchAPI<any>(`/api/context/${encodeURIComponent(game)}/segments`)
export const getScriptPrompt = () => fetchAPI<{ content: string }>('/api/prompts/script')
export const saveScriptPrompt = (content: string) =>
  fetchAPI<{ status: string }>('/api/prompts/script', { method: 'PUT', body: { content } })

// ─── TikTok Analytics ────────────────────────────────────────────────────────
export const getTikTokSummary = () => fetchAPI<any>('/api/metrics/tiktok/summary')
export const getTikTokVideos = () => fetchAPI<any>('/api/metrics/tiktok/videos')
export const getTikTokDaily = (days: number = 30) => fetchAPI<any>(`/api/metrics/tiktok/daily?days=${days}`)
export const getTikTokGames = () => fetchAPI<any>('/api/metrics/tiktok/games')
export const getCrossPlatformStats = () => fetchAPI<any>('/api/metrics/cross-platform')
export const importTikTokCSV = async (files: File[]): Promise<any> => {
  const formData = new FormData()
  for (const file of files) {
    formData.append('files', file)
  }

  const headers: Record<string, string> = {}
  let apiKey = getStoredApiKey()
  if (!apiKey) {
    apiKey = await fetchApiKey()
  }
  if (apiKey) {
    headers['X-API-Key'] = apiKey
  }

  const response = await fetch(`${API_BASE}/api/metrics/tiktok/import`, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`API Error: ${response.status} - ${errorText}`)
  }

  return response.json()
}
export const matchTikTokToLocal = () => fetchAPI<any>('/api/metrics/tiktok/match', { method: 'POST' })

// ─── TTS ─────────────────────────────────────────────────────────────────────
export const getTtsVoices = () => fetchAPI<any>('/api/tts/voices')