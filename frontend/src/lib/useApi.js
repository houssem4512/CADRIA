import { useCallback, useEffect, useRef, useState } from 'react'
import api, { errorMessage, invalidateCache } from './api'

/**
 * useQuery('/projects/', { params })
 * → { data, loading, error, refetch, mutate }
 */
export function useQuery(url, options = {}) {
  const { params, enabled = true, initialData = null } = options
  const [data, setData] = useState(initialData)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState(null)
  const mounted = useRef(true)

  const key = `${url}::${JSON.stringify(params || {})}`

  const load = useCallback(async () => {
    if (!enabled) return
    setLoading(true)
    setError(null)
    try {
      const res = await api.get(url, { params })
      if (mounted.current) setData(res.data)
    } catch (e) {
      if (mounted.current) setError(errorMessage(e))
    } finally {
      if (mounted.current) setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled])

  useEffect(() => {
    mounted.current = true
    load()
    return () => { mounted.current = false }
  }, [load])

  const mutate = useCallback((updater) => {
    setData((prev) => (typeof updater === 'function' ? updater(prev) : updater))
  }, [])

  return { data, loading, error, refetch: load, mutate, setData }
}

/** Mutation simple : POST/PATCH/DELETE avec état de chargement. */
export function useMutation(method = 'post') {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const run = useCallback(async (url, payload, config) => {
    setLoading(true)
    setError(null)
    try {
      const res = await api[method](url, payload, config)
      return res.data
    } catch (e) {
      const msg = errorMessage(e)
      setError(msg)
      throw Object.assign(new Error(msg), { cause: e })
    } finally {
      setLoading(false)
    }
  }, [method])

  return { run, loading, error, setError }
}

/** Liste paginée DRF avec recherche + filtres. */
export function usePaged(url, initialParams = {}) {
  const [params, setParams] = useState({ page: 1, ...initialParams })
  const { data, loading, error, refetch } = useQuery(url, { params })
  const results = data?.results ?? data ?? []
  const count = data?.count ?? results.length
  const page = data?.page ?? params.page ?? 1
  const pageSize = data?.page_size ?? 25

  const setFilter = useCallback((patch) => {
    setParams((p) => ({ ...p, page: 1, ...patch }))
  }, [])

  return {
    results, count, page, pageSize, loading, error, params,
    setPage: (p) => setParams((prev) => ({ ...prev, page: p })),
    setFilter, refetch, setParams,
  }
}

/** Debounce une valeur (recherche instantanée). */
export function useDebounced(value, delay = 300) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return v
}

/** Rafraîchit périodiquement (dashboard live). */
export function useInterval(callback, delay) {
  const saved = useRef(callback)
  useEffect(() => { saved.current = callback }, [callback])
  useEffect(() => {
    if (!delay) return
    const id = setInterval(() => saved.current(), delay)
    return () => clearInterval(id)
  }, [delay])
}

/** Invalide le cache API puis recharge une liste. */
export function refresh(prefix) {
  invalidateCache(prefix)
}

export { api, errorMessage }
