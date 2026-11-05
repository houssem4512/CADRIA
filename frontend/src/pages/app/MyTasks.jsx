import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CalendarClock, CheckCircle2, Clock, Download, Eye, Filter, Layers, ListChecks,
  PlayCircle, ShieldAlert, Sparkles, X,
} from 'lucide-react'
import { usePaged, useDebounced } from '../../lib/useApi'
import { useAuth } from '../../context/AuthContext'
import {
  Avatar, Badge, Button, Card, CardHeader, EmptyState, Progress, Ring, SearchInput, Select,
  TableSkeleton,
} from '../../components/ui'
import {
  TASK_PRIORITY, TASK_STATUS, TASK_TYPE, cx, daysUntil, formatDate, hours, num, pct,
  relativeDeadline, riskTone, toCSV,
} from '../../lib/format'

export default function MyTasks() {
  const { user } = useAuth()
  const [scope, setScope] = useState('mine')
  const [search, setSearch] = useState('')
  const debounced = useDebounced(search, 300)
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [risk, setRisk] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  const { results, count, loading, setPage, page, refetch } = usePaged('/tasks/', {
    page: 1,
    ...(scope === 'mine' ? { mine: 'true' } : {}),
    ...(debounced ? { search: debounced } : {}),
    ...(status ? { status } : {}),
    ...(risk === 'true' ? { at_risk: 'true' } : {}),
  })

  const filtered = useMemo(
    () => (priority ? results.filter((t) => t.priority === priority) : results),
    [results, priority],
  )

  const stats = useMemo(() => {
    const open = results.filter((t) => t.status !== 'DONE')
    return {
      total: results.length,
      open: open.length,
      done: results.filter((t) => t.status === 'DONE').length,
      overdue: open.filter((t) => t.is_overdue).length,
      blocked: open.filter((t) => t.blocked).length,
      hours: open.reduce((s, t) => s + Number(t.estimate_hours || 0), 0),
      atRisk: open.filter((t) => Number(t.risk_score) >= 50).length,
    }
  }, [results])

  const completion = stats.total ? Math.round((stats.done / stats.total) * 100) : 0

  return (
    <div className="space-y-5 p-5 sm:p-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Travail</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">
            {scope === 'mine' ? 'Mes tâches' : 'Toutes les tâches'}
          </h1>
          <p className="mt-1 text-[14px] text-slate-500">
            {num(stats.open)} ouverte{stats.open > 1 ? 's' : ''} · {hours(stats.hours)} de charge estimée
            {stats.overdue > 0 && <span className="ml-1.5 font-semibold text-rose-600">· {stats.overdue} en retard</span>}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" icon={Download} onClick={() => toCSV(filtered.map((t) => ({
            titre: t.title, projet: t.project, statut: t.status, priorite: t.priority,
            charge_h: t.estimate_hours, echeance: t.due_date, risque: t.risk_score,
          })), 'cadria-mes-taches.csv')}>Exporter</Button>
          <Button variant={scope === 'mine' ? 'secondary' : 'primary'} onClick={() => setScope(scope === 'mine' ? 'all' : 'mine')}>
            {scope === 'mine' ? 'Voir toutes les tâches' : 'Voir uniquement mes tâches'}
          </Button>
        </div>
      </header>

      {/* ------------------------------- Résumé ------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Card className="flex items-center gap-4 p-4">
          <Ring value={completion} size={52} stroke={6}>
            <span className="text-[11px] font-bold">{completion}%</span>
          </Ring>
          <div>
            <p className="text-[12.5px] font-semibold text-slate-800">Achèvement</p>
            <p className="text-[11.5px] text-slate-500">{stats.done} / {stats.total}</p>
          </div>
        </Card>
        <MiniStat icon={ListChecks} label="Ouvertes" value={num(stats.open)} tone="brand" />
        <MiniStat icon={Clock} label="Charge estimée" value={hours(stats.hours)} tone="sky" />
        <MiniStat icon={CalendarClock} label="En retard" value={num(stats.overdue)} tone={stats.overdue ? 'danger' : 'neutral'} />
        <MiniStat icon={ShieldAlert} label="À risque" value={num(stats.atRisk)} tone={stats.atRisk ? 'warning' : 'neutral'} />
      </div>

      {/* ------------------------------- Barre d’outils ------------------------------- */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput value={search} onChange={setSearch} placeholder="Rechercher une tâche…" className="min-w-[220px] flex-1" />
          <Button variant="secondary" icon={Filter} onClick={() => setShowFilters((s) => !s)}
            className={cx(showFilters && 'border-brand-400 bg-brand-50 text-brand-700')}>
            Filtres{(status || priority || risk) && <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />}
          </Button>
        </div>
        {showFilters && (
          <div className="mt-3 grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-4">
            <Select label="Statut" value={status} onChange={(e) => setStatus(e.target.value)}
              options={[{ value: '', label: 'Tous' }, ...Object.entries(TASK_STATUS).map(([k, v]) => ({ value: k, label: v.label }))]} />
            <Select label="Priorité" value={priority} onChange={(e) => setPriority(e.target.value)}
              options={[{ value: '', label: 'Toutes' }, ...Object.entries(TASK_PRIORITY).map(([k, v]) => ({ value: k, label: v.label }))]} />
            <Select label="Risque" value={risk} onChange={(e) => setRisk(e.target.value)}
              options={[{ value: '', label: 'Tous les niveaux' }, { value: 'true', label: 'Risque ≥ 50' }]} />
            <div className="flex items-end">
              <Button variant="ghost" icon={X} onClick={() => { setSearch(''); setStatus(''); setPriority(''); setRisk('') }}>
                Réinitialiser
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* ------------------------------- Liste ------------------------------- */}
      {loading ? (
        <Card><TableSkeleton rows={8} cols={6} /></Card>
      ) : filtered.length === 0 ? (
        <EmptyState icon={ListChecks}
          title={scope === 'mine' ? 'Aucune tâche assignée' : 'Aucune tâche'}
          description={search || status || priority
            ? 'Ajustez la recherche ou les filtres.'
            : scope === 'mine'
              ? 'Bonne nouvelle : vous n’avez aucune tâche en cours. Les nouvelles assignations apparaîtront ici.'
              : 'Aucune tâche n’a encore été créée sur vos projets.'} />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Tâche</th><th>Projet</th><th>Statut</th><th>Priorité</th>
                  <th>Charge</th><th>Risque</th><th>Échéance</th><th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((t) => {
                  const st = TASK_STATUS[t.status]
                  const pr = TASK_PRIORITY[t.priority]
                  const rk = riskTone(t.risk_score)
                  const dl = relativeDeadline(t.due_date)
                  return (
                    <tr key={t.id}>
                      <td>
                        <div className="flex items-start gap-2.5">
                          {t.created_by_agent && (
                            <span title="Proposée par l’Agent 1" className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded bg-violet-50 text-violet-600">
                              <Sparkles size={11} />
                            </span>
                          )}
                          <div className="min-w-0">
                            <p className="max-w-[280px] truncate text-[13px] font-semibold text-slate-800">{t.title}</p>
                            <div className="mt-1 flex flex-wrap items-center gap-1.5">
                              <Badge className={TASK_TYPE[t.task_type]?.cls}>{TASK_TYPE[t.task_type]?.label}</Badge>
                              {t.work_package_name && <span className="chip"><Layers size={10} /> {t.work_package_name}</span>}
                              {t.blocked && <Badge className="badge-danger">Bloquée</Badge>}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="max-w-[140px] truncate text-[12px] text-slate-600">{t.project_name || `#${t.project}`}</td>
                      <td><Badge className={st.cls} dot={st.hex}>{st.label}</Badge></td>
                      <td><Badge className={pr.cls}>{pr.label}</Badge></td>
                      <td className="whitespace-nowrap">
                        <span className="text-[12.5px] font-semibold text-slate-700">{hours(t.estimate_hours)}</span>
                        {t.spent_hours > 0 && (
                          <p className={cx('text-[10.5px]', t.effort_variance > 0 ? 'text-rose-500' : 'text-slate-400')}>
                            {hours(t.spent_hours)} réalisées
                          </p>
                        )}
                      </td>
                      <td><Badge className={rk.cls}>{Math.round(t.risk_score)}</Badge></td>
                      <td className="whitespace-nowrap">
                        <span className="text-[12px] text-slate-600">{formatDate(t.due_date, { day: '2-digit', month: 'short' })}</span>
                        {dl && <p className={cx('text-[10.5px]', dl.tone === 'danger' ? 'text-rose-500' : dl.tone === 'warning' ? 'text-amber-600' : 'text-slate-400')}>{dl.text}</p>}
                      </td>
                      <td className="text-right">
                        <Link to={`/app/projects/${t.project}`} className="btn btn-secondary btn-sm">
                          <Eye size={14} /> Projet
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {!loading && filtered.length > 0 && (
        <div className="flex items-center justify-between text-[12.5px] text-slate-500">
          <span>{filtered.length} tâche(s) affichée(s) sur {num(count)}</span>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Précédent</Button>
            <Button variant="secondary" size="sm" onClick={() => setPage(page + 1)}>Suivant</Button>
          </div>
        </div>
      )}
    </div>
  )
}

function MiniStat({ icon: Icon, label, value, tone = 'neutral' }) {
  const tones = {
    brand: 'bg-brand-50 text-brand-600', sky: 'bg-sky-50 text-sky-600',
    warning: 'bg-amber-50 text-amber-600', danger: 'bg-rose-50 text-rose-600',
    neutral: 'bg-slate-100 text-slate-600',
  }
  return (
    <Card className="p-4">
      <span className={cx('grid h-9 w-9 place-items-center rounded-lg', tones[tone])}><Icon size={16} /></span>
      <p className="mt-2.5 text-[20px] font-bold leading-none text-slate-900">{value}</p>
      <p className="mt-1 text-[11.5px] font-medium text-slate-500">{label}</p>
    </Card>
  )
}
