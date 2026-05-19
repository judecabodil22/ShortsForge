const API_BASE = import.meta.env.VITE_API_BASE || ''

const API_KEY_STORAGE_KEY = 'shortsforge_api_key'

export function getStoredApiKey(): string | null {
  return localStorage.getItem(API_KEY_STORAGE_KEY)
}

export function setStoredApiKey(key: string): void {
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
  
  // Add API key for non-public endpoints
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
    body: body ? JSON.stringify(body) : undefined,
  })
  
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`API Error: ${response.status} - ${errorText}`)
  }
  
  return response.json()
}

// Status API
export const getStatus = () => fetchAPI<{ pipeline: any; oauth_configured: boolean; workspace: string; game_title: string; parent_franchise: string }>('/api/status')
export const getHealth = () => fetchAPI<{ status: string }>('/api/health')

// Pipeline API
export const runPipeline = (source: string = 'youtube') => fetchAPI<{ status: string }>(`/api/pipeline/run?source=${source}`, { method: 'POST' })
export const stopPipeline = () => fetchAPI<{ status: string }>('/api/pipeline/stop', { method: 'POST' })
export const getPipelineSettings = () => fetchAPI<any>('/api/pipeline/settings')
export const savePipelineSettings = (settings: any) => fetchAPI<{ status: string }>('/api/pipeline/settings', { method: 'POST', body: settings })

// Metrics API
export const getMetricsSummary = () => fetchAPI<any>('/api/metrics/summary')
export const getVideoMetrics = () => fetchAPI<any>('/api/metrics/videos')
export const getContentPerformance = () => fetchAPI<any>('/api/metrics/content-performance')
export const syncMetrics = () => fetchAPI<any>('/api/metrics/sync', { method: 'POST' })

// Scripts API
export const getScripts = () => fetchAPI<any>('/api/scripts')
export const getScript = (id: string) => fetchAPI<any>(`/api/scripts/${id}`)
export const analyzeScript = (id: string) => fetchAPI<any>(`/api/scripts/${id}/analyze`, { method: 'POST' })

// Learnings API
export const getLearnings = () => fetchAPI<any>('/api/learnings')
export const getLearningWeights = () => fetchAPI<any>('/api/learnings/weights')

// Context API
export const getGames = () => fetchAPI<any>('/api/context/games')
export const getGameContext = (game: string) => fetchAPI<any>(`/api/context/${game}`)
export const getGraphData = (game: string) => fetchAPI<any>(`/api/context/${game}/graph`)
export const updateContextItem = (game: string, itemType: string, itemId: string, data: any) => 
  fetchAPI<any>(`/api/context/${game}/${itemType}/${itemId}`, { method: 'PUT', body: data })
export const deleteContextItem = (game: string, itemType: string, itemId: string) => 
  fetchAPI<any>(`/api/context/${game}/${itemType}/${itemId}`, { method: 'DELETE' })
export const deleteGame = (game: string) => 
  fetchAPI<any>(`/api/context/${game}`, { method: 'DELETE' })

// TTS API
export const getTTSVoices = () => fetchAPI<any>('/api/tts/voices')
export const getTTSLearnings = () => fetchAPI<any>('/api/tts/learnings')

// Desktop UI Replacements (System/Config)
export const getConfig = () => fetchAPI<any>('/api/config')
export const updateConfig = (data: any) => fetchAPI<any>('/api/config', { method: 'POST', body: data })
export const cleanupFiles = () => fetchAPI<any>('/api/system/cleanup', { method: 'POST' })
export const restartListener = () => fetchAPI<any>('/api/system/restart-listener', { method: 'POST' })
export const downloadFromUrl = (url: string) => fetchAPI<any>('/api/pipeline/download', { method: 'POST', body: { url } })
export const getLogs = (lines: number = 100) => fetchAPI<any>(`/api/logs?lines=${lines}`)
export const importContext = (game: string) => fetchAPI<any>('/api/context/import', { method: 'POST', body: { game } })
export const createGameContext = (game: string) => fetchAPI<any>('/api/context/create_game', { method: 'POST', body: { game } })
export const mergeContext = (target_game: string, source_game: string) => fetchAPI<any>('/api/context/merge', { method: 'POST', body: { target_game, source_game } })
export const clearContext = (game: string) => fetchAPI<any>('/api/context/clear', { method: 'POST', body: { game } })
export const getSegmentRefs = (game: string) => fetchAPI<any>(`/api/context/${encodeURIComponent(game)}/segments`)

// WebSocket connection
let wsInstance: WebSocket | null = null
let reconnectAttempts = 0
const MAX_RECONNECT_ATTEMPTS = 5

export function createWebSocketConnection(onMessage: (data: any) => void, onError?: (error: Event) => void) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)
  wsInstance = ws

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onMessage(data)
    } catch (e) {
      console.error('WebSocket JSON parse error:', e)
    }
  }

  ws.onclose = () => {
    console.log('WebSocket disconnected')
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      reconnectAttempts++
      console.log(`WebSocket reconnection attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}`)
      // Close old connection before reconnecting
      if (wsInstance && wsInstance.readyState === WebSocket.OPEN) {
        wsInstance.close()
      }
      setTimeout(() => {
        const newWs = createWebSocketConnection(onMessage, onError)
        if (newWs) {
          wsInstance = newWs
        }
      }, 2000 * reconnectAttempts)
    }
  }

  ws.onerror = (error) => {
    console.error('WebSocket error:', error)
    if (onError) onError(error)
  }

  return ws
}

export function closeWebSocket() {
  if (wsInstance) {
    wsInstance.close()
    wsInstance = null
  }
}