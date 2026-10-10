import { useState } from 'react'
import {
  Award, Bell, Building2, Briefcase, Camera, Check, Clock, Globe, KeyRound, Mail, Palette,
  Phone, Save, ShieldCheck, Sparkles, Trash2, User, X,
} from 'lucide-react'
import api, { errorMessage, fieldErrors } from '../../lib/api'
import { useQuery } from '../../lib/useApi'
import { useAuth } from '../../context/AuthContext'
import {
  Alert, Avatar, Badge, Button, Card, CardHeader, EmptyState, Input, Modal, Progress,
  Select, Textarea, Toggle,
} from '../../components/ui'
import { ROLE_LABEL, USER_STATUS, cx, hours, num, pct, timeAgo } from '../../lib/format'

const COLORS = ['#2563EB', '#1D4ED8', '#0EA5E9', '#0284C7', '#3B82F6', '#0369A1', '#1E40AF', '#38BDF8']

export default function Profile() {
  const { user, updateUser } = useAuth()
  const { data: skillsData } = useQuery('/skills/', { params: { page_size: 100 } })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)
  const [errors, setErrors] = useState({})
  const [form, setForm] = useState({
    first_name: user?.first_name || '', last_name: user?.last_name || '',
    phone: user?.phone || '', job_title: user?.job_title || '',
    bio: user?.bio || '', company: user?.company || '',
    avatar_color: user?.avatar_color || '#2563EB',
    weekly_capacity_hours: user?.weekly_capacity_hours ?? 35,
    timezone: user?.timezone || 'Europe/Paris', locale: user?.locale || 'fr',
  })
  const [notif, setNotif] = useState({
    notify_email: user?.notify_email ?? true, notify_push: user?.notify_push ?? true,
    notify_risk_alerts: user?.notify_risk_alerts ?? true,
    notify_assignments: user?.notify_assignments ?? true,
    notify_agent_runs: user?.notify_agent_runs ?? true,
    notify_weekly_digest: user?.notify_weekly_digest ?? false,
  })
  const [pwdOpen, setPwdOpen] = useState(false)
  const [skillsOpen, setSkillsOpen] = useState(false)

  const skills = skillsData?.results ?? skillsData ?? []
  const role = ROLE_LABEL[user?.role] || ROLE_LABEL.MEMBER
  const mySkills = user?.skills || []
  const utilisation = Number(user?.weekly_capacity_hours) > 0
    ? (Number(user?.workload_hours || 0) / Number(user?.weekly_capacity_hours)) * 100 : 0

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const saveProfile = async () => {
    setSaving(true); setMsg(null); setErrors({})
    try {
      const { data } = await api.patch('/me/', { ...form, ...notif })
      updateUser(data)
      setMsg({ tone: 'success', text: 'Profil mis à jour.' })
    } catch (e) {
      setMsg({ tone: 'error', text: errorMessage(e) })
      setErrors(fieldErrors(e))
    } finally { setSaving(false) }
  }

  return (
    <div className="space-y-5 p-5 sm:p-7">
      <header>
        <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Compte</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Mon profil</h1>
        <p className="mt-1 text-[14px] text-slate-500">Informations personnelles, compétences et préférences de notification.</p>
      </header>

      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}

      <div className="grid gap-5 xl:grid-cols-[1fr_1.6fr]">
        {/* ------------------------------ Carte identité ------------------------------ */}
        <div className="space-y-5">
          <Card>
            <div className="flex flex-col items-center border-b border-slate-100 px-5 py-6">
              <Avatar name={user?.full_name} color={form.avatar_color} size={88} />
              <h2 className="mt-3.5 text-[17px] font-bold text-slate-900">{user?.full_name}</h2>
              <p className="text-[13px] text-slate-500">{user?.email}</p>
              <div className="mt-3 flex flex-wrap justify-center gap-1.5">
                <Badge className={role.cls}>{role.label}</Badge>
                {user?.status && (
                  <Badge className={(USER_STATUS[user.status] || {}).cls}>{(USER_STATUS[user.status] || {}).label}</Badge>
                )}
              </div>
            </div>

            <div className="card-body space-y-2.5 text-[12.5px]">
              <Row icon={Briefcase} label="Poste" value={user?.job_title || '—'} />
              <Row icon={Building2} label="Organisation" value={user?.company || '—'} />
              <Row icon={Phone} label="Téléphone" value={user?.phone || '—'} />
              <Row icon={Clock} label="Membre depuis" value={user?.created_at ? new Date(user.created_at).toLocaleDateString('fr-FR') : '—'} />
              <Row icon={Globe} label="Fuseau horaire" value={user?.timezone} />
              {user?.last_seen_at && (
                <p className="pt-1 text-[11px] text-slate-400">Dernière activité {timeAgo(user.last_seen_at)}</p>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Capacité & charge" icon={Clock}
              subtitle="Utilisée par l’Agent 2 pour équilibrer les assignations" />
            <div className="card-body">
              <Input label="Capacité hebdomadaire (h)" type="number" min="0" step="1"
                value={form.weekly_capacity_hours} onChange={set('weekly_capacity_hours')} />
              <div className="mt-4">
                <div className="flex items-center justify-between text-[12.5px]">
                  <span className="text-slate-500">Charge actuelle</span>
                  <span className={cx('font-bold',
                    utilisation > 110 ? 'text-rose-600' : utilisation > 85 ? 'text-amber-600' : 'text-emerald-600')}>
                    {pct(utilisation, 0)}
                  </span>
                </div>
                <Progress value={Math.min(100, utilisation)} size={6} className="mt-1.5"
                  tone={utilisation > 110 ? 'bg-rose-500' : utilisation > 85 ? 'bg-amber-500' : 'bg-brand-600'} />
                <p className="mt-1.5 text-[11.5px] text-slate-400">
                  {hours(user?.workload_hours || 0)} planifiées sur {hours(form.weekly_capacity_hours)} de capacité
                </p>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Compétences" icon={Award}
              subtitle="Sert au matching de l’Agent 2"
              action={<Button variant="soft" size="sm" icon={Sparkles} onClick={() => setSkillsOpen(true)}>Gérer</Button>} />
            <div className="card-body">
              {mySkills.length === 0 ? (
                <EmptyState icon={Award} title="Aucune compétence renseignée"
                  description="Ajoutez vos compétences pour recevoir des assignations pertinentes."
                  action={<Button size="sm" onClick={() => setSkillsOpen(true)}>Ajouter</Button>} />
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {mySkills.map((s) => (
                    <span key={s.id} className="chip bg-brand-50 text-brand-700">
                      {s.name} <span className="font-bold">·{s.level}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </Card>

          <div className="flex gap-2">
            <Button variant="secondary" icon={KeyRound} className="flex-1" onClick={() => setPwdOpen(true)}>
              Changer le mot de passe
            </Button>
          </div>
        </div>

        {/* ------------------------------ Formulaire ------------------------------ */}
        <div className="space-y-5">
          <Card>
            <CardHeader title="Informations personnelles" icon={User} subtitle="Visibles par les membres de vos projets" />
            <div className="card-body space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Input label="Prénom" value={form.first_name} onChange={set('first_name')} error={errors.first_name} />
                <Input label="Nom" value={form.last_name} onChange={set('last_name')} error={errors.last_name} />
                <Input label="Poste" icon={Briefcase} value={form.job_title} onChange={set('job_title')} />
                <Input label="Organisation" icon={Building2} value={form.company} onChange={set('company')} />
                <Input label="Téléphone" icon={Phone} value={form.phone} onChange={set('phone')} />
                <Input label="E-mail (non modifiable)" icon={Mail} value={user?.email} disabled />
              </div>
              <Textarea label="Bio / présentation" value={form.bio} onChange={set('bio')}
                hint="Quelques lignes sur votre rôle et vos domaines d’expertise." />

              <div>
                <label className="label">Couleur d’avatar</label>
                <div className="flex flex-wrap gap-2">
                  {COLORS.map((c) => (
                    <button key={c} onClick={() => setForm({ ...form, avatar_color: c })}
                      className={cx('grid h-9 w-9 place-items-center rounded-lg transition',
                        form.avatar_color === c && 'ring-2 ring-offset-2 ring-slate-400')}
                      style={{ background: c }}>
                      {form.avatar_color === c && <Check size={15} className="text-white" />}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <Select label="Fuseau horaire" value={form.timezone} onChange={set('timezone')} options={[
                  { value: 'Europe/Paris', label: 'Europe/Paris (CET)' },
                  { value: 'Africa/Tunis', label: 'Africa/Tunis' },
                  { value: 'Europe/London', label: 'Europe/London' },
                  { value: 'UTC', label: 'UTC' },
                ]} />
                <Select label="Langue" value={form.locale} onChange={set('locale')} options={[
                  { value: 'fr', label: 'Français' }, { value: 'en', label: 'English' },
                ]} />
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Notifications" icon={Bell} subtitle="Choisissez les évènements qui vous alertent" />
            <div className="card-body">
              <div className="divide-y divide-slate-100">
                <Toggle checked={notif.notify_risk_alerts}
                  onChange={(v) => setNotif({ ...notif, notify_risk_alerts: v })}
                  label="Alertes de risque" description="Retards, dérive de charge, bugs récurrents détectés par l’Agent 3" />
                <Toggle checked={notif.notify_assignments}
                  onChange={(v) => setNotif({ ...notif, notify_assignments: v })}
                  label="Assignations de tâches" description="Nouvelle tâche attribuée ou réassignée" />
                <Toggle checked={notif.notify_agent_runs}
                  onChange={(v) => setNotif({ ...notif, notify_agent_runs: v })}
                  label="Exécutions d’agents" description="Fin d’analyse, plan proposé, échec d’exécution" />
                <Toggle checked={notif.notify_email}
                  onChange={(v) => setNotif({ ...notif, notify_email: v })}
                  label="Réception par e-mail" description="Envoi d’un récapitulatif à votre adresse" />
                <Toggle checked={notif.notify_push}
                  onChange={(v) => setNotif({ ...notif, notify_push: v })}
                  label="Notifications in-app" description="Toasts et badge dans le centre de notifications" />
                <Toggle checked={notif.notify_weekly_digest}
                  onChange={(v) => setNotif({ ...notif, notify_weekly_digest: v })}
                  label="Récapitulatif hebdomadaire" description="Synthèse des projets chaque lundi" />
              </div>
            </div>
          </Card>

          <div className="sticky bottom-4 flex justify-end gap-2">
            <Button size="lg" icon={Save} loading={saving} onClick={saveProfile}>Enregistrer les modifications</Button>
          </div>
        </div>
      </div>

      {pwdOpen && <PasswordModal onClose={() => setPwdOpen(false)} />}
      {skillsOpen && (
        <SkillsModal skills={skills} selected={mySkills}
          onClose={() => setSkillsOpen(false)}
          onSaved={() => { setSkillsOpen(false); window.location.reload() }} />
      )}
    </div>
  )
}

function Row({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-slate-100 py-1.5 last:border-0">
      <span className="flex items-center gap-2 text-slate-500">
        <Icon size={13} className="text-slate-400" /> {label}
      </span>
      <span className="truncate font-medium text-slate-800">{value}</span>
    </div>
  )
}

function PasswordModal({ onClose }) {
  const [form, setForm] = useState({ old_password: '', new_password: '', confirm: '' })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [done, setDone] = useState(false)

  const save = async () => {
    setErrors({}); setSaving(true)
    try {
      await api.post('/auth/password/change/', {
        old_password: form.old_password, new_password: form.new_password,
      })
      setDone(true)
      setTimeout(onClose, 1400)
    } catch (e) { setErrors(fieldErrors(e)) }
    finally { setSaving(false) }
  }

  return (
    <Modal open onClose={onClose} title="Changer le mot de passe" icon={KeyRound} size="sm"
      footer={<><Button variant="secondary" onClick={onClose}>Annuler</Button>
        <Button loading={saving} onClick={save} disabled={done}>Mettre à jour</Button></>}>
      {done ? (
        <Alert tone="success" title="Mot de passe mis à jour">Vous pouvez fermer cette fenêtre.</Alert>
      ) : (
        <div className="space-y-4">
          <Input label="Mot de passe actuel" type="password" required autoComplete="current-password"
            value={form.old_password} error={errors.old_password}
            onChange={(e) => setForm({ ...form, old_password: e.target.value })} />
          <Input label="Nouveau mot de passe" type="password" required autoComplete="new-password"
            value={form.new_password} error={errors.new_password}
            onChange={(e) => setForm({ ...form, new_password: e.target.value })}
            hint="8 caractères minimum, avec chiffres et majuscules." />
          <Input label="Confirmer le nouveau mot de passe" type="password" required autoComplete="new-password"
            value={form.confirm}
            error={form.confirm && form.confirm !== form.new_password ? 'Les mots de passe ne correspondent pas.' : ''}
            onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
        </div>
      )}
    </Modal>
  )
}

function SkillsModal({ skills, selected, onClose, onSaved }) {
  const [picked, setPicked] = useState(
    Object.fromEntries(selected.map((s) => [s.skill, s.level])),
  )
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const toggle = (id) => setPicked((p) => {
    const next = { ...p }
    if (next[id] === undefined) next[id] = 3
    else delete next[id]
    return next
  })

  const save = async () => {
    setSaving(true); setErr('')
    try {
      await api.put('/me/skills/', Object.entries(picked).map(([skill, level]) => ({ skill: Number(skill), level })))
      onSaved()
    } catch (e) { setErr(errorMessage(e)) }
    finally { setSaving(false) }
  }

  const grouped = skills.reduce((acc, s) => {
    ;(acc[s.category] ||= []).push(s)
    return acc
  }, {})

  return (
    <Modal open onClose={onClose} title="Mes compétences" size="lg" icon={Award}
      subtitle={`${Object.keys(picked).length} compétence(s) sélectionnée(s)`}
      footer={<><Button variant="secondary" onClick={onClose}>Annuler</Button>
        <Button loading={saving} onClick={save}>Enregistrer</Button></>}>
      {err && <Alert tone="error" className="mb-4">{err}</Alert>}
      <div className="space-y-5">
        {Object.entries(grouped).map(([cat, list]) => (
          <div key={cat}>
            <p className="label">{{ TECH: 'Technique', DATA: 'Data / IA', DESIGN: 'Design',
              FUNC: 'Fonctionnel', MGMT: 'Management' }[cat] || cat}</p>
            <div className="flex flex-wrap gap-1.5">
              {list.map((s) => {
                const on = picked[s.id] !== undefined
                return (
                  <button key={s.id} onClick={() => toggle(s.id)}
                    className={cx('rounded-lg border px-2.5 py-1.5 text-[12px] font-medium transition',
                      on ? 'border-brand-500 bg-brand-50 text-brand-700' : 'border-slate-200 text-slate-600 hover:border-slate-300')}>
                    {on && <Check size={11} className="mr-1 inline" />}
                    {s.name}
                  </button>
                )
              })}
            </div>
          </div>
        ))}

        {Object.keys(picked).length > 0 && (
          <div>
            <p className="label">Niveau de maîtrise</p>
            <div className="space-y-2">
              {Object.entries(picked).map(([id, level]) => {
                const s = skills.find((x) => x.id === Number(id))
                if (!s) return null
                return (
                  <div key={id} className="flex items-center gap-3">
                    <span className="w-[160px] shrink-0 truncate text-[12.5px] font-medium text-slate-700">{s.name}</span>
                    <div className="flex flex-1 gap-1">
                      {[1, 2, 3, 4, 5].map((n) => (
                        <button key={n} onClick={() => setPicked({ ...picked, [id]: n })}
                          className={cx('h-7 flex-1 rounded text-[11px] font-semibold transition',
                            level >= n ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200')}>
                          {n}
                        </button>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
            <p className="hint mt-2">1 = notions · 3 = autonome · 5 = expert. Ces niveaux alimentent le matching de l’Agent 2.</p>
          </div>
        )}

        {!skills.length && <EmptyState icon={Award} title="Aucune compétence disponible" />}
      </div>
    </Modal>
  )
}
