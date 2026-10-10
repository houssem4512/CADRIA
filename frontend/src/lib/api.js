import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 25000,
})

const TOKEN_KEY = 'cadria.access'
const REFRESH_KEY = 'cadria.refresh'

export const tokenStore = {
  get access() { return localStorage.getItem(TOKEN_KEY) },
  get refresh() { return localStorage.getItem(REFRESH_KEY) },
  set(access, refresh) {
    localStorage.setItem(TOKEN_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

api.interceptors.request.use((config) => {
  const token = tokenStore.access
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let refreshPromise = null

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry && tokenStore.refresh) {
      original._retry = true
      try {
        refreshPromise =
          refreshPromise ||
          axios.post('/api/auth/refresh/', { refresh: tokenStore.refresh })
        const { data } = await refreshPromise
        tokenStore.set(data.access, data.refresh || tokenStore.refresh)
        original.headers.Authorization = `Bearer ${data.access}`
        return api(original)
      } catch {
        tokenStore.clear()
        window.dispatchEvent(new CustomEvent('cadria:session-expired'))
      } finally {
        refreshPromise = null
      }
    }
    return Promise.reject(error)
  },
)

/** Normalise une erreur API en message lisible. */
export function errorMessage(error, fallback = 'Une erreur est survenue.') {
  const data = error?.response?.data
  if (!data) return error?.message || fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const first = Object.values(data)[0]
  if (Array.isArray(first)) return first[0]
  if (typeof first === 'string') return first
  return fallback
}

/** Aplatit les erreurs de validation DRF en { champ: message }. */
export function fieldErrors(error) {
  const data = error?.response?.data
  const out = {}
  if (data && typeof data === 'object' && !data.detail) {
    for (const [k, v] of Object.entries(data)) {
      out[k] = Array.isArray(v) ? v[0] : typeof v === 'string' ? v : 'Valeur invalide'
    }
  }
  return out
}

/** Petit cache mémoire GET pour éviter les allers-retours inutiles. */
const cache = new Map()
export async function cachedGet(url, config, ttl = 15000) {
  const key = url + JSON.stringify(config?.params || {})
  const hit = cache.get(key)
  if (hit && Date.now() - hit.t < ttl) return hit.data
  const res = await api.get(url, config)
  cache.set(key, { t: Date.now(), data: res.data })
  return res.data
}
export function invalidateCache(prefix = '') {
  for (const k of [...cache.keys()]) if (k.startsWith(prefix)) cache.delete(k)
}

/** Retourne toutes les pages d'une liste paginée DRF. */
export async function fetchAll(url, params = {}, maxPages = 20) {
  let results = []
  let page = 1
  let next = true
  while (next && page <= maxPages) {
    const { data } = await api.get(url, { params: { ...params, page } })
    results = results.concat(data.results || data)
    next = !!data.next
    page += 1
  }
  return results
}

export default api
