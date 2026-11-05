import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, AlertTriangle, Bot, Check, ChevronDown, Clock, Code2, Database, Gauge, GitBranch,
  Plug, RefreshCw, Server, ShieldAlert, Network, Sparkles, Workflow, X, Zap,
} from 'lucide-react'
import api, { errorMessage } from '../../lib/api'
import { useQuery } from '../../lib/useApi'
import {
  Alert, Badge, Button, Card, CardHeader, Dot, EmptyState, Ring, Select, Skeleton,
} from '../../components/ui'
import { BarChartView, LineChartView, TrendChart } from '../../components/charts'
import { RUN_STATUS, cx, formatDateTime, num, pct, timeAgo } from '../../lib/format'

const ICONS = { sitemap: Network, plug: Plug, 'shield-alert': ShieldAlert, sparkles: Sparkles, workflow: Workflow }

export default function AdminAgents() {
  const { data: agentsData, loading, refetch } = useQuery('/agents/', { params: { page_size: 20 } })
  const { data: monitor, refetch: rMonitor } = useQuery('/agents/monitor/')
  const { data: runsData, refetch: rRuns } = useQuery('/agent-runs/', { params: { page_size: 30 } })
  const { data: proposalsData } = useQuery('/proposals/', { params: { page_size: 30 } })

  const agents = agentsData?.results ?? agentsData ?? []
  const runs = runsData?.results ?? runsData ?? []
  const proposals = proposalsData?.results ?? proposalsData ?? []
  const totals = monitor?.totals || {}

  const [expanded, setExpanded] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [msg, setMsg] = useState(null)

  const refreshAll = async () => { await refetch(); await rMonitor(); await rRuns() }

  const filteredRuns = statusFilter ? runs.filter((r) => r.status === statusFilter) : runs

  const timeline = (monitor?.timeline || []).map((t) => ({
    label: new Date(t.date).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }),
    total: t.total, skipped: t.skipped, failed: t.failed,
  }))

  const perAgent = (monitor?.per_agent || []).map((a) => ({
    key: a.agent__key, name: a.agent__short_name || a.agent__key,
    total: a.total, skipped: a.skipped, succeeded: a.succeeded, failed: a.failed,
    awaiting: a.awaiting, latency: a.avg_latency || 0, rate: a.success_rate || 0,
  }))

  return (
    <div className="space-y-5 p-5 sm:p-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Administration</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Supervision des agents</h1>
          <p className="mt-1 text-[14px] text-slate-500">
            Observabilité du système multi-agents : latence, taux d’erreur, succès des appels et équilibrage de charge.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge className="badge-purple"><Dot className="bg-violet-500" pulse /> Runtime {monitor?.enabled ? 'branché' : 'non branché'}</Badge>
          <Button variant="secondary" icon={RefreshCw} onClick={refreshAll}>Actualiser</Button>
        </div>
      </header>

      {msg && (
        <Alert tone={msg.tone} action={<Button variant="ghost" size="sm" icon={X} onClick={() => setMsg(null)} />}>
          {msg.text}
        </Alert>
      )}

      {/* ------------------------------- KPI ------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Exécutions (30 j)</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-slate-900">{num(totals.runs)}</p>
          <p className="mt-1 text-[11.5px] text-slate-400">{num(totals.skipped)} réservées</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Réussites</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-emerald-600">{num(totals.success)}</p>
          <p className="mt-1 text-[11.5px] text-slate-400">{num(totals.failed)} échec(s)</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Latence moyenne</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-slate-900">{num(totals.avg_latency_ms)} ms</p>
          <p className="mt-1 text-[11.5px] text-slate-400">cible &lt; 3 000 ms</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Taux d’erreur JSON</p>
          <p className={cx('mt-2 text-[24px] font-bold leading-none',
            (monitor?.json_error_rate || 0) > 2 ? 'text-rose-600' : 'text-emerald-600')}>
            {pct(monitor?.json_error_rate || 0, 1)}
          </p>
          <p className="mt-1 text-[11.5px] text-slate-400">hors-format de génération</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">À valider</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-amber-600">
            {num(proposals.filter((p) => p.status === 'PENDING').length)}
          </p>
          <p className="mt-1 text-[11.5px] text-slate-400">plans en attente</p>
        </Card>
      </div>

      {/* ------------------------------- Graphes ------------------------------- */}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Exécutions quotidiennes" icon={Activity}
            subtitle="Volume et statuts sur la fenêtre choisie"
            action={<Badge className="badge-brand">{monitor?.window_days || 30} jours</Badge>} />
          <div className="card-body pt-2">
            {timeline.length
              ? <BarChartView data={timeline} xKey="label" height={250} stacked
                  series={[{ key: 'skipped', label: 'Réservées', color: '#8B5CF6' },
                          { key: 'failed', label: 'Échecs', color: '#E11D48' }]} />
              : <EmptyState icon={Activity} title="Aucune exécution sur la période" />}
          </div>
        </Card>

        <Card>
          <CardHeader title="Santé par agent" icon={Gauge} subtitle="Taux de succès et latence" />
          <div className="card-body pt-2">
            {perAgent.map((a) => (
              <div key={a.key} className="flex items-center gap-3 border-b border-slate-100 py-3 last:border-0">
                <Ring value={a.rate} size={48} stroke={5}
                  color={a.rate >= 90 ? '#10B981' : a.rate > 0 ? '#F59E0B' : '#94A3B8'}>
                  <span className="text-[10px] font-bold">{Math.round(a.rate)}%</span>
                </Ring>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-semibold text-slate-800">{a.name}</p>
                  <p className="text-[11px] text-slate-500">
                    {a.total} exécution(s) · {a.skipped} réservée(s)
                  </p>
                </div>
                <span className="shrink-0 text-[11.5px] font-semibold text-slate-600">{num(a.latency)} ms</span>
              </div>
            ))}
            {!perAgent.length && <EmptyState icon={Gauge} title="Aucune donnée" />}
          </div>
        </Card>
      </div>

      {/* ------------------------------- Cartes agents ------------------------------- */}
      <div className="grid gap-4 xl:grid-cols-3">
        {loading ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-72 rounded-xl" />)
          : agents.map((a) => {
            const Icon = ICONS[a.icon] || Bot
            const isOpen = expanded === a.key
            const stats = perAgent.find((x) => x.key === a.key) || {}
            return (
              <Card key={a.id} className="flex flex-col">
                <div className="flex items-start gap-3.5 p-5">
                  <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl text-white shadow-sm"
                    style={{ background: `linear-gradient(135deg, ${a.color}, ${a.color}CC)` }}>
                    <Icon size={22} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-slate-400">{a.key}</span>
                    <h3 className="mt-0.5 text-[15px] font-semibold leading-snug text-slate-900">{a.name}</h3>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge className="badge-purple">Emplacement réservé</Badge>
                      {a.requires_human_validation && <Badge className="badge-warning">Validation humaine</Badge>}
                    </div>
                  </div>
                </div>

                <div className="px-5">
                  <p className="line-clamp-3 text-[12.5px] leading-relaxed text-slate-600">{a.description}</p>
                  <div className="mt-3 grid grid-cols-3 gap-2 rounded-lg bg-slate-50 p-3 text-center">
                    <Stat label="Exécutions" value={stats.total ?? a.total_runs} />
                    <Stat label="Réservées" value={stats.skipped ?? 0} tone="text-violet-600" />
                    <Stat label="Échecs" value={stats.failed ?? a.failed_runs}
                      tone={stats.failed ? 'text-rose-600' : 'text-slate-900'} />
                  </div>
                  <div className="mt-2 rounded-lg border border-slate-200 p-2.5">
                    <p className="text-[10.5px] text-slate-500">Endpoint du runtime</p>
                    <p className="mt-0.5 truncate font-mono text-[11px] text-slate-700">
                      {a.runtime_endpoint || '— non configuré —'}
                    </p>
                  </div>
                  <button onClick={() => setExpanded(isOpen ? null : a.key)}
                    className="mt-3 flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-[12.5px] font-medium text-slate-700 transition hover:border-brand-300 hover:bg-brand-50/40">
                    <span className="flex items-center gap-1.5"><Code2 size={14} /> Contrat & configuration</span>
                    <ChevronDown size={14} className={cx('transition', isOpen && 'rotate-180')} />
                  </button>
                  {isOpen && (
                    <div className="mt-2 space-y-3 animate-fade-in">
                      <Info label="Modèle suggéré" value={a.suggested_model} />
                      <Info label="Stack suggérée" value={a.suggested_stack} />
                      <Schema title="Entrée" schema={a.input_schema_hint} />
                      <Schema title="Sortie" schema={a.output_schema_hint} />
                    </div>
                  )}
                </div>

                <div className="mt-auto flex items-center justify-between border-t border-slate-100 bg-slate-50/60 px-5 py-3">
                  <span className="text-[11px] text-slate-500">
                    {a.last_run_at ? `Dernier lancement ${timeAgo(a.last_run_at)}` : 'Jamais lancé'}
                  </span>
                  <span className="text-[11px] font-semibold text-slate-600">
                    {pct(a.success_rate || 0, 1)} succès
                  </span>
                </div>
              </Card>
            )
          })}
      </div>

      {/* ------------------------------- Journal des exécutions ------------------------------- */}
      <Card>
        <CardHeader title="Journal des exécutions" icon={GitBranch}
          subtitle="Traçabilité complète des lancements d’agents"
          action={
            <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-[180px] [&_.field]:h-8"
              options={[{ value: '', label: 'Tous les statuts' },
                ...Object.entries(RUN_STATUS).map(([k, v]) => ({ value: k, label: v.label }))]} />
          } />
        {filteredRuns.length === 0 ? (
          <div className="p-6"><EmptyState icon={GitBranch} title="Aucune exécution" /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>#</th><th>Agent</th><th>Projet</th><th>Statut</th><th>Déclencheur</th>
                  <th>Étape</th><th>Heure</th>
                </tr>
              </thead>
              <tbody>
                {filteredRuns.map((r) => {
                  const st = RUN_STATUS[r.status] || RUN_STATUS.QUEUED
                  return (
                    <tr key={r.id}>
                      <td className="font-mono text-[11px] text-slate-400">{r.id}</td>
                      <td>
                        <span className="flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full" style={{ background: r.agent_color }} />
                          <span className="text-[12.5px] font-semibold text-slate-800">{r.agent_key}</span>
                        </span>
                      </td>
                      <td>
                        <Link to={`/app/projects/${r.project}`} className="text-[12px] text-brand-700 hover:underline">
                          {r.project_reference}
                        </Link>
                        <p className="max-w-[150px] truncate text-[10.5px] text-slate-400">{r.project_name}</p>
                      </td>
                      <td><Badge className={st.cls} dot={st.dot}>{st.label}</Badge></td>
                      <td className="text-[12px] text-slate-600">
                        {r.triggered_by_name || 'Système'}
                        <span className="ml-1 text-[10.5px] text-slate-400">
                          {{ MANUAL: 'manuel', PIPELINE: 'pipeline', SCHEDULED: 'planifié', RETRY: 'retry' }[r.trigger]}
                        </span>
                      </td>
                      <td className="max-w-[190px] truncate text-[12px] text-slate-600">{r.step || '—'}</td>
                      <td className="whitespace-nowrap text-[11.5px] text-slate-500">{formatDateTime(r.created_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ------------------------------- Infra ------------------------------- */}
      <div className="grid gap-4 lg:grid-cols-3">
        <InfraCard icon={Server} title="Pipeline Airflow" tone="brand"
          items={['Ré-entraînement mensuel du modèle de génération (Agent 1)',
                 'Collecte hebdomadaire Jira/Trello pour le modèle de risque (Agent 3)',
                 'Déclenchement du CT sur écart temps estimé / temps réel']} />
        <InfraCard icon={Zap} title="Dashboard Grafana" tone="sky"
          items={['Latence et taux d’erreur de format JSON (Agent 1)',
                 'Taux de succès des appels API et équilibrage de charge (Agent 2)',
                 'Scores de risque par projet/sprint avec alertes (Agent 3)']} />
        <InfraCard icon={Database} title="Évaluation continue" tone="violet"
          items={['EvidentlyAI complété par des métriques custom',
                 'Taux de réassignation manuelle comme proxy de qualité',
                 'Risque prédit vs. retard effectif constaté']} />
      </div>
    </div>
  )
}

function Stat({ label, value, tone = 'text-slate-900' }) {
  return (
    <div>
      <p className={cx('text-[15px] font-bold leading-none', tone)}>{value ?? 0}</p>
      <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">{label}</p>
    </div>
  )
}

function Info({ label, value }) {
  return (
    <div>
      <p className="text-[10.5px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-0.5 text-[11.5px] text-slate-600">{value || '—'}</p>
    </div>
  )
}

function Schema({ title, schema }) {
  if (!schema || !Object.keys(schema).length) return null
  return (
    <div>
      <p className="text-[10.5px] font-semibold uppercase tracking-wide text-slate-500">Schéma de {title.toLowerCase()}</p>
      <pre className="mt-1 max-h-[180px] overflow-auto rounded-lg bg-slate-900 p-2.5 font-mono text-[10px] leading-relaxed text-slate-100">
{JSON.stringify(schema, null, 2)}
      </pre>
    </div>
  )
}

function InfraCard({ icon: Icon, title, items, tone }) {
  const tones = {
    brand: 'bg-brand-50 text-brand-600', sky: 'bg-sky-50 text-sky-600', violet: 'bg-violet-50 text-violet-600',
  }
  return (
    <Card>
      <CardHeader title={title} icon={Icon} />
      <div className="card-body pt-2">
        <ul className="space-y-2">
          {items.map((i) => (
            <li key={i} className="flex gap-2 text-[12.5px] leading-relaxed text-slate-600">
              <span className={cx('mt-1 grid h-4 w-4 shrink-0 place-items-center rounded', tones[tone])}>
                <Check size={10} />
              </span>
              {i}
            </li>
          ))}
        </ul>
        <Badge className="badge-purple mt-3">Emplacement réservé</Badge>
      </div>
    </Card>
  )
}
