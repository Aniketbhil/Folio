import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useStudent } from '../context/useStudent'
import { useCourse } from '../context/useCourse'
import {
  createConversation,
  deleteConversation,
  getConversationMessages,
  listCourseConversations,
  sendConversationMessage,
} from '../api/tutor'
import { getSourceFileUrl } from '../api/sources'
import type {
  ConversationListItem,
  GroundingStatus,
  MessageRead,
  TutorCitation,
} from '../types/tutor'
import { PageContainer, PageHeader } from '../components/layout/PageContainer'
import { Button } from '../components/ui/Button'
import { Card, CardDescription, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Modal } from '../components/ui/Modal'
import { Alert, LoadingState } from '../components/ui/Feedback'
import {
  AlertCircleIcon,
  ArrowRightIcon,
  BookOpenIcon,
  ChevronDownIcon,
  ExternalLinkIcon,
  FileTextIcon,
  MessageSquareIcon,
  PlusIcon,
  RefreshCwIcon,
  SendIcon,
  SparklesIcon,
  Trash2Icon,
  UserIcon,
} from '../components/ui/Icons'

export const TutorPage: React.FC = () => {
  const { activeStudent, students } = useStudent()
  const { activeCourse, activeCourseDetail, courses } = useCourse()

  // Conversations list for active student & course
  const [conversations, setConversations] = useState<ConversationListItem[]>([])
  const [isLoadingConvs, setIsLoadingConvs] = useState(false)
  const [convsError, setConvsError] = useState<string | null>(null)
  const [activeConvId, setActiveConvId] = useState<number | null>(null)

  // Messages in active conversation
  const [messages, setMessages] = useState<MessageRead[]>([])
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)

  // Composer state
  const [inputContent, setInputContent] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)

  // Mobile sessions toggle
  const [mobileSessionsOpen, setMobileSessionsOpen] = useState(false)

  // Delete conversation modal
  const [deletingConv, setDeletingConv] = useState<ConversationListItem | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  // Selected citation for inspection modal
  const [inspectedCitation, setInspectedCitation] = useState<TutorCitation | null>(null)

  // Chat scroll container ref
  const chatBottomRef = useRef<HTMLDivElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const tempIdCounterRef = useRef(1)

  // Auto-scroll to bottom of messages
  const scrollToBottom = () => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // 1. Fetch conversations when course or student changes
  useEffect(() => {
    if (!activeCourse || !activeStudent) {
      const timer = window.setTimeout(() => {
        setConversations([])
        setActiveConvId(null)
        setMessages([])
      }, 0)
      return () => {
        clearTimeout(timer)
      }
    }

    let isMounted = true
    const courseId = activeCourse.id
    const studentId = activeStudent.id

    listCourseConversations(courseId, studentId)
      .then((data) => {
        if (isMounted) {
          setConversations(data)
          setIsLoadingConvs(false)
          // Default to the first conversation if available, or null
          setActiveConvId((prev) => {
            if (prev && data.some((c) => c.id === prev)) {
              return prev
            }
            return data.length > 0 ? data[0].id : null
          })
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setConvsError(err instanceof Error ? err.message : 'Failed to load conversations.')
          setIsLoadingConvs(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [activeCourse, activeStudent])

  // 2. Fetch messages when activeConvId changes
  useEffect(() => {
    if (!activeConvId) {
      const timer = window.setTimeout(() => {
        setMessages([])
      }, 0)
      return () => {
        clearTimeout(timer)
      }
    }

    let isMounted = true
    const currentConvId = activeConvId

    getConversationMessages(currentConvId)
      .then((data) => {
        if (isMounted && currentConvId === activeConvId) {
          setMessages(data)
          setIsLoadingMessages(false)
          setTimeout(scrollToBottom, 50)
        }
      })
      .catch((err: unknown) => {
        if (isMounted && currentConvId === activeConvId) {
          setMessagesError(err instanceof Error ? err.message : 'Failed to load message history.')
          setIsLoadingMessages(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [activeConvId])

  // Create a new conversation session
  const handleCreateConversation = async () => {
    if (!activeCourse || !activeStudent) return
    try {
      const newConv = await createConversation(activeCourse.id, {
        student_id: activeStudent.id,
        title: `Study Session #${conversations.length + 1}`,
      })
      const asListItem: ConversationListItem = {
        id: newConv.id,
        course_id: newConv.course_id,
        student_id: newConv.student_id,
        title: newConv.title,
        created_at: newConv.created_at,
        updated_at: newConv.updated_at,
        message_count: 0,
        last_message_preview: null,
      }
      setConversations((prev) => [asListItem, ...prev])
      setActiveConvId(newConv.id)
      setMessages([])
      setMobileSessionsOpen(false)
      // Focus textarea
      setTimeout(() => textareaRef.current?.focus(), 100)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to create conversation.')
    }
  }

  // Delete conversation session
  const handleDeleteConversation = async () => {
    if (!deletingConv) return
    setIsDeleting(true)
    try {
      await deleteConversation(deletingConv.id)
      const remaining = conversations.filter((c) => c.id !== deletingConv.id)
      setConversations(remaining)
      if (activeConvId === deletingConv.id) {
        setActiveConvId(remaining.length > 0 ? remaining[0].id : null)
      }
      setDeletingConv(null)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to delete conversation.')
    } finally {
      setIsDeleting(false)
    }
  }

  // Send message
  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend ?? inputContent).trim()
    if (!text || isSending || !activeCourse || !activeStudent) return

    setSendError(null)

    let targetConvId = activeConvId

    // If no active conversation exists, auto-create one first
    if (!targetConvId) {
      try {
        const titleSnippet = text.length > 30 ? `${text.slice(0, 30)}...` : text
        const created = await createConversation(activeCourse.id, {
          student_id: activeStudent.id,
          title: titleSnippet,
        })
        targetConvId = created.id
        setActiveConvId(created.id)
        const asListItem: ConversationListItem = {
          id: created.id,
          course_id: created.course_id,
          student_id: created.student_id,
          title: created.title,
          created_at: created.created_at,
          message_count: 0,
        }
        setConversations((prev) => [asListItem, ...prev])
      } catch (err: unknown) {
        setSendError(err instanceof Error ? err.message : 'Failed to initiate conversation session.')
        return
      }
    }

    // Add optimistic user message to the UI
    const optimisticUserMsg: MessageRead = {
      id: tempIdCounterRef.current++,
      role: 'user',
      content: text,
      citations: [],
      followups: [],
      related_topics: [],
      created_at: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, optimisticUserMsg])
    setInputContent('')
    setIsSending(true)
    setTimeout(scrollToBottom, 30)

    try {
      const response = await sendConversationMessage(targetConvId, {
        content: text,
        student_id: activeStudent.id,
      })

      // Formulate assistant MessageRead
      const assistantMsg: MessageRead = {
        id: response.message_id || response.assistant_message_id || tempIdCounterRef.current++,
        role: 'assistant',
        content: response.answer,
        grounding: response.grounding,
        citations: response.citations || [],
        outside_knowledge_note: response.outside_knowledge_note,
        followups: response.followups || [],
        related_topics: response.related_topics || [],
        mastery_nudge: response.mastery_nudge,
        created_at: new Date().toISOString(),
      }

      setMessages((prev) => [...prev, assistantMsg])

      // Update preview in conversation list
      setConversations((prev) =>
        prev.map((c) =>
          c.id === targetConvId
            ? {
                ...c,
                message_count: c.message_count + 2,
                last_message_preview: response.answer.slice(0, 80),
              }
            : c
        )
      )
    } catch (err: unknown) {
      setSendError(err instanceof Error ? err.message : 'Tutor request failed.')
    } finally {
      setIsSending(false)
      setTimeout(scrollToBottom, 50)
    }
  }

  // Keydown handler: Enter sends, Shift+Enter newlines
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSendMessage()
    }
  }

  // Format citation location
  const formatCitationLocation = (loc: TutorCitation['location'], type: string) => {
    const t = type.toLowerCase()
    if (t === 'pdf' && loc.page_number) {
      return `Page ${loc.page_number}`
    }
    if (t === 'slide' && loc.slide_number) {
      return `Slide ${loc.slide_number}`
    }
    if ((t === 'video' || t === 'video_transcript') && loc.start_sec !== undefined && loc.start_sec !== null) {
      const sm = Math.floor(Number(loc.start_sec) / 60)
      const ss = Math.floor(Number(loc.start_sec) % 60)
      const em = Math.floor(Number(loc.end_sec ?? loc.start_sec) / 60)
      const es = Math.floor(Number(loc.end_sec ?? loc.start_sec) % 60)
      return `${String(sm).padStart(2, '0')}:${String(ss).padStart(2, '0')} - ${String(em).padStart(2, '0')}:${String(es).padStart(2, '0')}`
    }
    return 'Course Material'
  }

  // Grounding status badge helper
  const renderGroundingBadge = (status?: GroundingStatus) => {
    if (!status) return null
    switch (status) {
      case 'grounded':
        return (
          <Badge variant="brand" size="sm" dot>
            Grounded in Course Material
          </Badge>
        )
      case 'partial':
        return (
          <Badge variant="amber" size="sm" dot>
            Partially Grounded
          </Badge>
        )
      case 'unsupported':
        return (
          <Badge variant="error" size="sm" dot>
            Outside Knowledge
          </Badge>
        )
      default:
        return null
    }
  }

  const hasSources = (activeCourseDetail?.counts.sources ?? 0) > 0

  return (
    <PageContainer maxWidth="wide">
      {/* Header */}
      <PageHeader
        title="Grounded AI Tutor"
        description="Ask Socratic questions strictly grounded in your course materials with verbatim citations and topic references."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (activeConvId) {
                  setIsLoadingMessages(true)
                  void getConversationMessages(activeConvId).then((data) => {
                    setMessages(data)
                    setIsLoadingMessages(false)
                  })
                }
              }}
              disabled={isLoadingMessages || !activeConvId}
              leftIcon={<RefreshCwIcon className={isLoadingMessages ? 'animate-spin' : ''} />}
            >
              Refresh Chat
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => void handleCreateConversation()}
              disabled={!activeCourse || !activeStudent}
              leftIcon={<PlusIcon />}
            >
              New Chat
            </Button>
          </div>
        }
      />

      {/* State A: Missing Course or Student Selection */}
      {!activeCourse || !activeStudent ? (
        <Card className="p-6 text-center border-dashed border-2 border-surface-border dark:border-dark-border">
          <div className="max-w-md mx-auto space-y-4">
            <div className="w-12 h-12 rounded-xl bg-brand-50 dark:bg-brand-950/40 text-brand-700 dark:text-brand-300 flex items-center justify-center mx-auto">
              <MessageSquareIcon className="w-6 h-6" />
            </div>
            <div>
              <CardTitle className="text-lg">Tutor Context Incomplete</CardTitle>
              <CardDescription className="mt-1">
                The AI Tutor requires both an <strong>active student profile</strong> (to track
                mastery) and an <strong>active course syllabus</strong> (to retrieve source chunks).
              </CardDescription>
            </div>

            <div className="pt-2 flex flex-wrap items-center justify-center gap-3">
              {!activeStudent && (
                <Link to="/students">
                  <Button variant="primary" size="sm" leftIcon={<UserIcon />}>
                    {students.length > 0 ? 'Select Active Student' : 'Create Student Profile'}
                  </Button>
                </Link>
              )}
              {!activeCourse && (
                <Link to="/courses">
                  <Button variant="secondary" size="sm" leftIcon={<BookOpenIcon />}>
                    {courses.length > 0 ? 'Select Active Course' : 'Create Course Syllabus'}
                  </Button>
                </Link>
              )}
            </div>
          </div>
        </Card>
      ) : (
        <div className="space-y-3">
          {/* KB Empty / Warning Notice */}
          {!hasSources && (
            <Alert
              variant="warning"
              title="No Ingested Materials in this Course"
              description="This course has 0 uploaded sources. The tutor operates in strict source-grounded mode and will politely refuse questions that cannot be substantiated by verified course documents."
              action={
                <Link to="/sources">
                  <Button variant="outline" size="sm" rightIcon={<ArrowRightIcon />}>
                    Upload Course Materials
                  </Button>
                </Link>
              }
            />
          )}

          {/* Main Tutor Workspace: Side Sessions List + Active Conversation Pane */}
          <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-5 gap-4 h-[calc(100vh-250px)] min-h-125">
            {/* Mobile Sessions Toggle Button */}
            <div className="md:hidden flex items-center justify-between p-2 rounded-lg bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border text-xs">
              <button
                type="button"
                onClick={() => setMobileSessionsOpen(!mobileSessionsOpen)}
                className="flex items-center gap-1.5 font-medium text-surface-text dark:text-dark-text cursor-pointer"
              >
                <MessageSquareIcon className="w-4 h-4 text-brand-600" />
                <span>
                  {conversations.find((c) => c.id === activeConvId)?.title || 'Sessions'} (
                  {conversations.length})
                </span>
                <ChevronDownIcon className="w-3.5 h-3.5" />
              </button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleCreateConversation()}
                leftIcon={<PlusIcon className="w-3.5 h-3.5" />}
              >
                New
              </Button>
            </div>

            {/* Sessions Sidebar (Desktop: column 1; Mobile: conditional dropdown) */}
            <div
              className={`${
                mobileSessionsOpen ? 'block' : 'hidden'
              } md:block md:col-span-1 lg:col-span-1 bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border rounded-xl p-3 flex flex-col justify-between overflow-hidden`}
            >
              <div className="flex-1 flex flex-col min-h-0">
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-surface-border dark:border-dark-border shrink-0">
                  <span className="text-xs font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
                    Conversations
                  </span>
                  <button
                    type="button"
                    onClick={() => void handleCreateConversation()}
                    className="p-1 rounded text-surface-text-muted hover:text-surface-text hover:bg-surface-muted dark:hover:bg-dark-muted transition-colors cursor-pointer"
                    title="Create new session"
                  >
                    <PlusIcon className="w-4 h-4" />
                  </button>
                </div>

                {isLoadingConvs ? (
                  <LoadingState message="Loading sessions..." className="p-4" />
                ) : convsError ? (
                  <div className="text-xs text-red-600 p-2">{convsError}</div>
                ) : conversations.length === 0 ? (
                  <div className="p-4 text-center text-xs text-surface-text-muted dark:text-dark-text-muted space-y-2">
                    <p>No previous conversations.</p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handleCreateConversation()}
                      className="w-full text-xs"
                    >
                      Start First Chat
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-1 overflow-y-auto flex-1 pr-1">
                    {conversations.map((conv) => {
                      const isActive = conv.id === activeConvId
                      return (
                        <div
                          key={conv.id}
                          className={`group flex items-center justify-between p-2 rounded-lg text-xs transition-colors cursor-pointer ${
                            isActive
                              ? 'bg-brand-50 text-brand-900 dark:bg-brand-950/60 dark:text-brand-200 font-semibold border border-brand-200 dark:border-brand-900/60'
                              : 'text-surface-text-muted hover:text-surface-text hover:bg-surface-muted dark:hover:bg-dark-muted border border-transparent'
                          }`}
                          onClick={() => {
                            setActiveConvId(conv.id)
                            setMobileSessionsOpen(false)
                          }}
                        >
                          <div className="min-w-0 flex-1 pr-1">
                            <div className="truncate">{conv.title}</div>
                            {conv.last_message_preview && (
                              <div className="text-[10px] text-surface-text-muted/70 dark:text-dark-text-muted/60 truncate font-normal">
                                {conv.last_message_preview}
                              </div>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              setDeletingConv(conv)
                            }}
                            className="opacity-0 group-hover:opacity-100 p-1 text-surface-text-muted hover:text-red-600 dark:hover:text-red-400 transition-opacity cursor-pointer shrink-0"
                            title="Delete session"
                          >
                            <Trash2Icon className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Active Context Footnote */}
              <div className="pt-2 mt-2 border-t border-surface-border dark:border-dark-border text-[11px] text-surface-text-muted dark:text-dark-text-muted shrink-0 space-y-0.5">
                <div className="truncate font-medium text-surface-text dark:text-dark-text">
                  {activeCourse.name}
                </div>
                <div className="truncate text-xs">Learner: {activeStudent.name}</div>
              </div>
            </div>

            {/* Main Chat Pane (Desktop: columns 2-5) */}
            <div className="md:col-span-3 lg:col-span-4 bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border rounded-xl flex flex-col justify-between overflow-hidden shadow-xs">
              {/* Conversation Topbar */}
              <div className="p-3 sm:px-4 border-b border-surface-border dark:border-dark-border flex items-center justify-between shrink-0 bg-surface-muted/30 dark:bg-dark-muted/20">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-brand-50 dark:bg-brand-950/60 text-brand-700 dark:text-brand-300 flex items-center justify-center shrink-0">
                    <SparklesIcon className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-xs sm:text-sm font-semibold text-surface-text dark:text-dark-text truncate">
                      {conversations.find((c) => c.id === activeConvId)?.title ||
                        'Socratic Tutor Session'}
                    </h3>
                    <p className="text-[11px] text-surface-text-muted dark:text-dark-text-muted">
                      Source-grounded &bull; Bayesian Knowledge Tracing enabled
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="text-[11px] text-surface-text-muted dark:text-dark-text-muted hidden sm:inline">
                    {messages.length} message{messages.length === 1 ? '' : 's'}
                  </span>
                </div>
              </div>

              {/* Messages Scroll Area */}
              <div className="flex-1 p-3 sm:p-5 overflow-y-auto space-y-4">
                {isLoadingMessages && messages.length === 0 ? (
                  <LoadingState message="Retrieving conversation history..." />
                ) : messagesError ? (
                  <Alert variant="error" title="Could not load messages" description={messagesError} />
                ) : messages.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-3">
                    <div className="w-12 h-12 rounded-full bg-brand-50 dark:bg-brand-950/40 text-brand-700 dark:text-brand-300 flex items-center justify-center">
                      <SparklesIcon className="w-6 h-6" />
                    </div>
                    <div className="max-w-md space-y-1">
                      <h4 className="text-sm sm:text-base font-semibold text-surface-text dark:text-dark-text">
                        How can I help you learn today?
                      </h4>
                      <p className="text-xs text-surface-text-muted dark:text-dark-text-muted leading-relaxed">
                        Ask conceptual questions, request explanations with examples, or test your
                        understanding. All answers reference verified course materials.
                      </p>
                    </div>

                    {/* Starter Prompt Suggestions */}
                    <div className="pt-2 flex flex-wrap items-center justify-center gap-2 max-w-lg">
                      {[
                        'What are the core fundamentals of this course?',
                        'Can you explain the most challenging concept step by step?',
                        'Quiz me on the main topics covered so far.',
                      ].map((prompt, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => void handleSendMessage(prompt)}
                          className="px-2.5 py-1.5 rounded-lg text-xs bg-surface-muted/70 hover:bg-surface-muted dark:bg-dark-muted/60 dark:hover:bg-dark-muted text-surface-text dark:text-dark-text border border-surface-border dark:border-dark-border transition-colors text-left cursor-pointer"
                        >
                          &ldquo;{prompt}&rdquo;
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map((msg) => {
                    const isUser = msg.role === 'user'

                    return (
                      <div
                        key={msg.id}
                        className={`flex gap-2.5 sm:gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
                      >
                        {/* Assistant Avatar */}
                        {!isUser && (
                          <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-brand-50 dark:bg-brand-950 text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-900 flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold">
                            F
                          </div>
                        )}

                        {/* Message Body */}
                        <div
                          className={`max-w-[85%] sm:max-w-[80%] rounded-2xl p-3 sm:p-4 text-xs sm:text-sm space-y-2.5 shadow-xs ${
                            isUser
                              ? 'bg-brand-700 text-white dark:bg-brand-600 rounded-br-xs'
                              : 'bg-surface-muted/40 dark:bg-dark-muted/40 border border-surface-border dark:border-dark-border text-surface-text dark:text-dark-text rounded-bl-xs'
                          }`}
                        >
                          {/* Grounding Header for Assistant */}
                          {!isUser && msg.grounding && (
                            <div className="flex items-center gap-2 pb-1 border-b border-surface-border/60 dark:border-dark-border/60">
                              {renderGroundingBadge(msg.grounding)}
                            </div>
                          )}

                          {/* Message Content */}
                          <div className="leading-relaxed whitespace-pre-wrap font-sans">
                            {msg.content}
                          </div>

                          {/* Outside Knowledge Note */}
                          {!isUser && msg.outside_knowledge_note && (
                            <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 text-[11px] text-amber-900 dark:text-amber-200 flex items-start gap-1.5">
                              <AlertCircleIcon className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                              <span>{msg.outside_knowledge_note}</span>
                            </div>
                          )}

                          {/* Verified Source Citations Section */}
                          {!isUser && msg.citations && msg.citations.length > 0 && (
                            <div className="pt-2 border-t border-surface-border/60 dark:border-dark-border/60 space-y-1.5">
                              <span className="text-[10px] font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted">
                                Verified Sources ({msg.citations.length})
                              </span>
                              <div className="flex flex-wrap gap-1.5">
                                {msg.citations.map((cite) => (
                                  <button
                                    key={cite.chunk_id}
                                    type="button"
                                    onClick={() => setInspectedCitation(cite)}
                                    className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-mono bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border hover:border-brand-500 text-surface-text dark:text-dark-text transition-colors cursor-pointer"
                                  >
                                    <span className="font-bold text-brand-700 dark:text-brand-400">
                                      [{cite.ref}]
                                    </span>
                                    <span className="truncate max-w-32">{cite.source_title}</span>
                                    <span className="text-surface-text-muted text-[10px]">
                                      ({formatCitationLocation(cite.location, cite.source_type)})
                                    </span>
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Related Topics */}
                          {!isUser && msg.related_topics && msg.related_topics.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1 pt-1 text-[11px]">
                              <span className="text-surface-text-muted dark:text-dark-text-muted text-[10px] uppercase font-semibold">
                                Topics:
                              </span>
                              {msg.related_topics.map((t) => (
                                <span
                                  key={t.id}
                                  className="px-1.5 py-0.5 rounded bg-surface-muted dark:bg-dark-muted text-surface-text-muted dark:text-dark-text-muted text-[10px] border border-surface-border dark:border-dark-border"
                                >
                                  {t.name}
                                </span>
                              ))}
                            </div>
                          )}

                          {/* Follow-up Prompts */}
                          {!isUser && msg.followups && msg.followups.length > 0 && (
                            <div className="pt-2 border-t border-surface-border/60 dark:border-dark-border/60 space-y-1">
                              <span className="text-[10px] font-semibold uppercase tracking-wider text-surface-text-muted dark:text-dark-text-muted flex items-center gap-1">
                                <SparklesIcon className="w-3 h-3 text-brand-600" /> Suggested
                                Follow-ups:
                              </span>
                              <div className="flex flex-wrap gap-1">
                                {msg.followups.map((f, i) => (
                                  <button
                                    key={i}
                                    type="button"
                                    onClick={() => void handleSendMessage(f)}
                                    className="text-left px-2 py-1 rounded-md text-xs bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border hover:border-brand-500 text-surface-text dark:text-dark-text transition-colors cursor-pointer"
                                  >
                                    &rarr; {f}
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>

                        {/* User Avatar */}
                        {isUser && (
                          <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-surface-muted dark:bg-dark-muted text-surface-text-muted dark:text-dark-text-muted border border-surface-border dark:border-dark-border flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold">
                            {activeStudent.name.charAt(0).toUpperCase()}
                          </div>
                        )}
                      </div>
                    )
                  })
                )}

                {/* Live Thinking / Synthesis Indicator */}
                {isSending && (
                  <div className="flex gap-2.5 sm:gap-3 items-start justify-start">
                    <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-brand-50 dark:bg-brand-950 text-brand-700 dark:text-brand-300 border border-brand-200 dark:border-brand-900 flex items-center justify-center shrink-0 text-xs font-bold">
                      F
                    </div>
                    <div className="rounded-2xl p-3 sm:p-4 bg-surface-muted/40 dark:bg-dark-muted/40 border border-surface-border dark:border-dark-border rounded-bl-xs text-xs space-y-1">
                      <div className="flex items-center gap-2 text-surface-text-muted dark:text-dark-text-muted">
                        <RefreshCwIcon className="w-3.5 h-3.5 animate-spin text-brand-600 dark:text-brand-400" />
                        <span>Socratic Tutor is retrieving course chunks & synthesizing...</span>
                      </div>
                    </div>
                  </div>
                )}

                <div ref={chatBottomRef} />
              </div>

              {/* Send Error Alert */}
              {sendError && (
                <div className="p-3 border-t border-surface-border dark:border-dark-border">
                  <Alert variant="error" title="Message Error" description={sendError} />
                </div>
              )}

              {/* Message Composer Area */}
              <div className="p-3 sm:p-4 border-t border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card shrink-0">
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    void handleSendMessage()
                  }}
                  className="space-y-2"
                >
                  <div className="relative rounded-xl border border-surface-border dark:border-dark-border focus-within:ring-2 focus-within:ring-brand-500 focus-within:border-brand-500 bg-surface-canvas dark:bg-dark-canvas transition-all">
                    <textarea
                      ref={textareaRef}
                      value={inputContent}
                      onChange={(e) => setInputContent(e.target.value)}
                      onKeyDown={handleKeyDown}
                      rows={2}
                      placeholder={
                        hasSources
                          ? `Ask the tutor about ${activeCourse.name}... (Enter to send, Shift+Enter for new line)`
                          : 'Course materials needed to ground tutor answers...'
                      }
                      disabled={isSending}
                      className="w-full p-2.5 sm:p-3 text-xs sm:text-sm bg-transparent text-surface-text dark:text-dark-text placeholder:text-surface-text-muted focus:outline-none resize-none leading-relaxed"
                    />

                    <div className="flex items-center justify-between p-2 pt-0">
                      <div className="text-[11px] text-surface-text-muted dark:text-dark-text-muted">
                        <span className="hidden sm:inline">Press Enter to send &bull; Shift+Enter for newline</span>
                      </div>

                      <Button
                        type="submit"
                        variant="primary"
                        size="sm"
                        disabled={!inputContent.trim() || isSending}
                        leftIcon={
                          isSending ? (
                            <RefreshCwIcon className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <SendIcon className="w-3.5 h-3.5" />
                          )
                        }
                      >
                        {isSending ? 'Sending...' : 'Send'}
                      </Button>
                    </div>
                  </div>
                </form>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Citation Detail Inspector Modal */}
      <Modal
        isOpen={Boolean(inspectedCitation)}
        onClose={() => setInspectedCitation(null)}
        title={`Citation [${inspectedCitation?.ref}]: ${inspectedCitation?.source_title || 'Source Reference'}`}
        description="Verbatim source excerpt retrieved from your ingested course library."
        maxWidth="lg"
      >
        {inspectedCitation && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-lg bg-surface-muted dark:bg-dark-muted border border-surface-border dark:border-dark-border text-xs">
              <div className="flex items-center gap-2">
                <span className="font-semibold uppercase tracking-wider font-mono">
                  {inspectedCitation.source_type}
                </span>
                <span>&bull;</span>
                <span className="font-medium">
                  {formatCitationLocation(inspectedCitation.location, inspectedCitation.source_type)}
                </span>
                {inspectedCitation.section_title && (
                  <>
                    <span>&bull;</span>
                    <span className="italic truncate max-w-44">{inspectedCitation.section_title}</span>
                  </>
                )}
              </div>

              {inspectedCitation.score !== null && inspectedCitation.score !== undefined && (
                <span className="text-[11px] font-mono text-surface-text-muted">
                  Relevance: {(inspectedCitation.score * 100).toFixed(0)}%
                </span>
              )}
            </div>

            {/* Verbatim Snippet */}
            <div className="space-y-1">
              <label className="block text-xs font-semibold text-surface-text dark:text-dark-text">
                Verbatim Chunk Snippet:
              </label>
              <div className="p-3 rounded-lg bg-surface-muted/30 dark:bg-dark-muted/30 border border-surface-border dark:border-dark-border text-xs font-mono leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
                &ldquo;{inspectedCitation.snippet}&rdquo;
              </div>
            </div>

            {/* Modal Actions */}
            <div className="pt-2 flex items-center justify-between border-t border-surface-border dark:border-dark-border">
              <a
                href={getSourceFileUrl(inspectedCitation.source_id)}
                download
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-brand-700 dark:text-brand-400 hover:underline"
              >
                <FileTextIcon className="w-3.5 h-3.5" />
                <span>Open / Download Original File</span>
                <ExternalLinkIcon className="w-3 h-3" />
              </a>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setInspectedCitation(null)}
              >
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete Conversation Confirmation Modal */}
      <Modal
        isOpen={Boolean(deletingConv)}
        onClose={() => {
          if (!isDeleting) setDeletingConv(null)
        }}
        title="Delete Conversation Session"
        description="Are you sure you want to delete this study session and all its messages? This action cannot be undone."
        maxWidth="sm"
      >
        <div className="space-y-4">
          {deletingConv && (
            <div className="p-3 rounded-lg bg-surface-muted dark:bg-dark-muted border border-surface-border dark:border-dark-border text-xs">
              <div className="font-semibold text-surface-text dark:text-dark-text truncate">
                {deletingConv.title}
              </div>
              <div className="text-surface-text-muted dark:text-dark-text-muted mt-0.5">
                {deletingConv.message_count} message(s)
              </div>
            </div>
          )}

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-surface-border dark:border-dark-border">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setDeletingConv(null)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => void handleDeleteConversation()}
              disabled={isDeleting}
              leftIcon={
                isDeleting ? (
                  <RefreshCwIcon className="animate-spin" />
                ) : (
                  <Trash2Icon />
                )
              }
            >
              {isDeleting ? 'Deleting...' : 'Delete Session'}
            </Button>
          </div>
        </div>
      </Modal>
    </PageContainer>
  )
}
