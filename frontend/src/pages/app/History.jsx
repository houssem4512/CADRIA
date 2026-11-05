import { useMemo, useState } from 'react'
import {
  Activity, Bot, Check, Download, Filter, GitBranch, RefreshCw, Search, ShieldAlert,
  Sparkles, X,
} from 'lucide-react'
import { useQuery } from '../../lib/useApi'
import { useAuth } from '../../context/AuthContext'
import {
  Alert, Avatar, Badge, Button, Card, CardHeader, EmptyState, Pagination, SearchInput,
  Select, Skeleton,
} from '../../components/ui'
import { BarChartView } from '../../components/charts'
import { cx, formatDate, formatDateTime, timeAgo, toCSV } from '../../lib/format'

const ACTIONS = [
  { value: '', label: 'Toutes les actions' },
  { value: 'CREATE', label: 'Création' }, { value: 'UPDATE', label: 'Modification' },
  { value: 'DELETE', label: 'Suppression' }, { value: 'VALIDATE', label: 'Validation' },
  { value: 'REJECT', label: 'Rejet' }, { value: 'AGENT_RUN', label: 'Exécution agent' },
  { value: 'AGENT_WRITE', label: 'Écriture externe' }, { value: 'SYNC', label: 'Synchronisation' },
  { value: 'ALERT', label: 'Alerte' }, { value: 'LOGIN', label: 'Connexion' },
]

const ENTITIES = [
  { value: '', label: 'Toutes les entités' },
  { value: 'Project', label: 'Projet' }, { value: 'Task', label: 'Tâche' },
  { value: 'Proposal', label: 'Proposition' }, { value: 'RiskAlert', label: 'Alerte de risque' },
  { value: 'Team', label: 'Équipe' }, { value: 'User', label: 'Utilisateur' },
  { value: 'Integration', label: 'Connecteur' },
]

const SEVERITY_CLS = {
  INFO: 'badge-neutral', NOTICE: 'badge-sky', WARNING: 'badge-warning', CRITICAL: 'badge-danger',
}

const ACTION_DOT = {
  CREATE: 'bg-emerald-500', UPDATE: 'bg-brand-500', DELETE: 'bg-rose-500',
  VALIDATE: 'bg-emerald-500', REJECT: 'bg-amber-500', AGENT_RUN: 'bg-violet-500',
  AGENT_WRITE: 'bg-violet-600', SYNC: 'bg-sky-500', ALERT: 'bg-amber-500',
  LOGIN: 'bg-slate-400', LOGOUT: 'bg-slate-300', SIGNUP: 'bg-emerald-500',
  PERMISSION: 'bg-amber-500', EXPORT: 'bg-slate-400',
}

export default function History() {
  const { user } = useAuth()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [action, setAction] = useState('')
  const [entity, setEntity] = useState('')
  const [agent, setAgent] = useState('')
  const [days, setDays] = useState('30')
  const [showFilters, setShowFilters] = useState(false)
  const [selected, setSelected] = useState(null)

  const { data, loading, refetch } = useQuery('/audit/', {
    params: {
      page, page_size: 25,
      ...(search ? { search } : {}),
      ...(action ? { action } : {}),
      ...(entity ? { entity_type: entity } : {}),
      ...(agent ? { agent } : {}),
      ...(days ? { days } : {}),
    },
  })
  const { data: summary } = useQuery('/audit/summary/')

  const logs = data?.results ?? data ?? []
  const count = data?.count ?? 0
  const agentLogs = useMemo(() => logs.filter((l) => l.agent_key), [logs])

  const chartData = (summary?.by_action || []).filter((a) => a.count > 0).map((a) => ({
    label: a.label, count: a.count,
  }))

  return (
    <div className="space-y-5 p-5 sm:p-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Traçabilité</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Historique & journal d’audit</h1>
          <p className="mt-1 text-[14px] text-slate-500">
            {count.toLocaleString('fr-FR')} entrée{count > 1 ? 's' : ''} journalisée{count > 1 ? 's' : ''} ·{' '}
            {num(summary?.last_30_days)} sur les 30 derniers jours
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" icon={Download} onClick={() => toCSV(logs.map((l) => ({
            date: l.created_at, acteur: l.actor_display, action: l.action_label,
            entite: l.entity_type, libelle: l.entity_label, description: l.description,
            agent: l.agent_key || '', correlation: l.correlation_id || '', severite: l.severity,
          })), 'cadria-audit.csv')}>Exporter</Button>
          <Button variant="secondary" icon={RefreshCw} onClick={refetch}>Actualiser</Button>
        </div>
      </header>

      {/* ------------------------------- Synthèse ------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-4">
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Entrées totales</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-slate-900">{num(summary?.total)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">30 derniers jours</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-brand-700">{num(summary?.last_30_days)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Actions d’agents</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-violet-600">
            {num((summary?.by_agent || []).reduce((s, a) => s + a.count, 0))}
          </p>
          {(summary?.by_agent || []).length > 0 && (
            <p className="mt-1 truncate text-[11px] text-slate-400">
              {(summary.by_agent || []).map((a) => `${a.key} (${a.count})`).join(' · ')}
            </p>
          )}
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Avertissements & critiques</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-amber-600">
            {num((summary?.by_severity || []).filter((s) => s.key === 'WARNING' || s.key === 'CRITICAL')
              .reduce((s, x) => s + x.count, 0))}
          </p>
        </Card>
      </div>

      {chartData.length > 0 && (
        <Card>
          <CardHeader title="Répartition par type d’action" icon={Activity}
            subtitle="Volume journalisé par catégorie d’opération" />
          <div className="card-body pt-2">
            <BarChartView data={chartData} xKey="label" layout="vertical" height={Math.max(200, chartData.length * 30)}
              series={[{ key: 'count', label: 'Entrées', color: '#2563EB' }]} />
          </div>
        </Card>
      )}

      {/* ------------------------------- Filtres ------------------------------- */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1) }}
            placeholder="Rechercher une description, une entité, un identifiant…" className="min-w-[240px] flex-1" />
          <Button variant="secondary" icon={Filter} onClick={() => setShowFilters((s) => !s)}
            className={cx(showFilters && 'border-brand-400 bg-brand-50 text-brand-700')}>
            Filtres{(action || entity || agent || days !== '30') && <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />}
          </Button>
        </div>
        {showFilters && (
          <div className="mt-3 grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-4">
            <Select label="Action" value={action} onChange={(e) => { setAction(e.target.value); setPage(1) }} options={ACTIONS} />
            <Select label="Entité" value={entity} onChange={(e) => { setEntity(e.target.value); setPage(1) }} options={ENTITIES} />
            <Select label="Agent" value={agent} onChange={(e) => { setAgent(e.target.value); setPage(1) }}
              options={[{ value: '', label: 'Tous' }, { value: 'SCOPING', label: 'Agent 1 — Scoping' },
                        { value: 'OPS', label: 'Agent 2 — Ops' }, { value: 'RISK', label: 'Agent 3 — Risk' }]} />
            <Select label="Période" value={days} onChange={(e) => { setDays(e.target.value); setPage(1) }}
              options={[{ value: '7', label: '7 derniers jours' }, { value: '30', label: '30 derniers jours' },
                        { value: '90', label: '90 derniers jours' }]} />
          </div>
        )}
      </Card>

      {/* ------------------------------- Journal ------------------------------- */}
      {loading ? (
        <Card><div className="p-4 space-y-3">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div></Card>
      ) : logs.length === 0 ? (
        <EmptyState icon={GitBranch} title="Aucune entrée"
          description="Aucune action ne correspond aux filtres appliqués." />
      ) : (
        <Card>
          <CardHeader title="Journal d’audit" icon={GitBranch}
            subtitle="Chaque action est corrélée : acteur, entité, agent, identifiant de corrélation"
            action={<Badge className="badge-neutral">{logs.filter((l) => l.agent_key).length} action(s) agent</Badge>} />
          <ol className="relative space-y-0 border-t border-slate-100">
            {logs.map((l, i) => (
              <li key={l.id}>
                <button onClick={() => setSelected(selected === l.id ? null : l.id)}
                  className="flex w-full items-start gap-3.5 border-b border-slate-100 px-5 py-3.5 text-left transition hover:bg-slate-50">
                  <span className={cx('mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full', ACTION_DOT[l.action] || 'bg-slate-400')} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[13px] font-semibold text-slate-800">
                        {l.description || l.action_label}
                      </span>
                      <Badge className="badge-neutral">{l.action_label}</Badge>
                      {l.entity_type && <span className="chip">{l.entity_type}</span>}
                      {l.agent_key && (
                        <Badge className="badge-purple"><Sparkles size={10} /> {l.agent_key}</Badge>
                      )}
                      {l.severity !== 'INFO' && <Badge className={SEVERITY_CLS[l.severity]}>{l.severity}</Badge>}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-slate-500">
                      <span className="flex items-center gap-1.5">
                        <Avatar name={l.actor_display} color={l.actor_color} size={16} />
                        {l.actor_display}
                      </span>
                      <span>{formatDateTime(l.created_at)}</span>
                      {l.entity_label && <span className="truncate max-w-[200px]">· {l.entity_label}</span>}
                      {l.correlation_id && <span className="font-mono text-[10.5px] text-slate-400">#{l.correlation_id}</span>}
                    </div>

                    {selected === l.id && (
                      <div className="mt-3 animate-fade-in space-y-2.5 rounded-lg bg-slate-50 p-3.5">
                        <div className="grid gap-2 sm:grid-cols-2">
                          <Detail label="Entité" value={`${l.entity_type || '—'}${l.entity_id ? ` #${l.entity_id}` : ''}`} />
                          <Detail label="Sévérité" value={l.severity} />
                          <Detail label="Agent" value={l.agent_key || '— (action humaine)'} />
                          <Detail label="Exécution liée" value={l.run ? `#${l.run}` : '—'} />
                          <Detail label="Adresse IP" value={l.ip_address || '—'} />
                          <Detail label="Corrélation" value={l.correlation_id || '—'} />
                        </div>
                        {l.description && (
                          <div>
                            <p className="text-[10.5px] uppercase tracking-wide text-slate-400">Description</p>
                            <p className="mt-0.5 text-[12px] text-slate-700">{l.description}</p>
                          </div>
                        )}
                        {Object.keys(l.metadata || {}).length > 0 && (
                          <div>
                            <p className="text-[10.5px] uppercase tracking-wide text-slate-400">Métadonnées</p>
                            <pre className="mt-1 max-h-[160px] overflow-auto rounded bg-slate-900 p-2.5 font-mono text-[10.5px] text-slate-100">
{JSON.stringify(l.metadata, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </button>
              </li>
            ))}
          </ol>
          <Pagination count={count} page={page} pageSize={25} onPage={setPage} />
        </Card>
      )}

      <Alert tone="info" title="Portée de visibilité">
        En tant que {user?.role === 'ADMIN' ? 'administrateur, vous consultez l’ensemble du journal de la plateforme'
          : 'utilisateur non administrateur, vous consultez vos propres actions et celles de vos projets'}.
        Le journal complet reste accessible depuis l’espace administration.
      </Alert>
    </div>
  )
}

function Detail({ label, value }) {
  return (
    <div>
      <p className="text-[10.5px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 truncate font-mono text-[11.5px] text-slate-700">{value}</p>
    </div>
  )
}

function num(v) {
  return Number(v || 0).toLocaleString('fr-FR')
}
