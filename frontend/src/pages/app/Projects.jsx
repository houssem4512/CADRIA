import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowUpDown, CalendarClock, Download, Eye, Filter, FolderKanban, Grid3x3, List,
  Plus, Search, Sparkles, Users, X,
} from 'lucide-react'
import { usePaged, useDebounced } from '../../lib/useApi'
import { useAuth } from '../../context/AuthContext'
import {
  Avatar, AvatarStack, Badge, Button, Card, EmptyState, Input, Progress, SearchInput,
  Select, TableSkeleton,
} from '../../components/ui'
import {
  PROJECT_STATUS, cx, currency, daysUntil, formatDate, healthTone, hours, num, pct, toCSV,
} from '../../lib/format'

const HEALTH_OPTIONS = [
  { value: '', label: 'Toutes les santés' },
  { value: 'GREEN', label: 'Sain' },
  { value: 'AMBER', label: 'À surveiller' },
  { value: 'RED', label: 'Critique' },
]

export default function Projects() {
  const { canPilot } = useAuth()
  const [params, setParams] = useSearchParams()
  const [view, setView] = useState('grid')
  const [search, setSearch] = useState('')
  const debounced = useDebounced(search, 300)
  const [showFilters, setShowFilters] = useState(false)
  const [sortBy, setSortBy] = useState('-created_at')

  const status = params.get('status') || ''
  const health = params.get('health') || ''

  const { results, count, page, pageSize, loading, setPage, refetch } = usePaged('/projects/', {
    page: Number(params.get('page')) || 1,
    ...(debounced ? { search: debounced } : {}),
    ...(status ? { status } : {}),
    ...(health ? { health } : {}),
    ordering: sortBy,
  })

  useEffect(() => { setParams((p) => { p.set('page', String(page)); return p }, { replace: true }) }, [page, setParams])

  const stats = useMemo(() => ({
    total: count,
    active: results.filter((p) => p.status === 'ACTIVE').length,
    atRisk: results.filter((p) => p.health === 'RED').length,
    avgProgress: results.length ? Math.round(results.reduce((s, p) => s + p.progress, 0) / results.length) : 0,
  }), [results, count])

  const exportCSV = () => toCSV(results.map((p) => ({
    reference: p.reference, projet: p.name, statut: p.status, sante: p.health,
    avancement: `${p.progress}%`, risques: p.open_risks, taches: p.task_count,
    budget: p.budget, charge_estimee_h: p.estimated_effort_hours,
    echeance: p.target_end_date, responsable: p.owner_name,
  })), 'cadria-projets.csv')

  return (
    <div className="space-y-5 p-5 sm:p-7">
      {/* ------------------------------ En-tête ------------------------------ */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Portefeuille</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Projets</h1>
          <p className="mt-1 text-[14px] text-slate-500">
            {num(count)} projet{count > 1 ? 's' : ''} · {stats.active} en cours ·{' '}
            {stats.atRisk > 0 ? <span className="font-semibold text-rose-600">{stats.atRisk} à risque</span> : 'aucun projet critique'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" icon={Download} onClick={exportCSV}>Exporter</Button>
          {canPilot && (
            <Link to="/app/projects/new" className="btn btn-primary btn-md"><Plus size={15} /> Nouveau projet</Link>
          )}
        </div>
      </header>

      {/* ------------------------------ Statuts ------------------------------ */}
      <div className="flex flex-wrap gap-2">
        {[
          ['', 'Tous', null],
          ['ACTIVE', 'En cours', stats.active],
          ['AT_RISK', 'À risque', stats.atRisk],
          ['PLANNED', 'Planifiés', null],
          ['COMPLETED', 'Terminés', null],
        ].map(([value, label, badge]) => (
          <button key={value || 'all'}
            onClick={() => { setParams((p) => { value ? p.set('status', value) : p.delete('status'); p.delete('page'); return p }) }}
            className={cx(
              'rounded-lg border px-3 py-1.5 text-[12.5px] font-medium transition',
              status === value
                ? 'border-brand-500 bg-brand-50 text-brand-700'
                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300',
            )}>
            {label}
            {badge !== null && badge !== undefined && (
              <span className={cx('ml-1.5 rounded-full px-1.5 py-0.5 text-[10.5px] font-bold',
                status === value ? 'bg-brand-200 text-brand-800' : 'bg-slate-100 text-slate-500')}>
                {badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ------------------------------ Barre d’outils ------------------------------ */}
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput value={search} onChange={setSearch} placeholder="Rechercher un projet, une référence…" className="min-w-[220px] flex-1" />
          <Button variant="secondary" icon={Filter} onClick={() => setShowFilters((s) => !s)}
            className={cx(showFilters && 'border-brand-400 bg-brand-50 text-brand-700')}>
            Filtres{(health || sortBy !== '-created_at') && <span className="h-1.5 w-1.5 rounded-full bg-brand-600" />}
          </Button>
          <div className="flex items-center gap-1 rounded-lg border border-slate-200 p-0.5">
            {[['grid', Grid3x3], ['table', List]].map(([v, Icon]) => (
              <button key={v} onClick={() => setView(v)} title={v === 'grid' ? 'Vue cartes' : 'Vue tableau'}
                className={cx('rounded-md p-1.5 transition', view === v ? 'bg-brand-600 text-white' : 'text-slate-500 hover:bg-slate-100')}>
                <Icon size={15} />
              </button>
            ))}
          </div>
        </div>

        {showFilters && (
          <div className="mt-3 grid gap-3 border-t border-slate-100 pt-3 sm:grid-cols-3">
            <Select label="Santé du projet" value={health} options={HEALTH_OPTIONS}
              onChange={(e) => setParams((p) => { e.target.value ? p.set('health', e.target.value) : p.delete('health'); return p })} />
            <Select label="Trier par" value={sortBy} onChange={(e) => setSortBy(e.target.value)} options={[
              { value: '-created_at', label: 'Plus récents' },
              { value: 'created_at', label: 'Plus anciens' },
              { value: 'name', label: 'Nom (A→Z)' },
              { value: '-progress', label: 'Avancement' },
              { value: '-risk_score', label: 'Risque (décroissant)' },
              { value: 'target_end_date', label: 'Échéance' },
            ]} />
            <div className="flex items-end">
              <Button variant="ghost" icon={X} onClick={() => {
                setSearch(''); setSortBy('-created_at'); setParams(new URLSearchParams())
              }}>Réinitialiser</Button>
            </div>
          </div>
        )}
      </Card>

      {/* ------------------------------ Contenu ------------------------------ */}
      {loading ? (
        <Card><TableSkeleton rows={6} cols={5} /></Card>
      ) : results.length === 0 ? (
        <EmptyState
          icon={FolderKanban}
          title={search || status || health ? 'Aucun projet ne correspond' : 'Aucun projet pour le moment'}
          description={search || status || health
            ? 'Ajustez la recherche ou réinitialisez les filtres pour élargir les résultats.'
            : canPilot
              ? 'Créez votre premier projet, puis lancez le copilote pour obtenir un découpage en lots et tâches.'
              : 'Vous n’êtes rattaché à aucun projet pour le moment. Consultez l’onglet « Mes tâches ».'}
          action={canPilot
            ? <Link to="/app/projects/new" className="btn btn-primary btn-md"><Plus size={15} /> Créer un projet</Link>
            : undefined}
        />
      ) : view === 'grid' ? (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
          {results.map((p) => <ProjectCard key={p.id} project={p} />)}
        </div>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Projet</th><th>Statut</th><th>Avancement</th><th>Charge</th>
                  <th>Risque</th><th>Échéance</th><th>Responsable</th><th className="text-right">Actions</th>
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
                        <div className="flex items-center gap-3">
                          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 font-mono text-[10px] font-bold text-brand-700">
                            {p.reference.replace('PRJ-', '')}
                          </span>
                          <div className="min-w-0">
                            <Link to={`/app/projects/${p.id}`} className="block max-w-[220px] truncate text-[13.5px] font-semibold text-slate-900 hover:text-brand-700">
                              {p.name}
                            </Link>
                            <p className="max-w-[220px] truncate text-[11.5px] text-slate-500">{p.summary}</p>
                          </div>
                        </div>
                      </td>
                      <td><Badge className={st.cls}>{st.label}</Badge></td>
                      <td className="w-[130px]">
                        <div className="flex items-center gap-2">
                          <Progress value={p.progress} tone={p.health === 'RED' ? 'bg-rose-500' : 'bg-brand-600'} size={5} className="flex-1" />
                          <span className="w-9 text-right text-[11.5px] font-semibold text-slate-600">{p.progress}%</span>
                        </div>
                        <p className="mt-1 text-[10.5px] text-slate-400">{p.done_count}/{p.task_count} tâches</p>
                      </td>
                      <td className="whitespace-nowrap">
                        <span className="text-[12.5px] font-semibold text-slate-700">{hours(p.estimated_effort_hours)}</span>
                        <p className="text-[10.5px] text-slate-400">{hours(p.spent_effort_hours)} réalisées</p>
                      </td>
                      <td>
                        <Badge className={tone.cls} dot={tone.dot}>{Math.round(p.risk_score)}</Badge>
                        {p.open_risks > 0 && <p className="mt-1 text-[10.5px] text-rose-500">{p.open_risks} alerte(s)</p>}
                      </td>
                      <td className="whitespace-nowrap">
                        <span className="text-[12.5px] text-slate-700">{formatDate(p.target_end_date)}</span>
                        {d !== null && (
                          <p className={cx('text-[10.5px]', d < 0 ? 'text-rose-500' : d <= 7 ? 'text-amber-600' : 'text-slate-400')}>
                            {d < 0 ? `${Math.abs(d)} j de retard` : `dans ${d} j`}
                          </p>
                        )}
                      </td>
                      <td><AvatarStack people={p.members_detail || []} size={26} max={3} /></td>
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
        </Card>
      )}

      {!loading && results.length > 0 && (
        <div className="flex items-center justify-between text-[12.5px] text-slate-500">
          <span>Page {page} · {results.length} sur {num(count)}</span>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Précédent</Button>
            <Button variant="secondary" size="sm" disabled={results.length < pageSize} onClick={() => setPage(page + 1)}>Suivant</Button>
          </div>
        </div>
      )}
    </div>
  )
}

function ProjectCard({ project: p }) {
  const st = PROJECT_STATUS[p.status] || PROJECT_STATUS.DRAFT
  const tone = healthTone(p.health)
  const d = daysUntil(p.target_end_date)
  const late = d !== null && d < 0

  return (
    <Card hover className="overflow-hidden">
      <div className="flex items-start justify-between gap-3 px-5 pt-4">
        <div className="flex min-w-0 items-start gap-3">
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-brand-600 to-sky-500 font-mono text-[11px] font-bold text-white">
            {p.reference.replace('PRJ-', '')}
          </span>
          <div className="min-w-0">
            <Link to={`/app/projects/${p.id}`} className="block truncate text-[15px] font-semibold text-slate-900 hover:text-brand-700">
              {p.name}
            </Link>
            <p className="truncate text-[12px] text-slate-500">{p.summary || '—'}</p>
          </div>
        </div>
        <Badge className={tone.cls} dot={tone.dot}>{tone.label}</Badge>
      </div>

      <div className="flex flex-wrap gap-1.5 px-5 pt-3">
        <Badge className={st.cls}>{st.label}</Badge>
        <Badge className="badge-neutral">{p.methodology === 'SCRUM' ? 'Scrum' : p.methodology === 'KANBAN' ? 'Kanban' : p.methodology}</Badge>
        {p.external_provider && (
          <Badge className="badge-sky">{p.external_provider === 'JIRA' ? 'Jira' : 'Trello'} · {p.external_key}</Badge>
        )}
        {(p.tags || []).slice(0, 2).map((t) => <span key={t} className="chip">{t}</span>)}
      </div>

      <div className="px-5 pt-4">
        <div className="flex items-center justify-between text-[12px]">
          <span className="text-slate-500">Avancement</span>
          <span className="font-semibold text-slate-800">{p.progress}% · {p.done_count}/{p.task_count} tâches</span>
        </div>
        <Progress value={p.progress} tone={p.health === 'RED' ? 'bg-rose-500' : p.health === 'AMBER' ? 'bg-amber-500' : 'bg-brand-600'} size={6} className="mt-1.5" />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2 border-t border-slate-100 px-5 py-3">
        <MiniStat label="Charge" value={hours(p.estimated_effort_hours)} />
        <MiniStat label="Budget" value={currency(p.budget, p.currency)} />
        <MiniStat label="Risque" value={`${Math.round(p.risk_score)}/100`}
          tone={p.risk_score >= 55 ? 'text-rose-600' : p.risk_score >= 25 ? 'text-amber-600' : 'text-emerald-600'} />
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/60 px-5 py-3">
        <div className="flex items-center gap-2">
          <Avatar name={p.owner_name} color={p.owner_color} size={26} />
          <span className="max-w-[110px] truncate text-[11.5px] font-medium text-slate-600">{p.owner_name}</span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          {p.open_risks > 0 && (
            <span className="flex items-center gap-1 font-semibold text-rose-600">
              <span className="h-1.5 w-1.5 rounded-full bg-rose-500" /> {p.open_risks}
            </span>
          )}
          <span className="flex items-center gap-1">
            <Users size={12} /> {p.member_count}
          </span>
          <span className={cx('flex items-center gap-1', late ? 'font-semibold text-rose-600' : '')}>
            <CalendarClock size={12} />
            {late ? `${Math.abs(d)} j retard` : d !== null ? `${d} j` : formatDate(p.target_end_date, { day: '2-digit', month: 'short' })}
          </span>
        </div>
      </div>
    </Card>
  )
}

function MiniStat({ label, value, tone = 'text-slate-800' }) {
  return (
    <div>
      <p className="text-[10.5px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className={cx('mt-0.5 text-[12.5px] font-bold', tone)}>{value}</p>
    </div>
  )
}
