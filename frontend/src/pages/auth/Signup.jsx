import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, ArrowRight, Building2, Briefcase, Check, Eye, EyeOff, KeyRound, Lock,
  Mail, Phone, Sparkles, User, UserPlus, Users,
} from 'lucide-react'
import { Logo } from '../../components/Logo'
import { Button, Input, Select, Alert } from '../../components/ui'
import { useAuth } from '../../context/AuthContext'
import api, { errorMessage, fieldErrors } from '../../lib/api'
import { cx } from '../../lib/format'

const ROLES = [
  { value: 'PM', label: 'Chef de projet', desc: 'Cadre les projets, lance les agents et valide les plans' },
  { value: 'MEMBER', label: 'Membre d’équipe', desc: 'Travaille sur les tâches assignées et suit sa charge' },
  { value: 'VIEWER', label: 'Observateur', desc: 'Consulte les projets, indicateurs et rapports de risque' },
]

const STEPS = [
  { icon: UserPlus, title: '1 · Créez votre compte', text: 'Un e-mail et un mot de passe suffisent pour ouvrir un espace complet.' },
  { icon: Sparkles, title: '2 · Décrivez votre projet', text: 'Saisissez le projet en langage naturel, avec ses contraintes et son équipe.' },
  { icon: Check, title: '3 · Validez le découpage', text: 'Revue des lots, tâches et assignations avant toute écriture externe.' },
]

function score(p) {
  let s = 0
  if (p.length >= 8) s++
  if (p.length >= 12) s++
  if (/[A-Z]/.test(p) && /[a-z]/.test(p)) s++
  if (/\d/.test(p)) s++
  if (/[^A-Za-z0-9]/.test(p)) s++
  return s
}

export default function Signup() {
  const { register, user } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    first_name: '', last_name: '', email: '', company: '', job_title: '',
    phone: '', role: 'PM', password: '', password_confirm: '',
  })
  const [errors, setErrors] = useState({})
  const [globalError, setGlobalError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPwd, setShowPwd] = useState(false)
  const [mode, setMode] = useState('signup') // signup | forgot | reset
  const [forgot, setForgot] = useState({ email: '', code: '', new_password: '', sentCode: '' })
  const [forgotMsg, setForgotMsg] = useState('')

  useEffect(() => { if (user) navigate('/app', { replace: true }) }, [user, navigate])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const strength = score(form.password)

  const submit = async (e) => {
    e.preventDefault()
    setErrors({}); setGlobalError(''); setLoading(true)
    try {
      await register(form)
      navigate('/app', { replace: true })
    } catch (err) {
      setGlobalError(errorMessage(err, 'Impossible de créer le compte.'))
      setErrors(fieldErrors(err))
    } finally {
      setLoading(false)
    }
  }

  /* ------------------------- Réinitialisation ------------------------- */
  const requestCode = async (e) => {
    e.preventDefault()
    setForgotMsg(''); setErrors({})
    try {
      const { data } = await api.post('/auth/password/reset/', { email: forgot.email })
      setForgotMsg(`${data.detail || 'Code envoyé.'}${data.demo_code ? ` Code de démonstration : ${data.demo_code}` : ''}`)
      setForgot((f) => ({ ...f, sentCode: data.demo_code || '', code: data.demo_code || f.code }))
    } catch (err) {
      setGlobalError(errorMessage(err))
    }
  }

  const resetPassword = async (e) => {
    e.preventDefault()
    setForgotMsg(''); setErrors({})
    try {
      await api.post('/auth/password/reset/confirm/', {
        email: forgot.email, code: forgot.code, new_password: forgot.new_password,
      })
      setForgotMsg('Mot de passe réinitialisé — vous pouvez vous connecter.')
      setTimeout(() => navigate('/login'), 1400)
    } catch (err) {
      setGlobalError(errorMessage(err))
      setErrors(fieldErrors(err))
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      {/* ------------------------- Formulaire ------------------------- */}
      <main className="flex items-center justify-center overflow-y-auto bg-slate-50 px-5 py-10 sm:px-10">
        <div className="w-full max-w-[520px]">
          <div className="lg:hidden"><Link to="/"><Logo size={34} /></Link></div>

          <Link to="/login" className="mt-6 inline-flex items-center gap-1.5 text-[13px] font-medium text-slate-500 hover:text-brand-700 lg:mt-0">
            <ArrowLeft size={14} /> J’ai déjà un compte
          </Link>

          {mode === 'signup' && (
            <>
              <h2 className="mt-5 text-2xl font-bold tracking-tight text-slate-900">Créer votre espace Cadria</h2>
              <p className="mt-1.5 text-[14px] text-slate-500">
                Gratuit, sans engagement — explorez la plateforme complète avec des données de démonstration.
              </p>

              {globalError && <Alert tone="error" title="Inscription impossible" className="mt-5">{globalError}</Alert>}

              <form onSubmit={submit} className="mt-6 space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="Prénom" icon={User} required autoComplete="given-name" placeholder="Yassine"
                         value={form.first_name} onChange={set('first_name')} error={errors.first_name} />
                  <Input label="Nom" icon={User} required autoComplete="family-name" placeholder="Trabelsi"
                         value={form.last_name} onChange={set('last_name')} error={errors.last_name} />
                </div>

                <Input label="Adresse e-mail professionnelle" type="email" icon={Mail} required
                       autoComplete="email" placeholder="vous@entreprise.com"
                       value={form.email} onChange={set('email')} error={errors.email} />

                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="Organisation" icon={Building2} placeholder="Cadria"
                         value={form.company} onChange={set('company')} error={errors.company} />
                  <Input label="Poste" icon={Briefcase} placeholder="Chef de projet"
                         value={form.job_title} onChange={set('job_title')} error={errors.job_title} />
                </div>

                <Input label="Téléphone (facultatif)" icon={Phone} placeholder="+216 22 000 000"
                       value={form.phone} onChange={set('phone')} error={errors.phone} />

                <div>
                  <label className="label">Votre rôle</label>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {ROLES.map((r) => (
                      <button key={r.value} type="button" onClick={() => setForm({ ...form, role: r.value })}
                        className={cx(
                          'rounded-lg border px-3 py-2.5 text-left transition',
                          form.role === r.value
                            ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-500/20'
                            : 'border-slate-200 bg-white hover:border-slate-300',
                        )}>
                        <span className="flex items-center gap-1.5 text-[12.5px] font-semibold text-slate-800">
                          {form.role === r.value && <Check size={13} className="text-brand-600" />}
                          {r.label}
                        </span>
                        <span className="mt-1 block text-[11px] leading-snug text-slate-500">{r.desc}</span>
                      </button>
                    ))}
                  </div>
                  {errors.role && <p className="error-text">{errors.role}</p>}
                  <p className="hint">Le rôle administrateur est attribué par un administrateur existant.</p>
                </div>

                <div>
                  <label className="label">Mot de passe</label>
                  <div className="relative">
                    <Lock size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input type={showPwd ? 'text' : 'password'} required autoComplete="new-password"
                      placeholder="8 caractères minimum" value={form.password} onChange={set('password')}
                      className={`field pl-9 pr-10 ${errors.password ? 'field-error' : ''}`} />
                    <button type="button" onClick={() => setShowPwd((s) => !s)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
                      {showPwd ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                  {form.password && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className="flex flex-1 gap-1">
                        {[0, 1, 2, 3, 4].map((i) => (
                          <span key={i} className={cx('h-1 flex-1 rounded-full transition',
                            i < strength ? (strength <= 2 ? 'bg-rose-400' : strength === 3 ? 'bg-amber-400' : 'bg-emerald-500') : 'bg-slate-200')} />
                        ))}
                      </span>
                      <span className="text-[11px] font-medium text-slate-500">
                        {strength <= 2 ? 'Faible' : strength === 3 ? 'Correct' : 'Solide'}
                      </span>
                    </div>
                  )}
                  {errors.password && <p className="error-text">{errors.password}</p>}
                </div>

                <Input label="Confirmer le mot de passe" type={showPwd ? 'text' : 'password'} icon={KeyRound}
                       required autoComplete="new-password" placeholder="••••••••"
                       value={form.password_confirm} onChange={set('password_confirm')}
                       error={errors.password_confirm} />

                <Button type="submit" size="lg" loading={loading} className="w-full">
                  {loading ? 'Création…' : <>Créer mon compte <ArrowRight size={16} /></>}
                </Button>

                <p className="text-center text-[12px] leading-relaxed text-slate-500">
                  En créant un compte, vous acceptez d’utiliser Cadria dans un cadre de démonstration.
                  Les données saisies restent dans votre environnement.
                </p>
              </form>

              <p className="mt-6 text-center text-[13.5px] text-slate-600">
                Déjà inscrit ?{' '}
                <Link to="/login" className="font-semibold text-brand-700 hover:underline">Se connecter</Link>
              </p>
            </>
          )}

          {/* --------------------- Mot de passe oublié --------------------- */}
          {mode !== 'signup' && (
            <>
              <h2 className="mt-5 text-2xl font-bold tracking-tight text-slate-900">Réinitialiser le mot de passe</h2>
              <p className="mt-1.5 text-[14px] text-slate-500">
                Saisissez votre e-mail pour recevoir un code de vérification à 6 chiffres.
              </p>

              {globalError && <Alert tone="error" className="mt-5">{globalError}</Alert>}
              {forgotMsg && <Alert tone="success" className="mt-5">{forgotMsg}</Alert>}

              {mode === 'forgot' ? (
                <form onSubmit={requestCode} className="mt-6 space-y-4">
                  <Input label="Adresse e-mail" type="email" icon={Mail} required
                         placeholder="vous@entreprise.com" value={forgot.email}
                         onChange={(e) => setForgot({ ...forgot, email: e.target.value })} />
                  <Button type="submit" size="lg" className="w-full">Envoyer le code</Button>
                  <p className="hint text-center">
                    Aucun serveur SMTP n’est configuré en démonstration : le code est renvoyé directement dans la réponse.
                  </p>
                </form>
              ) : (
                <form onSubmit={resetPassword} className="mt-6 space-y-4">
                  <Input label="Adresse e-mail" type="email" icon={Mail} required
                         value={forgot.email} onChange={(e) => setForgot({ ...forgot, email: e.target.value })} />
                  <Input label="Code à 6 chiffres" icon={KeyRound} required maxLength={6}
                         placeholder="123456" value={forgot.code} error={errors.code}
                         onChange={(e) => setForgot({ ...forgot, code: e.target.value })} />
                  <Input label="Nouveau mot de passe" type="password" icon={Lock} required
                         autoComplete="new-password" value={forgot.new_password} error={errors.new_password}
                         onChange={(e) => setForgot({ ...forgot, new_password: e.target.value })} />
                  <Button type="submit" size="lg" className="w-full">Réinitialiser</Button>
                </form>
              )}

              <div className="mt-5 flex items-center justify-between text-[13px]">
                <button onClick={() => { setMode(mode === 'forgot' ? 'reset' : 'forgot'); setGlobalError('') }}
                  className="font-semibold text-brand-700 hover:underline">
                  {mode === 'forgot' ? 'J’ai déjà un code' : 'Renvoyer un code'}
                </button>
                <button onClick={() => { setMode('signup'); setGlobalError('') }}
                  className="font-medium text-slate-500 hover:text-slate-800">
                  Retour à l’inscription
                </button>
              </div>
            </>
          )}
        </div>
      </main>

      {/* ------------------------- Panneau droit ------------------------- */}
      <aside className="relative hidden overflow-hidden bg-gradient-to-br from-brand-800 via-brand-700 to-sky-600 p-12 text-white lg:flex lg:flex-col">
        <div className="grid-noise absolute inset-0 opacity-20" />
        <div className="absolute -left-20 top-1/4 h-80 w-80 rounded-full bg-sky-400/25 blur-3xl" />

        <div className="relative flex items-center justify-between">
          <Link to="/"><Logo variant="white" /></Link>
          <span className="badge bg-white/10 text-white ring-1 ring-inset ring-white/20">
            <Users size={12} /> Démo complète
          </span>
        </div>

        <div className="relative mt-auto">
          <h2 className="text-[32px] font-bold leading-tight tracking-tight text-balance">
            Trois étapes entre une idée et un projet piloté
          </h2>
          <div className="mt-8 space-y-4">
            {STEPS.map((s) => (
              <div key={s.title} className="flex gap-4 rounded-xl border border-white/15 bg-white/[0.07] p-4 backdrop-blur">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-white/15">
                  <s.icon size={17} />
                </span>
                <div>
                  <p className="text-[13.5px] font-semibold text-white">{s.title}</p>
                  <p className="mt-0.5 text-[12.5px] leading-relaxed text-brand-100">{s.text}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="relative mt-10 text-[12px] text-brand-200">
          Compte administrateur de démonstration : <b>admin@cadria.io</b> / Cadria@2026
        </p>
      </aside>
    </div>
  )
}
