import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Video, Eye, Users, TrendingUp, Download,
  RefreshCw, BarChart3,
} from 'lucide-react'
import { Card, StatCard } from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import {
  getTikTokSummary,
  getTikTokVideos,
  getTikTokDaily,
  getTikTokGames,
  importTikTokData,
  matchTikTokToLocal,
} from '@/lib/api'
import { formatNumber } from '@/lib/utils'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
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

export default function TikTokAnalytics() {
  const queryClient = useQueryClient()
  const [dailyDays, setDailyDays] = useState(30)

  const { data: summary } = useQuery({
    queryKey: ['tiktok-summary'],
    queryFn: getTikTokSummary,
  })

  const { data: videosData } = useQuery({
    queryKey: ['tiktok-videos'],
    queryFn: getTikTokVideos,
  })

  const { data: dailyData } = useQuery({
    queryKey: ['tiktok-daily', dailyDays],
    queryFn: () => getTikTokDaily(dailyDays),
  })

  const { data: gamesData } = useQuery({
    queryKey: ['tiktok-games'],
    queryFn: getTikTokGames,
  })

  const importMutation = useMutation({
    mutationFn: importTikTokData,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tiktok-summary'] })
      queryClient.invalidateQueries({ queryKey: ['tiktok-videos'] })
      queryClient.invalidateQueries({ queryKey: ['tiktok-daily'] })
      queryClient.invalidateQueries({ queryKey: ['tiktok-games'] })
    },
  })

  const matchMutation = useMutation({
    mutationFn: matchTikTokToLocal,
  })

  const videos = videosData?.videos || []
  const daily = dailyData?.daily || []
  const games = gamesData?.games || {}

  // Prepare game chart data
  const gameChartData = Object.entries(games).map(([game, stats]: [string, any]) => ({
    name: formatGameName(game),
    views: stats.total_views,
    videos: stats.video_count,
    color: GAME_COLORS[game] || '#8884d8',
  }))

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{
        hidden: { opacity: 0 },
        show: { opacity: 1, transition: { staggerChildren: 0.1 } }
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
            <span className="text-40k-gold">TIKTOK</span> ANALYTICS
          </h1>
          <p className="text-gray-400 mt-1">Track TikTok performance and cross-platform metrics</p>
        </div>
        <div className="flex gap-2">
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
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="cyber-button flex items-center gap-2"
            onClick={() => window.location.reload()}
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </motion.button>
        </div>
      </motion.div>

      {/* Stats Cards */}
      <motion.div
        variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <StatCard
          label="Total Videos"
          value={summary?.total_videos || 0}
          icon={<Video className="w-5 h-5" />}
        />
        <StatCard
          label="Total Views"
          value={formatNumber(summary?.total_views || 0)}
          icon={<Eye className="w-5 h-5" />}
        />
        <StatCard
          label="Avg Views"
          value={formatNumber(summary?.avg_views || 0)}
          icon={<TrendingUp className="w-5 h-5" />}
        />
        <StatCard
          label="Followers"
          value={summary?.current_followers || 0}
          icon={<Users className="w-5 h-5" />}
        />
      </motion.div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Daily Trend Chart */}
        <motion.div
          variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}
        >
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
                <AreaChart data={daily}>
                  <defs>
                    <linearGradient id="viewsGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ff6b6b" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#ff6b6b" stopOpacity={0}/>
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
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #2a2a3e',
                      borderRadius: '8px'
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="video_views"
                    stroke="#ff6b6b"
                    fillOpacity={1}
                    fill="url(#viewsGradient)"
                    name="Views"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </motion.div>

        {/* Game Performance Chart */}
        <motion.div
          variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}
        >
          <Card hoverable>
            <h3 className="text-lg font-display font-semibold text-white mb-4">Views by Game</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={gameChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
                  <XAxis dataKey="name" stroke="#666" tick={{ fill: '#666', fontSize: 10 }} />
                  <YAxis stroke="#666" tick={{ fill: '#666', fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1a2e',
                      border: '1px solid #2a2a3e',
                      borderRadius: '8px'
                    }}
                  />
                  <Bar dataKey="views" fill="#ff6b6b" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Audience Chart */}
      <motion.div
        variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}
      >
        <Card hoverable>
          <h3 className="text-lg font-display font-semibold text-white mb-4">Audience (New vs Returning)</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={daily}>
                <defs>
                  <linearGradient id="newGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4ecdc4" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#4ecdc4" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="returningGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#45b7d1" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#45b7d1" stopOpacity={0}/>
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
                  contentStyle={{
                    backgroundColor: '#1a1a2e',
                    border: '1px solid #2a2a3e',
                    borderRadius: '8px'
                  }}
                />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="new_viewers"
                  stackId="1"
                  stroke="#4ecdc4"
                  fillOpacity={1}
                  fill="url(#newGradient)"
                  name="New Viewers"
                />
                <Area
                  type="monotone"
                  dataKey="returning_viewers"
                  stackId="1"
                  stroke="#45b7d1"
                  fillOpacity={1}
                  fill="url(#returningGradient)"
                  name="Returning Viewers"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </motion.div>

      {/* Videos Table */}
      <motion.div
        variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}
      >
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
                {videos.map((video: any, i: number) => {
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
    </motion.div>
  )
}
