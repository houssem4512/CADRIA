import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import api, { invalidateCache } from '../lib/api'
import { useAuth } from './AuthContext'

const NotificationContext = createContext(null)
const POLL_INTERVAL = 45000

export function NotificationProvider({ children }) {
  const { user } = useAuth()
  const [summary, setSummary] = useState({ unread: 0, total: 0 })
  const [items, setItems] = useState([])
  const [toasts, setToasts] = useState([])
  const seenRef = useRef(new Set())
  const initialised = useRef(false)

  const refresh = useCallback(async () => {
    if (!user) return
    try {
      const [{ data: s }, { data: list }] = await Promise.all([
        api.get('/notifications/summary/'),
        api.get('/notifications/', { params: { page_size: 8 } }),
      ])
      setSummary(s)
      const results = list.results || list
      setItems(results)

      // Nouvelles notifications → toast (sauf au premier chargement)
      if (initialised.current) {
        for (const n of results) {
          if (!seenRef.current.has(n.id) && !n.is_read) {
            seenRef.current.add(n.id)
            setToasts((t) => [...t.slice(-2), { ...n, _key: `${n.id}-${Date.now()}` }])
            setTimeout(() => setToasts((t) => t.filter((x) => x._key !== `${n.id}-${n.id}`)), 100)
          }
          seenRef.current.add(n.id)
        }
      } else {
        results.forEach((n) => seenRef.current.add(n.id))
        initialised.current = true
      }
    } catch { /* silencieux : le polling ne doit pas casser l'app */ }
  }, [user])

  useEffect(() => {
    if (!user) { setItems([]); setSummary({ unread: 0, total: 0 }); return }
    refresh()
    const id = setInterval(refresh, POLL_INTERVAL)
    return () => clearInterval(id)
  }, [user, refresh])

  const markAllRead = useCallback(async () => {
    setItems((l) => l.map((n) => ({ ...n, is_read: true, read: true })))
    setSummary((s) => ({ ...s, unread: 0 }))
    try {
      await api.post('/notifications/mark_all_read/')
      invalidateCache('/notifications')
    } catch { /* noop */ }
  }, [])

  const markRead = useCallback(async (id) => {
    setItems((l) => l.map((n) => (n.id === id ? { ...n, is_read: true, read: true } : n)))
    setSummary((s) => ({ ...s, unread: Math.max(0, (s.unread || 1) - 1) }))
    try {
      await api.post(`/notifications/${id}/mark_read/`)
      invalidateCache('/notifications')
    } catch { /* noop */ }
  }, [])

  const dismissToast = useCallback((key) => {
    setToasts((t) => t.filter((x) => x._key !== key))
  }, [])

  const pushToast = useCallback((toast) => {
    setToasts((t) => [...t.slice(-2), toast])
  }, [])

  const value = useMemo(() => ({
    summary, items, toasts, refresh, markAllRead, markRead, dismissToast, pushToast,
    unread: summary.unread || 0,
  }), [summary, items, toasts, refresh, markAllRead, markRead, dismissToast, pushToast])

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>
}

export function useNotifications() {
  const ctx = useContext(NotificationContext)
  if (!ctx) throw new Error('useNotifications doit être utilisé dans <NotificationProvider>')
  return ctx
}
