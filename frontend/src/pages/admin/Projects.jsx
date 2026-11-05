import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CalendarClock, Download, Eye, Filter, FolderKanban, RefreshCw, Search, ShieldAlert, X,
} from 'lucide-react'
import { usePaged, useDebounced } from '../../lib/useApi'
import {
  Avatar, AvatarStack, Badge, Button, Card, EmptyState, Pagination, Progress, SearchInput,
  Select, TableSkeleton,
} from '../../components/ui'
import {
  PROJECT_STATUS, cx, currency, daysUntil, formatDate, healthTone, hours, num, pct, toCSV,
} from '../../lib/format'

export default function AdminProjects() {
  const [search, setSearch] = useState('')
  const debounced = useDebounced(search, 300)
  const [status, setStatus] = useState('')
  const [health, setHealth] = useState('')
  const [ordering, setOrdering] = useState('-created_at')
  const [showFilters, setShowFilters] = useState(false)

  const { results, count, page, pageSize, loading, setPage, refetch } = usePaged('/projects/', {
    ...(debounced ? { search: debounced } : {}),
    ...(status ? { status } : {}),
    ...(health ? { health } : {}),
    ordering,
  })

  const totals = useMemo(() => ({
    budget: results.reduce((s, p) => s + Number(p.budget || 0), 0),
    effort: results.reduce((s, p) => s + Number(p.estimated_effort_hours || 0), 0),
    spent: results.reduce((s, p) => s + Number(p.spent_effort_hours || 0), 0),
    tasks: results.reduce((s, p) => s + (p.task_count || 0), 0),
    atRisk: results.filter((p) => p.health === 'RED').length,
    alerts: results.reduce((s, p) => s + (p.open_risks || 0), 0),
    avgProgress: results.length ? Math.round(results.reduce((s, p) => s + p.progress, 0) / results.length) : 0,
  }), [results])

  return (
    <div className="space-y-5 p-5 sm:p-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Administration</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Supervision des projets</h1>
          <p className="mt-1 text-[14px] text-slate-500">
            {num(count)} projet{count > 1 ? 's' : ''} · {totals.atRisk > 0
              ? <span className="font-semibold text-rose-600">{totals.atRisk} à risque</span>
              : 'aucun projet critique'} · {totals.alerts} alerte(s) ouverte(s)
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" icon={Download} onClick={() => toCSV(results.map((p) => ({
            reference: p.reference, projet: p.name, responsable: p.owner_name, statut: p.status,
            sante: p.health, avancement: `${p.progress}%`, risque: p.risk_score, alertes: p.open_risks,
            taches: p.task_count, budget: p.budget, charge_estimee_h: p.estimated_effort_hours,
            charge_realisee_h: p.spent_effort_hours, echeance: p.target_end_date,
          })), 'cadria-supervision-projets.csv')}>Exporter</Button>
          <Button variant="secondary" icon={RefreshCw} onClick={refetch}>Actualiser</Button>
        </div>
      </header>

      {/* ------------------------------- Synthèse ------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Stat label="Projets" value={num(count)} sub={`${results.filter((p) => p.status === 'ACTIVE').length} en cours`} />
        <Stat label="Budget alloué" value={currency(totals.budget)} sub="sur cette page" tone="text-brand-700" />
        <Stat label="Charge estimée" value={hours(totals.effort)} sub={`${hours(totals.spent)} réalisées`} />
        <Stat label="Tâches" value={num(totals.tasks)} sub={`avancement moyen ${totals.avgProgress}%`} />
        <Stat label="Alertes ouvertes" value={num(totals.alerts)} tone={totals.alerts ? 'text-rose-600' : 'text-emerald-600'} />
      </div>

      {/* ------------------------------- Filtres ------------------------------- */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput value={search} onChange={setSearch}
            placeholder="Rechercher un projet, une référence, un responsable…" className="min-w-[240px] flex-1" />
          <Button variant="secondary" icon={Filter} onClick={() => setShowFilters((s) => !s)}
            className={cx(showFilters && 'border-brand-400 bg-brand-50 text-brand-700')}>
            Filtres{(status || health || ordering !== '-created_at') && <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />}
          </Button>
        </div>
        {showFilters && (
          <div className="mt-3 grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-4">
            <Select label="Statut" value={status} onChange={(e) => setStatus(e.target.value)}
              options={[{ value: '', label: 'Tous les statuts' },
                ...Object.entries(PROJECT_STATUS).map(([k, v]) => ({ value: k, label: v.label }))]} />
            <Select label="Santé" value={health} onChange={(e) => setHealth(e.target.value)}
              options={[{ value: '', label: 'Toutes' }, { value: 'GREEN', label: 'Sain' },
                        { value: 'AMBER', label: 'À surveiller' }, { value: 'RED', label: 'Critique' }]} />
            <Select label="Trier par" value={ordering} onChange={(e) => setOrdering(e.target.value)}
              options={[
                { value: '-created_at', label: 'Plus récents' },
                { value: '-risk_score', label: 'Risque décroissant' },
                { value: 'progress', label: 'Avancement croissant' },
                { value: 'target_end_date', label: 'Échéance' },
                { value: 'name', label: 'Nom (A→Z)' },
              ]} />
            <div className="flex items-end">
              <Button variant="ghost" icon={X} onClick={() => { setSearch(''); setStatus(''); setHealth(''); setOrdering('-created_at') }}>
                Réinitialiser
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* ------------------------------- Tableau ------------------------------- */}
      {loading ? (
        <Card><TableSkeleton rows={8} cols={7} /></Card>
      ) : results.length === 0 ? (
        <EmptyState icon={FolderKanban} title="Aucun projet"
          description="Aucun projet ne correspond aux critères appliqués." />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Projet</th><th>Responsable</th><th>Statut</th><th>Avancement</th>
                  <th>Risque</th><th>Budget</th><th>Échéance</th><th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {results.map((p) => {
                  const st = PROJECT_STATUS[p.status] || PROJECT_STATUS.DRAFT
                  const tone = healthTone(p.health)
                  const d = daysUntil(p.target_end_date)
                  return (
                    <tr key={p.id}>
                      <td>
                        <div className="flex items-center gap-2.5">
                          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-50 font-mono text-[10px] font-bold text-brand-700">
                            {p.reference.replace('PRJ-', '')}
                          </span>
                          <div className="min-w-0">
                            <Link to={`/app/projects/${p.id}`}
                              className="block max-w-[220px] truncate text-[13px] font-semibold text-slate-800 hover:text-brand-700">
                              {p.name}
                            </Link>
                            <p className="max-w-[220px] truncate text-[11px] text-slate-500">{p.summary}</p>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <Avatar name={p.owner_name} color={p.owner_color} size={26} />
                          <span className="max-w-[110px] truncate text-[12px] text-slate-600">{p.owner_name}</span>
                        </div>
                      </td>
                      <td>
                        <Badge className={st.cls}>{st.label}</Badge>
                        {p.open_risks > 0 && (
                          <p className="mt-1 text-[10.5px] text-rose-500">{p.open_risks} alerte(s)</p>
                        )}
                      </td>
                      <td className="w-[130px]">
                        <div className="flex items-center gap-2">
                          <Progress value={p.progress} size={5} className="flex-1"
                            tone={p.health === 'RED' ? 'bg-rose-500' : p.health === 'AMBER' ? 'bg-amber-500' : 'bg-brand-600'} />
                          <span className="w-9 text-right text-[11px] font-bold text-slate-600">{p.progress}%</span>
                        </div>
                        <p className="mt-1 text-[10.5px] text-slate-400">{p.done_count}/{p.task_count} tâches</p>
                      </td>
                      <td>
                        <Badge className={tone.cls} dot={tone.dot}>{Math.round(p.risk_score)}</Badge>
                        <p className="mt-1 text-[10.5px] text-slate-400">{tone.label}</p>
                      </td>
                      <td className="whitespace-nowrap">
                        <span className="text-[12px] font-semibold text-slate-700">{currency(p.budget, p.currency)}</span>
                        <p className="text-[10.5px] text-slate-400">{pct(p.budget_consumed, 0)} consommé</p>
                      </td>
                      <td className="whitespace-nowrap">
                        <span className="text-[12px] text-slate-600">{formatDate(p.target_end_date)}</span>
                        {d !== null && (
                          <p className={cx('text-[10.5px]', d < 0 ? 'text-rose-500' : d <= 7 ? 'text-amber-600' : 'text-slate-400')}>
                            {d < 0 ? `${Math.abs(d)} j de retard` : `dans ${d} j`}
                          </p>
                        )}
                      </td>
                      <td className="text-right">
                        <Link to={`/app/projects/${p.id}`} className="btn btn-secondary btn-sm">
                          <Eye size={14} /> Ouvrir
                        </Link>
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
    </div>
  )
}

function Stat({ label, value, sub, tone = 'text-slate-900' }) {
  return (
    <Card className="p-4">
      <p className="text-[11.5px] font-medium text-slate-500">{label}</p>
      <p className={cx('mt-2 text-[20px] font-bold leading-none', tone)}>{value}</p>
      {sub && <p className="mt-1 text-[11px] text-slate-400">{sub}</p>}
    </Card>
  )
}
