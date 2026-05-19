import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import ForceGraph2D from 'react-force-graph-2d'
import { motion, AnimatePresence } from 'framer-motion'
import { Network, ZoomIn, ZoomOut, Maximize2, RefreshCw, Pencil, Trash2, X, Save, Settings } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { getGames, getGraphData, getSegmentRefs, updateContextItem, deleteContextItem } from '@/lib/api'

const NODE_COLORS = {
  character: '#22d3ee',  // cyan
  location: '#4ade80',   // green
  term: '#facc15',       // yellow
  relationship: '#e879f9', // magenta
  game: '#fb923c',       // orange
}

interface NodeData {
  id: string
  label: string
  type: string
  category?: string
  description?: string
  val?: number
  x?: number
  y?: number
  neighbors?: string[]
  links?: any[]
  aliases?: string[]
  tags?: string[]
}

// interface LinkData {
//   source: string | NodeData
//   target: string | NodeData
//   label: string
// }

export default function Graph() {
  const containerRef = useRef<HTMLDivElement>(null)
  const fgRef = useRef<any>(null)
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })
  const [selectedGame, setSelectedGame] = useState<string>('')
  const [selectedNode, setSelectedNode] = useState<NodeData | null>(null)
  const [hoverNode, setHoverNode] = useState<NodeData | null>(null)
  const [showEditModal, setShowEditModal] = useState(false)
  const [editForm, setEditForm] = useState({ label: '', description: '' })
  const [showImplicitEdges, setShowImplicitEdges] = useState(true)
  const [showDirectEdges, setShowDirectEdges] = useState(true)
  const [showSettings, setShowSettings] = useState(false)
  const [graphSettings, setGraphSettings] = useState({
    linkDistance: 250,
    linkStrength: 1,
    chargeStrength: -500,
    collisionRadius: 60,
    centerStrength: 0.5,
    velocityDecay: 0.6,
  })
  
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
    queryFn: () => getSegmentRefs(selectedGame),
    enabled: !!selectedGame,
  })
  
  // Auto-select franchise on mount
  useEffect(() => {
    if (selectedGame) return // Already selected
    if (!games?.games?.length) return // No games loaded
    
    const series = games.games.find((g: any) => g.is_series)
    if (series) {
      setSelectedGame(series.name)
    } else if (games.games.length > 0) {
      setSelectedGame(games.games[0].name)
    }
  }, [games])
  
  const updateDimensions = useCallback(() => {
    if (containerRef.current) {
      const width = containerRef.current.clientWidth
      const height = containerRef.current.clientHeight || 600
      setDimensions({ width, height })
    }
  }, [])
  
  useEffect(() => {
    const timer = setTimeout(updateDimensions, 100)
    return () => clearTimeout(timer)
  }, [updateDimensions])
  
  useEffect(() => {
    window.addEventListener('resize', updateDimensions)
    return () => window.removeEventListener('resize', updateDimensions)
  }, [updateDimensions])

  const applyGraphSettings = useCallback((settings: typeof graphSettings) => {
    if (!fgRef.current) return
    const d3 = fgRef.current.d3
    if (d3) {
      d3.force('link').distance(settings.linkDistance).strength(settings.linkStrength)
      d3.force('charge').strength(settings.chargeStrength)
      d3.force('collision').radius(settings.collisionRadius)
      d3.force('center').strength(settings.centerStrength)
      d3.velocityDecay(settings.velocityDecay)
      fgRef.current.d3ReheatGraph()
    }
  }, [])

  const graphData = useMemo(() => {
    if (!rawGraphData?.nodes) return { nodes: [], links: [], implicitCount: 0, directCount: 0 }

    const nodesMap = new Map<string, NodeData>()
    const nodes = rawGraphData.nodes.map((n: any) => {
      const node: NodeData = {
        id: n.data.id,
        label: n.data.label,
        type: n.data.type,
        category: n.data.category,
        description: n.data.description,
        val: n.data.type === 'game' ? 8 : 1,
        neighbors: [],
        links: [],
        aliases: n.data.aliases || [],
        tags: n.data.tags || [],
      }
      if (node.type === 'relationship') node.val = 0.5
      nodesMap.set(node.id, node)
      return node
    })

    let implicitCount = 0
    let directCount = 0
    const links = rawGraphData.edges.map((e: any) => {
      const source = e.data.source
      const target = e.data.target
      const isImplicit = e.data.implicit === true
      const isDirect = e.data.is_direct === true

      const sNode = nodesMap.get(source)
      const tNode = nodesMap.get(target)

      if (sNode && tNode) {
        sNode.neighbors?.push(target)
        tNode.neighbors?.push(source)
        const link = { source, target, label: e.data.label, implicit: isImplicit, type: e.data.type, is_direct: isDirect }
        sNode.links?.push(link)
        tNode.links?.push(link)
      }

      if (isImplicit) implicitCount++
      if (isDirect) directCount++

      return { source, target, label: e.data.label, implicit: isImplicit, type: e.data.type, is_direct: isDirect }
    })

    // Scale node size based on degree
    nodes.forEach((n: NodeData) => {
       n.val = Math.min(10, 2 + (n.neighbors?.length || 0) * 0.5)
    })

    return { nodes, links, implicitCount, directCount }
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
    if (node.x == null || node.y == null || node.val == null) return

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

    // Draw Label (only show on hover/select for focused nodes)
    const showLabel = (isSelected || (isHighlight && hoverNode))
    
    if (showLabel) {
      const fontSize = 12 / globalScale
      ctx.font = `${isSelected ? 'bold ' : ''}${fontSize}px Inter, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = `rgba(255, 255, 255, ${isSelected ? 1 : 0.9})`
      ctx.fillText(node.label ?? '', node.x, node.y + node.val + (fontSize * 1.2))
    }
  }, [highlightNodes, selectedNode, hoverNode])
  
  const paintLink = useCallback((link: any, ctx: CanvasRenderingContext2D) => {
    if (link.source?.x == null || link.source?.y == null || link.target?.x == null || link.target?.y == null) return

    // Filter implicit edges if toggle is off
    if (link.implicit && !showImplicitEdges) return
    if (link.is_direct && !showDirectEdges) return

    const isHighlight = highlightLinks.size === 0 || highlightLinks.has(link)
    const isImplicit = link.implicit === true
    const isDirect = link.is_direct === true

    ctx.beginPath()
    ctx.moveTo(link.source.x, link.source.y)
    ctx.lineTo(link.target.x, link.target.y)

    if (isImplicit) {
      ctx.setLineDash([4, 4])
      ctx.lineWidth = 0.5
      ctx.strokeStyle = isHighlight ? 'rgba(100, 150, 255, 0.8)' : 'rgba(100, 150, 255, 0.2)'
    } else if (isDirect) {
      ctx.setLineDash([])
      ctx.lineWidth = isHighlight ? 2 : 1
      ctx.strokeStyle = isHighlight ? '#e879f9' : 'rgba(232, 121, 249, 0.5)'
    } else if (isHighlight && highlightLinks.size > 0) {
      ctx.setLineDash([])
      ctx.lineWidth = 1.5
      ctx.strokeStyle = '#22d3ee'
    } else {
      ctx.setLineDash([])
      ctx.lineWidth = 0.5
      ctx.strokeStyle = isHighlight ? 'rgba(80, 80, 100, 0.8)' : 'rgba(80, 80, 100, 0.15)'
    }

    ctx.stroke()
    ctx.setLineDash([])
  }, [highlightLinks, showImplicitEdges])

  const updateMutation = useMutation({
    mutationFn: ({ itemType, itemId, data }: { itemType: string; itemId: string; data: any }) =>
      updateContextItem(selectedGame, itemType, itemId, data),
    onSuccess: () => {
      refetch()
      setShowEditModal(false)
      setSelectedNode(null)
    },
    onError: (error: Error) => alert(`Failed to update: ${error.message}`)
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
            className="cyber-input w-56"
          >
            <option value="">Select Franchise</option>
            {((games?.games || []) as any[]).map((game) => (
              <option key={game.name} value={game.name}>
                {game.is_series ? '📁 ' : ''}{game.display_name}
              </option>
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
        <div className="w-px h-4 bg-gray-600" />
        <div className="flex items-center gap-2">
          <div className="w-6 h-0.5 bg-gray-400" />
          <span className="text-sm text-gray-400">explicit</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-0.5 border-t-2 border-dashed border-blue-400" />
          <span className="text-sm text-gray-400">implicit</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-0.5 bg-cyber-magenta" />
          <span className="text-sm text-gray-400">direct</span>
        </div>
        <button
          onClick={() => setShowImplicitEdges(!showImplicitEdges)}
          className={`cyber-button text-xs px-3 py-1 ${showImplicitEdges ? 'bg-cyber-cyan/20 text-cyber-cyan' : ''}`}
        >
          {showImplicitEdges ? 'Hide' : 'Show'} Implicit
        </button>
        <button
          onClick={() => setShowDirectEdges(!showDirectEdges)}
          className={`cyber-button text-xs px-3 py-1 ${showDirectEdges ? 'bg-cyber-magenta/20 text-cyber-magenta' : ''}`}
        >
          {showDirectEdges ? 'Hide' : 'Show'} Direct
        </button>
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
            <button onClick={() => setShowSettings(!showSettings)} className={`cyber-button p-2 bg-cyber-dark/80 backdrop-blur ${showSettings ? 'text-cyber-cyan' : ''}`}>
              <Settings className="w-4 h-4" />
            </button>
          </div>

          {showSettings && (
            <div className="absolute top-4 left-4 z-10 bg-cyber-dark/95 backdrop-blur border border-cyber-border rounded-lg p-4 w-64">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-white">Graph Settings</span>
                <button onClick={() => setShowSettings(false)} className="text-gray-400 hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-gray-400 flex justify-between">
                    <span>Link Distance</span>
                    <span className="text-cyber-cyan">{graphSettings.linkDistance}</span>
                  </label>
                  <input
                    type="range"
                    min="50"
                    max="500"
                    value={graphSettings.linkDistance}
                    onChange={(e) => {
                      const newSettings = { ...graphSettings, linkDistance: Number(e.target.value) }
                      setGraphSettings(newSettings)
                      applyGraphSettings(newSettings)
                    }}
                    className="w-full h-1 bg-gray-700 rounded appearance-none cursor-pointer"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 flex justify-between">
                    <span>Link Force</span>
                    <span className="text-cyber-cyan">{graphSettings.linkStrength.toFixed(1)}</span>
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={graphSettings.linkStrength}
                    onChange={(e) => {
                      const newSettings = { ...graphSettings, linkStrength: Number(e.target.value) }
                      setGraphSettings(newSettings)
                      applyGraphSettings(newSettings)
                    }}
                    className="w-full h-1 bg-gray-700 rounded appearance-none cursor-pointer"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 flex justify-between">
                    <span>Repel Force</span>
                    <span className="text-cyber-cyan">{graphSettings.chargeStrength}</span>
                  </label>
                  <input
                    type="range"
                    min="-2000"
                    max="-50"
                    value={graphSettings.chargeStrength}
                    onChange={(e) => {
                      const newSettings = { ...graphSettings, chargeStrength: Number(e.target.value) }
                      setGraphSettings(newSettings)
                      applyGraphSettings(newSettings)
                    }}
                    className="w-full h-1 bg-gray-700 rounded appearance-none cursor-pointer"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 flex justify-between">
                    <span>Center Force</span>
                    <span className="text-cyber-cyan">{graphSettings.centerStrength.toFixed(2)}</span>
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.05"
                    value={graphSettings.centerStrength}
                    onChange={(e) => {
                      const newSettings = { ...graphSettings, centerStrength: Number(e.target.value) }
                      setGraphSettings(newSettings)
                      applyGraphSettings(newSettings)
                    }}
                    className="w-full h-1 bg-gray-700 rounded appearance-none cursor-pointer"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 flex justify-between">
                    <span>Velocity Decay</span>
                    <span className="text-cyber-cyan">{graphSettings.velocityDecay.toFixed(1)}</span>
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={graphSettings.velocityDecay}
                    onChange={(e) => {
                      const newSettings = { ...graphSettings, velocityDecay: Number(e.target.value) }
                      setGraphSettings(newSettings)
                      applyGraphSettings(newSettings)
                    }}
                    className="w-full h-1 bg-gray-700 rounded appearance-none cursor-pointer"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 flex justify-between">
                    <span>Collision</span>
                    <span className="text-cyber-cyan">{graphSettings.collisionRadius}</span>
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="150"
                    value={graphSettings.collisionRadius}
                    onChange={(e) => {
                      const newSettings = { ...graphSettings, collisionRadius: Number(e.target.value) }
                      setGraphSettings(newSettings)
                      applyGraphSettings(newSettings)
                    }}
                    className="w-full h-1 bg-gray-700 rounded appearance-none cursor-pointer"
                  />
                </div>
                <button
                  onClick={() => {
                    const defaultSettings = { linkDistance: 250, linkStrength: 1, chargeStrength: -500, collisionRadius: 60, centerStrength: 0.5, velocityDecay: 0.6 }
                    setGraphSettings(defaultSettings)
                    applyGraphSettings(defaultSettings)
                  }}
                  className="w-full cyber-button text-xs py-1 mt-2"
                >
                  Reset to Default
                </button>
              </div>
            </div>
          )}

          <div ref={containerRef} className="w-full h-[600px] bg-[#09090b] rounded-lg">
            {graphData.nodes.length > 0 && dimensions.width > 0 && (
              <ForceGraph2D
                ref={fgRef}
                width={dimensions.width}
                height={dimensions.height}
                graphData={graphData}
                nodeCanvasObject={paintNode}
                nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
                  if (node.x == null || node.y == null || node.val == null) return
                  ctx.fillStyle = color
                  ctx.beginPath()
                  ctx.arc(node.x, node.y, Math.max(15, (node.val ?? 0) + 10), 0, 2 * Math.PI, false)
                  ctx.fill()
                }}
                linkCanvasObject={paintLink}
                onNodeClick={handleNodeClick}
                onBackgroundClick={() => setSelectedNode(null)}
                onNodeHover={(node: any) => setHoverNode(node || null)}
                d3AlphaDecay={0.05}
                d3VelocityDecay={graphSettings.velocityDecay}
                cooldownTicks={100}
                onEngineStop={() => {
                  applyGraphSettings(graphSettings)
                  fgRef.current?.zoomToFit(400, 50)
                }}
              />
            )}
          </div>

          <div className="absolute bottom-4 left-4 z-10 flex gap-4 text-xs text-gray-400 bg-cyber-dark/80 backdrop-blur px-3 py-1.5 rounded-full border border-cyber-border/50">
            <span>Nodes: {graphData.nodes.length}</span>
            <span>Edges: {graphData.links.length - graphData.implicitCount - graphData.directCount} explicit + {graphData.directCount} direct + {graphData.implicitCount} implicit</span>
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
                <div className="flex items-start gap-3">
                  <div
                    className="w-14 h-14 rounded-full flex items-center justify-center text-xl font-bold flex-shrink-0"
                    style={{
                      backgroundColor: `${NODE_COLORS[selectedNode.type as keyof typeof NODE_COLORS]}20`,
                      color: NODE_COLORS[selectedNode.type as keyof typeof NODE_COLORS]
                    }}
                  >
                    {selectedNode.label?.[0]?.toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-white text-lg truncate">{selectedNode.label}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="px-2 py-0.5 bg-cyber-dark/80 rounded text-xs capitalize" style={{ color: NODE_COLORS[selectedNode.type as keyof typeof NODE_COLORS] }}>
                        {selectedNode.type}
                      </span>
                      {selectedNode.category && (
                        <span className="px-2 py-0.5 bg-cyber-dark/80 rounded text-xs text-gray-400">
                          {selectedNode.category}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="p-3 bg-cyber-dark rounded-lg text-center">
                    <p className="text-2xl font-bold text-cyber-cyan">{selectedNode.neighbors?.length || 0}</p>
                    <p className="text-xs text-gray-400">Connections</p>
                  </div>
                  <div className="p-3 bg-cyber-dark rounded-lg text-center">
                    <p className="text-2xl font-bold text-cyber-magenta">{selectedNode.links?.length || 0}</p>
                    <p className="text-xs text-gray-400">Relationships</p>
                  </div>
                </div>

                {selectedNode.description && (
                  <div className="p-3 bg-cyber-dark rounded-lg">
                    <p className="text-xs text-gray-400 mb-1">Description</p>
                    <p className="text-sm text-gray-200">{selectedNode.description}</p>
                  </div>
                )}

                {(selectedNode as any).aliases?.length > 0 && (
                  <div className="p-3 bg-cyber-dark rounded-lg">
                    <p className="text-xs text-gray-400 mb-2">Aliases</p>
                    <div className="flex flex-wrap gap-1">
                      {(selectedNode as any).aliases.map((alias: string, idx: number) => (
                        <span key={idx} className="px-2 py-0.5 bg-cyber-border/50 rounded text-xs text-gray-300">
                          {alias}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {(selectedNode as any).tags?.length > 0 && (
                  <div className="p-3 bg-cyber-dark rounded-lg">
                    <p className="text-xs text-gray-400 mb-2">Tags</p>
                    <div className="flex flex-wrap gap-1">
                      {(selectedNode as any).tags.map((tag: string, idx: number) => (
                        <span key={idx} className="px-2 py-0.5 bg-cyber-cyan/20 text-cyber-cyan rounded text-xs">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {selectedNode.neighbors && selectedNode.neighbors.length > 0 && (
                  <div className="p-3 bg-cyber-dark rounded-lg">
                    <p className="text-xs text-gray-400 mb-2">Connected To</p>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {selectedNode.neighbors.slice(0, 10).map((neighborId: string) => {
                        const neighborNode = graphData.nodes.find((n: any) => n.id === neighborId)
                        return neighborNode ? (
                          <div key={neighborId} className="flex items-center gap-2">
                            <div
                              className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold"
                              style={{
                                backgroundColor: `${NODE_COLORS[neighborNode.type as keyof typeof NODE_COLORS]}40`,
                                color: NODE_COLORS[neighborNode.type as keyof typeof NODE_COLORS]
                              }}
                            >
                              {neighborNode.label?.[0]?.toUpperCase()}
                            </div>
                            <span className="text-sm text-gray-300 truncate">{neighborNode.label}</span>
                            <span className="text-xs text-gray-500 capitalize">{neighborNode.type}</span>
                          </div>
                        ) : null
                      })}
                      {selectedNode.neighbors.length > 10 && (
                        <p className="text-xs text-gray-500">+{selectedNode.neighbors.length - 10} more</p>
                      )}
                    </div>
                  </div>
                )}

                {segmentRefs?.references && Object.keys(segmentRefs.references).length > 0 && (
                  <div className="p-3 bg-cyber-dark rounded-lg">
                    <p className="text-xs text-gray-400 mb-2">Source Transcripts</p>
                    <div className="flex flex-wrap gap-2 max-h-24 overflow-y-auto">
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