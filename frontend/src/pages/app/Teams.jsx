import { useMemo, useState } from 'react'
import {
  Briefcase, Check, Download, Gauge, Mail, Phone, Plus, RefreshCw, Search, ShieldAlert,
  Sparkles, UserPlus, Users, X,
} from 'lucide-react'
import api, { errorMessage, fieldErrors } from '../../lib/api'
import { useQuery } from '../../lib/useApi'
import {
  Alert, Avatar, AvatarStack, Badge, Button, Card, CardHeader, EmptyState, Input, Modal,
  Progress, Ring, SearchInput, Select, Skeleton, Textarea,
} from '../../components/ui'
import { BarChartView, RadarChartView } from '../../components/charts'
import { ROLE_LABEL, USER_STATUS, cx, hours, num, pct, timeAgo, toCSV } from '../../lib/format'

const SKILL_CATEGORIES = {
  TECH: 'Technique', DATA: 'Data / IA', DESIGN: 'Design', FUNC: 'Fonctionnel', MGMT: 'Management',
}

export default function Teams() {
  const [tab, setTab] = useState('teams')
  const { data: teamsData, loading: lTeams, refetch: rTeams } = useQuery('/teams/', { params: { page_size: 50 } })
  const { data: membersData, loading: lMembers, refetch: rMembers } = useQuery('/members/', { params: { page_size: 60 } })
  const { data: skillsData } = useQuery('/skills/', { params: { page_size: 100 } })
  const [search, setSearch] = useState('')
  const [teamOpen, setTeamOpen] = useState(false)
  const [editingTeam, setEditingTeam] = useState(null)
  const [member, setMember] = useState(null)

  const teams = teamsData?.results ?? teamsData ?? []
  const members = membersData?.results ?? membersData ?? []
  const skills = skillsData?.results ?? skillsData ?? []

  const q = search.toLowerCase()
  const filteredMembers = useMemo(() => members.filter((m) =>
    !q || `${m.full_name} ${m.email} ${m.job_title} ${(m.team_names || []).join(' ')}`.toLowerCase().includes(q)
  ), [members, q])

  const stats = useMemo(() => {
    const caps = members.filter((m) => Number(m.weekly_capacity_hours) > 0)
    const load = caps.reduce((s, m) => s + Number(m.workload_hours || 0), 0)
    const cap = caps.reduce((s, m) => s + Number(m.weekly_capacity_hours || 0), 0)
    return {
      teams: teams.length,
      members: members.length,
      load, cap,
      avg: cap ? (load / cap) * 100 : 0,
      over: members.filter((m) => Number(m.utilisation) > 110).length,
      free: members.filter((m) => Number(m.utilisation) < 50).length,
    }
  }, [teams, members])

  return (
    <div className="space-y-5 p-5 sm:p-7">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Ressources</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Équipes & compétences</h1>
          <p className="mt-1 text-[14px] text-slate-500">
            {num(stats.teams)} équipe{stats.teams > 1 ? 's' : ''} · {num(stats.members)} membre{stats.members > 1 ? 's' : ''} ·{' '}
            charge moyenne {pct(stats.avg, 0)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" icon={Download} onClick={() => toCSV(members.map((m) => ({
            nom: m.full_name, email: m.email, poste: m.job_title, role: m.role,
            capacite_h: m.weekly_capacity_hours, charge_h: m.workload_hours,
            utilisation: `${m.utilisation}%`, equipes: (m.team_names || []).join(' | '),
          })), 'cadria-membres.csv')}>Exporter</Button>
          <Button icon={Plus} onClick={() => { setEditingTeam(null); setTeamOpen(true) }}>Nouvelle équipe</Button>
        </div>
      </header>

      {/* ------------------------------- KPI ------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Équipes</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-slate-900">{num(stats.teams)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Membres</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-slate-900">{num(stats.members)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Charge planifiée</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-slate-900">{hours(stats.load)}</p>
          <p className="mt-1 text-[11.5px] text-slate-400">sur {hours(stats.cap)} de capacité</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">En surcharge</p>
          <p className={cx('mt-2 text-[24px] font-bold leading-none', stats.over ? 'text-rose-600' : 'text-emerald-600')}>
            {num(stats.over)}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-slate-500">Disponibles</p>
          <p className="mt-2 text-[24px] font-bold leading-none text-sky-600">{num(stats.free)}</p>
          <p className="mt-1 text-[11.5px] text-slate-400">sous 50 % de charge</p>
        </Card>
      </div>

      {/* ------------------------------- Onglets ------------------------------- */}
      <div className="flex gap-1 border-b border-slate-200">
        {[['teams', 'Équipes', teams.length], ['members', 'Membres', members.length]].map(([k, l, c]) => (
          <button key={k} onClick={() => setTab(k)}
            className={cx('relative px-3.5 py-2.5 text-[13px] font-medium transition',
              tab === k ? 'text-brand-700' : 'text-slate-500 hover:text-slate-800')}>
            {l}
            <span className={cx('ml-1.5 rounded-full px-1.5 py-0.5 text-[10.5px] font-semibold',
              tab === k ? 'bg-brand-100 text-brand-700' : 'bg-slate-100 text-slate-500')}>{c}</span>
            {tab === k && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand-600" />}
          </button>
        ))}
      </div>

      {tab === 'teams' ? (
        lTeams ? <Skeleton className="h-64 w-full rounded-xl" />
        : teams.length === 0 ? (
          <EmptyState icon={Users} title="Aucune équipe"
            description="Créez une équipe pour regrouper les membres et suivre leur charge."
            action={<Button icon={Plus} onClick={() => { setEditingTeam(null); setTeamOpen(true) }}>Créer une équipe</Button>} />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            {teams.map((t) => <TeamCard key={t.id} team={t} onEdit={() => { setEditingTeam(t); setTeamOpen(true) }} />)}
          </div>
        )
      ) : (
        <>
          <Card className="p-3">
            <SearchInput value={search} onChange={setSearch} placeholder="Rechercher un membre, un poste, une équipe…" />
          </Card>
          {lMembers ? <Skeleton className="h-72 w-full rounded-xl" />
          : filteredMembers.length === 0 ? (
            <EmptyState icon={Search} title="Aucun membre trouvé" description="Modifiez votre recherche." />
          ) : (
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Membre</th><th>Rôle</th><th>Équipes</th><th>Tâches</th>
                      <th>Utilisation</th><th>Compétences</th><th className="text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredMembers.map((m) => {
                      const role = ROLE_LABEL[m.role] || ROLE_LABEL.MEMBER
                      const util = Number(m.utilisation) || 0
                      return (
                        <tr key={m.id}>
                          <td>
                            <div className="flex items-center gap-2.5">
                              <Avatar name={m.full_name} color={m.avatar_color} size={34} />
                              <div className="min-w-0">
                                <p className="truncate text-[13px] font-semibold text-slate-800">{m.full_name}</p>
                                <p className="truncate text-[11.5px] text-slate-500">{m.job_title || m.email}</p>
                              </div>
                            </div>
                          </td>
                          <td><Badge className={role.cls}>{role.label}</Badge></td>
                          <td>
                            <div className="flex flex-wrap gap-1">
                              {(m.team_names || []).slice(0, 2).map((n) => <span key={n} className="chip">{n}</span>)}
                              {(m.team_names || []).length === 0 && <span className="text-[11.5px] text-slate-400">—</span>}
                            </div>
                          </td>
                          <td className="text-[12.5px] font-semibold text-slate-700">{num(m.active_tasks)}</td>
                          <td className="w-[150px]">
                            <div className="flex items-center gap-2">
                              <Progress value={Math.min(100, util)} size={5} className="flex-1"
                                tone={util > 110 ? 'bg-rose-500' : util > 85 ? 'bg-amber-500' : 'bg-brand-600'} />
                              <span className={cx('w-10 text-right text-[11px] font-bold',
                                util > 110 ? 'text-rose-600' : util > 85 ? 'text-amber-600' : 'text-emerald-600')}>
                                {Math.round(util)}%
                              </span>
                            </div>
                          </td>
                          <td>
                            <span className="text-[11.5px] text-slate-500">
                              {num(m.workload_hours, 1)} h / {num(m.weekly_capacity_hours, 0)} h
                            </span>
                          </td>
                          <td className="text-right">
                            <Button variant="secondary" size="sm" onClick={() => setMember(m)}>Détails</Button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}

      {teamOpen && (
        <TeamModal team={editingTeam} members={members}
          onClose={() => { setTeamOpen(false); setEditingTeam(null) }}
          onSaved={() => { setTeamOpen(false); setEditingTeam(null); rTeams() }} />
      )}
      {member && <MemberModal member={member} skills={skills} onClose={() => setMember(null)} />}
    </div>
  )
}

function TeamCard({ team, onEdit }) {
  const load = (team.members || []).reduce((s, m) => s + Number(m.workload_hours || 0), 0)
  const cap = (team.members || []).reduce((s, m) => s + Number(m.weekly_capacity_hours || 0), 0)
  const util = cap ? (load / cap) * 100 : 0

  return (
    <Card hover className="flex flex-col">
      <div className="flex items-start gap-3.5 p-5">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-white shadow-sm"
          style={{ background: `linear-gradient(135deg, ${team.color || '#2563EB'}, ${team.color || '#2563EB'}CC)` }}>
          <Users size={19} />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[15px] font-semibold text-slate-900">{team.name}</h3>
          <p className="mt-0.5 line-clamp-2 text-[12px] text-slate-500">{team.description || 'Aucune description'}</p>
        </div>
        <Button variant="ghost" size="sm" onClick={onEdit}>Modifier</Button>
      </div>

      <div className="px-5">
        <div className="flex items-center justify-between text-[12px]">
          <span className="text-slate-500">Utilisation</span>
          <span className={cx('font-bold', util > 110 ? 'text-rose-600' : util > 85 ? 'text-amber-600' : 'text-emerald-600')}>
            {pct(util, 0)}
          </span>
        </div>
        <Progress value={Math.min(100, util)} size={6} className="mt-1.5"
          tone={util > 110 ? 'bg-rose-500' : util > 85 ? 'bg-amber-500' : 'bg-brand-600'} />
        <p className="mt-1.5 text-[11px] text-slate-400">{hours(load)} planifiées sur {hours(cap)} de capacité</p>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/60 px-5 py-3">
        <AvatarStack people={team.members || []} size={28} max={5} />
        <span className="text-[11.5px] text-slate-500">{team.member_count} membre(s)</span>
      </div>
    </Card>
  )
}

function TeamModal({ team, members, onClose, onSaved }) {
  const [form, setForm] = useState({
    name: team?.name || '', description: team?.description || '',
    color: team?.color || '#2563EB', member_ids: (team?.members || []).map((m) => m.id),
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const COLORS = ['#2563EB', '#0EA5E9', '#1D4ED8', '#0284C7', '#3B82F6', '#0369A1', '#1E40AF', '#38BDF8']

  const save = async () => {
    setSaving(true); setErrors({})
    try {
      if (team) await api.patch(`/teams/${team.id}/`, form)
      else await api.post('/teams/', form)
      onSaved()
    } catch (e) { setErrors(fieldErrors(e)) }
    finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title={team ? 'Modifier l’équipe' : 'Nouvelle équipe'}
      subtitle={team?.name} size="lg" icon={Users}
      footer={<><Button variant="secondary" onClick={onClose}>Annuler</Button>
        <Button loading={saving} onClick={save}>{team ? 'Enregistrer' : 'Créer l’équipe'}</Button></>}>
      <div className="space-y-4">
        <Input label="Nom de l’équipe" required value={form.name} error={errors.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <Textarea label="Description" value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })} />
        <div>
          <label className="label">Couleur</label>
          <div className="flex flex-wrap gap-2">
            {COLORS.map((c) => (
              <button key={c} onClick={() => setForm({ ...form, color: c })}
                className={cx('h-8 w-8 rounded-lg transition', form.color === c && 'ring-2 ring-offset-2 ring-slate-400')}
                style={{ background: c }} />
            ))}
          </div>
        </div>
        <div>
          <label className="label">Membres ({form.member_ids.length})</label>
          <div className="max-h-[280px] space-y-1.5 overflow-y-auto pr-1">
            {members.map((m) => {
              const on = form.member_ids.includes(m.id)
              return (
                <button key={m.id} onClick={() => setForm({
                  ...form,
                  member_ids: on ? form.member_ids.filter((x) => x !== m.id) : [...form.member_ids, m.id],
                })}
                  className={cx('flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition',
                    on ? 'border-brand-400 bg-brand-50/60' : 'border-slate-200 hover:border-slate-300')}>
                  <Avatar name={m.full_name} color={m.avatar_color} size={30} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[12.5px] font-semibold text-slate-800">{m.full_name}</p>
                    <p className="truncate text-[11px] text-slate-500">{m.job_title || m.email}</p>
                  </div>
                  <span className="shrink-0 text-[11px] text-slate-500">{m.utilisation}%</span>
                  {on && <Check size={15} className="shrink-0 text-brand-600" />}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </Modal>
  )
}

function MemberModal({ member, onClose }) {
  const role = ROLE_LABEL[member.role] || ROLE_LABEL.MEMBER
  const util = Number(member.utilisation) || 0
  const load = Number(member.workload_hours) || 0
  const cap = Number(member.weekly_capacity_hours) || 0

  return (
    <Modal open onClose={onClose} title={member.full_name} subtitle={member.job_title || member.email}
      size="lg" icon={Briefcase}>
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <Avatar name={member.full_name} color={member.avatar_color} size={64} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className={role.cls}>{role.label}</Badge>
              {member.status && <Badge className={(USER_STATUS[member.status] || {}).cls}>{(USER_STATUS[member.status] || {}).label}</Badge>}
            </div>
            <div className="mt-2 space-y-1 text-[12.5px] text-slate-600">
              <p className="flex items-center gap-1.5"><Mail size={13} className="text-slate-400" /> {member.email}</p>
              {member.company && <p className="flex items-center gap-1.5"><Briefcase size={13} className="text-slate-400" /> {member.company}</p>}
              {member.last_seen_at && <p className="text-[11.5px] text-slate-400">Vu {timeAgo(member.last_seen_at)}</p>}
            </div>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <Metric label="Tâches ouvertes" value={num(member.active_tasks)} />
          <Metric label="Charge planifiée" value={hours(load)} />
          <Metric label="Capacité / semaine" value={hours(cap)} />
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
          <div className="flex items-center justify-between">
            <p className="text-[13px] font-semibold text-slate-800">Utilisation de la capacité</p>
            <Ring value={Math.min(100, util)} size={54} stroke={6}
              color={util > 110 ? '#E11D48' : util > 85 ? '#F59E0B' : '#10B981'}>
              <span className="text-[11px] font-bold">{Math.round(util)}%</span>
            </Ring>
          </div>
          <Progress value={Math.min(100, util)} size={6} className="mt-3"
            tone={util > 110 ? 'bg-rose-500' : util > 85 ? 'bg-amber-500' : 'bg-brand-600'} />
          {util > 110 && (
            <Alert tone="warning" className="mt-3">
              Ce membre dépasse sa capacité : l’Agent 2 proposera une réassignation lors de la prochaine assignation.
            </Alert>
          )}
        </div>

        {(member.team_names || []).length > 0 && (
          <div>
            <p className="label">Équipes</p>
            <div className="flex flex-wrap gap-1.5">
              {member.team_names.map((n) => <span key={n} className="chip bg-brand-50 text-brand-700">{n}</span>)}
            </div>
          </div>
        )}

        {member.skills?.length > 0 && (
          <div>
            <p className="label">Compétences</p>
            <div className="flex flex-wrap gap-1.5">
              {member.skills.map((s) => (
                <span key={s.id} className="chip">
                  {s.name} <span className="text-brand-600">·{s.level}</span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}

function Metric({ label, value }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2.5">
      <p className="text-[10.5px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 text-[15px] font-bold text-slate-900">{value}</p>
    </div>
  )
}
