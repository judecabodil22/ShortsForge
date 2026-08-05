import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Brain, Trash2, RefreshCw } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { getMemPalaceStatus, clearMemPalace, getStatus } from '@/lib/api'
import { useToast } from '@/contexts/ToastContext'

export default function MemPalacePage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const { data: status, isLoading, refetch } = useQuery({
    queryKey: ['mempalace-status'],
    queryFn: getMemPalaceStatus,
  })

  const { data: appStatus } = useQuery({
    queryKey: ['status'],
    queryFn: getStatus,
  })

  const clearMutation = useMutation({
    mutationFn: (game: string) => clearMemPalace(game),
    onSuccess: () => {
      toast('success', 'MemPalace game memory cleared')
      queryClient.invalidateQueries({ queryKey: ['mempalace-status'] })
    },
    onError: (e: Error) => toast('error', e.message),
  })

  const games = status?.games || {}
  const gameEntries = Object.entries(games) as [string, any][]

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-40k-gold">MEM</span>PALACE
          </h1>
          <p className="text-gray-400 mt-1">Persistent game memory (ChromaDB)</p>
        </div>
        <button className="cyber-button flex items-center gap-2" onClick={() => refetch()}>
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <Card>
        <div className="flex items-center gap-3 mb-4">
          <Brain className="w-5 h-5 text-40k-gold" />
          <h2 className="text-lg font-display text-white">Status</h2>
        </div>
        {isLoading ? (
          <p className="text-gray-400">Loading…</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div className="p-3 bg-40k-dark rounded-lg">
              <p className="text-xs text-gray-400 uppercase">Available</p>
              <p className="text-40k-gold text-xl">{status?.available ? 'Yes' : 'No'}</p>
            </div>
            <div className="p-3 bg-40k-dark rounded-lg">
              <p className="text-xs text-gray-400 uppercase">Total drawers</p>
              <p className="text-white text-xl">{status?.total_drawers ?? 0}</p>
            </div>
            <div className="p-3 bg-40k-dark rounded-lg">
              <p className="text-xs text-gray-400 uppercase">Active game</p>
              <p className="text-white text-sm truncate">{appStatus?.game_title || '—'}</p>
            </div>
          </div>
        )}
        {status?.reason && <p className="text-red-400 text-sm mt-3">{status.reason}</p>}
        {status?.error && <p className="text-red-400 text-sm mt-3">{status.error}</p>}
      </Card>

      <Card>
        <h2 className="text-lg font-display text-white mb-4">Game wings</h2>
        {gameEntries.length === 0 ? (
          <p className="text-gray-500 text-sm">No game memory recorded yet. Run Phase 2–4 to mine transcripts.</p>
        ) : (
          <div className="space-y-2">
            {gameEntries.map(([game, info]) => (
              <div key={game} className="flex items-center justify-between p-3 bg-40k-dark rounded-lg">
                <div>
                  <p className="text-white font-medium">{game}</p>
                  <p className="text-xs text-gray-400">
                    {typeof info === 'object' ? JSON.stringify(info) : String(info)}
                  </p>
                </div>
                <button
                  className="cyber-button px-3 py-1 text-xs flex items-center gap-1 text-red-300"
                  onClick={() => {
                    if (confirm(`Clear MemPalace memory for ${game}?`)) clearMutation.mutate(game)
                  }}
                >
                  <Trash2 className="w-3 h-3" /> Clear
                </button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </motion.div>
  )
}
