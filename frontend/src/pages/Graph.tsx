import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import ForceGraph2D from 'react-force-graph-2d'
import { motion, AnimatePresence } from 'framer-motion'
import { Network, ZoomIn, ZoomOut, Maximize2, RefreshCw, Pencil, Trash2, X, Save, Settings } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { getGames, getGraphData, getSegmentRefs, updateContextItem, deleteContextItem } from '@/lib/api'
import {
  DEFAULT_GRAPH_SETTINGS,
  loadGraphSettings,
  saveGraphSettings,
  THEME_PHYSICS,
  THEME_OPTIONS,
  type GraphSettings,
  type VisualTheme,
} from '@/lib/graphSettings'

const NODE_COLORS = {
  character: '#c9a227',
  location: '#8b7312',
  term: '#e8c547',
  relationship: '#b71c3a',
  game: '#7a1029',
}

const THEME_COLORS: Record<VisualTheme, Record<string, string>> = {
  starchart: { character: '#c9a227', location: '#8b7312', term: '#e8c547', relationship: '#b71c3a', game: '#7a1029', background: '#0a0a0c' },
  brain: { character: '#9b59b6', location: '#8e44ad', term: '#a569bd', relationship: '#e74c8c', game: '#c0392b', background: '#0a0612' },
  circuit: { character: '#00ff41', location: '#00cc33', term: '#33ff66', relationship: '#ff6600', game: '#ffcc00', background: '#0a0f0a' },
  hologram: { character: '#00ffff', location: '#00cccc', term: '#66ffff', relationship: '#ff00ff', game: '#00ffaa', background: '#001a1a' },
  code: { character: '#00ff00', location: '#00cc00', term: '#33ff33', relationship: '#ff3333', game: '#ffff00', background: '#000800' },
  world: { character: '#4a90d9', location: '#6b5b95', term: '#d4a574', relationship: '#c94c4c', game: '#2ecc71', background: '#0d0d0d' },
}

const LINK_IMPLICIT = 'rgba(183, 28, 58, 0.55)'
const LINK_HIGHLIGHT = '#e8c547'
const LINK_DEFAULT = 'rgba(201, 162, 39, 0.25)'

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
  const [showSettings, setShowSettings] = useState(false)
  const [graphSettings, setGraphSettings] = useState<GraphSettings>(() => loadGraphSettings())
  const [graphReady, setGraphReady] = useState(false)
  const initialFitKeyRef = useRef<string>('')
  const [animationTime, setAnimationTime] = useState(0)
  
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

  // Animation loop for theme effects
  useEffect(() => {
    let animId: number
    const animate = () => {
      setAnimationTime(Date.now() / 1000)
      animId = requestAnimationFrame(animate)
    }
    animId = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(animId)
  }, [])

  const applyGraphSettings = useCallback((settings: GraphSettings) => {
    const fg = fgRef.current
    if (!fg) return

    const link = fg.d3Force('link')
    if (link) {
      link.distance(settings.linkDistance)
      link.strength(settings.linkStrength)
    }
    const charge = fg.d3Force('charge')
    if (charge) charge.strength(settings.chargeStrength)
    const center = fg.d3Force('center')
    if (center) center.strength(settings.centerStrength)
    const collision = fg.d3Force('collision')
    if (collision?.radius) collision.radius(settings.collisionRadius)
    if (typeof fg.d3ReheatSimulation === 'function') {
      fg.d3ReheatSimulation()
    }
  }, [])

  const handleThemeChange = useCallback((theme: VisualTheme) => {
    const themePhysics = THEME_PHYSICS[theme]
    const newSettings = { ...graphSettings, visualTheme: theme, ...themePhysics }
    setGraphSettings(newSettings)
    saveGraphSettings(newSettings)
    applyGraphSettings(newSettings)
  }, [graphSettings, applyGraphSettings])

  const commitGraphSettings = useCallback(
    (next: GraphSettings) => {
      setGraphSettings(next)
      saveGraphSettings(next)
      applyGraphSettings(next)
    },
    [applyGraphSettings]
  )

  const updateGraphSetting = useCallback(
    <K extends keyof GraphSettings>(key: K, value: GraphSettings[K]) => {
      setGraphSettings((prev) => {
        const next = { ...prev, [key]: value }
        saveGraphSettings(next)
        queueMicrotask(() => applyGraphSettings(next))
        return next
      })
    },
    [applyGraphSettings]
  )

  const graphData = useMemo(() => {
    if (!rawGraphData?.nodes) return { nodes: [], links: [], implicitCount: 0, contextCount: 0 }

    const nodesMap = new Map<string, NodeData>()
    const nodes = rawGraphData.nodes
      .filter((n: any) => n.data.type !== 'relationship')
      .map((n: any) => {
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
        nodesMap.set(node.id, node)
        return node
      })

    let implicitCount = 0
    let contextCount = 0
    const links = rawGraphData.edges
      .map((e: any) => {
        const source = e.data.source
        const target = e.data.target
        const isImplicit = e.data.implicit === true
        const isContext = e.data.is_context === true

        const sNode = nodesMap.get(source)
        const tNode = nodesMap.get(target)
        if (!sNode || !tNode) return null

        const link = {
          source,
          target,
          label: e.data.label,
          implicit: isImplicit,
          type: e.data.type,
          is_direct: e.data.is_direct === true,
          is_context: isContext,
        }
        sNode.neighbors?.push(target)
        tNode.neighbors?.push(source)
        sNode.links?.push(link)
        tNode.links?.push(link)

        if (isImplicit) implicitCount++
        if (isContext) contextCount++
        return link
      })
      .filter(Boolean) as Array<{
        source: string
        target: string
        label: string
        implicit: boolean
        type: string
        is_direct: boolean
        is_context: boolean
      }>

    nodes.forEach((n: NodeData) => {
      n.val = Math.min(10, 2 + (n.neighbors?.length || 0) * 0.5)
    })

    return { nodes, links, implicitCount, contextCount }
  }, [rawGraphData])

  const graphInstanceKey = useMemo(
    () => `${selectedGame}:${graphData.nodes.length}:${graphData.links.length}`,
    [selectedGame, graphData.nodes.length, graphData.links.length]
  )

  useEffect(() => {
    setGraphReady(false)
    initialFitKeyRef.current = ''
  }, [graphInstanceKey])

  useEffect(() => {
    if (graphReady && fgRef.current) {
      applyGraphSettings(graphSettings)
    }
  }, [graphReady, applyGraphSettings, graphSettings])

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

    const theme = graphSettings.visualTheme
    const colors = THEME_COLORS[theme]
    const isHighlight = highlightNodes.size === 0 || highlightNodes.has(node.id)
    const isSelected = selectedNode?.id === node.id
    const isHovered = hoverNode?.id === node.id

    const color = colors[node.type] || '#666'
    const opacity = isHighlight ? 1 : 0.2

    // Draw based on theme
    if (theme === 'starchart') {
      // Original starchart - simple circles
      if (isSelected) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, node.val * 2, 0, 2 * Math.PI, false)
        ctx.fillStyle = `${color}40`
        ctx.fill()
      }
      ctx.beginPath()
      ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI, false)
      ctx.fillStyle = `${color}${Math.floor(opacity * 255).toString(16).padStart(2, '0')}`
      ctx.fill()
      ctx.lineWidth = isSelected ? 0.8 : 0.2
      ctx.strokeStyle = isSelected ? '#fff' : '#111'
      ctx.stroke()
    } 
    else if (theme === 'brain') {
      // Brain neurons - gradient circles with pulse
      const pulse = Math.sin(animationTime * 3 + node.id.charCodeAt(0)) * 0.3 + 0.7
      const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, node.val * 2)
      gradient.addColorStop(0, isHighlight ? `${color}${Math.floor(pulse * 255).toString(16).padStart(2, '0')}` : `${color}33`)
      gradient.addColorStop(0.7, `${color}22`)
      gradient.addColorStop(1, 'transparent')
      ctx.beginPath()
      ctx.arc(node.x, node.y, node.val * (isSelected ? 2.5 : 2), 0, 2 * Math.PI, false)
      ctx.fillStyle = gradient
      ctx.fill()
      ctx.beginPath()
      ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI, false)
      ctx.fillStyle = `${color}${Math.floor(opacity * 255).toString(16).padStart(2, '0')}`
      ctx.fill()
      if (isSelected || isHovered) {
        ctx.lineWidth = 1.5
        ctx.strokeStyle = '#fff'
        ctx.stroke()
      }
    }
    else if (theme === 'circuit') {
      // Digital circuits - squares with connection dots
      const size = node.val * 1.2
      ctx.fillStyle = `${color}${Math.floor(opacity * 255).toString(16).padStart(2, '0')}`
      ctx.fillRect(node.x - size, node.y - size, size * 2, size * 2)
      ctx.strokeStyle = isSelected ? '#fff' : (isHighlight ? color : '#222')
      ctx.lineWidth = isSelected ? 2 : 1
      ctx.strokeRect(node.x - size, node.y - size, size * 2, size * 2)
      // Connection dots
      ctx.fillStyle = isHighlight ? '#00ff41' : '#005500'
      ctx.fillRect(node.x - size - 3, node.y - 2, 3, 4)
      ctx.fillRect(node.x + size, node.y - 2, 3, 4)
      ctx.fillRect(node.x - 2, node.y - size - 3, 4, 3)
      ctx.fillRect(node.x - 2, node.y + size, 4, 3)
    }
    else if (theme === 'hologram') {
      // Hologram - circles with scan line
      const flicker = Math.sin(animationTime * 20) * 0.1 + 0.9
      // Outer glow
      const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, node.val * 2)
      gradient.addColorStop(0, `${color}60`)
      gradient.addColorStop(1, 'transparent')
      ctx.beginPath()
      ctx.arc(node.x, node.y, node.val * 2, 0, 2 * Math.PI, false)
      ctx.fillStyle = gradient
      ctx.fill()
      // Main circle
      ctx.beginPath()
      ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI, false)
      ctx.fillStyle = `${color}${Math.floor(opacity * flicker * 255).toString(16).padStart(2, '0')}`
      ctx.fill()
      // Scan line
      const scanY = node.y - node.val + ((animationTime * 50) % (node.val * 2))
      ctx.beginPath()
      ctx.moveTo(node.x - node.val, scanY)
      ctx.lineTo(node.x + node.val, scanY)
      ctx.strokeStyle = `${color}80`
      ctx.lineWidth = 1
      ctx.stroke()
      if (isSelected) {
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 1.5
        ctx.stroke()
      }
    }
    else if (theme === 'code') {
      // Code matrix - terminal rectangles
      ctx.fillStyle = `${color}${Math.floor(opacity * 255).toString(16).padStart(2, '0')}`
      ctx.fillRect(node.x - node.val * 1.5, node.y - node.val, node.val * 3, node.val * 2)
      ctx.strokeStyle = isSelected ? '#fff' : (isHighlight ? color : '#003300')
      ctx.lineWidth = isSelected ? 2 : 1
      ctx.strokeRect(node.x - node.val * 1.5, node.y - node.val, node.val * 3, node.val * 2)
      // Cursor
      const cursorBlink = Math.sin(animationTime * 4) > 0
      if (cursorBlink && (isSelected || isHovered)) {
        ctx.fillStyle = '#00ff00'
        ctx.fillRect(node.x - node.val * 1.5 + 2, node.y - node.val + 2, 2, node.val * 2 - 4)
      }
    }
    else if (theme === 'world') {
      // World map - map pin style
      const pinSize = node.val * 1.3
      // Pin head
      ctx.beginPath()
      ctx.arc(node.x, node.y, pinSize * 0.6, 0, 2 * Math.PI, false)
      ctx.fillStyle = `${color}${Math.floor(opacity * 255).toString(16).padStart(2, '0')}`
      ctx.fill()
      if (isSelected || isHovered) {
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 1.5
        ctx.stroke()
      }
      // Pin point
      ctx.beginPath()
      ctx.moveTo(node.x, node.y + pinSize * 0.6)
      ctx.lineTo(node.x - pinSize * 0.3, node.y + pinSize * 1.2)
      ctx.lineTo(node.x + pinSize * 0.3, node.y + pinSize * 1.2)
      ctx.closePath()
      ctx.fillStyle = isHighlight ? color : '#333'
      ctx.fill()
      // Center dot
      ctx.beginPath()
      ctx.arc(node.x, node.y, pinSize * 0.25, 0, 2 * Math.PI, false)
      ctx.fillStyle = '#fff'
      ctx.fill()
    }

    // Draw Label (only show on hover/select for focused nodes)
    const showLabel = (isSelected || (isHighlight && hoverNode))
    if (showLabel) {
      const fontSize = Math.max(8, 12 / globalScale)
      ctx.font = `${isSelected ? 'bold ' : ''}${fontSize}px Inter, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = `rgba(255, 255, 255, ${isSelected ? 1 : 0.9})`
      ctx.fillText(node.label ?? '', node.x, node.y + node.val + fontSize + 2)
    }
  }, [highlightNodes, selectedNode, hoverNode, graphSettings.visualTheme, animationTime])
  
  const paintLink = useCallback((link: any, ctx: CanvasRenderingContext2D) => {
    if (link.source?.x == null || link.source?.y == null || link.target?.x == null || link.target?.y == null) return

    // Filter implicit edges if toggle is off
    if (link.implicit && !showImplicitEdges) return

    const theme = graphSettings.visualTheme
    const colors = THEME_COLORS[theme]
    const isHighlight = highlightLinks.size === 0 || highlightLinks.has(link)
    const isImplicit = link.implicit === true
    const isContext = link.is_context === true

    const baseColor = isContext ? colors.term : (isImplicit ? colors.relationship : colors.character)

    ctx.beginPath()
    ctx.moveTo(link.source.x, link.source.y)
    ctx.lineTo(link.target.x, link.target.y)

    if (theme === 'starchart') {
      if (isContext) {
        ctx.setLineDash([])
        ctx.lineWidth = isHighlight ? 2.5 : 1.5
        ctx.strokeStyle = isHighlight ? LINK_HIGHLIGHT : 'rgba(201, 162, 39, 0.75)'
      } else if (isImplicit) {
        ctx.setLineDash([4, 4])
        ctx.lineWidth = isHighlight ? 1 : 0.5
        ctx.strokeStyle = isHighlight ? LINK_IMPLICIT : 'rgba(183, 28, 58, 0.2)'
      } else if (isHighlight && highlightLinks.size > 0) {
        ctx.setLineDash([])
        ctx.lineWidth = 1.5
        ctx.strokeStyle = LINK_HIGHLIGHT
      } else {
        ctx.setLineDash([])
        ctx.lineWidth = 0.5
        ctx.strokeStyle = isHighlight ? 'rgba(201, 162, 39, 0.65)' : LINK_DEFAULT
      }
    }
    else if (theme === 'brain') {
      // Pulsing neural pathways
      const pulse = Math.sin(animationTime * 2 + link.source.id.charCodeAt(0)) * 0.3 + 0.7
      ctx.setLineDash([])
      ctx.lineWidth = isHighlight ? 2 : (isImplicit ? 0.5 : 1)
      ctx.strokeStyle = isHighlight ? `${colors.character}${Math.floor(pulse * 200).toString(16).padStart(2, '0')}` : `${baseColor}40`
    }
    else if (theme === 'circuit') {
      // Digital circuit traces with dots
      ctx.setLineDash(isImplicit ? [3, 3] : [])
      ctx.lineWidth = isHighlight ? 1.5 : (isImplicit ? 0.5 : 0.8)
      ctx.strokeStyle = isHighlight ? '#00ff41' : `${baseColor}66`
      // Circuit connection dots
      if (isHighlight) {
        const midX = (link.source.x + link.target.x) / 2
        const midY = (link.source.y + link.target.y) / 2
        ctx.fillStyle = '#00ff41'
        ctx.fillRect(midX - 2, midY - 2, 4, 4)
      }
    }
    else if (theme === 'hologram') {
      // Hologram dashed cyan lines
      const flicker = Math.sin(animationTime * 10) * 0.2 + 0.8
      ctx.setLineDash([8, 4])
      ctx.lineWidth = isHighlight ? 2 : 1
      ctx.strokeStyle = isHighlight ? `rgba(0, 255, 255, ${flicker})` : `${colors.character}44`
    }
    else if (theme === 'code') {
      // Matrix-style vertical lines
      ctx.setLineDash([])
      ctx.lineWidth = isHighlight ? 2.5 : 1
      ctx.strokeStyle = isHighlight ? '#00ff00' : `${baseColor}33`
      // Add flowing effect
      const flowPos = (animationTime * 30) % 40
      if (isHighlight) {
        ctx.setLineDash([flowPos, 40 - flowPos])
      }
    }
    else if (theme === 'world') {
      // World map arc paths
      const midX = (link.source.x + link.target.x) / 2
      const midY = (link.source.y + link.target.y) / 2 - 20
      ctx.beginPath()
      ctx.moveTo(link.source.x, link.source.y)
      ctx.quadraticCurveTo(midX, midY, link.target.x, link.target.y)
      ctx.setLineDash(isImplicit ? [5, 5] : [])
      ctx.lineWidth = isHighlight ? 2 : 1
      ctx.strokeStyle = isHighlight ? colors.character : `${baseColor}44`
    }

    ctx.stroke()
    ctx.setLineDash([])
  }, [highlightLinks, showImplicitEdges, graphSettings.visualTheme, animationTime])

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
  const handleFit = () => {
    initialFitKeyRef.current = ''
    fgRef.current?.zoomToFit(400, 80)
    initialFitKeyRef.current = graphInstanceKey
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold text-white">
            <span className="text-cyber-cyan">KNOWLEDGE</span> GRAPH
          </h1>
          <p className="text-gray-400 mt-1">
            Nodes are entities; edges are saved relationships and transcript co-occurrence.
          </p>
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
          <div className="w-6 h-0.5 bg-40k-gold-bright" />
          <span className="text-sm text-gray-400">context relationship</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-6 h-0.5 border-t-2 border-dashed border-40k-crimson-bright" />
          <span className="text-sm text-gray-400">co-occurrence</span>
        </div>
        <button
          onClick={() => setShowImplicitEdges(!showImplicitEdges)}
          className={`cyber-button text-xs px-3 py-1 ${showImplicitEdges ? 'bg-40k-gold/20 text-40k-gold' : ''}`}
        >
          {showImplicitEdges ? 'Hide' : 'Show'} Co-occurrence
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
                  <label className="text-xs text-gray-400 mb-1 block">Visual Theme</label>
                  <div className="flex flex-wrap gap-1">
                    {THEME_OPTIONS.map((option) => (
                      <button
                        key={option.value}
                        onClick={() => handleThemeChange(option.value)}
                        className={`px-2 py-1 text-xs rounded transition-colors ${
                          graphSettings.visualTheme === option.value
                            ? 'bg-cyber-cyan text-black'
                            : 'bg-cyber-dark border border-cyber-border text-gray-300 hover:bg-cyber-border'
                        }`}
                      >
                        {option.icon} {option.label}
                      </button>
                    ))}
                  </div>
                </div>
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
                    onChange={(e) => updateGraphSetting('linkDistance', Number(e.target.value))}
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
                  onClick={() => commitGraphSettings({ ...DEFAULT_GRAPH_SETTINGS })}
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
                key={graphInstanceKey}
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
                  setGraphReady(true)
                  if (initialFitKeyRef.current !== graphInstanceKey) {
                    initialFitKeyRef.current = graphInstanceKey
                    requestAnimationFrame(() => {
                      fgRef.current?.zoomToFit(400, 80)
                    })
                  }
                }}
              />
            )}
          </div>

          <motion.div
            className="absolute bottom-4 left-4 z-10 flex flex-col gap-2 max-w-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            <motion.div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400 bg-cyber-dark/80 backdrop-blur px-3 py-1.5 rounded-full border border-cyber-border/50">
              <span>Nodes: {graphData.nodes.length}</span>
              <span>Edges: {graphData.contextCount} context + {graphData.implicitCount} co-occurrence</span>
              {rawGraphData?.stats?.sources && (
                <span className="text-gray-500">
                  MemPalace: {rawGraphData.stats.sources.mempalace_chunks} chunks · transcripts:{' '}
                  {(rawGraphData.stats.sources.transcript_files || []).length}
                </span>
              )}
            </motion.div>
            {graphData.nodes.length > 15 && graphData.contextCount < 3 && (
              <p className="text-xs text-amber-200/90 bg-cyber-dark/90 backdrop-blur px-3 py-2 rounded-lg border border-amber-500/30">
                Many entities but few relationship edges. Add relationships in Context or re-run Phase 3 on your transcript.
              </p>
            )}
          </motion.div>
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
                        <span key={idx} className="px-2 py-0.5 bg-40k-gold/20 text-40k-gold rounded text-xs">
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
                            <span key={idx} className="px-2 py-1 bg-40k-gold/20 text-40k-gold text-xs rounded">
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