import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Search, FileText, BarChart2, Sparkles, Tag, Hash, Copy, Check } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { getScripts, getScriptMetadata, analyzeScript } from '@/lib/api'
import { cn } from '@/lib/utils'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export default function Scripts() {
  const [search, setSearch] = useState('')
  const [selectedScript, setSelectedScript] = useState<string | null>(null)
  const [analyzedScript, setAnalyzedScript] = useState<any>(null)
  const [copiedField, setCopiedField] = useState<string | null>(null)

  const { data } = useQuery({
    queryKey: ['scripts'],
    queryFn: getScripts,
  })

  const { data: metadata } = useQuery({
    queryKey: ['script-metadata', selectedScript],
    queryFn: () => getScriptMetadata(selectedScript!),
    enabled: !!selectedScript,
  })

  const scripts = data?.scripts || []

  const filteredScripts = scripts.filter((s: any) => 
    (s.video_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
    (s.content_type ?? '').toLowerCase().includes(search.toLowerCase())
  )

  const handleAnalyze = async (id: string) => {
    try {
      const result = await analyzeScript(id)
      setAnalyzedScript(result)
    } catch (e) {
      console.error('Analysis error:', e)
    }
  }

  const copyToClipboard = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedField(field)
      setTimeout(() => setCopiedField(null), 2000)
    } catch {}
  }

  const thumbnailUrl = (script: any): string | undefined => {
    const videoName = script?.video_name
    if (!videoName) return undefined
    return `${API_BASE}/api/thumbnails/${videoName}-Short1-thumb.jpg`
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
            <span className="text-40k-gold">SCRIPT</span> MANAGER
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
            <FileText className="w-5 h-5 text-40k-gold" />
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
                    'p-4 bg-40k-dark rounded-lg cursor-pointer transition-all hover:border-40k-gold/30 flex gap-3',
                    selectedScript === script.id ? 'border-40k-gold' : 'border-transparent'
                  )}
                  onClick={() => setSelectedScript(script.id)}
                >
                  <img
                    src={thumbnailUrl(script)}
                    alt=""
                    className="w-16 h-24 rounded object-cover flex-shrink-0 bg-40k-darkest"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
                  />
                  <div className="flex-1 min-w-0">
                    <h4 className="font-medium text-white truncate">{script.video_name}</h4>
                    <div className="flex items-center gap-2 mt-2">
                      <span className="px-2 py-0.5 text-xs rounded bg-40k-gold/20 text-40k-gold">
                        {script.content_type || 'Unknown'}
                      </span>
                      <span className="text-xs text-gray-500">
                        {script.created_at?.split('T')[0]}
                      </span>
                    </div>
                    {script.description && (
                      <p className="text-xs text-gray-400 mt-2 line-clamp-2">{script.description}</p>
                    )}
                  </div>
                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={(e) => {
                      e.stopPropagation()
                      handleAnalyze(script.id)
                    }}
                    className="p-2 text-gray-400 hover:text-40k-crimson-bright transition-colors flex-shrink-0"
                  >
                    <Sparkles className="w-4 h-4" />
                  </motion.button>
                </motion.div>
              ))
            )}
          </div>
          </Card>
        </motion.div>

        {/* Script Details / Analysis */}
        <motion.div layout variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card layout hoverable className="h-full">
          {selectedScript && metadata ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-display font-semibold text-white flex items-center gap-2">
                  <FileText className="w-5 h-5 text-40k-gold" />
                  {metadata.title || 'Script Details'}
                </h3>
                <button
                  onClick={() => {
                    const script = scripts.find((s: any) => s.id === selectedScript)
                    if (script) handleAnalyze(script.id)
                  }}
                  className="px-3 py-1 text-xs bg-40k-crimson-bright/20 text-40k-crimson-bright rounded hover:bg-40k-crimson-bright/30 transition-colors"
                >
                  Analyze
                </button>
              </div>

              {/* Description */}
              {metadata.description && (
                <div className="p-3 bg-40k-dark rounded-lg">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs text-gray-400 uppercase tracking-wider">Description</p>
                    <button onClick={() => copyToClipboard(metadata.description, 'desc')} className="text-gray-500 hover:text-40k-gold transition-colors">
                      {copiedField === 'desc' ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                  <p className="text-sm text-gray-300">{metadata.description}</p>
                </div>
              )}

              {/* Hashtags */}
              {metadata.hashtags && (
                <div className="p-3 bg-40k-dark rounded-lg">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs text-gray-400 uppercase tracking-wider flex items-center gap-1">
                      <Hash className="w-3 h-3" /> Hashtags
                    </p>
                    <button onClick={() => copyToClipboard(metadata.hashtags, 'tags')} className="text-gray-500 hover:text-40k-gold transition-colors">
                      {copiedField === 'tags' ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {String(metadata.hashtags).split(',').map((h: string, i: number) => (
                      <span key={i} className="px-2 py-0.5 text-xs bg-40k-gold/10 text-40k-gold rounded">{h.trim()}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Tags */}
              {metadata.tags && (
                <div className="p-3 bg-40k-dark rounded-lg">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs text-gray-400 uppercase tracking-wider flex items-center gap-1">
                      <Tag className="w-3 h-3" /> SEO Tags
                    </p>
                    <button onClick={() => copyToClipboard(metadata.tags, 'seo')} className="text-gray-500 hover:text-40k-gold transition-colors">
                      {copiedField === 'seo' ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {String(metadata.tags).split(',').map((t: string, i: number) => (
                      <span key={i} className="px-2 py-0.5 text-xs bg-40k-darkest text-gray-300 rounded">{t.trim()}</span>
                    ))}
                  </div>
                </div>
              )}

              {analyzedScript && (
                <>
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-display font-semibold text-white flex items-center gap-2 mt-2">
                      <BarChart2 className="w-5 h-5 text-40k-crimson-bright" />
                      NLP Analysis
                    </h3>
                    <div className="px-3 py-1 bg-40k-crimson-bright/20 text-40k-crimson-bright rounded text-sm">
                      Virality: {analyzedScript.virality_prediction?.toFixed(0) || 50}/100
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(analyzedScript.features || {}).slice(0, 12).map(([key, value]) => (
                      <div key={key} className="p-3 bg-40k-dark rounded-lg">
                        <p className="text-xs text-gray-400 capitalize">{key.replace(/_/g, ' ')}</p>
                        <p className="text-lg font-medium text-40k-gold">
                          {typeof value === 'number' ? (Number.isInteger(value) ? value : value.toFixed(1)) : value?.toString() || '-'}
                        </p>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500">
              <Sparkles className="w-12 h-12 mb-4 opacity-30" />
              <p>Select a script to view details</p>
              <p className="text-sm mt-2">description, hashtags, tags, and analysis will appear here</p>
            </div>
          )}
          </Card>
        </motion.div>
      </div>
    </motion.div>
  )
}