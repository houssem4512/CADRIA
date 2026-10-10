import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bell, BellOff, Check, CheckCheck, Megaphone, RefreshCw, Send, Sparkles, Star, Trash2, X,
} from 'lucide-react'
import api, { errorMessage } from '../../lib/api'
import { useQuery } from '../../lib/useApi'
import {
  Alert, Badge, Button, Card, CardHeader, EmptyState, Input, Modal, SearchInput, Select,
  Skeleton, Textarea,
} from '../../components/ui'
import { NOTIF_CATEGORY, NOTIF_LEVEL, cx, formatDate, formatDateTime, timeAgo } from '../../lib/format'

const LEVELS = [
  { value: 'INFO', label: 'Information', cls: 'badge-sky', dot: 'bg-sky-500' },
  { value: 'SUCCESS', label: 'Succès', cls: 'badge-success', dot: 'bg-emerald-500' },
  { value: 'WARNING', label: 'Avertissement', cls: 'badge-warning', dot: 'bg-amber-500' },
  { value: 'ERROR', label: 'Erreur / incident', cls: 'badge-danger', dot: 'bg-rose-500' },
  { value: 'AGENT', label: 'Agent', cls: 'badge-purple', dot: 'bg-violet-500' },
]

const TARGETS = [
  { value: 'ALL', label: 'Tous les utilisateurs', desc: 'Diffusion générale à l’ensemble de la plateforme' },
  { value: 'ADMIN', label: 'Administrateurs', desc: 'Communications internes à l’équipe d’administration' },
  { value: 'PM', label: 'Chefs de projet', desc: 'Chefs de projet et responsables de portefeuille' },
  { value: 'MEMBER', label: 'Membres d’équipe', desc: 'Contributeurs opérationnels' },
  { value: 'VIEWER', label: 'Observateurs', desc: 'Comptes en lecture seule' },
]

const TEMPLATES = [
  { label: 'Maintenance planifiée', level: 'WARNING', category: 'SYSTEM',
    title: 'Maintenance planifiée de la plateforme',
    message: 'Cadria sera indisponible samedi de 02h00 à 04h00 (heure de Paris) pour une mise à jour de l’infrastructure. Aucune donnée ne sera perdue.' },
  { label: 'Nouvelle fonctionnalité', level: 'SUCCESS', category: 'SYSTEM',
    title: 'Nouvelle fonctionnalité disponible',
    message: 'Le centre de notifications est désormais accessible depuis la barre supérieure, avec filtres par catégorie et préférences personnalisables.' },
  { label: 'Campagne de validation', level: 'INFO', category: 'VALIDATION',
    title: 'Campagne de validation des plans en attente',
    message: 'Plusieurs plans de découpage sont en attente de validation. Merci de les traiter avant la fin de la semaine afin de débloquer les écritures Jira.' },
  { label: 'Alerte de sécurité', level: 'ERROR', category: 'ACCOUNT',
    title: 'Action requise : renforcement des mots de passe',
    message: 'Par mesure de sécurité, nous vous invitons à renouveler votre mot de passe depuis votre profil dans les 7 prochains jours.' },
]

export default function Announcements() {
  const { data, loading, refetch } = useQuery('/notifications/', { params: { page_size: 60 } })
  const { data: summary } = useQuery('/notifications/summary/')
  const { data: usersData } = useQuery('/users/', { params: { page_size: 100 } })
  const [composing, setComposing] = useState(false)
  const [search, setSearch] = useState('')
  const [notice, setNotice] = useState(null)

  const all = data?.results ?? data ?? []
  const broadcasts = all.filter((n) => n.is_broadcast)
  const users = usersData?.results ?? usersData ?? []

  const list = useMemo(() => {
    if (!search) return broadcasts
    const q = search.toLowerCase()
    return broadcasts.filter((n) => `${n.title} ${n.message}`.toLowerCase().includes(q))
  }, [broadcasts, search])

  const stats = useMemo(() => ({
    total: all.length,
    unread: summary?.unread || 0,
    broadcasts: broadcasts.length,
    critical: all.filter((n) => n.level === 'ERROR').length,
  }), [all, broadcasts, summary])

  return (
    <div className="space-y-5 p-5 sm:p-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Administration</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Annonces & diffusion</h1>
          <p className="mt-1 text-[14px] text-slate-500">
            {stats.broadcasts} diffusion{stats.broadcasts > 1 ? 's' : ''} envoyée{stats.broadcasts > 1 ? 's' : ''} ·{' '}
            {users.length} destinataire{users.length > 1 ? 's' : ''} potentiel{users.length > 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" icon={RefreshCw} onClick={refetch}>Actualiser</Button>
          <Button icon={Megaphone} onClick={() => setComposing(true)}>Nouvelle annonce</Button>
        </div>
      </header>

      {notice && (
        <Alert tone={notice.tone} action={<Button variant="ghost" size="sm" icon={X} onClick={() => setNotice(null)} />}>
          {notice.text}
        </Alert>
      )}

      {/* ------------------------------- Synthèse ------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Diffusions envoyées</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-slate-900">{stats.broadcasts}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Notifications totales</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-slate-900">{stats.total}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Non lues (tous comptes)</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-brand-700">{stats.unread}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Niveau erreur</p>
          <p className={cx('mt-2 text-[24px] font-bold leading-none', stats.critical ? 'text-rose-600' : 'text-emerald-600')}>
            {stats.critical}
          </p>
        </Card>
      </div>

      <Alert tone="info" title="Diffusion ciblée">
        Une annonce peut être adressée à tous les utilisateurs, à un rôle précis, ou à une sélection
        nominative de comptes. Les diffusions apparaissent dans le centre de notifications de chaque
        destinataire et ne peuvent pas être supprimées individuellement.
      </Alert>

      {/* ------------------------------- Liste ------------------------------- */}
      <Card className="p-3">
        <SearchInput value={search} onChange={setSearch} placeholder="Rechercher une annonce…" />
      </Card>

      {loading ? (
        <div className="space-y-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}</div>
      ) : list.length === 0 ? (
        <EmptyState icon={Megaphone} title="Aucune annonce diffusée"
          description="Composez votre première annonce pour informer les utilisateurs de la plateforme."
          action={<Button icon={Megaphone} onClick={() => setComposing(true)}>Composer une annonce</Button>} />
      ) : (
        <div className="space-y-3">
          {list.map((n) => {
            const lv = LEVELS.find((l) => l.value === n.level) || LEVELS[0]
            const target = TARGETS.find((t) => t.value === n.target_role) || TARGETS[0]
            return (
              <Card key={n.id} className="overflow-hidden">
                <div className="flex items-start gap-3.5 p-4">
                  <span className={cx('mt-0.5 grid h-10 w-10 shrink-0 place-items-center rounded-lg', lv.cls)}>
                    <Megaphone size={17} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-[14.5px] font-semibold text-slate-900">{n.title}</h3>
                      <Badge className={lv.cls} dot={lv.dot}>{lv.label}</Badge>
                      <Badge className="badge-neutral">{NOTIF_CATEGORY[n.category] || n.category}</Badge>
                    </div>
                    {n.message && <p className="mt-1.5 text-[13px] leading-relaxed text-slate-600">{n.message}</p>}
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-slate-400">
                      <span className="flex items-center gap-1.5"><Send size={11} /> {target.label}</span>
                      <span>{formatDateTime(n.created_at)} · {timeAgo(n.created_at)}</span>
                      {n.link && <Link to={n.link} className="link">Lien associé</Link>}
                    </div>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {composing && (
        <ComposeModal
          users={users}
          onClose={() => setComposing(false)}
          onSent={(msg) => { setComposing(false); setNotice({ tone: 'success', text: msg }); refetch() }}
        />
      )}
    </div>
  )
}

function ComposeModal({ users, onClose, onSent }) {
  const [form, setForm] = useState({
    title: '', message: '', level: 'INFO', category: 'SYSTEM',
    link: '', target_role: 'ALL', targets: [],
  })
  const [errors, setErrors] = useState({})
  const [sending, setSending] = useState(false)

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const applyTemplate = (t) => setForm((f) => ({
    ...f, title: t.title, message: t.message, level: t.level, category: t.category,
  }))

  const send = async () => {
    setErrors({}); setSending(true)
    try {
      const payload = { ...form }
      if (!payload.targets.length) delete payload.targets
      const { data } = await api.post('/notifications/broadcast/', payload)
      onSent(`Annonce diffusée à ${data.target_role === 'ALL' ? 'tous les rôles' : data.target_role.toLowerCase()}.`)
    } catch (e) {
      const d = e?.response?.data || {}
      setErrors(Object.fromEntries(Object.entries(d).map(([k, v]) => [k, Array.isArray(v) ? v[0] : v])) || { global: errorMessage(e) })
    } finally { setSending(false) }
  }

  const targetLabel = TARGETS.find((t) => t.value === form.target_role)?.label

  return (
    <Modal open onClose={onClose} title="Composer une annonce" size="lg" icon={Megaphone}
      subtitle="Diffusion vers tous les utilisateurs ou un rôle ciblé"
      footer={<><Button variant="secondary" onClick={onClose}>Annuler</Button>
        <Button icon={Send} loading={sending} onClick={send} disabled={!form.title.trim()}>Diffuser l’annonce</Button></>}>
      <div className="space-y-4">
        <div>
          <p className="label">Modèles</p>
          <div className="flex flex-wrap gap-1.5">
            {TEMPLATES.map((t) => (
              <button key={t.label} onClick={() => applyTemplate(t)}
                className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-[12px] font-medium text-slate-600 transition hover:border-brand-300 hover:bg-brand-50/40">
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <Input label="Titre" required value={form.title} error={errors.title} onChange={set('title')}
          placeholder="Maintenance planifiée de la plateforme" />
        <Textarea label="Message" value={form.message} error={errors.message} onChange={set('message')}
          rows={5} placeholder="Décrivez l’annonce en quelques phrases claires et actionnables." />

        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Niveau" value={form.level} onChange={set('level')}
            options={LEVELS.map((l) => ({ value: l.value, label: l.label }))} />
          <Select label="Catégorie" value={form.category} onChange={set('category')}
            options={Object.entries(NOTIF_CATEGORY).map(([k, v]) => ({ value: k, label: v }))} />
        </div>

        <div>
          <label className="label">Audience</label>
          <div className="grid gap-2 sm:grid-cols-2">
            {TARGETS.map((t) => (
              <button key={t.value} type="button" onClick={() => setForm({ ...form, target_role: t.value, targets: [] })}
                className={cx('rounded-lg border px-3 py-2.5 text-left transition',
                  form.target_role === t.value && !form.targets.length
                    ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-500/20'
                    : 'border-slate-200 hover:border-slate-300')}>
                <span className="flex items-center gap-1.5 text-[12.5px] font-semibold text-slate-800">
                  {form.target_role === t.value && !form.targets.length && <Check size={13} className="text-brand-600" />}
                  {t.label}
                </span>
                <span className="mt-0.5 block text-[11px] leading-snug text-slate-500">{t.desc}</span>
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="label">
            Ou sélection nominative ({form.targets.length} compte{form.targets.length > 1 ? 's' : ''})
          </label>
          <div className="max-h-[200px] space-y-1.5 overflow-y-auto rounded-lg border border-slate-200 p-2">
            {users.map((u) => {
              const on = form.targets.includes(u.id)
              return (
                <button key={u.id}
                  onClick={() => setForm({
                    ...form,
                    targets: on ? form.targets.filter((x) => x !== u.id) : [...form.targets, u.id],
                  })}
                  className={cx('flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left transition',
                    on ? 'bg-brand-50' : 'hover:bg-slate-50')}>
                  <span className={cx('grid h-4 w-4 shrink-0 place-items-center rounded border',
                    on ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-300')}>
                    {on && <Check size={11} />}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-[12.5px] text-slate-700">{u.full_name}</span>
                  <span className="shrink-0 text-[11px] text-slate-400">{u.email}</span>
                </button>
              )
            })}
          </div>
          <p className="hint">Si des comptes sont sélectionnés, la sélection nominative prime sur le rôle.</p>
        </div>

        <Input label="Lien associé (facultatif)" value={form.link} onChange={set('link')}
          placeholder="/app/projects/1" hint="Route interne vers laquelle mène l’annonce." />

        <Alert tone="info">
          Aperçu : <b>{form.title || 'Titre de l’annonce'}</b> —{' '}
          {form.targets.length ? `${form.targets.length} compte(s) sélectionné(s)` : targetLabel}.
        </Alert>
      </div>
    </Modal>
  )
}
