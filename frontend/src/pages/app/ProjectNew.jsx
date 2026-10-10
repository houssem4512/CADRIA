import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeft, ArrowRight, Briefcase, Calendar, Check, ChevronsUpDown, FileText, GitBranch,
  Sparkles, Target, Users, Wallet, Wand2, X,
} from 'lucide-react'
import api, { errorMessage, fieldErrors } from '../../lib/api'
import { useQuery } from '../../lib/useApi'
import {
  Alert, Avatar, Badge, Button, Card, CardHeader, Input, Modal, Select, Textarea, Toggle,
} from '../../components/ui'
import { cx } from '../../lib/format'

const METHODOLOGIES = [
  { value: 'SCRUM', label: 'Scrum', desc: 'Sprints courts, revue et rétrospective' },
  { value: 'KANBAN', label: 'Kanban', desc: 'Flux continu, limitation du travail en cours' },
  { value: 'WATERFALL', label: 'Cycle en V', desc: 'Phases séquentielles, jalons fixes' },
  { value: 'HYBRID', label: 'Hybride', desc: 'Jalons fixes et itérations internes' },
]

const TEMPLATES = [
  {
    id: 'web', label: 'Refonte web / portail',
    brief: `Refondre le portail existant : modernisation de l'interface, accessibilité RGAA, intégration du SSO, et exposition d'une API publique documentée. L'équipe doit livrer en plusieurs itérations avec une mise en production progressive.`,
    tags: ['front', 'api', 'sso', 'accessibilité'],
  },
  {
    id: 'mobile', label: 'Application mobile',
    brief: `Livrer une application mobile iOS/Android permettant la saisie de données terrain en mode hors-ligne, avec synchronisation automatique à la reconnexion et gestion des conflits.`,
    tags: ['mobile', 'offline', 'react-native'],
  },
  {
    id: 'data', label: 'Projet data / IA',
    brief: `Construire un modèle de prédiction entraîné sur l'historique interne, avec pipeline d'entraînement reproductible, évaluation continue de la qualité et dashboard de suivi des dérives.`,
    tags: ['data', 'ml', 'mlops'],
  },
  {
    id: 'infra', label: 'Migration infrastructure',
    brief: `Migrer les applications internes vers une infrastructure conteneurisée, industrialiser les déploiements (GitOps) et mettre en place l'observabilité complète, sans interruption de service.`,
    tags: ['cloud', 'kubernetes', 'gitops'],
  },
]

const SUGGESTED = [
  'Décrivez l’objectif métier en une phrase, puis le périmètre fonctionnel.',
  'Précisez les contraintes : budget, délai, équipe disponible, outils imposés.',
  'Mentionnez les dépendances externes et les hypothèses à valider.',
]

export default function ProjectNew() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    name: '', summary: '', brief: '', methodology: 'SCRUM',
    start_date: new Date().toISOString().slice(0, 10),
    target_end_date: '', budget: '', currency: 'EUR',
    team: null, member_ids: [], tags: [], run_scoping: false,
  })
  const [errors, setErrors] = useState({})
  const [globalError, setGlobalError] = useState('')
  const [saving, setSaving] = useState(false)
  const [tagInput, setTagInput] = useState('')
  const [memberPicker, setMemberPicker] = useState(false)

  const { data: membersData } = useQuery('/members/', { params: { page_size: 60 } })
  const { data: teamsData } = useQuery('/teams/', { params: { page_size: 30 } })
  const members = membersData?.results ?? membersData ?? []
  const teams = teamsData?.results ?? teamsData ?? []

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const wordCount = useMemo(() => form.brief.trim().split(/\s+/).filter(Boolean).length, [form.brief])
  const briefQuality = Math.min(100, Math.round((wordCount / 60) * 100))

  const addTag = () => {
    const t = tagInput.trim().toLowerCase()
    if (t && !form.tags.includes(t) && form.tags.length < 8) setForm({ ...form, tags: [...form.tags, t] })
    setTagInput('')
  }

  const toggleMember = (id) => {
    setForm((f) => ({
      ...f,
      member_ids: f.member_ids.includes(id) ? f.member_ids.filter((x) => x !== id) : [...f.member_ids, id],
    }))
  }

  const applyTemplate = (t) => {
    setForm((f) => ({
      ...f,
      name: f.name || t.label,
      brief: t.brief,
      tags: Array.from(new Set([...f.tags, ...t.tags])),
    }))
  }

  const canContinue = step === 0
    ? form.name.trim().length >= 3
    : step === 1
      ? form.brief.trim().length >= 40
      : true

  const submit = async () => {
    setErrors({}); setGlobalError(''); setSaving(true)
    try {
      const payload = {
        name: form.name, summary: form.summary, brief: form.brief,
        methodology: form.methodology,
        start_date: form.start_date || null, target_end_date: form.target_end_date || null,
        budget: form.budget || null, currency: form.currency,
        team: form.team || null, member_ids: form.member_ids, tags: form.tags,
        status: form.run_scoping ? 'SCOPING' : 'DRAFT',
      }
      const { data } = await api.post('/projects/', payload)
      if (form.run_scoping) {
        try {
          await api.post('/agents/runs/start/', {
            project: data.id, agent: 'SCOPING',
            input: { brief: form.brief, constraints: { budget: form.budget || null } },
          })
        } catch { /* l’emplacement réservé ne doit pas bloquer la création */ }
      }
      navigate(`/app/projects/${data.id}`, { replace: true })
    } catch (err) {
      setGlobalError(errorMessage(err, 'Impossible de créer le projet.'))
      setErrors(fieldErrors(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-5 sm:p-7">
      <button onClick={() => navigate(-1)} className="inline-flex items-center gap-1.5 text-[13px] font-medium text-slate-500 hover:text-brand-700">
        <ArrowLeft size={14} /> Retour aux projets
      </button>

      <header>
        <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Nouveau</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Créer un projet</h1>
        <p className="mt-1 text-[14px] text-slate-500">
          Décrivez le projet en langage naturel : le copilote s’appuiera sur cette description pour proposer un découpage.
        </p>
      </header>

      {/* ------------------------------ Étapes ------------------------------ */}
      <div className="flex items-center gap-2">
        {['Identification', 'Description', 'Cadre & équipe'].map((label, i) => (
          <div key={label} className="flex flex-1 items-center gap-2">
            <button onClick={() => i < step && setStep(i)}
              className={cx('grid h-8 w-8 shrink-0 place-items-center rounded-full text-[12.5px] font-bold transition',
                i < step ? 'bg-emerald-500 text-white' : i === step ? 'bg-brand-600 text-white' : 'bg-slate-200 text-slate-500')}>
              {i < step ? <Check size={15} /> : i + 1}
            </button>
            <span className={cx('hidden text-[12.5px] font-medium sm:block', i === step ? 'text-slate-900' : 'text-slate-500')}>
              {label}
            </span>
            {i < 2 && <span className={cx('h-px flex-1', i < step ? 'bg-emerald-400' : 'bg-slate-200')} />}
          </div>
        ))}
      </div>

      {globalError && <Alert tone="error" title="Création impossible">{globalError}</Alert>}

      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        {/* ------------------------------ Formulaire ------------------------------ */}
        <div className="space-y-5">
          {step === 0 && (
            <Card>
              <CardHeader title="Identification" icon={Briefcase} subtitle="Nom, résumé et méthodologie de travail" />
              <div className="card-body space-y-4">
                <Input label="Nom du projet" required placeholder="Refonte du portail client"
                  value={form.name} onChange={set('name')} error={errors.name}
                  hint="Court et explicite — il servira de référence dans Jira/Trello." />
                <Input label="Résumé (une ligne)" placeholder="Nouveau portail self-service pour les clients grand compte"
                  value={form.summary} onChange={set('summary')} error={errors.summary} />

                <div>
                  <label className="label">Méthodologie</label>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {METHODOLOGIES.map((m) => (
                      <button key={m.value} type="button" onClick={() => setForm({ ...form, methodology: m.value })}
                        className={cx('rounded-lg border px-3 py-2.5 text-left transition',
                          form.methodology === m.value
                            ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-500/20'
                            : 'border-slate-200 bg-white hover:border-slate-300')}>
                        <span className="flex items-center gap-1.5 text-[13px] font-semibold text-slate-800">
                          {form.methodology === m.value && <Check size={13} className="text-brand-600" />}
                          {m.label}
                        </span>
                        <span className="mt-0.5 block text-[11.5px] text-slate-500">{m.desc}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          )}

          {step === 1 && (
            <Card>
              <CardHeader title="Description en langage naturel" icon={FileText}
                subtitle="C’est la matière première de l’Agent 1 — soyez le plus précis possible"
                action={<Badge className="badge-brand">{wordCount} mots</Badge>} />
              <div className="card-body space-y-4">
                <Textarea
                  label="Description du projet" required rows={10}
                  placeholder={`Décrivez le contexte, l'objectif, le périmètre fonctionnel, les contraintes (budget, délai, équipe), les dépendances et les hypothèses…`}
                  value={form.brief} onChange={set('brief')} error={errors.brief}
                  className="min-h-[240px]"
                />
                <div>
                  <div className="flex items-center justify-between text-[12px]">
                    <span className="text-slate-500">Qualité de la description</span>
                    <span className={cx('font-semibold',
                      briefQuality >= 80 ? 'text-emerald-600' : briefQuality >= 40 ? 'text-amber-600' : 'text-rose-600')}>
                      {briefQuality >= 80 ? 'Excellente' : briefQuality >= 40 ? 'Correcte' : 'Insuffisante'}
                    </span>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div className={cx('h-full rounded-full transition-all',
                      briefQuality >= 80 ? 'bg-emerald-500' : briefQuality >= 40 ? 'bg-amber-500' : 'bg-rose-500')}
                      style={{ width: `${briefQuality}%` }} />
                  </div>
                </div>
                <div className="rounded-lg bg-brand-50/60 p-3.5">
                  <p className="flex items-center gap-1.5 text-[12.5px] font-semibold text-brand-800">
                    <Sparkles size={14} /> Conseils pour un bon cadrage
                  </p>
                  <ul className="mt-2 space-y-1">
                    {SUGGESTED.map((s) => (
                      <li key={s} className="flex gap-2 text-[12px] text-slate-600">
                        <Check size={13} className="mt-0.5 shrink-0 text-brand-600" /> {s}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </Card>
          )}

          {step === 2 && (
            <>
              <Card>
                <CardHeader title="Cadre temporel & budgétaire" icon={Target} subtitle="Jalons, budget et étiquettes" />
                <div className="card-body space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Input label="Date de début" type="date" icon={Calendar}
                      value={form.start_date} onChange={set('start_date')} error={errors.start_date} />
                    <Input label="Échéance cible" type="date" icon={Calendar}
                      value={form.target_end_date} onChange={set('target_end_date')} error={errors.target_end_date} />
                  </div>
                  <div className="grid gap-4 sm:grid-cols-[1fr_110px]">
                    <Input label="Budget (facultatif)" type="number" min="0" icon={Wallet}
                      placeholder="250000" value={form.budget} onChange={set('budget')} error={errors.budget} />
                    <Select label="Devise" value={form.currency} onChange={set('currency')} options={[
                      { value: 'EUR', label: 'EUR €' }, { value: 'USD', label: 'USD $' },
                      { value: 'TND', label: 'TND DT' }, { value: 'GBP', label: 'GBP £' },
                    ]} />
                  </div>
                  <div>
                    <label className="label">Étiquettes</label>
                    <div className="flex flex-wrap gap-1.5 rounded-lg border border-slate-300 bg-white p-2">
                      {form.tags.map((t) => (
                        <span key={t} className="chip bg-brand-50 text-brand-700">
                          {t}
                          <button onClick={() => setForm({ ...form, tags: form.tags.filter((x) => x !== t) })}
                            className="ml-0.5 text-brand-500 hover:text-brand-800"><X size={11} /></button>
                        </span>
                      ))}
                      <input value={tagInput} onChange={(e) => setTagInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag() } }}
                        onBlur={addTag} placeholder={form.tags.length ? '' : 'Ajouter une étiquette…'}
                        className="min-w-[120px] flex-1 bg-transparent px-1 text-[13px] outline-none placeholder:text-slate-400" />
                    </div>
                  </div>
                </div>
              </Card>

              <Card>
                <CardHeader title="Équipe" icon={Users}
                  subtitle="Sélectionnez l’équipe et les membres mobilisés"
                  action={<Badge className="badge-brand">{form.member_ids.length} membre(s)</Badge>} />
                <div className="card-body space-y-4">
                  <Select label="Équipe rattachée (facultatif)" value={form.team || ''}
                    onChange={(e) => setForm({ ...form, team: e.target.value || null })}
                    options={[{ value: '', label: '— Aucune équipe —' },
                      ...(teams || []).map((t) => ({ value: t.id, label: `${t.name} · ${t.member_count} membres` }))]} />

                  <div>
                    <button onClick={() => setMemberPicker(true)}
                      className="flex w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-left transition hover:border-slate-400">
                      <span className="flex -space-x-2">
                        {form.member_ids.length === 0 && <span className="text-[13px] text-slate-500">Choisir les membres…</span>}
                        {form.member_ids.slice(0, 6).map((id) => {
                          const m = members.find((x) => x.id === id)
                          return m ? <Avatar key={id} name={m.full_name} color={m.avatar_color} size={28} ring /> : null
                        })}
                      </span>
                      <ChevronsUpDown size={15} className="text-slate-400" />
                    </button>
                  </div>

                  <div className="rounded-lg border border-violet-200 bg-violet-50/70 p-3.5">
                    <Toggle
                      checked={form.run_scoping}
                      onChange={(v) => setForm({ ...form, run_scoping: v })}
                      label="Lancer l’Agent 1 après la création"
                      description="Le lancement est journalisé en « emplacement réservé » tant que le runtime n’est pas branché."
                    />
                  </div>
                </div>
              </Card>
            </>
          )}

          {/* ------------------------------ Navigation ------------------------------ */}
          <div className="flex items-center justify-between">
            <Button variant="secondary" disabled={step === 0 || saving}
              onClick={() => setStep((s) => Math.max(0, s - 1))}>
              <ArrowLeft size={15} /> Précédent
            </Button>
            {step < 2 ? (
              <Button disabled={!canContinue} onClick={() => setStep((s) => s + 1)} iconRight>
                Suivant
              </Button>
            ) : (
              <Button loading={saving} onClick={submit} icon={Wand2}>
                {saving ? 'Création…' : 'Créer le projet'}
              </Button>
            )}
          </div>
        </div>

        {/* ------------------------------ Panneau latéral ------------------------------ */}
        <aside className="space-y-4">
          <Card>
            <CardHeader title="Aperçu" icon={Target} />
            <div className="card-body space-y-3">
              <div>
                <p className="font-mono text-[10.5px] font-bold uppercase tracking-wider text-brand-600">Référence auto</p>
                <p className="mt-0.5 text-[15px] font-bold text-slate-900">{form.name || 'Nom du projet'}</p>
                <p className="text-[12.5px] text-slate-500">{form.summary || 'Résumé du projet'}</p>
              </div>
              <div className="divider" />
              <div className="grid grid-cols-2 gap-2 text-[12px]">
                <Info label="Méthodologie" value={METHODOLOGIES.find((m) => m.value === form.methodology)?.label} />
                <Info label="Début" value={form.start_date || '—'} />
                <Info label="Échéance" value={form.target_end_date || '—'} />
                <Info label="Budget" value={form.budget ? `${Number(form.budget).toLocaleString('fr-FR')} ${form.currency}` : '—'} />
                <Info label="Membres" value={form.member_ids.length} />
                <Info label="Étiquettes" value={form.tags.length} />
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Modèles de description" icon={GitBranch}
              subtitle="Démarrez d’un cadre existant" />
            <div className="card-body space-y-2">
              {TEMPLATES.map((t) => (
                <button key={t.id} onClick={() => applyTemplate(t)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-left transition hover:border-brand-300 hover:bg-brand-50/40">
                  <span className="block text-[13px] font-semibold text-slate-800">{t.label}</span>
                  <span className="mt-0.5 line-clamp-2 block text-[11.5px] text-slate-500">{t.brief}</span>
                </button>
              ))}
            </div>
          </Card>

          <Alert tone="info" title="Validation humaine obligatoire">
            Aucun ticket n’est créé dans Jira ou Trello sans votre validation explicite du plan,
            des tâches et des assignations proposées.
          </Alert>
        </aside>
      </div>

      {/* ------------------------------ Sélecteur de membres ------------------------------ */}
      <Modal open={memberPicker} onClose={() => setMemberPicker(false)} title="Sélectionner les membres"
        subtitle={`${form.member_ids.length} membre(s) sélectionné(s)`} size="lg" icon={Users}
        footer={
          <>
            <Button variant="secondary" onClick={() => setForm({ ...form, member_ids: [] })}>Tout désélectionner</Button>
            <Button onClick={() => setMemberPicker(false)}>Valider ({form.member_ids.length})</Button>
          </>
        }>
        <div className="space-y-1.5">
          {members.map((m) => {
            const selected = form.member_ids.includes(m.id)
            return (
              <button key={m.id} onClick={() => toggleMember(m.id)}
                className={cx('flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition',
                  selected ? 'border-brand-400 bg-brand-50/60' : 'border-slate-200 hover:border-slate-300')}>
                <Avatar name={m.full_name} color={m.avatar_color} size={34} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-semibold text-slate-800">{m.full_name}</p>
                  <p className="truncate text-[11.5px] text-slate-500">
                    {m.job_title || m.email} · {m.workload_hours} h en cours
                  </p>
                </div>
                {selected && <Check size={16} className="text-brand-600" />}
              </button>
            )
          })}
          {!members.length && <p className="py-6 text-center text-[13px] text-slate-500">Aucun membre disponible.</p>}
        </div>
      </Modal>
    </div>
  )
}

function Info({ label, value }) {
  return (
    <div>
      <p className="text-[10.5px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 truncate font-semibold text-slate-800">{value ?? '—'}</p>
    </div>
  )
}
