import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Play, Square, RefreshCw, FileText, Video, Zap, Activity, FolderOpen, Settings, X } from 'lucide-react'
import { Card, StatCard } from '@/components/ui/Card'
import { getMetricsSummary, getStatus, getLearningWeights, runPipeline, stopPipeline, syncMetrics, getLogs } from '@/lib/api'
import { formatNumber } from '@/lib/utils'
import { AnimatedCounter } from '@/components/ui/AnimatedCounter'

export default function Dashboard() {
  const queryClient = useQueryClient()
  const [videoSource, setVideoSource] = useState<'youtube' | 'local'>('youtube')
  const [showLogs, setShowLogs] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)

  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: getStatus,
    refetchInterval: 5000,
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })

  const stopMutation = useMutation({
    mutationFn: stopPipeline,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['status'] })
    },
  })

  const syncMutation = useMutation({
    mutationFn: syncMetrics,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metrics-summary'] })
    },
  })

  const { data: logsData } = useQuery({
    queryKey: ['logs'],
    queryFn: () => getLogs(200),
    refetchInterval: showLogs ? 2000 : false,
    enabled: showLogs
  })

  useEffect(() => {
    if (showLogs && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logsData, showLogs])

  const baseline = metrics?.baseline || {}

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
      {/* Header */}
      <div className="flex items-center justify-between">
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
        >
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-cyber-cyan">DASH</span>BOARD
          </h1>
          <p className="text-gray-400 mt-1">System overview and quick stats</p>
        </motion.div>

        <div className="flex items-center gap-3">
          <button 
            className="cyber-button flex items-center gap-2"
            onClick={() => setShowLogs(true)}
          >
            <Settings className="w-4 h-4" />
            Logs
          </button>
          <button 
            className="cyber-button flex items-center gap-2"
            onClick={() => syncMutation.mutate()}
            disabled={syncMutation.isPending}
          >
            <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
            {syncMutation.isPending ? 'Syncing...' : 'Sync Metrics'}
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <StatCard
            label="Total Videos"
            value={<AnimatedCounter value={metrics?.total_videos || 0} />}
            icon={<Video className="w-6 h-6" />}
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <StatCard
            label="Total Scripts"
            value={<AnimatedCounter value={metrics?.total_scripts || 0} />}
            icon={<FileText className="w-6 h-6" />}
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <StatCard
            label="Avg Views"
            value={<AnimatedCounter value={baseline.avg_views || 0} format={(v) => formatNumber(v)} />}
            icon={<Activity className="w-6 h-6" />}
          />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
          <StatCard
            label="Avg Engagement"
            value={<AnimatedCounter value={baseline.avg_engagement || 0} format={(v) => `${v.toFixed(2)}%`} />}
            icon={<Zap className="w-6 h-6" />}
            trend={{ value: 12, positive: true }}
          />
        </motion.div>
      </div>

      {/* Pipeline Status & Content Type */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pipeline Status */}
        <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card hoverable className="h-full">
          <h3 className="text-lg font-display font-semibold text-white mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-cyber-cyan" />
            Pipeline Status
          </h3>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-cyber-dark rounded-lg">
              <span className="text-gray-400">Status</span>
              <span className={`px-3 py-1 rounded-full text-sm ${
                status?.pipeline?.running 
                  ? 'bg-cyber-green/20 text-cyber-green' 
                  : 'bg-gray-500/20 text-gray-400'
              }`}>
                {status?.pipeline?.running ? 'Running' : 'Idle'}
              </span>
            </div>

            {/* Current Phase */}
            {status?.pipeline?.running && (
              <div className="p-3 bg-cyber-dark rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-gray-400 text-sm">Current Phase</span>
                  <span className="text-cyber-cyan text-sm font-medium capitalize">
                    {status?.pipeline?.current_phase?.replace('_', ' ') || 'Starting...'}
                  </span>
                </div>
                <div className="h-2 bg-cyber-border rounded-full overflow-hidden">
                  <motion.div 
                    className="h-full bg-gradient-to-r from-cyber-cyan to-cyber-magenta"
                    initial={{ width: 0 }}
                    animate={{ width: `${status?.pipeline?.progress || 0}%` }}
                    transition={{ type: 'spring', stiffness: 50, damping: 20 }}
                  />
                </div>
                <div className="flex justify-between mt-1 text-xs text-gray-500">
                  <span>{status?.pipeline?.progress || 0}%</span>
                  <span>{status?.pipeline?.message || ''}</span>
                </div>
              </div>
            )}

            {/* Error Display */}
            {status?.pipeline?.error && (
              <div className="p-3 bg-cyber-red/10 border border-cyber-red/30 rounded-lg">
                <div className="flex items-center gap-2 text-cyber-red text-sm font-medium mb-1">
                  ⚠️ Error
                </div>
                <p className="text-xs text-gray-300 font-mono">{status.pipeline.error}</p>
              </div>
            )}

            <div className="flex items-center justify-between p-3 bg-cyber-dark rounded-lg">
              <span className="text-gray-400">OAuth</span>
              <span className={`px-3 py-1 rounded-full text-sm ${
                status?.oauth_configured 
                  ? 'bg-cyber-green/20 text-cyber-green' 
                  : 'bg-cyber-orange/20 text-cyber-orange'
              }`}>
                {status?.oauth_configured ? 'Connected' : 'Not Configured'}
              </span>
            </div>

            {/* Video Source Toggle */}
            <div className="flex items-center gap-2 p-3 bg-cyber-dark rounded-lg">
              <span className="text-gray-400 text-sm">Source:</span>
              <button
                onClick={() => setVideoSource('youtube')}
                className={`px-3 py-1 rounded text-sm flex items-center gap-1 ${
                  videoSource === 'youtube' 
                    ? 'bg-cyber-cyan/20 text-cyber-cyan border border-cyber-cyan' 
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                <Video className="w-3 h-3" /> YouTube
              </button>
              <button
                onClick={() => setVideoSource('local')}
                className={`px-3 py-1 rounded text-sm flex items-center gap-1 ${
                  videoSource === 'local' 
                    ? 'bg-cyber-cyan/20 text-cyber-cyan border border-cyber-cyan' 
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                <FolderOpen className="w-3 h-3" /> Local Media
              </button>
            </div>

            <div className="flex gap-3 mt-4">
              <motion.button 
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="cyber-button-primary flex-1 flex items-center justify-center gap-2"
                onClick={() => runMutation.mutate()}
                disabled={runMutation.isPending || status?.pipeline?.running}
              >
                <Play className="w-4 h-4" />
                {runMutation.isPending ? 'Starting...' : 'Run Pipeline'}
              </motion.button>
              <motion.button 
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
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
        <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card hoverable className="h-full">
          <h3 className="text-lg font-display font-semibold text-white mb-4">
            Content Type Selection (70/30)
          </h3>
          
          <div className="space-y-3">
            {weights?.weights && Object.entries(weights.weights).length > 0 ? (
              Object.entries(weights.weights).map(([type, weight]) => (
                <div key={type} className="flex items-center gap-3">
                  <div className="w-24 text-sm text-gray-400 capitalize">{type}</div>
                  <div className="flex-1 h-2 bg-cyber-dark rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${(weight as number) * 100}%` }}
                      className="h-full bg-gradient-to-r from-cyber-cyan to-cyber-magenta"
                    />
                  </div>
                  <div className="w-12 text-right text-sm text-cyber-cyan">
                    {((weight as number) * 100).toFixed(0)}%
                  </div>
                </div>
              ))
            ) : (
              <p className="text-gray-500 text-sm">No learning data yet. Run the pipeline to collect data.</p>
            )}
          </div>

          {weights?.selected && (
            <div className="mt-4 p-3 bg-cyber-dark rounded-lg">
              <p className="text-sm text-gray-400">
                Next selected type: <span className="text-cyber-cyan font-medium capitalize">{weights.selected}</span>
              </p>
            </div>
          )}
          </Card>
        </motion.div>
      </div>

      {/* Recent Activity */}
      <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
        <Card hoverable>
        <h3 className="text-lg font-display font-semibold text-white mb-4">
          Learnings Summary
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center p-4 bg-cyber-dark rounded-lg">
            <p className="text-2xl font-display font-bold text-cyber-cyan">
              <AnimatedCounter value={metrics?.learnings_count || 0} />
            </p>
            <p className="text-sm text-gray-400">Patterns Discovered</p>
          </div>
          <div className="text-center p-4 bg-cyber-dark rounded-lg">
            <p className="text-2xl font-display font-bold text-cyber-magenta">
              <AnimatedCounter value={metrics?.total_scripts || 0} />
            </p>
            <p className="text-sm text-gray-400">Scripts Analyzed</p>
          </div>
          <div className="text-center p-4 bg-cyber-dark rounded-lg">
            <p className="text-2xl font-display font-bold text-cyber-yellow">
              <AnimatedCounter value={baseline.sample_count || 0} />
            </p>
            <p className="text-sm text-gray-400">Data Points</p>
          </div>
          <div className="text-center p-4 bg-cyber-dark rounded-lg">
            <p className="text-2xl font-display font-bold text-cyber-green">
              <AnimatedCounter value={baseline.avg_score || 0} />
            </p>
            <p className="text-sm text-gray-400">Avg Score</p>
          </div>
        </div>
        </Card>
      </motion.div>

      {/* Logs Modal */}
      {showLogs && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-cyber-card border border-cyber-border rounded-lg p-4 w-full max-w-4xl h-[80vh] flex flex-col"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-display font-semibold text-white flex items-center gap-2">
                <Settings className="w-5 h-5 text-cyber-cyan" />
                Pipeline Logs
              </h3>
              <button onClick={() => setShowLogs(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="flex-1 bg-cyber-dark border border-cyber-border rounded p-4 overflow-y-auto font-mono text-xs text-cyber-green">
              {logsData?.logs?.length ? (
                logsData.logs.map((log: string, i: number) => (
                  <div key={i} className="mb-1 whitespace-pre-wrap">{log}</div>
                ))
              ) : (
                <div className="text-gray-500 italic">No logs available...</div>
              )}
              <div ref={logsEndRef} />
            </div>
          </motion.div>
        </div>
      )}
    </motion.div>
  )
}