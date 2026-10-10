import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import api, { errorMessage, tokenStore } from '../lib/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    if (!tokenStore.access) {
      setLoading(false)
      return null
    }
    try {
      const { data } = await api.get('/me/')
      setUser(data)
      return data
    } catch {
      tokenStore.clear()
      setUser(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const onExpired = () => {
      tokenStore.clear()
      setUser(null)
      window.location.href = '/login?expired=1'
    }
    window.addEventListener('cadria:session-expired', onExpired)
    return () => window.removeEventListener('cadria:session-expired', onExpired)
  }, [load])

  const login = useCallback(async (email, password) => {
    const { data } = await api.post('/auth/login/', { email, password })
    tokenStore.set(data.access, data.refresh)
    setUser(data.user)
    return data.user
  }, [])

  const register = useCallback(async (payload) => {
    const { data } = await api.post('/auth/register/', payload)
    tokenStore.set(data.access, data.refresh)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout/', { refresh: tokenStore.refresh })
    } catch { /* on purge côté client quoi qu'il arrive */ }
    tokenStore.clear()
    setUser(null)
  }, [])

  const updateUser = useCallback((patch) => {
    setUser((u) => (u ? { ...u, ...patch } : u))
  }, [])

  const isAdmin = user?.role === 'ADMIN' || user?.is_superuser
  const isPM = user?.role === 'PM'
  const value = useMemo(() => ({
    user, loading, login, register, logout, updateUser, refresh: load,
    isAdmin,
    isPM,
    /** PM ou ADMIN : peut créer des projets, lancer les agents, valider les plans. */
    canPilot: isAdmin || isPM,
    /** Espace d'accueil selon le rôle : admin → /admin, autres → /app. */
    homePath: isAdmin ? '/admin' : '/app',
  }), [user, loading, login, register, logout, updateUser, load, isAdmin, isPM])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth doit être utilisé dans <AuthProvider>')
  return ctx
}

export { errorMessage }
