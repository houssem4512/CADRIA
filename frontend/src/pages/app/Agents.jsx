import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, AlertTriangle, Bot, Check, ChevronDown, Clock, Code2, Database, GitBranch,
  PlayCircle, Plug, RefreshCw, Server, ShieldAlert, Network, Sparkles, Workflow, X, Zap,
} from 'lucide-react'
import api, { errorMessage } from '../../lib/api'
import { useQuery } from '../../lib/useApi'
import {
  Alert, Badge, Button, Card, CardHeader, Dot, EmptyState, Ring, Select, Skeleton,
} from '../../components/ui'
import { BarChartView, TrendChart } from '../../components/charts'
import { RUN_STATUS, cx, formatDateTime, num, pct, timeAgo } from '../../lib/format'

const ICONS = { sitemap: Network, plug: Plug, 'shield-alert': ShieldAlert, sparkles: Sparkles, workflow: Workflow }

export default function Agents() {
  const { data: agentsData, loading, refetch } = useQuery('/agents/')
  const { data: monitorData, refetch: refetchMonitor } = useQuery('/agents/monitor/')
  const { data: runsData, refetch: refetchRuns } = useQuery('/agent-runs/', { params: { page_size: 25 } })
  const { data: projectsData } = useQuery('/projects/', { params: { page_size: 50 } })
  const { data: proposalsData } = useQuery('/proposals/', { params: { pending: 'true' } })

  const agents = agentsData?.results ?? agentsData ?? []
  const runs = runsData?.results ?? runsData ?? []
  const projects = projectsData?.results ?? projectsData ?? []
  const pending = proposalsData?.results ?? proposalsData ?? []
  const monitor = monitorData || {}

  const [launching, setLaunching] = useState(null)
  const [result, setResult] = useState(null)
  const [expanded, setExpanded] = useState(null)
  const [picker, setPicker] = useState({ project: '', agent: 'SCOPING' })

  const totals = monitor.totals || {}

  const refreshAll = async () => { await refetch(); await refetchMonitor(); await refetchRuns() }

  const launch = async () => {
    if (!picker.project) return
    setLaunching(picker.agent)
    setResult(null)
    try {
      const { data } = await api.post('/agents/runs/start/', {
        project: Number(picker.project), agent: picker.agent,
        input: { triggered_from: 'agents-page' },
      })
      setResult(data)
      await refreshAll()
    } catch (e) {
      setResult({ detail: errorMessage(e, 'Échec du lancement.') })
    } finally { setLaunching(null) }
  }

  const perAgentChart = (monitor.per_agent || []).map((a) => ({
    name: a.agent__short_name || a.agent__key,
    réservé: a.skipped,
    réussi: a.succeeded,
    échec: a.failed,
  }))

  return (
    <div className="space-y-5 p-5 sm:p-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Copilote</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Agents & orchestration</h1>
          <p className="mt-1 text-[14px] text-slate-500">
            Trois agents spécialisés coordonnés par un orchestrateur — emplacements réservés en attente du runtime.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge className="badge-purple"><Dot className="bg-violet-500" pulse /> Runtime non branché</Badge>
          <Button variant="secondary" icon={RefreshCw} onClick={refreshAll}>Actualiser</Button>
        </div>
      </header>

      <Alert tone="info" title="Emplacement réservé — aucune inférence simulée">
        Le contrat d’entrée/sortie de chaque agent est figé côté plateforme. Chaque lancement crée une
        exécution journalisée au statut « réservé », sans appel de modèle ni écriture externe. Branchez
        le runtime (<code className="rounded bg-white/70 px-1 font-mono text-[11.5px]">AGENT_RUNTIME_ENABLED=True</code> +{' '}
        <code className="rounded bg-white/70 px-1 font-mono text-[11.5px]">dispatch()</code>) pour activer l’inférence.
      </Alert>

      {/* ------------------------------- Supervision ------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Exécutions (30 j)</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-slate-900">{num(totals.runs || 0)}</p>
          <p className="mt-1 text-[11.5px] text-slate-400">{num(totals.skipped || 0)} réservées</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Latence moyenne</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-slate-900">{num(totals.avg_latency_ms || 0)} ms</p>
          <p className="mt-1 text-[11.5px] text-slate-400">aucune inférence exécutée</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Taux d’erreur JSON</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-emerald-600">{pct(monitor.json_error_rate || 0, 1)}</p>
          <p className="mt-1 text-[11.5px] text-slate-400">objectif &lt; 2 %</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">En attente de validation</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-amber-600">{num(pending.length)}</p>
          <p className="mt-1 text-[11.5px] text-slate-400">plans à valider</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Orchestrateur</p>
          <p className="mt-2 text-[18px] font-bold leading-none text-brand-700">{monitor.orchestrator || 'LangGraph'}</p>
          <p className="mt-1 text-[11.5px] text-slate-400">CrewAI / AutoGen compatibles</p>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Exécutions par agent" icon={Activity} subtitle="Répartition des 30 derniers jours" />
          <div className="card-body pt-2">
            {perAgentChart.length
              ? <BarChartView data={perAgentChart} xKey="name" stacked height={230}
                  series={[{ key: 'réussi', label: 'Réussies', color: '#10B981' },
                          { key: 'réservé', label: 'Réservées', color: '#8B5CF6' },
                          { key: 'échec', label: 'Échecs', color: '#E11D48' }]} />
              : <EmptyState icon={Activity} title="Aucune exécution" />}
          </div>
        </Card>

        <Card>
          <CardHeader title="Lancer un agent" icon={PlayCircle} subtitle="Exécution journalisée dans l’audit" />
          <div className="card-body space-y-3">
            <Select label="Projet" value={picker.project}
              onChange={(e) => setPicker({ ...picker, project: e.target.value })}
              options={[{ value: '', label: '— Choisir un projet —' },
                ...projects.map((p) => ({ value: p.id, label: `${p.reference} · ${p.name}` }))]} />
            <Select label="Agent" value={picker.agent}
              onChange={(e) => setPicker({ ...picker, agent: e.target.value })}
              options={agents.map((a) => ({ value: a.key, label: a.name }))} />
            <Button className="w-full" icon={PlayCircle} disabled={!picker.project}
              loading={!!launching} onClick={launch}>Lancer l’exécution</Button>
            <p className="hint">
              Le résultat est une exécution « réservée » : aucune inférence, aucune écriture externe.
            </p>
          </div>
        </Card>
      </div>

      {result && (
        <Alert tone={result.reserved ? 'info' : 'success'}
          title={result.reserved ? 'Exécution enregistrée — emplacement réservé' : 'Exécution lancée'}
          action={<Button variant="ghost" size="sm" icon={X} onClick={() => setResult(null)}>Fermer</Button>}>
          {result.detail || `Exécution #${result.run?.id} · statut ${RUN_STATUS[result.run?.status]?.label}`}
          {result.run?.id && (
            <p className="mt-1.5 text-[11.5px] opacity-80">
              Contrat de sortie attendu : {JSON.stringify(Object.keys(result.run.output_payload?._contract || {})).slice(0, 120)}
            </p>
          )}
        </Alert>
      )}

      {/* ------------------------------- Cartes agents ------------------------------- */}
      <div className="grid gap-4 xl:grid-cols-3">
        {loading ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-80 w-full rounded-xl" />)
        ) : agents.map((a) => {
          const Icon = ICONS[a.icon] || Bot
          const isOpen = expanded === a.key
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
                <p className="text-[12.5px] leading-relaxed text-slate-600">{a.description}</p>

                <div className="mt-3 grid grid-cols-3 gap-2 rounded-lg bg-slate-50 p-3 text-center">
                  <Stat label="Exécutions" value={a.total_runs} />
                  <Stat label="Réussies" value={a.successful_runs} tone="text-emerald-600" />
                  <Stat label="Latence" value={`${num(a.avg_latency_ms)} ms`} />
                </div>

                <button onClick={() => setExpanded(isOpen ? null : a.key)}
                  className="mt-3 flex w-full items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-[12.5px] font-medium text-slate-700 transition hover:border-brand-300 hover:bg-brand-50/40">
                  <span className="flex items-center gap-1.5"><Code2 size={14} /> Contrat d’interface</span>
                  <ChevronDown size={14} className={cx('transition', isOpen && 'rotate-180')} />
                </button>

                {isOpen && (
                  <div className="mt-2 space-y-3 animate-fade-in">
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Modèle suggéré</p>
                      <p className="mt-0.5 text-[11.5px] text-slate-600">{a.suggested_model}</p>
                    </div>
                    <div>
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Stack</p>
                      <p className="mt-0.5 text-[11.5px] text-slate-600">{a.suggested_stack}</p>
                    </div>
                    <Contract title="Entrée" schema={a.input_schema_hint} />
                    <Contract title="Sortie" schema={a.output_schema_hint} />
                    {(a.capabilities || []).length > 0 && (
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Capacités</p>
                        <ul className="mt-1.5 space-y-1">
                          {a.capabilities.map((c) => (
                            <li key={c} className="flex gap-1.5 text-[11.5px] text-slate-600">
                              <Check size={12} className="mt-0.5 shrink-0 text-brand-600" /> {c}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
                      <p className="text-[11px] text-slate-500">Endpoint du runtime</p>
                      <p className="mt-0.5 font-mono text-[11px] text-slate-700">{a.runtime_endpoint || '— non configuré —'}</p>
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-auto flex items-center justify-between gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3">
                <span className="text-[11px] text-slate-500">
                  {a.last_run_at ? `Dernier lancement ${timeAgo(a.last_run_at)}` : 'Jamais lancé'}
                </span>
                <Button size="sm" variant="soft" icon={PlayCircle}
                  onClick={() => { setPicker({ ...picker, agent: a.key }) }}>
                  Sélectionner
                </Button>
              </div>
            </Card>
          )
        })}
      </div>

      {/* ------------------------------- Plans à valider ------------------------------- */}
      <Card>
        <CardHeader title="Plans en attente de validation" icon={Check}
          subtitle="Étape de validation humaine avant toute écriture Jira/Trello" />
        {pending.length === 0 ? (
          <div className="p-6"><EmptyState icon={Check} title="Aucun plan en attente"
            description="Les propositions de l’Agent 1 apparaîtront ici, projet par projet." /></div>
        ) : (
          <div className="divide-y divide-slate-100">
            {pending.map((p) => (
              <div key={p.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-violet-50 text-violet-600">
                  <Sparkles size={16} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-semibold text-slate-800">{p.title}</p>
                  <p className="truncate text-[11.5px] text-slate-500">
                    {p.project_name} · v{p.version} · {p.tasks_count} tâches · {num(p.total_estimate_hours, 1)} h ·{' '}
                    complétude {Math.round(Number(p.confidence) * 100)} %
                  </p>
                </div>
                <Badge className="badge-warning">À valider</Badge>
                <Link to={`/app/projects/${p.project}/validation`} className="btn btn-primary btn-sm">Revoir</Link>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* ------------------------------- Journal d’exécutions ------------------------------- */}
      <Card>
        <CardHeader title="Journal des exécutions" icon={GitBranch}
          subtitle="Traçabilité complète : agent, déclencheur, statut, corrélation"
          action={<Button variant="ghost" size="sm" icon={RefreshCw} onClick={refetchRuns} />} />
        {runs.length === 0 ? (
          <div className="p-6"><EmptyState icon={GitBranch} title="Aucune exécution" /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Agent</th><th>Projet</th><th>Statut</th><th>Déclencheur</th>
                  <th>Étape courante</th><th>Heure</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const st = RUN_STATUS[r.status] || RUN_STATUS.QUEUED
                  return (
                    <tr key={r.id}>
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
                        <p className="max-w-[160px] truncate text-[10.5px] text-slate-400">{r.project_name}</p>
                      </td>
                      <td><Badge className={st.cls} dot={st.dot}>{st.label}</Badge></td>
                      <td className="text-[12px] text-slate-600">
                        {r.triggered_by_name || 'Système'}
                        <span className="ml-1.5 text-[10.5px] text-slate-400">
                          {{ MANUAL: 'manuel', PIPELINE: 'pipeline', SCHEDULED: 'planifié', RETRY: 'retry' }[r.trigger]}
                        </span>
                      </td>
                      <td className="max-w-[200px] truncate text-[12px] text-slate-600">{r.step || '—'}</td>
                      <td className="whitespace-nowrap text-[11.5px] text-slate-500">{formatDateTime(r.created_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* ------------------------------- Pipeline / observabilité ------------------------------- */}
      <div className="grid gap-4 lg:grid-cols-3">
        <IntegrationCard icon={Server} title="Pipeline Airflow" tone="brand"
          items={['Ré-entraînement mensuel du modèle de génération (Agent 1)',
                 'Collecte hebdomadaire des données Jira/Trello (Agent 3)',
                 'Déclenchement du CT sur écart temps estimé / temps réel']} />
        <IntegrationCard icon={Zap} title="Dashboard Grafana" tone="sky"
          items={['Latence et taux d’erreur de format JSON',
                 'Taux de succès des appels API et équilibrage de charge',
                 'Scores de risque par projet / sprint avec alertes']} />
        <IntegrationCard icon={Database} title="Évaluation continue" tone="violet"
          items={['Score de complétude et taux d’estimations aberrantes',
                 'Indice d’équilibrage et taux de réassignation manuelle',
                 'Risque prédit vs. retard effectif constaté']} />
      </div>
    </div>
  )
}

function Stat({ label, value, tone = 'text-slate-900' }) {
  return (
    <div>
      <p className={cx('text-[15px] font-bold leading-none', tone)}>{value}</p>
      <p className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">{label}</p>
    </div>
  )
}

function Contract({ title, schema }) {
  const entries = Object.entries(schema || {})
  if (!entries.length) return null
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Schéma de {title.toLowerCase()}</p>
      <pre className="mt-1 max-h-[200px] overflow-auto rounded-lg bg-slate-900 p-3 font-mono text-[10.5px] leading-relaxed text-slate-100">
{JSON.stringify(schema, null, 2)}
      </pre>
    </div>
  )
}

function IntegrationCard({ icon: Icon, title, items, tone }) {
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
