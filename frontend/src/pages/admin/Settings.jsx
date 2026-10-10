import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Activity, Bell, Bot, Building2, Check, Database, ExternalLink, Gauge, Globe, Info,
  KeyRound, Plug, RefreshCw, Save, Server, Settings2, Shield, ShieldCheck, Sparkles,
  Workflow, X, Zap,
} from 'lucide-react'
import api, { errorMessage } from '../../lib/api'
import { useQuery } from '../../lib/useApi'
import { useAuth } from '../../context/AuthContext'
import {
  Alert, Avatar, Badge, Button, Card, CardHeader, Dot, EmptyState, Input, Progress,
  Select, Skeleton, Toggle,
} from '../../components/ui'
import { cx, formatDateTime, num, pct } from '../../lib/format'

export default function AdminSettings() {
  const { user } = useAuth()
  const { data: monitor } = useQuery('/agents/monitor/')
  const { data: agentsData } = useQuery('/agents/', { params: { page_size: 10 } })
  const { data: integrations } = useQuery('/integrations/', { params: { page_size: 20 } })
  const { data: usersData } = useQuery('/users/', { params: { page_size: 5 } })
  const [msg, setMsg] = useState(null)

  const agents = agentsData?.results ?? agentsData ?? []
  const connectors = integrations?.results ?? integrations ?? []
  const k = usersData ? {} : {}

  return (
    <div className="space-y-5 p-5 sm:p-7">
      <header>
        <p className="text-[12px] font-semibold uppercase tracking-wider text-brand-600">Administration</p>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Paramètres de la plateforme</h1>
        <p className="mt-1 text-[14px] text-slate-500">
          Configuration du runtime d’agents, des connecteurs et des règles de gouvernance.
        </p>
      </header>

      {msg && (
        <Alert tone={msg.tone} action={<Button variant="ghost" size="sm" icon={X} onClick={() => setMsg(null)} />}>
          {msg.text}
        </Alert>
      )}

      <div className="grid gap-5 xl:grid-cols-3">
        {/* ------------------------------- Runtime ------------------------------- */}
        <div className="space-y-5 xl:col-span-2">
          <Card>
            <CardHeader title="Runtime des agents" icon={Bot}
              subtitle="Branchement du système multi-agents"
              action={
                <Badge className={monitor?.enabled ? 'badge-success' : 'badge-purple'}
                  dot={monitor?.enabled ? 'bg-emerald-500' : 'bg-violet-500'}>
                  {monitor?.enabled ? 'Branché' : 'Emplacement réservé'}
                </Badge>
              } />
            <div className="card-body space-y-4">
              <Alert tone="info" title="État actuel">
                {monitor?.enabled
                  ? 'Le runtime est branché : les lancements d’agents appellent le service d’inférence.'
                  : 'Aucun runtime n’est branché. Les lancements créent des exécutions au statut « réservé », journalisées dans l’audit, sans appel de modèle ni écriture externe.'}
              </Alert>

              <div className="grid gap-3 sm:grid-cols-2">
                <InfoBlock label="Orchestrateur" value={monitor?.orchestrator || 'LangGraph'}
                  hint="LangGraph, CrewAI ou AutoGen" />
                <InfoBlock label="Exécutions totales" value={num(monitor?.totals?.runs)}
                  hint={`${num(monitor?.totals?.skipped)} réservées`} />
                <InfoBlock label="Latence moyenne" value={`${num(monitor?.totals?.avg_latency_ms)} ms`}
                  hint="aucune inférence exécutée" />
                <InfoBlock label="Taux d’erreur JSON" value={pct(monitor?.json_error_rate || 0, 1)}
                  hint="hors-format de génération" />
              </div>

              <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4">
                <p className="flex items-center gap-1.5 text-[13px] font-semibold text-slate-800">
                  <KeyRound size={14} className="text-brand-600" /> Pour brancher le runtime
                </p>
                <ol className="mt-2.5 space-y-2 text-[12.5px] text-slate-600">
                  {[
                    ['1', 'Implémenter orchestration/services.py::dispatch(run) — appel HTTP au runtime, file Celery ou exécution locale.'],
                    ['2', 'Renseigner le champ runtime_endpoint de chaque AgentDefinition.'],
                    ['3', 'Passer la variable d’environnement AGENT_RUNTIME_ENABLED=True, puis redémarrer l’API.'],
                  ].map(([n, t]) => (
                    <li key={n} className="flex gap-2.5">
                      <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-brand-600 text-[10.5px] font-bold text-white">
                        {n}
                      </span>
                      <span className="leading-relaxed">{t}</span>
                    </li>
                  ))}
                </ol>
                <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-[11px] leading-relaxed text-slate-100">
{`# config/settings.py — variables d'environnement
AGENT_RUNTIME_ENABLED=True
SCOPING_AGENT_URL=https://agents.local/scoping
OPS_AGENT_URL=https://agents.local/ops
RISK_AGENT_URL=https://agents.local/risk
ORCHESTRATOR=LangGraph`}
                </pre>
              </div>

              <div className="space-y-2">
                <p className="label">Agents configurés</p>
                {agents.map((a) => (
                  <div key={a.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 px-3.5 py-2.5">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: a.color }} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-semibold text-slate-800">{a.name}</p>
                      <p className="truncate font-mono text-[11px] text-slate-500">
                        {a.runtime_endpoint || '— endpoint non configuré —'}
                      </p>
                    </div>
                    <Badge className="badge-purple">Réservé</Badge>
                    {a.requires_human_validation && <Badge className="badge-warning">Validation humaine</Badge>}
                  </div>
                ))}
                {!agents.length && <EmptyState icon={Bot} title="Aucun agent défini" />}
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Connecteurs Jira / Trello" icon={Plug}
              subtitle="Configurations enregistrées sur la plateforme"
              action={<Badge className="badge-neutral">{connectors.length} connecteur(s)</Badge>} />
            {connectors.length === 0 ? (
              <div className="p-6">
                <EmptyState icon={Plug} title="Aucun connecteur"
                  description="Les connecteurs sont ajoutés depuis la page d’un projet (onglet Connecteurs)." />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr><th>Nom</th><th>Fournisseur</th><th>Projet</th><th>Statut</th><th>Synchro auto</th></tr>
                  </thead>
                  <tbody>
                    {connectors.map((c) => (
                      <tr key={c.id}>
                        <td>
                          <p className="text-[13px] font-semibold text-slate-800">{c.name}</p>
                          <p className="truncate text-[11px] text-slate-500">{c.base_url}</p>
                        </td>
                        <td><Badge className="badge-sky">{c.provider === 'JIRA' ? 'Jira' : c.provider === 'TRELLO' ? 'Trello' : 'GitHub'}</Badge></td>
                        <td className="max-w-[140px] truncate text-[12px] text-slate-600">
                          {c.project ? <Link to={`/app/projects/${c.project}`} className="link">Projet #{c.project}</Link> : '—'}
                        </td>
                        <td>
                          <Badge className={c.status === 'CONNECTED' ? 'badge-success' : c.status === 'ERROR' ? 'badge-danger' : 'badge-neutral'}
                            dot={c.status === 'CONNECTED' ? 'bg-emerald-500' : c.status === 'ERROR' ? 'bg-rose-500' : 'bg-slate-400'}>
                            {{ CONNECTED: 'Connecté', DISCONNECTED: 'Déconnecté', ERROR: 'Erreur' }[c.status]}
                          </Badge>
                        </td>
                        <td className="text-[12px] text-slate-600">
                          {c.auto_sync ? `toutes les ${c.sync_interval_minutes} min` : 'manuelle'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        {/* ------------------------------- Panneau latéral ------------------------------- */}
        <aside className="space-y-5">
          <Card>
            <CardHeader title="Mon compte administrateur" icon={ShieldCheck} />
            <div className="card-body">
              <div className="flex items-center gap-3">
                <Avatar name={user?.full_name} color={user?.avatar_color} size={52} />
                <div className="min-w-0">
                  <p className="truncate text-[14px] font-semibold text-slate-900">{user?.full_name}</p>
                  <p className="truncate text-[12px] text-slate-500">{user?.email}</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <Badge className="badge-danger">Administrateur</Badge>
                {user?.is_superuser && <Badge className="badge-purple">Superuser</Badge>}
                {user?.is_staff && <Badge className="badge-sky">Django Admin</Badge>}
              </div>
              <div className="mt-4 space-y-1.5 text-[12.5px]">
                <Row label="Dernière activité" value={user?.last_seen_at ? formatDateTime(user.last_seen_at) : '—'} />
                <Row label="Fuseau horaire" value={user?.timezone} />
                <Row label="Langue" value={user?.locale === 'fr' ? 'Français' : 'English'} />
              </div>
              <Link to="/app/profile" className="btn btn-secondary btn-sm mt-4 w-full">
                <Settings2 size={14} /> Gérer mon profil
              </Link>
            </div>
          </Card>

          <Card>
            <CardHeader title="Règles de gouvernance" icon={Shield}
              subtitle="Politiques appliquées par la plateforme" />
            <div className="card-body">
              <div className="divide-y divide-slate-100">
                <Rule label="Validation humaine obligatoire" on
                  desc="Aucune écriture Jira/Trello sans confirmation du chef de projet." />
                <Rule label="Journalisation des actions agents" on
                  desc="Chaque exécution et écriture est tracée avec identifiant de corrélation." />
                <Rule label="Idempotence des appels API" on
                  desc="Protection contre la duplication de tickets et gestion du rate limiting." />
                <Rule label="Rôle admin non auto-attribuable" on
                  desc="Le rôle administrateur ne peut pas être choisi à l’inscription." />
                <Rule label="Suspension de compte immédiate" on
                  desc="Un compte suspendu perd l’accès dès la prochaine requête." />
                <Rule label="Notifications ciblées par rôle" on
                  desc="Les diffusions peuvent viser un rôle ou une sélection nominative." />
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Stack technique" icon={Server} subtitle="Environnement de référence" />
            <div className="card-body space-y-2">
              <Tech name="Front-end" value="React 19 · Vite · Tailwind CSS · Recharts" />
              <Tech name="Back-end" value="Django 5 · Django REST Framework · JWT" />
              <Tech name="Base de données" value="SQLite (démo) · PostgreSQL en production" />
              <Tech name="Orchestration" value="LangGraph · CrewAI · AutoGen" />
              <Tech name="Observabilité" value="Grafana · Airflow · EvidentlyAI" />
              <Tech name="Modèles" value="SLM LoRA/QLoRA · XGBoost · DistilBERT" />
            </div>
          </Card>

          <Card>
            <CardHeader title="Raccourcis" icon={Globe} />
            <div className="card-body space-y-2">
              <Shortcut to="/admin" icon={Gauge} label="Vue d’ensemble" desc="KPI et santé plateforme" />
              <Shortcut to="/admin/users" icon={ShieldCheck} label="Gestion des comptes" desc="Rôles, statuts, actions groupées" />
              <Shortcut to="/admin/agents" icon={Bot} label="Supervision des agents" desc="Latence, erreurs, équilibrage" />
              <Shortcut to="/admin/audit" icon={Activity} label="Journal d’audit" desc="Traçabilité complète" />
              <Shortcut to="/admin/announcements" icon={Bell} label="Annonces" desc="Diffusion ciblée" />
              <Shortcut to="/admin/" icon={Database} label="Django Admin" desc="Administration technique" external />
            </div>
          </Card>
        </aside>
      </div>
    </div>
  )
}

function InfoBlock({ label, value, hint }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3.5 py-3">
      <p className="text-[10.5px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-[16px] font-bold text-slate-900">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-slate-500">{hint}</p>}
    </div>
  )
}

function Rule({ label, on, desc }) {
  return (
    <div className="flex items-start gap-2.5 py-2.5">
      <span className={cx('mt-0.5 grid h-4.5 w-4.5 shrink-0 place-items-center rounded-full',
        on ? 'bg-emerald-500 text-white' : 'bg-slate-200 text-slate-500')} style={{ height: 18, width: 18 }}>
        {on ? <Check size={11} /> : <X size={11} />}
      </span>
      <div className="min-w-0">
        <p className="text-[12.5px] font-medium text-slate-800">{label}</p>
        <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">{desc}</p>
      </div>
    </div>
  )
}

function Tech({ name, value }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-[10.5px] uppercase tracking-wide text-slate-400">{name}</p>
      <p className="mt-0.5 text-[12px] font-medium text-slate-800">{value}</p>
    </div>
  )
}

function Shortcut({ to, icon: Icon, label, desc, external }) {
  const inner = (
    <>
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
        <Icon size={15} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[12.5px] font-semibold text-slate-800">{label}</p>
        <p className="truncate text-[11px] text-slate-500">{desc}</p>
      </div>
      {external ? <ExternalLink size={13} className="shrink-0 text-slate-300" />
                 : <span className="shrink-0 text-slate-300">›</span>}
    </>
  )
  return external
    ? <a href={to} className="flex items-center gap-2.5 rounded-lg border border-slate-200 px-3 py-2 transition hover:border-brand-300 hover:bg-brand-50/40">{inner}</a>
    : <Link to={to} className="flex items-center gap-2.5 rounded-lg border border-slate-200 px-3 py-2 transition hover:border-brand-300 hover:bg-brand-50/40">{inner}</Link>
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-1.5 last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-800">{value}</span>
    </div>
  )
}
