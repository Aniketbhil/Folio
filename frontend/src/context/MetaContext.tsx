import React, { useCallback, useEffect, useState } from 'react'
import { getMeta } from '../api/meta'
import { formatApiError } from '../api/errors'
import { MetaContext } from './metaContextDef'
import type { MetaResponse } from '../types/meta'

export const MetaProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [meta, setMeta] = useState<MetaResponse | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // Manual refetch callable by UI actions
  const refetch = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getMeta()
      setMeta(data)
    } catch (err) {
      setError(formatApiError(err, 'Failed to load system metadata'))
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Mount effect: fetch async without synchronous setState in effect body
  useEffect(() => {
    let isMounted = true

    getMeta()
      .then((data) => {
        if (isMounted) {
          setMeta(data)
          setIsLoading(false)
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(formatApiError(err, 'Failed to load system metadata'))
          setIsLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [])

  return (
    <MetaContext.Provider
      value={{
        meta,
        isLoading,
        error,
        refetch,
      }}
    >
      {children}
    </MetaContext.Provider>
  )
}
