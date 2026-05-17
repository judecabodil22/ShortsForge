import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import ForceGraph2D from 'react-force-graph-2d'
import { motion, AnimatePresence } from 'framer-motion'
import { Network, ZoomIn, ZoomOut, Maximize2, RefreshCw, Pencil, Trash2, X, Save } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { getGames, getGraphData, updateContextItem, deleteContextItem } from '@/lib/api'

const NODE_COLORS = {
  character: '#00fff5',  // cyan
  location: '#00ff88',   // green
  term: '#f0ff00',       // yellow
  relationship: '#ff00ff', // magenta
}

interface NodeData {
  id: string
  label: string
  type: string
  description?: string
  val?: number
  x?: number
  y?: number
  neighbors?: string[]
  links?: any[]
}

// interface LinkData {
//   source: string | NodeData
//   target: string | NodeData
//   label: string
// }

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null)
  const fgRef = useRef<any>(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 })
  
  const [selectedGame, setSelectedGame] = useState<string>('')
  const [selectedNode, setSelectedNode] = useState<NodeData | null>(null)
  const [hoverNode, setHoverNode] = useState<NodeData | null>(null)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editForm, setEditForm] = useState({ label: '', description: '' })

  const { data: games } = useQuery({
    queryKey: ['games'],
    queryFn: getGames,
  })

  const { data: rawGraphData, refetch } = useQuery({
    queryKey: ['graph', selectedGame],
    queryFn: () => getGraphData(selectedGame),
    enabled: !!selectedGame,
  })

  const { data: segmentRefs } = useQuery({
    queryKey: ['segmentRefs', selectedGame],
    queryFn: () => fetch(`/api/context/${encodeURIComponent(selectedGame)}/segments`).then(r => r.json()),
    enabled: !!selectedGame,
  })

  useEffect(() => {
    if (games?.games?.length > 0 && !selectedGame) {
      setSelectedGame(games.games[0])
    }
  }, [games])

  useEffect(() => {
    if (containerRef.current) {
      setDimensions({
        width: containerRef.current.clientWidth,
        height: containerRef.current.clientHeight || 600
      })
    }
    
    const handleResize = () => {
      if (containerRef.current) {
        setDimensions({
          width: containerRef.current.clientWidth,
          height: containerRef.current.clientHeight || 600
        })
      }
    }
    
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const graphData = useMemo(() => {
    if (!rawGraphData?.nodes) return { nodes: [], links: [] }

    const nodesMap = new Map<string, NodeData>()
    const nodes = rawGraphData.nodes.map((n: any) => {
      const node = { ...n.data, val: 1, neighbors: [], links: [] }
      nodesMap.set(node.id, node)
      return node
    })

    const links = rawGraphData.edges.map((e: any) => {
      const source = e.data.source
      const target = e.data.target
      
      const sNode = nodesMap.get(source)
      const tNode = nodesMap.get(target)
      
      if (sNode && tNode) {
        sNode.neighbors?.push(target)
        tNode.neighbors?.push(source)
        const link = { source, target, label: e.data.label }
        sNode.links?.push(link)
        tNode.links?.push(link)
      }
      
      return { source, target, label: e.data.label }
    })
    
    // Scale node size based on degree
    nodes.forEach((n: NodeData) => {
       n.val = Math.min(10, 2 + (n.neighbors?.length || 0) * 0.5)
    })

    return { nodes, links }
  }, [rawGraphData])

  const highlightNodes = useMemo(() => {
    const set = new Set<string>()
    if (hoverNode) {
      set.add(hoverNode.id)
      hoverNode.neighbors?.forEach(n => set.add(n))
    }
    if (selectedNode) {
      set.add(selectedNode.id)
      selectedNode.neighbors?.forEach(n => set.add(n))
    }
    return set
  }, [hoverNode, selectedNode])

  const highlightLinks = useMemo(() => {
    const set = new Set<any>()
    if (hoverNode) hoverNode.links?.forEach(l => set.add(l))
    if (selectedNode) selectedNode.links?.forEach(l => set.add(l))
    return set
  }, [hoverNode, selectedNode])

  const handleNodeClick = useCallback((node: NodeData) => {
    setSelectedNode(node)
    setEditForm({ label: node.label, description: node.description || '' })
    
    // Center node
    if (fgRef.current && node.x !== undefined && node.y !== undefined) {
      fgRef.current.centerAt(node.x, node.y, 1000)
      fgRef.current.zoom(1.5, 1000)
    }
  }, [])

  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const isHighlight = highlightNodes.size === 0 || highlightNodes.has(node.id)
    const isSelected = selectedNode?.id === node.id
    
    const color = NODE_COLORS[node.type as keyof typeof NODE_COLORS] || '#666'
    const opacity = isHighlight ? 1 : 0.2
    
    // Draw outer glow if selected
    if (isSelected) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, node.val * 2, 0, 2 * Math.PI, false)
      ctx.fillStyle = `${color}40`
      ctx.fill()
    }

    // Draw Node Body
    ctx.beginPath()
    ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI, false)
    ctx.fillStyle = `${color}${Math.floor(opacity * 255).toString(16).padStart(2, '0')}`
    ctx.fill()
    
    // Draw Node Border
    ctx.lineWidth = isSelected ? 0.8 : 0.2
    ctx.strokeStyle = isSelected ? '#fff' : '#111'
    ctx.stroke()

    // Draw Label
    if (isHighlight) {
      const fontSize = 12 / globalScale
      ctx.font = `${isSelected ? 'bold ' : ''}${fontSize}px Inter, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`
      ctx.fillText(node.label, node.x, node.y + node.val + (fontSize * 1.2))
    }
  }, [highlightNodes, selectedNode])
  
  const paintLink = useCallback((link: any, ctx: CanvasRenderingContext2D) => {
    const isHighlight = highlightLinks.size === 0 || highlightLinks.has(link)
    
    ctx.beginPath()
    ctx.moveTo(link.source.x, link.source.y)
    ctx.lineTo(link.target.x, link.target.y)
    
    if (isHighlight && highlightLinks.size > 0) {
      ctx.lineWidth = 1.5
      ctx.strokeStyle = '#00fff5'
    } else {
      ctx.lineWidth = 0.5
      ctx.strokeStyle = isHighlight ? 'rgba(74, 74, 106, 0.8)' : 'rgba(74, 74, 106, 0.1)'
    }
    
    ctx.stroke()
  }, [highlightLinks])

  const updateMutation = useMutation({
    mutationFn: ({ itemType, itemId, data }: { itemType: string; itemId: string; data: any }) =>
      updateContextItem(selectedGame, itemType, itemId, data),
    onSuccess: () => {
      refetch()
      setShowEditModal(false)
      setSelectedNode(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: ({ itemType, itemId }: { itemType: string; itemId: string }) =>
      deleteContextItem(selectedGame, itemType, itemId),
    onSuccess: () => {
      refetch()
      setSelectedNode(null)
    },
  })

  const handleZoomIn = () => fgRef.current?.zoom(fgRef.current.zoom() * 1.5, 400)
  const handleZoomOut = () => fgRef.current?.zoom(fgRef.current.zoom() / 1.5, 400)
  const handleFit = () => fgRef.current?.zoomToFit(400, 50)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-cyber-cyan">KNOWLEDGE</span> GRAPH
          </h1>
          <p className="text-gray-400 mt-1">Interactive Obsidian-style visualization</p>
        </div>

        <div className="flex items-center gap-4">
          <select
            value={selectedGame}
            onChange={(e) => setSelectedGame(e.target.value)}
            className="cyber-input w-48"
          >
            {(games?.games || []).map((game: string) => (
              <option key={game} value={game}>{game}</option>
            ))}
          </select>
          <button onClick={() => refetch()} className="cyber-button">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex gap-4">
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
            <span className="text-sm text-gray-400 capitalize">{type}</span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <Card className="lg:col-span-3 p-0 overflow-hidden relative">
          <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
            <button onClick={handleZoomIn} className="cyber-button p-2 bg-cyber-dark/80 backdrop-blur">
              <ZoomIn className="w-4 h-4" />
            </button>
            <button onClick={handleZoomOut} className="cyber-button p-2 bg-cyber-dark/80 backdrop-blur">
              <ZoomOut className="w-4 h-4" />
            </button>
            <button onClick={handleFit} className="cyber-button p-2 bg-cyber-dark/80 backdrop-blur">
              <Maximize2 className="w-4 h-4" />
            </button>
          </div>

          <div ref={containerRef} className="w-full h-[600px] bg-[#0A0A0F] rounded-lg">
            {graphData.nodes.length > 0 && dimensions.width > 0 && (
              <ForceGraph2D
                ref={fgRef}
                width={dimensions.width}
                height={dimensions.height}
                graphData={graphData}
                nodeCanvasObject={paintNode}
                nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
                  ctx.fillStyle = color
                  ctx.beginPath()
                  ctx.arc(node.x, node.y, Math.max(15, node.val + 10), 0, 2 * Math.PI, false)
                  ctx.fill()
                }}
                linkCanvasObject={paintLink}
                onNodeClick={handleNodeClick}
                onBackgroundClick={() => setSelectedNode(null)}
                onNodeHover={(node: any) => setHoverNode(node || null)}
                d3AlphaDecay={0.05}
                d3VelocityDecay={0.3}
                cooldownTicks={100}
                onEngineStop={() => fgRef.current?.zoomToFit(400, 50)}
              />
            )}
          </div>

          <div className="absolute bottom-4 left-4 z-10 flex gap-4 text-xs text-gray-400 bg-cyber-dark/80 backdrop-blur px-3 py-1.5 rounded-full border border-cyber-border/50">
            <span>Nodes: {graphData.nodes.length}</span>
            <span>Edges: {graphData.links.length}</span>
          </div>
        </Card>

        <Card>
          <h3 className="text-lg font-display font-semibold text-white mb-4 flex items-center gap-2">
            <Network className="w-5 h-5 text-cyber-magenta" />
            Node Details
          </h3>

          <AnimatePresence mode="wait">
            {selectedNode ? (
              <motion.div
                key={selectedNode.id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-4"
              >
                <div className="flex items-center gap-3">
                  <div 
                    className="w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold"
                    style={{ 
                      backgroundColor: `${NODE_COLORS[selectedNode.type as keyof typeof NODE_COLORS]}20`,
                      color: NODE_COLORS[selectedNode.type as keyof typeof NODE_COLORS]
                    }}
                  >
                    {selectedNode.label?.[0]?.toUpperCase()}
                  </div>
                  <div>
                    <p className="font-medium text-white">{selectedNode.label}</p>
                    <p className="text-xs text-gray-400 capitalize">{selectedNode.type}</p>
                  </div>
                </div>

                {selectedNode.description && (
                  <div className="p-3 bg-cyber-dark rounded-lg">
                    <p className="text-sm text-gray-300">{selectedNode.description}</p>
                  </div>
                )}

                {segmentRefs?.references && Object.keys(segmentRefs.references).length > 0 && (
                  <div className="p-3 bg-cyber-dark rounded-lg">
                    <p className="text-xs text-gray-400 mb-2">Source Transcripts</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(segmentRefs.references).flatMap(([_transcript, nodes]: [string, any]) =>
                        nodes.filter((n: any) => n.node.toLowerCase() === selectedNode.label?.toLowerCase() || 
                          selectedNode.label?.toLowerCase().includes(n.node.toLowerCase())).map((n: any, idx: number) => (
                          <span key={idx} className="px-2 py-1 bg-cyber-cyan/20 text-cyber-cyan text-xs rounded">
                            {n.transcript}
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <button 
                    className="cyber-button w-full text-sm flex items-center justify-center gap-2"
                    onClick={() => setShowEditModal(true)}
                  >
                    <Pencil className="w-4 h-4" />
                    Edit Node
                  </button>
                  <button 
                    className="cyber-button w-full text-sm text-cyber-red flex items-center justify-center gap-2"
                    onClick={() => {
                      if (confirm(`Are you sure you want to delete "${selectedNode.label}"?`)) {
                        deleteMutation.mutate({
                          itemType: selectedNode.type,
                          itemId: selectedNode.id,
                        })
                      }
                    }}
                  >
                    <Trash2 className="w-4 h-4" />
                    Delete Node
                  </button>
                </div>
              </motion.div>
            ) : (
              <div className="flex flex-col items-center justify-center h-48 text-gray-500">
                <Network className="w-10 h-10 mb-3 opacity-30" />
                <p className="text-sm">Click a node to view details</p>
              </div>
            )}
          </AnimatePresence>
        </Card>
      </div>

      <AnimatePresence>
        {showEditModal && selectedNode && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
            onClick={() => setShowEditModal(false)}
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
                  Edit Node
                </h3>
                <button onClick={() => setShowEditModal(false)} className="text-gray-400 hover:text-white">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-sm text-gray-400 mb-2 block">Name</label>
                  <input
                    type="text"
                    value={editForm.label}
                    onChange={(e) => setEditForm({ ...editForm, label: e.target.value })}
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
              </div>

              <div className="mt-6 flex gap-3">
                <button 
                  className="cyber-button flex-1 flex items-center justify-center gap-2"
                  onClick={() => setShowEditModal(false)}
                >
                  Cancel
                </button>
                <button 
                  className="cyber-button-primary flex-1 flex items-center justify-center gap-2"
                  onClick={() => {
                    updateMutation.mutate({
                      itemType: selectedNode.type,
                      itemId: selectedNode.id,
                      data: {
                        name: editForm.label,
                        description: editForm.description,
                      },
                    })
                  }}
                >
                  <Save className="w-4 h-4" />
                  Save
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}