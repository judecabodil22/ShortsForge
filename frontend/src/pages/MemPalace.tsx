import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, useReducedMotion } from 'framer-motion'
import { Brain, Trash2, RefreshCw, Database, Layers } from 'lucide-react'
import { Card, StatCard } from '@/components/ui/Card'
import { PageHeader } from '@/components/ui/PageHeader'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { getMemPalaceStatus, clearMemPalace, getStatus } from '@/lib/api'
import { useToast } from '@/contexts/ToastContext'
import { stagger, motionSafe, fadeUp } from '@/lib/animations'

export default function MemPalacePage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const reduced = useReducedMotion()

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
    <motion.div
      variants={motionSafe(stagger.container, reduced)}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <PageHeader
        accentWord="MEM"
        title="MEMPALACE"
        subtitle="Persistent game memory (ChromaDB)"
        actions={
          <button type="button" className="cyber-button flex items-center gap-2" onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        }
      />

      <motion.div
        variants={motionSafe(stagger.container, reduced)}
        className="grid grid-cols-1 sm:grid-cols-3 gap-4"
      >
        <StatCard
          label="Available"
          value={isLoading ? '…' : status?.available ? 'Yes' : 'No'}
          icon={<Brain className="w-5 h-5" />}
          delay={0}
        />
        <StatCard
          label="Total drawers"
          value={isLoading ? '…' : status?.total_drawers ?? 0}
          icon={<Layers className="w-5 h-5" />}
          delay={0.05}
        />
        <StatCard
          label="Active game"
          value={appStatus?.game_title || '—'}
          icon={<Database className="w-5 h-5" />}
          delay={0.1}
        />
      </motion.div>

      {(status?.reason || status?.error) && (
        <Card accent="crimson" notch>
          {status?.reason && <p className="text-40k-crimson-bright text-sm">{status.reason}</p>}
          {status?.error && <p className="text-40k-crimson-bright text-sm mt-1">{status.error}</p>}
        </Card>
      )}

      <motion.div variants={motionSafe(fadeUp, reduced)}>
        <Card accent notch>
          <SectionHeader title="Game wings" subtitle="Memory partitioned by game" icon={<Brain className="w-4 h-4" />} terminal />
          {gameEntries.length === 0 ? (
            <p className="text-stone-500 text-sm">No game memory recorded yet. Run Phase 2–4 to mine transcripts.</p>
          ) : (
            <div className="space-y-2 mt-2">
              {gameEntries.map(([game, info], i) => (
                <motion.div
                  key={game}
                  variants={motionSafe(fadeUp, reduced)}
                  initial="hidden"
                  animate="show"
                  transition={{ delay: i * 0.04 }}
                  className="flex items-center justify-between p-3 bg-40k-dark border border-40k-border corner-notch hover:border-40k-gold/40 transition-colors"
                >
                  <div>
                    <p className="text-white font-medium font-display tracking-wide">{game}</p>
                    <p className="text-xs text-stone-500 font-mono mt-0.5">
                      {typeof info === 'object' ? JSON.stringify(info) : String(info)}
                    </p>
                  </div>
                  <button
                    type="button"
                    className="cyber-button px-3 py-1 text-xs flex items-center gap-1 text-40k-crimson-bright border-40k-crimson/40"
                    onClick={() => {
                      if (confirm(`Clear MemPalace memory for ${game}?`)) clearMutation.mutate(game)
                    }}
                  >
                    <Trash2 className="w-3 h-3" /> Clear
                  </button>
                </motion.div>
              ))}
            </div>
          )}
        </Card>
      </motion.div>
    </motion.div>
  )
}
