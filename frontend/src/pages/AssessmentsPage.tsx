import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  CheckCircle2,
  Clock,
  Plus,
  RefreshCw,
  Sparkles,
  Target,
  Trash2,
  XCircle,
} from "lucide-react";

import { useStudent } from "../context/useStudent";
import { useCourse } from "../context/useCourse";
import {
  createAssessment,
  createOrResumeDiagnostic,
  deleteAssessment,
  getAssessment,
  getAssessmentReport,
  listCourseAssessments,
  submitAssessment,
  submitQuestionAnswer,
} from "../api/assessments";
import { getCourseKnowledgeGraph } from "../api/mastery";
import type {
  AnswerSubmitResponse,
  AssessmentCreate,
  AssessmentDifficulty,
  AssessmentKind,
  AssessmentListItem,
  AssessmentOut,
  AssessmentReportResponse,
  QuestionConceptOut,
  QuestionOut,
  QuestionTopicOut,
  QuestionType,
  TopicScoreSummary,
} from "../types/assessment";
import type { GraphNode } from "../types/mastery";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Modal } from "../components/ui/Modal";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { Alert, LoadingState } from "../components/ui/Feedback";
import { PageContainer } from "../components/layout/PageContainer";

type ViewMode = "list" | "taking" | "report";

export const AssessmentsPage: React.FC = () => {
  const { activeStudent } = useStudent();
  const { activeCourse } = useCourse();
  const [searchParams] = useSearchParams();

  // Main state
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [assessments, setAssessments] = useState<AssessmentListItem[]>([]);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [filterKind, setFilterKind] = useState<string>("all");

  // Active taking state
  const [activeAssessment, setActiveAssessment] =
    useState<AssessmentOut | null>(null);
  const [activeQuestionIndex, setActiveQuestionIndex] = useState(0);
  const [isLoadingAssessment, setIsLoadingAssessment] = useState(false);
  const [assessmentError, setAssessmentError] = useState<string | null>(null);

  // In-flight diagnostic lock
  const isStartingDiagnosticRef = useRef(false);
  const [isStartingDiagnostic, setIsStartingDiagnostic] = useState(false);

  // Current answer state for active question
  const [currentAnswer, setCurrentAnswer] = useState<string>("");
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false);
  const [answerFeedback, setAnswerFeedback] =
    useState<AnswerSubmitResponse | null>(null);
  const [answerError, setAnswerError] = useState<string | null>(null);

  // Active report state
  const [report, setReport] = useState<AssessmentReportResponse | null>(null);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  // Question timer (tracking seconds spent on current question)
  const [questionSeconds, setQuestionSeconds] = useState(0);

  // Create Modal state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createKind, setCreateKind] = useState<AssessmentKind>("quiz");
  const [createTitle, setCreateTitle] = useState("");
  const [createDifficulty, setCreateDifficulty] =
    useState<AssessmentDifficulty>("auto");
  const [createNumQuestions, setCreateNumQuestions] = useState<number>(5);
  const [createTypes, setCreateTypes] = useState<QuestionType[]>(["mcq"]);
  const [selectedTopicId, setSelectedTopicId] = useState<string>("all");
  const [courseTopics, setCourseTopics] = useState<GraphNode[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Submit confirmation modal state
  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);
  const [isSubmittingAssessment, setIsSubmittingAssessment] = useState(false);

  // Delete confirmation modal state
  const [deleteTargetId, setDeleteTargetId] = useState<number | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Helper functions for safe display of backend fields
  const getTopicName = (
    top: QuestionTopicOut | string | undefined | null,
  ): string => {
    if (!top) return "";
    if (typeof top === "string") return top;
    return top.name || "";
  };

  const getConceptName = (
    con: QuestionConceptOut | string | undefined | null,
  ): string => {
    if (!con) return "";
    if (typeof con === "string") return con;
    return con.name || "";
  };

  const formatTopicBadgeLabel = (t: unknown): string => {
    if (!t) return "";
    if (typeof t === "string") return t;
    if (typeof t === "object") {
      const obj = t as Record<string, unknown>;
      if (obj.topic && typeof obj.topic === "object") {
        const inner = obj.topic as Record<string, unknown>;
        if (inner.name) return String(inner.name);
      }
      if (obj.name) return String(obj.name);
      if (obj.topic_name) return String(obj.topic_name);
    }
    return String(t);
  };

  const formatAnswerDisplay = (ans: unknown): string => {
    if (ans === null || ans === undefined) return "(None)";
    if (typeof ans === "string") return ans;
    if (typeof ans === "number" || typeof ans === "boolean") return String(ans);
    if (typeof ans === "object") {
      const obj = ans as Record<string, unknown>;
      if (obj.text && obj.key) return `${obj.key}: ${obj.text}`;
      if (obj.text) return String(obj.text);
      if (obj.value !== undefined)
        return `${obj.value}${obj.unit ? ` ${obj.unit}` : ""}`;
      return JSON.stringify(ans);
    }
    return String(ans);
  };

  const formatTopicSummaryName = (item: TopicScoreSummary): string => {
    if (item.topic_name) return item.topic_name;
    if (item.topic?.name) return item.topic.name;
    return `Topic #${item.topic_id || ""}`;
  };

  // Consume search params for targeted quiz creation from Mastery graph
  useEffect(() => {
    const topicIdParam = searchParams.get("topicId");
    if (topicIdParam) {
      const timer = window.setTimeout(() => {
        setSelectedTopicId(topicIdParam);
        setIsCreateModalOpen(true);
      }, 0);
      return () => clearTimeout(timer);
    }
  }, [searchParams]);

  // Manual reload assessments list
  const loadAssessments = useCallback(async () => {
    if (!activeCourse || !activeStudent) return;

    setIsLoadingList(true);
    setListError(null);
    try {
      const data = await listCourseAssessments(
        activeCourse.id,
        activeStudent.id,
      );
      setAssessments(data);
    } catch (err) {
      setListError(
        err instanceof Error ? err.message : "Failed to load assessments",
      );
    } finally {
      setIsLoadingList(false);
    }
  }, [activeCourse, activeStudent]);

  // Initial load effect
  useEffect(() => {
    if (!activeCourse || !activeStudent) {
      const timer = window.setTimeout(() => {
        setAssessments([]);
      }, 0);
      return () => clearTimeout(timer);
    }

    let isMounted = true;
    listCourseAssessments(activeCourse.id, activeStudent.id)
      .then((data) => {
        if (isMounted) {
          setAssessments(data);
          setIsLoadingList(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setListError(
            err instanceof Error ? err.message : "Failed to load assessments",
          );
          setIsLoadingList(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [activeCourse, activeStudent]);

  // Load course topics for the create modal
  useEffect(() => {
    if (!activeCourse) {
      const timer = window.setTimeout(() => setCourseTopics([]), 0);
      return () => clearTimeout(timer);
    }

    let isMounted = true;
    getCourseKnowledgeGraph(activeCourse.id)
      .then((graph) => {
        if (isMounted) {
          setCourseTopics(graph.nodes.filter((n) => n.is_leaf));
        }
      })
      .catch(() => {
        if (isMounted) setCourseTopics([]);
      });

    return () => {
      isMounted = false;
    };
  }, [activeCourse]);

  // Timer interval for question answering
  useEffect(() => {
    if (viewMode !== "taking" || !activeAssessment) return;

    const interval = window.setInterval(() => {
      setQuestionSeconds((prev) => prev + 1);
    }, 1000);

    return () => {
      window.clearInterval(interval);
    };
  }, [viewMode, activeAssessment, activeQuestionIndex]);

  // Switch active question with proper state reset
  const handleSelectQuestion = (
    index: number,
    assessmentContext?: AssessmentOut,
  ) => {
    const targetAssessment = assessmentContext || activeAssessment;
    setActiveQuestionIndex(index);
    setQuestionSeconds(0);

    if (!targetAssessment || !targetAssessment.questions) return;
    const q = targetAssessment.questions[index];
    if (q) {
      if (q.answered && q.attempt) {
        setCurrentAnswer(q.attempt.answer);
        setAnswerFeedback({
          attempt_id: q.attempt.id ?? 0,
          is_correct: q.attempt.is_correct,
          score: q.attempt.score,
          correct_answer: "",
          explanation: q.attempt.feedback || "",
          feedback: q.attempt.feedback || "",
          citations: q.sources,
          progress: {
            answered: targetAssessment.questions.filter((item) => item.answered)
              .length,
            total: targetAssessment.questions.length,
          },
        });
      } else {
        setCurrentAnswer("");
        setAnswerFeedback(null);
      }
      setAnswerError(null);
    }
  };

  // Open an assessment to take or resume
  const handleOpenAssessment = async (assessmentId: number) => {
    setIsLoadingAssessment(true);
    setAssessmentError(null);
    try {
      const data = await getAssessment(assessmentId);
      setActiveAssessment(data);
      const firstUnanswered = data.questions.findIndex((q) => !q.answered);
      const targetIndex = firstUnanswered !== -1 ? firstUnanswered : 0;
      handleSelectQuestion(targetIndex, data);
      setViewMode("taking");
    } catch (err) {
      setAssessmentError(
        err instanceof Error ? err.message : "Failed to load assessment",
      );
    } finally {
      setIsLoadingAssessment(false);
    }
  };

  // Open assessment report
  const handleOpenReport = async (assessmentId: number) => {
    setIsLoadingReport(true);
    setReportError(null);
    try {
      const data = await getAssessmentReport(assessmentId);
      setReport(data);
      setViewMode("report");
    } catch (err) {
      setReportError(
        err instanceof Error ? err.message : "Failed to load assessment report",
      );
    } finally {
      setIsLoadingReport(false);
    }
  };

  // Quick Diagnostic launch
  const handleLaunchDiagnostic = async () => {
    if (isStartingDiagnosticRef.current || !activeCourse || !activeStudent)
      return;

    isStartingDiagnosticRef.current = true;
    setIsStartingDiagnostic(true);
    setIsLoadingAssessment(true);
    setAssessmentError(null);
    setListError(null);
    try {
      const data = await createOrResumeDiagnostic(
        activeCourse.id,
        activeStudent.id,
      );
      setActiveAssessment(data);
      const firstUnanswered = data.questions.findIndex((q) => !q.answered);
      const targetIndex = firstUnanswered !== -1 ? firstUnanswered : 0;
      handleSelectQuestion(targetIndex, data);
      setViewMode("taking");
    } catch (err) {
      setListError(
        err instanceof Error ? err.message : "Failed to launch diagnostic test",
      );
    } finally {
      isStartingDiagnosticRef.current = false;
      setIsStartingDiagnostic(false);
      setIsLoadingAssessment(false);
    }
  };

  // Create custom quiz / mock exam
  const handleCreateCustomAssessment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeCourse || !activeStudent) return;

    setIsCreating(true);
    setCreateError(null);
    try {
      const payload: AssessmentCreate = {
        student_id: activeStudent.id,
        kind: createKind,
        title: createTitle.trim() || undefined,
        difficulty: createDifficulty,
        num_questions: createNumQuestions,
        question_types: createTypes.length > 0 ? createTypes : ["mcq"],
        topic_ids:
          selectedTopicId !== "all"
            ? [parseInt(selectedTopicId, 10)]
            : undefined,
      };

      const created = await createAssessment(activeCourse.id, payload);
      setIsCreateModalOpen(false);
      setActiveAssessment(created);
      handleSelectQuestion(0, created);
      setViewMode("taking");
    } catch (err) {
      setCreateError(
        err instanceof Error ? err.message : "Failed to create assessment",
      );
    } finally {
      setIsCreating(false);
    }
  };

  // Submit answer for active question
  const handleSubmitAnswer = async () => {
    if (!activeAssessment) return;
    const q = activeAssessment.questions[activeQuestionIndex];
    if (!q || !currentAnswer.trim() || !activeStudent) return;

    setIsSubmittingAnswer(true);
    setAnswerError(null);
    try {
      const res = await submitQuestionAnswer(activeAssessment.id, q.id, {
        answer: currentAnswer.trim(),
        time_taken_sec: questionSeconds,
        student_id: activeStudent.id,
      });

      setAnswerFeedback(res);

      // Update question state in active assessment
      setActiveAssessment((prev) => {
        if (!prev) return null;
        const updatedQuestions = [...prev.questions];
        updatedQuestions[activeQuestionIndex] = {
          ...q,
          answered: true,
          attempt: {
            id: res.attempt_id,
            answer: currentAnswer.trim(),
            is_correct: res.is_correct,
            score: res.score,
            feedback: res.feedback || res.explanation,
            time_taken_sec: questionSeconds,
            created_at: new Date().toISOString(),
          },
        };
        return {
          ...prev,
          questions: updatedQuestions,
        };
      });
    } catch (err) {
      setAnswerError(
        err instanceof Error ? err.message : "Failed to submit answer",
      );
    } finally {
      setIsSubmittingAnswer(false);
    }
  };

  // Finalize and submit assessment
  const handleFinalizeAssessment = async () => {
    if (!activeAssessment) return;

    setIsSubmittingAssessment(true);
    try {
      const finalReport = await submitAssessment(activeAssessment.id);
      setIsSubmitModalOpen(false);
      setReport(finalReport);
      setViewMode("report");
    } catch (err) {
      setAssessmentError(
        err instanceof Error ? err.message : "Failed to submit assessment",
      );
      setIsSubmitModalOpen(false);
    } finally {
      setIsSubmittingAssessment(false);
    }
  };

  // Delete assessment
  const handleDeleteConfirm = async () => {
    if (!deleteTargetId) return;

    setIsDeleting(true);
    try {
      await deleteAssessment(deleteTargetId);
      setAssessments((prev) => prev.filter((a) => a.id !== deleteTargetId));
      setDeleteTargetId(null);
    } catch (err) {
      setListError(
        err instanceof Error ? err.message : "Failed to delete assessment",
      );
    } finally {
      setIsDeleting(false);
    }
  };

  // Filtered assessment list
  const filteredAssessments = assessments.filter((a) => {
    if (filterKind === "all") return true;
    return a.kind === filterKind;
  });

  // Format seconds to mm:ss
  const formatTime = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const secs = sec % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  // -------------------------------------------------------------
  // RENDER: Active Assessment Taking View
  // -------------------------------------------------------------
  if (viewMode === "taking" && activeAssessment) {
    const currentQ: QuestionOut | undefined =
      activeAssessment.questions[activeQuestionIndex];
    const answeredCount = activeAssessment.questions.filter(
      (q) => q.answered,
    ).length;
    const totalCount = activeAssessment.questions.length;
    const progressPct =
      totalCount > 0 ? Math.round((answeredCount / totalCount) * 100) : 0;
    const isAnswered = currentQ?.answered || answerFeedback !== null;

    return (
      <PageContainer maxWidth="narrow">
        <div className="space-y-5">
          {/* Top Bar Navigation */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-surface-border-subtle dark:border-dark-border-subtle">
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setViewMode("list");
                  loadAssessments();
                }}
                leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}
              >
                Assessments
              </Button>
              <div>
                <h1 className="text-base sm:text-lg font-bold text-surface-text dark:text-dark-text flex items-center gap-2">
                  <span>{activeAssessment.title || "Adaptive Assessment"}</span>
                  <Badge variant="brand" size="sm" className="capitalize">
                    {activeAssessment.kind.replace("_", " ")}
                  </Badge>
                </h1>
                <p className="text-xs text-surface-text-muted dark:text-dark-text-muted">
                  {activeAssessment.difficulty
                    ? `Difficulty: ${activeAssessment.difficulty}`
                    : "Adaptive Difficulty"}{" "}
                  &bull; {totalCount} Questions
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-surface-muted dark:bg-dark-muted text-xs font-medium text-surface-text-muted dark:text-dark-text-muted">
                <Clock className="w-3.5 h-3.5" />
                <span>{formatTime(questionSeconds)}</span>
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsSubmitModalOpen(true)}
              >
                Finish & Submit
              </Button>
            </div>
          </div>

          {/* Progress Bar & Stepper */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-surface-text-muted dark:text-dark-text-muted">
              <span>
                Progress: {answeredCount} of {totalCount} Answered
              </span>
              <span>{progressPct}% Completed</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-surface-border-subtle dark:bg-dark-border-subtle overflow-hidden">
              <div
                className="h-full bg-brand-600 dark:bg-brand-500 transition-all duration-300"
                style={{ width: `${progressPct}%` }}
              />
            </div>

            {/* Question Chips */}
            <div className="flex flex-wrap gap-1.5 pt-1">
              {activeAssessment.questions.map((q, idx) => {
                const isActive = idx === activeQuestionIndex;
                const isCorrect = q.attempt?.is_correct;

                let chipClass =
                  "bg-surface-muted dark:bg-dark-muted text-surface-text-muted dark:text-dark-text-muted border-transparent";
                if (q.answered) {
                  if (isCorrect) {
                    chipClass =
                      "bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800";
                  } else {
                    chipClass =
                      "bg-rose-100 dark:bg-rose-950/60 text-rose-800 dark:text-rose-300 border-rose-300 dark:border-rose-800";
                  }
                }
                if (isActive) {
                  chipClass +=
                    " ring-2 ring-brand-600 dark:ring-brand-400 font-bold";
                }

                return (
                  <button
                    key={q.id}
                    type="button"
                    onClick={() => handleSelectQuestion(idx)}
                    className={`w-7 h-7 rounded text-xs border flex items-center justify-center transition-all cursor-pointer ${chipClass}`}
                    title={`Question ${idx + 1}`}
                  >
                    {idx + 1}
                  </button>
                );
              })}
            </div>
          </div>

          {assessmentError && (
            <Alert variant="error" onDismiss={() => setAssessmentError(null)}>
              {assessmentError}
            </Alert>
          )}

          {/* Active Question Card */}
          {currentQ && (
            <Card padding="lg" className="space-y-6">
              {/* Question Metadata */}
              <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-surface-border-subtle dark:border-dark-border-subtle">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="neutral" size="sm">
                    Q{activeQuestionIndex + 1}
                  </Badge>
                  <Badge variant="brand" size="sm">
                    {getTopicName(currentQ.topic)}
                  </Badge>
                  {getConceptName(currentQ.concept) && (
                    <Badge variant="neutral" size="sm">
                      Concept: {getConceptName(currentQ.concept)}
                    </Badge>
                  )}
                  <Badge variant="neutral" size="sm" className="capitalize">
                    {currentQ.difficulty || "Adaptive"}
                  </Badge>
                </div>
                <span className="text-xs uppercase tracking-wider font-semibold text-surface-text-muted dark:text-dark-text-muted">
                  {(currentQ.qtype || currentQ.question_type || "mcq").replace(
                    "_",
                    " ",
                  )}
                </span>
              </div>

              {/* Prompt */}
              <div className="text-base sm:text-lg font-medium text-surface-text dark:text-dark-text leading-relaxed">
                {currentQ.prompt}
              </div>

              {/* Answer Choices / Inputs */}
              {(() => {
                const qType = currentQ.qtype || currentQ.question_type || "mcq";
                return (
                  <div className="space-y-3 pt-2">
                    {qType === "mcq" && currentQ.options && (
                      <div className="space-y-2.5">
                        {currentQ.options.map((opt) => {
                          const isSelected = currentAnswer === opt.key;
                          let optionCardClass =
                            "border-surface-border dark:border-dark-border hover:border-brand-500 hover:bg-brand-50/20 dark:hover:bg-brand-950/20";

                          if (isAnswered) {
                            const isCorrectOption =
                              answerFeedback?.correct_answer === opt.key ||
                              (currentQ.attempt?.answer === opt.key &&
                                currentQ.attempt.is_correct);
                            const isSelectedIncorrect =
                              isSelected &&
                              !currentQ.attempt?.is_correct &&
                              (!answerFeedback || !answerFeedback.is_correct);

                            if (isCorrectOption) {
                              optionCardClass =
                                "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-100 font-medium";
                            } else if (isSelectedIncorrect) {
                              optionCardClass =
                                "border-rose-500 bg-rose-50 dark:bg-rose-950/40 text-rose-900 dark:text-rose-100";
                            } else {
                              optionCardClass =
                                "border-surface-border-subtle dark:border-dark-border-subtle opacity-60";
                            }
                          } else if (isSelected) {
                            optionCardClass =
                              "border-brand-600 bg-brand-50/50 dark:bg-brand-950/40 ring-1 ring-brand-600 font-medium";
                          }

                          return (
                            <div
                              key={opt.key}
                              onClick={() => {
                                if (!isAnswered) setCurrentAnswer(opt.key);
                              }}
                              className={`p-3.5 rounded-lg border flex items-start gap-3 transition-all ${
                                isAnswered ? "cursor-default" : "cursor-pointer"
                              } ${optionCardClass}`}
                            >
                              <span className="w-6 h-6 rounded-md bg-surface-muted dark:bg-dark-muted text-xs font-bold flex items-center justify-center shrink-0 uppercase">
                                {opt.key}
                              </span>
                              <span className="text-sm pt-0.5 text-surface-text dark:text-dark-text">
                                {opt.text}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {qType === "short_answer" && (
                      <div className="space-y-2">
                        <label className="text-xs font-medium text-surface-text-muted dark:text-dark-text-muted">
                          Your Answer:
                        </label>
                        <textarea
                          value={currentAnswer}
                          onChange={(e) => setCurrentAnswer(e.target.value)}
                          disabled={isAnswered}
                          rows={3}
                          placeholder="Type your concise answer..."
                          className="w-full px-3 py-2 rounded-lg border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-surface-text dark:text-dark-text text-sm focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:opacity-75 disabled:cursor-not-allowed"
                        />
                      </div>
                    )}

                    {qType === "numerical" && (
                      <div className="space-y-2 max-w-xs">
                        <label className="text-xs font-medium text-surface-text-muted dark:text-dark-text-muted">
                          Numerical Value{" "}
                          {currentQ.unit ? `(${currentQ.unit})` : ""}:
                        </label>
                        <div className="flex items-center gap-2">
                          <Input
                            type="text"
                            value={currentAnswer}
                            onChange={(e) => setCurrentAnswer(e.target.value)}
                            disabled={isAnswered}
                            placeholder="e.g. 42.5"
                          />
                          {currentQ.unit && (
                            <span className="text-xs font-medium text-surface-text-muted dark:text-dark-text-muted px-2 py-1 rounded bg-surface-muted dark:bg-dark-muted">
                              {currentQ.unit}
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}

              {answerError && (
                <Alert variant="error" onDismiss={() => setAnswerError(null)}>
                  {answerError}
                </Alert>
              )}

              {/* Submit Answer Action for active question */}
              {!isAnswered && (
                <div className="flex justify-end pt-2">
                  <Button
                    variant="primary"
                    disabled={!currentAnswer.trim() || isSubmittingAnswer}
                    isLoading={isSubmittingAnswer}
                    onClick={handleSubmitAnswer}
                    leftIcon={<CheckCircle2 className="w-4 h-4" />}
                  >
                    Check Answer
                  </Button>
                </div>
              )}

              {/* Immediate Feedback Box */}
              {isAnswered && answerFeedback && (
                <div
                  className={`p-4 rounded-xl border space-y-3 ${
                    answerFeedback.is_correct
                      ? "bg-emerald-50/70 dark:bg-emerald-950/30 border-emerald-300 dark:border-emerald-800 text-emerald-900 dark:text-emerald-100"
                      : "bg-rose-50/70 dark:bg-rose-950/30 border-rose-300 dark:border-rose-800 text-rose-900 dark:text-rose-100"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 font-bold text-sm">
                      {answerFeedback.is_correct ? (
                        <>
                          <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                          <span>Correct! (+{answerFeedback.score} pt)</span>
                        </>
                      ) : (
                        <>
                          <XCircle className="w-5 h-5 text-rose-600 dark:text-rose-400" />
                          <span>Incorrect</span>
                        </>
                      )}
                    </div>
                    {answerFeedback.mastery_update &&
                      (() => {
                        const beforeVal =
                          answerFeedback.mastery_update.p_mastery_before ??
                          answerFeedback.mastery_update.before ??
                          0;
                        const afterVal =
                          answerFeedback.mastery_update.p_mastery_after ??
                          answerFeedback.mastery_update.after ??
                          0;
                        return (
                          <Badge variant="brand" size="sm">
                            Mastery: {Math.round(beforeVal * 100)}% &rarr;{" "}
                            {Math.round(afterVal * 100)}%
                          </Badge>
                        );
                      })()}
                  </div>

                  {/* Correct answer notice if incorrect */}
                  {!answerFeedback.is_correct &&
                    Boolean(answerFeedback.correct_answer) && (
                      <div className="text-xs font-semibold">
                        Correct Answer:{" "}
                        <span className="underline">
                          {formatAnswerDisplay(answerFeedback.correct_answer)}
                        </span>
                      </div>
                    )}

                  {/* Explanation */}
                  {(answerFeedback.explanation || answerFeedback.feedback) && (
                    <div className="text-xs leading-relaxed opacity-95">
                      <strong className="block mb-0.5">Explanation:</strong>
                      {answerFeedback.explanation || answerFeedback.feedback}
                    </div>
                  )}

                  {/* Citations */}
                  {answerFeedback.citations &&
                    answerFeedback.citations.length > 0 && (
                      <div className="pt-2 border-t border-current/10">
                        <span className="text-[11px] font-semibold uppercase tracking-wider opacity-80 block mb-1">
                          Course Material Evidence:
                        </span>
                        <div className="space-y-1.5">
                          {answerFeedback.citations.map((cite, cIdx) => {
                            const pageNum = (
                              cite.location as
                                | Record<string, unknown>
                                | undefined
                            )?.page_number;
                            const snippet =
                              "snippet" in cite
                                ? (cite as { snippet?: string }).snippet
                                : "";
                            return (
                              <div
                                key={cIdx}
                                className="text-xs bg-surface-card/60 dark:bg-dark-card/60 p-2 rounded border border-current/10 text-surface-text dark:text-dark-text"
                              >
                                <span className="font-semibold">
                                  {cite.source_title}
                                </span>
                                {pageNum !== undefined
                                  ? ` (p. ${String(pageNum)})`
                                  : ""}
                                {snippet ? (
                                  <p className="italic text-[11px] mt-0.5 text-surface-text-muted dark:text-dark-text-muted">
                                    &ldquo;{snippet}&rdquo;
                                  </p>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                </div>
              )}

              {/* Bottom Question Navigation Controls */}
              <div className="flex items-center justify-between pt-4 border-t border-surface-border-subtle dark:border-dark-border-subtle">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={activeQuestionIndex === 0}
                  onClick={() => handleSelectQuestion(activeQuestionIndex - 1)}
                  leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}
                >
                  Previous
                </Button>

                {activeQuestionIndex < totalCount - 1 ? (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() =>
                      handleSelectQuestion(activeQuestionIndex + 1)
                    }
                    rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                  >
                    Next Question
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setIsSubmitModalOpen(true)}
                    rightIcon={<CheckCircle className="w-3.5 h-3.5" />}
                  >
                    Finish Assessment
                  </Button>
                )}
              </div>
            </Card>
          )}
        </div>

        {/* Submit Confirmation Modal */}
        <Modal
          isOpen={isSubmitModalOpen}
          onClose={() => setIsSubmitModalOpen(false)}
          title="Submit Assessment?"
        >
          <div className="space-y-4">
            <p className="text-sm text-surface-text dark:text-dark-text">
              You have answered <strong>{answeredCount}</strong> of{" "}
              <strong>{totalCount}</strong> questions.
            </p>
            {answeredCount < totalCount && (
              <Alert variant="warning">
                You have {totalCount - answeredCount} unanswered question(s).
                Unanswered questions will receive zero points.
              </Alert>
            )}
            <p className="text-xs text-surface-text-muted dark:text-dark-text-muted">
              Once submitted, your final score and Bayesian topic mastery will
              be updated.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsSubmitModalOpen(false)}
                disabled={isSubmittingAssessment}
              >
                Continue Quiz
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleFinalizeAssessment}
                isLoading={isSubmittingAssessment}
              >
                Confirm & Submit
              </Button>
            </div>
          </div>
        </Modal>
      </PageContainer>
    );
  }

  // -------------------------------------------------------------
  // RENDER: Assessment Report View
  // -------------------------------------------------------------
  if (viewMode === "report" && report) {
    const { summary, by_topic, weak_topics, strong_topics, review } = report;
    const reportKind = report.kind || report.assessment?.kind || "quiz";
    const reportTitle =
      report.title || report.assessment?.title || "Assessment Results";

    return (
      <PageContainer maxWidth="standard">
        <div className="space-y-6">
          {/* Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-surface-border-subtle dark:border-dark-border-subtle">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setViewMode("list");
                    loadAssessments();
                  }}
                  leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}
                >
                  All Assessments
                </Button>
                <Badge variant="brand" size="sm" className="capitalize">
                  {reportKind.replace("_", " ")} Report
                </Badge>
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-surface-text dark:text-dark-text">
                {reportTitle}
              </h1>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  setViewMode("list");
                  setIsCreateModalOpen(true);
                }}
                leftIcon={<Plus className="w-3.5 h-3.5" />}
              >
                Take Another Quiz
              </Button>
            </div>
          </div>

          {isLoadingReport && (
            <LoadingState message="Loading assessment report..." />
          )}

          {reportError && (
            <Alert variant="error" onDismiss={() => setReportError(null)}>
              {reportError}
            </Alert>
          )}

          {/* Hero Score Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card padding="md" className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-brand-50 dark:bg-brand-950/50 flex items-center justify-center text-brand-600 dark:text-brand-400 shrink-0">
                <Target className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs uppercase tracking-wider font-semibold text-surface-text-muted dark:text-dark-text-muted">
                  Overall Score
                </span>
                <div className="text-2xl font-extrabold text-surface-text dark:text-dark-text">
                  {summary.score_pct}%
                </div>
              </div>
            </Card>

            <Card padding="md" className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-emerald-50 dark:bg-emerald-950/50 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shrink-0">
                <CheckCircle className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs uppercase tracking-wider font-semibold text-surface-text-muted dark:text-dark-text-muted">
                  Correct Questions
                </span>
                <div className="text-2xl font-extrabold text-surface-text dark:text-dark-text">
                  {summary.correct} / {summary.total_questions}
                </div>
              </div>
            </Card>

            <Card padding="md" className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-surface-muted dark:bg-dark-muted flex items-center justify-center text-surface-text-muted dark:text-dark-text-muted shrink-0">
                <Clock className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xs uppercase tracking-wider font-semibold text-surface-text-muted dark:text-dark-text-muted">
                  Avg Time / Question
                </span>
                <div className="text-2xl font-extrabold text-surface-text dark:text-dark-text">
                  {summary.avg_time_sec ? `${summary.avg_time_sec}s` : "N/A"}
                </div>
              </div>
            </Card>
          </div>

          {/* Strengths & Weaknesses */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card padding="md">
              <CardHeader className="p-0 pb-2">
                <CardTitle className="text-sm font-semibold flex items-center gap-2 text-emerald-700 dark:text-emerald-400">
                  <CheckCircle className="w-4 h-4" /> Strong Topics
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {strong_topics && strong_topics.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {strong_topics.map((t, idx) => (
                      <Badge key={idx} variant="brand" size="sm">
                        {formatTopicBadgeLabel(t)}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-surface-text-muted dark:text-dark-text-muted">
                    No strong topics identified yet. Practice more questions to
                    demonstrate mastery.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card padding="md">
              <CardHeader className="p-0 pb-2">
                <CardTitle className="text-sm font-semibold flex items-center gap-2 text-amber-700 dark:text-amber-400">
                  <AlertCircle className="w-4 h-4" /> Areas for Review
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {weak_topics && weak_topics.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {weak_topics.map((t, idx) => (
                      <Badge key={idx} variant="amber" size="sm">
                        {formatTopicBadgeLabel(t)}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-surface-text-muted dark:text-dark-text-muted">
                    Great work! No significant weak topics found in this
                    assessment.
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Topic Performance Table */}
          {by_topic && by_topic.length > 0 && (
            <Card padding="md">
              <CardHeader className="p-0 pb-3">
                <CardTitle className="text-sm font-semibold">
                  Topic Mastery Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0 space-y-3">
                {by_topic.map((top, idx) => (
                  <div key={top.topic_id ?? idx} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-surface-text dark:text-dark-text">
                        {formatTopicSummaryName(top)}
                      </span>
                      <span className="text-surface-text-muted dark:text-dark-text-muted">
                        {top.correct} / {top.total} ({top.accuracy}%)
                      </span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-surface-border-subtle dark:border-dark-border-subtle overflow-hidden">
                      <div
                        className={`h-full ${
                          top.accuracy >= 70
                            ? "bg-emerald-500"
                            : top.accuracy >= 40
                              ? "bg-amber-500"
                              : "bg-rose-500"
                        }`}
                        style={{ width: `${top.accuracy}%` }}
                      />
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Detailed Question Review */}
          <div className="space-y-4">
            <h2 className="text-base font-bold text-surface-text dark:text-dark-text">
              Question-by-Question Review
            </h2>

            <div className="space-y-3">
              {review.map((item, idx) => (
                <Card
                  key={item.question_id || idx}
                  padding="md"
                  className={`border-l-4 ${
                    item.is_correct
                      ? "border-l-emerald-500"
                      : "border-l-rose-500"
                  }`}
                >
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-surface-text-muted dark:text-dark-text-muted">
                          Q{idx + 1}
                        </span>
                        <Badge variant="neutral" size="sm">
                          {getTopicName(item.topic)}
                        </Badge>
                        {getConceptName(item.concept) && (
                          <Badge variant="neutral" size="sm">
                            {getConceptName(item.concept)}
                          </Badge>
                        )}
                      </div>
                      <Badge
                        variant={item.is_correct ? "brand" : "amber"}
                        size="sm"
                      >
                        {item.is_correct ? "Correct" : "Incorrect"}
                      </Badge>
                    </div>

                    <p className="text-sm font-medium text-surface-text dark:text-dark-text">
                      {item.prompt}
                    </p>

                    <div className="text-xs space-y-1 pt-1">
                      <div>
                        <span className="text-surface-text-muted dark:text-dark-text-muted">
                          Your Answer:{" "}
                        </span>
                        <span
                          className={
                            item.is_correct
                              ? "font-semibold text-emerald-700 dark:text-emerald-400"
                              : "font-semibold text-rose-700 dark:text-rose-400"
                          }
                        >
                          {formatAnswerDisplay(
                            item.student_answer || item.your_answer,
                          )}
                        </span>
                      </div>
                      {!item.is_correct && (
                        <div>
                          <span className="text-surface-text-muted dark:text-dark-text-muted">
                            Correct Answer:{" "}
                          </span>
                          <span className="font-semibold text-emerald-700 dark:text-emerald-400">
                            {formatAnswerDisplay(item.correct_answer)}
                          </span>
                        </div>
                      )}
                    </div>

                    {item.explanation && (
                      <div className="mt-2 p-2.5 rounded-lg bg-surface-muted dark:bg-dark-muted text-xs text-surface-text dark:text-dark-text leading-relaxed">
                        <strong className="block mb-0.5">Explanation:</strong>
                        {item.explanation}
                      </div>
                    )}

                    {item.citations && item.citations.length > 0 && (
                      <div className="mt-2 text-[11px] text-surface-text-muted dark:text-dark-text-muted">
                        <span className="font-semibold uppercase tracking-wider block mb-0.5">
                          Citation:
                        </span>
                        {item.citations[0].source_title}
                        {item.citations[0].location?.page_number &&
                          ` (p. ${item.citations[0].location.page_number})`}
                        : &ldquo;{item.citations[0].snippet}&rdquo;
                      </div>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          </div>
        </div>
      </PageContainer>
    );
  }

  // -------------------------------------------------------------
  // RENDER: Assessments Dashboard / List View
  // -------------------------------------------------------------
  return (
    <PageContainer maxWidth="standard">
      <div className="space-y-6">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-surface-text dark:text-dark-text">
              Adaptive Assessments
            </h1>
            <p className="text-xs sm:text-sm text-surface-text-muted dark:text-dark-text-muted mt-0.5">
              Personalized practice quizzes, diagnostic tests, and mock exams
              with instant Bayesian Knowledge Tracing.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={loadAssessments}
              isLoading={isLoadingList}
              leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            >
              Refresh
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={handleLaunchDiagnostic}
              disabled={
                !activeCourse ||
                !activeStudent ||
                isLoadingAssessment ||
                isStartingDiagnostic
              }
              isLoading={isStartingDiagnostic}
              leftIcon={<Sparkles className="w-3.5 h-3.5" />}
            >
              Quick Diagnostic
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsCreateModalOpen(true)}
              disabled={!activeCourse || !activeStudent}
              leftIcon={<Plus className="w-3.5 h-3.5" />}
            >
              New Quiz
            </Button>
          </div>
        </div>

        {/* Missing Context Warnings */}
        {!activeStudent && (
          <Alert variant="warning">
            <div className="flex items-center justify-between">
              <span>
                Please select an active student profile to view or create
                assessments.
              </span>
              <Link to="/profile">
                <Button
                  variant="secondary"
                  size="sm"
                  rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                >
                  Manage Profile
                </Button>
              </Link>
            </div>
          </Alert>
        )}

        {activeStudent && !activeCourse && (
          <Alert variant="warning">
            <div className="flex items-center justify-between">
              <span>
                Please select an active course to view or create assessments.
              </span>
              <Link to="/courses">
                <Button
                  variant="secondary"
                  size="sm"
                  rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                >
                  Select Course
                </Button>
              </Link>
            </div>
          </Alert>
        )}

        {activeCourse && activeCourse.kb_status !== "ready" && (
          <Alert variant="info">
            <div className="flex items-center justify-between">
              <span>
                Knowledge base status: <strong>{activeCourse.kb_status}</strong>
                . Ingest course sources to enable grounded assessment
                generation.
              </span>
              <Link to="/sources">
                <Button
                  variant="secondary"
                  size="sm"
                  rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                >
                  Manage Sources
                </Button>
              </Link>
            </div>
          </Alert>
        )}

        {listError && (
          <Alert variant="error" onDismiss={() => setListError(null)}>
            {listError}
          </Alert>
        )}

        {/* Filters and Search Bar */}
        <div className="flex items-center justify-between gap-3 pt-2">
          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-surface-muted dark:bg-dark-muted text-xs">
            <button
              type="button"
              onClick={() => setFilterKind("all")}
              className={`px-3 py-1 rounded-md font-medium transition-all ${
                filterKind === "all"
                  ? "bg-surface-card dark:bg-dark-card text-surface-text dark:text-dark-text shadow-xs"
                  : "text-surface-text-muted dark:text-dark-text-muted hover:text-surface-text"
              }`}
            >
              All ({assessments.length})
            </button>
            <button
              type="button"
              onClick={() => setFilterKind("diagnostic")}
              className={`px-3 py-1 rounded-md font-medium transition-all ${
                filterKind === "diagnostic"
                  ? "bg-surface-card dark:bg-dark-card text-surface-text dark:text-dark-text shadow-xs"
                  : "text-surface-text-muted dark:text-dark-text-muted hover:text-surface-text"
              }`}
            >
              Diagnostic
            </button>
            <button
              type="button"
              onClick={() => setFilterKind("quiz")}
              className={`px-3 py-1 rounded-md font-medium transition-all ${
                filterKind === "quiz"
                  ? "bg-surface-card dark:bg-dark-card text-surface-text dark:text-dark-text shadow-xs"
                  : "text-surface-text-muted dark:text-dark-text-muted hover:text-surface-text"
              }`}
            >
              Quizzes
            </button>
            <button
              type="button"
              onClick={() => setFilterKind("mock_exam")}
              className={`px-3 py-1 rounded-md font-medium transition-all ${
                filterKind === "mock_exam"
                  ? "bg-surface-card dark:bg-dark-card text-surface-text dark:text-dark-text shadow-xs"
                  : "text-surface-text-muted dark:text-dark-text-muted hover:text-surface-text"
              }`}
            >
              Mock Exams
            </button>
          </div>

          <span className="text-xs text-surface-text-muted dark:text-dark-text-muted hidden sm:inline">
            Showing {filteredAssessments.length} assessment(s)
          </span>
        </div>

        {/* Assessments List / Cards */}
        {isLoadingList ? (
          <LoadingState message="Loading course assessments..." />
        ) : filteredAssessments.length === 0 ? (
          <Card padding="lg" className="text-center py-12">
            <div className="max-w-md mx-auto space-y-3">
              <div className="w-12 h-12 rounded-xl bg-brand-50 dark:bg-brand-950/40 text-brand-600 dark:text-brand-400 flex items-center justify-center mx-auto">
                <Target className="w-6 h-6" />
              </div>
              <CardTitle className="text-base">No Assessments Yet</CardTitle>
              <CardDescription className="text-xs">
                Start a Diagnostic Assessment to benchmark your current
                knowledge across all topics, or create a targeted practice quiz.
              </CardDescription>
              <div className="flex justify-center gap-2 pt-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleLaunchDiagnostic}
                  disabled={
                    !activeCourse ||
                    !activeStudent ||
                    isLoadingAssessment ||
                    isStartingDiagnostic
                  }
                  isLoading={isStartingDiagnostic}
                  leftIcon={<Sparkles className="w-3.5 h-3.5" />}
                >
                  Start Diagnostic
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsCreateModalOpen(true)}
                  disabled={!activeCourse || !activeStudent}
                  leftIcon={<Plus className="w-3.5 h-3.5" />}
                >
                  Create Quiz
                </Button>
              </div>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredAssessments.map((a) => {
              const isInProgress = a.status === "in_progress";
              const totalQ = a.num_questions ?? a.question_count ?? 0;
              const progressPct =
                totalQ > 0 ? Math.round((a.answered_count / totalQ) * 100) : 0;

              return (
                <Card
                  key={a.id}
                  padding="md"
                  className="space-y-3 flex flex-col justify-between"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Badge variant="brand" size="sm" className="capitalize">
                        {a.kind.replace("_", " ")}
                      </Badge>
                      <Badge
                        variant={isInProgress ? "amber" : "brand"}
                        size="sm"
                        dot={isInProgress}
                      >
                        {isInProgress ? "In Progress" : "Completed"}
                      </Badge>
                    </div>

                    <div>
                      <CardTitle className="text-sm font-semibold truncate">
                        {a.title || `${a.kind.toUpperCase()} #${a.id}`}
                      </CardTitle>
                      <CardDescription className="text-xs pt-0.5">
                        {totalQ} Questions &bull;{" "}
                        {new Date(a.created_at).toLocaleDateString()}
                      </CardDescription>
                    </div>

                    {/* Progress or Score */}
                    <div className="pt-1 space-y-1">
                      <div className="flex items-center justify-between text-xs text-surface-text-muted dark:text-dark-text-muted">
                        <span>
                          {isInProgress
                            ? `Answered: ${a.answered_count} / ${totalQ}`
                            : `Final Score: ${a.score !== null ? `${a.score}%` : "Graded"}`}
                        </span>
                        <span>{progressPct}%</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-surface-border-subtle dark:bg-dark-border-subtle overflow-hidden">
                        <div
                          className={`h-full ${
                            isInProgress
                              ? "bg-amber-500"
                              : (a.score || 0) >= 70
                                ? "bg-emerald-500"
                                : "bg-brand-600"
                          }`}
                          style={{ width: `${progressPct}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="pt-2 border-t border-surface-border-subtle dark:border-dark-border-subtle flex items-center justify-between">
                    <span className="text-[11px] text-surface-text-muted dark:text-dark-text-muted">
                      {new Date(a.created_at).toLocaleDateString()}
                    </span>

                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteTargetId(a.id)}
                        className="text-surface-text-muted hover:text-rose-600 p-1.5"
                        title="Delete Assessment"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>

                      {isInProgress ? (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleOpenAssessment(a.id)}
                          rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                        >
                          Resume
                        </Button>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenReport(a.id)}
                        >
                          View Report
                        </Button>
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}

        {/* Modal: Create Custom Assessment */}
        <Modal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          title="Create Custom Assessment"
        >
          <form onSubmit={handleCreateCustomAssessment} className="space-y-4">
            {createError && (
              <Alert variant="error" onDismiss={() => setCreateError(null)}>
                {createError}
              </Alert>
            )}

            <div>
              <label className="text-xs font-medium text-surface-text dark:text-dark-text block mb-1">
                Assessment Title (optional)
              </label>
              <Input
                type="text"
                placeholder="e.g. Unit 2 Practice Quiz"
                value={createTitle}
                onChange={(e) => setCreateTitle(e.target.value)}
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-surface-text dark:text-dark-text block mb-1">
                  Type
                </label>
                <Select
                  value={createKind}
                  onChange={(e) =>
                    setCreateKind(e.target.value as AssessmentKind)
                  }
                >
                  <option value="quiz">Practice Quiz</option>
                  <option value="mock_exam">Mock Exam</option>
                  <option value="diagnostic">Diagnostic</option>
                </Select>
              </div>

              <div>
                <label className="text-xs font-medium text-surface-text dark:text-dark-text block mb-1">
                  Difficulty
                </label>
                <Select
                  value={createDifficulty}
                  onChange={(e) =>
                    setCreateDifficulty(e.target.value as AssessmentDifficulty)
                  }
                >
                  <option value="auto">Auto (Adaptive / BKT)</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-surface-text dark:text-dark-text block mb-1">
                  Questions Count
                </label>
                <Select
                  value={createNumQuestions}
                  onChange={(e) =>
                    setCreateNumQuestions(Number(e.target.value))
                  }
                >
                  <option value={3}>3 Questions (Quick)</option>
                  <option value={5}>5 Questions (Standard)</option>
                  <option value={10}>10 Questions (Comprehensive)</option>
                  <option value={15}>15 Questions (Full Exam)</option>
                </Select>
              </div>

              <div>
                <label className="text-xs font-medium text-surface-text dark:text-dark-text block mb-1">
                  Topic Scope
                </label>
                <Select
                  value={selectedTopicId}
                  onChange={(e) => setSelectedTopicId(e.target.value)}
                >
                  <option value="all">All Course Topics</option>
                  {courseTopics.map((top) => (
                    <option key={top.id} value={top.id}>
                      {top.name}
                    </option>
                  ))}
                </Select>
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-surface-text dark:text-dark-text block mb-1.5">
                Question Formats
              </label>
              <div className="flex flex-wrap gap-4 text-xs text-surface-text dark:text-dark-text">
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={createTypes.includes("mcq")}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setCreateTypes([...createTypes, "mcq"]);
                      } else if (createTypes.length > 1) {
                        setCreateTypes(createTypes.filter((t) => t !== "mcq"));
                      }
                    }}
                    className="rounded text-brand-600 focus:ring-brand-500"
                  />
                  <span>Multiple Choice (MCQ)</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={createTypes.includes("short_answer")}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setCreateTypes([...createTypes, "short_answer"]);
                      } else if (createTypes.length > 1) {
                        setCreateTypes(
                          createTypes.filter((t) => t !== "short_answer"),
                        );
                      }
                    }}
                    className="rounded text-brand-600 focus:ring-brand-500"
                  />
                  <span>Short Answer</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={createTypes.includes("numerical")}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setCreateTypes([...createTypes, "numerical"]);
                      } else if (createTypes.length > 1) {
                        setCreateTypes(
                          createTypes.filter((t) => t !== "numerical"),
                        );
                      }
                    }}
                    className="rounded text-brand-600 focus:ring-brand-500"
                  />
                  <span>Numerical</span>
                </label>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-surface-border-subtle dark:border-dark-border-subtle">
              <Button
                variant="outline"
                size="sm"
                type="button"
                onClick={() => setIsCreateModalOpen(false)}
                disabled={isCreating}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                type="submit"
                isLoading={isCreating}
                leftIcon={<Plus className="w-3.5 h-3.5" />}
              >
                Generate Assessment
              </Button>
            </div>
          </form>
        </Modal>

        {/* Modal: Delete Confirmation */}
        <Modal
          isOpen={deleteTargetId !== null}
          onClose={() => setDeleteTargetId(null)}
          title="Delete Assessment"
        >
          <div className="space-y-4">
            <p className="text-sm text-surface-text dark:text-dark-text">
              Are you sure you want to delete this assessment and its recorded
              attempts? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDeleteTargetId(null)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleDeleteConfirm}
                isLoading={isDeleting}
              >
                Delete
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </PageContainer>
  );
};
