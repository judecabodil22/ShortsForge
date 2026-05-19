import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Search, FileText, BarChart2, Sparkles } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { getScripts, analyzeScript } from '@/lib/api'
import { cn } from '@/lib/utils'

export default function Scripts() {
  const [search, setSearch] = useState('')
  const [selectedScript, setSelectedScript] = useState<string | null>(null)
  const [analyzedScript, setAnalyzedScript] = useState<any>(null)

  const { data } = useQuery({
    queryKey: ['scripts'],
    queryFn: getScripts,
  })

  const scripts = data?.scripts || []

  const filteredScripts = scripts.filter((s: any) => 
    s.video_name?.toLowerCase().includes(search.toLowerCase()) ||
    s.content_type?.toLowerCase().includes(search.toLowerCase())
  )

  const handleAnalyze = async (id: string) => {
    try {
      const result = await analyzeScript(id)
      setAnalyzedScript(result)
    } catch (e) {
      console.error('Analysis error:', e)
    }
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
      <motion.div variants={{ hidden: { opacity: 0, y: -20 }, show: { opacity: 1, y: 0 } }} className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-cyber-cyan">SCRIPT</span> MANAGER
          </h1>
          <p className="text-gray-400 mt-1">View and analyze generated scripts</p>
        </div>
      </motion.div>

      {/* Search */}
      <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }} className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500" />
        <input
          type="text"
          placeholder="Search scripts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="cyber-input pl-10"
        />
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Scripts List */}
        <motion.div layout variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card layout hoverable className="max-h-[600px] overflow-y-auto">
          <h3 className="text-lg font-display font-semibold text-white mb-4 flex items-center gap-2">
            <FileText className="w-5 h-5 text-cyber-cyan" />
            Scripts ({filteredScripts.length})
          </h3>

          <div className="space-y-3">
            {filteredScripts.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No scripts found</p>
            ) : (
              filteredScripts.map((script: any) => (
                <motion.div
                  key={script.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className={cn(
                    'p-4 bg-cyber-dark rounded-lg cursor-pointer transition-all hover:border-cyber-cyan/30',
                    selectedScript === script.id ? 'border-cyber-cyan' : 'border-transparent'
                  )}
                  onClick={() => setSelectedScript(script.id)}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-medium text-white">{script.video_name}</h4>
                      <div className="flex items-center gap-2 mt-2">
                        <span className="px-2 py-0.5 text-xs rounded bg-cyber-cyan/20 text-cyber-cyan">
                          {script.content_type || 'Unknown'}
                        </span>
                        <span className="text-xs text-gray-500">
                          {script.created_at?.split('T')[0]}
                        </span>
                      </div>
                    </div>
                    <motion.button
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                      onClick={(e) => {
                        e.stopPropagation()
                        handleAnalyze(script.id)
                      }}
                      className="p-2 text-gray-400 hover:text-cyber-magenta transition-colors"
                    >
                      <Sparkles className="w-4 h-4" />
                    </motion.button>
                  </div>
                </motion.div>
              ))
            )}
          </div>
          </Card>
        </motion.div>

        {/* Script Details / Analysis */}
        <motion.div layout variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card layout hoverable className="h-full">
          {analyzedScript ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-display font-semibold text-white flex items-center gap-2">
                  <BarChart2 className="w-5 h-5 text-cyber-magenta" />
                  NLP Analysis
                </h3>
                <div className="px-3 py-1 bg-cyber-magenta/20 text-cyber-magenta rounded text-sm">
                  Virality: {analyzedScript.virality_prediction?.toFixed(0) || 50}/100
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {Object.entries(analyzedScript.features || {}).slice(0, 12).map(([key, value]) => (
                  <div key={key} className="p-3 bg-cyber-dark rounded-lg">
                    <p className="text-xs text-gray-400 capitalize">{key.replace(/_/g, ' ')}</p>
                    <p className="text-lg font-medium text-cyber-cyan">
                      {typeof value === 'number' ? (Number.isInteger(value) ? value : value.toFixed(1)) : value?.toString() || '-'}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500">
              <Sparkles className="w-12 h-12 mb-4 opacity-30" />
              <p>Select a script and click analyze</p>
              <p className="text-sm mt-2">to see NLP features and virality prediction</p>
            </div>
          )}
          </Card>
        </motion.div>
      </div>
    </motion.div>
  )
}