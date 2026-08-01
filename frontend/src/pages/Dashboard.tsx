import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Play, Square, RefreshCw, FileText, Video, Zap, Activity, FolderOpen, Settings, X, Download, ExternalLink, Wifi, WifiOff } from 'lucide-react'
import { Card, StatCard } from '@/components/ui/Card'
import { getMetricsSummary, getStatus, getLearningWeights, runPipeline, stopPipeline, syncMetrics, getLogs, downloadFromUrl } from '@/lib/api'
import { formatNumber } from '@/lib/utils'
import { AnimatedCounter } from '@/components/ui/AnimatedCounter'
import { useToast } from '@/contexts/ToastContext'
import PipelineProgress from '@/components/pipeline-progress'
import { stagger, slideLeft, springGentle } from '@/lib/animations'
import { useWebSocket } from '@/lib/websocket'

export default function Dashboard() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [videoSource, setVideoSource] = useState<'youtube' | 'local'>('youtube')
  const [showLogs, setShowLogs] = useState(false)
  const [downloadUrl, setDownloadUrl] = useState('')
  const logsEndRef = useRef<HTMLDivElement>(null)

  const wsUrl = `ws://${window.location.hostname}:8000/ws`
  const { isConnected, subscribe } = useWebSocket(wsUrl)

  useEffect(() => {
    const unsubStatus = subscribe('pipeline:status', () => {
      queryClient.invalidateQueries({ queryKey: ['status'] })
    })
    const unsubLog = subscribe('log', () => {
      queryClient.invalidateQueries({ queryKey: ['logs'] })
    })
    const unsubMetrics = subscribe('metrics:updated', () => {
      queryClient.invalidateQueries({ queryKey: ['metrics-summary'] })
    })
    return () => { unsubStatus(); unsubLog(); unsubMetrics() }
  }, [subscribe, queryClient])

  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: getStatus,
    refetchInterval: isConnected ? false : 5000,
  })

  const { data: metrics } = useQuery({
    queryKey: ['metrics-summary'],
    queryFn: getMetricsSummary,
  })

  const { data: weights } = useQuery({
    queryKey: ['learning-weights'],
    queryFn: getLearningWeights,
  })

  const runMutation = useMutation({
    mutationFn: () => runPipeline(videoSource),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['status'] }),
    onError: (error: Error) => toast('error', `Failed to run pipeline: ${error.message}`),
  })

  const stopMutation = useMutation({
    mutationFn: stopPipeline,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['status'] }),
    onError: (error: Error) => toast('error', `Failed to stop pipeline: ${error.message}`),
  })

  const syncMutation = useMutation({
    mutationFn: syncMetrics,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['metrics-summary'] }),
    onError: (error: Error) => toast('error', `Failed to sync metrics: ${error.message}`),
  })

  const downloadMutation = useMutation({
    mutationFn: (url: string) => downloadFromUrl(url),
    onSuccess: () => { toast('success', 'Download started'); setDownloadUrl('') },
    onError: (error: Error) => toast('error', `Download failed: ${error.message}`),
  })

  const { data: logsData } = useQuery({
    queryKey: ['logs'],
    queryFn: () => getLogs(200),
    refetchInterval: showLogs ? 2000 : false,
    enabled: showLogs,
  })

  useEffect(() => {
    if (showLogs && logsEndRef.current && logsData?.logs?.length) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [showLogs, logsData?.logs?.length])

  const baseline = metrics?.baseline || {}

  return (
    <motion.div variants={stagger.container} initial="hidden" animate="show" className="space-y-6">
      {/* Header */}
      <motion.div variants={slideLeft} className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-40k-gold">DASH</span>BOARD
          </h1>
          <p className="text-gray-400 mt-1">System overview and quick stats</p>
        </div>

        <div className="flex items-center gap-3">
          <motion.div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${
              isConnected
                ? 'bg-40k-gold/10 border-40k-gold/30 text-40k-gold'
                : 'bg-red-500/10 border-red-500/30 text-red-400'
            }`}
            animate={isConnected ? { scale: [1, 1.02, 1] } : {}}
            transition={{ duration: 2, repeat: Infinity }}
          >
            {isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            <span className="text-xs">{isConnected ? 'Live' : 'Offline'}</span>
          </motion.div>
          <motion.button
            className="cyber-button flex items-center gap-2"
            onClick={() => setShowLogs(true)}
            whileHover={{ scale: 1.03, boxShadow: '0 0 15px rgb(var(--40k-gold-rgb) / 0.2)' }}
            whileTap={{ scale: 0.97 }}
          >
            <Settings className="w-4 h-4" />
            Logs
          </motion.button>
          <motion.button
            className="cyber-button flex items-center gap-2"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
          >
            <motion.div
              animate={syncMutation.isPending ? { rotate: 360 } : {}}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            >
              <RefreshCw className="w-4 h-4" />
            </motion.div>
            {syncMutation.isPending ? 'Syncing...' : 'Sync Metrics'}
          </motion.button>
        </div>
      </motion.div>

      {/* Pipeline Error Banner */}
      {status?.pipeline?.error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-40k-red-bright/10 border border-40k-red-bright/30 rounded-lg px-5 py-4 flex items-start gap-3"
        >
          <motion.div
            className="w-2 h-2 mt-1.5 rounded-full bg-40k-red-bright flex-shrink-0"
            animate={{ scale: [1, 1.5, 1], opacity: [0.7, 1, 0.7] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-40k-red-bright">Pipeline Error</p>
            <p className="text-xs text-gray-300 font-mono mt-1 break-words">{status.pipeline.error}</p>
          </div>
        </motion.div>
      )}

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Videos" value={<AnimatedCounter value={metrics?.total_videos || 0} />} icon={<Video className="w-6 h-6" />} delay={0.05} />
        <StatCard label="Total Scripts" value={<AnimatedCounter value={metrics?.total_scripts || 0} />} icon={<FileText className="w-6 h-6" />} delay={0.1} />
        <StatCard label="Avg Views" value={<AnimatedCounter value={baseline.avg_views || 0} format={(v) => formatNumber(v)} />} icon={<Activity className="w-6 h-6" />} delay={0.15} />
        <StatCard label="Avg Engagement" value={<AnimatedCounter value={baseline.avg_engagement || 0} format={(v) => `${v.toFixed(2)}%`} />} icon={<Zap className="w-6 h-6" />} trend={{ value: 12, positive: true }} delay={0.2} />
      </div>

      {/* Pipeline Status & Content Type */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pipeline Status */}
        <motion.div variants={stagger.item}>
          <Card hoverable className="h-full">
            <h3 className="text-lg font-display font-semibold text-white mb-4 flex items-center gap-2">
              <motion.div
                animate={status?.pipeline?.running ? { rotate: [0, 15, -15, 0] } : {}}
                transition={{ duration: 3, repeat: Infinity }}
              >
                <Activity className="w-5 h-5 text-40k-gold" />
              </motion.div>
              Pipeline Status
            </h3>

            <div className="space-y-4">
              <motion.div
                className="flex items-center justify-between p-3 bg-40k-dark rounded-lg"
                whileHover={{ backgroundColor: 'rgba(var(--40k-gold-rgb), 0.05)' }}
              >
                <span className="text-gray-400">Status</span>
                <motion.span
                  className={`px-3 py-1 rounded-full text-sm ${
                    status?.pipeline?.running
                      ? 'bg-40k-gold-dim/20 text-40k-gold-dim'
                      : 'bg-gray-500/20 text-gray-400'
                  }`}
                  animate={status?.pipeline?.running ? { opacity: [0.7, 1, 0.7] } : {}}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  {status?.pipeline?.running ? 'Running' : 'Idle'}
                </motion.span>
              </motion.div>

              <PipelineProgress status={status} />

              {/* URL Download */}
              <motion.div
                className="p-3 bg-40k-dark rounded-lg space-y-2"
                whileHover={{ backgroundColor: 'rgba(var(--40k-gold-rgb), 0.03)' }}
              >
                <label className="text-xs text-gray-400 flex items-center gap-1">
                  <Download className="w-3 h-3" /> Download from URL
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={downloadUrl}
                    onChange={(e) => setDownloadUrl(e.target.value)}
                    placeholder="https://youtube.com/watch?v=..."
                    className="flex-1 bg-40k-black border border-40k-border rounded px-3 py-1.5 text-xs text-white placeholder-gray-600 focus:outline-none focus:border-40k-gold/50 transition-all duration-300"
                  />
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => downloadUrl.trim() && downloadMutation.mutate(downloadUrl.trim())}
                    disabled={!downloadUrl.trim() || downloadMutation.isPending}
                    className="cyber-button px-3 py-1.5 text-xs flex items-center gap-1"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Get
                  </motion.button>
                </div>
              </motion.div>

              <motion.div
                className="flex items-center justify-between p-3 bg-40k-dark rounded-lg"
                whileHover={{ backgroundColor: 'rgba(var(--40k-gold-rgb), 0.05)' }}
              >
                <span className="text-gray-400">OAuth</span>
                <span className={`px-3 py-1 rounded-full text-sm ${
                  status?.oauth_configured
                    ? 'bg-40k-gold-dim/20 text-40k-gold-dim'
                    : 'bg-40k-bronze/20 text-40k-bronze'
                }`}>
                  {status?.oauth_configured ? 'Connected' : 'Not Configured'}
                </span>
              </motion.div>

              <motion.div
                className="flex items-center justify-between p-3 bg-40k-dark rounded-lg"
                whileHover={{ backgroundColor: 'rgba(var(--40k-gold-rgb), 0.05)' }}
              >
                <span className="text-gray-400">Game Title</span>
                <span className="text-40k-gold text-sm font-medium">{status?.game_title || 'Not set'}</span>
              </motion.div>

              {status?.parent_franchise && status?.parent_franchise !== status?.game_title && (
                <motion.div
                  className="flex items-center justify-between p-3 bg-40k-dark rounded-lg"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                >
                  <span className="text-gray-400">Series</span>
                  <span className="text-40k-crimson-bright text-sm font-medium">{status?.parent_franchise}</span>
                </motion.div>
              )}

              {/* Video Source Toggle */}
              <div className="flex items-center gap-2 p-3 bg-40k-dark rounded-lg">
                <span className="text-gray-400 text-sm">Source:</span>
                {(['youtube', 'local'] as const).map((src) => (
                  <motion.button
                    key={src}
                    onClick={() => setVideoSource(src)}
                    className={`px-3 py-1 rounded text-sm flex items-center gap-1 transition-all duration-200 ${
                      videoSource === src
                        ? 'bg-40k-gold/20 text-40k-gold border border-40k-gold'
                        : 'text-gray-500 hover:text-gray-300'
                    }`}
                    whileHover={videoSource !== src ? { scale: 1.05 } : {}}
                    whileTap={{ scale: 0.95 }}
                  >
                    {src === 'youtube' ? <Video className="w-3 h-3" /> : <FolderOpen className="w-3 h-3" />}
                    {src === 'youtube' ? 'YouTube' : 'Local Media'}
                  </motion.button>
                ))}
              </div>

              <div className="flex gap-3 mt-4">
                <motion.button
                  whileHover={{ scale: 1.03, boxShadow: '0 0 20px rgb(var(--40k-gold-rgb) / 0.35)' }}
                  whileTap={{ scale: 0.97 }}
                  className="cyber-button-primary flex-1 flex items-center justify-center gap-2"
                  onClick={() => runMutation.mutate()}
                  disabled={runMutation.isPending || status?.pipeline?.running}
                >
                  <Play className="w-4 h-4" />
                  {runMutation.isPending ? 'Starting...' : 'Run Pipeline'}
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.97 }}
                  className="cyber-button flex-1 flex items-center justify-center gap-2"
                  onClick={() => stopMutation.mutate()}
                  disabled={stopMutation.isPending || !status?.pipeline?.running}
                >
                  <Square className="w-4 h-4" />
                  {stopMutation.isPending ? 'Stopping...' : 'Stop'}
                </motion.button>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Content Type Weights */}
        <motion.div variants={stagger.item}>
          <Card hoverable className="h-full">
            <h3 className="text-lg font-display font-semibold text-white mb-4">
              Content Type Selection (70/30)
            </h3>

            <div className="space-y-3">
              {weights?.weights && Object.entries(weights.weights).length > 0 ? (
                Object.entries(weights.weights).map(([type, weight], idx) => (
                  <motion.div
                    key={type}
                    className="flex items-center gap-3"
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.08, ...springGentle }}
                  >
                    <div className="w-24 text-sm text-gray-400 capitalize">{type}</div>
                    <div className="flex-1 h-3 bg-40k-dark rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${(weight as number) * 100}%` }}
                        transition={{ type: 'spring', stiffness: 60, damping: 20, delay: idx * 0.1 }}
                        className="h-full bg-gradient-to-r from-40k-gold to-40k-crimson-bright rounded-full"
                      />
                    </div>
                    <div className="w-12 text-right text-sm text-40k-gold">
                      {((weight as number) * 100).toFixed(0)}%
                    </div>
                  </motion.div>
                ))
              ) : (
                <p className="text-gray-500 text-sm">No learning data yet. Run the pipeline to collect data.</p>
              )}
            </div>

            {weights?.selected && (
              <motion.div
                className="mt-4 p-3 bg-40k-dark rounded-lg"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
              >
                <p className="text-sm text-gray-400">
                  Next selected type: <span className="text-40k-gold font-medium capitalize">{weights.selected}</span>
                </p>
              </motion.div>
            )}
          </Card>
        </motion.div>
      </div>

      {/* Learnings Summary */}
      <motion.div variants={stagger.item}>
        <Card hoverable>
          <h3 className="text-lg font-display font-semibold text-white mb-4">
            Learnings Summary
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Patterns Discovered', value: metrics?.learnings_count || 0, color: 'text-40k-gold' },
              { label: 'Scripts Analyzed', value: metrics?.total_scripts || 0, color: 'text-40k-crimson-bright' },
              { label: 'Data Points', value: baseline.sample_count || 0, color: 'text-40k-gold-bright' },
              { label: 'Avg Score', value: baseline.avg_score || 0, color: 'text-40k-gold-dim' },
            ].map((item, idx) => (
              <motion.div
                key={item.label}
                className="text-center p-4 bg-40k-dark rounded-lg"
                initial={{ opacity: 0, y: 16, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ delay: 0.1 + idx * 0.08, type: 'spring', stiffness: 80, damping: 15 }}
                whileHover={{ y: -2, boxShadow: '0 0 15px rgb(var(--40k-gold-rgb) / 0.1)' }}
              >
                <motion.p
                  className={`text-2xl font-display font-bold ${item.color}`}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.2 + idx * 0.08 }}
                >
                  <AnimatedCounter value={item.value} />
                </motion.p>
                <p className="text-sm text-gray-400 mt-1">{item.label}</p>
              </motion.div>
            ))}
          </div>
        </Card>
      </motion.div>

      {/* Logs Modal */}
      <AnimatePresence>
        {showLogs && (
          <motion.div
            className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: 'spring', stiffness: 200, damping: 20 }}
            className="bg-40k-card border border-40k-border rounded-lg p-4 w-full max-w-4xl h-[80vh] flex flex-col"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-display font-semibold text-white flex items-center gap-2">
                <Activity className="w-5 h-5 text-40k-gold" />
                Pipeline Logs
              </h3>
              <motion.button
                onClick={() => setShowLogs(false)}
                className="text-gray-400 hover:text-white transition-colors"
                whileHover={{ scale: 1.1, rotate: 90 }}
                whileTap={{ scale: 0.9 }}
              >
                <X className="w-5 h-5" />
              </motion.button>
            </div>

            <div className="flex-1 bg-40k-dark border border-40k-border rounded p-4 overflow-y-auto font-mono text-xs text-40k-gold-dim">
              {logsData?.logs?.length ? (
                logsData.logs.map((log: string, i: number) => {
                  const lower = log.toLowerCase()
                  const colorClass = lower.includes('error') || lower.includes('failed')
                    ? 'text-red-400'
                    : lower.includes('warn')
                    ? 'text-yellow-400'
                    : lower.includes('complete') || lower.includes('success')
                    ? 'text-green-400'
                    : ''
                  return (
                    <motion.div
                      key={i}
                      className={`mb-1 whitespace-pre-wrap ${colorClass}`}
                      initial={{ opacity: 0, x: -5 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: Math.min(i * 0.005, 0.5) }}
                    >
                      {log}
                    </motion.div>
                  )
                })
              ) : (
                <div className="text-gray-500 italic">No logs available...</div>
              )}
              <div ref={logsEndRef} />
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
    </motion.div>
  )
}
