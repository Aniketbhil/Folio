import React from 'react'
import {
  ActivityIcon,
  BookOpenIcon,
  CheckCircleIcon,
  FileTextIcon,
  HomeIcon,
  MessageSquareIcon,
  UserIcon,
} from '../ui/Icons'

export interface NavItem {
  id: string
  label: string
  path: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
  disabled?: boolean
}

export const MAIN_NAV_ITEMS: NavItem[] = [
  { id: 'overview', label: 'Overview', path: '/', icon: HomeIcon },
  { id: 'students', label: 'Students', path: '/students', icon: UserIcon },
  { id: 'courses', label: 'Courses', path: '/courses', icon: BookOpenIcon },
  { id: 'sources', label: 'Sources', path: '/sources', icon: FileTextIcon },
  { id: 'tutor', label: 'AI Tutor', path: '/tutor', icon: MessageSquareIcon },
  { id: 'assessments', label: 'Assessments', path: '/assessments', icon: CheckCircleIcon },
  { id: 'mastery', label: 'Mastery Graph', path: '/mastery', icon: ActivityIcon },
]

export const UPCOMING_NAV_ITEMS: NavItem[] = []

export const ALL_NAV_ITEMS: NavItem[] = [
  ...MAIN_NAV_ITEMS,
  ...UPCOMING_NAV_ITEMS,
]
