import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Check, Eye, EyeOff, Lock, LogIn, Mail, ShieldCheck, Sparkles } from 'lucide-react'
import { Logo } from '../../components/Logo'
import { Button, Input, Alert } from '../../components/ui'
import { useAuth } from '../../context/AuthContext'
import { errorMessage, fieldErrors } from '../../lib/api'

const DEMO_ACCOUNTS = [
  { email: 'admin@cadria.io', label: 'Administrateur', role: 'ADMIN', desc: 'Comptes, statistiques, supervision agents, audit' },
  { email: 'pm@cadria.io', label: 'Chef de projet', role: 'PM', desc: 'Projets, lancement des agents, validation des plans' },
  { email: 'member@cadria.io', label: 'Membre d’équipe', role: 'MEMBER', desc: 'Mes tâches, charge, notifications' },
]

const HIGHLIGHTS = [
  'Découpage automatique en lots, tâches et estimations',
  'Validation humaine avant toute écriture Jira / Trello',
  'Score de risque expliqué par projet, sprint et tâche',
  "Journal d'audit complet, y compris les actions des agents",
]

export default function Login() {
  const { login, user } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [form, setForm] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [globalError, setGlobalError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPwd, setShowPwd] = useState(false)
  const [notice, setNotice] = useState(params.get('expired') ? 'Votre session a expiré, reconnectez-vous.' : '')

  useEffect(() => {
    if (user) {
      // Chaque rôle reste dans son espace : admin → /admin, autres → /app.
      const home = user.role === 'ADMIN' || user.is_superuser ? '/admin' : '/app'
      const next = params.get('next')
      navigate(next && next.startsWith(home) ? next : home, { replace: true })
    }
  }, [user, navigate, params])

  const submit = async (e) => {
    e.preventDefault()
    setErrors({}); setGlobalError(''); setLoading(true)
    try {
      const u = await login(form.email.trim(), form.password)
      const home = u.role === 'ADMIN' || u.is_superuser ? '/admin' : '/app'
      const next = params.get('next')
      navigate(next && next.startsWith(home) ? next : home, { replace: true })
    } catch (err) {
      setGlobalError(errorMessage(err, 'Impossible de se connecter.'))
      setErrors(fieldErrors(err))
    } finally {
      setLoading(false)
    }
  }

  const useDemo = (email) => {
    setForm({ email, password: 'Cadria@2026' })
    setGlobalError(''); setErrors({})
    setNotice('Identifiants pré-remplis — cliquez sur « Se connecter ».')
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_1.05fr]">
      {/* ------------------------- Panneau gauche ------------------------- */}
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-brand-900 via-brand-800 to-brand-600 p-12 text-white lg:flex lg:flex-col">
        <div className="grid-noise absolute inset-0 opacity-20" />
        <div className="absolute -right-24 top-1/3 h-80 w-80 rounded-full bg-sky-400/25 blur-3xl" />
        <div className="absolute -left-16 bottom-0 h-72 w-72 rounded-full bg-brand-400/20 blur-3xl" />

        <div className="relative">
          <Link to="/"><Logo variant="white" /></Link>
        </div>

        <div className="relative mt-auto max-w-lg">
          <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-[12px] font-semibold ring-1 ring-inset ring-white/20">
            <Sparkles size={13} /> Copilote multi-agents
          </span>
          <h1 className="mt-5 text-[38px] font-bold leading-[1.12] tracking-tight text-balance">
            Cadrez, découpez et pilotez vos projets avec un copilote IA
          </h1>
          <p className="mt-4 text-[15px] leading-relaxed text-brand-100">
            Décrivez le projet en langage naturel : obtenez une architecture, des tâches chiffrées,
            une première assignation et une surveillance continue des risques.
          </p>

          <ul className="mt-8 space-y-2.5">
            {HIGHLIGHTS.map((h) => (
              <li key={h} className="flex items-start gap-2.5 text-[13.5px] text-brand-50">
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-white/15">
                  <Check size={12} />
                </span>
                {h}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative mt-10 flex items-center gap-3 rounded-xl border border-white/15 bg-white/[0.07] p-4 backdrop-blur">
          <ShieldCheck size={18} className="shrink-0 text-sky-300" />
          <p className="text-[12.5px] leading-relaxed text-brand-100">
            Aucune écriture dans Jira ou Trello sans validation humaine : le chef de projet confirme
            le plan, les tâches et les assignations avant création des tickets.
          </p>
        </div>
      </aside>

      {/* ------------------------- Formulaire ------------------------- */}
      <main className="flex items-center justify-center overflow-y-auto bg-slate-50 px-5 py-10 sm:px-10">
        <div className="w-full max-w-[440px]">
          <div className="lg:hidden">
            <Link to="/"><Logo size={34} /></Link>
          </div>

          <Link to="/" className="mt-6 inline-flex items-center gap-1.5 text-[13px] font-medium text-slate-500 hover:text-brand-700 lg:mt-0">
            <ArrowLeft size={14} /> Retour à l’accueil
          </Link>

          <h2 className="mt-5 text-2xl font-bold tracking-tight text-slate-900">Bon retour parmi nous</h2>
          <p className="mt-1.5 text-[14px] text-slate-500">Connectez-vous pour accéder à votre espace Cadria.</p>

          {notice && (
            <Alert tone="info" className="mt-5">
              {notice}
              <button onClick={() => setNotice('')} className="ml-2 font-semibold underline">OK</button>
            </Alert>
          )}
          {globalError && <Alert tone="error" title="Connexion impossible" className="mt-5">{globalError}</Alert>}

          <form onSubmit={submit} className="mt-6 space-y-4">
            <Input
              label="Adresse e-mail" type="email" autoComplete="email" required
              icon={Mail} placeholder="vous@entreprise.com"
              value={form.email} error={errors.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            <div>
              <div className="flex items-center justify-between">
                <label className="label mb-1.5">Mot de passe</label>
                <Link to="/signup?mode=forgot" className="mb-1.5 text-[12px] font-medium text-brand-600 hover:underline">
                  Mot de passe oublié ?
                </Link>
              </div>
              <div className="relative">
                <Lock size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type={showPwd ? 'text' : 'password'} required autoComplete="current-password"
                  placeholder="••••••••" value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className={`field pl-9 pr-10 ${errors.password ? 'field-error' : ''}`}
                />
                <button type="button" onClick={() => setShowPwd((s) => !s)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
                  {showPwd ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              {errors.password && <p className="error-text">{errors.password}</p>}
            </div>

            <Button type="submit" size="lg" loading={loading} className="w-full">
              {loading ? 'Connexion…' : <>Se connecter <ArrowRight size={16} /></>}
            </Button>
          </form>

          <p className="mt-6 text-center text-[13.5px] text-slate-600">
            Pas encore de compte ?{' '}
            <Link to="/signup" className="font-semibold text-brand-700 hover:underline">Créer un compte</Link>
          </p>

          {/* ------------------- Comptes de démonstration ------------------- */}
          <div className="mt-8 rounded-xl border border-slate-200 bg-white p-4">
            <p className="flex items-center gap-2 text-[12.5px] font-semibold text-slate-700">
              <Sparkles size={14} className="text-brand-600" /> Comptes de démonstration
            </p>
            <p className="mt-1 text-[11.5px] text-slate-500">
              Mot de passe commun : <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">Cadria@2026</code>
            </p>
            <div className="mt-3 space-y-1.5">
              {DEMO_ACCOUNTS.map((a) => (
                <button key={a.email} type="button" onClick={() => useDemo(a.email)}
                  className="flex w-full items-center gap-3 rounded-lg border border-slate-200 px-3 py-2.5 text-left transition hover:border-brand-300 hover:bg-brand-50/50">
                  <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg text-white ${
                    a.role === 'ADMIN' ? 'bg-brand-800' : a.role === 'PM' ? 'bg-brand-600' : 'bg-sky-500'}`}>
                    {a.role === 'ADMIN' ? <ShieldCheck size={15} /> : a.role === 'PM' ? <Sparkles size={15} /> : <LogIn size={15} />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[13px] font-semibold text-slate-800">{a.label}</span>
                    <span className="block truncate text-[11.5px] text-slate-500">{a.desc}</span>
                  </span>
                  <ArrowRight size={14} className="shrink-0 text-slate-300" />
                </button>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
