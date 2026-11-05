import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, AlertTriangle, ArrowRight, BarChart3, Bell, Bot, CheckCircle2, ChevronRight,
  Download, FolderKanban, Gauge, History, Layers, Plug, RefreshCw, Server, Shield,
  ShieldAlert, Sparkles, TrendingUp, UserPlus, Users, Zap,
} from 'lucide-react'
import { useQuery } from '../../lib/useApi'
import {
  Alert, Avatar, Badge, Button, Card, CardHeader, Dot, EmptyState, Progress, Ring, Skeleton,
} from '../../components/ui'
import { BarChartView, DonutChart, LineChartView, RadarChartView, TrendChart } from '../../components/charts'
import {
  PROJECT_STATUS, ROLE_LABEL, RUN_STATUS, USER_STATUS, cx, compact, currency, formatDateTime,
  healthTone, hours, num, pct, timeAgo, toCSV,
} from '../../lib/format'

export default function AdminOverview() {
  const { data, loading, error, refetch } = useQuery('/analytics/admin/')
  const { data: insights } = useQuery('/analytics/insights/')
  const { data: monitor } = useQuery('/agents/monitor/')
  const [refreshing, setRefreshing] = useState(false)

  const reload = async () => { setRefreshing(true); await refetch(); setRefreshing(false) }

  if (loading && !data) {
    return (
      <div className="space-y-5 p-7">
        <Skeleton className="h-9 w-80" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
        </div>
      </div>
    )
  }
  if (error) return <div className="p-7"><Alert tone="error" title="Tableau de bord indisponible">{error}</Alert></div>

  const k = data.kpis || {}
  const gen = insights?.generation_quality || {}
  const assign = insights?.assignment_quality || {}
  const riskQ = insights?.risk_quality || {}

  const healthColor = k.platform_health >= 75 ? '#10B981' : k.platform_health >= 50 ? '#F59E0B' : '#E11D48'

  const qualityRadar = [
    { label: 'Génération', value: Math.max(0, 100 - (gen.avg_estimate_gap_agent_pct || 0)) },
    { label: 'Assignation', value: assign.load_balance_index || 0 },
    { label: 'Adoption plan', value: gen.acceptance_rate || 0 },
    { label: 'Risque couvert', value: riskQ.alerts_total ? Math.round((1 - (riskQ.alerts_open / riskQ.alerts_total)) * 100) : 100 },
    { label: 'Achèvement', value: k.completion_rate || 0 },
  ]

  return (
    <div className="space-y-5 p-5 sm:p-7">
      {/* ------------------------------ En-tête ------------------------------ */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Espace administration</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Vue d’ensemble de la plateforme</h1>
          <p className="mt-1 text-[14px] text-slate-500">
            {num(k.users)} utilisateur{num(k.users) > 1 ? 's' : ''} · {num(k.projects)} projet{num(k.projects) > 1 ? 's' : ''} ·{' '}
            {num(k.agent_runs_30d)} exécution{num(k.agent_runs_30d) > 1 ? 's' : ''} d’agent sur 30 jours
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" icon={Download} onClick={() => toCSV([
            ...Object.entries(k).map(([key, value]) => ({ indicateur: key, valeur: value })),
          ], 'cadria-kpi-admin.csv')}>Exporter</Button>
          <Button variant="secondary" icon={refreshing ? RefreshCw : RefreshCw}
            loading={refreshing} onClick={reload} className={refreshing ? '[&>svg]:animate-spin' : ''}>
            Actualiser
          </Button>
          <Link to="/admin/users" className="btn btn-primary btn-md"><UserPlus size={15} /> Gérer les comptes</Link>
        </div>
      </header>

      {/* ------------------------------ Santé plateforme ------------------------------ */}
      <div className="grid gap-4 xl:grid-cols-[280px_1fr]">
        <Card className="flex flex-col items-center justify-center p-6 text-center">
          <Ring value={k.platform_health} size={130} stroke={11} color={healthColor}>
            <span className="text-2xl font-bold">{k.platform_health}</span>
          </Ring>
          <p className="mt-3 text-[15px] font-semibold text-slate-900">Santé de la plateforme</p>
          <p className="mt-1 text-[12.5px] text-slate-500">
            {k.platform_health >= 75 ? 'Bonne — aucun point de vigilance majeur'
              : k.platform_health >= 50 ? 'À surveiller — quelques dérives détectées'
              : 'Dégradée — intervention recommandée'}
          </p>
          <div className="mt-4 w-full space-y-1.5 text-left">
            <HealthLine label="Projets à risque" value={num(k.projects_at_risk)} bad={k.projects_at_risk > 0} />
            <HealthLine label="Alertes ouvertes" value={num(k.open_alerts)} bad={k.open_alerts > 3} />
            <HealthLine label="Plans à valider" value={num(k.pending_validations)} bad={k.pending_validations > 0} />
            <HealthLine label="Comptes en attente" value={num(k.users_pending)} bad={k.users_pending > 0} />
          </div>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi icon={Users} label="Utilisateurs" value={num(k.users)}
            sub={`${num(k.users_active)} actifs · ${num(k.new_users_30d)} nouveaux`} tone="brand" to="/admin/users" />
          <Kpi icon={FolderKanban} label="Projets" value={num(k.projects)}
            sub={`${num(k.projects_active)} en cours`} tone="sky" to="/admin/projects" />
          <Kpi icon={Layers} label="Tâches" value={num(k.tasks)}
            sub={`${pct(k.completion_rate, 1)} achevées`} tone="success" />
          <Kpi icon={Bot} label="Exécutions agent" value={num(k.agent_runs)}
            sub={`${num(k.agent_runs_30d)} sur 30 jours`} tone="violet" to="/admin/agents" />
          <Kpi icon={ShieldAlert} label="Alertes ouvertes" value={num(k.open_alerts)}
            tone={k.open_alerts ? 'danger' : 'neutral'} />
          <Kpi icon={CheckCircle2} label="Plans à valider" value={num(k.pending_validations)}
            tone={k.pending_validations ? 'warning' : 'neutral'} />
          <Kpi icon={Users} label="Équipes" value={num(k.teams)} sub="équipes constituées" tone="sky" to="/app/teams" />
          <Kpi icon={Gauge} label="Charge totale" value={hours(k.estimated_hours)}
            sub={`${hours(k.spent_hours)} réalisées`} tone="brand" />
        </div>
      </div>

      {/* ------------------------------ Croissance ------------------------------ */}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Croissance de la plateforme" icon={TrendingUp}
            subtitle="Nouveaux utilisateurs et projets créés (6 derniers mois)"
            action={<Badge className="badge-brand">{num(k.users)} comptes</Badge>} />
          <div className="card-body pt-2">
            <BarChartView data={data.growth || []} xKey="month" height={250}
              series={[
                { key: 'users', label: 'Utilisateurs', color: '#1D4ED8' },
                { key: 'projects', label: 'Projets', color: '#38BDF8' },
              ]} />
          </div>
        </Card>

        <Card>
          <CardHeader title="Qualité du système" icon={RadarChartView ? Gauge : Gauge}
            subtitle="Métriques hétérogènes agrégées" />
          <div className="card-body pt-2">
            <RadarChartView data={qualityRadar} height={250} />
          </div>
        </Card>
      </div>

      {/* ------------------------------ Répartitions ------------------------------ */}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader title="Répartition des rôles" icon={Shield} subtitle="Permissions sur la plateforme" />
          <div className="card-body pt-2">
            <DonutChart
              data={(data.role_distribution || []).filter((r) => r.count > 0)
                .map((r, i) => ({ label: r.label, value: r.count, color: ['#E11D48', '#1D4ED8', '#0EA5E9', '#94A3B8'][i] }))}
              centerValue={num(k.users)} centerLabel="comptes" />
          </div>
        </Card>

        <Card>
          <CardHeader title="Statut des comptes" icon={Users} subtitle="Cycle de vie des utilisateurs" />
          <div className="card-body pt-2">
            {(data.user_status_distribution || []).map((s) => {
              const meta = USER_STATUS[s.key] || {}
              const total = (data.user_status_distribution || []).reduce((a, x) => a + x.count, 0) || 1
              return (
                <div key={s.key} className="flex items-center gap-3 border-b border-slate-100 py-3 last:border-0">
                  <span className={cx('h-2.5 w-2.5 shrink-0 rounded-full',
                    s.key === 'ACTIVE' ? 'bg-emerald-500' : s.key === 'PENDING' ? 'bg-amber-500' : 'bg-rose-500')} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-medium text-slate-700">{s.label}</p>
                    <Progress value={(s.count / total) * 100} size={4} className="mt-1.5"
                      tone={s.key === 'ACTIVE' ? 'bg-emerald-500' : s.key === 'PENDING' ? 'bg-amber-500' : 'bg-rose-500'} />
                  </div>
                  <span className="text-[13px] font-bold text-slate-800">{s.count}</span>
                </div>
              )
            })}
          </div>
        </Card>

        <Card>
          <CardHeader title="État des projets" icon={FolderKanban} subtitle="Répartition du portefeuille" />
          <div className="card-body pt-2">
            {(data.project_status_distribution || []).filter((s) => s.count > 0).map((s) => {
              const meta = PROJECT_STATUS[s.key] || {}
              const total = (data.project_status_distribution || []).reduce((a, x) => a + x.count, 0) || 1
              return (
                <div key={s.key} className="flex items-center gap-3 border-b border-slate-100 py-2.5 last:border-0">
                  <Badge className={meta.cls}>{meta.label}</Badge>
                  <Progress value={(s.count / total) * 100} size={5} className="flex-1" tone="bg-brand-600" />
                  <span className="w-6 text-right text-[13px] font-bold text-slate-800">{s.count}</span>
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      {/* ------------------------------ Agents + Insights ------------------------------ */}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Activité des agents" icon={Bot}
            subtitle="Exécutions journalisées sur 30 jours"
            action={<Link to="/admin/agents" className="link text-[12.5px]">Supervision</Link>} />
          <div className="card-body pt-2">
            {(data.agent_activity || []).length === 0 ? (
              <EmptyState icon={Bot} title="Aucune exécution sur la période" />
            ) : (
              <LineChartView
                data={(data.agent_activity || []).map((a) => ({
                  ...a,
                  label: new Date(a.day).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }),
                }))}
                xKey="label" height={230}
                series={[{ key: 'runs', label: 'Exécutions', color: '#2563EB' }]} />
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Insights qualité" icon={Gauge} subtitle="Métriques transverses des 3 agents" />
          <div className="card-body pt-2">
            <Section title="Qualité de génération">
              <Line label="Tâches issues d’un agent" value={num(gen.agent_tasks)} />
              <Line label="Écart moyen d’estimation" value={pct(gen.avg_estimate_gap_agent_pct, 1)}
                tone={(gen.avg_estimate_gap_agent_pct || 0) > 30 ? 'text-amber-600' : 'text-emerald-600'} />
              <Line label="Taux d’acceptation des plans" value={pct(gen.acceptance_rate, 1)} />
            </Section>
            <Section title="Qualité d’assignation">
              <Line label="Indice d’équilibrage" value={pct(assign.load_balance_index, 1)}
                tone={(assign.load_balance_index || 0) >= 70 ? 'text-emerald-600' : 'text-amber-600'} />
              <Line label="Utilisation moyenne" value={pct(assign.avg_utilisation_pct, 1)} />
              <Line label="Membres en surcharge" value={num(assign.overloaded_members)}
                tone={assign.overloaded_members ? 'text-rose-600' : 'text-emerald-600'} />
              <Line label="Suggestions acceptées" value={pct(assign.suggestions_accepted, 1)} />
            </Section>
            <Section title="Qualité de prédiction">
              <Line label="Alertes émises" value={num(riskQ.alerts_total)} />
              <Line label="Alertes traitées" value={num(riskQ.alerts_total - (riskQ.alerts_open || 0))} />
              <Line label="Risque moyen projet" value={`${num(riskQ.avg_project_risk, 1)}/100`} />
              <Line label="Signaux faibles détectés" value={num(insights?.comments?.weak_signals)} />
            </Section>
          </div>
        </Card>
      </div>

      {/* ------------------------------ Top risques + derniers comptes ------------------------------ */}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader title="Projets les plus à risque" icon={ShieldAlert}
            subtitle="Tri par score de risque décroissant"
            action={<Link to="/admin/projects" className="link text-[12.5px]">Tout voir</Link>} />
          <div className="card-body pt-2">
            {(data.top_risky_projects || []).length === 0 && <EmptyState icon={ShieldAlert} title="Aucun projet" />}
            {(data.top_risky_projects || []).map((p) => {
              const tone = healthTone(p.health)
              return (
                <Link key={p.id} to={`/app/projects/${p.id}`}
                  className="flex items-center gap-3 border-b border-slate-100 py-2.5 transition last:border-0 hover:bg-slate-50">
                  <span className={cx('h-2.5 w-2.5 shrink-0 rounded-full', tone.dot)} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-semibold text-slate-800">{p.name}</p>
                    <p className="truncate text-[11.5px] text-slate-500">
                      {p.reference} · {p.owner} · {p.tasks} tâche(s)
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className={cx('text-[13px] font-bold',
                      p.risk_score >= 55 ? 'text-rose-600' : p.risk_score >= 25 ? 'text-amber-600' : 'text-emerald-600')}>
                      {Math.round(p.risk_score)}
                    </p>
                    <p className="text-[10.5px] text-slate-400">{p.progress}% avancement</p>
                  </div>
                </Link>
              )
            })}
          </div>
        </Card>

        <Card>
          <CardHeader title="Derniers comptes créés" icon={UserPlus}
            subtitle="Inscriptions récentes"
            action={<Link to="/admin/users" className="link text-[12.5px]">Gérer</Link>} />
          <div className="card-body pt-2">
            {(data.recent_users || []).map((u) => {
              const role = ROLE_LABEL[u.role] || ROLE_LABEL.MEMBER
              return (
                <div key={u.id} className="flex items-center gap-3 border-b border-slate-100 py-2.5 last:border-0">
                  <Avatar name={u.name} color={u.color} size={34} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-semibold text-slate-800">{u.name}</p>
                    <p className="truncate text-[11.5px] text-slate-500">{u.email}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <Badge className={role.cls}>{role.label}</Badge>
                    <p className="mt-1 text-[10.5px] text-slate-400">{timeAgo(u.created_at)}</p>
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      {/* ------------------------------ Activité plateforme ------------------------------ */}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Activité de la plateforme" icon={Activity}
            subtitle="Actions journalisées et connexions (30 jours)"
            action={<Link to="/admin/audit" className="link text-[12.5px]">Journal complet</Link>} />
          <div className="card-body pt-2">
            {(data.activity_timeline || []).length === 0 ? (
              <EmptyState icon={Activity} title="Aucune activité enregistrée" />
            ) : (
              <BarChartView
                data={(data.activity_timeline || []).map((a) => ({
                  ...a,
                  label: new Date(a.date).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }),
                }))}
                xKey="label" height={220}
                series={[{ key: 'actions', label: 'Actions', color: '#2563EB' },
                        { key: 'logins', label: 'Connexions', color: '#38BDF8' }]} />
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Activité récente" icon={History}
            subtitle="20 dernières entrées du journal" />
          <div className="card-body pt-2">
            <ul className="space-y-2.5">
              {(data.activity || []).slice(0, 10).map((a) => (
                <li key={a.id} className="flex gap-2.5">
                  <span className={cx('mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full',
                    a.severity === 'CRITICAL' ? 'bg-rose-500'
                      : a.severity === 'WARNING' ? 'bg-amber-500'
                      : a.agent ? 'bg-violet-500' : 'bg-brand-500')} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12px] text-slate-700">{a.description || a.label}</p>
                    <p className="text-[10.5px] text-slate-400">
                      {a.actor} · {timeAgo(a.created_at)}
                      {a.agent && <span className="ml-1 font-semibold text-violet-600">{a.agent}</span>}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </div>

      {/* ------------------------------ Budget ------------------------------ */}
      <Card>
        <CardHeader title="Budget & effort consolidés" icon={BarChart3}
          subtitle="Vue financière de l’ensemble du portefeuille" />
        <div className="card-body grid gap-4 sm:grid-cols-4">
          <Big label="Budget total alloué" value={currency(k.budget_total)} tone="text-brand-700" />
          <Big label="Charge estimée" value={hours(k.estimated_hours)} />
          <Big label="Charge réalisée" value={hours(k.spent_hours)} />
          <Big label="Taux d’achèvement" value={pct(k.completion_rate, 1)}
            tone={k.completion_rate >= 50 ? 'text-emerald-600' : 'text-amber-600'} />
        </div>
      </Card>
    </div>
  )
}

function Kpi({ icon: Icon, label, value, sub, tone = 'brand', to }) {
  const tones = {
    brand: 'bg-brand-50 text-brand-600', sky: 'bg-sky-50 text-sky-600',
    success: 'bg-emerald-50 text-emerald-600', warning: 'bg-amber-50 text-amber-600',
    danger: 'bg-rose-50 text-rose-600', violet: 'bg-violet-50 text-violet-600',
    neutral: 'bg-slate-100 text-slate-600',
  }
  const inner = (
    <>
      <div className="flex items-start justify-between">
        <span className={cx('grid h-9 w-9 place-items-center rounded-lg', tones[tone])}><Icon size={16} /></span>
        {to && <ChevronRight size={15} className="text-slate-300" />}
      </div>
      <p className="mt-2.5 text-[22px] font-bold leading-none text-slate-900">{value}</p>
      <p className="mt-1 text-[12px] font-medium text-slate-600">{label}</p>
      {sub && <p className="mt-0.5 text-[11px] text-slate-400">{sub}</p>}
    </>
  )
  return to ? <Link to={to} className="card card-hover p-4">{inner}</Link> : <Card className="p-4">{inner}</Card>
}

function HealthLine({ label, value, bad }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-1.5 text-[12px]">
      <span className="text-slate-600">{label}</span>
      <span className={cx('font-bold', bad ? 'text-rose-600' : 'text-emerald-600')}>{value}</span>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="border-b border-slate-100 py-2.5 last:border-0">
      <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      <div className="space-y-0.5">{children}</div>
    </div>
  )
}

function Line({ label, value, tone = 'text-slate-800' }) {
  return (
    <div className="flex items-center justify-between text-[12px]">
      <span className="text-slate-500">{label}</span>
      <span className={cx('font-semibold', tone)}>{value}</span>
    </div>
  )
}

function Big({ label, value, tone = 'text-slate-900' }) {
  return (
    <div className="rounded-xl bg-slate-50 px-4 py-3.5">
      <p className="text-[11px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className={cx('mt-1 text-[20px] font-bold', tone)}>{value}</p>
    </div>
  )
}
