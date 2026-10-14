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
]

export const UPCOMING_NAV_ITEMS: NavItem[] = [
  {
    id: 'tutor',
    label: 'AI Tutor',
    path: '/tutor',
    icon: MessageSquareIcon,
    badge: 'Soon',
    disabled: true,
  },
  {
    id: 'assessments',
    label: 'Assessments',
    path: '/assessments',
    icon: CheckCircleIcon,
    badge: 'Soon',
    disabled: true,
  },
  {
    id: 'mastery',
    label: 'Knowledge & Mastery',
    path: '/mastery',
    icon: ActivityIcon,
    badge: 'Soon',
    disabled: true,
  },
]

export const ALL_NAV_ITEMS: NavItem[] = [
  ...MAIN_NAV_ITEMS,
  ...UPCOMING_NAV_ITEMS,
]
