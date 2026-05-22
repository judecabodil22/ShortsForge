import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { RefreshCw, TrendingUp, Eye, Heart, MessageCircle } from 'lucide-react'
import { Card, StatCard } from '@/components/ui/Card'
import { getMetricsSummary, getVideoMetrics, getContentPerformance } from '@/lib/api'
import { formatNumber } from '@/lib/utils'
import { AnimatedCounter } from '@/components/ui/AnimatedCounter'
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

export default function Metrics() {
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

  const baseline = summary?.baseline || {}

  // Deduplicate by youtube_id — keep the latest metrics row per video
  const seenIds = new Set<string>()
  const uniqueVideos = (videos?.videos || [])
    .sort((a: any, b: any) => (b.created_at || '').localeCompare(a.created_at || ''))
    .filter((v: any) => {
      if (seenIds.has(v.youtube_id)) return false
      seenIds.add(v.youtube_id)
      return true
    })

  // Prepare chart data
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
      <motion.div variants={{ hidden: { opacity: 0, y: -20 }, show: { opacity: 1, y: 0 } }} className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-40k-gold">PERFORMANCE</span> METRICS
          </h1>
          <p className="text-gray-400 mt-1">Track video performance and analytics</p>
        </div>

        <motion.button 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="cyber-button flex items-center gap-2"
          onClick={() => window.location.reload()}
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </motion.button>
      </motion.div>

      {/* Quick Stats */}
      <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }} className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard
          label="Total Videos"
          value={<AnimatedCounter value={summary?.total_videos || 0} />}
          icon={<Eye className="w-6 h-6" />}
        />
        <StatCard
          label="Avg Views"
          value={<AnimatedCounter value={baseline.avg_views || 0} format={(v) => formatNumber(v)} />}
          icon={<TrendingUp className="w-6 h-6" />}
          trend={{ value: 8, positive: true }}
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
      </motion.div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Views Chart */}
        <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card hoverable>
          <h3 className="text-lg font-display font-semibold text-white mb-4">Top Videos - Views</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={videoData}>
                <defs>
                  <linearGradient id="viewsGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00fff5" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#00fff5" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
                <XAxis 
                  dataKey="name" 
                  stroke="#666" 
                  tick={{ fill: '#666', fontSize: 10 }}
                  angle={-45}
                  textAnchor="end"
                  height={60}
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
                  dataKey="views" 
                  stroke="#00fff5" 
                  fillOpacity={1} 
                  fill="url(#viewsGradient)" 
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          </Card>
        </motion.div>

        {/* Content Type Performance */}
        <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card hoverable>
          <h3 className="text-lg font-display font-semibold text-white mb-4">Content Type Performance</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={contentData}>
                <defs>
                  <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff00ff" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#ff00ff" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
                <XAxis 
                  dataKey="name" 
                  stroke="#666"
                  tick={{ fill: '#666', fontSize: 10 }}
                />
                <YAxis stroke="#666" tick={{ fill: '#666', fontSize: 10 }} />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1a1a2e', 
                    border: '1px solid #2a2a3e',
                    borderRadius: '8px'
                  }}
                />
                <Bar 
                  dataKey="score" 
                  fill="#ff00ff" 
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
          </Card>
        </motion.div>
      </div>

      {/* Video Table */}
      <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
        <Card hoverable>
        <h3 className="text-lg font-display font-semibold text-white mb-4">Recent Videos</h3>
        <div className="overflow-x-auto">
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
              {uniqueVideos.slice(0, 10).map((video: any, i: number) => (
                <motion.tr
                  key={video.id || i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.05 }}
                  className="border-b border-40k-border/50 hover:bg-40k-dark/50"
                >
                  <td className="py-3 px-4 text-white truncate max-w-xs">{video.title}</td>
                  <td className="py-3 px-4 text-right text-40k-gold">{formatNumber(video.views || 0)}</td>
                  <td className="py-3 px-4 text-right text-40k-crimson-bright">{formatNumber(video.likes || 0)}</td>
                  <td className="py-3 px-4 text-right text-40k-gold-bright">{(video.engagement_ratio || 0).toFixed(2)}%</td>
                  <td className="py-3 px-4 text-right">
                    <span className={`px-2 py-1 rounded text-xs ${
                      video.performance_score > 50
                        ? 'bg-40k-gold-dim/20 text-40k-gold-dim'
                        : 'bg-40k-bronze/20 text-40k-bronze'
                    }`}>
                      {(video.performance_score || 0).toFixed(0)}
                    </span>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
        </Card>
      </motion.div>
    </motion.div>
  )
}