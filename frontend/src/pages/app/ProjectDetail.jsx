import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Activity, AlertTriangle, ArrowLeft, BarChart3, Bot, Calendar, Check, CheckCircle2, ChevronRight,
  Clock, Download, Edit3, ExternalLink, Eye, GitBranch, Layers, MessageSquare, PlayCircle,
  Plug, Plus, RefreshCw, ShieldAlert, Sparkles, Target, Trash2, Users, Wand2, X, XCircle,
} from 'lucide-react'
import api, { errorMessage, fieldErrors } from '../../lib/api'
import { useQuery } from '../../lib/useApi'
import { useAuth } from '../../context/AuthContext'
import {
  Alert, Avatar, AvatarStack, Badge, Breadcrumbs, Button, Card, CardHeader, ConfirmDialog,
  EmptyState, Input, Modal, Progress, Ring, Select, Skeleton, Tabs, Textarea,
} from '../../components/ui'
import { BarChartView, DonutChart, RadarChartView, TrendChart } from '../../components/charts'
import {
  PROPOSAL_STATUS, PROJECT_STATUS, RISK_CATEGORY, RUN_STATUS, TASK_PRIORITY, TASK_STATUS,
  TASK_TYPE, cx, currency, daysUntil, formatDate, formatDateTime, healthTone, hours, num,
  pct, relativeDeadline, riskTone, timeAgo, toCSV,
} from '../../lib/format'

const TABS = [
  { key: 'overview', label: 'Vue d’ensemble', icon: Target },
  { key: 'tasks', label: 'Tâches & lots', icon: Layers },
  { key: 'board', label: 'Kanban', icon: Activity },
  { key: 'team', label: 'Équipe & charge', icon: Users },
  { key: 'agents', label: 'Copilote', icon: Sparkles },
  { key: 'validation', label: 'Validation', icon: CheckCircle2 },
  { key: 'risks', label: 'Risques', icon: ShieldAlert },
  { key: 'integrations', label: 'Connecteurs', icon: Plug },
  { key: 'activity', label: 'Activité', icon: GitBranch },
]

export default function ProjectDetail() {
  const { id, tab = 'overview' } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { data: project, loading, error, refetch } = useQuery(`/projects/${id}/`)
  const [tabState, setTabState] = useState(tab)

  const setTab = (t) => { setTabState(t); navigate(`/app/projects/${id}/${t}`, { replace: true }) }

  if (loading && !project) return <DetailSkeleton />
  if (error) return <div className="p-7"><Alert tone="error" title="Projet introuvable">{error}</Alert></div>
  if (!project) return null

  const st = PROJECT_STATUS[project.status] || PROJECT_STATUS.DRAFT
  const tone = healthTone(project.health)
  const indicators = project.health_indicators || {}
  const canEdit = user?.id === project.owner || user?.role === 'ADMIN' || user?.is_superuser

  const tabCounts = {
    tasks: project.task_count,
    risks: project.open_risks,
    validation: (project.proposals_pending ?? 0),
    team: project.member_count,
  }

  return (
    <div className="space-y-5 p-5 sm:p-7">
      {/* ------------------------------ Fil d’Ariane ------------------------------ */}
      <Breadcrumbs items={[
        { to: '/app', label: 'Tableau de bord' },
        { to: '/app/projects', label: 'Projets' },
        { label: project.reference },
      ]} />

      {/* ------------------------------ En-tête ------------------------------ */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-brand-600">{project.reference}</span>
            <Badge className={st.cls}>{st.label}</Badge>
            <Badge className={tone.cls} dot={tone.dot}>{tone.label}</Badge>
            <Badge className="badge-neutral">{project.methodology}</Badge>
            {project.external_provider && (
              <Badge className="badge-sky">
                <Plug size={11} /> {project.external_provider === 'JIRA' ? 'Jira' : 'Trello'} · {project.external_key}
              </Badge>
            )}
          </div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">{project.name}</h1>
          <p className="mt-1 max-w-3xl text-[14px] text-slate-500">{project.summary}</p>
          <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-slate-500">
            <span className="flex items-center gap-1.5">
              <Avatar name={project.owner_name} color={project.owner_color} size={20} />
              {project.owner_name}
            </span>
            {project.team_name && <span className="flex items-center gap-1.5"><Users size={13} /> {project.team_name}</span>}
            <span className="flex items-center gap-1.5">
              <Calendar size={13} /> {formatDate(project.start_date)} → {formatDate(project.target_end_date)}
            </span>
            {project.budget && <span>💶 {currency(project.budget, project.currency)}</span>}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" icon={RefreshCw} onClick={refetch}>Actualiser</Button>
          {canEdit && <EditProject project={project} onSaved={refetch} />}
          <Button variant="primary" icon={Wand2} onClick={() => setTab('agents')}>Lancer le copilote</Button>
        </div>
      </header>

      {/* ------------------------------ Bandeau KPI ------------------------------ */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Avancement</p>
          <div className="mt-2 flex items-center gap-3">
            <Ring value={project.progress} size={48} stroke={5}
              color={project.health === 'RED' ? '#E11D48' : project.health === 'AMBER' ? '#F59E0B' : '#2563EB'} />
            <div>
              <p className="text-[13px] font-semibold text-slate-800">{project.done_count}/{project.task_count} tâches</p>
              <p className="text-[11px] text-slate-400">{num(indicators.overdue_tasks)} en retard</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Charge</p>
          <p className="mt-2 text-[22px] font-bold leading-none text-slate-900">{hours(project.estimated_effort_hours)}</p>
          <p className="mt-1 text-[11.5px] text-slate-400">
            {hours(project.spent_effort_hours)} réalisées · écart{' '}
            <span className={cx('font-semibold', indicators.effort_variance_pct > 0 ? 'text-rose-600' : 'text-emerald-600')}>
              {indicators.effort_variance_pct > 0 ? '+' : ''}{num(indicators.effort_variance_pct, 1)} %
            </span>
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Score de risque</p>
          <div className="mt-2 flex items-center gap-3">
            <span className={cx('text-[22px] font-bold leading-none',
              project.risk_score >= 55 ? 'text-rose-600' : project.risk_score >= 25 ? 'text-amber-600' : 'text-emerald-600')}>
              {Math.round(project.risk_score)}
            </span>
            <span className="text-[12px] text-slate-400">/100</span>
          </div>
          <Progress value={project.risk_score} size={4} className="mt-2"
            tone={project.risk_score >= 55 ? 'bg-rose-500' : project.risk_score >= 25 ? 'bg-amber-500' : 'bg-emerald-500'} />
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Alertes ouvertes</p>
          <p className="mt-2 text-[22px] font-bold leading-none text-slate-900">{num(project.open_risks)}</p>
          <p className="mt-1 text-[11.5px] text-slate-400">{num(indicators.blocked_tasks)} tâche(s) bloquée(s)</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Budget consommé</p>
          <p className="mt-2 text-[22px] font-bold leading-none text-slate-900">{pct(project.budget_consumed, 1)}</p>
          <Progress value={project.budget_consumed} size={4} className="mt-2"
            tone={project.budget_consumed > 90 ? 'bg-rose-500' : 'bg-brand-600'} />
        </Card>
      </div>

      {/* ------------------------------ Onglets ------------------------------ */}
      <Tabs
        value={tabState}
        onChange={setTab}
        tabs={TABS.map((t) => ({
          ...t,
          count: tabCounts[t.key] || undefined,
        }))}
        className="sticky top-0 z-10 bg-slate-50/95 backdrop-blur"
      />

      {tabState === 'overview' && <OverviewTab project={project} onRecompute={refetch} />}
      {tabState === 'tasks' && <TasksTab project={project} onChanged={refetch} canEdit={canEdit} />}
      {tabState === 'board' && <BoardTab project={project} onChanged={refetch} canEdit={canEdit} />}
      {tabState === 'team' && <TeamTab project={project} onChanged={refetch} canEdit={canEdit} />}
      {tabState === 'agents' && <AgentsTab project={project} onChanged={refetch} canEdit={canEdit} />}
      {tabState === 'validation' && <ValidationTab project={project} onChanged={refetch} canEdit={canEdit} />}
      {tabState === 'risks' && <RisksTab project={project} onChanged={refetch} />}
      {tabState === 'integrations' && <IntegrationsTab project={project} onChanged={refetch} canEdit={canEdit} />}
      {tabState === 'activity' && <ActivityTab project={project} />}
    </div>
  )
}

/* =========================================================================
 * Onglet — Vue d’ensemble
 * ========================================================================= */
function OverviewTab({ project, onRecompute }) {
  const { data: workload } = useQuery(`/projects/${project.id}/workload/`)
  const { data: board } = useQuery(`/projects/${project.id}/board/`)
  const [recomputing, setRecomputing] = useState(false)

  const recompute = async () => {
    setRecomputing(true)
    try { await api.post(`/projects/${project.id}/recompute/`); await onRecompute() }
    finally { setRecomputing(false) }
  }

  const byStatus = (board?.columns || []).map((c) => ({
    label: TASK_STATUS[c.key]?.label || c.key, value: c.tasks.length,
    color: TASK_STATUS[c.key]?.hex,
  }))

  const riskRadar = (project.risk_alerts || []).slice(0, 8).map((a) => ({
    label: (RISK_CATEGORY[a.category] || a.category).slice(0, 14),
    value: Number(a.score),
  }))

  const lots = (project.work_packages || []).map((wp) => ({
    label: wp.name.length > 22 ? `${wp.name.slice(0, 20)}…` : wp.name,
    est: Number(wp.estimated_effort_hours),
    confiance: Math.round(Number(wp.confidence) * 100),
  }))

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-3">
        {/* Description */}
        <Card className="xl:col-span-2">
          <CardHeader title="Description du projet" icon={Target}
            subtitle="Matière première du cadrage (Agent 1)"
            action={<Badge className="badge-brand">{(project.brief || '').trim().split(/\s+/).filter(Boolean).length} mots</Badge>} />
          <div className="card-body">
            {project.brief
              ? <p className="whitespace-pre-line text-[13.5px] leading-relaxed text-slate-700">{project.brief}</p>
              : <EmptyState icon={Target} title="Aucune description" description="Ajoutez une description pour permettre au copilote de proposer un découpage." />}
            {(project.tags || []).length > 0 && (
              <div className="mt-4 flex flex-wrap gap-1.5">
                {project.tags.map((t) => <span key={t} className="chip">{t}</span>)}
              </div>
            )}
          </div>
        </Card>

        {/* Santé */}
        <Card>
          <CardHeader title="Indicateurs de santé" icon={BarChart3}
            action={<Button variant="ghost" size="sm" icon={RefreshCw} loading={recomputing} onClick={recompute}>Recalculer</Button>} />
          <div className="card-body pt-2">
            {[
              ['Avancement', pct(project.progress), project.progress, 'bg-brand-600'],
              ['Budget consommé', pct(project.budget_consumed, 1), project.budget_consumed,
                project.budget_consumed > 90 ? 'bg-rose-500' : 'bg-sky-500'],
              ['Score de risque', `${Math.round(project.risk_score)}/100`, project.risk_score,
                project.risk_score >= 55 ? 'bg-rose-500' : project.risk_score >= 25 ? 'bg-amber-500' : 'bg-emerald-500'],
            ].map(([l, v, val, tone]) => (
              <div key={l} className="border-b border-slate-100 py-2.5 last:border-0">
                <div className="flex items-center justify-between text-[12.5px]">
                  <span className="text-slate-600">{l}</span>
                  <span className="font-bold text-slate-800">{v}</span>
                </div>
                <Progress value={val} tone={tone} size={5} className="mt-1.5" />
              </div>
            ))}
            <div className="mt-3 grid grid-cols-2 gap-2">
              <Metric label="Tâches en retard" value={num(project.health_indicators?.overdue_tasks)}
                tone={project.health_indicators?.overdue_tasks ? 'text-rose-600' : 'text-slate-800'} />
              <Metric label="Tâches bloquées" value={num(project.health_indicators?.blocked_tasks)}
                tone={project.health_indicators?.blocked_tasks ? 'text-amber-600' : 'text-slate-800'} />
              <Metric label="Lots" value={num((project.work_packages || []).length)} />
              <Metric label="Sprints" value={num((project.sprints || []).length)} />
            </div>
          </div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        <Card>
          <CardHeader title="Répartition par statut" icon={Activity} />
          <div className="card-body pt-2">
            <DonutChart data={byStatus.filter((s) => s.value > 0)} centerValue={project.task_count} centerLabel="tâches" />
          </div>
        </Card>

        <Card>
          <CardHeader title="Charge par lot" icon={Layers} subtitle="Effort estimé (heures)" />
          <div className="card-body pt-2">
            {lots.length
              ? <BarChartView data={lots} xKey="label" series={[{ key: 'est', label: 'Heures', color: '#2563EB' }]} layout="vertical" height={Math.max(180, lots.length * 34)} />
              : <EmptyState icon={Layers} title="Aucun lot" description="Les lots apparaissent après le premier découpage du copilote." />}
          </div>
        </Card>

        <Card>
          <CardHeader title="Profil de risque" icon={ShieldAlert} subtitle="Score des alertes récentes" />
          <div className="card-body pt-2">
            {riskRadar.length >= 3
              ? <RadarChartView data={riskRadar} height={240} />
              : <EmptyState icon={ShieldAlert} title="Données insuffisantes" description="Au moins 3 alertes sont nécessaires pour tracer le profil de risque." />}
          </div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        {/* Lots */}
        <Card>
          <CardHeader title="Lots de travail" icon={Layers}
            subtitle={`${(project.work_packages || []).length} lot(s) issus du découpage`} />
          <div className="card-body pt-2">
            {(project.work_packages || []).length === 0 && (
              <EmptyState icon={Layers} title="Aucun lot défini"
                description="Lancez l’Agent 1 pour obtenir une proposition de découpage en lots." />
            )}
            {(project.work_packages || []).map((wp) => (
              <div key={wp.id} className="border-b border-slate-100 py-3 last:border-0">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-2.5">
                    <span className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: wp.color }} />
                    <div className="min-w-0">
                      <p className="truncate text-[13.5px] font-semibold text-slate-800">{wp.name}</p>
                      {wp.description && <p className="mt-0.5 line-clamp-2 text-[11.5px] text-slate-500">{wp.description}</p>}
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-[12.5px] font-bold text-slate-800">{hours(wp.estimated_effort_hours)}</p>
                    <p className="text-[10.5px] text-slate-400">{wp.task_count} tâche(s)</p>
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <Progress value={wp.progress} size={4} className="flex-1" tone="bg-brand-600" />
                  <span className="text-[10.5px] text-slate-500">{wp.progress}% · confiance {Math.round(Number(wp.confidence) * 100)}%</span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Sprints */}
        <Card>
          <CardHeader title="Sprints" icon={GitBranch} subtitle="Vélocité et engagement" />
          <div className="card-body pt-2">
            {(project.sprints || []).length === 0 && <EmptyState icon={GitBranch} title="Aucun sprint planifié" />}
            {(project.sprints || []).map((s) => {
              const delivered = Number(s.completed_points)
              const committed = Number(s.committed_points) || 1
              const rate = Math.round((delivered / committed) * 100)
              const stBadge = { PLANNED: 'badge-neutral', ACTIVE: 'badge-brand', COMPLETED: 'badge-success' }[s.status]
              return (
                <div key={s.id} className="border-b border-slate-100 py-3 last:border-0">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-[13.5px] font-semibold text-slate-800">{s.name}</p>
                        <Badge className={stBadge}>
                          {{ PLANNED: 'Planifié', ACTIVE: 'Actif', COMPLETED: 'Terminé' }[s.status]}
                        </Badge>
                      </div>
                      {s.goal && <p className="mt-0.5 line-clamp-2 text-[11.5px] text-slate-500">{s.goal}</p>}
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-[12.5px] font-bold text-slate-800">{num(delivered, 1)} pts</p>
                      <p className="text-[10.5px] text-slate-400">sur {num(committed, 1)}</p>
                    </div>
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <Progress value={Math.min(100, rate)} size={4} className="flex-1"
                      tone={rate >= 85 ? 'bg-emerald-500' : rate >= 60 ? 'bg-brand-600' : 'bg-amber-500'} />
                    <span className="text-[10.5px] text-slate-500">{rate}% livré</span>
                  </div>
                  {s.start_date && (
                    <p className="mt-1 text-[10.5px] text-slate-400">
                      {formatDate(s.start_date, { day: '2-digit', month: 'short' })} → {formatDate(s.end_date, { day: '2-digit', month: 'short' })}
                      {s.risk_score > 40 && <span className="ml-2 font-semibold text-amber-600">risque {Math.round(s.risk_score)}</span>}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </Card>
      </div>
    </div>
  )
}

function Metric({ label, value, tone = 'text-slate-800' }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-[10.5px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className={cx('mt-0.5 text-[15px] font-bold', tone)}>{value}</p>
    </div>
  )
}

/* =========================================================================
 * Onglet — Tâches & lots
 * ========================================================================= */
function TasksTab({ project, onChanged, canEdit }) {
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [lotFilter, setLotFilter] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')
  const [task, setTask] = useState(null)
  const [creating, setCreating] = useState(false)

  const tasks = useMemo(() => {
    let list = [...(project.recent_tasks || [])]
    if (search) {
      const q = search.toLowerCase()
      list = list.filter((t) => t.title.toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q))
    }
    if (statusFilter) list = list.filter((t) => t.status === statusFilter)
    if (lotFilter) list = list.filter((t) => String(t.work_package) === String(lotFilter))
    if (priorityFilter) list = list.filter((t) => t.priority === priorityFilter)
    return list
  }, [project.recent_tasks, search, statusFilter, lotFilter, priorityFilter])

  const exportTasks = () => toCSV((project.recent_tasks || []).map((t) => ({
    titre: t.title, lot: t.work_package_name, statut: t.status, priorite: t.priority,
    type: t.task_type, assigne: t.assignee_detail?.full_name || '',
    estime_h: t.estimate_hours, realise_h: t.spent_hours, risque: t.risk_score,
    echeance: t.due_date,
  })), `cadria-${project.reference}-taches.csv`)

  return (
    <div className="space-y-4">
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Input icon={Eye} placeholder="Filtrer les tâches…" value={search}
            onChange={(e) => setSearch(e.target.value)} className="min-w-[200px] flex-1 [&_.field]:h-9" />
          <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-[150px]"
            options={[{ value: '', label: 'Tous les statuts' },
              ...Object.entries(TASK_STATUS).map(([k, v]) => ({ value: k, label: v.label }))]} />
          <Select value={lotFilter} onChange={(e) => setLotFilter(e.target.value)} className="w-[170px]"
            options={[{ value: '', label: 'Tous les lots' },
              ...(project.work_packages || []).map((wp) => ({ value: wp.id, label: wp.name }))]} />
          <Select value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} className="w-[150px]"
            options={[{ value: '', label: 'Toutes priorités' },
              ...Object.entries(TASK_PRIORITY).map(([k, v]) => ({ value: k, label: v.label }))]} />
          <Button variant="secondary" size="sm" icon={Download} onClick={exportTasks}>CSV</Button>
          {canEdit && <Button size="sm" icon={Plus} onClick={() => setCreating(true)}>Tâche</Button>}
        </div>
      </Card>

      {tasks.length === 0 ? (
        <EmptyState icon={Layers} title="Aucune tâche"
          description={project.task_count
            ? 'Ajustez les filtres pour afficher les tâches.'
            : 'Lancez l’Agent 1 pour obtenir une proposition de découpage, ou créez une tâche manuellement.'} />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Tâche</th><th>Lot</th><th>Statut</th><th>Priorité</th><th>Assigné</th>
                  <th>Charge</th><th>Risque</th><th>Échéance</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((t) => {
                  const st = TASK_STATUS[t.status]
                  const pr = TASK_PRIORITY[t.priority]
                  const risk = riskTone(t.risk_score)
                  const dl = relativeDeadline(t.due_date)
                  return (
                    <tr key={t.id} onClick={() => setTask(t)} className="cursor-pointer">
                      <td>
                        <div className="flex items-start gap-2.5">
                          {t.created_by_agent && (
                            <span title="Créée par l’Agent 1" className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded bg-violet-50 text-violet-600">
                              <Sparkles size={11} />
                            </span>
                          )}
                          <div className="min-w-0">
                            <p className="max-w-[260px] truncate text-[13px] font-semibold text-slate-800">{t.title}</p>
                            <div className="mt-1 flex flex-wrap items-center gap-1.5">
                              <Badge className={TASK_TYPE[t.task_type]?.cls}>{TASK_TYPE[t.task_type]?.label}</Badge>
                              {t.blocked && <Badge className="badge-danger">Bloquée</Badge>}
                              {t.external_id && <Badge className="badge-sky">{t.external_id}</Badge>}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="max-w-[130px] truncate text-[12px] text-slate-600">{t.work_package_name || '—'}</td>
                      <td><Badge className={st.cls} dot={st.hex}>{st.label}</Badge></td>
                      <td><Badge className={pr.cls}>{pr.label}</Badge></td>
                      <td>{t.assignee_detail
                        ? <div className="flex items-center gap-2">
                            <Avatar name={t.assignee_detail.full_name} color={t.assignee_detail.avatar_color} size={24} />
                            <span className="max-w-[100px] truncate text-[12px] text-slate-600">{t.assignee_detail.full_name}</span>
                          </div>
                        : <span className="text-[12px] text-slate-400">Non assignée</span>}
                      </td>
                      <td className="whitespace-nowrap">
                        <span className="text-[12px] font-semibold text-slate-700">{hours(t.estimate_hours)}</span>
                        {t.spent_hours > 0 && (
                          <p className={cx('text-[10.5px]', t.effort_variance > 0 ? 'text-rose-500' : 'text-slate-400')}>
                            {hours(t.spent_hours)} · {t.effort_variance > 0 ? '+' : ''}{num(t.effort_variance, 1)}%
                          </p>
                        )}
                      </td>
                      <td><Badge className={risk.cls}>{Math.round(t.risk_score)}</Badge></td>
                      <td className="whitespace-nowrap">
                        <span className="text-[12px] text-slate-600">{formatDate(t.due_date, { day: '2-digit', month: 'short' })}</span>
                        {dl && <p className={cx('text-[10.5px]', dl.tone === 'danger' ? 'text-rose-500' : dl.tone === 'warning' ? 'text-amber-600' : 'text-slate-400')}>{dl.text}</p>}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {task && <TaskDrawer task={task} project={project} onClose={() => setTask(null)} onChanged={onChanged} canEdit={canEdit} />}
      {creating && <TaskModal project={project} onClose={() => setCreating(false)} onSaved={() => { setCreating(false); onChanged() }} />}
    </div>
  )
}

function TaskDrawer({ task, project, onClose, onChanged, canEdit }) {
  const [status, setStatus] = useState(task.status)
  const [saving, setSaving] = useState(false)
  const risk = riskTone(task.risk_score)
  const st = TASK_STATUS[status]

  const save = async () => {
    setSaving(true)
    try {
      await api.patch(`/tasks/${task.id}/`, { status })
      await onChanged()
      onClose()
    } finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title={task.title} subtitle={`${project.name} · ${TASK_TYPE[task.task_type]?.label}`}
      size="lg" icon={Layers}
      footer={canEdit && status !== task.status
        ? <><Button variant="secondary" onClick={() => setStatus(task.status)}>Annuler</Button>
            <Button loading={saving} onClick={save}>Enregistrer</Button></>
        : null}>
      <div className="space-y-4">
        <div className="flex flex-wrap gap-1.5">
          <Badge className={st.cls} dot={st.hex}>{st.label}</Badge>
          <Badge className={TASK_PRIORITY[task.priority].cls}>{TASK_PRIORITY[task.priority].label}</Badge>
          {task.created_by_agent && <Badge className="badge-purple"><Sparkles size={11} /> Agent 1</Badge>}
          {task.blocked && <Badge className="badge-danger">Bloquée</Badge>}
        </div>

        {task.description && <p className="text-[13.5px] leading-relaxed text-slate-700">{task.description}</p>}

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Assigné à">
            {task.assignee_detail
              ? <span className="flex items-center gap-2">
                  <Avatar name={task.assignee_detail.full_name} color={task.assignee_detail.avatar_color} size={24} />
                  {task.assignee_detail.full_name}
                </span>
              : 'Non assignée'}
          </Field>
          <Field label="Lot">{task.work_package_name || '—'}</Field>
          <Field label="Sprint">{task.sprint_name || '—'}</Field>
          <Field label="Échéance">{formatDate(task.due_date)}</Field>
          <Field label="Charge estimée">{hours(task.estimate_hours)}</Field>
          <Field label="Charge réalisée">
            {hours(task.spent_hours)}
            {task.effort_variance !== 0 && (
              <span className={cx('ml-1.5 text-[11.5px] font-semibold', task.effort_variance > 0 ? 'text-rose-600' : 'text-emerald-600')}>
                ({task.effort_variance > 0 ? '+' : ''}{num(task.effort_variance, 1)} %)
              </span>
            )}
          </Field>
        </div>

        {(task.required_skills || []).length > 0 && (
          <div>
            <p className="label">Compétences requises</p>
            <div className="flex flex-wrap gap-1.5">{task.required_skills.map((s) => <span key={s} className="chip">{s}</span>)}</div>
          </div>
        )}

        {(task.acceptance_criteria || []).length > 0 && (
          <div>
            <p className="label">Critères d’acceptation</p>
            <ul className="space-y-1.5">
              {task.acceptance_criteria.map((c, i) => (
                <li key={i} className="flex gap-2 text-[12.5px] text-slate-600">
                  <Check size={14} className="mt-0.5 shrink-0 text-brand-600" /> {c}
                </li>
              ))}
            </ul>
          </div>
        )}

        {task.risk_score > 0 && (
          <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex items-center justify-between">
              <p className="flex items-center gap-1.5 text-[13px] font-semibold text-slate-800">
                <ShieldAlert size={15} className="text-amber-600" /> Analyse de risque
              </p>
              <Badge className={risk.cls}>{risk.label} · {Math.round(task.risk_score)}</Badge>
            </div>
            {(task.risk_factors || []).length > 0 && (
              <div className="mt-3 space-y-1.5">
                {task.risk_factors.map((f, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-[150px] shrink-0 truncate text-[11.5px] text-slate-600">{f.label}</span>
                    <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                      <span className="block h-full rounded-full bg-amber-500" style={{ width: `${Number(f.weight) * 100}%` }} />
                    </span>
                    <span className="w-8 text-right text-[10.5px] font-semibold text-slate-500">{Math.round(f.weight * 100)}%</span>
                  </div>
                ))}
              </div>
            )}
            {task.risk_explanation && <p className="mt-2.5 text-[12px] text-slate-600">{task.risk_explanation}</p>}
          </div>
        )}

        {canEdit && (
          <div>
            <label className="label">Changer le statut</label>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(TASK_STATUS).map(([k, v]) => (
                <button key={k} onClick={() => setStatus(k)}
                  className={cx('rounded-lg border px-3 py-1.5 text-[12px] font-medium transition',
                    status === k ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-200 text-slate-600 hover:border-slate-300')}>
                  {v.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}

function TaskModal({ project, onClose, onSaved }) {
  const [form, setForm] = useState({
    title: '', description: '', task_type: 'FEATURE', priority: 'MEDIUM',
    work_package: '', estimate_hours: 8, due_date: '', assignee: '',
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const { data: membersData } = useQuery('/members/', { params: { page_size: 60 } })
  const members = membersData?.results ?? membersData ?? []

  const save = async () => {
    setSaving(true); setErrors({})
    try {
      await api.post('/tasks/', {
        project: project.id,
        title: form.title, description: form.description, task_type: form.task_type,
        priority: form.priority, estimate_hours: Number(form.estimate_hours) || 0,
        due_date: form.due_date || null,
        work_package: form.work_package || null,
        assignee: form.assignee || null,
      })
      onSaved()
    } catch (e) { setErrors(fieldErrors(e)) }
    finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title="Nouvelle tâche" subtitle={project.name} icon={Plus}
      footer={<><Button variant="secondary" onClick={onClose}>Annuler</Button>
        <Button loading={saving} onClick={save}>Créer la tâche</Button></>}>
      <div className="space-y-4">
        <Input label="Titre" required value={form.title} error={errors.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })} />
        <Textarea label="Description" value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Type" value={form.task_type} onChange={(e) => setForm({ ...form, task_type: e.target.value })}
            options={Object.entries(TASK_TYPE).map(([k, v]) => ({ value: k, label: v.label }))} />
          <Select label="Priorité" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}
            options={Object.entries(TASK_PRIORITY).map(([k, v]) => ({ value: k, label: v.label }))} />
          <Select label="Lot" value={form.work_package} onChange={(e) => setForm({ ...form, work_package: e.target.value })}
            options={[{ value: '', label: '— Aucun —' },
              ...(project.work_packages || []).map((wp) => ({ value: wp.id, label: wp.name }))]} />
          <Input label="Charge estimée (h)" type="number" min="0" step="0.5"
            value={form.estimate_hours} onChange={(e) => setForm({ ...form, estimate_hours: e.target.value })} />
          <Input label="Échéance" type="date" value={form.due_date}
            onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
          <Select label="Assigné à" value={form.assignee} onChange={(e) => setForm({ ...form, assignee: e.target.value })}
            options={[{ value: '', label: '— Non assignée —' },
              ...members.map((m) => ({ value: m.id, label: m.full_name }))]} />
        </div>
      </div>
    </Modal>
  )
}

/* =========================================================================
 * Onglet — Kanban
 * ========================================================================= */
function BoardTab({ project, onChanged, canEdit }) {
  const { data: board, loading, refetch } = useQuery(`/projects/${project.id}/board/`)
  const [moving, setMoving] = useState(null)

  const move = async (taskId, status) => {
    setMoving(taskId)
    try {
      await api.post(`/tasks/${taskId}/move/`, { status })
      await refetch(); await onChanged()
    } finally { setMoving(null) }
  }

  if (loading && !board) return <Card><Skeleton className="h-64 w-full" /></Card>

  return (
    <div className="grid gap-4 overflow-x-auto lg:grid-cols-5">
      {(board?.columns || []).map((col) => {
        const meta = TASK_STATUS[col.key]
        return (
          <Card key={col.key} className="flex min-w-[260px] flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: meta.hex }} />
                <span className="text-[13px] font-semibold text-slate-800">{meta.label}</span>
                <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10.5px] font-bold text-slate-600">
                  {col.tasks.length}
                </span>
              </div>
            </div>
            <div className="flex-1 space-y-2 p-2.5">
              {col.tasks.length === 0 && (
                <p className="rounded-lg border border-dashed border-slate-200 px-3 py-6 text-center text-[11.5px] text-slate-400">
                  Aucune tâche
                </p>
              )}
              {col.tasks.map((t) => (
                <div key={t.id}
                  className={cx('rounded-lg border border-slate-200 bg-white p-3 transition hover:border-brand-300 hover:shadow-card',
                    moving === t.id && 'opacity-50')}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[12.5px] font-semibold leading-snug text-slate-800">{t.title}</p>
                    <Badge className={TASK_PRIORITY[t.priority].cls}>{TASK_PRIORITY[t.priority].label.slice(0, 4)}.</Badge>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1">
                    <Badge className={TASK_TYPE[t.task_type]?.cls}>{TASK_TYPE[t.task_type]?.label}</Badge>
                    {t.created_by_agent && <Badge className="badge-purple"><Sparkles size={10} /></Badge>}
                  </div>
                  <div className="mt-2.5 flex items-center justify-between">
                    {t.assignee_detail
                      ? <Avatar name={t.assignee_detail.full_name} color={t.assignee_detail.avatar_color} size={22} />
                      : <span className="text-[10.5px] text-slate-400">Non assignée</span>}
                    <span className="text-[10.5px] text-slate-500">{hours(t.estimate_hours)}</span>
                  </div>
                  {canEdit && (
                    <div className="mt-2.5 flex gap-1 border-t border-slate-100 pt-2">
                      {Object.keys(TASK_STATUS).filter((k) => k !== col.key).map((k) => (
                        <button key={k} onClick={() => move(t.id, k)} title={TASK_STATUS[k].label}
                          className="rounded px-1.5 py-0.5 text-[10px] font-medium text-slate-500 transition hover:bg-brand-50 hover:text-brand-700">
                          {TASK_STATUS[k].label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>
        )
      })}
    </div>
  )
}

/* =========================================================================
 * Onglet — Équipe & charge
 * ========================================================================= */
function TeamTab({ project, onChanged, canEdit }) {
  const { data: workload, refetch } = useQuery(`/projects/${project.id}/workload/`)
  const [adding, setAdding] = useState(false)

  const chartData = (workload || []).map((m) => ({
    name: m.name.split(' ')[0], pleine: m.name, estimé: m.estimated_hours, capacité: m.capacity_hours,
  }))

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Charge planifiée vs. capacité" icon={BarChart3}
            subtitle="Heures estimées par membre (tâches non terminées)"
            action={<Button variant="ghost" size="sm" icon={RefreshCw} onClick={refetch} />} />
          <div className="card-body pt-2">
            {chartData.length
              ? <BarChartView data={chartData} xKey="name" height={Math.max(220, chartData.length * 34)} layout="vertical"
                  series={[{ key: 'estimé', label: 'Estimé (h)', color: '#2563EB' },
                          { key: 'capacité', label: 'Capacité (h)', color: '#BAE6FD' }]} />
              : <EmptyState icon={Users} title="Aucun membre" />}
          </div>
        </Card>

        <Card>
          <CardHeader title="Équilibrage de charge" icon={Users}
            subtitle="Indice 100 = parfaitement équilibré" />
          <div className="card-body">
            {(() => {
              const rows = workload || []
              if (!rows.length) return <EmptyState icon={Users} title="Aucune donnée" />
              const caps = rows.filter((r) => r.capacity_hours > 0)
              const over = caps.filter((r) => r.utilisation_pct > 110).length
              const under = caps.filter((r) => r.utilisation_pct < 50).length
              const avg = caps.length ? caps.reduce((s, r) => s + r.utilisation_pct, 0) / caps.length : 0
              const total = rows.reduce((s, r) => s + r.estimated_hours, 0)
              const mean = rows.length ? total / rows.length : 0
              const variance = rows.length ? rows.reduce((s, r) => s + Math.abs(r.estimated_hours - mean), 0) / rows.length : 0
              const index = total > 0 ? Math.max(0, Math.round(100 - (variance / (total / rows.length || 1)) * 100)) : 100
              return (
                <>
                  <div className="flex items-center justify-center py-2">
                    <Ring value={index} size={110} stroke={9}
                      color={index >= 75 ? '#10B981' : index >= 50 ? '#F59E0B' : '#E11D48'}>
                      <span className="text-lg font-bold">{index}</span>
                    </Ring>
                  </div>
                  <div className="mt-2 space-y-2">
                    <Row label="Utilisation moyenne" value={pct(avg, 1)} />
                    <Row label="Membres en surcharge" value={over} tone={over ? 'text-rose-600' : 'text-emerald-600'} />
                    <Row label="Membres sous-chargés" value={under} tone={under ? 'text-amber-600' : 'text-slate-800'} />
                    <Row label="Charge totale" value={hours(total)} />
                  </div>
                  <p className="mt-3 rounded-lg bg-brand-50/60 p-3 text-[11.5px] leading-relaxed text-slate-600">
                    L’Agent 2 utilisera cet indice pour proposer des réassignations équilibrées
                    lors de la prochaine assignation.
                  </p>
                </>
              )
            })()}
          </div>
        </Card>
      </div>

      <Card>
        <CardHeader title="Membres du projet" icon={Users}
          subtitle={`${project.member_count} membre(s) mobilisé(s)`}
          action={canEdit && <Button variant="secondary" size="sm" icon={Plus} onClick={() => setAdding(true)}>Ajouter</Button>} />
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th>Membre</th><th>Rôle</th><th>Tâches</th><th>Charge</th><th>Utilisation</th><th>Compétences</th>
              </tr>
            </thead>
            <tbody>
              {(project.members_detail || []).map((m) => {
                const w = (workload || []).find((x) => x.id === m.id) || {}
                const util = w.utilisation_pct || 0
                return (
                  <tr key={m.id}>
                    <td>
                      <div className="flex items-center gap-2.5">
                        <Avatar name={m.full_name} color={m.avatar_color} size={32} />
                        <div className="min-w-0">
                          <p className="truncate text-[13px] font-semibold text-slate-800">{m.full_name}</p>
                          <p className="truncate text-[11.5px] text-slate-500">{m.job_title || m.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="text-[12px] text-slate-600">{m.job_title || '—'}</td>
                    <td className="text-[12.5px] font-semibold text-slate-700">{w.open_tasks ?? m.active_tasks ?? 0}</td>
                    <td className="whitespace-nowrap text-[12.5px] text-slate-600">
                      {hours(w.estimated ?? m.workload_hours)} / {hours(w.capacity ?? m.weekly_capacity_hours)}
                    </td>
                    <td className="w-[150px]">
                      <div className="flex items-center gap-2">
                        <Progress value={Math.min(100, util)} size={5} className="flex-1"
                          tone={util > 110 ? 'bg-rose-500' : util > 85 ? 'bg-amber-500' : 'bg-brand-600'} />
                        <span className={cx('w-11 text-right text-[11px] font-bold',
                          util > 110 ? 'text-rose-600' : util > 85 ? 'text-amber-600' : 'text-emerald-600')}>
                          {pct(util, 0)}
                        </span>
                      </div>
                    </td>
                    <td>
                      <div className="flex flex-wrap gap-1">
                        {(w.skills || []).slice(0, 3).map((s) => <span key={s} className="chip">{s}</span>)}
                        {(w.skills || []).length > 3 && <span className="chip">+{(w.skills || []).length - 3}</span>}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {(project.members_detail || []).length === 0 && (
            <div className="p-6"><EmptyState icon={Users} title="Aucun membre" description="Ajoutez des membres pour répartir la charge." /></div>
          )}
        </div>
      </Card>

      {adding && <AddMemberModal project={project} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); onChanged(); refetch() }} />}
    </div>
  )
}

function AddMemberModal({ project, onClose, onSaved }) {
  const [selected, setSelected] = useState((project.members_detail || []).map((m) => m.id))
  const [saving, setSaving] = useState(false)
  const { data } = useQuery('/members/', { params: { page_size: 60 } })
  const members = data?.results ?? data ?? []

  const save = async () => {
    setSaving(true)
    try { await api.patch(`/projects/${project.id}/`, { member_ids: selected }); onSaved() }
    finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title="Gérer les membres" subtitle={project.name} size="lg" icon={Users}
      footer={<><Button variant="secondary" onClick={onClose}>Annuler</Button>
        <Button loading={saving} onClick={save}>Enregistrer ({selected.length})</Button></>}>
      <div className="space-y-1.5">
        {members.map((m) => {
          const on = selected.includes(m.id)
          return (
            <button key={m.id} onClick={() => setSelected((s) => on ? s.filter((x) => x !== m.id) : [...s, m.id])}
              className={cx('flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition',
                on ? 'border-brand-400 bg-brand-50/60' : 'border-slate-200 hover:border-slate-300')}>
              <Avatar name={m.full_name} color={m.avatar_color} size={32} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-semibold text-slate-800">{m.full_name}</p>
                <p className="truncate text-[11.5px] text-slate-500">
                  {m.job_title || m.email} · {m.workload_hours} h · {m.utilisation}% de charge
                </p>
              </div>
              {on && <Check size={16} className="text-brand-600" />}
            </button>
          )
        })}
      </div>
    </Modal>
  )
}

/* =========================================================================
 * Onglet — Copilote & agents
 * ========================================================================= */
function AgentsTab({ project, onChanged, canEdit }) {
  const { data: agentsData } = useQuery('/agents/')
  const { data: runsData, refetch: refetchRuns } = useQuery('/agent-runs/', { params: { project: project.id } })
  const agents = agentsData?.results ?? agentsData ?? []
  const runs = runsData?.results ?? runsData ?? []
  const [launching, setLaunching] = useState(null)
  const [result, setResult] = useState(null)

  const launch = async (agent) => {
    setLaunching(agent.key)
    try {
      const { data } = await api.post('/agents/runs/start/', {
        project: project.id, agent: agent.key,
        input: { brief: project.brief, project_reference: project.reference },
      })
      setResult(data)
      await refetchRuns(); await onChanged()
    } catch (e) {
      setResult({ detail: errorMessage(e) })
    } finally { setLaunching(null) }
  }

  return (
    <div className="space-y-5">
      {result && (
        <Alert tone={result.reserved ? 'info' : 'success'}
          title={result.reserved ? 'Emplacement réservé — aucune inférence effectuée' : 'Exécution lancée'}
          action={<Button variant="ghost" size="sm" icon={X} onClick={() => setResult(null)}>Fermer</Button>}>
          {result.detail || `Exécution #${result.run?.id} créée avec le statut ${RUN_STATUS[result.run?.status]?.label || result.run?.status}.`}
        </Alert>
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        {agents.map((a) => (
          <Card key={a.id} className="flex flex-col">
            <div className="flex items-start gap-3.5 p-5">
              <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl text-white shadow-sm"
                style={{ background: `linear-gradient(135deg, ${a.color}, ${a.color}CC)` }}>
                <Bot size={22} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-[14.5px] font-semibold text-slate-900">{a.name}</h3>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <Badge className="badge-purple">Emplacement réservé</Badge>
                  {a.requires_human_validation && <Badge className="badge-warning">Validation humaine</Badge>}
                </div>
              </div>
            </div>
            <div className="px-5 pb-4">
              <p className="text-[12.5px] leading-relaxed text-slate-600">{a.description}</p>
              <div className="mt-3 space-y-1.5 rounded-lg bg-slate-50 p-3 text-[11.5px]">
                <p className="text-slate-600"><b className="text-slate-800">Modèle suggéré</b> · {a.suggested_model}</p>
                <p className="text-slate-600"><b className="text-slate-800">Stack</b> · {a.suggested_stack}</p>
              </div>
              {(a.capabilities || []).length > 0 && (
                <ul className="mt-3 space-y-1">
                  {a.capabilities.map((c) => (
                    <li key={c} className="flex gap-1.5 text-[11.5px] text-slate-600">
                      <Check size={12} className="mt-0.5 shrink-0 text-brand-600" /> {c}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="mt-auto flex items-center justify-between gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3">
              <span className="text-[11.5px] text-slate-500">{a.total_runs} exécution(s)</span>
              {canEdit ? (
                <Button size="sm" icon={PlayCircle} loading={launching === a.key} onClick={() => launch(a)}>
                  Lancer
                </Button>
              ) : (
                <span className="text-[11px] font-medium text-slate-400">Réservé au chef de projet</span>
              )}
            </div>
          </Card>
        ))}
        {!agents.length && <Card className="p-6 xl:col-span-3"><EmptyState icon={Bot} title="Aucun agent défini" /></Card>}
      </div>

      {/* -------------------------- Historique d’exécutions -------------------------- */}
      <Card>
        <CardHeader title="Exécutions sur ce projet" icon={GitBranch}
          subtitle={`${runs.length} exécution(s) journalisée(s)`}
          action={<Button variant="ghost" size="sm" icon={RefreshCw} onClick={refetchRuns} />} />
        {runs.length === 0 ? (
          <div className="p-6"><EmptyState icon={GitBranch} title="Aucune exécution" description="Lancez un agent pour créer la première trace." /></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr><th>Agent</th><th>Statut</th><th>Déclencheur</th><th>Étape</th><th>Heure</th><th>Résultat</th></tr>
              </thead>
              <tbody>
                {runs.slice(0, 15).map((r) => {
                  const st = RUN_STATUS[r.status] || RUN_STATUS.QUEUED
                  return (
                    <tr key={r.id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full" style={{ background: r.agent_color }} />
                          <span className="text-[12.5px] font-semibold text-slate-800">{r.agent_key}</span>
                        </div>
                      </td>
                      <td><Badge className={st.cls} dot={st.dot}>{st.label}</Badge></td>
                      <td className="text-[12px] text-slate-600">
                        {r.triggered_by_name || 'Système'}
                        <span className="ml-1.5 text-[10.5px] text-slate-400">
                          {{ MANUAL: 'manuel', PIPELINE: 'pipeline', SCHEDULED: 'planifié', RETRY: 'retry' }[r.trigger]}
                        </span>
                      </td>
                      <td className="max-w-[220px] truncate text-[12px] text-slate-600">{r.step || '—'}</td>
                      <td className="whitespace-nowrap text-[12px] text-slate-500">{formatDateTime(r.created_at)}</td>
                      <td>
                        {r.output_payload?._reserved && <Badge className="badge-purple">Réservé</Badge>}
                        {r.error_message && <span className="text-[11.5px] text-rose-600">{r.error_message}</span>}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

/* =========================================================================
 * Onglet — Validation humaine
 * ========================================================================= */
function ValidationTab({ project, onChanged, canEdit }) {
  const { data, refetch } = useQuery('/proposals/', { params: { project: project.id } })
  const proposals = data?.results ?? data ?? []
  const [open, setOpen] = useState(null)

  return (
    <div className="space-y-4">
      <Alert tone="info" title="Étape de validation humaine obligatoire">
        Conformément à l’architecture, aucune écriture dans Jira ou Trello n’est effectuée sans la
        confirmation du chef de projet : revue du plan proposé, des tâches et des assignations.
      </Alert>

      {proposals.length === 0 ? (
        <EmptyState icon={CheckCircle2} title="Aucune proposition"
          description="Lancez l’Agent 1 depuis l’onglet Copilote pour générer un plan de découpage à valider." />
      ) : (
        <div className="space-y-4">
          {proposals.map((p) => {
            const st = PROPOSAL_STATUS[p.status]
            return (
              <Card key={p.id}>
                <CardHeader
                  title={p.title}
                  subtitle={`v${p.version} · ${formatDateTime(p.created_at)}`}
                  icon={Wand2}
                  action={<Badge className={st.cls}>{st.label}</Badge>}
                />
                <div className="card-body">
                  <p className="text-[13.5px] leading-relaxed text-slate-700">{p.summary}</p>

                  <div className="mt-4 grid gap-3 sm:grid-cols-4">
                    <Metric label="Lots" value={p.lots_count} />
                    <Metric label="Tâches" value={p.tasks_count} />
                    <Metric label="Effort total" value={hours(p.total_estimate_hours)} />
                    <Metric label="Complétude" value={pct(Number(p.confidence) * 100, 0)} />
                  </div>

                  {(p.assignments || []).length > 0 && (
                    <div className="mt-4">
                      <p className="label">Assignations proposées (Agent 2)</p>
                      <div className="space-y-1.5">
                        {p.assignments.slice(0, 4).map((a) => (
                          <div key={a.id} className="flex items-center gap-3 rounded-lg bg-slate-50 px-3 py-2">
                            <Avatar name={a.candidate_detail?.full_name} color={a.candidate_detail?.avatar_color} size={26} />
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-[12px] font-medium text-slate-800">{a.candidate_detail?.full_name}</p>
                              <p className="truncate text-[11px] text-slate-500">{a.task_title}</p>
                            </div>
                            <Badge className={Number(a.match_score) > 0.8 ? 'badge-success' : 'badge-sky'}>
                              {Math.round(Number(a.match_score) * 100)} %
                            </Badge>
                            {a.accepted === true && <Badge className="badge-success"><Check size={11} /> Acceptée</Badge>}
                            {a.accepted === false && <Badge className="badge-danger"><X size={11} /> Refusée</Badge>}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
                    <div className="text-[12px] text-slate-500">
                      {p.validated_at
                        ? <>{p.status === 'REJECTED' ? 'Rejeté' : 'Validé'} par {p.validated_by_name} · {formatDateTime(p.validated_at)}</>
                        : 'En attente de décision'}
                    </div>
                    {p.status === 'PENDING' && canEdit
                      ? <Button icon={Eye} onClick={() => setOpen(p)}>Revoir et décider</Button>
                      : <Button variant="secondary" icon={Eye} onClick={() => setOpen(p)}>Consulter</Button>}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {open && <ValidationModal proposal={open} canEdit={canEdit} onClose={() => setOpen(null)} onDone={() => { setOpen(null); refetch(); onChanged() }} />}
    </div>
  )
}

function ValidationModal({ proposal, onClose, onDone, canEdit = true }) {
  const [decision, setDecision] = useState(null)
  const [createTasks, setCreateTasks] = useState(true)
  const [pushExternal, setPushExternal] = useState(false)
  const [reason, setReason] = useState('')
  const [assignments, setAssignments] = useState(
    Object.fromEntries((proposal.assignments || []).map((a) => [String(a.id), a.accepted !== false])),
  )
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const submit = async () => {
    if (!decision) return
    setSaving(true); setErr('')
    try {
      await api.post(`/proposals/${proposal.id}/validate/`, {
        decision, reason, create_tasks: createTasks, push_to_external: pushExternal,
        assignments: Object.fromEntries(Object.entries(assignments).map(([k, v]) => [k, v])),
      })
      onDone()
    } catch (e) { setErr(errorMessage(e)) }
    finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title={proposal.title}
      subtitle={`v${proposal.version} · ${proposal.project_name}`} size="xl" icon={CheckCircle2}
      footer={
        proposal.status !== 'PENDING' || !canEdit
          ? <Button variant="secondary" onClick={onClose}>Fermer</Button>
          : <>
              <Button variant="ghost" onClick={onClose}>Annuler</Button>
              <Button variant="danger" icon={XCircle} loading={saving && decision === 'REJECT'}
                onClick={() => { setDecision('REJECT'); submit() }}>Rejeter</Button>
              <Button variant="success" icon={Check} loading={saving && decision === 'APPROVE'}
                onClick={() => { setDecision('APPROVE'); submit() }}>Approuver le plan</Button>
            </>
      }>
      {!canEdit && proposal.status === 'PENDING' && (
        <Alert tone="info" className="mb-4">
          Consultation seule : la validation est réservée au chef de projet propriétaire ou à un administrateur.
        </Alert>
      )}
      {err && <Alert tone="error" className="mb-4">{err}</Alert>}

      <div className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-4">
          <Metric label="Lots" value={proposal.lots_count} />
          <Metric label="Tâches" value={proposal.tasks_count} />
          <Metric label="Effort total" value={hours(proposal.total_estimate_hours)} />
          <Metric label="Complétude" value={pct(Number(proposal.confidence) * 100, 0)} />
        </div>

        <div>
          <p className="label">Résumé de la proposition</p>
          <p className="rounded-lg bg-slate-50 p-3.5 text-[13px] leading-relaxed text-slate-700">{proposal.summary}</p>
        </div>

        {(proposal.assumptions || []).length > 0 && (
          <div>
            <p className="label">Hypothèses formulées</p>
            <ul className="space-y-1">
              {proposal.assumptions.map((a, i) => (
                <li key={i} className="flex gap-2 text-[12.5px] text-slate-600">
                  <Check size={13} className="mt-0.5 shrink-0 text-brand-600" /> {a}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <p className="label">Lots proposés ({proposal.lots_count})</p>
          <div className="space-y-1.5">
            {(proposal.lots_payload || []).map((l, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: l.color }} />
                <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium text-slate-800">{l.name}</span>
                <span className="shrink-0 text-[11.5px] text-slate-500">{hours(l.estimate_hours)}</span>
                <Badge className="badge-sky">{Math.round(Number(l.confidence || 0) * 100)} % confiance</Badge>
              </div>
            ))}
          </div>
        </div>

        <div>
          <p className="label">Tâches proposées ({proposal.tasks_count})</p>
          <div className="max-h-[280px] space-y-1.5 overflow-y-auto pr-1">
            {(proposal.tasks_payload || []).map((t, i) => (
              <div key={i} className="rounded-lg border border-slate-200 px-3 py-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[12.5px] font-semibold text-slate-800">
                      <span className="mr-1.5 font-mono text-[10.5px] text-slate-400">{t.ref}</span>{t.title}
                    </p>
                    <p className="mt-0.5 text-[11px] text-slate-500">{t.lot} · {t.sprint}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <Badge className={TASK_PRIORITY[t.priority]?.cls || 'badge-neutral'}>
                      {TASK_PRIORITY[t.priority]?.label || t.priority}
                    </Badge>
                    <span className="text-[11.5px] font-semibold text-slate-700">{hours(t.estimate_hours)}</span>
                  </div>
                </div>
                {(t.skills || []).length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {t.skills.map((s) => <span key={s} className="chip">{s}</span>)}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {(proposal.assignments || []).length > 0 && (
          <div>
            <p className="label">Assignations proposées — à arbitrer</p>
            <div className="space-y-2">
              {proposal.assignments.map((a) => {
                const on = assignments[String(a.id)]
                return (
                  <div key={a.id} className={cx('rounded-lg border px-3 py-2.5 transition',
                    on ? 'border-brand-300 bg-brand-50/40' : 'border-slate-200 bg-slate-50/50')}>
                    <div className="flex items-center gap-3">
                      <Avatar name={a.candidate_detail?.full_name} color={a.candidate_detail?.avatar_color} size={30} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[12.5px] font-semibold text-slate-800">{a.candidate_detail?.full_name}</p>
                        <p className="truncate text-[11px] text-slate-500">{a.task_title}</p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="text-[11.5px] font-bold text-brand-700">{Math.round(Number(a.match_score) * 100)} %</p>
                        <p className="text-[10px] text-slate-500">
                          {hours(a.workload_before_hours)} → {hours(a.workload_after_hours)}
                        </p>
                      </div>
                      <button onClick={() => setAssignments((s) => ({ ...s, [String(a.id)]: !on }))}
                        className={cx('btn btn-sm', on ? 'btn-primary' : 'btn-secondary')}>
                        {on ? <><Check size={13} /> Accepter</> : 'Refuser'}
                      </button>
                    </div>
                    {a.rationale && <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">{a.rationale}</p>}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {(proposal.risks_payload || []).length > 0 && (
          <div>
            <p className="label">Risques identifiés</p>
            <div className="space-y-1.5">
              {proposal.risks_payload.map((r, i) => (
                <div key={i} className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2">
                  <AlertTriangle size={14} className="shrink-0 text-amber-600" />
                  <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium text-amber-900">{r.title}</span>
                  <Badge className="badge-warning">{Math.round(r.score)}</Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
          <p className="text-[13px] font-semibold text-slate-800">Actions après validation</p>
          <div className="mt-2 space-y-1">
            <label className="flex cursor-pointer items-center gap-2.5 text-[12.5px] text-slate-700">
              <input type="checkbox" checked={createTasks} onChange={(e) => setCreateTasks(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
              Créer les tâches dans Cadria
            </label>
            <label className="flex cursor-pointer items-center gap-2.5 text-[12.5px] text-slate-700">
              <input type="checkbox" checked={pushExternal} onChange={(e) => setPushExternal(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
              Pousser vers {project_provider_label(proposal)} (Agent 2 — non branché, action journalisée uniquement)
            </label>
          </div>
        </div>
      </div>
    </Modal>
  )
}

function project_provider_label(p) {
  return 'Jira / Trello'
}

/* =========================================================================
 * Onglet — Risques
 * ========================================================================= */
function RisksTab({ project, onChanged }) {
  const { data, refetch } = useQuery('/risks/', { params: { project: project.id } })
  const alerts = data?.results ?? data ?? []
  const [ack, setAck] = useState(null)
  const [comment, setComment] = useState('')
  const [sending, setSending] = useState(false)

  const open = alerts.filter((a) => !a.acknowledged)
  const done = alerts.filter((a) => a.acknowledged)

  const acknowledge = async (a) => {
    setAck(a.id)
    try { await api.post(`/risks/${a.id}/acknowledge/`); await refetch(); await onChanged() }
    finally { setAck(null) }
  }

  const postComment = async () => {
    if (!comment.trim()) return
    setSending(true)
    try {
      await api.post('/comments/', { project: project.id, body: comment.trim() })
      setComment('')
      await onChanged()
    } finally { setSending(false) }
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-4">
        <Card className="p-4">
          <p className="text-[11.5px] text-slate-500">Score projet</p>
          <p className={cx('mt-1.5 text-[24px] font-bold leading-none',
            project.risk_score >= 55 ? 'text-rose-600' : project.risk_score >= 25 ? 'text-amber-600' : 'text-emerald-600')}>
            {Math.round(project.risk_score)}<span className="text-[13px] text-slate-400">/100</span>
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] text-slate-500">Alertes ouvertes</p>
          <p className="mt-1.5 text-[24px] font-bold leading-none text-slate-900">{open.length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] text-slate-500">Critiques</p>
          <p className="mt-1.5 text-[24px] font-bold leading-none text-rose-600">
            {alerts.filter((a) => a.severity === 'CRITICAL' && !a.acknowledged).length}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] text-slate-500">Traitées</p>
          <p className="mt-1.5 text-[24px] font-bold leading-none text-emerald-600">{done.length}</p>
        </Card>
      </div>

      {alerts.length === 0 ? (
        <EmptyState icon={ShieldAlert} title="Aucune alerte de risque"
          description="L’Agent 3 produira les scores et alertes une fois le runtime branché." />
      ) : (
        <div className="space-y-3">
          {[...open, ...done].map((a) => {
            const sev = { CRITICAL: 'border-rose-200 bg-rose-50/40', WARNING: 'border-amber-200 bg-amber-50/40', INFO: 'border-slate-200' }[a.severity]
            const dot = { CRITICAL: 'bg-rose-500', WARNING: 'bg-amber-500', INFO: 'bg-slate-400' }[a.severity]
            return (
              <Card key={a.id} className={cx('overflow-hidden', a.acknowledged && 'opacity-70')}>
                <div className={cx('border-l-4 px-5 py-4', sev,
                  a.severity === 'CRITICAL' ? 'border-l-rose-500' : a.severity === 'WARNING' ? 'border-l-amber-500' : 'border-l-slate-400')}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex min-w-0 items-start gap-3">
                      <span className={cx('mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full', dot)} />
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h3 className="text-[14.5px] font-semibold text-slate-900">{a.title}</h3>
                          <Badge className="badge-neutral">{RISK_CATEGORY[a.category] || a.category}</Badge>
                          {a.acknowledged && <Badge className="badge-success"><Check size={11} /> Traitée</Badge>}
                        </div>
                        <p className="mt-1 text-[13px] leading-relaxed text-slate-600">{a.message}</p>
                        {a.task_title && <p className="mt-1 text-[11.5px] text-slate-500">Tâche concernée : {a.task_title}</p>}
                      </div>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-2">
                      <Ring value={a.score} size={54} stroke={6}
                        color={a.severity === 'CRITICAL' ? '#E11D48' : a.severity === 'WARNING' ? '#F59E0B' : '#94A3B8'}>
                        <span className="text-[11px] font-bold">{Math.round(a.score)}</span>
                      </Ring>
                      {!a.acknowledged && (
                        <Button variant="secondary" size="sm" icon={Check}
                          loading={ack === a.id} onClick={() => acknowledge(a)}>Accuser réception</Button>
                      )}
                    </div>
                  </div>

                  {(a.factors || []).length > 0 && (
                    <div className="mt-3 space-y-1.5 rounded-lg bg-white/70 p-3">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Facteurs contributeurs</p>
                      {a.factors.map((f, i) => (
                        <div key={i} className="flex items-center gap-2">
                          <span className="w-[180px] shrink-0 truncate text-[11.5px] text-slate-600">{f.label}</span>
                          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                            <span className={cx('block h-full rounded-full', dot)} style={{ width: `${Number(f.weight) * 100}%` }} />
                          </span>
                          <span className="w-8 text-right text-[10.5px] font-semibold text-slate-500">{Math.round(f.weight * 100)}%</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {a.recommendation && (
                    <p className="mt-3 flex gap-2 rounded-lg bg-brand-50/70 p-3 text-[12px] leading-relaxed text-slate-700">
                      <Wand2 size={14} className="mt-0.5 shrink-0 text-brand-600" /> {a.recommendation}
                    </p>
                  )}

                  <p className="mt-2.5 text-[11px] text-slate-400">
                    Détectée {timeAgo(a.detected_at)}
                    {a.acknowledged_by && ` · accusée par ${a.acknowledged_by}`}
                  </p>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Commentaires — source de signaux faibles pour l’Agent 3 */}
      <Card>
        <CardHeader title="Commentaires d’équipe" icon={MessageSquare}
          subtitle="Les signaux faibles (« bloqué », « en attente de », « régression ») sont détectés automatiquement" />
        <div className="card-body">
          <div className="flex gap-2">
            <input value={comment} onChange={(e) => setComment(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && postComment()}
              placeholder="Partager un point de blocage, une dépendance, un avancement…"
              className="field flex-1" />
            <Button icon={MessageSquare} loading={sending} onClick={postComment} disabled={!comment.trim()}>Publier</Button>
          </div>
          <div className="mt-4 space-y-3">
            {(project.comments || []).map((c) => (
              <div key={c.id} className="flex gap-3">
                <Avatar name={c.author_name} color={c.author_color} size={30} />
                <div className="min-w-0 flex-1 rounded-lg bg-slate-50 px-3.5 py-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[12.5px] font-semibold text-slate-800">{c.author_name}</span>
                    <span className="text-[11px] text-slate-400">{timeAgo(c.created_at)}</span>
                    {c.weak_signal && <Badge className="badge-warning"><AlertTriangle size={10} /> Signal faible</Badge>}
                  </div>
                  <p className="mt-1 text-[12.5px] leading-relaxed text-slate-700">{c.body}</p>
                </div>
              </div>
            ))}
            {(project.comments || []).length === 0 && (
              <p className="py-4 text-center text-[12.5px] text-slate-500">Aucun commentaire pour l’instant.</p>
            )}
          </div>
        </div>
      </Card>
    </div>
  )
}

/* =========================================================================
 * Onglet — Connecteurs
 * ========================================================================= */
function IntegrationsTab({ project, onChanged, canEdit }) {
  const { data, refetch } = useQuery('/integrations/', { params: { project: project.id } })
  const list = data?.results ?? data ?? []
  const [testing, setTesting] = useState(null)

  const test = async (i) => {
    setTesting(i.id)
    try { await api.post(`/integrations/${i.id}/test/`); await refetch() }
    finally { setTesting(null) }
  }

  return (
    <div className="space-y-4">
      <Alert tone="info" title="Agent 2 — connecteurs non branchés">
        Les connecteurs Jira, Trello et GitHub sont configurés côté plateforme mais l’Agent 2 (intégration)
        n’est pas encore branché : les tests de connexion et les écritures sont journalisés sans effet externe.
      </Alert>

      {list.length === 0 ? (
        <EmptyState icon={Plug} title="Aucun connecteur configuré"
          description="Ajoutez un connecteur Jira ou Trello pour préparer la synchronisation." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {list.map((i) => {
            const st = {
              CONNECTED: { cls: 'badge-success', label: 'Connecté' },
              DISCONNECTED: { cls: 'badge-neutral', label: 'Déconnecté' },
              ERROR: { cls: 'badge-danger', label: 'Erreur' },
            }[i.status] || { cls: 'badge-neutral', label: i.status }
            return (
              <Card key={i.id}>
                <CardHeader
                  title={i.name}
                  subtitle={i.base_url || '—'}
                  icon={Plug}
                  action={<Badge className={st.cls} dot={i.status === 'CONNECTED' ? 'bg-emerald-500' : i.status === 'ERROR' ? 'bg-rose-500' : 'bg-slate-400'}>{st.label}</Badge>}
                />
                <div className="card-body">
                  <div className="grid grid-cols-2 gap-3 text-[12.5px]">
                    <InfoRow label="Fournisseur" value={i.provider === 'JIRA' ? 'Jira' : i.provider === 'TRELLO' ? 'Trello' : 'GitHub'} />
                    <InfoRow label="Projet / board" value={i.board_key || '—'} />
                    <InfoRow label="Espace" value={i.workspace || '—'} />
                    <InfoRow label="Intervalle" value={i.auto_sync ? `${i.sync_interval_minutes} min` : 'Manuel'} />
                    <InfoRow label="Dernière synchro" value={i.last_sync_at ? formatDateTime(i.last_sync_at) : 'Jamais'} />
                  </div>
                  {i.last_error && (
                    <Alert tone="warning" className="mt-3">{i.last_error}</Alert>
                  )}
                  <div className="mt-4 flex gap-2">
                    <Button variant="secondary" size="sm" icon={RefreshCw}
                      loading={testing === i.id} onClick={() => test(i)}>Tester la connexion</Button>
                    {i.base_url && (
                      <a href={i.base_url} target="_blank" rel="noreferrer" className="btn btn-secondary btn-sm">
                        <ExternalLink size={14} /> Ouvrir
                      </a>
                    )}
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}

function InfoRow({ label, value }) {
  return (
    <div>
      <p className="text-[10.5px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 truncate font-medium text-slate-800">{value}</p>
    </div>
  )
}

function Row({ label, value, tone = 'text-slate-800' }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-2 text-[12.5px] last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className={cx('font-semibold', tone)}>{value}</span>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-[10.5px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 text-[12.5px] font-medium text-slate-800">{children}</p>
    </div>
  )
}

/* =========================================================================
 * Onglet — Activité
 * ========================================================================= */
function ActivityTab({ project }) {
  const { data } = useQuery('/audit/', { params: { entity_type: 'Project', entity_id: project.id, scope: 'all', page_size: 50 } })
  const logs = data?.results ?? data ?? []

  return (
    <Card>
      <CardHeader title="Historique du projet" icon={GitBranch}
        subtitle="Journal d’audit : actions humaines et actions déclenchées par les agents" />
      {logs.length === 0 ? (
        <div className="p-6"><EmptyState icon={GitBranch} title="Aucune activité enregistrée" /></div>
      ) : (
        <div className="card-body pt-2">
          <ol className="relative space-y-4 border-l border-slate-200 pl-5">
            {logs.map((l) => (
              <li key={l.id} className="relative">
                <span className={cx('absolute -left-[26px] top-1 grid h-4 w-4 place-items-center rounded-full ring-4 ring-white',
                  l.severity === 'CRITICAL' ? 'bg-rose-500' : l.severity === 'WARNING' ? 'bg-amber-500'
                    : l.agent_key ? 'bg-violet-500' : 'bg-brand-600')} />
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[13px] font-semibold text-slate-800">{l.description || l.action_label}</span>
                  <Badge className="badge-neutral">{l.action_label}</Badge>
                  {l.agent_key && <Badge className="badge-purple"><Sparkles size={10} /> {l.agent_key}</Badge>}
                </div>
                <p className="mt-0.5 text-[11.5px] text-slate-500">
                  {l.actor_display} · {formatDateTime(l.created_at)}
                  {l.correlation_id && <span className="ml-2 font-mono text-[10.5px] text-slate-400">{l.correlation_id}</span>}
                </p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </Card>
  )
}

/* =========================================================================
 * Édition du projet
 * ========================================================================= */
function EditProject({ project, onSaved }) {
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ ...project })
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const navigate = useNavigate()

  const save = async () => {
    setSaving(true)
    try {
      await api.patch(`/projects/${project.id}/`, {
        name: form.name, summary: form.summary, brief: form.brief, status: form.status,
        health: form.health, methodology: form.methodology, start_date: form.start_date,
        target_end_date: form.target_end_date, budget: form.budget || null,
        currency: form.currency, tags: form.tags || [],
      })
      await onSaved(); setOpen(false)
    } finally { setSaving(false) }
  }

  const remove = async () => {
    await api.delete(`/projects/${project.id}/`)
    navigate('/app/projects', { replace: true })
  }

  return (
    <>
      <Button variant="secondary" icon={Edit3} onClick={() => setOpen(true)}>Modifier</Button>

      <Modal open={open} onClose={() => setOpen(false)} title="Modifier le projet" subtitle={project.reference}
        size="lg" icon={Edit3}
        footer={<>
          <Button variant="ghost" className="mr-auto text-rose-600 hover:bg-rose-50" icon={Trash2}
            onClick={() => setConfirmDelete(true)}>Supprimer</Button>
          <Button variant="secondary" onClick={() => setOpen(false)}>Annuler</Button>
          <Button loading={saving} onClick={save}>Enregistrer</Button>
        </>}>
        <div className="space-y-4">
          <Input label="Nom" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <Input label="Résumé" value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} />
          <Textarea label="Description" value={form.brief} onChange={(e) => setForm({ ...form, brief: e.target.value })} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Select label="Statut" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}
              options={Object.entries(PROJECT_STATUS).map(([k, v]) => ({ value: k, label: v.label }))} />
            <Select label="Santé" value={form.health} onChange={(e) => setForm({ ...form, health: e.target.value })}
              options={[{ value: 'GREEN', label: 'Sain' }, { value: 'AMBER', label: 'À surveiller' }, { value: 'RED', label: 'Critique' }]} />
            <Select label="Méthodologie" value={form.methodology} onChange={(e) => setForm({ ...form, methodology: e.target.value })}
              options={[{ value: 'SCRUM', label: 'Scrum' }, { value: 'KANBAN', label: 'Kanban' },
                        { value: 'WATERFALL', label: 'Cycle en V' }, { value: 'HYBRID', label: 'Hybride' }]} />
            <Input label="Budget" type="number" value={form.budget ?? ''}
              onChange={(e) => setForm({ ...form, budget: e.target.value })} />
            <Input label="Début" type="date" value={form.start_date || ''}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
            <Input label="Échéance" type="date" value={form.target_end_date || ''}
              onChange={(e) => setForm({ ...form, target_end_date: e.target.value })} />
          </div>
        </div>
      </Modal>

      <ConfirmDialog open={confirmDelete} onClose={() => setConfirmDelete(false)} onConfirm={remove}
        title="Supprimer ce projet ?"
        message={`« ${project.name} » et toutes ses tâches, lots et sprints seront définitivement supprimés. Cette action est irréversible.`}
        confirmLabel="Supprimer définitivement" />
    </>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-5 p-7">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-9 w-96" />
      <div className="grid gap-4 sm:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-72 w-full" />
    </div>
  )
}
