import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  RefreshCw, TrendingUp, Eye, Heart, MessageCircle,
  Video, Users, Download, BarChart3,
} from 'lucide-react'
import { Card, StatCard } from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import {
  getMetricsSummary, getVideoMetrics, getContentPerformance,
  getTikTokSummary, getTikTokVideos, getTikTokDaily, getTikTokGames,
  getCrossPlatformStats, importTikTokData, matchTikTokToLocal,
} from '@/lib/api'
import { formatNumber } from '@/lib/utils'
import { AnimatedCounter } from '@/components/ui/AnimatedCounter'
import { useToast } from '@/contexts/ToastContext'
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

const GAME_COLORS: Record<string, string> = {
  atomic_heart: '#ff6b6b',
  banishers: '#4ecdc4',
  genshin_impact: '#45b7d1',
  unknown: '#8884d8',
}

function formatGameName(game: string): string {
  return game.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

type Tab = 'youtube' | 'tiktok' | 'comparison'

export default function Performance() {
  const [activeTab, setActiveTab] = useState<Tab>('youtube')
  const [dailyDays, setDailyDays] = useState(30)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // YouTube queries
  const { data: summary } = useQuery({
    queryKey: ['metrics-summary'],
    queryFn: getMetricsSummary,
  })
  const { data: videos } = useQuery({
    queryKey: ['video-metrics'],
    queryFn: getVideoMetrics,
  })
  const { data: contentPerf } = useQuery({
    queryKey: ['content-performance'],
    queryFn: getContentPerformance,
  })

  // TikTok queries
  const { data: tiktokSummary } = useQuery({
    queryKey: ['tiktok-summary'],
    queryFn: getTikTokSummary,
  })
  const { data: tiktokVideosData } = useQuery({
    queryKey: ['tiktok-videos'],
    queryFn: getTikTokVideos,
  })
  const { data: tiktokDaily } = useQuery({
    queryKey: ['tiktok-daily', dailyDays],
    queryFn: () => getTikTokDaily(dailyDays),
  })
  const { data: tiktokGames } = useQuery({
    queryKey: ['tiktok-games'],
    queryFn: getTikTokGames,
  })

  // Cross-platform query
  const { data: crossPlatform } = useQuery({
    queryKey: ['cross-platform-stats'],
    queryFn: getCrossPlatformStats,
  })

  // Mutations
  const importMutation = useMutation({
    mutationFn: importTikTokData,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tiktok-summary'] })
      queryClient.invalidateQueries({ queryKey: ['tiktok-videos'] })
      queryClient.invalidateQueries({ queryKey: ['tiktok-daily'] })
      queryClient.invalidateQueries({ queryKey: ['tiktok-games'] })
      queryClient.invalidateQueries({ queryKey: ['cross-platform-stats'] })
      toast('success', 'TikTok data imported successfully')
    },
    onError: (error: Error) => toast('error', `Failed to import TikTok data: ${error.message}`),
  })

  const matchMutation = useMutation({
    mutationFn: matchTikTokToLocal,
    onSuccess: () => toast('success', 'TikTok clips matched successfully'),
    onError: (error: Error) => toast('error', `Failed to match TikTok clips: ${error.message}`),
  })

  // YouTube data processing
  const baseline = summary?.baseline || {}
  const hasNoData = (videos?.videos || []).length === 0

  const seenIds = new Set<string>()
  const uniqueVideos = (videos?.videos || [])
    .sort((a: any, b: any) => (b.created_at || '').localeCompare(a.created_at || ''))
    .filter((v: any) => {
      if (seenIds.has(v.youtube_id)) return false
      seenIds.add(v.youtube_id)
      return true
    })

  const titleCounts = new Map<string, number>()
  const videoData = uniqueVideos.slice(0, 10).map((v: any) => {
    const baseTitle = v.title?.slice(0, 20) || 'Unknown'
    const count = titleCounts.get(baseTitle) || 0
    titleCounts.set(baseTitle, count + 1)
    return {
      name: count > 0 ? `${baseTitle} (${count})` : baseTitle,
      views: v.views || 0,
      engagement: v.engagement_ratio || 0,
    }
  })

  const contentData = contentPerf
    ? Object.entries(contentPerf).map(([name, data]: [string, any]) => ({
        name,
        views: data.avg_views || 0,
        score: data.avg_score || 0,
        count: data.script_count || 0,
      }))
    : []

  // TikTok data processing
  const tiktokVideos = tiktokVideosData?.videos || []
  const tiktokDailyData = tiktokDaily?.daily || []
  const tiktokGamesData = tiktokGames?.games || {}

  const tiktokGameChartData = Object.entries(tiktokGamesData).map(([game, stats]: [string, any]) => ({
    name: formatGameName(game),
    views: stats.total_views,
    videos: stats.video_count,
    color: GAME_COLORS[game] || '#8884d8',
  }))

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'youtube', label: 'YouTube Shorts', icon: <Video className="w-4 h-4" /> },
    { id: 'tiktok', label: 'TikTok', icon: <Video className="w-4 h-4" /> },
    { id: 'comparison', label: 'Cross-Platform', icon: <BarChart3 className="w-4 h-4" /> },
  ]

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{
        hidden: { opacity: 0 },
        show: { opacity: 1, transition: { staggerChildren: 0.1 } },
      }}
      className="space-y-6"
    >
      {/* Header */}
      <motion.div
        variants={{ hidden: { opacity: 0, y: -20 }, show: { opacity: 1, y: 0 } }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-40k-gold">PERFORMANCE</span> DASHBOARD
          </h1>
          <p className="text-gray-400 mt-1">Track video performance across platforms</p>
        </div>
        <div className="flex gap-2">
          {activeTab === 'tiktok' && (
            <>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="cyber-button flex items-center gap-2"
                onClick={() => matchMutation.mutate()}
                disabled={matchMutation.isPending}
              >
                <BarChart3 className="w-4 h-4" />
                {matchMutation.isPending ? 'Matching...' : 'Match Clips'}
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="cyber-button flex items-center gap-2"
                onClick={() => importMutation.mutate()}
                disabled={importMutation.isPending}
              >
                <Download className="w-4 h-4" />
                {importMutation.isPending ? 'Importing...' : 'Import CSV'}
              </motion.button>
            </>
          )}
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="cyber-button flex items-center gap-2"
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ['metrics-summary'] })
              queryClient.invalidateQueries({ queryKey: ['video-metrics'] })
              queryClient.invalidateQueries({ queryKey: ['content-performance'] })
              queryClient.invalidateQueries({ queryKey: ['tiktok-summary'] })
              queryClient.invalidateQueries({ queryKey: ['tiktok-videos'] })
              queryClient.invalidateQueries({ queryKey: ['tiktok-daily'] })
              queryClient.invalidateQueries({ queryKey: ['tiktok-games'] })
              queryClient.invalidateQueries({ queryKey: ['cross-platform-stats'] })
            }}
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </motion.button>
        </div>
      </motion.div>

      {/* Tabs */}
      <motion.div
        variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}
        className="flex gap-1 p-1 bg-40k-dark/50 rounded-lg border border-40k-border"
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md transition-all ${
              activeTab === tab.id
                ? 'bg-40k-gold/20 text-40k-gold border border-40k-gold/30'
                : 'text-gray-400 hover:text-white hover:bg-40k-dark/50'
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </motion.div>

      {/* YouTube Tab */}
      {activeTab === 'youtube' && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <StatCard
              label="Total Videos"
              value={<AnimatedCounter value={summary?.total_videos || 0} />}
              icon={<Eye className="w-6 h-6" />}
            />
            <StatCard
              label="Avg Views"
              value={<AnimatedCounter value={baseline.avg_views || 0} format={(v) => formatNumber(v)} />}
              icon={<TrendingUp className="w-6 h-6" />}
            />
            <StatCard
              label="Avg Engagement"
              value={<AnimatedCounter value={baseline.avg_engagement || 0} format={(v) => `${v.toFixed(2)}%`} />}
              icon={<Heart className="w-6 h-6" />}
            />
            <StatCard
              label="Performance Score"
              value={<AnimatedCounter value={baseline.avg_score || 0} />}
              icon={<MessageCircle className="w-6 h-6" />}
            />
          </div>

          {hasNoData ? (
            <Card>
              <div className="flex flex-col items-center justify-center py-16 text-gray-500">
                <TrendingUp className="w-16 h-16 mb-4 opacity-20" />
                <p className="text-lg font-medium text-gray-400">No YouTube metrics yet</p>
                <p className="text-sm mt-2">Upload videos and run the pipeline to see performance data.</p>
              </div>
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card hoverable>
                  <h3 className="text-lg font-display font-semibold text-white mb-4">Top Videos - Views</h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={videoData}>
                        <defs>
                          <linearGradient id="viewsGrad" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ff6b6b" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#ff6b6b" stopOpacity={0} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
                        <XAxis dataKey="name" stroke="#666" tick={{ fill: '#666', fontSize: 10 }} />
                        <YAxis stroke="#666" tick={{ fill: '#666', fontSize: 10 }} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                        />
                        <Area type="monotone" dataKey="views" stroke="#ff6b6b" fillOpacity={1} fill="url(#viewsGrad)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </Card>

                <Card hoverable>
                  <h3 className="text-lg font-display font-semibold text-white mb-4">Content Type Performance</h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={contentData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
                        <XAxis dataKey="name" stroke="#666" tick={{ fill: '#666', fontSize: 10 }} />
                        <YAxis stroke="#666" tick={{ fill: '#666', fontSize: 10 }} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                        />
                        <Bar dataKey="score" fill="#ff6b6b" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Card>
              </div>

              <Card hoverable>
                <SectionHeader title="Recent Videos" icon={<Video className="w-4 h-4" />} terminal />
                <div className="overflow-x-auto mt-4">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-40k-border">
                        <th className="text-left py-3 px-4 text-gray-400 font-medium">Title</th>
                        <th className="text-right py-3 px-4 text-gray-400 font-medium">Views</th>
                        <th className="text-right py-3 px-4 text-gray-400 font-medium">Likes</th>
                        <th className="text-right py-3 px-4 text-gray-400 font-medium">Engagement</th>
                        <th className="text-right py-3 px-4 text-gray-400 font-medium">Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {uniqueVideos.slice(0, 10).map((v: any, i: number) => (
                        <motion.tr
                          key={v.youtube_id || i}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: i * 0.03 }}
                          className="border-b border-40k-border/50 hover:bg-40k-dark/50"
                        >
                          <td className="py-3 px-4 text-white truncate max-w-xs">
                            <a
                              href={`https://youtube.com/shorts/${v.youtube_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="hover:text-40k-gold transition-colors"
                            >
                              {v.title?.slice(0, 40)}{v.title?.length > 40 ? '...' : ''}
                            </a>
                          </td>
                          <td className="py-3 px-4 text-right text-40k-gold">{formatNumber(v.views || 0)}</td>
                          <td className="py-3 px-4 text-right text-40k-crimson-bright">{formatNumber(v.likes || 0)}</td>
                          <td className="py-3 px-4 text-right">
                            <span className={`px-2 py-1 rounded text-xs ${
                              (v.engagement_ratio || 0) > 3
                                ? 'bg-green-500/20 text-green-400'
                                : (v.engagement_ratio || 0) > 1
                                ? 'bg-yellow-500/20 text-yellow-400'
                                : 'bg-gray-500/20 text-gray-400'
                            }`}>
                              {(v.engagement_ratio || 0).toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right text-40k-gold">{(v.performance_score || 0).toFixed(1)}</td>
                        </motion.tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}
        </motion.div>
      )}

      {/* TikTok Tab */}
      {activeTab === 'tiktok' && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Total Videos"
              value={tiktokSummary?.total_videos || 0}
              icon={<Video className="w-5 h-5" />}
            />
            <StatCard
              label="Total Views"
              value={formatNumber(tiktokSummary?.total_views || 0)}
              icon={<Eye className="w-5 h-5" />}
            />
            <StatCard
              label="Avg Views"
              value={formatNumber(tiktokSummary?.avg_views || 0)}
              icon={<TrendingUp className="w-5 h-5" />}
            />
            <StatCard
              label="Followers"
              value={tiktokSummary?.current_followers || 0}
              icon={<Users className="w-5 h-5" />}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card hoverable>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-display font-semibold text-white">Daily Views</h3>
                <select
                  value={dailyDays}
                  onChange={(e) => setDailyDays(Number(e.target.value))}
                  className="cyber-input text-sm py-1 px-2"
                >
                  <option value={7}>Last 7 days</option>
                  <option value={30}>Last 30 days</option>
                  <option value={90}>Last 90 days</option>
                </select>
              </div>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={tiktokDailyData}>
                    <defs>
                      <linearGradient id="ttViewsGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ff6b6b" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#ff6b6b" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
                    <XAxis
                      dataKey="metric_date"
                      stroke="#666"
                      tick={{ fill: '#666', fontSize: 10 }}
                      tickFormatter={(v) => v?.slice(5) || v}
                    />
                    <YAxis stroke="#666" tick={{ fill: '#666', fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                    />
                    <Area
                      type="monotone"
                      dataKey="video_views"
                      stroke="#ff6b6b"
                      fillOpacity={1}
                      fill="url(#ttViewsGradient)"
                      name="Views"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>

            <Card hoverable>
              <h3 className="text-lg font-display font-semibold text-white mb-4">Views by Game</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={tiktokGameChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
                    <XAxis dataKey="name" stroke="#666" tick={{ fill: '#666', fontSize: 10 }} />
                    <YAxis stroke="#666" tick={{ fill: '#666', fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                    />
                    <Bar dataKey="views" fill="#ff6b6b" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <Card hoverable>
            <h3 className="text-lg font-display font-semibold text-white mb-4">Audience (New vs Returning)</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={tiktokDailyData}>
                  <defs>
                    <linearGradient id="newGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4ecdc4" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#4ecdc4" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="returningGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#45b7d1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#45b7d1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
                  <XAxis
                    dataKey="metric_date"
                    stroke="#666"
                    tick={{ fill: '#666', fontSize: 10 }}
                    tickFormatter={(v) => v?.slice(5) || v}
                  />
                  <YAxis stroke="#666" tick={{ fill: '#666', fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', borderRadius: '8px' }}
                  />
                  <Legend />
                  <Area type="monotone" dataKey="new_viewers" stackId="1" stroke="#4ecdc4" fillOpacity={1} fill="url(#newGrad)" name="New Viewers" />
                  <Area type="monotone" dataKey="returning_viewers" stackId="1" stroke="#45b7d1" fillOpacity={1} fill="url(#returningGrad)" name="Returning Viewers" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card hoverable>
            <SectionHeader title="All TikTok Videos" icon={<Video className="w-4 h-4" />} terminal />
            <div className="overflow-x-auto mt-4">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-40k-border">
                    <th className="text-left py-3 px-4 text-gray-400 font-medium">Title</th>
                    <th className="text-left py-3 px-4 text-gray-400 font-medium">Game</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">Views</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">Likes</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">Comments</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">Shares</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">Engagement</th>
                    <th className="text-center py-3 px-4 text-gray-400 font-medium">Matched</th>
                  </tr>
                </thead>
                <tbody>
                  {tiktokVideos.map((video: any, i: number) => {
                    const engagement = video.total_views > 0
                      ? ((video.total_likes + video.total_comments + video.total_shares) / video.total_views * 100)
                      : 0
                    return (
                      <motion.tr
                        key={video.id || i}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ delay: i * 0.03 }}
                        className="border-b border-40k-border/50 hover:bg-40k-dark/50"
                      >
                        <td className="py-3 px-4 text-white truncate max-w-xs">
                          <a
                            href={video.tiktok_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-40k-gold transition-colors"
                          >
                            {video.title?.slice(0, 40)}{video.title?.length > 40 ? '...' : ''}
                          </a>
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className="px-2 py-1 rounded text-xs"
                            style={{
                              backgroundColor: `${GAME_COLORS[video.game] || '#8884d8'}20`,
                              color: GAME_COLORS[video.game] || '#8884d8',
                            }}
                          >
                            {formatGameName(video.game || 'unknown')}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-right text-40k-gold">{formatNumber(video.total_views)}</td>
                        <td className="py-3 px-4 text-right text-40k-crimson-bright">{formatNumber(video.total_likes)}</td>
                        <td className="py-3 px-4 text-right text-gray-300">{video.total_comments}</td>
                        <td className="py-3 px-4 text-right text-gray-300">{video.total_shares}</td>
                        <td className="py-3 px-4 text-right">
                          <span className={`px-2 py-1 rounded text-xs ${
                            engagement > 3
                              ? 'bg-green-500/20 text-green-400'
                              : engagement > 1
                              ? 'bg-yellow-500/20 text-yellow-400'
                              : 'bg-gray-500/20 text-gray-400'
                          }`}>
                            {engagement.toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          {video.matched_youtube_id ? (
                            <span className="text-green-400">✓</span>
                          ) : (
                            <span className="text-gray-600">—</span>
                          )}
                        </td>
                      </motion.tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Comparison Tab */}
      {activeTab === 'comparison' && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* YouTube Summary */}
            <Card hoverable>
              <h3 className="text-lg font-display font-semibold text-white mb-4">
                <span className="text-40k-gold">YouTube</span> Shorts
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-4 bg-40k-dark/30 rounded-lg">
                  <p className="text-2xl font-bold text-40k-gold">{crossPlatform?.youtube?.total_videos || 0}</p>
                  <p className="text-sm text-gray-400">Videos</p>
                </div>
                <div className="text-center p-4 bg-40k-dark/30 rounded-lg">
                  <p className="text-2xl font-bold text-40k-gold">{formatNumber(crossPlatform?.youtube?.avg_views || 0)}</p>
                  <p className="text-sm text-gray-400">Avg Views</p>
                </div>
                <div className="text-center p-4 bg-40k-dark/30 rounded-lg">
                  <p className="text-2xl font-bold text-40k-gold">{(crossPlatform?.youtube?.avg_engagement || 0).toFixed(2)}%</p>
                  <p className="text-sm text-gray-400">Avg Engagement</p>
                </div>
                <div className="text-center p-4 bg-40k-dark/30 rounded-lg">
                  <p className="text-2xl font-bold text-40k-gold">{(crossPlatform?.youtube?.avg_performance || 0).toFixed(1)}</p>
                  <p className="text-sm text-gray-400">Avg Score</p>
                </div>
              </div>
            </Card>

            {/* TikTok Summary */}
            <Card hoverable>
              <h3 className="text-lg font-display font-semibold text-white mb-4">
                <span className="text-[#ff0050]">TikTok</span>
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-4 bg-40k-dark/30 rounded-lg">
                  <p className="text-2xl font-bold text-[#ff0050]">{crossPlatform?.tiktok?.total_videos || 0}</p>
                  <p className="text-sm text-gray-400">Videos</p>
                </div>
                <div className="text-center p-4 bg-40k-dark/30 rounded-lg">
                  <p className="text-2xl font-bold text-[#ff0050]">{formatNumber(crossPlatform?.tiktok?.avg_views || 0)}</p>
                  <p className="text-sm text-gray-400">Avg Views</p>
                </div>
                <div className="text-center p-4 bg-40k-dark/30 rounded-lg">
                  <p className="text-2xl font-bold text-[#ff0050]">{(crossPlatform?.tiktok?.avg_engagement || 0).toFixed(2)}%</p>
                  <p className="text-sm text-gray-400">Avg Engagement</p>
                </div>
                <div className="text-center p-4 bg-40k-dark/30 rounded-lg">
                  <p className="text-2xl font-bold text-[#ff0050]">—</p>
                  <p className="text-sm text-gray-400">Avg Score</p>
                </div>
              </div>
            </Card>
          </div>

          {/* Cross-Platform Game Performance */}
          <Card hoverable>
            <h3 className="text-lg font-display font-semibold text-white mb-4">Game Performance by Platform</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-40k-border">
                    <th className="text-left py-3 px-4 text-gray-400 font-medium">Game</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">YT Videos</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">YT Avg Views</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">TT Videos</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">TT Avg Views</th>
                    <th className="text-right py-3 px-4 text-gray-400 font-medium">TT Engagement</th>
                  </tr>
                </thead>
                <tbody>
                  {(crossPlatform?.youtube?.content_types || []).map((ct: any, i: number) => {
                    const gameName = ct.content_type || 'unknown'
                    const ttGame = (crossPlatform?.tiktok_games || []).find(
                      (g: any) => g.game?.toLowerCase() === gameName.toLowerCase()
                    )
                    return (
                      <tr key={i} className="border-b border-40k-border/50 hover:bg-40k-dark/50">
                        <td className="py-3 px-4 text-white capitalize">{formatGameName(gameName)}</td>
                        <td className="py-3 px-4 text-right text-gray-300">{ct.count}</td>
                        <td className="py-3 px-4 text-right text-40k-gold">{formatNumber(ct.avg_views)}</td>
                        <td className="py-3 px-4 text-right text-gray-300">{ttGame?.count || 0}</td>
                        <td className="py-3 px-4 text-right text-[#ff0050]">{formatNumber(ttGame?.avg_views || 0)}</td>
                        <td className="py-3 px-4 text-right">
                          <span className={`px-2 py-1 rounded text-xs ${
                            (ttGame?.avg_engagement || 0) > 3
                              ? 'bg-green-500/20 text-green-400'
                              : (ttGame?.avg_engagement || 0) > 1
                              ? 'bg-yellow-500/20 text-yellow-400'
                              : 'bg-gray-500/20 text-gray-400'
                          }`}>
                            {(ttGame?.avg_engagement || 0).toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                  {(crossPlatform?.tiktok_games || [])
                    .filter((tt: any) => !(crossPlatform?.youtube?.content_types || []).find(
                      (ct: any) => ct.content_type?.toLowerCase() === tt.game?.toLowerCase()
                    ))
                    .map((tt: any, i: number) => (
                      <tr key={`tt-${i}`} className="border-b border-40k-border/50 hover:bg-40k-dark/50">
                        <td className="py-3 px-4 text-white capitalize">{formatGameName(tt.game || 'unknown')}</td>
                        <td className="py-3 px-4 text-right text-gray-600">—</td>
                        <td className="py-3 px-4 text-right text-gray-600">—</td>
                        <td className="py-3 px-4 text-right text-gray-300">{tt.count}</td>
                        <td className="py-3 px-4 text-right text-[#ff0050]">{formatNumber(tt.avg_views)}</td>
                        <td className="py-3 px-4 text-right">
                          <span className={`px-2 py-1 rounded text-xs ${
                            (tt.avg_engagement || 0) > 3
                              ? 'bg-green-500/20 text-green-400'
                              : (tt.avg_engagement || 0) > 1
                              ? 'bg-yellow-500/20 text-yellow-400'
                              : 'bg-gray-500/20 text-gray-400'
                          }`}>
                            {(tt.avg_engagement || 0).toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Learning Integration Info */}
          <Card hoverable>
            <h3 className="text-lg font-display font-semibold text-white mb-4">Cross-Platform Learning</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-40k-dark/30 rounded-lg">
                <h4 className="text-sm font-medium text-40k-gold mb-2">TikTok-Enhanced Retention</h4>
                <p className="text-xs text-gray-400">
                  Clips from games with high TikTok engagement (&gt;3%) get a +5 bonus in the retention adjustment.
                  Low engagement games (&lt;1%) get a -3 penalty.
                </p>
              </div>
              <div className="p-4 bg-40k-dark/30 rounded-lg">
                <h4 className="text-sm font-medium text-40k-gold mb-2">Cross-Platform Scoring</h4>
                <p className="text-xs text-gray-400">
                  Performance scores are now calculated using both YouTube and TikTok metrics when available.
                  The system normalizes both platforms to 0-100 and blends them.
                </p>
              </div>
              <div className="p-4 bg-40k-dark/30 rounded-lg">
                <h4 className="text-sm font-medium text-40k-gold mb-2">Learning Signals</h4>
                <p className="text-xs text-gray-400">
                  TikTok engagement patterns inform which content types perform best.
                  This data feeds into the virality scoring and clip selection process.
                </p>
              </div>
            </div>
          </Card>
        </motion.div>
      )}
    </motion.div>
  )
}
