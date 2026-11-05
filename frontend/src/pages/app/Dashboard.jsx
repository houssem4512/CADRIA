import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, AlertTriangle, ArrowRight, Bell, CalendarClock, CheckCircle2, ChevronRight,
  Clock, FolderKanban, Gauge, ListChecks, Plus, RefreshCw, ShieldAlert, Sparkles,
  TrendingUp, Users, Zap,
} from 'lucide-react'
import { useQuery } from '../../lib/useApi'
import { useAuth } from '../../context/AuthContext'
import { useNotifications } from '../../context/NotificationContext'
import {
  Alert, Avatar, AvatarStack, Badge, Button, Card, CardHeader, EmptyState, Progress,
  Ring, Skeleton, SkeletonCard,
} from '../../components/ui'
import { BarChartView, DonutChart, LineChartView, TrendChart } from '../../components/charts'
import {
  PROJECT_STATUS, RISK_CATEGORY, TASK_PRIORITY, TASK_STATUS, cx, currency, daysUntil,
  formatDate, healthTone, hours, num, pct, riskTone, timeAgo,
} from '../../lib/format'

const STATUS_COLORS = {
  TODO: '#94A3B8', IN_PROGRESS: '#2563EB', REVIEW: '#8B5CF6', BLOCKED: '#E11D48', DONE: '#10B981',
}

export default function Dashboard() {
  const { user, canPilot } = useAuth()
  const { refresh: refreshNotifs } = useNotifications()
  const { data, loading, error, refetch } = useQuery('/analytics/dashboard/')
  const [refreshing, setRefreshing] = useState(false)

  const reload = async () => {
    setRefreshing(true)
    await refetch()
    refreshNotifs()
    setRefreshing(false)
  }

  useEffect(() => {
    const hour = new Date().getHours()
    if (hour < 12) return
    // salut personnalisé géré dans le rendu
  }, [])

  const kpis = data?.kpis || {}
  const greeting = (() => {
    const h = new Date().getHours()
    if (h < 6) return 'Bonne nuit'
    if (h < 12) return 'Bonjour'
    if (h < 18) return 'Bon après-midi'
    return 'Bonsoir'
  })()

  if (loading && !data) {
    return (
      <div className="space-y-5 p-5 sm:p-7">
        <Skeleton className="h-9 w-72" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-7">
        <Alert tone="error" title="Tableau de bord indisponible">{error}</Alert>
      </div>
    )
  }

  return (
    <div className="space-y-5 p-5 sm:p-7">
      {/* ------------------------------ En-tête ------------------------------ */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">
            {canPilot ? 'Espace chef de projet' : 'Espace membre d’équipe'}
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">
            {greeting}, {user?.first_name || (canPilot ? 'chef de projet' : 'à vous')} 👋
          </h1>
          <p className="mt-1 text-[14px] text-slate-500">
            {num(kpis.projects)} projet{kpis.projects > 1 ? 's' : ''} suivi{kpis.projects > 1 ? 's' : ''} ·{' '}
            {num(kpis.tasks_open)} tâche{kpis.tasks_open > 1 ? 's' : ''} ouverte{kpis.tasks_open > 1 ? 's' : ''} ·{' '}
            {kpis.open_alerts > 0
              ? <span className="font-semibold text-amber-600">{kpis.open_alerts} alerte{kpis.open_alerts > 1 ? 's' : ''} de risque</span>
              : 'aucune alerte ouverte'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" icon={refreshing ? RefreshCw : RefreshCw}
                  loading={refreshing} onClick={reload} className={refreshing ? '[&>svg]:animate-spin' : ''}>
            Actualiser
          </Button>
          {canPilot && (
            <Link to="/app/projects/new" className="btn btn-primary btn-md"><Plus size={15} /> Nouveau projet</Link>
          )}
        </div>
      </header>

      {/* --------------------------- Alertes urgentes --------------------------- */}
      {(kpis.critical_alerts > 0 || kpis.pending_validations > 0) && (
        <div className="grid gap-3 lg:grid-cols-2">
          {kpis.critical_alerts > 0 && (
            <Alert tone="error" title={`${kpis.critical_alerts} risque${kpis.critical_alerts > 1 ? 's' : ''} critique${kpis.critical_alerts > 1 ? 's' : ''} ouvert${kpis.critical_alerts > 1 ? 's' : ''}`}
              action={<Link to="/app/projects?health=RED" className="btn btn-sm bg-white/70 text-rose-700 hover:bg-white">Traiter <ArrowRight size={13} /></Link>}>
              L’Agent 3 a détecté des dérives nécessitant un arbitrage rapide.
            </Alert>
          )}
          {canPilot && kpis.pending_validations > 0 && (
            <Alert tone="warning" title={`${kpis.pending_validations} plan${kpis.pending_validations > 1 ? 's' : ''} en attente de validation`}
              action={<Link to="/app/agents" className="btn btn-sm bg-white/70 text-amber-700 hover:bg-white">Valider <ArrowRight size={13} /></Link>}>
              Aucune écriture dans Jira/Trello n’est possible avant votre confirmation.
            </Alert>
          )}
        </div>
      )}

      {/* -------------------------------- KPI -------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard icon={FolderKanban} label="Projets actifs" value={num(kpis.active_projects)}
          sub={`${num(kpis.projects)} au total`} tone="brand" progress={pct(kpis.projects ? (kpis.active_projects / kpis.projects) * 100 : 0)} />
        <KpiCard icon={CheckCircle2} label="Taux d’achèvement" value={pct(kpis.completion_rate, 1)}
          sub={`${num(kpis.tasks_done)} / ${num(kpis.tasks_total)} tâches`} tone="success"
          progress={kpis.completion_rate} />
        <KpiCard icon={AlertTriangle} label="Alertes ouvertes" value={num(kpis.open_alerts)}
          sub={`${num(kpis.critical_alerts)} critique${kpis.critical_alerts > 1 ? 's' : ''}`}
          tone={kpis.critical_alerts ? 'danger' : 'neutral'} />
        <KpiCard icon={Clock} label="Charge estimée" value={hours(kpis.estimated_hours)}
          sub={`${hours(kpis.spent_hours)} réalisées · écart ${kpis.effort_variance_pct > 0 ? '+' : ''}${num(kpis.effort_variance_pct, 1)} %`}
          tone="sky" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard icon={ListChecks} label="Tâches ouvertes" value={num(kpis.tasks_open)}
          sub={`${num(kpis.tasks_overdue)} en retard · ${num(kpis.tasks_blocked)} bloquée${kpis.tasks_blocked > 1 ? 's' : ''}`}
          tone={kpis.tasks_overdue ? 'warning' : 'neutral'} />
        <KpiCard icon={ShieldAlert} label="Projets à risque" value={num(kpis.at_risk)}
          sub="santé rouge" tone={kpis.at_risk ? 'danger' : 'success'} />
        <KpiCard icon={Users} label="Membres mobilisés" value={num(kpis.team_members)}
          sub="sur vos projets" tone="brand" />
        <KpiCard icon={Bell} label="Notifications" value={num(kpis.unread_notifications)}
          sub="non lues" tone="sky" to="/app/notifications" />
      </div>

      {/* ------------------------------- Graphes ------------------------------- */}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader title="Avancement du portefeuille" icon={TrendingUp}
            subtitle="Tâches créées et terminées par semaine (12 dernières semaines)"
            action={<Badge className="badge-brand">{num(kpis.tasks_total)} tâches</Badge>} />
          <div className="card-body pt-2">
            <LineChartView
              data={(data?.progress_timeline || []).map((w) => ({
                ...w,
                label: new Date(w.week).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }),
              }))}
              xKey="label"
              series={[
                { key: 'done', label: 'Terminées', color: '#1D4ED8' },
                { key: 'created', label: 'Créées', color: '#38BDF8' },
              ]}
              height={250}
            />
          </div>
        </Card>

        <Card>
          <CardHeader title="Répartition des tâches" icon={Gauge} subtitle="Par statut" />
          <div className="card-body pt-2">
            <DonutChart
              data={(data?.status_distribution || [])
                .filter((s) => s.count > 0)
                .map((s) => ({ label: s.label, value: s.count, color: STATUS_COLORS[s.key] }))}
              centerValue={num(kpis.tasks_total)}
              centerLabel="tâches"
            />
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader title="Priorités ouvertes" icon={Activity} subtitle="Tâches non terminées" />
          <div className="card-body pt-2">
            <BarChartView
              data={(data?.priority_distribution || []).map((p) => ({ ...p, label: p.label }))}
              xKey="label"
              series={[{ key: 'count', label: 'Tâches', color: '#2563EB' }]}
              layout="vertical" height={210}
            />
          </div>
        </Card>

        <Card>
          <CardHeader title="Risques par nature" icon={ShieldAlert} subtitle="Alertes non traitées" />
          <div className="card-body pt-2">
            {(data?.risk_by_category || []).map((r) => {
              const max = Math.max(1, ...(data.risk_by_category || []).map((x) => x.count))
              const tone = r.count >= max && r.count > 0 ? 'bg-rose-500' : r.count > 0 ? 'bg-amber-500' : 'bg-slate-300'
              return (
                <div key={r.key} className="mb-2.5 last:mb-0">
                  <div className="flex items-center justify-between text-[12.5px]">
                    <span className="text-slate-600">{RISK_CATEGORY[r.key] || r.label}</span>
                    <span className="font-semibold text-slate-800">{r.count}</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div className={cx('h-full rounded-full transition-all', tone)} style={{ width: `${(r.count / max) * 100}%` }} />
                  </div>
                </div>
              )
            })}
            {!(data?.risk_by_category || []).length && (
              <p className="py-6 text-center text-[13px] text-slate-500">Aucune alerte enregistrée.</p>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Santé du portefeuille" icon={ShieldAlert} subtitle="Projets par état de santé" />
          <div className="card-body pt-2">
            {(data?.health_distribution || []).map((h) => {
              const tone = healthTone(h.key)
              const total = (data.health_distribution || []).reduce((s, x) => s + x.count, 0) || 1
              return (
                <div key={h.key} className="flex items-center gap-3 border-b border-slate-100 py-3 last:border-0">
                  <Ring value={(h.count / total) * 100} size={46} stroke={5} color={tone.hex}>
                    <span className="text-[10px] font-bold">{h.count}</span>
                  </Ring>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-semibold text-slate-800">{h.label}</p>
                    <p className="text-[11.5px] text-slate-500">{pct((h.count / total) * 100, 1)} du portefeuille</p>
                  </div>
                </div>
              )
            })}
          </div>
        </Card>
      </div>

      {/* --------------------- Charge équipe + vélocité --------------------- */}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader title="Charge de l’équipe" icon={Users}
            subtitle="Utilisation de la capacité hebdomadaire"
            action={canPilot ? <Link to="/app/teams" className="link text-[12.5px]">Gérer</Link> : undefined} />
          <div className="card-body pt-2">
            {(data?.workload || []).length === 0 && (
              <EmptyState icon={Users} title="Aucun membre mobilisé" description="Ajoutez des membres à vos projets pour suivre leur charge." />
            )}
            {(data?.workload || []).map((m) => {
              const over = m.utilisation > 110
              const near = m.utilisation > 85 && !over
              return (
                <div key={m.id} className="flex items-center gap-3 border-b border-slate-100 py-2.5 last:border-0">
                  <Avatar name={m.name} color={m.color} size={34} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <p className="truncate text-[13px] font-semibold text-slate-800">{m.name}</p>
                      <span className={cx('text-[12px] font-bold',
                        over ? 'text-rose-600' : near ? 'text-amber-600' : 'text-emerald-600')}>
                        {pct(m.utilisation, 1)}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <Progress value={Math.min(100, m.utilisation)} size={5}
                        tone={over ? 'bg-rose-500' : near ? 'bg-amber-500' : 'bg-brand-600'} className="flex-1" />
                      <span className="shrink-0 text-[11px] text-slate-500">{hours(m.estimated)} / {hours(m.capacity)}</span>
                    </div>
                    {m.job_title && <p className="mt-0.5 truncate text-[11px] text-slate-400">{m.job_title}</p>}
                  </div>
                </div>
              )
            })}
          </div>
        </Card>

        <Card>
          <CardHeader title="Vélocité des sprints" icon={Zap}
            subtitle="Points engagés vs. points livrés"
            action={<Badge className="badge-sky">{(data?.velocity || []).length} sprints</Badge>} />
          <div className="card-body pt-2">
            {(data?.velocity || []).length === 0 ? (
              <EmptyState icon={Zap} title="Aucun sprint terminé"
                description="La vélocité s’affiche dès la clôture d’un premier sprint." />
            ) : (
              <BarChartView
                data={data.velocity}
                xKey="name"
                series={[
                  { key: 'planned', label: 'Engagés', color: '#93C5FD' },
                  { key: 'delivered', label: 'Livrés', color: '#1D4ED8' },
                ]}
                height={230}
              />
            )}
          </div>
        </Card>
      </div>

      {/* ------------------ Échéances + activité + notifications ------------------ */}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader title="Échéances à venir" icon={CalendarClock} subtitle="Tâches les plus proches"
            action={<Link to="/app/tasks" className="link text-[12.5px]">Tout voir</Link>} />
          <div className="card-body pt-2">
            {(data?.upcoming_deadlines || []).length === 0 && (
              <EmptyState icon={CalendarClock} title="Aucune échéance planifiée" />
            )}
            {(data?.upcoming_deadlines || []).map((t) => {
              const d = daysUntil(t.due_date)
              const late = d !== null && d < 0
              const soon = d !== null && d >= 0 && d <= 3
              return (
                <Link key={t.id} to={`/app/projects/${t.project_id}`}
                  className="flex items-start gap-3 rounded-lg border-b border-slate-100 py-2.5 transition last:border-0 hover:bg-slate-50">
                  <span className={cx('mt-0.5 h-2 w-2 shrink-0 rounded-full',
                    late ? 'bg-rose-500' : soon ? 'bg-amber-500' : 'bg-slate-300')} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium text-slate-800">{t.title}</p>
                    <p className="truncate text-[11.5px] text-slate-500">{t.project}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className={cx('text-[11.5px] font-semibold', late ? 'text-rose-600' : soon ? 'text-amber-600' : 'text-slate-500')}>
                      {late ? `${Math.abs(d)} j de retard` : d === 0 ? 'aujourd’hui' : `dans ${d} j`}
                    </p>
                    <p className="text-[10.5px] text-slate-400">{formatDate(t.due_date)}</p>
                  </div>
                </Link>
              )
            })}
          </div>
        </Card>

        <Card>
          <CardHeader title="Activité récente" icon={Activity} subtitle="Actions journalisées"
            action={canPilot ? <Link to="/app/history" className="link text-[12.5px]">Historique</Link> : undefined} />
          <div className="card-body pt-2">
            {(data?.activity || []).length === 0 && <EmptyState icon={Activity} title="Aucune activité" />}
            <ul className="space-y-3">
              {(data?.activity || []).slice(0, 7).map((a) => (
                <li key={a.id} className="flex gap-2.5">
                  <span className={cx('mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full',
                    a.severity === 'CRITICAL' ? 'bg-rose-500'
                      : a.severity === 'WARNING' ? 'bg-amber-500'
                      : a.agent ? 'bg-violet-500' : 'bg-brand-500')} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12.5px] text-slate-700">
                      {a.description || a.label}
                      {a.agent && <span className="ml-1.5 badge badge-purple">{a.agent}</span>}
                    </p>
                    <p className="text-[11px] text-slate-400">{timeAgo(a.created_at)}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </Card>

        <Card>
          <CardHeader title="Dernières notifications" icon={Bell}
            subtitle="Centre de notifications"
            action={<Link to="/app/notifications" className="link text-[12.5px]">Ouvrir</Link>} />
          <div className="card-body pt-2">
            {(data?.recent_notifications || []).length === 0 && <EmptyState icon={Bell} title="Rien de neuf" />}
            {(data?.recent_notifications || []).map((n) => (
              <Link key={n.id} to={n.link || '/app/notifications'}
                className={cx('flex gap-3 rounded-lg border-b border-slate-100 py-2.5 transition last:border-0 hover:bg-slate-50',
                  !n.read && 'bg-brand-50/30')}>
                <span className={cx('mt-1.5 h-2 w-2 shrink-0 rounded-full',
                  n.level === 'ERROR' ? 'bg-rose-500' : n.level === 'WARNING' ? 'bg-amber-500'
                    : n.level === 'AGENT' ? 'bg-violet-500' : n.level === 'SUCCESS' ? 'bg-emerald-500' : 'bg-sky-500')} />
                <div className="min-w-0 flex-1">
                  <p className={cx('truncate text-[12.5px]', n.read ? 'text-slate-600' : 'font-semibold text-slate-900')}>{n.title}</p>
                  <p className="line-clamp-2 text-[11.5px] text-slate-500">{n.message}</p>
                  <p className="mt-0.5 text-[10.5px] text-slate-400">{timeAgo(n.created_at)}</p>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}

function KpiCard({ icon: Icon, label, value, sub, tone = 'brand', progress, to }) {
  const tones = {
    brand: 'bg-brand-50 text-brand-600',
    sky: 'bg-sky-50 text-sky-600',
    success: 'bg-emerald-50 text-emerald-600',
    warning: 'bg-amber-50 text-amber-600',
    danger: 'bg-rose-50 text-rose-600',
    neutral: 'bg-slate-100 text-slate-600',
  }
  const bars = {
    brand: 'bg-brand-600', sky: 'bg-sky-500', success: 'bg-emerald-500',
    warning: 'bg-amber-500', danger: 'bg-rose-500', neutral: 'bg-slate-400',
  }
  const Inner = (
    <>
      <div className="flex items-start justify-between gap-3">
        <span className={cx('grid h-10 w-10 shrink-0 place-items-center rounded-xl', tones[tone])}>
          <Icon size={18} />
        </span>
        {to && <ChevronRight size={16} className="text-slate-300" />}
      </div>
      <p className="mt-3 text-[26px] font-bold leading-none tracking-tight text-slate-900">{value}</p>
      <p className="mt-1.5 text-[12.5px] font-medium text-slate-600">{label}</p>
      {sub && <p className="mt-0.5 text-[11.5px] text-slate-400">{sub}</p>}
      {progress !== undefined && (
        <Progress value={progress} tone={bars[tone]} size={4} className="mt-3" />
      )}
    </>
  )
  return to ? (
    <Link to={to} className="card card-hover p-5">{Inner}</Link>
  ) : (
    <Card className="p-5">{Inner}</Card>
  )
}
