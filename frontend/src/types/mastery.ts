import type { TutorCitation } from './tutor'

export interface GraphNode {
  id: number
  name: string
  parent_id: number | null
  level: number
  is_leaf: boolean
  chunk_count: number
}

export interface GraphEdge {
  from: number
  to: number
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface TopicPrereqOut {
  id: number
  name: string
  satisfied: boolean
}

export interface LeafTopicMasteryOut {
  topic: {
    id: number
    name: string
    parent_id?: number | null
    parent_name?: string | null
  }
  p_mastery: number
  effective_mastery: number
  retrievability: number
  status: 'new' | 'weak' | 'learning' | 'strong' | string
  attempts: number
  correct: number
  accuracy: number | null
  last_practiced_at?: string | null
  due_for_review: boolean
  trend: number[]
  trend_delta: number
  prerequisites: TopicPrereqOut[]
}

export interface CoverageOut {
  practiced: number
  total: number
}

export interface CountsOut {
  new: number
  weak: number
  learning: number
  strong: number
  due_for_review: number
}

export interface CourseMasteryResponse {
  student_id: number
  course_id: number
  average_mastery?: number | null
  readiness: number
  coverage: CoverageOut
  counts: CountsOut
  topics: LeafTopicMasteryOut[]
  kb_not_ready?: boolean
}

export interface TopicBrief {
  id: number
  name: string
}

export interface ConceptBrief {
  id: number
  name: string
  definition: string
}

export interface TopicDetailResponse {
  id: number
  name: string
  description?: string | null
  parent?: TopicBrief | null
  children: TopicBrief[]
  concepts: ConceptBrief[]
  prerequisites: TopicBrief[]
  unlocks: TopicBrief[]
  chunk_count: number
  chunks: TutorCitation[]
}

export interface ConceptItem {
  id: number
  name: string
  definition: string
  topic_id: number
  topic_name: string
}
