import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Activity, Bell, ChevronDown, Command, FolderKanban, Gauge, History, LayoutDashboard,
  LogOut, Menu, Plug, Plus, Search, Settings, Sparkles, Users, X, Check,
  PanelLeftClose, PanelLeft, Sun, Moon, CircleHelp,
} from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { useNotifications } from '../../context/NotificationContext'
import { Logo } from '../Logo'
import { cx, timeAgo, NOTIF_LEVEL, ROLE_LABEL } from '../../lib/format'
import { Avatar, Badge, Button, IconButton } from '../ui'

const NAV_CLIENT = [
  { to: '/app', label: 'Tableau de bord', icon: LayoutDashboard, end: true },
  { to: '/app/projects', label: 'Projets', icon: FolderKanban },
  { to: '/app/tasks', label: 'Mes tâches', icon: Activity },
  { to: '/app/agents', label: 'Copilote & agents', icon: Sparkles },
  { to: '/app/teams', label: 'Équipes', icon: Users },
  { to: '/app/notifications', label: 'Notifications', icon: Bell },
  { to: '/app/history', label: 'Historique', icon: History },
]

/** Interface membre d'équipe : tâches et projets en consultation uniquement. */
const NAV_MEMBER = [
  { to: '/app', label: 'Tableau de bord', icon: LayoutDashboard, end: true },
  { to: '/app/tasks', label: 'Mes tâches', icon: Activity },
  { to: '/app/projects', label: 'Mes projets', icon: FolderKanban },
  { to: '/app/notifications', label: 'Notifications', icon: Bell },
]

const NAV_ADMIN = [
  { to: '/admin', label: 'Vue d’ensemble', icon: Gauge, end: true },
  { to: '/admin/users', label: 'Comptes', icon: Users },
  { to: '/admin/projects', label: 'Projets', icon: FolderKanban },
  { to: '/admin/agents', label: 'Supervision agents', icon: Sparkles },
  { to: '/admin/audit', label: "Journal d'audit", icon: History },
  { to: '/admin/announcements', label: 'Annonces', icon: Bell },
  { to: '/admin/settings', label: 'Paramètres', icon: Settings },
]

export default function AppLayout({ mode = 'client' }) {
  const { user, logout, canPilot } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { unread, items, markRead, markAllRead } = useNotifications()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const [bellOpen, setBellOpen] = useState(false)
  const [userOpen, setUserOpen] = useState(false)
  const [commandOpen, setCommandOpen] = useState(false)

  const isAdmin = mode === 'admin'
  const nav = isAdmin ? NAV_ADMIN : (canPilot ? NAV_CLIENT : NAV_MEMBER)
  const accent = isAdmin ? 'from-brand-800 to-brand-600' : 'from-brand-700 to-sky-500'

  useEffect(() => { setSidebarOpen(false); setBellOpen(false); setUserOpen(false) }, [location.pathname])

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setCommandOpen(true) }
      if (e.key === 'Escape') { setCommandOpen(false); setBellOpen(false); setUserOpen(false) }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    const onClick = () => { setBellOpen(false); setUserOpen(false) }
    if (bellOpen || userOpen) {
      // laisse le temps au clic courant de se propager
      const t = setTimeout(() => document.addEventListener('click', onClick), 0)
      return () => { clearTimeout(t); document.removeEventListener('click', onClick) }
    }
  }, [bellOpen, userOpen])

  const role = ROLE_LABEL[user?.role] || ROLE_LABEL.MEMBER

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* ------------------------------ Sidebar ------------------------------ */}
      <aside className={cx(
        'fixed inset-y-0 left-0 z-40 flex flex-col border-r border-slate-200 bg-white transition-all duration-200 lg:static lg:translate-x-0',
        collapsed ? 'lg:w-[72px]' : 'lg:w-[252px]',
        sidebarOpen ? 'w-[252px] translate-x-0' : '-translate-x-full w-[252px]',
      )}>
        <div className={cx('flex h-16 items-center border-b border-slate-100 px-4', collapsed && 'lg:justify-center lg:px-0')}>
          <Link to="/app" className="shrink-0">
            <Logo withText={!collapsed} />
          </Link>
          <button onClick={() => setSidebarOpen(false)} className="ml-auto btn btn-ghost btn-icon lg:hidden">
            <X size={18} />
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto p-3">
          {isAdmin && (
            <div className={cx('mb-3 rounded-lg bg-gradient-to-r px-3 py-2 text-white', accent)}>
              <p className="text-[11px] font-semibold uppercase tracking-wider opacity-80">Espace</p>
              <p className="text-sm font-bold">Administration</p>
            </div>
          )}
          {nav.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) => cx(
                'group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13.5px] font-medium transition',
                isActive
                  ? 'bg-brand-50 text-brand-700'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
                collapsed && 'lg:justify-center lg:px-0',
              )}>
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brand-600" />}
                  <item.icon size={17} className={cx('shrink-0', isActive && 'text-brand-600')} />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                  {!collapsed && item.to.endsWith('/notifications') && unread > 0 && (
                    <span className="ml-auto rounded-full bg-rose-500 px-1.5 py-0.5 text-[10px] font-bold text-white">
                      {unread > 99 ? '99+' : unread}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {(isAdmin || canPilot) && (
          <div className="border-t border-slate-100 p-3">
            {!collapsed ? (
              <div className="rounded-xl bg-gradient-to-br from-brand-50 to-sky-50 p-3.5">
                <div className="flex items-center gap-2 text-brand-800">
                  <Sparkles size={15} />
                  <span className="text-[12.5px] font-semibold">Agents en attente</span>
                </div>
                <p className="mt-1.5 text-[11.5px] leading-relaxed text-slate-600">
                  Les 3 agents sont réservés. Branchez le runtime pour activer le copilote.
                </p>
                <Link to={isAdmin ? '/admin/agents' : '/app/agents'}
                  className="mt-2.5 inline-flex text-[11.5px] font-semibold text-brand-700 hover:underline">
                  Voir le contrat →
                </Link>
              </div>
            ) : (
              <div className="hidden lg:block">
                <Link to={isAdmin ? '/admin/agents' : '/app/agents'}
                  className="grid h-10 w-10 place-items-center rounded-lg bg-brand-50 text-brand-600" title="Agents">
                  <Sparkles size={17} />
                </Link>
              </div>
            )}
          </div>
        )}
      </aside>

      {sidebarOpen && <div className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden" onClick={() => setSidebarOpen(false)} />}

      {/* ------------------------------ Main ------------------------------ */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur-md sm:px-6">
          <button onClick={() => setSidebarOpen(true)} className="btn btn-ghost btn-icon lg:hidden"><Menu size={19} /></button>
          <button onClick={() => setCollapsed((c) => !c)} className="btn btn-ghost btn-icon hidden lg:inline-flex">
            {collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
          </button>

          <button onClick={() => setCommandOpen(true)}
            className="hidden h-9 w-full max-w-md items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 text-left text-[13px] text-slate-400 transition hover:border-slate-300 hover:bg-white md:flex">
            <Search size={15} />
            <span className="flex-1">Rechercher un projet, une tâche, un membre…</span>
            <kbd className="rounded border border-slate-300 bg-white px-1.5 py-0.5 text-[10px] font-semibold text-slate-500">⌘K</kbd>
          </button>

          <div className="ml-auto flex items-center gap-1">
            {!isAdmin && canPilot && (
              <Link to="/app/projects/new" className="btn btn-primary btn-sm hidden sm:inline-flex">
                <Plus size={15} /> Nouveau projet
              </Link>
            )}

            {/* Cloche de notifications */}
            <div className="relative">
              <button onClick={(e) => { e.stopPropagation(); setBellOpen((o) => !o); setUserOpen(false) }}
                className="btn btn-ghost btn-icon relative" title="Notifications">
                <Bell size={18} />
                {unread > 0 && (
                  <span className="absolute right-1 top-1 grid h-4 min-w-[16px] place-items-center rounded-full bg-rose-500 px-1 text-[9.5px] font-bold text-white ring-2 ring-white">
                    {unread > 9 ? '9+' : unread}
                  </span>
                )}
              </button>
              {bellOpen && (
                <div onClick={(e) => e.stopPropagation()}
                  className="absolute right-0 top-12 z-50 w-[360px] max-w-[calc(100vw-2rem)] animate-scale-in overflow-hidden rounded-xl border border-slate-200 bg-white shadow-panel">
                  <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                    <span className="text-[13.5px] font-semibold text-slate-900">Notifications</span>
                    {unread > 0 && (
                      <button onClick={markAllRead} className="text-[12px] font-medium text-brand-600 hover:underline">
                        Tout marquer comme lu
                      </button>
                    )}
                  </div>
                  <div className="max-h-[380px] divide-y divide-slate-100 overflow-y-auto">
                    {items.length === 0 ? (
                      <p className="px-4 py-8 text-center text-[13px] text-slate-500">Aucune notification.</p>
                    ) : items.slice(0, 7).map((n) => {
                      const tone = NOTIF_LEVEL[n.level] || NOTIF_LEVEL.INFO
                      return (
                        <Link key={n.id} to={n.link || (isAdmin ? '/admin/announcements' : '/app/notifications')}
                          onClick={() => markRead(n.id)}
                          className={cx('flex gap-3 px-4 py-3 transition hover:bg-slate-50', !n.is_read && 'bg-brand-50/40')}>
                          <span className={cx('mt-1.5 h-2 w-2 shrink-0 rounded-full', n.is_read ? 'bg-slate-300' : tone.dot)} />
                          <div className="min-w-0 flex-1">
                            <p className={cx('truncate text-[13px]', n.is_read ? 'text-slate-600' : 'font-semibold text-slate-900')}>{n.title}</p>
                            <p className="mt-0.5 line-clamp-2 text-[12px] text-slate-500">{n.message}</p>
                            <p className="mt-1 text-[11px] text-slate-400">{timeAgo(n.created_at)}</p>
                          </div>
                        </Link>
                      )
                    })}
                  </div>
                  <Link to={isAdmin ? '/admin/announcements' : '/app/notifications'}
                    className="block border-t border-slate-100 bg-slate-50/70 px-4 py-2.5 text-center text-[12.5px] font-semibold text-brand-700 hover:bg-slate-100">
                    Voir toutes les notifications
                  </Link>
                </div>
              )}
            </div>

            {/* Menu utilisateur */}
            <div className="relative">
              <button onClick={(e) => { e.stopPropagation(); setUserOpen((o) => !o); setBellOpen(false) }}
                className="flex items-center gap-2 rounded-lg p-1 pr-2 transition hover:bg-slate-100">
                <Avatar name={user?.full_name} color={user?.avatar_color} size={32} />
                <div className="hidden text-left sm:block">
                  <p className="text-[12.5px] font-semibold leading-tight text-slate-800">{user?.full_name}</p>
                  <p className="text-[11px] leading-tight text-slate-500">{role.label}</p>
                </div>
                <ChevronDown size={14} className="text-slate-400" />
              </button>
              {userOpen && (
                <div onClick={(e) => e.stopPropagation()}
                  className="absolute right-0 top-12 z-50 w-64 animate-scale-in overflow-hidden rounded-xl border border-slate-200 bg-white shadow-panel">
                  <div className="border-b border-slate-100 px-4 py-3.5">
                    <div className="flex items-center gap-3">
                      <Avatar name={user?.full_name} color={user?.avatar_color} size={40} />
                      <div className="min-w-0">
                        <p className="truncate text-[13.5px] font-semibold text-slate-900">{user?.full_name}</p>
                        <p className="truncate text-[12px] text-slate-500">{user?.email}</p>
                      </div>
                    </div>
                    <div className="mt-2.5"><Badge className={role.cls}>{role.label}</Badge></div>
                  </div>
                  <div className="p-1.5">
                    <MenuItem to={isAdmin ? '/admin/settings' : '/app/profile'} icon={Settings} label="Mon profil & préférences" />
                    <MenuItem to={isAdmin ? '/admin' : '/app'} icon={LayoutDashboard} label="Tableau de bord" />
                    <MenuItem to="/app/notifications" icon={Bell} label="Centre de notifications" />
                  </div>
                  <div className="border-t border-slate-100 p-1.5">
                    <button onClick={async () => { await logout(); navigate('/login') }}
                      className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-rose-600 transition hover:bg-rose-50">
                      <LogOut size={16} /> Se déconnecter
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>

      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} nav={nav}
        canCreateProject={!isAdmin && canPilot} />
    </div>
  )
}

function MenuItem({ to, icon: Icon, label }) {
  return (
    <Link to={to} className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] font-medium text-slate-700 transition hover:bg-slate-100">
      <Icon size={16} className="text-slate-400" /> {label}
    </Link>
  )
}

/* --------------------------- Palette de commandes --------------------------- */
function CommandPalette({ open, onClose, nav, canCreateProject }) {
  const [q, setQ] = useState('')
  const navigate = useNavigate()
  const results = useMemo(() => {
    const actions = [
      ...nav.map((n) => ({ label: n.label, to: n.to, icon: n.icon, group: 'Navigation' })),
      ...(canCreateProject ? [{ label: 'Nouveau projet', to: '/app/projects/new', icon: Plus, group: 'Actions' }] : []),
      { label: 'Voir le site public', to: '/', icon: CircleHelp, group: 'Actions' },
    ]
    if (!q) return actions
    return actions.filter((a) => a.label.toLowerCase().includes(q.toLowerCase()))
  }, [q, nav, canCreateProject])

  useEffect(() => { if (!open) setQ('') }, [open])
  if (!open) return null

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-slate-900/40 p-4 pt-[12vh] backdrop-blur-sm" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg animate-scale-in overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-panel">
        <div className="flex items-center gap-3 border-b border-slate-100 px-4">
          <Command size={17} className="text-slate-400" />
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Rechercher une page ou une action…"
            className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-slate-400" />
          <kbd className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] text-slate-500">ESC</kbd>
        </div>
        <div className="max-h-80 overflow-y-auto p-2">
          {results.length === 0 && <p className="px-3 py-8 text-center text-[13px] text-slate-500">Aucun résultat.</p>}
          {results.map((r, i) => (
            <button key={i} onClick={() => { navigate(r.to); onClose() }}
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[13.5px] text-slate-700 transition hover:bg-brand-50 hover:text-brand-800">
              <r.icon size={16} className="text-slate-400" />
              <span className="flex-1">{r.label}</span>
              <span className="text-[11px] text-slate-400">{r.group}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
