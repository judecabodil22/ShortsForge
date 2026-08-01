import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Search, Users, MapPin, BookOpen, Link2, Pencil, Trash2, X, Save, Gamepad2, Database, Layers, CheckCircle2, ShieldCheck } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { getGames, getGameContext, updateContextItem, deleteContextItem, clearContext, createGameContext, getStatus } from '@/lib/api'
import { stagger, slideLeft } from '@/lib/animations'

const TYPE_CONFIG = {
  character: { icon: Users, color: 'text-40k-gold', bg: 'bg-40k-gold/20' },
  location: { icon: MapPin, color: 'text-40k-gold-dim', bg: 'bg-40k-gold-dim/20' },
  term: { icon: BookOpen, color: 'text-40k-gold-bright', bg: 'bg-40k-gold-bright/20' },
  relationship: { icon: Link2, color: 'text-40k-crimson-bright', bg: 'bg-40k-crimson-bright/20' },
  game: { icon: Gamepad2, color: 'text-40k-gold-bright', bg: 'bg-40k-gold-bright/20' },
}

interface ContextItem {
  id: string
  name: string
  type: string
  description?: string
  category?: string
  metadata?: Record<string, any>
  verified?: boolean
}

interface GameEntry {
  name: string
  is_series: boolean
  display_name: string
  children: string[]
}

export default function Context() {
  const queryClient = useQueryClient()
  const [selectedFranchise, setSelectedFranchise] = useState<string>('')
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState<'all' | 'character' | 'location' | 'term' | 'relationship'>('all')
  const [editingItem, setEditingItem] = useState<ContextItem | null>(null)
  const [editForm, setEditForm] = useState({ name: '', description: '', category: '' })
  
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createGameName, setCreateGameName] = useState('')

  // Get status to find auto-detected franchise
  const { data: status } = useQuery({
    queryKey: ['status'],
    queryFn: getStatus,
  })

  // Auto-select franchise on mount
  const { data: games } = useQuery({
    queryKey: ['games'],
    queryFn: getGames,
  })

  useEffect(() => {
    if (selectedFranchise) return // Already selected, don't override
    if (!games?.games?.length) return // No games loaded
    
    // Find first series or first game
    const series = games.games.find((g: GameEntry) => g.is_series)
    if (series) {
      setSelectedFranchise(series.name)
    } else if (games.games.length > 0) {
      setSelectedFranchise((games.games[0] as GameEntry).name)
    }
  }, [games])

  // Also check if PARENT_FRANCHISE is set and auto-select it
  useEffect(() => {
    if (selectedFranchise) return // Already selected from games effect
    if (!status?.parent_franchise) return // No parent franchise
    
    setSelectedFranchise(status.parent_franchise)
  }, [status])

  const { data: context, isLoading: contextLoading } = useQuery({
    queryKey: ['context', selectedFranchise],
    queryFn: () => getGameContext(selectedFranchise),
    enabled: !!selectedFranchise,
  })

  const updateMutation = useMutation({
    mutationFn: async ({ itemType, itemId, data }: { itemType: string; itemId: string; data: any }) => {
      const result = await updateContextItem(selectedFranchise, itemType, itemId, data)
      return result
    },
    onSuccess: (result) => {
      if (result?.item) {
        queryClient.setQueryData(['context', selectedFranchise], (old: any) => {
          if (!old) return old
          const updated = result.item
          const items = old[updated.type + 's'] || []
          return {
            ...old,
            [updated.type + 's']: items.map((i: any) =>
              i.id === updated.id ? { ...i, ...updated } : i
            )
          }
        })
      }
      queryClient.invalidateQueries({ queryKey: ['context', selectedFranchise] })
      setEditingItem(null)
    },
    onError: (error: Error) => alert(`Failed to update: ${error.message}`)
  })

  const deleteMutation = useMutation({
    mutationFn: ({ itemType, itemId }: { itemType: string; itemId: string }) =>
      deleteContextItem(selectedFranchise, itemType, itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['context', selectedFranchise] })
      setEditingItem(null)
    },
    onError: (error: Error) => alert(`Failed to delete: ${error.message}`)
  })

  const verifyMutation = useMutation({
    mutationFn: ({ itemType, itemId }: { itemType: string; itemId: string }) =>
      updateContextItem(selectedFranchise, itemType, itemId, { verified: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['context', selectedFranchise] })
    },
    onError: (error: Error) => alert(`Failed to verify: ${error.message}`)
  })
  
  const clearMutation = useMutation({
    mutationFn: (game: string) => clearContext(game),
    onSuccess: (data) => {
      if (data.error) alert(`Error: ${data.error}`)
      else alert('Context and memory cleared.')
      queryClient.invalidateQueries({ queryKey: ['context', selectedFranchise] })
    },
    onError: (error: Error) => alert(`Failed to clear context: ${error.message}`)
  })

  const createGameMutation = useMutation({
    mutationFn: (game: string) => createGameContext(game),
    onSuccess: (data) => {
      if (data.error) alert(`Error: ${data.error}`)
      else {
        alert(`Franchise "${data.game}" created successfully.`)
        setSelectedFranchise(data.game)
        setShowCreateModal(false)
        setCreateGameName('')
        queryClient.invalidateQueries({ queryKey: ['games'] })
      }
    },
    onError: (error: Error) => alert(`Failed to create franchise: ${error.message}`)
  })

  const handleEdit = (item: ContextItem) => {
    setEditingItem(item)
    setEditForm({
      name: item.name,
      description: item.description || '',
      category: item.category || '',
    })
  }

  const handleSave = () => {
    if (!editingItem) return
    updateMutation.mutate({
      itemType: editingItem.type,
      itemId: editingItem.id,
      data: {
        name: editForm.name,
        description: editForm.description,
        category: editForm.category,
      },
    })
  }

  const handleDelete = () => {
    if (!editingItem) return
    if (confirm('Are you sure you want to delete this item?')) {
      deleteMutation.mutate({
        itemType: editingItem.type,
        itemId: editingItem.id,
      })
    }
  }

  // Get selected franchise info for display
  const selectedFranchiseInfo = (games?.games || []).find((g: GameEntry) => g.name === selectedFranchise)

  // Build items from context data
  const items: ContextItem[] = [
    ...((context?.characters || []) as any[]).map((c: any) => ({
      id: c.id || c.name,
      name: c.name || c,
      type: 'character',
      description: c.description,
      category: c.category,
      metadata: c.metadata,
      verified: c.verified
    })),
    ...((context?.locations || []) as any[]).map((l: any) => ({
      id: l.id || l.name,
      name: l.name || l,
      type: 'location',
      description: l.description,
      category: l.category,
      metadata: l.metadata,
      verified: l.verified
    })),
    ...((context?.terms || []) as any[]).map((t: any) => ({
      id: t.id || t.name,
      name: t.name || t,
      type: 'term',
      description: t.description,
      category: t.category,
      metadata: t.metadata,
      verified: t.verified
    })),
    ...((context?.relationships || []) as any[]).map((r: any, idx: number) => ({
      id: r.id || (r.from && r.to ? `${r.from}-${r.to}` : `rel-${idx}`),
      name: r.from && r.to ? `${r.from} → ${r.to}` : r.relationship || r.name || 'Unnamed relationship',
      type: 'relationship',
      description: r.relationship || '',
      category: r.relationship || '',
      metadata: r.metadata,
      verified: r.verified
    })),
  ]

  const counts = {
    character: items.filter(i => i.type === 'character').length,
    location: items.filter(i => i.type === 'location').length,
    term: items.filter(i => i.type === 'term').length,
    relationship: items.filter(i => i.type === 'relationship').length,
  }

  const filteredItems = items.filter(item => {
    if (activeTab !== 'all' && item.type !== activeTab) return false
    if (search && !item.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <motion.div variants={stagger.container} initial="hidden" animate="show" className="space-y-6">
      <motion.div variants={slideLeft} className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-40k-gold">CONTEXT</span> EDITOR
          </h1>
          <p className="text-gray-400 mt-1">
            {selectedFranchiseInfo?.is_series 
              ? `Franchise context for ${selectedFranchiseInfo.display_name}`
              : 'Manage game context entities'}
          </p>
        </div>

        <div className="flex gap-3">
          <select
            value={selectedFranchise}
            onChange={(e) => setSelectedFranchise(e.target.value)}
            className="cyber-input w-56"
          >
            <option value="">Select Franchise</option>
            {((games?.games || []) as GameEntry[]).map((game) => (
              <option key={game.name} value={game.name}>
                {game.is_series ? '📁 ' : ''}{game.display_name}
              </option>
            ))}
          </select>
          
          {selectedFranchise && (
            <motion.button 
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="cyber-button flex items-center gap-2 text-40k-red-bright border-40k-red-bright/50"
              disabled={clearMutation.isPending}
              onClick={() => {
                if (window.confirm(`Are you sure you want to CLEAR ALL context for this franchise? This cannot be undone.`)) {
                  clearMutation.mutate(selectedFranchise)
                }
              }}
              title="Clear Franchise Context"
            >
              <Trash2 className="w-4 h-4" />
              Clear All
            </motion.button>
          )}
          
          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="cyber-button flex items-center gap-2"
            onClick={() => setShowCreateModal(true)}
          >
            <Plus className="w-4 h-4" />
            New Franchise
          </motion.button>
        </div>
      </motion.div>

      {/* Franchise Info Banner */}
      {selectedFranchiseInfo?.is_series && selectedFranchiseInfo.children?.length > 0 && (
        <Card className="bg-40k-dark/50 border-40k-gold/20">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-40k-gold/20 flex items-center justify-center">
              <Layers className="w-5 h-5 text-40k-gold" />
            </div>
            <div>
              <p className="text-sm text-gray-400">Franchise contains:</p>
              <div className="flex gap-2 mt-1">
                {selectedFranchiseInfo.children.map((child: string) => (
                  <span key={child} className="px-2 py-1 text-xs bg-40k-gold/10 text-40k-gold rounded">
                    {child}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}

      {selectedFranchise ? (
        <>
          {contextLoading ? (
            <div className="space-y-4">
              <div className="flex gap-2">
                {[1,2,3,4,5].map(i => (
                  <div key={i} className="h-10 w-24 bg-40k-dark rounded-lg animate-pulse" />
                ))}
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {[1,2,3,4,5,6].map(i => (
                  <div key={i} className="h-24 bg-40k-dark rounded-lg animate-pulse" />
                ))}
              </div>
            </div>
          ) : (
          <>
          {/* Tabs and Counts */}
          <div className="flex items-center gap-4">
            <div className="flex gap-2">
              {(['all', 'character', 'location', 'term', 'relationship'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 rounded-lg text-sm transition-all ${
                    activeTab === tab
                      ? 'bg-40k-gold/20 text-40k-gold border border-40k-gold/30'
                      : 'bg-40k-card text-gray-400 hover:text-white'
                  }`}
                >
                  {tab === 'all' ? 'All' : tab.charAt(0).toUpperCase() + tab.slice(1)}
                  <span className="ml-2 text-xs opacity-60">
                    ({tab === 'all' ? Object.values(counts).reduce((a, b) => a + b, 0) : counts[tab as keyof typeof counts]})
                  </span>
                </button>
              ))}
            </div>

            <div className="flex-1">
              <div className="relative max-w-xs">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search entities..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="cyber-input pl-10"
                />
              </div>
            </div>
          </div>

          {/* Entity Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredItems.map((item: ContextItem, i: number) => {
              const config = TYPE_CONFIG[item.type as keyof typeof TYPE_CONFIG] || TYPE_CONFIG.term
              const Icon = config.icon

              return (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.02 }}
                >
                  <Card className="hover:border-40k-gold/30 transition-all cursor-pointer">
                    <div className="flex items-start gap-3">
                      <div className={`w-10 h-10 rounded-lg ${config.bg} flex items-center justify-center ${config.color}`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-white truncate flex items-center gap-1.5">
                          {item.name}
                          {item.verified === true ? (
                            <ShieldCheck className="w-3.5 h-3.5 text-green-400 shrink-0" aria-label="Verified" />
                          ) : (
                            <span className="inline-block px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-yellow-400 border border-yellow-400/30 rounded shrink-0">
                              Unconfirmed
                            </span>
                          )}
                        </h4>
                        <p className="text-xs text-gray-400 capitalize mt-1">
                          {item.type}
                          {item.category && ` • ${item.category}`}
                        </p>
                      </div>
                    </div>

                    {item.description && (
                      <p className="mt-3 text-sm text-gray-400 line-clamp-2">
                        {item.description}
                      </p>
                    )}

                    <div className="mt-4 flex items-center justify-end gap-2">
                      {item.verified !== true && (
                        <button 
                          className="text-xs text-green-400 hover:text-green-300 flex items-center gap-1 disabled:opacity-50"
                          onClick={(e) => {
                            e.stopPropagation()
                            verifyMutation.mutate({ itemType: item.type, itemId: item.id })
                          }}
                          disabled={verifyMutation.isPending}
                        >
                          <CheckCircle2 className="w-3 h-3" />
                          Confirm
                        </button>
                      )}
                      <button 
                        className="text-xs text-40k-gold hover:underline flex items-center gap-1"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleEdit(item)
                        }}
                      >
                        <Pencil className="w-3 h-3" />
                        Edit
                      </button>
                    </div>
                  </Card>
                </motion.div>
              )
            })}
          </div>

          {filteredItems.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              <Database className="w-12 h-12 mb-4 opacity-30" />
              <p>No entities found in this franchise</p>
              <p className="text-sm mt-2">Run the pipeline to extract context from videos</p>
            </div>
          )}
          </>
        )}
        </>
      ) : (
        <div className="flex flex-col items-center justify-center h-64 text-gray-500">
          <Database className="w-12 h-12 mb-4 opacity-30" />
          <p>Select a franchise to view its shared context</p>
        </div>
      )}

      {/* Edit Modal */}
      <AnimatePresence>
        {editingItem && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setEditingItem(null)}
          >
            <motion.div 
              initial={{ scale: 0.9 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.9 }}
              className="bg-40k-card border border-40k-border rounded-lg p-6 w-full max-w-md"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-display font-semibold text-white flex items-center gap-2">
                  <Pencil className="w-5 h-5 text-40k-gold" />
                  Edit {editingItem.type.charAt(0).toUpperCase() + editingItem.type.slice(1)}
                </h3>
                <button onClick={() => setEditingItem(null)} className="text-gray-400 hover:text-white">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-sm text-gray-400 mb-2 block">Name</label>
                  <input
                    type="text"
                    value={editForm.name}
                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    className="cyber-input w-full"
                  />
                </div>

                <div>
                  <label className="text-sm text-gray-400 mb-2 block">Description</label>
                  <textarea
                    value={editForm.description}
                    onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                    className="cyber-input w-full h-24 resize-none"
                  />
                </div>

                <div>
                  <label className="text-sm text-gray-400 mb-2 block">Category</label>
                  <input
                    type="text"
                    value={editForm.category}
                    onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                    className="cyber-input w-full"
                    placeholder="e.g., ally, location, theme"
                  />
                </div>
              </div>

              <div className="flex justify-between mt-6">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleDelete}
                  className="px-4 py-2 text-40k-red-bright hover:bg-40k-red-bright/10 rounded-lg"
                >
                  Delete
                </motion.button>
                <div className="flex gap-2">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setEditingItem(null)}
                    className="cyber-button"
                  >
                    Cancel
                  </motion.button>
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleSave}
                    className="cyber-button-primary flex items-center gap-2"
                  >
                    <Save className="w-4 h-4" />
                    Save
                  </motion.button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create Franchise Modal */}
      <AnimatePresence>
        {showCreateModal && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setShowCreateModal(false)}
          >
            <motion.div 
              initial={{ scale: 0.9 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.9 }}
              className="bg-40k-card border border-40k-border rounded-lg p-6 w-full max-w-md"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-display font-semibold text-white flex items-center gap-2">
                  <Layers className="w-5 h-5 text-40k-gold" />
                  Create New Franchise
                </h3>
                <button onClick={() => setShowCreateModal(false)} className="text-gray-400 hover:text-white">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-sm text-gray-400 mb-2 block">Franchise/Series Name</label>
                  <input
                    type="text"
                    value={createGameName}
                    onChange={(e) => setCreateGameName(e.target.value)}
                    className="cyber-input w-full"
                    placeholder="e.g., tomb_raider_series"
                  />
                  <p className="text-xs text-gray-500 mt-1">Use underscores for spaces, e.g., "tomb_raider_series"</p>
                </div>
              </div>

              <div className="flex justify-end gap-2 mt-6">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => setShowCreateModal(false)}
                  className="cyber-button"
                >
                  Cancel
                </motion.button>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => {
                    if (createGameName.trim()) {
                      createGameMutation.mutate(createGameName.trim())
                    }
                  }}
                  disabled={!createGameName.trim() || createGameMutation.isPending}
                  className="cyber-button-primary flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  Create
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}