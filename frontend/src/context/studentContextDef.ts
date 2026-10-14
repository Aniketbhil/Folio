import { createContext } from 'react'
import type { StudentCreate, StudentRead } from '../types/student'

export interface StudentContextValue {
  students: StudentRead[]
  activeStudent: StudentRead | null
  activeStudentId: number | null
  isLoading: boolean
  error: string | null
  setActiveStudentId: (id: number | null) => void
  refreshStudents: () => Promise<void>
  addStudent: (payload: StudentCreate) => Promise<StudentRead>
  removeStudent: (id: number) => Promise<void>
}

export const StudentContext = createContext<StudentContextValue | undefined>(undefined)
