import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Compass,
  List,
  MessageSquare,
  Network,
  RefreshCw,
  Sparkles,
  X,
} from 'lucide-react'

import { useStudent } from '../context/useStudent'
import { useCourse } from '../context/useCourse'
import {
  getCourseKnowledgeGraph,
  getStudentCourseMastery,
  getTopicDetail,
} from '../api/mastery'
import type {
  CourseMasteryResponse,
  GraphNode,
  GraphResponse,
  LeafTopicMasteryOut,
  TopicDetailResponse,
} from '../types/mastery'
import { Card, CardDescription, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Alert, LoadingState } from '../components/ui/Feedback'
import { PageContainer } from '../components/layout/PageContainer'

interface LayoutNode extends GraphNode {
  x: number
  y: number
  width: number
  height: number
  mastery?: LeafTopicMasteryOut
}

export const MasteryPage: React.FC = () => {
  const { activeStudent } = useStudent()
  const { activeCourse } = useCourse()

  // State
  const [graphData, setGraphData] = useState<GraphResponse | null>(null)
  const [masteryData, setMasteryData] = useState<CourseMasteryResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // View mode: 'graph' or 'list'
  const [viewMode, setViewMode] = useState<'graph' | 'list'>('graph')

  // Selected Node for detail drawer
  const [selectedNodeId, setSelectedNodeId] = useState<number | null>(null)
  const [selectedTopicDetail, setSelectedTopicDetail] = useState<TopicDetailResponse | null>(null)
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  // Hovered node for highlighting connected edges
  const [hoveredNodeId, setHoveredNodeId] = useState<number | null>(null)

  // Manual reload
  const loadData = useCallback(async () => {
    if (!activeCourse) return

    setIsLoading(true)
    setError(null)
    try {
      const graphPromise = getCourseKnowledgeGraph(activeCourse.id)
      const masteryPromise = activeStudent
        ? getStudentCourseMastery(activeStudent.id, activeCourse.id)
        : Promise.resolve(null)

      const [graphRes, masteryRes] = await Promise.all([graphPromise, masteryPromise])
      setGraphData(graphRes)
      setMasteryData(masteryRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load knowledge graph')
    } finally {
      setIsLoading(false)
    }
  }, [activeCourse, activeStudent])

  // Initial data loading effect
  useEffect(() => {
    if (!activeCourse) {
      const timer = window.setTimeout(() => {
        setGraphData(null)
        setMasteryData(null)
      }, 0)
      return () => clearTimeout(timer)
    }

    let isMounted = true
    const courseId = activeCourse.id
    const studentId = activeStudent ? activeStudent.id : null

    const graphPromise = getCourseKnowledgeGraph(courseId)
    const masteryPromise = studentId
      ? getStudentCourseMastery(studentId, courseId)
      : Promise.resolve(null)

    Promise.all([graphPromise, masteryPromise])
      .then(([graphRes, masteryRes]) => {
        if (isMounted) {
          setGraphData(graphRes)
          setMasteryData(masteryRes)
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Failed to load knowledge graph')
          setIsLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [activeCourse, activeStudent])

  // Load detailed topic info when a node is selected
  useEffect(() => {
    if (!selectedNodeId) {
      const timer = window.setTimeout(() => {
        setSelectedTopicDetail(null)
      }, 0)
      return () => clearTimeout(timer)
    }

    let isCancelled = false
    getTopicDetail(selectedNodeId)
      .then((detail) => {
        if (!isCancelled) {
          setSelectedTopicDetail(detail)
          setIsLoadingDetail(false)
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setDetailError(err instanceof Error ? err.message : 'Failed to load topic details')
          setIsLoadingDetail(false)
        }
      })

    return () => {
      isCancelled = true
    }
  }, [selectedNodeId])

  // Build map of topic mastery for quick lookup
  const masteryMap = useMemo(() => {
    const map = new Map<number, LeafTopicMasteryOut>()
    if (masteryData && masteryData.topics) {
      for (const t of masteryData.topics) {
        map.set(t.topic.id, t)
      }
    }
    return map
  }, [masteryData])

  // -------------------------------------------------------------
  // DAG Auto-Layout Algorithm (Native Pure SVG, No External Libraries)
  // -------------------------------------------------------------
  const layout = useMemo(() => {
    if (!graphData || graphData.nodes.length === 0) {
      return { nodes: [], edges: [], width: 800, height: 400 }
    }

    const { nodes, edges } = graphData

    // 1. Calculate in-degree and adjacency for topological layering
    const inDegree = new Map<number, number>()
    const adjList = new Map<number, number[]>()
    for (const n of nodes) {
      inDegree.set(n.id, 0)
      adjList.set(n.id, [])
    }
    for (const e of edges) {
      inDegree.set(e.to, (inDegree.get(e.to) || 0) + 1)
      adjList.get(e.from)?.push(e.to)
    }

    // 2. Assign layers (columns)
    const layer = new Map<number, number>()
    const queue: number[] = []

    for (const n of nodes) {
      if ((inDegree.get(n.id) || 0) === 0) {
        layer.set(n.id, 0)
        queue.push(n.id)
      }
    }

    // Process DAG
    const tempInDegree = new Map(inDegree)
    while (queue.length > 0) {
      const curr = queue.shift()!
      const currLayer = layer.get(curr) || 0
      const neighbors = adjList.get(curr) || []
      for (const next of neighbors) {
        const nextLayer = Math.max(layer.get(next) || 0, currLayer + 1)
        layer.set(next, nextLayer)
        const rem = (tempInDegree.get(next) || 1) - 1
        tempInDegree.set(next, rem)
        if (rem === 0) {
          queue.push(next)
        }
      }
    }

    // Handle any isolated or cyclic nodes
    for (const n of nodes) {
      if (!layer.has(n.id)) {
        layer.set(n.id, n.level || 0)
      }
    }

    // 3. Group nodes by layer
    const maxLayer = Math.max(0, ...Array.from(layer.values()))
    const layerNodes: number[][] = Array.from({ length: maxLayer + 1 }, () => [])
    for (const n of nodes) {
      const l = layer.get(n.id) || 0
      layerNodes[l].push(n.id)
    }

    // 4. Coordinates layout
    const nodeWidth = 160
    const nodeHeight = 60
    const colGap = 100
    const rowGap = 36
    const padX = 50
    const padY = 50

    const maxNodesInLayer = Math.max(1, ...layerNodes.map((ln) => ln.length))
    const totalHeight = Math.max(450, padY * 2 + maxNodesInLayer * (nodeHeight + rowGap))
    const totalWidth = Math.max(750, padX * 2 + (maxLayer + 1) * (nodeWidth + colGap) - colGap)

    const layoutNodes: LayoutNode[] = []
    const nodeMap = new Map<number, LayoutNode>()

    for (let l = 0; l <= maxLayer; l++) {
      const currentLayerNodes = layerNodes[l]
      const count = currentLayerNodes.length
      const layerHeight = count * (nodeHeight + rowGap) - rowGap
      const startY = (totalHeight - layerHeight) / 2

      for (let idx = 0; idx < count; idx++) {
        const id = currentLayerNodes[idx]
        const origNode = nodes.find((n) => n.id === id)!
        const x = padX + l * (nodeWidth + colGap)
        const y = startY + idx * (nodeHeight + rowGap)

        const lNode: LayoutNode = {
          ...origNode,
          x,
          y,
          width: nodeWidth,
          height: nodeHeight,
          mastery: masteryMap.get(id),
        }
        layoutNodes.push(lNode)
        nodeMap.set(id, lNode)
      }
    }

    // 5. Edges with coordinates
    const layoutEdges = edges
      .map((e) => {
        const source = nodeMap.get(e.from)
        const target = nodeMap.get(e.to)
        if (!source || !target) return null
        return {
          from: e.from,
          to: e.to,
          source,
          target,
        }
      })
      .filter((e): e is NonNullable<typeof e> => e !== null)

    return {
      nodes: layoutNodes,
      edges: layoutEdges,
      width: totalWidth,
      height: totalHeight,
    }
  }, [graphData, masteryMap])

  // Helper: Status badge color
  const getStatusColor = (status?: string, pMastery?: number) => {
    if (pMastery !== undefined && pMastery !== null) {
      if (pMastery >= 0.8) return 'emerald'
      if (pMastery >= 0.4) return 'amber'
      return 'rose'
    }
    switch (status) {
      case 'strong':
        return 'emerald'
      case 'learning':
        return 'amber'
      case 'weak':
        return 'rose'
      default:
        return 'neutral'
    }
  }

  return (
    <PageContainer maxWidth="standard">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-surface-text dark:text-dark-text">
              Knowledge & Mastery Graph
            </h1>
            <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted mt-0.5">
              Prerequisite DAG with Bayesian Knowledge Tracing and forgetting-curve tracking.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 p-1 rounded-lg bg-surface-muted dark:bg-dark-muted text-xs">
              <button
                type="button"
                onClick={() => setViewMode('graph')}
                className={`px-3 py-1 rounded-md font-medium flex items-center gap-1.5 transition-all ${
                  viewMode === 'graph'
                    ? 'bg-surface-card dark:bg-dark-card text-surface-text dark:text-dark-text shadow-xs'
                    : 'text-surface-text-muted dark:text-dark-text-muted hover:text-surface-text'
                }`}
              >
                <Network className="w-3.5 h-3.5" />
                <span>Graph View</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('list')}
                className={`px-3 py-1 rounded-md font-medium flex items-center gap-1.5 transition-all ${
                  viewMode === 'list'
                    ? 'bg-surface-card dark:bg-dark-card text-surface-text dark:text-dark-text shadow-xs'
                    : 'text-surface-text-muted dark:text-dark-text-muted hover:text-surface-text'
                }`}
              >
                <List className="w-3.5 h-3.5" />
                <span>Curriculum List</span>
              </button>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={loadData}
              isLoading={isLoading}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Missing Context Alerts */}
        {!activeStudent && (
          <Alert variant="warning">
            <div className="flex items-center justify-between">
              <span>Select an active student profile to inspect personalized concept mastery.</span>
              <Link to="/profile">
                <Button variant="secondary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                  Manage Profile
                </Button>
              </Link>
            </div>
          </Alert>
        )}

        {activeStudent && !activeCourse && (
          <Alert variant="warning">
            <div className="flex items-center justify-between">
              <span>Select a course to view its curriculum knowledge graph.</span>
              <Link to="/courses">
                <Button variant="secondary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                  Select Course
                </Button>
              </Link>
            </div>
          </Alert>
        )}

        {activeCourse && activeCourse.kb_status !== 'ready' && (
          <Alert variant="info">
            <div className="flex items-center justify-between">
              <span>
                Course knowledge base status is <strong>{activeCourse.kb_status}</strong>. Ingest course sources to populate concepts and prerequisites.
              </span>
              <Link to="/sources">
                <Button variant="secondary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                  Manage Sources
                </Button>
              </Link>
            </div>
          </Alert>
        )}

        {error && (
          <Alert variant="error" onDismiss={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Missing Student Context Alert */}
        {!activeStudent && (
          <Alert variant="info">
            <div className="flex items-center justify-between">
              <span>Select an active student profile to track Bayesian mastery progress and view personalized node statistics.</span>
              <Link to="/profile">
                <Button variant="secondary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                  Manage Profile
                </Button>
              </Link>
            </div>
          </Alert>
        )}

        {/* Top Summary Metrics Bar */}
        {masteryData && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
            <Card padding="sm" className="space-y-1">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-surface-text-muted dark:text-dark-text-muted">
                Course Mastery
              </span>
              <div className="text-xl font-bold text-surface-text dark:text-dark-text">
                {masteryData.average_mastery !== null && masteryData.average_mastery !== undefined
                  ? `${Math.round(masteryData.average_mastery * 100)}%`
                  : '0% (Unpracticed)'}
              </div>
            </Card>

            <Card padding="sm" className="space-y-1">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-surface-text-muted dark:text-dark-text-muted">
                Exam Readiness
              </span>
              <div className="text-xl font-bold text-brand-600 dark:text-brand-400">
                {Math.round(masteryData.readiness * 100)}%
              </div>
            </Card>

            <Card padding="sm" className="space-y-1">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-surface-text-muted dark:text-dark-text-muted">
                Topic Coverage
              </span>
              <div className="text-xl font-bold text-surface-text dark:text-dark-text">
                {masteryData.coverage.practiced} / {masteryData.coverage.total}{' '}
                <span className="text-xs font-normal text-surface-text-muted">
                  ({masteryData.coverage.total > 0 ? Math.round((masteryData.coverage.practiced / masteryData.coverage.total) * 100) : 0}%)
                </span>
              </div>
            </Card>

            <Card padding="sm" className="space-y-1">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-surface-text-muted dark:text-dark-text-muted">
                Due for Review
              </span>
              <div className="text-xl font-bold text-amber-600 dark:text-amber-400">
                {masteryData.counts.due_for_review} Topics
              </div>
            </Card>
          </div>
        )}

        {/* Legend */}
        <div className="flex flex-wrap items-center justify-between gap-3 px-3.5 py-2 rounded-lg bg-surface-muted/50 dark:bg-dark-muted/50 border border-surface-border-subtle dark:border-dark-border-subtle text-xs">
          <div className="flex flex-wrap items-center gap-4">
            <span className="font-semibold text-surface-text dark:text-dark-text">Legend:</span>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />
              <span className="text-surface-text-muted dark:text-dark-text-muted">Mastered (&ge;80%)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-amber-500 inline-block" />
              <span className="text-surface-text-muted dark:text-dark-text-muted">Learning (40-79%)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-rose-500 inline-block" />
              <span className="text-surface-text-muted dark:text-dark-text-muted">Needs Practice (&lt;40%)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-stone-400 inline-block" />
              <span className="text-surface-text-muted dark:text-dark-text-muted">Unpracticed</span>
            </div>
          </div>
          <div className="text-[11px] text-surface-text-muted dark:text-dark-text-muted flex items-center gap-1">
            <span>Arrow (A &rarr; B): A is prerequisite for B</span>
          </div>
        </div>

        {/* Main Content Area */}
        {isLoading ? (
          <LoadingState message="Computing curriculum graph and learner mastery..." />
        ) : !graphData || graphData.nodes.length === 0 ? (
          <Card padding="lg" className="text-center py-12">
            <div className="max-w-md mx-auto space-y-3">
              <div className="w-12 h-12 rounded-xl bg-brand-50 dark:bg-brand-950/40 text-brand-600 dark:text-brand-400 flex items-center justify-center mx-auto">
                <Network className="w-6 h-6" />
              </div>
              <CardTitle className="text-base">No Graph Entities Available</CardTitle>
              <CardDescription className="text-xs">
                The current course does not have extracted topics or prerequisite relationships yet. Upload course materials in Sources to build the knowledge graph.
              </CardDescription>
              <div className="pt-2">
                <Link to="/sources">
                  <Button variant="primary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                    Upload Course Sources
                  </Button>
                </Link>
              </div>
            </div>
          </Card>
        ) : viewMode === 'graph' ? (
          /* ----------------------------------------------------------- */
          /* GRAPH VIEW: Pure SVG DAG Canvas                             */
          /* ----------------------------------------------------------- */
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 items-start">
            {/* SVG Visualizer Container */}
            <div className="lg:col-span-2 overflow-auto rounded-xl border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card shadow-xs min-h-125">
              <svg
                viewBox={`0 0 ${layout.width} ${layout.height}`}
                className="w-full h-auto min-w-160 select-none"
              >
                <defs>
                  {/* Arrow markers */}
                  <marker
                    id="arrowhead-default"
                    viewBox="0 0 10 10"
                    refX="9"
                    refY="5"
                    markerWidth="6"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#a8a29e" />
                  </marker>
                  <marker
                    id="arrowhead-active"
                    viewBox="0 0 10 10"
                    refX="9"
                    refY="5"
                    markerWidth="7"
                    markerHeight="7"
                    orient="auto-start-reverse"
                  >
                    <path d="M 0 1 L 10 5 L 0 9 z" fill="#059669" />
                  </marker>
                </defs>

                {/* Background Grid Pattern */}
                <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                  <circle cx="1" cy="1" r="1" className="fill-stone-200 dark:fill-stone-800" />
                </pattern>
                <rect width={layout.width} height={layout.height} fill="url(#grid)" />

                {/* Render Prerequisite Edges */}
                {layout.edges.map((e, idx) => {
                  const x1 = e.source.x + e.source.width
                  const y1 = e.source.y + e.source.height / 2
                  const x2 = e.target.x
                  const y2 = e.target.y + e.target.height / 2
                  const dx = (x2 - x1) / 2

                  const isConnected =
                    hoveredNodeId === e.from ||
                    hoveredNodeId === e.to ||
                    selectedNodeId === e.from ||
                    selectedNodeId === e.to

                  return (
                    <path
                      key={idx}
                      d={`M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`}
                      fill="none"
                      stroke={isConnected ? '#059669' : '#a8a29e'}
                      strokeWidth={isConnected ? '2.5' : '1.5'}
                      strokeDasharray={isConnected ? undefined : '4 2'}
                      markerEnd={isConnected ? 'url(#arrowhead-active)' : 'url(#arrowhead-default)'}
                      className="transition-all duration-200"
                    />
                  )
                })}

                {/* Render Topic Nodes */}
                {layout.nodes.map((node) => {
                  const isSelected = selectedNodeId === node.id
                  const isHovered = hoveredNodeId === node.id
                  const m = node.mastery
                  const pVal = m ? m.p_mastery : undefined

                  let strokeColor = '#a8a29e'
                  let fillColor = '#fafaf9'
                  const textColor = '#292524'

                  if (pVal !== undefined) {
                    if (pVal >= 0.8) {
                      strokeColor = '#059669'
                      fillColor = '#ecfdf5'
                    } else if (pVal >= 0.4) {
                      strokeColor = '#d97706'
                      fillColor = '#fffbeb'
                    } else {
                      strokeColor = '#e11d48'
                      fillColor = '#fff1f2'
                    }
                  }

                  return (
                    <g
                      key={node.id}
                      transform={`translate(${node.x}, ${node.y})`}
                      className="cursor-pointer"
                      onClick={() => setSelectedNodeId(node.id)}
                      onMouseEnter={() => setHoveredNodeId(node.id)}
                      onMouseLeave={() => setHoveredNodeId(null)}
                    >
                      {/* Node Card Box */}
                      <rect
                        width={node.width}
                        height={node.height}
                        rx="8"
                        ry="8"
                        fill={fillColor}
                        stroke={isSelected ? '#15803d' : strokeColor}
                        strokeWidth={isSelected ? '3' : isHovered ? '2' : '1.5'}
                        className="transition-all duration-150"
                        filter={isSelected ? 'drop-shadow(0 4px 6px rgba(0,0,0,0.15))' : undefined}
                      />

                      {/* Topic Name */}
                      <text
                        x="12"
                        y="24"
                        fill={textColor}
                        fontSize="12"
                        fontWeight="600"
                        className="font-sans"
                      >
                        {node.name.length > 18 ? `${node.name.substring(0, 16)}...` : node.name}
                      </text>

                      {/* Mastery / Status Pill */}
                      <rect
                        x="12"
                        y="34"
                        width={pVal !== undefined ? '48' : '40'}
                        height="16"
                        rx="4"
                        ry="4"
                        fill={strokeColor}
                        opacity="0.15"
                      />
                      <text
                        x="18"
                        y="46"
                        fill={strokeColor}
                        fontSize="10"
                        fontWeight="700"
                        className="font-sans"
                      >
                        {pVal !== undefined ? `${Math.round(pVal * 100)}%` : 'New'}
                      </text>

                      {/* Due for review dot */}
                      {m?.due_for_review && (
                        <circle cx={node.width - 12} cy="14" r="4" fill="#d97706" />
                      )}
                    </g>
                  )
                })}
              </svg>
            </div>

            {/* Inspection Side Panel */}
            <div className="space-y-4">
              {selectedNodeId ? (
                <Card padding="md" className="space-y-4 sticky top-4">
                  <div className="flex items-start justify-between pb-2 border-b border-surface-border-subtle dark:border-dark-border-subtle">
                    <div>
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
                        Topic Details
                      </span>
                      <CardTitle className="text-base font-bold">
                        {layout.nodes.find((n) => n.id === selectedNodeId)?.name}
                      </CardTitle>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedNodeId(null)}
                      className="p-1 h-auto text-surface-text-muted hover:text-surface-text"
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>

                  {isLoadingDetail ? (
                    <LoadingState message="Loading topic metadata..." />
                  ) : detailError ? (
                    <Alert variant="error">{detailError}</Alert>
                  ) : selectedTopicDetail ? (
                    <div className="space-y-4">
                      {/* Mastery Stats */}
                      {masteryMap.get(selectedNodeId) ? (
                        (() => {
                          const m = masteryMap.get(selectedNodeId)!
                          return (
                            <div className="p-3 rounded-lg bg-surface-muted/60 dark:bg-dark-muted/60 space-y-2 text-xs">
                              <div className="flex items-center justify-between">
                                <span className="text-surface-text-muted dark:text-dark-text-muted font-medium">
                                  Current Mastery:
                                </span>
                                <Badge
                                  variant={getStatusColor(m.status, m.p_mastery) === 'emerald' ? 'brand' : 'amber'}
                                  size="sm"
                                >
                                  {Math.round(m.p_mastery * 100)}% ({m.status})
                                </Badge>
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="text-surface-text-muted dark:text-dark-text-muted font-medium">
                                  Retrievability:
                                </span>
                                <span>{Math.round(m.retrievability * 100)}%</span>
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="text-surface-text-muted dark:text-dark-text-muted font-medium">
                                  Practice Attempts:
                                </span>
                                <span>
                                  {m.correct} / {m.attempts} ({m.accuracy !== null ? `${Math.round(m.accuracy * 100)}%` : '0%'})
                                </span>
                              </div>
                              {m.due_for_review && (
                                <div className="text-amber-700 dark:text-amber-400 font-semibold pt-1">
                                  &bull; Due for spaced review
                                </div>
                              )}
                            </div>
                          )
                        })()
                      ) : (
                        <div className="p-2.5 rounded-lg bg-surface-muted/60 dark:bg-dark-muted/60 text-xs text-surface-text-muted dark:text-dark-text-muted">
                          No practice attempts recorded yet for this topic.
                        </div>
                      )}

                      {/* Description */}
                      {selectedTopicDetail.description && (
                        <p className="text-xs text-surface-text dark:text-dark-text leading-relaxed">
                          {selectedTopicDetail.description}
                        </p>
                      )}

                      {/* Key Concepts */}
                      {selectedTopicDetail.concepts.length > 0 && (
                        <div className="space-y-1.5">
                          <span className="text-[11px] font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted block">
                            Key Concepts:
                          </span>
                          <div className="space-y-1.5 max-h-40 overflow-y-auto">
                            {selectedTopicDetail.concepts.map((c) => (
                              <div
                                key={c.id}
                                className="p-2 rounded bg-surface-muted/40 dark:bg-dark-muted/40 text-xs border border-surface-border-subtle dark:border-dark-border-subtle"
                              >
                                <span className="font-semibold block">{c.name}</span>
                                <span className="text-[11px] text-surface-text-muted dark:text-dark-text-muted">
                                  {c.definition}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Prerequisites & Unlocks */}
                      <div className="space-y-2 text-xs">
                        {selectedTopicDetail.prerequisites.length > 0 && (
                          <div>
                            <span className="text-[11px] font-semibold text-surface-text-muted dark:text-dark-text-muted block mb-1">
                              Prerequisites:
                            </span>
                            <div className="flex flex-wrap gap-1">
                              {selectedTopicDetail.prerequisites.map((p) => (
                                <Badge key={p.id} variant="neutral" size="sm">
                                  {p.name}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}

                        {selectedTopicDetail.unlocks.length > 0 && (
                          <div>
                            <span className="text-[11px] font-semibold text-surface-text-muted dark:text-dark-text-muted block mb-1">
                              Unlocks:
                            </span>
                            <div className="flex flex-wrap gap-1">
                              {selectedTopicDetail.unlocks.map((u) => (
                                <Badge key={u.id} variant="brand" size="sm">
                                  {u.name}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Action buttons */}
                      <div className="pt-2 border-t border-surface-border-subtle dark:border-dark-border-subtle flex flex-col gap-2">
                        <Link
                          to={`/assessments?topicId=${selectedTopicDetail.id}&topicName=${encodeURIComponent(selectedTopicDetail.name)}`}
                          className="w-full"
                        >
                          <Button variant="primary" size="sm" className="w-full" leftIcon={<Sparkles className="w-3.5 h-3.5" />}>
                            Practice in Quiz
                          </Button>
                        </Link>
                        <Link
                          to={`/tutor?topicId=${selectedTopicDetail.id}&topicName=${encodeURIComponent(selectedTopicDetail.name)}`}
                          className="w-full"
                        >
                          <Button variant="outline" size="sm" className="w-full" leftIcon={<MessageSquare className="w-3.5 h-3.5" />}>
                            Ask AI Tutor
                          </Button>
                        </Link>
                      </div>
                    </div>
                  ) : null}
                </Card>
              ) : (
                <Card padding="md" className="text-center py-10 space-y-2">
                  <div className="w-10 h-10 rounded-xl bg-surface-muted dark:bg-dark-muted text-surface-text-muted dark:text-dark-text-muted flex items-center justify-center mx-auto">
                    <Compass className="w-5 h-5" />
                  </div>
                  <CardTitle className="text-sm">Select a Topic Node</CardTitle>
                  <CardDescription className="text-xs">
                    Click any topic node on the knowledge graph to inspect its mastery, prerequisite requirements, key concepts, and citations.
                  </CardDescription>
                </Card>
              )}
            </div>
          </div>
        ) : (
          /* ----------------------------------------------------------- */
          /* LIST VIEW: Curriculum Hierarchy & Mastery Breakdown          */
          /* ----------------------------------------------------------- */
          <div className="space-y-3">
            {graphData.nodes.map((node) => {
              const m = masteryMap.get(node.id)
              const pVal = m?.p_mastery
              const isSelected = selectedNodeId === node.id

              return (
                <Card
                  key={node.id}
                  padding="md"
                  className={`transition-all hover:border-brand-500 cursor-pointer ${
                    isSelected ? 'ring-2 ring-brand-600 dark:ring-brand-400' : ''
                  }`}
                  onClick={() => setSelectedNodeId(node.id === selectedNodeId ? null : node.id)}
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-surface-text dark:text-dark-text">
                          {node.name}
                        </span>
                        <Badge
                          variant={getStatusColor(m?.status, pVal) === 'emerald' ? 'brand' : 'amber'}
                          size="sm"
                        >
                          {pVal !== undefined ? `${Math.round(pVal * 100)}% Mastery` : 'Unpracticed'}
                        </Badge>
                        {m?.due_for_review && (
                          <Badge variant="amber" size="sm">
                            Due for Review
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-surface-text-muted dark:text-dark-text-muted">
                        Level {node.level} &bull; {node.chunk_count} Grounded Source Chunks
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      {m && (
                        <div className="text-right text-xs hidden sm:block">
                          <span className="font-semibold text-surface-text dark:text-dark-text block">
                            {m.correct} / {m.attempts} Correct
                          </span>
                          <span className="text-surface-text-muted dark:text-dark-text-muted">
                            Accuracy: {m.accuracy !== null ? `${Math.round(m.accuracy * 100)}%` : '0%'}
                          </span>
                        </div>
                      )}
                      <Button variant="outline" size="sm">
                        {isSelected ? 'Hide Details' : 'View Details'}
                      </Button>
                    </div>
                  </div>

                  {/* Expanded Detail inside list card */}
                  {isSelected && selectedTopicDetail && (
                    <div className="mt-4 pt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle space-y-3">
                      {selectedTopicDetail.description && (
                        <p className="text-xs text-surface-text dark:text-dark-text">
                          {selectedTopicDetail.description}
                        </p>
                      )}

                      {selectedTopicDetail.concepts.length > 0 && (
                        <div className="space-y-1">
                          <span className="text-[11px] font-semibold text-surface-text-muted dark:text-dark-text-muted">
                            Concepts:
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {selectedTopicDetail.concepts.map((c) => (
                              <Badge key={c.id} variant="neutral" size="sm">
                                {c.name}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="flex items-center gap-2 pt-2">
                        <Link to={`/assessments?topicId=${node.id}&topicName=${encodeURIComponent(node.name)}`}>
                          <Button variant="primary" size="sm" leftIcon={<Sparkles className="w-3.5 h-3.5" />}>
                            Practice in Quiz
                          </Button>
                        </Link>
                        <Link to={`/tutor?topicId=${node.id}&topicName=${encodeURIComponent(node.name)}`}>
                          <Button variant="outline" size="sm" leftIcon={<MessageSquare className="w-3.5 h-3.5" />}>
                            Ask AI Tutor
                          </Button>
                        </Link>
                      </div>
                    </div>
                  )}
                </Card>
              )
            })}
          </div>
        )}
      </div>
    </PageContainer>
  )
}
