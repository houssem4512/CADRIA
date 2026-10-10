import { Link } from 'react-router-dom'
import { ArrowLeft, Compass, Home, LayoutDashboard } from 'lucide-react'
import { Logo } from '../components/Logo'
import { useAuth } from '../context/AuthContext'

export default function NotFound() {
  const { user } = useAuth()
  return (
    <div className="grid-noise grid min-h-screen place-items-center bg-slate-50 px-5">
      <div className="w-full max-w-lg text-center">
        <div className="mx-auto w-fit"><Logo size={38} /></div>
        <p className="mt-8 text-[86px] font-bold leading-none tracking-tighter gradient-text">404</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">Page introuvable</h1>
        <p className="mx-auto mt-3 max-w-sm text-[14px] leading-relaxed text-slate-600">
          Cette page n’existe pas ou n’est plus accessible. Vérifiez l’adresse, ou repartez
          de votre tableau de bord.
        </p>
        <div className="mt-7 flex flex-wrap justify-center gap-2.5">
          <Link to={user ? '/app' : '/'} className="btn btn-primary btn-lg">
            {user ? <LayoutDashboard size={16} /> : <Home size={16} />}
            {user ? 'Mon tableau de bord' : 'Accueil'}
          </Link>
          <Link to="/" className="btn btn-secondary btn-lg">
            <Compass size={16} /> Découvrir la plateforme
          </Link>
        </div>
        <Link to="/" className="mt-8 inline-flex items-center gap-1.5 text-[13px] font-medium text-slate-500 hover:text-brand-700">
          <ArrowLeft size={14} /> Retour
        </Link>
      </div>
    </div>
  )
}
