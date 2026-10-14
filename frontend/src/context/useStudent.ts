import { useContext } from 'react'
import { StudentContext, type StudentContextValue } from './studentContextDef'

export function useStudent(): StudentContextValue {
  const context = useContext(StudentContext)
  if (!context) {
    throw new Error('useStudent must be used within a StudentProvider')
  }
  return context
}
