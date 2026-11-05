import { useMemo, useState } from 'react'
import {
  Check, Download, Edit3, Eye, EyeOff, Filter, KeyRound, Mail, MoreHorizontal, Plus,
  RefreshCw, Search, ShieldCheck, ShieldOff, Trash2, UserPlus, Users, X,
} from 'lucide-react'
import api, { errorMessage, fieldErrors } from '../../lib/api'
import { usePaged, useDebounced } from '../../lib/useApi'
import { useAuth } from '../../context/AuthContext'
import {
  Alert, Avatar, Badge, Button, Card, ConfirmDialog, EmptyState, Input, Modal, Pagination,
  Progress, SearchInput, Select, TableSkeleton, Textarea,
} from '../../components/ui'
import { ROLE_LABEL, USER_STATUS, cx, formatDate, hours, num, timeAgo, toCSV } from '../../lib/format'

const ROLE_OPTIONS = [
  { value: 'ADMIN', label: 'Administrateur', desc: 'Accès complet : comptes, supervision, paramètres' },
  { value: 'PM', label: 'Chef de projet', desc: 'Pilote ses projets, lance les agents, valide les plans' },
  { value: 'MEMBER', label: 'Membre d’équipe', desc: 'Travaille sur les tâches assignées' },
  { value: 'VIEWER', label: 'Observateur', desc: 'Consultation seule des projets et indicateurs' },
]

const STATUS_OPTIONS = [
  { value: 'ACTIVE', label: 'Actif' },
  { value: 'PENDING', label: 'En attente' },
  { value: 'SUSPENDED', label: 'Suspendu' },
]

export default function AdminUsers() {
  const { user: me } = useAuth()
  const [search, setSearch] = useState('')
  const debounced = useDebounced(search, 300)
  const [role, setRole] = useState('')
  const [status, setStatus] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [selected, setSelected] = useState([])
  const [editing, setEditing] = useState(null)
  const [creating, setCreating] = useState(false)
  const [detail, setDetail] = useState(null)
  const [confirm, setConfirm] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)

  const { results, count, page, pageSize, loading, setPage, setFilter, refetch } = usePaged('/users/', {
    ...(debounced ? { search: debounced } : {}),
    ...(role ? { role } : {}),
    ...(status ? { status } : {}),
    ordering: '-created_at',
  })

  const allSelected = selected.length > 0 && selected.length === results.length
  const toggleAll = () => setSelected(allSelected ? [] : results.map((u) => u.id))
  const toggle = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id])

  const bulk = async (action, extra = {}) => {
    setBusy(true)
    try {
      const { data } = await api.post('/users/bulk_action/', { ids: selected, action, ...extra })
      setNotice({ tone: 'success', text: `Action « ${action} » appliquée à ${data.updated} compte(s).` })
      setSelected([]); await refetch()
    } catch (e) { setNotice({ tone: 'error', text: errorMessage(e) }) }
    finally { setBusy(false) }
  }

  const toggleActive = async (u) => {
    setBusy(true)
    try {
      const { data } = await api.post(`/users/${u.id}/toggle_active/`)
      setNotice({
        tone: data.is_active ? 'success' : 'warning',
        text: `${u.full_name} est ${data.is_active ? 'activé' : 'suspendu'}.`,
      })
      await refetch()
    } catch (e) { setNotice({ tone: 'error', text: errorMessage(e) }) }
    finally { setBusy(false) }
  }

  const resetPwd = async (u) => {
    setBusy(true)
    try {
      const { data } = await api.post(`/users/${u.id}/reset_password/`)
      setNotice({ tone: 'success', text: `Mot de passe de ${u.email} réinitialisé : ${data.password}` })
    } catch (e) { setNotice({ tone: 'error', text: errorMessage(e) }) }
    finally { setBusy(false) }
  }

  const exportCsv = () => toCSV(results.map((u) => ({
    nom: u.full_name, email: u.email, role: u.role, statut: u.status,
    poste: u.job_title, organisation: u.company, actif: u.is_active,
    capacite_h: u.weekly_capacity_hours, charge_h: u.workload_hours,
    utilisation: `${u.utilisation}%`, equipes: (u.team_names || []).join(' | '),
    inscrit_le: u.created_at,
  })), 'cadria-comptes.csv')

  return (
    <div className="space-y-5 p-5 sm:p-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Administration</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Gestion des comptes</h1>
          <p className="mt-1 text-[14px] text-slate-500">
            {num(count)} compte{count > 1 ? 's' : ''} · {results.filter((u) => u.is_active).length} actif(s) sur cette page
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" icon={Download} onClick={exportCsv}>Exporter</Button>
          <Button variant="secondary" icon={RefreshCw} onClick={refetch}>Actualiser</Button>
          <Button icon={UserPlus} onClick={() => setCreating(true)}>Créer un compte</Button>
        </div>
      </header>

      {notice && (
        <Alert tone={notice.tone} action={<Button variant="ghost" size="sm" icon={X} onClick={() => setNotice(null)} />}>
          {notice.text}
        </Alert>
      )}

      {/* ------------------------------- Filtres ------------------------------- */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput value={search} onChange={setSearch}
            placeholder="Rechercher un nom, un e-mail, une organisation…" className="min-w-[240px] flex-1" />
          <Button variant="secondary" icon={Filter} onClick={() => setShowFilters((s) => !s)}
            className={cx(showFilters && 'border-brand-400 bg-brand-50 text-brand-700')}>
            Filtres{(role || status) && <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />}
          </Button>
        </div>
        {showFilters && (
          <div className="mt-3 grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-3">
            <Select label="Rôle" value={role} onChange={(e) => setRole(e.target.value)}
              options={[{ value: '', label: 'Tous les rôles' }, ...ROLE_OPTIONS.map((r) => ({ value: r.value, label: r.label }))]} />
            <Select label="Statut" value={status} onChange={(e) => setStatus(e.target.value)}
              options={[{ value: '', label: 'Tous les statuts' }, ...STATUS_OPTIONS]} />
            <div className="flex items-end">
              <Button variant="ghost" icon={X} onClick={() => { setSearch(''); setRole(''); setStatus('') }}>
                Réinitialiser
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* ------------------------------- Actions groupées ------------------------------- */}
      {selected.length > 0 && (
        <Card className="flex flex-wrap items-center gap-3 border-brand-200 bg-brand-50/60 p-3 animate-fade-in">
          <span className="text-[13px] font-semibold text-brand-800">{selected.length} compte(s) sélectionné(s)</span>
          <div className="ml-auto flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" icon={ShieldCheck} loading={busy} onClick={() => bulk('activate')}>Activer</Button>
            <Button variant="secondary" size="sm" icon={ShieldOff} loading={busy} onClick={() => bulk('suspend')}>Suspendre</Button>
            <Select value="" onChange={(e) => e.target.value && bulk('role', { role: e.target.value })}
              className="w-[170px] [&_.field]:h-8"
              options={[{ value: '', label: 'Changer le rôle…' }, ...ROLE_OPTIONS.map((r) => ({ value: r.value, label: r.label }))]} />
            <Button variant="danger" size="sm" icon={Trash2} loading={busy} onClick={() => setConfirm({ bulk: true })}>
              Supprimer
            </Button>
            <Button variant="ghost" size="sm" icon={X} onClick={() => setSelected([])}>Annuler</Button>
          </div>
        </Card>
      )}

      {/* ------------------------------- Tableau ------------------------------- */}
      {loading ? (
        <Card><TableSkeleton rows={8} cols={6} /></Card>
      ) : results.length === 0 ? (
        <EmptyState icon={Users} title="Aucun compte trouvé"
          description="Ajustez la recherche ou les filtres, ou créez un nouveau compte."
          action={<Button icon={UserPlus} onClick={() => setCreating(true)}>Créer un compte</Button>} />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th className="w-10">
                    <input type="checkbox" checked={allSelected} onChange={toggleAll}
                      className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
                  </th>
                  <th>Utilisateur</th><th>Rôle</th><th>Statut</th><th>Charge</th>
                  <th>Équipes</th><th>Inscription</th><th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {results.map((u) => {
                  const r = ROLE_LABEL[u.role] || ROLE_LABEL.MEMBER
                  const s = USER_STATUS[u.status] || {}
                  const util = Number(u.utilisation) || 0
                  const isSelf = u.id === me?.id
                  return (
                    <tr key={u.id} className={cx(!u.is_active && 'opacity-60')}>
                      <td>
                        <input type="checkbox" checked={selected.includes(u.id)} onChange={() => toggle(u.id)}
                          disabled={isSelf}
                          className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500 disabled:opacity-40" />
                      </td>
                      <td>
                        <button onClick={() => setDetail(u)} className="flex items-center gap-2.5 text-left">
                          <Avatar name={u.full_name} color={u.avatar_color} size={34} />
                          <div className="min-w-0">
                            <p className="flex items-center gap-1.5 truncate text-[13px] font-semibold text-slate-800 hover:text-brand-700">
                              {u.full_name}
                              {isSelf && <Badge className="badge-brand">vous</Badge>}
                            </p>
                            <p className="truncate text-[11.5px] text-slate-500">
                              {u.email}{u.job_title ? ` · ${u.job_title}` : ''}
                            </p>
                          </div>
                        </button>
                      </td>
                      <td><Badge className={r.cls}>{r.label}</Badge></td>
                      <td>
                        <Badge className={s.cls} dot={u.is_active ? 'bg-emerald-500' : 'bg-rose-500'}>{s.label}</Badge>
                      </td>
                      <td className="w-[130px]">
                        <div className="flex items-center gap-2">
                          <Progress value={Math.min(100, util)} size={5} className="flex-1"
                            tone={util > 110 ? 'bg-rose-500' : util > 85 ? 'bg-amber-500' : 'bg-brand-600'} />
                          <span className="w-9 text-right text-[11px] font-bold text-slate-600">{Math.round(util)}%</span>
                        </div>
                        <p className="mt-1 text-[10.5px] text-slate-400">
                          {num(u.active_tasks)} tâche(s) · {hours(u.workload_hours)}
                        </p>
                      </td>
                      <td>
                        <div className="flex flex-wrap gap-1">
                          {(u.team_names || []).slice(0, 2).map((n) => <span key={n} className="chip">{n}</span>)}
                          {(u.team_names || []).length === 0 && <span className="text-[11.5px] text-slate-400">—</span>}
                        </div>
                      </td>
                      <td className="whitespace-nowrap">
                        <span className="text-[12px] text-slate-600">{formatDate(u.created_at)}</span>
                        {u.last_seen_at && <p className="text-[10.5px] text-slate-400">vu {timeAgo(u.last_seen_at)}</p>}
                      </td>
                      <td>
                        <div className="flex items-center justify-end gap-1">
                          <button onClick={() => setDetail(u)} title="Voir"
                            className="btn btn-ghost btn-icon rounded-lg"><Eye size={15} /></button>
                          <button onClick={() => setEditing(u)} title="Modifier"
                            className="btn btn-ghost btn-icon rounded-lg"><Edit3 size={15} /></button>
                          <button onClick={() => resetPwd(u)} title="Réinitialiser le mot de passe"
                            className="btn btn-ghost btn-icon rounded-lg"><KeyRound size={15} /></button>
                          {!isSelf && (
                            <button onClick={() => toggleActive(u)}
                              title={u.is_active ? 'Suspendre' : 'Activer'}
                              className={cx('btn btn-ghost btn-icon rounded-lg',
                                u.is_active ? 'text-amber-600 hover:bg-amber-50' : 'text-emerald-600 hover:bg-emerald-50')}>
                              {u.is_active ? <ShieldOff size={15} /> : <ShieldCheck size={15} />}
                            </button>
                          )}
                          {!isSelf && (
                            <button onClick={() => setConfirm({ user: u })} title="Supprimer"
                              className="btn btn-ghost btn-icon rounded-lg text-rose-500 hover:bg-rose-50">
                              <Trash2 size={15} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <Pagination count={count} page={page} pageSize={pageSize} onPage={setPage} />
        </Card>
      )}

      {creating && <UserModal onClose={() => setCreating(false)} onSaved={() => { setCreating(false); refetch() }} />}
      {editing && <UserModal user={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); refetch() }} />}
      {detail && <UserDetail user={detail} onClose={() => setDetail(null)} onEdit={() => { setEditing(detail); setDetail(null) }} />}

      <ConfirmDialog
        open={!!confirm}
        onClose={() => setConfirm(null)}
        title={confirm?.bulk ? `Supprimer ${selected.length} compte(s) ?` : `Supprimer ${confirm?.user?.full_name} ?`}
        message={confirm?.bulk
          ? 'Les comptes sélectionnés et leurs données associées seront définitivement supprimés.'
          : 'Ce compte et ses données associées seront définitivement supprimés. Cette action est irréversible.'}
        confirmLabel="Supprimer définitivement"
        loading={busy}
        onConfirm={async () => {
          if (confirm?.bulk) await bulk('delete')
          else {
            try {
              await api.delete(`/users/${confirm.user.id}/`)
              setNotice({ tone: 'success', text: `${confirm.user.full_name} a été supprimé.` })
              await refetch()
            } catch (e) { setNotice({ tone: 'error', text: errorMessage(e) }) }
          }
          setConfirm(null)
        }}
      />
    </div>
  )
}

/* ------------------------------- Formulaire ------------------------------- */
function UserModal({ user, onClose, onSaved }) {
  const [form, setForm] = useState({
    email: user?.email || '', first_name: user?.first_name || '', last_name: user?.last_name || '',
    role: user?.role || 'PM', status: user?.status || 'ACTIVE', phone: user?.phone || '',
    job_title: user?.job_title || '', company: user?.company || '',
    is_active: user?.is_active ?? true, is_staff: user?.is_staff ?? false,
    weekly_capacity_hours: user?.weekly_capacity_hours ?? 35,
    hourly_cost: user?.hourly_cost ?? 50,
    password: '',
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  const save = async () => {
    setSaving(true); setErrors({})
    try {
      const payload = { ...form }
      if (!payload.password) delete payload.password
      if (user) await api.patch(`/users/${user.id}/`, payload)
      else await api.post('/users/', payload)
      onSaved()
    } catch (e) { setErrors(fieldErrors(e)) }
    finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title={user ? 'Modifier le compte' : 'Créer un compte'}
      subtitle={user?.email || 'Nouvel utilisateur Cadria'} size="lg" icon={user ? Edit3 : UserPlus}
      footer={<><Button variant="secondary" onClick={onClose}>Annuler</Button>
        <Button loading={saving} onClick={save}>{user ? 'Enregistrer' : 'Créer le compte'}</Button></>}>
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Prénom" required value={form.first_name} error={errors.first_name} onChange={set('first_name')} />
          <Input label="Nom" required value={form.last_name} error={errors.last_name} onChange={set('last_name')} />
        </div>
        <Input label="Adresse e-mail" type="email" required icon={Mail}
          value={form.email} error={errors.email} onChange={set('email')} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Poste" value={form.job_title} onChange={set('job_title')} />
          <Input label="Organisation" value={form.company} onChange={set('company')} />
          <Input label="Téléphone" value={form.phone} onChange={set('phone')} />
          <Input label={user ? 'Nouveau mot de passe (facultatif)' : 'Mot de passe'}
            type="password" autoComplete="new-password"
            value={form.password} error={errors.password} onChange={set('password')}
            hint={user ? 'Laisser vide pour conserver le mot de passe actuel.' : 'Laisser vide pour générer « Cadria@2026 ».'} />
        </div>

        <div>
          <label className="label">Rôle</label>
          <div className="grid gap-2 sm:grid-cols-2">
            {ROLE_OPTIONS.map((r) => (
              <button key={r.value} type="button" onClick={() => setForm({ ...form, role: r.value })}
                className={cx('rounded-lg border px-3 py-2.5 text-left transition',
                  form.role === r.value ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-500/20'
                    : 'border-slate-200 hover:border-slate-300')}>
                <span className="flex items-center gap-1.5 text-[12.5px] font-semibold text-slate-800">
                  {form.role === r.value && <Check size={13} className="text-brand-600" />} {r.label}
                </span>
                <span className="mt-0.5 block text-[11px] leading-snug text-slate-500">{r.desc}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Statut" value={form.status} onChange={set('status')} options={STATUS_OPTIONS} />
          <Input label="Capacité hebdomadaire (h)" type="number" min="0"
            value={form.weekly_capacity_hours} onChange={set('weekly_capacity_hours')} />
        </div>

        <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 px-4">
          <label className="flex cursor-pointer items-center justify-between gap-4 py-2.5">
            <span>
              <span className="block text-[13px] font-medium text-slate-800">Compte actif</span>
              <span className="mt-0.5 block text-[11.5px] text-slate-500">Un compte inactif ne peut pas se connecter.</span>
            </span>
            <input type="checkbox" checked={form.is_active} onChange={set('is_active')}
              className="h-4 w-8 rounded-full border-slate-300 text-brand-600 focus:ring-brand-500" />
          </label>
          <label className="flex cursor-pointer items-center justify-between gap-4 py-2.5">
            <span>
              <span className="block text-[13px] font-medium text-slate-800">Accès Django Admin</span>
              <span className="mt-0.5 block text-[11.5px] text-slate-500">Accès à l’interface d’administration technique.</span>
            </span>
            <input type="checkbox" checked={form.is_staff} onChange={set('is_staff')}
              className="h-4 w-8 rounded-full border-slate-300 text-brand-600 focus:ring-brand-500" />
          </label>
        </div>
      </div>
    </Modal>
  )
}

/* ------------------------------- Détail ------------------------------- */
function UserDetail({ user, onClose, onEdit }) {
  const r = ROLE_LABEL[user.role] || ROLE_LABEL.MEMBER
  const s = USER_STATUS[user.status] || {}
  const util = Number(user.utilisation) || 0

  return (
    <Modal open onClose={onClose} title={user.full_name} subtitle={user.email} size="lg" icon={Users}
      footer={<><Button variant="secondary" onClick={onClose}>Fermer</Button>
        <Button icon={Edit3} onClick={onEdit}>Modifier</Button></>}>
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <Avatar name={user.full_name} color={user.avatar_color} size={64} />
          <div>
            <div className="flex flex-wrap gap-1.5">
              <Badge className={r.cls}>{r.label}</Badge>
              <Badge className={s.cls} dot={user.is_active ? 'bg-emerald-500' : 'bg-rose-500'}>{s.label}</Badge>
              {user.is_staff && <Badge className="badge-purple">Django Admin</Badge>}
            </div>
            <p className="mt-2 text-[12.5px] text-slate-600">
              {user.job_title || '—'}{user.company ? ` · ${user.company}` : ''}
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-4">
          <Metric label="Tâches ouvertes" value={num(user.active_tasks)} />
          <Metric label="Charge" value={hours(user.workload_hours)} />
          <Metric label="Capacité" value={hours(user.weekly_capacity_hours)} />
          <Metric label="Utilisation" value={pct(util, 0)}
            tone={util > 110 ? 'text-rose-600' : util > 85 ? 'text-amber-600' : 'text-emerald-600'} />
        </div>

        <div className="grid gap-2 rounded-xl bg-slate-50 p-4 text-[12.5px] sm:grid-cols-2">
          <Info label="E-mail" value={user.email} />
          <Info label="Téléphone" value={user.phone || '—'} />
          <Info label="Organisation" value={user.company || '—'} />
          <Info label="Coût horaire" value={user.hourly_cost ? `${Number(user.hourly_cost).toLocaleString('fr-FR')} €` : '—'} />
          <Info label="Inscription" value={formatDate(user.created_at)} />
          <Info label="Dernière activité" value={user.last_seen_at ? timeAgo(user.last_seen_at) : 'Jamais'} />
        </div>

        {(user.team_names || []).length > 0 && (
          <div>
            <p className="label">Équipes</p>
            <div className="flex flex-wrap gap-1.5">
              {user.team_names.map((n) => <span key={n} className="chip bg-brand-50 text-brand-700">{n}</span>)}
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}

function Metric({ label, value, tone = 'text-slate-900' }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2.5">
      <p className="text-[10.5px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className={cx('mt-0.5 text-[16px] font-bold', tone)}>{value}</p>
    </div>
  )
}

function Info({ label, value }) {
  return (
    <div>
      <p className="text-[10.5px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 truncate font-medium text-slate-800">{value}</p>
    </div>
  )
}

function pct(v, d = 0) {
  return `${Number(v || 0).toFixed(d)} %`
}
