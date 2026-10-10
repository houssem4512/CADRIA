import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Archive, ArchiveRestore, Bell, BellOff, Check, CheckCheck, Filter, Megaphone, RefreshCw,
  Search, Settings2, Star, Trash2, X,
} from 'lucide-react'
import api, { errorMessage } from '../../lib/api'
import { useQuery } from '../../lib/useApi'
import { useNotifications } from '../../context/NotificationContext'
import {
  Alert, Badge, Button, Card, CardHeader, EmptyState, Modal, SearchInput, Select, Skeleton,
  Toggle,
} from '../../components/ui'
import { NOTIF_CATEGORY, NOTIF_LEVEL, cx, formatDate, formatDateTime, timeAgo } from '../../lib/format'

const CATEGORIES = [
  { value: '', label: 'Toutes les catégories' },
  ...Object.entries(NOTIF_CATEGORY).map(([k, v]) => ({ value: k, label: v })),
]

const LEVELS = [
  { value: '', label: 'Tous les niveaux' },
  { value: 'INFO', label: 'Information' }, { value: 'SUCCESS', label: 'Succès' },
  { value: 'WARNING', label: 'Avertissement' }, { value: 'ERROR', label: 'Erreur' },
  { value: 'AGENT', label: 'Agent' },
]

export default function NotificationCenter() {
  const { summary, refresh: refreshGlobal, markAllRead: globalMarkAll } = useNotifications()
  const [filter, setFilter] = useState('all') // all | unread | starred | archived
  const [category, setCategory] = useState('')
  const [level, setLevel] = useState('')
  const [search, setSearch] = useState('')
  const [prefsOpen, setPrefsOpen] = useState(false)
  const [busy, setBusy] = useState(null)

  const { data, loading, refetch } = useQuery('/notifications/', {
    params: {
      page_size: 60,
      ...(filter === 'unread' ? { unread: 'true' } : {}),
      ...(filter === 'archived' ? { archived: 'true' } : {}),
      ...(category ? { category } : {}),
      ...(level ? { level } : {}),
      ...(search ? { search } : {}),
    },
  })

  const items = data?.results ?? data ?? []
  const list = useMemo(() => {
    let l = items
    if (filter === 'unread') l = l.filter((n) => !n.is_read)
    if (filter === 'starred') l = l.filter((n) => n.starred && !n.archived)
    if (filter !== 'archived') l = l.filter((n) => !n.archived)
    return l
  }, [items, filter])

  const act = async (id, path, patch) => {
    setBusy(id)
    try { await api.post(`/notifications/${id}/${path}/`); await refetch(); refreshGlobal() }
    catch (e) { /* silencieux */ }
    finally { setBusy(null) }
  }

  const remove = async (id) => {
    setBusy(id)
    try { await api.delete(`/notifications/${id}/`); await refetch(); refreshGlobal() }
    finally { setBusy(null) }
  }

  const markAll = async () => { await globalMarkAll(); await refetch() }

  const counts = {
    all: summary.total || 0,
    unread: summary.unread || 0,
    starred: items.filter((n) => n.starred).length,
    archived: items.filter((n) => n.archived).length,
  }

  return (
    <div className="space-y-5 p-5 sm:p-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Communication</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Centre de notifications</h1>
          <p className="mt-1 text-[14px] text-slate-500">
            {num(summary.total)} notification{summary.total > 1 ? 's' : ''} ·{' '}
            <span className={summary.unread ? 'font-semibold text-brand-700' : ''}>{num(summary.unread)} non lue{summary.unread > 1 ? 's' : ''}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" icon={RefreshCw} onClick={() => { refetch(); refreshGlobal() }}>Actualiser</Button>
          <Button variant="secondary" icon={Settings2} onClick={() => setPrefsOpen(true)}>Préférences</Button>
          <Button icon={CheckCheck} onClick={markAll} disabled={!summary.unread}>Tout marquer comme lu</Button>
        </div>
      </header>

      {/* ------------------------------- Répartition ------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Non lues</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-brand-700">{num(summary.unread || 0)}</p>
        </Card>
        {['RISK', 'AGENT', 'VALIDATION', 'INTEGRATION'].map((c) => (
          <Card key={c} className="p-4">
            <p className="text-[11.5px] font-medium text-slate-500">{NOTIF_CATEGORY[c]}</p>
            <p className="mt-2 text-[24px] font-bold leading-none text-slate-900">
              {num((summary.by_category || {})[c] || 0)}
            </p>
          </Card>
        ))}
      </div>

      {/* ------------------------------- Filtres ------------------------------- */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap gap-1.5">
            {[['all', 'Toutes', Bell], ['unread', 'Non lues', BellOff], ['starred', 'Suivies', Star], ['archived', 'Archivées', Archive]].map(([k, l, Icon]) => (
              <button key={k} onClick={() => setFilter(k)}
                className={cx('flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[12.5px] font-medium transition',
                  filter === k ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300')}>
                <Icon size={13} /> {l}
                <span className={cx('rounded-full px-1.5 py-0.5 text-[10px] font-bold',
                  filter === k ? 'bg-brand-200 text-brand-800' : 'bg-slate-100 text-slate-500')}>
                  {counts[k]}
                </span>
              </button>
            ))}
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <SearchInput value={search} onChange={setSearch} placeholder="Rechercher…" className="w-[200px]" />
            <Select value={category} onChange={(e) => setCategory(e.target.value)} options={CATEGORIES} className="w-[170px]" />
            <Select value={level} onChange={(e) => setLevel(e.target.value)} options={LEVELS} className="w-[160px]" />
          </div>
        </div>
      </Card>

      {/* ------------------------------- Liste ------------------------------- */}
      {loading ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}</div>
      ) : list.length === 0 ? (
        <EmptyState icon={Bell} title="Aucune notification"
          description={filter === 'unread' ? 'Tout est à jour — aucune notification non lue.'
            : filter === 'starred' ? 'Suivez les notifications importantes avec l’étoile.'
            : 'Les alertes de risque, assignations et validations apparaîtront ici.'} />
      ) : (
        <div className="space-y-2">
          {list.map((n) => {
            const tone = NOTIF_LEVEL[n.level] || NOTIF_LEVEL.INFO
            return (
              <Card key={n.id} className={cx('overflow-hidden transition hover:shadow-card', !n.is_read && 'ring-1 ring-brand-200')}>
                <div className="flex items-start gap-3.5 p-4">
                  <span className={cx('mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-lg', tone.bg, tone.ring, 'ring-1 ring-inset')}>
                    <span className={cx('h-2.5 w-2.5 rounded-full', tone.dot)} />
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {n.is_broadcast && <Badge className="badge-purple"><Megaphone size={10} /> Diffusion</Badge>}
                      <p className={cx('text-[13.5px]', n.is_read ? 'font-medium text-slate-700' : 'font-semibold text-slate-900')}>
                        {n.title}
                      </p>
                      <Badge className={tone.cls}>{NOTIF_CATEGORY[n.category] || n.category}</Badge>
                      {n.starred && <Star size={12} className="fill-amber-400 text-amber-400" />}
                    </div>
                    {n.message && <p className="mt-1 text-[12.5px] leading-relaxed text-slate-600">{n.message}</p>}
                    <p className="mt-1.5 text-[11px] text-slate-400">
                      {formatDateTime(n.created_at)} · {timeAgo(n.created_at)}
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-1">
                    {n.link && (
                      <Link to={n.link} className="btn btn-secondary btn-sm">
                        <Search size={13} /> Ouvrir
                      </Link>
                    )}
                    <IconBtn label={n.is_read ? 'Marquer non lu' : 'Marquer comme lu'}
                      onClick={() => act(n.id, n.is_read ? 'mark_unread' : 'mark_read')}
                      busy={busy === n.id}>
                      {n.is_read ? <BellOff size={15} /> : <Check size={15} />}
                    </IconBtn>
                    {!n.is_broadcast && (
                      <>
                        <IconBtn label="Suivre" onClick={() => act(n.id, 'toggle_star')} busy={busy === n.id}
                          active={n.starred}>
                          <Star size={15} className={n.starred ? 'fill-amber-400 text-amber-400' : ''} />
                        </IconBtn>
                        <IconBtn label={n.archived ? 'Restaurer' : 'Archiver'} onClick={() => act(n.id, 'archive')} busy={busy === n.id}>
                          {n.archived ? <ArchiveRestore size={15} /> : <Archive size={15} />}
                        </IconBtn>
                        <IconBtn label="Supprimer" danger onClick={() => remove(n.id)} busy={busy === n.id}>
                          <Trash2 size={15} />
                        </IconBtn>
                      </>
                    )}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {prefsOpen && <PreferencesModal onClose={() => setPrefsOpen(false)} />}
    </div>
  )
}

function IconBtn({ children, label, onClick, busy, active, danger }) {
  return (
    <button title={label} onClick={onClick} disabled={busy}
      className={cx('btn btn-ghost btn-icon rounded-lg',
        danger ? 'text-rose-500 hover:bg-rose-50 hover:text-rose-700' : 'hover:bg-slate-100',
        active && 'text-amber-500')}>
      {children}
    </button>
  )
}

function PreferencesModal({ onClose }) {
  const { data, refetch } = useQuery('/notifications/preferences/')
  const { data: meData } = useQuery('/me/')
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [prefs, setPrefs] = useState(null)
  const [me, setMe] = useState(null)

  const channels = prefs || data || {}
  const user = me || meData || {}

  const patchChannel = async (key, value) => {
    setPrefs({ ...(prefs || data || {}), [key]: value })
    await api.patch('/notifications/preferences/', { [key]: value })
  }

  const patchUser = async (key, value) => {
    setMe({ ...(me || meData || {}), [key]: value })
    setSaving(true)
    try { await api.patch('/me/', { [key]: value }); setMsg('Préférences enregistrées.') }
    catch (e) { setMsg(errorMessage(e)) }
    finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title="Préférences de notification" size="lg" icon={Settings2}
      footer={<Button onClick={onClose}>Terminé</Button>}>
      {msg && <Alert tone="success" className="mb-4">{msg}</Alert>}

      <div className="space-y-5">
        <section>
          <p className="label">Canaux de diffusion</p>
          <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 px-4">
            <Toggle checked={channels.in_app} onChange={(v) => patchChannel('in_app', v)}
              label="Notifications in-app" description="Centre de notifications et toasts dans l’application" />
            <Toggle checked={channels.email} onChange={(v) => patchChannel('email', v)}
              label="E-mail" description="Récapitulatif envoyé à votre adresse professionnelle" />
            <Toggle checked={channels.slack} onChange={(v) => patchChannel('slack', v)}
              label="Slack" description="Intégration via webhook (non branchée en démonstration)" />
          </div>
        </section>

        <section>
          <p className="label">Types d’évènements</p>
          <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 px-4">
            <Toggle checked={user.notify_risk_alerts} onChange={(v) => patchUser('notify_risk_alerts', v)}
              label="Alertes de risque" description="Retards, dérive de charge, bugs récurrents" />
            <Toggle checked={user.notify_assignments} onChange={(v) => patchUser('notify_assignments', v)}
              label="Assignations de tâches" description="Lorsqu’une tâche vous est attribuée ou réassignée" />
            <Toggle checked={user.notify_agent_runs} onChange={(v) => patchUser('notify_agent_runs', v)}
              label="Exécutions d’agents" description="Fin d’analyse, plan proposé, échec d’exécution" />
            <Toggle checked={user.notify_weekly_digest} onChange={(v) => patchUser('notify_weekly_digest', v)}
              label="Récapitulatif hebdomadaire" description="Synthèse des projets chaque lundi" />
          </div>
        </section>

        <section>
          <p className="label">Fréquence de synthèse</p>
          <Select value={channels.digest_frequency || 'REALTIME'}
            onChange={(e) => patchChannel('digest_frequency', e.target.value)}
            options={[
              { value: 'REALTIME', label: 'Temps réel' },
              { value: 'DAILY', label: 'Quotidien' },
              { value: 'WEEKLY', label: 'Hebdomadaire' },
            ]} />
        </section>

        <Alert tone="info">
          Les diffusions d’annonces envoyées par l’administration s’appliquent à tous les utilisateurs
          et ne peuvent pas être désactivées individuellement.
        </Alert>
      </div>
    </Modal>
  )
}

function num(v) {
  return Number(v || 0).toLocaleString('fr-FR')
}
