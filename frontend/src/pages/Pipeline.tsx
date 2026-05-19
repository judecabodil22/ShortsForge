import { useState, useEffect, useRef } from 'react'
import { Play, Square, Settings, GripVertical, Video, FolderOpen, X, Save, Download, Activity, CheckCircle, Clock, AlertCircle, Loader2, ChevronDown, ChevronUp, Terminal } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Reorder, motion, AnimatePresence } from 'framer-motion'
import { useMutation, useQuery } from '@tanstack/react-query'
import { runPipeline, stopPipeline, downloadFromUrl, getLogs, getPipelineSettings, savePipelineSettings, getStatus } from '@/lib/api'

interface Phase {
  id: string
  name: string
  description: string
  enabled: boolean
  videoSource?: 'youtube' | 'local'
}

interface PipelineStatus {
  running: boolean
  current_phase: string
  progress: number
  message: string
  error: string | null
}

const PHASE_MAP: Record<string, number> = {
  'download': 1,
  'transcribe': 2,
  'scripts': 3,
  'clip': 4,
  'tts': 5,
  'upload': 6,
}

const PHASE_ORDER = ['download', 'transcribe', 'scripts', 'clip', 'tts', 'upload']

const initialPhases: Phase[] = [
  { id: 'p1', name: 'Download', description: 'Download or import videos', enabled: true, videoSource: 'youtube' },
  { id: 'p2', name: 'Transcribe', description: 'Convert audio to text with timestamps', enabled: true },
  { id: 'p3', name: 'Scripts', description: 'Generate AI-powered narration scripts', enabled: true },
  { id: 'p4', name: 'Clip', description: 'Extract video clips based on scene detection', enabled: true },
  { id: 'p5', name: 'TTS', description: 'Create AI voice narration with subtitles', enabled: true },
]

export default function Pipeline() {
  const [phases, setPhases] = useState<Phase[]>(initialPhases)
  const [selectedPhase, setSelectedPhase] = useState<Phase | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [localVideos, setLocalVideos] = useState<{name: string; path: string}[]>([])
  const [settingsLoaded, setSettingsLoaded] = useState(false)
  const [downloadUrl, setDownloadUrl] = useState('')
  const [expandedLogs, setExpandedLogs] = useState(false)
  const [liveLogs, setLiveLogs] = useState<string[]>([])
  const logsEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Pipeline status from API
  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: getStatus,
    refetchInterval: 2000,
  })

  // Load settings on mount
  const { data: settings } = useQuery({
    queryKey: ['pipeline-settings'],
    queryFn: getPipelineSettings,
  })

  useEffect(() => {
    if (settings?.phases && !settingsLoaded) {
      setPhases(settings.phases.map((p: any) => ({
        id: p.id,
        name: p.name,
        description: p.description || `${p.name} phase`,
        enabled: p.enabled,
        videoSource: p.video_source || 'youtube',
      })))
      setSettingsLoaded(true)
    }
  }, [settings, settingsLoaded])

  const saveSettings = (newPhases: Phase[]) => {
    setPhases(newPhases)
    savePipelineSettings({
      phases: newPhases.map(p => ({
        id: p.id,
        name: p.name,
        enabled: p.enabled,
        video_source: p.videoSource || 'youtube',
      }))
    })
  }

  // WebSocket for real-time logs
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'log' || data.log) {
          const logLine = data.log || data.message || data.text
          if (logLine && typeof logLine === 'string') {
            setLiveLogs(prev => {
              const newLogs = [...prev, logLine]
              return newLogs.slice(-500) // Keep last 500 lines
            })
          }
        }
        if (data.type === 'progress' || data.progress !== undefined) {
          // Refresh status on progress updates
        }
      } catch (e) {
        // Ignore parse errors
      }
    }

    ws.onerror = () => {
      console.log('WebSocket connection lost, falling back to polling')
    }

    return () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close()
      }
    }
  }, [])

  // Poll logs when running
  const { data: logsData } = useQuery({
    queryKey: ['logs'],
    queryFn: () => getLogs(100),
    refetchInterval: status?.pipeline?.running ? 1500 : false,
    enabled: status?.pipeline?.running || expandedLogs
  })

  // Sync polled logs into live logs
  useEffect(() => {
    if (logsData?.logs?.length) {
      setLiveLogs(prev => {
        const newLogs = [...prev, ...logsData.logs.slice(-50)]
        return newLogs.slice(-500)
      })
    }
  }, [logsData])

  useEffect(() => {
    if (expandedLogs && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [liveLogs, expandedLogs])

  const downloadMutation = useMutation({
    mutationFn: (url: string) => downloadFromUrl(url),
    onSuccess: () => alert('Download started!'),
    onError: (error: Error) => alert(`Download failed: ${error.message}`)
  })

  const runMutation = useMutation({
    mutationFn: () => {
      const source = phases.find(p => p.id === 'p1')?.videoSource || 'youtube'
      setLiveLogs([])
      return runPipeline(source)
    },
    onError: (error: Error) => alert(`Failed to run pipeline: ${error.message}`)
  })

  const stopMutation = useMutation({
    mutationFn: stopPipeline,
    onError: (error: Error) => alert(`Failed to stop pipeline: ${error.message}`)
  })

  const togglePhase = (id: string) => {
    const newPhases = phases.map(p => 
      p.id === id ? { ...p, enabled: !p.enabled } : p
    )
    saveSettings(newPhases)
  }

  const toggleVideoSource = (source: 'youtube' | 'local') => {
    const newPhases = phases.map(p => 
      p.id === 'p1' ? { ...p, videoSource: source } : p
    )
    saveSettings(newPhases)
  }

  const openSettings = (phase: Phase) => {
    if (phase.id === 'p1') {
      setLocalVideos([
        { name: 'gameplay_recording.mp4', path: '/home/alph4r1us/ShortsForge/media/gameplay_recording.mp4' },
        { name: 'cutscene_01.mp4', path: '/home/alph4r1us/ShortsForge/media/cutscene_01.mp4' },
      ])
    }
    setSelectedPhase(phase)
    setShowSettings(true)
  }

  const pipelineStatus: PipelineStatus = status?.pipeline || {
    running: false,
    current_phase: '',
    progress: 0,
    message: '',
    error: null
  }

  const currentPhaseIndex = PHASE_MAP[pipelineStatus.current_phase?.toLowerCase()] || 0

  const getPhaseStatus = (phaseName: string): 'pending' | 'running' | 'complete' | 'error' => {
    const phaseNum = PHASE_MAP[phaseName.toLowerCase()]
    if (!pipelineStatus.running) return 'pending'
    if (phaseNum < currentPhaseIndex) return 'complete'
    if (phaseNum === currentPhaseIndex) return 'running'
    return 'pending'
  }

  const getLogColor = (log: string): string => {
    if (log.includes('ERROR') || log.includes('error:')) return 'text-cyber-red'
    if (log.includes('WARNING') || log.includes('warn')) return 'text-cyber-orange'
    if (log.includes('SUCCESS') || log.includes('complete') || log.includes('Done')) return 'text-cyber-green'
    if (log.includes('Starting') || log.includes('Processing')) return 'text-cyber-cyan'
    return 'text-gray-300'
  }

  return (
    <motion.div 
      initial="hidden"
      animate="show"
      variants={{
        hidden: { opacity: 0 },
        show: {
          opacity: 1,
          transition: { staggerChildren: 0.1 }
        }
      }}
      className="space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-cyber-cyan">PIPELINE</span> CONTROL
          </h1>
          <p className="text-gray-400 mt-1">
            {pipelineStatus.running ? `Running: ${pipelineStatus.current_phase}` : 'Configure and run the pipeline'}
          </p>
        </div>

        <div className="flex gap-3">
          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={`cyber-button-primary flex items-center gap-2 ${pipelineStatus.running ? 'opacity-50' : ''}`}
            onClick={() => runMutation.mutate()}
            disabled={runMutation.isPending || pipelineStatus.running}
          >
            {runMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {runMutation.isPending ? 'Starting...' : 'Run Pipeline'}
          </motion.button>
          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className={`cyber-button flex items-center gap-2 ${!pipelineStatus.running ? 'opacity-50' : ''}`}
            onClick={() => stopMutation.mutate()}
            disabled={!pipelineStatus.running || stopMutation.isPending}
          >
            {stopMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Square className="w-4 h-4" />
            )}
            Stop
          </motion.button>
        </div>
      </div>

      {/* Pipeline Status Card */}
      <Card className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-cyber-cyan/5 to-cyber-magenta/5" />
        <div className="relative">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-display font-semibold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-cyber-cyan" />
              Pipeline Status
              {pipelineStatus.running && (
                <motion.span
                  animate={{ opacity: [1, 0.5, 1] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                  className="w-2 h-2 rounded-full bg-cyber-green"
                />
              )}
            </h3>
            <div className={`px-3 py-1 rounded-full text-sm font-medium ${
              pipelineStatus.running 
                ? 'bg-cyber-green/20 text-cyber-green' 
                : pipelineStatus.error
                  ? 'bg-cyber-red/20 text-cyber-red'
                  : 'bg-gray-500/20 text-gray-400'
            }`}>
              {pipelineStatus.error ? 'Error' : pipelineStatus.running ? 'Running' : 'Idle'}
            </div>
          </div>

          {/* Phase Timeline */}
          <div className="relative">
            <div className="flex items-center justify-between mb-4">
              {PHASE_ORDER.slice(0, 5).map((phase, idx) => {
                const phaseStatus = getPhaseStatus(phase)
                const phaseName = phase.charAt(0).toUpperCase() + phase.slice(1)
                return (
                  <div key={phase} className="flex flex-col items-center flex-1">
                    <motion.div
                      className={`w-10 h-10 rounded-full flex items-center justify-center border-2 ${
                        phaseStatus === 'complete' ? 'bg-cyber-green border-cyber-green' :
                        phaseStatus === 'running' ? 'bg-cyber-cyan border-cyber-cyan animate-pulse' :
                        phaseStatus === 'error' ? 'bg-cyber-red border-cyber-red' :
                        'bg-cyber-dark border-cyber-border'
                      }`}
                      animate={phaseStatus === 'running' ? { scale: [1, 1.1, 1] } : {}}
                      transition={{ duration: 1, repeat: Infinity }}
                    >
                      {phaseStatus === 'complete' ? (
                        <CheckCircle className="w-5 h-5 text-black" />
                      ) : phaseStatus === 'running' ? (
                        <Loader2 className="w-5 h-5 text-black animate-spin" />
                      ) : phaseStatus === 'error' ? (
                        <AlertCircle className="w-5 h-5 text-black" />
                      ) : (
                        <span className="text-sm font-bold text-gray-500">{idx + 1}</span>
                      )}
                    </motion.div>
                    <span className={`text-xs mt-2 text-center ${phaseStatus === 'running' ? 'text-cyber-cyan' : 'text-gray-500'}`}>
                      {phaseName}
                    </span>
                  </div>
                )
              })}
            </div>

            {/* Progress Bar */}
            <div className="h-2 bg-cyber-dark rounded-full overflow-hidden">
              <motion.div 
                className="h-full bg-gradient-to-r from-cyber-cyan to-cyber-magenta"
                animate={{ width: pipelineStatus.running ? `${pipelineStatus.progress}%` : '0%' }}
                transition={{ type: 'spring', stiffness: 50, damping: 20 }}
              />
            </div>

            {/* Status Message */}
            <div className="flex justify-between mt-2 text-xs text-gray-500">
              <span>{pipelineStatus.progress}%</span>
              <span className="text-cyber-cyan">{pipelineStatus.message || (pipelineStatus.running ? 'Processing...' : 'Ready')}</span>
            </div>
          </div>

          {/* Error Display */}
          {pipelineStatus.error && (
            <motion.div 
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-4 p-3 bg-cyber-red/10 border border-cyber-red/30 rounded-lg"
            >
              <div className="flex items-center gap-2 text-cyber-red text-sm font-medium mb-1">
                <AlertCircle className="w-4 h-4" />
                Error
              </div>
              <p className="text-xs text-gray-300 font-mono">{pipelineStatus.error}</p>
            </motion.div>
          )}
        </div>
      </Card>

      {/* Live Logs Panel */}
      <Card className="p-0 overflow-hidden">
        <div 
          className="flex items-center justify-between p-4 cursor-pointer hover:bg-cyber-dark/50 transition-colors"
          onClick={() => setExpandedLogs(!expandedLogs)}
        >
          <div className="flex items-center gap-2">
            <Terminal className="w-5 h-5 text-cyber-cyan" />
            <h3 className="text-lg font-display font-semibold text-white">Live Logs</h3>
            {pipelineStatus.running && (
              <motion.div
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ duration: 0.8, repeat: Infinity }}
                className="w-2 h-2 rounded-full bg-cyber-green"
              />
            )}
            <span className="text-xs text-gray-500">({liveLogs.length} lines)</span>
          </div>
          <button className="text-gray-400 hover:text-white">
            {expandedLogs ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
        </div>
        
        <AnimatePresence>
          {expandedLogs && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 300, opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="h-[300px] bg-cyber-dark border-t border-cyber-border p-4 overflow-y-auto font-mono text-xs space-y-1">
                {liveLogs.length > 0 ? (
                  liveLogs.map((log, i) => (
                    <motion.div 
                      key={i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i > liveLogs.length - 10 ? 0.05 : 0 }}
                      className={getLogColor(log)}
                    >
                      <span className="text-gray-600 mr-2">{(i + 1).toString().padStart(4, ' ')}</span>
                      {log}
                    </motion.div>
                  ))
                ) : (
                  <div className="text-gray-500 italic flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    Waiting for logs...
                  </div>
                )}
                <div ref={logsEndRef} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Compact Log Preview */}
        {!expandedLogs && liveLogs.length > 0 && (
          <div className="h-16 bg-cyber-dark border-t border-cyber-border px-4 py-2 overflow-hidden font-mono text-xs">
            <div className={`text-gray-300 truncate`}>
              {liveLogs[liveLogs.length - 1]}
            </div>
          </div>
        )}
      </Card>

      {/* Phase Configuration */}
      <div>
        <h3 className="text-lg font-display font-semibold text-white mb-4">Phase Configuration</h3>
        <Reorder.Group axis="y" values={phases} onReorder={(newOrder) => saveSettings(newOrder)} className="flex flex-col gap-4">
          {phases.map((phase, index) => {
            const phaseName = phase.name.toLowerCase()
            const phaseStatus = getPhaseStatus(phaseName)
            return (
              <Reorder.Item key={phase.id} value={phase}>
                <Card hoverable className="relative overflow-hidden group cursor-grab active:cursor-grabbing">
                  <motion.div 
                    className="absolute top-0 left-0 h-full bg-cyber-cyan/5 transition-all"
                    animate={{ width: phaseStatus === 'running' ? '100%' : phaseStatus === 'complete' ? '100%' : '0%' }}
                    initial={{ width: 0 }}
                  />
                  <div className="absolute top-0 right-0 w-16 h-16 opacity-10">
                    <div className="w-full h-full bg-gradient-to-br from-cyber-cyan to-transparent" />
                  </div>
                  
                  <div className="flex items-start justify-between relative">
                    <div className="flex items-start gap-4">
                      <div className="mt-1 text-gray-500 group-hover:text-cyber-cyan transition-colors">
                        <GripVertical className="w-5 h-5" />
                      </div>
                      <div className="flex items-center gap-2">
                        <motion.div
                          className={`w-8 h-8 rounded-full flex items-center justify-center ${
                            phaseStatus === 'complete' ? 'bg-cyber-green/20 text-cyber-green' :
                            phaseStatus === 'running' ? 'bg-cyber-cyan/20 text-cyber-cyan' :
                            phaseStatus === 'error' ? 'bg-cyber-red/20 text-cyber-red' :
                            'bg-cyber-dark text-gray-500'
                          }`}
                          animate={phaseStatus === 'running' ? { scale: [1, 1.1, 1] } : {}}
                        >
                          {phaseStatus === 'complete' ? (
                            <CheckCircle className="w-4 h-4" />
                          ) : phaseStatus === 'running' ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <span className="text-xs font-bold">{index + 1}</span>
                          )}
                        </motion.div>
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="w-6 h-6 rounded bg-cyber-cyan/20 text-cyber-cyan text-xs flex items-center justify-center font-bold">
                              {index + 1}
                            </span>
                            <h3 className="font-display font-semibold text-white">{phase.name}</h3>
                            {phase.id === 'p1' && (
                              <span className={`text-xs px-2 py-0.5 rounded ${
                                phase.videoSource === 'local' 
                                  ? 'bg-cyber-green/20 text-cyber-green' 
                                  : 'bg-cyber-cyan/20 text-cyber-cyan'
                              }`}>
                                {phase.videoSource === 'local' ? 'Local' : 'YouTube'}
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-400">
                            {phase.id === 'p1' 
                              ? phase.videoSource === 'local' 
                                ? 'Process videos from local media folder'
                                : 'Download videos from YouTube'
                              : phase.description
                            }
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 flex items-center gap-3 pl-12">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={phase.enabled}
                        onChange={() => togglePhase(phase.id)}
                        className="w-4 h-4 rounded border-cyber-border bg-cyber-dark text-cyber-cyan focus:ring-cyber-cyan"
                      />
                      <span className="text-sm text-gray-400">Enabled</span>
                    </label>
                    <button 
                      className="ml-auto p-2 text-gray-400 hover:text-cyber-cyan transition-colors"
                      onClick={() => openSettings(phase)}
                    >
                      <Settings className="w-4 h-4" />
                    </button>
                  </div>
                </Card>
              </Reorder.Item>
            )
          })}
        </Reorder.Group>
      </div>

      {/* Settings Modal */}
      {showSettings && selectedPhase && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-cyber-card border border-cyber-border rounded-lg p-6 w-full max-w-lg"
          >
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-display font-semibold text-white">
                {selectedPhase.name} Settings
              </h3>
              <button onClick={() => setShowSettings(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            {selectedPhase.id === 'p1' && (
              <div className="space-y-4">
                <div>
                  <label className="text-sm text-gray-400 mb-2 block">Video Source</label>
                  <div className="flex gap-3">
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => toggleVideoSource('youtube')}
                      className={`flex-1 p-3 rounded-lg border flex items-center justify-center gap-2 ${
                        selectedPhase.videoSource === 'youtube'
                          ? 'border-cyber-cyan bg-cyber-cyan/10 text-cyber-cyan'
                          : 'border-cyber-border text-gray-400 hover:border-gray-500'
                      }`}
                    >
                      <Video className="w-4 h-4" />
                      YouTube
                    </motion.button>
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => toggleVideoSource('local')}
                      className={`flex-1 p-3 rounded-lg border flex items-center justify-center gap-2 ${
                        selectedPhase.videoSource === 'local'
                          ? 'border-cyber-cyan bg-cyber-cyan/10 text-cyber-cyan'
                          : 'border-cyber-border text-gray-400 hover:border-gray-500'
                      }`}
                    >
                      <FolderOpen className="w-4 h-4" />
                      Local Media
                    </motion.button>
                  </div>
                </div>

                {selectedPhase.videoSource === 'youtube' && (
                  <div className="mt-4">
                    <label className="text-sm text-gray-400 mb-2 block">Direct Download URL</label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={downloadUrl}
                        onChange={(e) => setDownloadUrl(e.target.value)}
                        placeholder="https://youtube.com/watch?v=..."
                        className="flex-1 bg-cyber-dark border border-cyber-border rounded px-3 py-2 text-sm text-white focus:border-cyber-cyan focus:outline-none"
                      />
                      <motion.button 
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={() => downloadUrl && downloadMutation.mutate(downloadUrl)}
                        disabled={!downloadUrl || downloadMutation.isPending}
                        className="cyber-button px-4 flex items-center gap-2"
                      >
                        <Download className="w-4 h-4" />
                        Get
                      </motion.button>
                    </div>
                  </div>
                )}

                {selectedPhase.videoSource === 'local' && localVideos.length > 0 && (
                  <div>
                    <label className="text-sm text-gray-400 mb-2 block">Available Videos</label>
                    <div className="space-y-2 max-h-48 overflow-y-auto">
                      {localVideos.map((video, i) => (
                        <div key={i} className="p-2 bg-cyber-dark rounded text-sm text-gray-300 flex items-center gap-2">
                          <Video className="w-4 h-4 text-cyber-cyan" />
                          {video.name}
                        </div>
                      ))}
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      Place videos in: ~/ShortsForge/media/
                    </p>
                  </div>
                )}
              </div>
            )}

            {selectedPhase.id !== 'p1' && (
              <p className="text-gray-400">No additional settings for this phase.</p>
            )}

            <div className="mt-6 flex justify-end">
              <motion.button 
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setShowSettings(false)} 
                className="cyber-button-primary flex items-center gap-2"
              >
                <Save className="w-4 h-4" />
                Save
              </motion.button>
            </div>
          </motion.div>
        </div>
      )}
    </motion.div>
  )
}