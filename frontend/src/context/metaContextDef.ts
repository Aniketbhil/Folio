import { createContext } from 'react'
import type { MetaResponse } from '../types/meta'

export interface MetaContextValue {
  meta: MetaResponse | null
  isLoading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export const MetaContext = createContext<MetaContextValue | undefined>(undefined)
