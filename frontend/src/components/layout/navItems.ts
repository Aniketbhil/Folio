import React from 'react'
import {
  ActivityIcon,
  BookOpenIcon,
  CheckCircleIcon,
  HomeIcon,
  MessageSquareIcon,
} from '../ui/Icons'

export interface NavItem {
  id: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'overview', label: 'Overview', icon: HomeIcon },
  { id: 'sources', label: 'Sources & Library', icon: BookOpenIcon },
  { id: 'tutor', label: 'AI Tutor', icon: MessageSquareIcon },
  { id: 'assessments', label: 'Assessments', icon: CheckCircleIcon },
  { id: 'mastery', label: 'Knowledge & Mastery', icon: ActivityIcon },
]
