import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Brain, TrendingUp, BarChart3, TestTube, CheckCircle, Clock, PieChart as PieChartIcon, Video } from 'lucide-react'
import { Card, StatCard } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { getLearningDashboard, getActiveABTests, getTikTokLearningSignals, getCurrentABTest, createABTest } from '@/lib/api'
import { stagger, slideLeft } from '@/lib/animations'
import { formatNumber } from '@/lib/utils'
import { useToast } from '@/contexts/ToastContext'
import { useThemeColors } from '@/hooks/useThemeColors'
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  Tooltip,
} from 'recharts'

function formatContentType(name: string): string {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export default function LearningDashboard() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const colors = useThemeColors()
  const chartPalette = [colors.chart1, colors.chart2, colors.chart3, colors.goldBright, colors.goldDim, colors.bronze, colors.crimsonBright]
  const [abName, setAbName] = useState('Hook Style Test')
  const [abType, setAbType] = useState('hook')

  const { data: dashboard } = useQuery({
    queryKey: ['learning-dashboard'],
    queryFn: getLearningDashboard,
  })

  const createAbMutation = useMutation({
    mutationFn: () => createABTest({
      test_name: abName,
      test_type: abType,
      variant_a: { label: 'Control' },
      variant_b: { label: 'Challenger' },
    }),
    onSuccess: () => {
      toast('success', 'A/B test created')
      queryClient.invalidateQueries({ queryKey: ['ab-tests'] })
      queryClient.invalidateQueries({ queryKey: ['current-ab-test'] })
    },
    onError: (e: Error) => toast('error', e.message),
  })

  const { data: abTests } = useQuery({
    queryKey: ['ab-tests'],
    queryFn: getActiveABTests,
  })

  const { data: tiktokSignals } = useQuery({
    queryKey: ['tiktok-learning-signals'],
    queryFn: getTikTokLearningSignals,
  })

  const { data: currentTest } = useQuery({
    queryKey: ['current-ab-test'],
    queryFn: getCurrentABTest,
  })

  const activeTests = abTests?.active || []
  const testHistory = abTests?.history || []

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{
        hidden: { opacity: 0 },
        show: { opacity: 1, transition: { staggerChildren: 0.1 } }
      }}
    >
      <PageHeader
        accentWord="LEARNING"
        title="LEARNING DASHBOARD"
        subtitle="Self-learning from your own YouTube Shorts performance"
      />

      {/* Stats Overview */}
      <motion.div
        variants={{ ...stagger.container, show: { opacity: 1 } }}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6"
      >
        <StatCard
          label="Learning Status"
          value={dashboard?.insights?.baseline?.status || 'unknown'}
          icon={<Brain className="w-5 h-5" />}
        />
        <StatCard
          label="Active A/B Tests"
          value={activeTests.length.toString()}
          icon={<TestTube className="w-5 h-5" />}
        />
        <StatCard
          label="Completed Tests"
          value={testHistory.length.toString()}
          icon={<CheckCircle className="w-5 h-5" />}
        />
        <StatCard
          label="TikTok Games"
          value={tiktokSignals?.total_games?.toString() || '0'}
          icon={<Video className="w-5 h-5" />}
        />
      </motion.div>

      {/* Learning Insights */}
      <motion.div
        variants={{ ...slideLeft, show: { opacity: 1 } }}
        className="mb-6"
      >
        <Card accent="gold" notch>
          <SectionHeader title="Learning Insights" icon={<TrendingUp className="w-4 h-4" />} terminal />
          <div className="mt-4">
            {dashboard?.insights?.has_insights ? (
              <ul className="space-y-2">
                {dashboard.insights.insights.map((insight: string, i: number) => (
                  <li key={i} className="text-sm text-gray-300 flex items-start gap-2">
                    <span className="text-40k-gold">●</span>
                    {insight}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-400">No insights available yet. Run more pipelines to generate learning data.</p>
            )}
          </div>
        </Card>
      </motion.div>

      {/* Current A/B Test */}
      <motion.div variants={{ ...slideLeft, show: { opacity: 1 } }} className="mb-6">
        <Card>
          <SectionHeader title="Create A/B Test" icon={<TestTube className="w-4 h-4" />} terminal />
          <div className="mt-3 flex flex-wrap gap-2 items-end">
            <div>
              <label className="text-xs text-gray-400">Name</label>
              <input
                value={abName}
                onChange={(e) => setAbName(e.target.value)}
                className="block mt-1 bg-40k-dark border border-40k-border rounded px-2 py-1 text-sm text-white"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400">Type</label>
              <input
                value={abType}
                onChange={(e) => setAbType(e.target.value)}
                className="block mt-1 bg-40k-dark border border-40k-border rounded px-2 py-1 text-sm text-white"
              />
            </div>
            <button
              className="cyber-button px-3 py-1.5 text-xs"
              disabled={createAbMutation.isPending || !abName.trim()}
              onClick={() => createAbMutation.mutate()}
            >
              Create
            </button>
          </div>
        </Card>
      </motion.div>

      {currentTest && currentTest.id && (
        <motion.div
          variants={{ ...slideLeft, show: { opacity: 1 } }}
          className="mb-6"
        >
          <Card accent="gold" notch>
            <SectionHeader title="Current A/B Test" icon={<TestTube className="w-4 h-4" />} terminal />
            <div className="mt-4">
              <div className="flex items-center gap-2 mb-3">
                <Clock className="w-4 h-4 text-40k-gold" />
                <span className="text-sm text-gray-400">Running</span>
                <span className="text-xs text-gray-500">•</span>
                <span className="text-xs text-gray-500">Created {new Date(currentTest.created_at).toLocaleDateString()}</span>
              </div>
              
              <h4 className="text-white font-medium mb-2">{currentTest.test_name}</h4>
              <p className="text-xs text-gray-400 mb-4">Type: {currentTest.test_type}</p>
              
              {/* Variant Comparison */}
              <div className="grid grid-cols-2 gap-4">
                {/* Variant A */}
                <div className="p-3 bg-40k-dark rounded border border-40k-border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-40k-gold">Variant A</span>
                    <span className="text-xs text-gray-400">{currentTest.scripts_a || 0} scripts</span>
                  </div>
                  <p className="text-sm text-white mb-1">{currentTest.variant_a?.label || 'N/A'}</p>
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <span>Samples: {currentTest.samples_a}</span>
                    <span>•</span>
                    <span>Avg: {currentTest.avg_performance_a?.toFixed(1) || '0'}</span>
                  </div>
                </div>
                
                {/* Variant B */}
                <div className="p-3 bg-40k-dark rounded border border-40k-border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-40k-crimson-bright">Variant B</span>
                    <span className="text-xs text-gray-400">{currentTest.scripts_b || 0} scripts</span>
                  </div>
                  <p className="text-sm text-white mb-1">{currentTest.variant_b?.label || 'N/A'}</p>
                  <div className="flex items-center gap-2 text-xs text-gray-400">
                    <span>Samples: {currentTest.samples_b}</span>
                    <span>•</span>
                    <span>Avg: {currentTest.avg_performance_b?.toFixed(1) || '0'}</span>
                  </div>
                </div>
              </div>
              
              <p className="text-xs text-gray-500 mt-3">
                Pipeline automatically assigns scripts to variants (even/odd round-robin).
                Results are recorded when YouTube metrics are fetched.
              </p>
            </div>
          </Card>
        </motion.div>
      )}

      {/* TikTok Learning Signals */}
      <motion.div
        variants={{ ...slideLeft, show: { opacity: 1 } }}
        className="mb-6"
      >
        <Card accent="crimson" notch>
          <SectionHeader title="TikTok Learning Signals" icon={<Video className="w-4 h-4" />} terminal />
          <div className="mt-4">
            {tiktokSignals?.games && tiktokSignals.games.length > 0 ? (
              <>
                {/* Summary */}
                <div className="grid grid-cols-3 gap-4 mb-4">
                  <div className="text-center p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                    <p className="text-2xl font-bold text-green-400">{tiktokSignals.bonus_games}</p>
                    <p className="text-xs text-gray-400">Bonus Games (+5)</p>
                  </div>
                  <div className="text-center p-3 bg-gray-500/10 rounded-lg border border-gray-500/20">
                    <p className="text-2xl font-bold text-gray-400">{tiktokSignals.neutral_games}</p>
                    <p className="text-xs text-gray-400">Neutral</p>
                  </div>
                  <div className="text-center p-3 bg-red-500/10 rounded-lg border border-red-500/20">
                    <p className="text-2xl font-bold text-red-400">{tiktokSignals.penalty_games}</p>
                    <p className="text-xs text-gray-400">Penalty Games (-3)</p>
                  </div>
                </div>

                {/* Game Details */}
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-40k-border">
                        <th className="text-left py-2 px-3 text-gray-400 font-medium text-sm">Game</th>
                        <th className="text-right py-2 px-3 text-gray-400 font-medium text-sm">Videos</th>
                        <th className="text-right py-2 px-3 text-gray-400 font-medium text-sm">Avg Views</th>
                        <th className="text-right py-2 px-3 text-gray-400 font-medium text-sm">Engagement</th>
                        <th className="text-right py-2 px-3 text-gray-400 font-medium text-sm">Score Effect</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tiktokSignals.games.map((game: any, i: number) => (
                        <tr key={i} className="border-b border-40k-border/50 hover:bg-40k-dark/50">
                          <td className="py-2 px-3 text-white capitalize">
                            {game.game.replace(/_/g, ' ')}
                          </td>
                          <td className="py-2 px-3 text-right text-gray-300">{game.video_count}</td>
                          <td className="py-2 px-3 text-right text-gray-300">{formatNumber(game.avg_views)}</td>
                          <td className="py-2 px-3 text-right">
                            <span className={`px-2 py-0.5 rounded text-xs ${
                              game.engagement_ratio > 3
                                ? 'bg-green-500/20 text-green-400'
                                : game.engagement_ratio > 1
                                ? 'bg-yellow-500/20 text-yellow-400'
                                : 'bg-gray-500/20 text-gray-400'
                            }`}>
                              {game.engagement_ratio.toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-2 px-3 text-right">
                            <span className={`font-medium ${
                              game.score_effect > 0
                                ? 'text-green-400'
                                : game.score_effect < 0
                                ? 'text-red-400'
                                : 'text-gray-400'
                            }`}>
                              {game.score_effect > 0 ? '+' : ''}{game.score_effect}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <p className="text-xs text-gray-500 mt-3">
                  TikTok engagement data feeds into <code className="text-40k-gold">retention_adjustment()</code>.
                  Games with &gt;3% engagement get a +5 bonus; &lt;1% get a -3 penalty.
                </p>
              </>
            ) : (
              <p className="text-sm text-gray-400">No TikTok data imported yet. Import TikTok analytics to enable cross-platform learning.</p>
            )}
          </div>
        </Card>
      </motion.div>

      {/* Content Type Effectiveness */}
      <motion.div
        variants={{ ...slideLeft, show: { opacity: 1 } }}
        className="mb-6"
      >
        <Card accent="crimson" notch>
          <SectionHeader title="Content Type Effectiveness" icon={<PieChartIcon className="w-4 h-4" />} terminal />
          <div className="h-64 mt-4">
            {dashboard?.content_effectiveness && Object.keys(dashboard.content_effectiveness).length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={Object.entries(dashboard.content_effectiveness).map(([name, data]: [string, any]) => ({
                      name,
                      value: data.avg_relative_score || 0,
                    }))}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    fill={colors.chart1}
                    dataKey="value"
                    label={({ name, percent }: any) => `${formatContentType(name)}: ${(percent * 100).toFixed(0)}%`}
                  >
                    {Object.entries(dashboard.content_effectiveness).map(([_, __], i) => (
                      <Cell key={`cell-${i}`} fill={chartPalette[i % chartPalette.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-gray-400">No content type data yet.</p>
            )}
          </div>
        </Card>
      </motion.div>

      {/* Active A/B Tests */}
      <motion.div
        variants={{ ...slideLeft, show: { opacity: 1 } }}
        className="mb-6"
      >
        <Card accent="gold" notch>
          <SectionHeader title="Active A/B Tests" icon={<TestTube className="w-4 h-4" />} terminal />
          <div className="mt-4">
            {activeTests.length > 0 ? (
              <div className="space-y-3">
                {activeTests.map((test: any) => (
                  <div key={test.id} className="p-3 bg-40k-dark rounded border border-40k-border">
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="text-white font-medium">{test.test_name}</h4>
                        <p className="text-xs text-gray-400">Type: {test.test_type}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-40k-gold" />
                        <span className="text-xs text-gray-400">Running</span>
                      </div>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-xs text-gray-400">Variant A</span>
                        <div className="text-sm text-white">
                          Samples: {test.samples_a}, Avg: {test.avg_performance_a?.toFixed(1) || '0'}
                        </div>
                      </div>
                      <div>
                        <span className="text-xs text-gray-400">Variant B</span>
                        <div className="text-sm text-white">
                          Samples: {test.samples_b}, Avg: {test.avg_performance_b?.toFixed(1) || '0'}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">No active A/B tests. The system automatically creates tests as you run the pipeline and collect performance data.</p>
            )}
          </div>
        </Card>
      </motion.div>

      {/* A/B Test History */}
      <motion.div
        variants={{ ...slideLeft, show: { opacity: 1 } }}
        className="mb-6"
      >
        <Card accent="crimson" notch>
          <SectionHeader title="A/B Test History" icon={<BarChart3 className="w-4 h-4" />} terminal />
          <div className="mt-4">
            {testHistory.length > 0 ? (
              <div className="space-y-3">
                {testHistory.map((test: any) => (
                  <div key={test.id} className="p-3 bg-40k-dark rounded border border-40k-border flex justify-between items-center">
                    <div>
                      <h4 className="text-white font-medium">{test.test_name}</h4>
                      <p className="text-xs text-gray-400">Type: {test.test_type}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {test.winner === 'a' ? (
                        <>
                          <CheckCircle className="w-4 h-4 text-40k-gold" />
                          <span className="text-xs text-40k-gold">Variant A won</span>
                        </>
                      ) : test.winner === 'b' ? (
                        <>
                          <CheckCircle className="w-4 h-4 text-40k-gold" />
                          <span className="text-xs text-40k-gold">Variant B won</span>
                        </>
                      ) : (
                        <span className="text-xs text-gray-400">Tie/Unknown</span>
                      )}
                      <span className="text-xs text-gray-400">
                        Confidence: {(test.confidence_score || 0).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">No completed A/B tests yet.</p>
            )}
          </div>
        </Card>
      </motion.div>
    </motion.div>
  )
}
