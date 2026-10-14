import React, { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useCourse } from '../context/useCourse'
import {
  deleteSource,
  getCourseKbStatus,
  getSourceFileUrl,
  listCourseSources,
  listSourceChunks,
  rebuildCourseKb,
  retrySource,
  uploadCourseSource,
} from '../api/sources'
import type { ChunkRead, KBStatusResponse, SourceRead } from '../types/source'
import { PageContainer, PageHeader } from '../components/layout/PageContainer'
import { Button } from '../components/ui/Button'
import { Card, CardDescription, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { Modal } from '../components/ui/Modal'
import { Alert, EmptyState, LoadingState } from '../components/ui/Feedback'
import {
  AlertCircleIcon,
  ArrowRightIcon,
  BookOpenIcon,
  DownloadIcon,
  FileTextIcon,
  LayersIcon,
  PlusIcon,
  RefreshCwIcon,
  SearchIcon,
  Trash2Icon,
  UploadCloudIcon,
} from '../components/ui/Icons'

const ALLOWED_EXTENSIONS = ['.pdf', '.pptx', '.vtt', '.srt', '.txt', '.json']
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024 // 50MB

export const SourcesPage: React.FC = () => {
  const { courses, activeCourseId, activeCourseDetail, setActiveCourseId } = useCourse()
  const fileInputId = useId()

  // Sources list state
  const [sources, setSources] = useState<SourceRead[]>([])
  const [isLoadingSources, setIsLoadingSources] = useState(false)
  const [sourcesError, setSourcesError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')

  // KB Status state
  const [kbStatus, setKbStatus] = useState<KBStatusResponse | null>(null)
  const [isRebuildingKb, setIsRebuildingKb] = useState(false)
  const [kbMessage, setKbMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Upload modal state
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadTitle, setUploadTitle] = useState('')
  const [uploadMediaUrl, setUploadMediaUrl] = useState('')
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)

  // Chunks viewer modal state
  const [selectedSourceForChunks, setSelectedSourceForChunks] = useState<SourceRead | null>(null)
  const [chunks, setChunks] = useState<ChunkRead[]>([])
  const [isLoadingChunks, setIsLoadingChunks] = useState(false)
  const [chunksError, setChunksError] = useState<string | null>(null)

  // Delete confirmation modal state
  const [deletingSource, setDeletingSource] = useState<SourceRead | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  // Retry loading state by source ID
  const [retryingSourceId, setRetryingSourceId] = useState<number | null>(null)

  // Ref to cancel active polling on unmount
  const pollTimerRef = useRef<number | null>(null)

  // Load sources for active course (for manual refresh / post-mutations)
  const fetchSources = useCallback(
    async (silent = false) => {
      if (!activeCourseId) {
        setSources([])
        return
      }
      if (!silent) setIsLoadingSources(true)
      try {
        const data = await listCourseSources(activeCourseId)
        setSources(data)
        setSourcesError(null)
      } catch (err: unknown) {
        if (!silent) {
          setSourcesError(err instanceof Error ? err.message : 'Failed to load course materials.')
        }
      } finally {
        if (!silent) setIsLoadingSources(false)
      }
    },
    [activeCourseId]
  )

  // Load KB status for active course (for manual refresh / post-mutations)
  const fetchKbStatus = useCallback(
    async () => {
      if (!activeCourseId) {
        setKbStatus(null)
        return
      }
      try {
        const data = await getCourseKbStatus(activeCourseId)
        setKbStatus(data)
      } catch {
        // Non-fatal if KB status isn't available yet
      }
    },
    [activeCourseId]
  )

  // Async load on mount or course switch without synchronous setState in effect
  useEffect(() => {
    let isMounted = true
    if (!activeCourseId) {
      return
    }

    listCourseSources(activeCourseId)
      .then((data) => {
        if (isMounted) {
          setSources(data)
          setSourcesError(null)
          setIsLoadingSources(false)
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setSourcesError(err instanceof Error ? err.message : 'Failed to load course materials.')
          setIsLoadingSources(false)
        }
      })

    getCourseKbStatus(activeCourseId)
      .then((data) => {
        if (isMounted) {
          setKbStatus(data)
        }
      })
      .catch(() => {
        // Non-fatal if KB status isn't available yet
      })

    return () => {
      isMounted = false
    }
  }, [activeCourseId])

  // Active polling if any source is processing or KB is building
  useEffect(() => {
    const hasActiveSourceProcessing = sources.some(
      (s) => s.status === 'queued' || s.status === 'processing'
    )
    const isKbBuilding = kbStatus?.kb_status === 'building'

    if ((hasActiveSourceProcessing || isKbBuilding) && activeCourseId) {
      pollTimerRef.current = window.setTimeout(() => {
        void fetchSources(true)
        void fetchKbStatus()
      }, 3000)
    }

    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current)
      }
    }
  }, [sources, kbStatus, activeCourseId, fetchSources, fetchKbStatus])

  // Handle file validation and selection
  const handleFileSelect = (file: File) => {
    setUploadError(null)
    const lowerName = file.name.toLowerCase()
    const isValidExt = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext))

    if (!isValidExt) {
      setUploadError(`Unsupported file type. Supported formats: ${ALLOWED_EXTENSIONS.join(', ')}`)
      return
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      setUploadError('File exceeds the 50 MB upload limit.')
      return
    }

    setSelectedFile(file)
    if (!uploadTitle.trim()) {
      // Suggest title from filename without extension
      const baseName = file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ')
      setUploadTitle(baseName)
    }
  }

  // Handle upload submit
  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeCourseId) {
      setUploadError('Please select a course first.')
      return
    }
    if (!selectedFile) {
      setUploadError('Please select a file to upload.')
      return
    }

    setIsUploading(true)
    setUploadError(null)

    try {
      await uploadCourseSource(activeCourseId, {
        file: selectedFile,
        title: uploadTitle.trim() || undefined,
        media_url: uploadMediaUrl.trim() || undefined,
      })
      // Reset form
      setSelectedFile(null)
      setUploadTitle('')
      setUploadMediaUrl('')
      setIsUploadOpen(false)
      // Refresh sources list and KB status
      await fetchSources(false)
      await fetchKbStatus()
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setIsUploading(false)
    }
  }

  // Handle retry for failed source
  const handleRetry = async (sourceId: number) => {
    setRetryingSourceId(sourceId)
    try {
      await retrySource(sourceId)
      await fetchSources(true)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to retry ingestion.')
    } finally {
      setRetryingSourceId(null)
    }
  }

  // Handle delete source
  const handleDeleteConfirm = async () => {
    if (!deletingSource) return
    setIsDeleting(true)
    try {
      await deleteSource(deletingSource.id)
      setDeletingSource(null)
      await fetchSources(false)
      await fetchKbStatus()
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete source.')
    } finally {
      setIsDeleting(false)
    }
  }

  // Handle KB Rebuild
  const handleRebuildKb = async () => {
    if (!activeCourseId) return
    setIsRebuildingKb(true)
    setKbMessage(null)
    try {
      await rebuildCourseKb(activeCourseId)
      setKbMessage({
        type: 'success',
        text: 'Knowledge base build queued. Indexing topics and concepts...',
      })
      await fetchKbStatus()
    } catch (err: unknown) {
      setKbMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to trigger KB rebuild.',
      })
    } finally {
      setIsRebuildingKb(false)
    }
  }

  // Handle opening chunks viewer
  const handleViewChunks = async (source: SourceRead) => {
    setSelectedSourceForChunks(source)
    setChunks([])
    setIsLoadingChunks(true)
    setChunksError(null)

    try {
      const data = await listSourceChunks(source.id, 100, 0)
      setChunks(data)
    } catch (err: unknown) {
      setChunksError(err instanceof Error ? err.message : 'Failed to load chunks.')
    } finally {
      setIsLoadingChunks(false)
    }
  }

  // Filter sources
  const filteredSources = sources.filter((s) => {
    const matchesSearch =
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.original_filename.toLowerCase().includes(searchQuery.toLowerCase())
    if (!matchesSearch) return false

    if (typeFilter === 'all') return true
    if (typeFilter === 'pdf') return s.source_type === 'pdf'
    if (typeFilter === 'pptx') return s.source_type === 'pptx'
    if (typeFilter === 'transcript') {
      return (
        s.source_type === 'video_transcript' ||
        s.original_filename.endsWith('.vtt') ||
        s.original_filename.endsWith('.srt')
      )
    }
    if (typeFilter === 'text') {
      return s.original_filename.endsWith('.txt') || s.original_filename.endsWith('.json')
    }
    return true
  })

  // Format file size
  const formatBytes = (bytes?: number) => {
    if (!bytes || bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
  }

  // Status Badge Helper
  const renderSourceStatusBadge = (status: string, stage?: string | null) => {
    switch (status) {
      case 'ready':
        return (
          <Badge variant="brand" size="sm" dot>
            Ready
          </Badge>
        )
      case 'processing':
        return (
          <Badge variant="amber" size="sm" dot className="animate-pulse">
            Processing{stage ? `: ${stage}` : ''}
          </Badge>
        )
      case 'queued':
        return (
          <Badge variant="neutral" size="sm" dot>
            Queued
          </Badge>
        )
      case 'failed':
        return (
          <Badge variant="error" size="sm" dot>
            Failed
          </Badge>
        )
      default:
        return (
          <Badge variant="neutral" size="sm">
            {status}
          </Badge>
        )
    }
  }

  // Type Badge Helper
  const renderSourceTypeBadge = (sourceType: string, filename: string) => {
    const ext = filename.split('.').pop()?.toUpperCase() || sourceType.toUpperCase()
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-mono font-medium bg-surface-muted dark:bg-dark-muted text-surface-text-muted dark:text-dark-text-muted border border-surface-border dark:border-dark-border">
        {ext}
      </span>
    )
  }

  const readySourcesCount = sources.filter((s) => s.status === 'ready').length

  return (
    <PageContainer>
      {/* Header */}
      <PageHeader
        title="Course Sources & Ingestion"
        description="Ingest lecture slides, readings, transcripts, and notes to generate vector chunks and knowledge graph concepts."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                void fetchSources(false)
                void fetchKbStatus()
              }}
              disabled={isLoadingSources || !activeCourseId}
              leftIcon={<RefreshCwIcon className={isLoadingSources ? 'animate-spin' : ''} />}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsUploadOpen(true)}
              disabled={!activeCourseId}
              leftIcon={<UploadCloudIcon />}
            >
              Upload Material
            </Button>
          </div>
        }
      />

      {/* No Active Course Selected State */}
      {!activeCourseId ? (
        <Card className="p-6 text-center border-dashed border-2 border-surface-border dark:border-dark-border">
          <div className="max-w-md mx-auto space-y-4">
            <div className="w-12 h-12 rounded-xl bg-brand-50 dark:bg-brand-950/40 text-brand-700 dark:text-brand-300 flex items-center justify-center mx-auto">
              <BookOpenIcon className="w-6 h-6" />
            </div>
            <div>
              <CardTitle className="text-lg">No Active Course Selected</CardTitle>
              <CardDescription className="mt-1">
                Source materials, documents, and knowledge bases belong to a specific course.
                Choose an existing course below or create a new one to begin uploading.
              </CardDescription>
            </div>

            {courses.length > 0 ? (
              <div className="pt-2">
                <label className="block text-xs font-medium text-surface-text-muted dark:text-dark-text-muted mb-2">
                  Select a course to manage:
                </label>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  {courses.map((course) => (
                    <Button
                      key={course.id}
                      variant="outline"
                      size="sm"
                      onClick={() => setActiveCourseId(course.id)}
                      className="text-xs"
                    >
                      {course.name}
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="pt-2">
                <Link to="/courses">
                  <Button variant="primary" size="sm" rightIcon={<ArrowRightIcon />}>
                    Create Your First Course
                  </Button>
                </Link>
              </div>
            )}
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          {/* Active Course Banner & KB Status Card */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Active Course Overview */}
            <Card className="p-4 sm:p-5 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-xs font-semibold text-brand-700 dark:text-brand-300 uppercase tracking-wider">
                    Current Course Context
                  </span>
                  <Link
                    to="/courses"
                    className="text-xs text-surface-text-muted dark:text-dark-text-muted hover:text-brand-600 dark:hover:text-brand-400 transition-colors"
                  >
                    Switch course
                  </Link>
                </div>
                <h3 className="text-base sm:text-lg font-bold text-surface-text dark:text-dark-text">
                  {activeCourseDetail?.name || 'Selected Course'}
                </h3>
                {activeCourseDetail?.description && (
                  <p className="mt-1 text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted line-clamp-2">
                    {activeCourseDetail.description}
                  </p>
                )}
              </div>

              <div className="mt-4 pt-3 border-t border-surface-border dark:border-dark-border flex items-center justify-between text-xs text-surface-text-muted dark:text-dark-text-muted">
                <span>Total Materials: <strong className="text-surface-text dark:text-dark-text">{sources.length}</strong></span>
                <span>Ready: <strong className="text-brand-700 dark:text-brand-400">{readySourcesCount}</strong></span>
              </div>
            </Card>

            {/* Knowledge Base Status & Rebuild Action */}
            <Card className="p-4 sm:p-5 lg:col-span-2 flex flex-col justify-between">
              <div>
                <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
                      Knowledge Base Status
                    </span>
                    {kbStatus && (
                      <Badge
                        variant={
                          kbStatus.kb_status === 'ready'
                            ? 'brand'
                            : kbStatus.kb_status === 'building'
                            ? 'amber'
                            : kbStatus.kb_status === 'failed'
                            ? 'error'
                            : 'neutral'
                        }
                        size="sm"
                        dot
                      >
                        {kbStatus.kb_status.toUpperCase()}
                      </Badge>
                    )}
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleRebuildKb()}
                    disabled={
                      isRebuildingKb ||
                      kbStatus?.kb_status === 'building' ||
                      readySourcesCount === 0
                    }
                    leftIcon={
                      <RefreshCwIcon
                        className={
                          isRebuildingKb || kbStatus?.kb_status === 'building'
                            ? 'animate-spin'
                            : ''
                        }
                      />
                    }
                    className="text-xs"
                  >
                    {kbStatus?.kb_status === 'building' ? 'Building KB...' : 'Rebuild Knowledge Base'}
                  </Button>
                </div>

                {/* Progress bar if KB is building */}
                {kbStatus?.kb_status === 'building' && (
                  <div className="mb-3 space-y-1">
                    <div className="flex justify-between text-xs text-surface-text-muted dark:text-dark-text-muted">
                      <span>Stage: {kbStatus.stage || 'indexing'}</span>
                      <span>{kbStatus.progress}%</span>
                    </div>
                    <div className="w-full bg-surface-muted dark:bg-dark-muted h-2 rounded-full overflow-hidden">
                      <div
                        className="bg-brand-600 dark:bg-brand-500 h-full transition-all duration-300"
                        style={{ width: `${Math.max(5, kbStatus.progress)}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* KB Message feedback */}
                {kbMessage && (
                  <div className="mb-3">
                    <Alert
                      variant={kbMessage.type === 'success' ? 'success' : 'error'}
                      title={kbMessage.type === 'success' ? 'Notice' : 'Build Error'}
                      description={kbMessage.text}
                    />
                  </div>
                )}

                {/* KB Counts Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                  <div className="p-2 rounded-lg bg-surface-muted/60 dark:bg-dark-muted/40 border border-surface-border dark:border-dark-border">
                    <div className="text-xs text-surface-text-muted dark:text-dark-text-muted">Topics</div>
                    <div className="text-base font-semibold text-surface-text dark:text-dark-text">
                      {kbStatus?.counts.topics ?? 0}
                    </div>
                  </div>
                  <div className="p-2 rounded-lg bg-surface-muted/60 dark:bg-dark-muted/40 border border-surface-border dark:border-dark-border">
                    <div className="text-xs text-surface-text-muted dark:text-dark-text-muted">Concepts</div>
                    <div className="text-base font-semibold text-surface-text dark:text-dark-text">
                      {kbStatus?.counts.concepts ?? 0}
                    </div>
                  </div>
                  <div className="p-2 rounded-lg bg-surface-muted/60 dark:bg-dark-muted/40 border border-surface-border dark:border-dark-border">
                    <div className="text-xs text-surface-text-muted dark:text-dark-text-muted">Total Chunks</div>
                    <div className="text-base font-semibold text-surface-text dark:text-dark-text">
                      {kbStatus?.counts.total_chunks ?? 0}
                    </div>
                  </div>
                  <div className="p-2 rounded-lg bg-surface-muted/60 dark:bg-dark-muted/40 border border-surface-border dark:border-dark-border">
                    <div className="text-xs text-surface-text-muted dark:text-dark-text-muted">Tagged Chunks</div>
                    <div className="text-base font-semibold text-brand-700 dark:text-brand-400">
                      {kbStatus?.counts.tagged_chunks ?? 0}
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-3 text-[11px] text-surface-text-muted dark:text-dark-text-muted">
                {readySourcesCount === 0
                  ? 'Ingest at least one source document to enable knowledge base construction.'
                  : 'Knowledge base powers vector retrieval and conceptual graph mapping for adaptive tutoring.'}
              </div>
            </Card>
          </div>

          {/* Sources Filter & Search Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-text-muted dark:text-dark-text-muted" />
              <input
                type="text"
                placeholder="Search materials by title or filename..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs sm:text-sm rounded-lg bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border text-surface-text dark:text-dark-text placeholder:text-surface-text-muted focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>

            {/* Filter buttons */}
            <div className="flex flex-wrap items-center gap-1 text-xs">
              {(
                [
                  { id: 'all', label: 'All' },
                  { id: 'pdf', label: 'PDF' },
                  { id: 'pptx', label: 'PPTX' },
                  { id: 'transcript', label: 'Transcripts' },
                  { id: 'text', label: 'Text/JSON' },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setTypeFilter(tab.id)}
                  className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer font-medium ${
                    typeFilter === tab.id
                      ? 'bg-brand-50 dark:bg-brand-950/50 text-brand-800 dark:text-brand-300 font-semibold'
                      : 'text-surface-text-muted dark:text-dark-text-muted hover:text-surface-text dark:hover:text-dark-text hover:bg-surface-muted dark:hover:bg-dark-muted'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Error Alert */}
          {sourcesError && (
            <Alert
              variant="error"
              title="Failed to load course materials"
              description={sourcesError}
              action={
                <Button variant="outline" size="sm" onClick={() => void fetchSources(false)}>
                  Try Again
                </Button>
              }
            />
          )}

          {/* Sources List / Empty / Loading */}
          {isLoadingSources && sources.length === 0 ? (
            <LoadingState message="Loading course materials..." />
          ) : sources.length === 0 ? (
            <EmptyState
              title="No materials uploaded yet"
              description="Ground your AI tutor with lecture slides (.pptx), textbook chapters or notes (.pdf), transcripts (.vtt, .srt), or structured text (.txt, .json)."
              action={
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => setIsUploadOpen(true)}
                  leftIcon={<UploadCloudIcon />}
                >
                  Upload Your First Material
                </Button>
              }
            />
          ) : filteredSources.length === 0 ? (
            <div className="p-8 text-center text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted">
              No materials match your search query or filter.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
              {filteredSources.map((source) => (
                <Card
                  key={source.id}
                  className="p-3.5 sm:p-4 flex flex-col justify-between transition-all hover:border-surface-border-strong dark:hover:border-dark-border-strong"
                >
                  <div>
                    {/* Header: Type, Status, File Name */}
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {renderSourceTypeBadge(source.source_type, source.original_filename)}
                        {renderSourceStatusBadge(source.status, source.stage)}
                      </div>
                      <span className="text-[11px] font-mono text-surface-text-muted dark:text-dark-text-muted shrink-0">
                        {formatBytes(
                          typeof source.meta?.file_size_bytes === 'number'
                            ? (source.meta.file_size_bytes as number)
                            : undefined
                        )}
                      </span>
                    </div>

                    {/* Title */}
                    <h4 className="text-sm sm:text-base font-semibold text-surface-text dark:text-dark-text line-clamp-1">
                      {source.title || source.original_filename}
                    </h4>
                    <p className="text-xs text-surface-text-muted dark:text-dark-text-muted font-mono truncate mt-0.5">
                      {source.original_filename}
                    </p>

                    {/* Progress Bar if processing */}
                    {source.status === 'processing' && (
                      <div className="mt-3 space-y-1">
                        <div className="flex justify-between text-[11px] text-surface-text-muted dark:text-dark-text-muted">
                          <span>{source.stage || 'Extracting units...'}</span>
                          <span>{source.progress}%</span>
                        </div>
                        <div className="w-full bg-surface-muted dark:bg-dark-muted h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-amber-600 dark:bg-amber-500 h-full transition-all duration-300"
                            style={{ width: `${Math.max(8, source.progress)}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Error display if failed */}
                    {source.status === 'failed' && source.error && (
                      <div className="mt-2 p-2 rounded bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-[11px] text-rose-800 dark:text-rose-300">
                        <div className="flex items-center gap-1 font-semibold mb-0.5">
                          <AlertCircleIcon className="w-3.5 h-3.5 shrink-0" />
                          <span>Ingestion failed:</span>
                        </div>
                        <p className="line-clamp-2">{source.error}</p>
                      </div>
                    )}

                    {/* Media URL if present */}
                    {source.media_url && (
                      <div className="mt-2 text-[11px] text-surface-text-muted dark:text-dark-text-muted truncate">
                        🔗 <span className="font-mono">{source.media_url}</span>
                      </div>
                    )}
                  </div>

                  {/* Footer & Actions */}
                  <div className="mt-4 pt-3 border-t border-surface-border dark:border-dark-border flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2 text-xs text-surface-text-muted dark:text-dark-text-muted">
                      <span className="inline-flex items-center gap-1">
                        <LayersIcon className="w-3.5 h-3.5" />
                        <strong>{source.chunk_count}</strong> chunks
                      </span>
                    </div>

                    <div className="flex items-center gap-1 sm:gap-1.5">
                      {/* Retry button (only if failed) */}
                      {source.status === 'failed' && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => void handleRetry(source.id)}
                          disabled={retryingSourceId === source.id}
                          leftIcon={
                            <RefreshCwIcon
                              className={`w-3.5 h-3.5 ${
                                retryingSourceId === source.id ? 'animate-spin' : ''
                              }`}
                            />
                          }
                          className="text-xs text-amber-700 dark:text-amber-400"
                        >
                          Retry
                        </Button>
                      )}

                      {/* View Chunks button */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => void handleViewChunks(source)}
                        leftIcon={<LayersIcon className="w-3.5 h-3.5" />}
                        className="text-xs"
                      >
                        Chunks
                      </Button>

                      {/* Download Original File */}
                      <a
                        href={getSourceFileUrl(source.id)}
                        download={source.original_filename}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center justify-center p-1.5 rounded-lg text-surface-text-muted hover:text-surface-text hover:bg-surface-muted dark:hover:bg-dark-muted transition-colors cursor-pointer"
                        title="Download original file"
                        aria-label={`Download ${source.original_filename}`}
                      >
                        <DownloadIcon className="w-4 h-4" />
                      </a>

                      {/* Delete button */}
                      <button
                        type="button"
                        onClick={() => setDeletingSource(source)}
                        className="p-1.5 rounded-lg text-surface-text-muted hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors cursor-pointer"
                        title="Delete source"
                        aria-label={`Delete ${source.title || source.original_filename}`}
                      >
                        <Trash2Icon className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Upload Source Modal */}
      <Modal
        isOpen={isUploadOpen}
        onClose={() => {
          if (!isUploading) {
            setIsUploadOpen(false)
            setSelectedFile(null)
            setUploadError(null)
          }
        }}
        title="Upload Course Material"
        description="Ingest lecture slides, readings, or video transcripts to empower the AI tutor."
        maxWidth="lg"
      >
        <form onSubmit={(e) => void handleUploadSubmit(e)} className="space-y-4">
          {uploadError && (
            <Alert variant="error" title="Upload error" description={uploadError} />
          )}

          {/* Drag & Drop Zone */}
          <div>
            <label
              htmlFor={fileInputId}
              className="block text-xs font-semibold text-surface-text dark:text-dark-text mb-1.5"
            >
              Source File <span className="text-rose-500">*</span>
            </label>
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setIsDragging(true)
              }}
              onDragLeave={(e) => {
                e.preventDefault()
                setIsDragging(false)
              }}
              onDrop={(e) => {
                e.preventDefault()
                setIsDragging(false)
                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                  handleFileSelect(e.dataTransfer.files[0])
                }
              }}
              className={`border-2 border-dashed rounded-xl p-5 text-center transition-all cursor-pointer ${
                isDragging
                  ? 'border-brand-500 bg-brand-50/50 dark:bg-brand-950/30'
                  : selectedFile
                  ? 'border-brand-600 bg-brand-50/20 dark:bg-brand-950/20'
                  : 'border-surface-border dark:border-dark-border hover:border-surface-border-strong dark:hover:border-dark-border-strong bg-surface-muted/30 dark:bg-dark-muted/20'
              }`}
              onClick={() => {
                const el = document.getElementById(fileInputId) as HTMLInputElement | null
                el?.click()
              }}
            >
              <input
                id={fileInputId}
                type="file"
                accept={ALLOWED_EXTENSIONS.join(',')}
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileSelect(e.target.files[0])
                  }
                }}
              />

              {selectedFile ? (
                <div className="space-y-2">
                  <div className="w-10 h-10 rounded-lg bg-brand-100 dark:bg-brand-900/40 text-brand-700 dark:text-brand-300 flex items-center justify-center mx-auto">
                    <FileTextIcon className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-surface-text dark:text-dark-text truncate max-w-xs mx-auto">
                      {selectedFile.name}
                    </div>
                    <div className="text-xs text-surface-text-muted dark:text-dark-text-muted">
                      {formatBytes(selectedFile.size)} • Click or drop another to replace
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="w-10 h-10 rounded-lg bg-surface-muted dark:bg-dark-muted text-surface-text-muted dark:text-dark-text-muted flex items-center justify-center mx-auto">
                    <UploadCloudIcon className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xs sm:text-sm font-semibold text-surface-text dark:text-dark-text">
                      Click to browse or drag and drop file here
                    </div>
                    <div className="text-[11px] text-surface-text-muted dark:text-dark-text-muted mt-0.5">
                      Supported: PDF, PPTX, VTT, SRT, TXT, JSON (max 50 MB)
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Title Input */}
          <div>
            <label className="block text-xs font-semibold text-surface-text dark:text-dark-text mb-1">
              Title <span className="text-surface-text-muted dark:text-dark-text-muted font-normal">(optional)</span>
            </label>
            <Input
              type="text"
              placeholder="e.g. Chapter 3: Networking Fundamentals"
              value={uploadTitle}
              onChange={(e) => setUploadTitle(e.target.value)}
              disabled={isUploading}
            />
          </div>

          {/* Media URL Input */}
          <div>
            <label className="block text-xs font-semibold text-surface-text dark:text-dark-text mb-1">
              Associated Video / Media URL <span className="text-surface-text-muted dark:text-dark-text-muted font-normal">(optional, for transcripts)</span>
            </label>
            <Input
              type="url"
              placeholder="https://youtube.com/watch?v=..."
              value={uploadMediaUrl}
              onChange={(e) => setUploadMediaUrl(e.target.value)}
              disabled={isUploading}
            />
          </div>

          {/* Modal Actions */}
          <div className="pt-2 flex items-center justify-end gap-2 border-t border-surface-border dark:border-dark-border">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsUploadOpen(false)}
              disabled={isUploading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={!selectedFile || isUploading}
              leftIcon={
                isUploading ? (
                  <RefreshCwIcon className="animate-spin" />
                ) : (
                  <PlusIcon />
                )
              }
            >
              {isUploading ? 'Uploading & Ingesting...' : 'Upload & Process'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Chunks Viewer Modal */}
      <Modal
        isOpen={Boolean(selectedSourceForChunks)}
        onClose={() => setSelectedSourceForChunks(null)}
        title={selectedSourceForChunks?.title || 'Extracted Chunks'}
        description={`Displaying vector chunks extracted from ${
          selectedSourceForChunks?.original_filename || 'source'
        }.`}
        maxWidth="2xl"
      >
        <div className="space-y-4">
          {isLoadingChunks ? (
            <LoadingState message="Fetching source chunks..." />
          ) : chunksError ? (
            <Alert variant="error" title="Failed to load chunks" description={chunksError} />
          ) : chunks.length === 0 ? (
            <div className="p-6 text-center text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted">
              No chunks have been generated for this source yet. If ingestion is in progress, check back in a few seconds.
            </div>
          ) : (
            <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
              <div className="flex items-center justify-between text-xs text-surface-text-muted dark:text-dark-text-muted pb-2 border-b border-surface-border dark:border-dark-border">
                <span>Total Chunks: <strong className="text-surface-text dark:text-dark-text">{chunks.length}</strong></span>
                <span>Avg tokens: <strong className="text-surface-text dark:text-dark-text">
                  {Math.round(chunks.reduce((acc, c) => acc + c.token_count, 0) / (chunks.length || 1))}
                </strong></span>
              </div>

              {chunks.map((chunk) => (
                <div
                  key={chunk.id}
                  className="p-3 sm:p-4 rounded-lg bg-surface-muted/40 dark:bg-dark-muted/30 border border-surface-border dark:border-dark-border space-y-2 text-xs"
                >
                  <div className="flex flex-wrap items-center justify-between gap-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold text-brand-700 dark:text-brand-400">
                        Chunk #{chunk.chunk_index}
                      </span>
                      {chunk.page_number && (
                        <span className="text-surface-text-muted dark:text-dark-text-muted">
                          Page {chunk.page_number}
                        </span>
                      )}
                      {chunk.slide_number && (
                        <span className="text-surface-text-muted dark:text-dark-text-muted">
                          Slide {chunk.slide_number}
                        </span>
                      )}
                      {chunk.section_title && (
                        <span className="text-surface-text-muted dark:text-dark-text-muted italic truncate max-w-xs">
                          {chunk.section_title}
                        </span>
                      )}
                    </div>
                    <span className="font-mono text-[11px] text-surface-text-muted dark:text-dark-text-muted">
                      {chunk.token_count} tokens
                    </span>
                  </div>

                  <p className="font-mono text-[11px] sm:text-xs text-surface-text dark:text-dark-text whitespace-pre-wrap leading-relaxed max-h-40 overflow-y-auto bg-surface-card dark:bg-dark-card p-2.5 rounded border border-surface-border/50 dark:border-dark-border/50">
                    {chunk.text}
                  </p>
                </div>
              ))}
            </div>
          )}

          <div className="pt-2 flex justify-end border-t border-surface-border dark:border-dark-border">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedSourceForChunks(null)}
            >
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={Boolean(deletingSource)}
        onClose={() => {
          if (!isDeleting) setDeletingSource(null)
        }}
        title="Delete Course Material"
        description="Are you sure you want to delete this source? This will permanently remove the original file, all extracted chunks, and vector embeddings."
        maxWidth="sm"
      >
        <div className="space-y-4">
          {deletingSource && (
            <div className="p-3 rounded-lg bg-surface-muted dark:bg-dark-muted border border-surface-border dark:border-dark-border text-xs">
              <div className="font-semibold text-surface-text dark:text-dark-text truncate">
                {deletingSource.title || deletingSource.original_filename}
              </div>
              <div className="font-mono text-surface-text-muted dark:text-dark-text-muted mt-0.5">
                {deletingSource.original_filename} • {deletingSource.chunk_count} chunks
              </div>
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-surface-border dark:border-dark-border">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeletingSource(null)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => void handleDeleteConfirm()}
              disabled={isDeleting}
              leftIcon={
                isDeleting ? (
                  <RefreshCwIcon className="animate-spin" />
                ) : (
                  <Trash2Icon />
                )
              }
            >
              {isDeleting ? 'Deleting...' : 'Delete Material'}
            </Button>
          </div>
        </div>
      </Modal>
    </PageContainer>
  )
}
