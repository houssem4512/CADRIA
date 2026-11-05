import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight, BarChart3, Bell, Bot, Check, ChevronRight, Database, FileSearch,
  GitBranch, LineChart, Lock, Plug, Shield, ShieldAlert, Network, Sparkles,
  Users, Workflow, Zap,
} from 'lucide-react'
import { Logo } from '../components/Logo'
import { CadriaGreeter } from '../components/WavingAvatar'
import { useAuth } from '../context/AuthContext'
import { cx } from '../lib/format'

const AGENTS = [
  {
    n: 'Agent 1',
    name: 'Cadrage & décomposition',
    icon: Network,
    color: '#1D4ED8',
    points: [
      'Génération structurée texte → JSON (lots / tâches / estimations)',
      'RAG sur l’historique des projets passés pour ancrer les estimations',
      'Extraction des dépendances, hypothèses et hors-périmètre',
    ],
  },
  {
    n: 'Agent 2',
    name: 'Intégration Jira/Trello & assignation',
    icon: Plug,
    color: '#0EA5E9',
    points: [
      'Création de sprints, d’epics et de tickets via API Jira ou Trello',
      'Matching de compétences par embeddings + équilibrage de charge',
      'Idempotence des appels, rate limiting et traçabilité des écritures',
    ],
  },
  {
    n: 'Agent 3',
    name: 'Analyse & suivi des risques',
    icon: ShieldAlert,
    color: '#1E40AF',
    points: [
      'Vélocité, cycle time, ratio de retard, taux de réouverture de bugs',
      'Lecture NLP des commentaires : détection des signaux faibles',
      'Score de risque par tâche / sprint / projet, avec facteurs contributeurs',
    ],
  },
]

const FEATURES = [
  { icon: FileSearch, title: 'Cadrage en langage naturel', text: 'Décrivez le projet, obtenez une architecture, des lots, des tâches chiffrées et les risques associés.' },
  { icon: Workflow, title: 'Validation humaine obligatoire', text: 'Aucune écriture dans Jira ou Trello sans revue du plan, des tâches et des assignations.' },
  { icon: Shield, title: 'Score de risque expliqué', text: 'Un score par tâche, sprint et projet, accompagné des facteurs qui le justifient et d’une recommandation.' },
  { icon: Users, title: 'Équilibrage de charge', text: 'Assignation initiale par compétences et charge réellement disponible, avec indice d’équilibrage.' },
  { icon: BarChart3, title: 'Supervision unifiée', text: 'Latence, taux d’erreur de format JSON, succès des appels API et scores de risque dans un même tableau de bord.' },
  { icon: GitBranch, title: "Journal d'audit complet", text: 'Qui a fait quoi, quel agent a déclenché quelle action, dans quel ordre — corrélé par identifiant.' },
]

const LIFECYCLE = [
  { step: '01', title: 'Description du projet', text: 'Le chef de projet saisit une description en langage naturel et ses contraintes (budget, délai, équipe).', icon: FileSearch },
  { step: '02', title: 'Découpage proposé', text: 'L’Agent 1 propose architecture, lots, tâches, estimations et risques — ancrés sur l’historique projets.', icon: Network },
  { step: '03', title: 'Revue & validation', text: 'Le chef de projet ajuste, accepte ou rejette le plan, et arbitre les assignations proposées.', icon: Check },
  { step: '04', title: 'Écriture Jira/Trello', text: 'L’Agent 2 crée sprints, epics et tickets, puis applique les assignations validées.', icon: Plug },
  { step: '05', title: 'Surveillance continue', text: 'L’Agent 3 surveille retards, dérive de charge et bugs récurrents, et alerte avec explication.', icon: LineChart },
]

const STATS = [
  { value: '3', label: 'agents spécialisés', sub: 'coordonnés par un orchestrateur' },
  { value: '100 %', label: 'validation humaine', sub: 'avant toute écriture externe' },
  { value: 'CPU', label: 'inférence locale', sub: 'pas de LLM lourd requis' },
  { value: '2', label: 'connecteurs', sub: 'Jira & Trello (+ GitHub en suivi)' },
]

export default function Home() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [scrolled, setScrolled] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <div className="min-h-screen bg-white">
      {/* ============================== Nav ============================== */}
      <header className={cx(
        'fixed inset-x-0 top-0 z-50 transition-all duration-300',
        scrolled ? 'border-b border-slate-200 bg-white/85 backdrop-blur-md' : 'bg-transparent',
      )}>
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-5 sm:px-8">
          <Link to="/"><Logo /></Link>
          <nav className="ml-6 hidden items-center gap-6 lg:flex">
            {[['Plateforme', '#plateforme'], ['Agents', '#agents'], ['Déroulé', '#deroule'], ['Sécurité', '#securite']].map(([l, h]) => (
              <a key={h} href={h} className="text-[13.5px] font-medium text-slate-600 transition hover:text-brand-700">{l}</a>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {user ? (
              <Link to="/app" className="btn btn-primary btn-md">
                Ouvrir mon espace <ArrowRight size={15} />
              </Link>
            ) : (
              <>
                <Link to="/login" className="btn btn-ghost btn-md hidden sm:inline-flex">Connexion</Link>
                <Link to="/signup" className="btn btn-primary btn-md">Essayer la démo</Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* ============================== Hero ============================== */}
      <section className="relative overflow-hidden pt-28 pb-20 sm:pt-36 sm:pb-28">
        <div className="grid-noise absolute inset-0 opacity-70" />
        <div className="absolute -left-40 -top-40 h-[520px] w-[520px] rounded-full bg-brand-200/35 blur-3xl" />
        <div className="absolute -right-32 top-20 h-[420px] w-[420px] rounded-full bg-sky-200/40 blur-3xl" />

        <div className="relative mx-auto grid max-w-7xl items-center gap-14 px-5 sm:px-8 lg:grid-cols-[1.05fr_1fr]">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-[12px] font-semibold text-brand-700">
              <Sparkles size={13} />
              Architecture multi-agents · validation humaine intégrée
            </span>
            <h1 className="mt-5 text-4xl font-bold leading-[1.1] tracking-tight text-slate-900 text-balance sm:text-5xl lg:text-[56px]">
              Le copilote de <span className="gradient-text">cadrage, découpage et pilotage</span> de vos projets
            </h1>
            <p className="mt-5 max-w-xl text-[16px] leading-relaxed text-slate-600">
              Décrivez un projet en langage naturel. Cadria propose une architecture, découpe le travail
              en lots et tâches, estime l’effort, identifie les risques — puis crée les sprints et tickets
              dans Jira ou Trello et surveille en continu la santé du projet.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link to="/signup" className="btn btn-primary btn-lg">
                Démarrer <ArrowRight size={16} />
              </Link>
              <a href="#agents" className="btn btn-secondary btn-lg">
                <Bot size={16} /> Découvrir les agents
              </a>
            </div>

            <div className="mt-9 grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
              {STATS.map((s) => (
                <div key={s.label}>
                  <p className="text-2xl font-bold tracking-tight text-brand-700">{s.value}</p>
                  <p className="mt-0.5 text-[12.5px] font-semibold text-slate-800">{s.label}</p>
                  <p className="text-[11.5px] leading-snug text-slate-500">{s.sub}</p>
                </div>
              ))}
            </div>
          </div>

          {/* ------------------- Aperçu visuel + présentation ------------------- */}
          <div className="space-y-6">
            <HeroMockup />
            <div className="pl-1 sm:pl-4">
              <CadriaGreeter />
            </div>
          </div>
        </div>
      </section>

      {/* ============================ Plateforme ============================ */}
      <section id="plateforme" className="border-y border-slate-200 bg-slate-50/70 py-20">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <span className="badge badge-brand">La plateforme</span>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
              Deux espaces, une même traçabilité
            </h2>
            <p className="mt-3 text-[15px] text-slate-600">
              Un espace projet pour cadrer et piloter au quotidien, un espace administration pour
              gérer les comptes, superviser les agents et suivre la qualité de la plateforme.
            </p>
          </div>

          <div className="mt-12 grid gap-6 lg:grid-cols-2">
            <SpaceCard
              title="Espace client"
              subtitle="Chef de projet & équipe"
              accent="from-brand-600 to-sky-500"
              icon={Workflow}
              items={[
                ['Tableau de bord', 'KPI, vélocité, risques et charge de l’équipe'],
                ['Copilote', 'Lancement des agents, revue et validation des plans'],
                ['Projets & tâches', 'Lots, sprints, kanban, commentaires et historique'],
                ['Notifications', 'Centre unifié, filtres par catégorie et préférences'],
                ['Équipes', 'Membres, compétences, capacité et équilibrage de charge'],
              ]}
            />
            <SpaceCard
              title="Espace administration"
              subtitle="Supervision & gouvernance"
              accent="from-brand-800 to-brand-600"
              icon={Shield}
              items={[
                ['Gestion des comptes', 'Création, édition, rôles, suspension, actions groupées'],
                ['Statistiques', 'Croissance, répartition, santé plateforme et insights qualité'],
                ['Supervision agents', 'Latence, taux d’erreur JSON, succès API, équilibrage'],
                ["Journal d'audit", 'Chaque action, y compris celles déclenchées par un agent'],
                ['Annonces', 'Diffusion ciblée vers tous les utilisateurs ou un rôle'],
              ]}
            />
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="card card-hover p-5">
                <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600">
                  <f.icon size={18} />
                </span>
                <h3 className="mt-3.5 text-[15px] font-semibold text-slate-900">{f.title}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-slate-600">{f.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================== Agents ============================== */}
      <section id="agents" className="relative overflow-hidden py-20 sm:py-28">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-200 to-transparent" />
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
            <div className="lg:sticky lg:top-24">
              <span className="badge badge-brand">Architecture multi-agents</span>
              <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
                Trois agents spécialisés, un orchestrateur
              </h2>
              <p className="mt-4 text-[15px] leading-relaxed text-slate-600">
                Coordination via LangGraph, CrewAI ou AutoGen, avec une étape de validation humaine
                avant toute écriture dans Jira ou Trello : confirmation du chef de projet avant
                création des tickets et des assignations.
              </p>

              <div className="mt-7 rounded-2xl border border-violet-200 bg-violet-50/70 p-5">
                <div className="flex items-start gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white text-violet-600 shadow-sm">
                    <Database size={17} />
                  </span>
                  <div>
                    <p className="text-[13.5px] font-semibold text-violet-900">
                      Emplacements réservés — prêts à brancher
                    </p>
                    <p className="mt-1 text-[12.5px] leading-relaxed text-violet-800/80">
                      Le contrat d’entrée/sortie de chaque agent est figé côté plateforme. Les lancements
                      sont journalisés en statut « réservé » jusqu’au branchement du runtime : aucune
                      inférence n’est simulée.
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {['LangGraph', 'CrewAI', 'AutoGen', 'EvidentlyAI', 'Airflow', 'Grafana'].map((t) => (
                    <span key={t} className="rounded-md bg-white px-2 py-1 text-[11px] font-semibold text-violet-700 ring-1 ring-inset ring-violet-200">
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-5">
              {AGENTS.map((a) => (
                <article key={a.n} className="card card-hover overflow-hidden">
                  <div className="flex items-start gap-4 p-5">
                    <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl text-white shadow-sm"
                          style={{ background: `linear-gradient(135deg, ${a.color}, ${a.color}CC)` }}>
                      <a.icon size={22} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wider text-slate-600">
                          {a.n}
                        </span>
                        <h3 className="text-[16px] font-semibold text-slate-900">{a.name}</h3>
                      </div>
                      <ul className="mt-3 space-y-1.5">
                        {a.points.map((p) => (
                          <li key={p} className="flex gap-2 text-[13px] leading-relaxed text-slate-600">
                            <Check size={14} className="mt-0.5 shrink-0 text-brand-600" /> {p}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ============================= Déroulé ============================= */}
      <section id="deroule" className="border-y border-slate-200 bg-slate-900 py-20 text-white">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="max-w-2xl">
            <span className="badge bg-white/10 text-white ring-1 ring-inset ring-white/20">Cycle de vie</span>
            <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
              De la description libre au projet surveillé
            </h2>
            <p className="mt-3 text-[15px] text-slate-300">
              Chaque étape laisse une trace : le journal d’audit relie l’action, l’agent responsable et l’ordre d’exécution.
            </p>
          </div>

          <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {LIFECYCLE.map((s, i) => (
              <div key={s.step} className="relative rounded-2xl border border-white/10 bg-white/[0.04] p-5 transition hover:border-brand-400/50 hover:bg-white/[0.07]">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold tracking-widest text-brand-400">{s.step}</span>
                  <s.icon size={17} className="text-slate-400" />
                </div>
                <h3 className="mt-3 text-[14.5px] font-semibold text-white">{s.title}</h3>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-slate-400">{s.text}</p>
                {i < LIFECYCLE.length - 1 && (
                  <ChevronRight size={15} className="absolute -right-3 top-1/2 hidden -translate-y-1/2 text-slate-600 lg:block" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ============================ Sécurité ============================ */}
      <section id="securite" className="py-20">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
            <div>
              <span className="badge badge-brand">Gouvernance</span>
              <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
                Traçabilité transverse, du clic à l’appel API
              </h2>
              <p className="mt-4 text-[15px] leading-relaxed text-slate-600">
                Les métriques hétérogènes des trois agents — qualité de génération, qualité d’assignation,
                qualité de prédiction — sont agrégées dans un tableau de bord système unique.
              </p>
              <ul className="mt-6 space-y-3">
                {[
                  ['Score de complétude', 'Taux d’estimations aberrantes et de JSON hors-format, mesurés en continu'],
                  ['Indice d’équilibrage', 'Taux de réassignation manuelle a posteriori comme proxy de qualité'],
                  ['Risque prédit vs. constaté', 'Comparaison au retard effectif du projet pour détecter la dérive'],
                  ['Idempotence', 'Aucune duplication de ticket, gestion du rate limiting et audit de chaque écriture'],
                ].map(([t, d]) => (
                  <li key={t} className="flex gap-3">
                    <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md bg-brand-50 text-brand-600">
                      <Check size={13} />
                    </span>
                    <div>
                      <p className="text-[14px] font-semibold text-slate-900">{t}</p>
                      <p className="text-[13px] text-slate-600">{d}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              {[
                { icon: Lock, title: 'Authentification JWT', text: 'Jetons d’accès courts, refresh rotatif, suspension de compte instantanée.' },
                { icon: Shield, title: 'Rôles & permissions', text: 'Administrateur, chef de projet, membre d’équipe, observateur.' },
                { icon: Zap, title: 'Actions idempotentes', text: 'Une clé de corrélation par exécution d’agent, propagée jusqu’à l’audit.' },
                { icon: Bell, title: 'Notifications ciblées', text: 'Alertes de risque, assignations et validations, par utilisateur ou par rôle.' },
              ].map((c) => (
                <div key={c.title} className="card p-5">
                  <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600">
                    <c.icon size={18} />
                  </span>
                  <h3 className="mt-3 text-[14.5px] font-semibold text-slate-900">{c.title}</h3>
                  <p className="mt-1 text-[12.5px] leading-relaxed text-slate-600">{c.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ============================== CTA ============================== */}
      <section className="px-5 pb-20 sm:px-8">
        <div className="relative mx-auto max-w-6xl overflow-hidden rounded-3xl bg-gradient-to-br from-brand-800 via-brand-700 to-sky-600 px-8 py-14 text-center text-white sm:px-14">
          <div className="grid-noise absolute inset-0 opacity-20" />
          <div className="relative">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Prêt à cadrer votre prochain projet ?</h2>
            <p className="mx-auto mt-3 max-w-xl text-[15px] text-brand-100">
              Créez un compte de démonstration et explorez la plateforme complète : tableau de bord,
              projets, équipes, notifications, espace administration.
            </p>
            <div className="mt-7 flex flex-wrap justify-center gap-3">
              <Link to="/signup" className="btn btn-lg bg-white text-brand-800 hover:bg-brand-50">
                Créer mon compte <ArrowRight size={16} />
              </Link>
              <button onClick={() => navigate('/login')}
                className="btn btn-lg border border-white/30 bg-white/10 text-white backdrop-blur hover:bg-white/20">
                Se connecter à la démo
              </button>
            </div>
            <p className="mt-5 text-[12px] text-brand-200">
              Compte de démonstration : admin@cadria.io · pm@cadria.io · member@cadria.io — mot de passe Cadria@2026
            </p>
          </div>
        </div>
      </section>

      {/* ============================= Footer ============================= */}
      <footer className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 px-5 py-10 sm:px-8 lg:flex-row">
          <div className="flex flex-col items-center gap-2 lg:items-start">
            <Logo />
            <p className="max-w-sm text-center text-[12.5px] text-slate-500 lg:text-left">
              Copilote de cadrage, de découpage et de pilotage de projets.
              React + Django REST, architecture multi-agents avec validation humaine.
            </p>
          </div>
          <div className="flex flex-wrap justify-center gap-x-8 gap-y-2 text-[13px] text-slate-600">
            <a href="#plateforme" className="hover:text-brand-700">Plateforme</a>
            <a href="#agents" className="hover:text-brand-700">Agents</a>
            <a href="#deroule" className="hover:text-brand-700">Déroulé</a>
            <a href="#securite" className="hover:text-brand-700">Gouvernance</a>
            <Link to="/login" className="font-semibold text-brand-700 hover:underline">Connexion</Link>
          </div>
        </div>
        <div className="border-t border-slate-200 py-4 text-center text-[11.5px] text-slate-400">
          © {new Date().getFullYear()} Cadria — Projet de démonstration.
        </div>
      </footer>
    </div>
  )
}

/* --------------------------- Sous-composants --------------------------- */
function SpaceCard({ title, subtitle, items, icon: Icon, accent }) {
  return (
    <div className="card card-hover overflow-hidden">
      <div className={`bg-gradient-to-r px-6 py-5 text-white ${accent}`}>
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-white/15 backdrop-blur">
            <Icon size={19} />
          </span>
          <div>
            <h3 className="text-[17px] font-bold text-white">{title}</h3>
            <p className="text-[12.5px] text-white/80">{subtitle}</p>
          </div>
        </div>
      </div>
      <ul className="divide-y divide-slate-100">
        {items.map(([t, d]) => (
          <li key={t} className="flex items-start gap-3 px-6 py-3.5">
            <Check size={15} className="mt-0.5 shrink-0 text-brand-600" />
            <div>
              <p className="text-[13.5px] font-semibold text-slate-800">{t}</p>
              <p className="text-[12.5px] text-slate-500">{d}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function HeroMockup() {
  return (
    <div className="relative">
      <div className="absolute -inset-4 rounded-[28px] bg-gradient-to-br from-brand-200/40 to-sky-200/40 blur-2xl" />
      <div className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-panel">
        {/* barre de fenêtre */}
        <div className="flex items-center gap-2 border-b border-slate-100 bg-slate-50/80 px-4 py-2.5">
          <span className="flex gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
            <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
          </span>
          <span className="ml-2 truncate text-[11.5px] text-slate-500">cadria.io/app · Refonte du portail client</span>
        </div>

        <div className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-brand-600">PRJ-0001 · Scrum</p>
              <h3 className="mt-0.5 text-[15px] font-bold text-slate-900">Refonte du portail client</h3>
            </div>
            <span className="badge badge-warning">À surveiller</span>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-2.5">
            {[['Avancement', '64 %', '#2563EB'], ['Charge', '1 240 h', '#0EA5E9'], ['Risque', '38/100', '#F59E0B']].map(([l, v, c]) => (
              <div key={l} className="rounded-lg border border-slate-100 bg-slate-50/70 p-2.5">
                <p className="text-[10.5px] text-slate-500">{l}</p>
                <p className="mt-0.5 text-[15px] font-bold" style={{ color: c }}>{v}</p>
              </div>
            ))}
          </div>

          {/* mini barres */}
          <div className="mt-4 rounded-lg border border-slate-100 p-3">
            <p className="mb-2.5 text-[11.5px] font-semibold text-slate-700">Charge par lot</p>
            {[['Cadrage & conception UX', 92, '#1D4ED8'], ['Refonte front-end', 74, '#2563EB'],
              ['API publique', 61, '#0EA5E9'], ['SSO & sécurité', 43, '#38BDF8']].map(([l, v, c]) => (
              <div key={l} className="mb-2 flex items-center gap-2 last:mb-0">
                <span className="w-[112px] shrink-0 truncate text-[10.5px] text-slate-500">{l}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <span className="block h-full rounded-full" style={{ width: `${v}%`, background: c }} />
                </span>
                <span className="w-7 text-right text-[10.5px] font-semibold text-slate-600">{v}%</span>
              </div>
            ))}
          </div>

          {/* alerte agent */}
          <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-violet-200 bg-violet-50/70 p-3">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-white text-violet-600 shadow-sm">
              <ShieldAlert size={14} />
            </span>
            <div className="min-w-0">
              <p className="text-[12px] font-semibold text-violet-900">Agent 3 · Risque de retard détecté</p>
              <p className="mt-0.5 text-[11px] leading-relaxed text-violet-800/80">
                Écart estimé/réalisé +42 % sur « API publique » · 2 tâches bloquées · vélocité −18 %
              </p>
            </div>
          </div>

          <div className="mt-4 flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50/70 p-2.5">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand-600 text-white">
              <Sparkles size={13} />
            </span>
            <p className="flex-1 text-[11.5px] text-slate-600">Plan v2 · 24 tâches proposées</p>
            <span className="badge badge-warning">À valider</span>
          </div>
        </div>
      </div>

      {/* cartes flottantes */}
      <div className="absolute -bottom-5 -left-4 hidden animate-fade-in rounded-xl border border-slate-200 bg-white p-3 shadow-panel sm:block">
        <div className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-emerald-50 text-emerald-600"><Check size={15} /></span>
          <div>
            <p className="text-[11.5px] font-semibold text-slate-800">Plan validé</p>
            <p className="text-[10.5px] text-slate-500">24 tâches créées dans Jira</p>
          </div>
        </div>
      </div>
      <div className="absolute -right-3 -top-5 hidden animate-fade-in rounded-xl border border-slate-200 bg-white p-3 shadow-panel sm:block">
        <div className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-50 text-brand-600"><Users size={15} /></span>
          <div>
            <p className="text-[11.5px] font-semibold text-slate-800">Charge équilibrée</p>
            <p className="text-[10.5px] text-slate-500">Indice 0,82</p>
          </div>
        </div>
      </div>
    </div>
  )
}
