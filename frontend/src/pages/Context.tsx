import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Search, Users, MapPin, BookOpen, Link2, Pencil, Trash2, X, Save } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { getGames, getGameContext, updateContextItem, deleteContextItem, clearContext, deleteGame } from '@/lib/api'

const TYPE_CONFIG = {
  character: { icon: Users, color: 'text-cyber-cyan', bg: 'bg-cyber-cyan/20' },
  location: { icon: MapPin, color: 'text-cyber-green', bg: 'bg-cyber-green/20' },
  term: { icon: BookOpen, color: 'text-cyber-yellow', bg: 'bg-cyber-yellow/20' },
  relationship: { icon: Link2, color: 'text-cyber-magenta', bg: 'bg-cyber-magenta/20' },
}

interface ContextItem {
  id: string
  name: string
  type: string
  description?: string
  category?: string
  metadata?: Record<string, any>
}

export default function Context() {
  const queryClient = useQueryClient()
  const [selectedGame, setSelectedGame] = useState<string>('')
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState<'all' | 'character' | 'location' | 'term' | 'relationship'>('all')
  const [editingItem, setEditingItem] = useState<ContextItem | null>(null)
  const [editForm, setEditForm] = useState({ name: '', description: '', category: '' })

  const { data: games } = useQuery({
    queryKey: ['games'],
    queryFn: getGames,
  })

  const { data: context } = useQuery({
    queryKey: ['context', selectedGame],
    queryFn: () => getGameContext(selectedGame),
    enabled: !!selectedGame,
  })

  const updateMutation = useMutation({
    mutationFn: ({ itemType, itemId, data }: { itemType: string; itemId: string; data: any }) =>
      updateContextItem(selectedGame, itemType, itemId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['context', selectedGame] })
      setEditingItem(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: ({ itemType, itemId }: { itemType: string; itemId: string }) =>
      deleteContextItem(selectedGame, itemType, itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['context', selectedGame] })
      setEditingItem(null)
    },
})
  
  const clearMutation = useMutation({
    mutationFn: (game: string) => clearContext(game),
    onSuccess: (data) => {
      if (data.error) alert(`Error: ${data.error}`)
      else alert('Context and memory cleared.')
      queryClient.invalidateQueries({ queryKey: ['context', selectedGame] })
    }
  })

  const deleteGameMutation = useMutation({
    mutationFn: (game: string) => deleteGame(game),
    onSuccess: (data) => {
      if (data.error) alert(`Error: ${data.error}`)
      else {
        alert(`Game "${data.game}" deleted successfully.`)
        setSelectedGame('')
        queryClient.invalidateQueries({ queryKey: ['games'] })
      }
    }
  })

  const items = context ? [
    ...(context.characters || []),
    ...(context.locations || []),
    ...(context.terms || []),
    ...(context.relationships || []),
  ] : []

  const filteredItems = items.filter((item: ContextItem) => 
    item.name?.toLowerCase().includes(search.toLowerCase()) &&
    (activeTab === 'all' || item.type === activeTab)
  )

  const counts = {
    character: context?.characters?.length || 0,
    location: context?.locations?.length || 0,
    term: context?.terms?.length || 0,
    relationship: context?.relationships?.length || 0,
  }

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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-cyber-cyan">CONTEXT</span> EDITOR
          </h1>
          <p className="text-gray-400 mt-1">Manage game context entities</p>
        </div>

        <div className="flex gap-3">
          <select
            value={selectedGame}
            onChange={(e) => setSelectedGame(e.target.value)}
            className="cyber-input w-48"
          >
            <option value="">Select Game</option>
            {(games?.games || []).map((game: string) => (
              <option key={game} value={game}>{game}</option>
            ))}
          </select>
          {selectedGame && (
            <motion.button 
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="cyber-button flex items-center gap-2 text-cyber-red border-cyber-red/50"
              disabled={deleteGameMutation.isPending}
              onClick={() => {
                if (selectedGame && window.confirm(`Are you sure you want to DELETE the entire game "${selectedGame}"? This will remove all context data and cannot be undone.`)) {
                  deleteGameMutation.mutate(selectedGame)
                }
              }}
              title="Delete Game Context"
            >
              <Trash2 className="w-4 h-4" />
              {deleteGameMutation.isPending ? 'Deleting...' : 'Delete Game'}
            </motion.button>
          )}
          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="cyber-button flex items-center gap-2 text-cyber-red border-cyber-red/30"
            disabled={!selectedGame || clearMutation.isPending}
            onClick={() => {
              if (selectedGame && window.confirm(`Are you sure you want to clear ALL context for ${selectedGame}? This cannot be undone.`)) {
                clearMutation.mutate(selectedGame)
              }
            }}
            title="Clear Context & Memory"
          >
            <Trash2 className="w-4 h-4" />
            Clear Context
          </motion.button>
          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="cyber-button-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Entity
          </motion.button>
        </div>
      </div>

      {selectedGame ? (
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
                      ? 'bg-cyber-cyan/20 text-cyber-cyan border border-cyber-cyan/30'
                      : 'bg-cyber-card text-gray-400 hover:text-white'
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
                  <Card className="hover:border-cyber-cyan/30 transition-all cursor-pointer">
                    <div className="flex items-start gap-3">
                      <div className={`w-10 h-10 rounded-lg ${config.bg} flex items-center justify-center ${config.color}`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div className="flex-1">
                        <h4 className="font-medium text-white">{item.name}</h4>
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

                    <div className="mt-4 flex items-center justify-between">
                      <span className="text-xs text-gray-500">
                        Verified: {item.metadata?.validation_count > 0 ? '✓' : '—'}
                      </span>
                      <button 
                        className="text-xs text-cyber-cyan hover:underline flex items-center gap-1"
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
              <p>No entities found</p>
            </div>
          )}
        </>
      ) : (
        <div className="flex flex-col items-center justify-center h-64 text-gray-500">
          <Users className="w-12 h-12 mb-4 opacity-30" />
          <p>Select a game to view and manage its context</p>
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
              className="bg-cyber-card border border-cyber-border rounded-lg p-6 w-full max-w-md"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-display font-semibold text-white flex items-center gap-2">
                  <Pencil className="w-5 h-5 text-cyber-cyan" />
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
                
                {editingItem.type === 'relationship' && (
                  <div>
                    <label className="text-sm text-gray-400 mb-2 block">Category</label>
                    <input
                      type="text"
                      value={editForm.category}
                      onChange={(e) => setEditForm({ ...editForm, category: e.target.value })}
                      className="cyber-input w-full"
                      placeholder="e.g., family, enemy, ally"
                    />
                  </div>
                )}
                
                <div>
                  <label className="text-sm text-gray-400 mb-2 block">Description</label>
                  <textarea
                    value={editForm.description}
                    onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                    className="cyber-input w-full h-24 resize-none"
                  />
                </div>
              </div>

              <div className="mt-6 flex gap-3">
                <motion.button 
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="cyber-button flex-1 flex items-center justify-center gap-2"
                  onClick={() => setEditingItem(null)}
                >
                  Cancel
                </motion.button>
                <motion.button 
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className="cyber-button-primary flex-1 flex items-center justify-center gap-2"
                  onClick={handleSave}
                  disabled={updateMutation.isPending}
                >
                  <Save className="w-4 h-4" />
                  {updateMutation.isPending ? 'Saving...' : 'Save'}
                </motion.button>
              </div>

              <div className="mt-3">
                <motion.button 
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  className="w-full cyber-button text-cyber-red flex items-center justify-center gap-2"
                  onClick={handleDelete}
                  disabled={deleteMutation.isPending}
                >
                  <Trash2 className="w-4 h-4" />
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete Item'}
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}