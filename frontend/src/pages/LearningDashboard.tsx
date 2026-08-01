import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Brain, TrendingUp, BarChart3, TestTube, CheckCircle, Clock } from 'lucide-react'
import { Card, StatCard } from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { getLearningDashboard, getActiveABTests } from '@/lib/api'
import { stagger, slideLeft } from '@/lib/animations'
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  Tooltip,
} from 'recharts'

const EMOTION_COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE']

export default function LearningDashboard() {
  const { data: dashboard } = useQuery({
    queryKey: ['learning-dashboard'],
    queryFn: getLearningDashboard,
  })

  const { data: abTests } = useQuery({
    queryKey: ['ab-tests'],
    queryFn: getActiveABTests,
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
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-display font-bold text-white">Learning Dashboard</h1>
        <div className="text-sm text-gray-400">
          Self-learning from your own YouTube Shorts performance
        </div>
      </div>

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
          label="Content Types"
          value={Object.keys(dashboard?.content_effectiveness || {}).length.toString()}
          icon={<BarChart3 className="w-5 h-5" />}
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

      {/* Content Type Effectiveness */}
      <motion.div
        variants={{ ...slideLeft, show: { opacity: 1 } }}
        className="mb-6"
      >
        <Card accent="crimson" notch>
          <SectionHeader title="Content Type Effectiveness" icon={<PieChart className="w-4 h-4" />} terminal />
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
                    fill="#8884d8"
                    dataKey="value"
                    label={({ name, percent }: any) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  >
                    {Object.entries(dashboard.content_effectiveness).map(([_, __], i) => (
                      <Cell key={`cell-${i}`} fill={EMOTION_COLORS[i % EMOTION_COLORS.length]} />
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
              <p className="text-sm text-gray-400">No active A/B tests. Create one from the Scripts page!</p>
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
