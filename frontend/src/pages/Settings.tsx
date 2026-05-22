import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, Trash2, RefreshCw, Settings as SettingsIcon, Server, Cpu } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { getConfig, updateConfig, cleanupFiles, restartListener, getGames } from '@/lib/api'

export default function Settings() {
  const queryClient = useQueryClient()
  const [formData, setFormData] = useState({
    GAME_TITLE: '',
    TTS_VOICE: '',
    CLIPS_PER_HOUR: '',
    PARENT_FRANCHISE: ''
  })
  
  const [isFranchise, setIsFranchise] = useState(false)

  const { data: gamesData } = useQuery({
    queryKey: ['games'],
    queryFn: getGames,
  })

  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
  })

  useEffect(() => {
    if (config) {
      setFormData({
        GAME_TITLE: config.GAME_TITLE || '',
        TTS_VOICE: config.TTS_VOICE || '',
        CLIPS_PER_HOUR: config.CLIPS_PER_HOUR || '',
        PARENT_FRANCHISE: config.PARENT_FRANCHISE || ''
      })
      if (config.PARENT_FRANCHISE) {
        setIsFranchise(true)
      }
    }
  }, [config])

  const saveMutation = useMutation({
    mutationFn: (data: typeof formData) => updateConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
      alert('Configuration saved successfully!')
    },
    onError: (error: Error) => alert(`Failed to save config: ${error.message}`)
  })

  const cleanupMutation = useMutation({
    mutationFn: cleanupFiles,
    onSuccess: () => alert('Files cleaned up successfully!'),
    onError: (error: Error) => alert(`Failed to cleanup files: ${error.message}`)
  })

  const restartMutation = useMutation({
    mutationFn: restartListener,
    onSuccess: () => alert('Listener restarted successfully!'),
    onError: (error: Error) => alert(`Failed to restart listener: ${error.message}`)
  })

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault()
    const finalData = { ...formData }
    if (!isFranchise) {
      finalData.PARENT_FRANCHISE = ''
    }
    saveMutation.mutate(finalData)
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
        <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-40k-gold">SYSTEM</span> SETTINGS
          </h1>
          <p className="text-gray-400 mt-1">Configure ShortsForge core parameters</p>
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card hoverable className="h-full">
            <h3 className="text-lg font-display font-semibold text-white mb-6 flex items-center gap-2">
              <SettingsIcon className="w-5 h-5 text-40k-gold" />
              Environment Configuration
            </h3>

            {isLoading ? (
              <div className="text-gray-400 animate-pulse">Loading configuration...</div>
            ) : (
              <form onSubmit={handleSave} className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Target Game Title</label>
                  <input
                    type="text"
                    value={formData.GAME_TITLE}
                    onChange={e => setFormData({ ...formData, GAME_TITLE: e.target.value })}
                    className="w-full bg-40k-dark border border-40k-border rounded px-3 py-2 text-white focus:border-40k-gold focus:outline-none"
                    placeholder="e.g. Cyberpunk 2077"
                  />
                </div>
                
                <div className="pt-2 pb-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input 
                      type="checkbox" 
                      checked={isFranchise}
                      onChange={(e) => setIsFranchise(e.target.checked)}
                      className="form-checkbox h-4 w-4 text-40k-gold bg-40k-dark border-40k-border rounded"
                    />
                    <span className="text-sm text-gray-300">Is this game part of a Franchise/Series?</span>
                  </label>
                </div>
                
                {isFranchise && (
                  <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>
                    <label className="block text-sm text-40k-gold mb-1">Parent Franchise Context</label>
                    <select
                      value={formData.PARENT_FRANCHISE}
                      onChange={e => setFormData({ ...formData, PARENT_FRANCHISE: e.target.value })}
                      className="w-full bg-40k-dark border border-40k-gold/50 rounded px-3 py-2 text-white focus:border-40k-gold focus:outline-none appearance-none"
                    >
                      <option value="">Select a Franchise Context...</option>
                      {(gamesData?.games || []).map((game: any) => (
                        <option key={game.name} value={game.name}>{game.display_name || game.name}</option>
                      ))}
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                      If selected, this game will read from and write to the Franchise context.
                    </p>
                  </motion.div>
                )}
                <div>
                  <label className="block text-sm text-gray-400 mb-1">TTS Voice Model</label>
                  <select
                    value={formData.TTS_VOICE}
                    onChange={e => setFormData({ ...formData, TTS_VOICE: e.target.value })}
                    className="w-full bg-40k-dark border border-40k-border rounded px-3 py-2 text-white focus:border-40k-gold focus:outline-none appearance-none"
                  >
                    <option value="">Select a voice...</option>
                    {["Vindemiatrix", "Puck", "Aoede", "Charon", "Kore", "Fenrir", "Orus", "Enceladus", "Iapetus", "Nereus", "Zephyr", "Atlas", "Callirhoe", "Ceres"].map(voice => (
                      <option key={voice} value={voice}>{voice}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Target Clips Per Hour</label>
                  <input
                    type="text"
                    value={formData.CLIPS_PER_HOUR}
                    onChange={e => setFormData({ ...formData, CLIPS_PER_HOUR: e.target.value })}
                    className="w-full bg-40k-dark border border-40k-border rounded px-3 py-2 text-white focus:border-40k-gold focus:outline-none"
                    placeholder="e.g. 1"
                  />
                </div>

                <div className="pt-4">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    type="submit"
                    disabled={saveMutation.isPending}
                    className="cyber-button-primary flex items-center gap-2 w-full justify-center"
                  >
                    <Save className="w-4 h-4" />
                    {saveMutation.isPending ? 'Saving...' : 'Save Configuration'}
                  </motion.button>
                </div>
              </form>
            )}
          </Card>
        </motion.div>

        <motion.div variants={{ hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }}>
          <Card hoverable className="h-full">
            <h3 className="text-lg font-display font-semibold text-white mb-6 flex items-center gap-2">
              <Server className="w-5 h-5 text-40k-gold" />
              System Tools
            </h3>

            <div className="space-y-4">
              <div className="p-4 bg-40k-dark rounded-lg border border-40k-border">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h4 className="text-white font-medium">Cleanup Generated Files</h4>
                    <p className="text-sm text-gray-400">Deletes media, shorts, TTS, and transcripts. Keeps scripts.</p>
                  </div>
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => {
                      if (window.confirm('Are you sure you want to delete generated files?')) {
                        cleanupMutation.mutate()
                      }
                    }}
                    disabled={cleanupMutation.isPending}
                    className="cyber-button flex items-center gap-2 text-40k-red-bright border-40k-red-bright/50 hover:bg-40k-red-bright/10"
                  >
                    <Trash2 className="w-4 h-4" />
                    {cleanupMutation.isPending ? 'Cleaning...' : 'Cleanup'}
                  </motion.button>
                </div>
              </div>

              <div className="p-4 bg-40k-dark rounded-lg border border-40k-border">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h4 className="text-white font-medium">Restart Telegram Listener</h4>
                    <p className="text-sm text-gray-400">Restarts the background listener process.</p>
                  </div>
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => restartMutation.mutate()}
                    disabled={restartMutation.isPending}
                    className="cyber-button flex items-center gap-2 text-40k-gold-bright border-40k-gold-bright/50 hover:bg-40k-gold-bright/10"
                  >
                    <RefreshCw className={`w-4 h-4 ${restartMutation.isPending ? 'animate-spin' : ''}`} />
                    {restartMutation.isPending ? 'Restarting...' : 'Restart'}
                  </motion.button>
                </div>
              </div>

              <div className="mt-8 p-4 bg-40k-gold/10 rounded-lg border border-40k-gold/30 flex items-center gap-4">
                <Cpu className="w-8 h-8 text-40k-gold" />
                <div>
                  <h4 className="text-white font-display font-bold">ShortsForge v2.0.0</h4>
                  <p className="text-xs text-40k-gold">Cyberpunk Edition • System Online</p>
                </div>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>
    </motion.div>
  )
}
