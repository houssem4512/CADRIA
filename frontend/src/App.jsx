import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import AppLayout from './components/layout/AppLayout'
import { ToastStack } from './components/Toast'
import { Logo } from './components/Logo'

// Public
const Home = lazy(() => import('./pages/Home'))
const Login = lazy(() => import('./pages/auth/Login'))
const Signup = lazy(() => import('./pages/auth/Signup'))
const NotFound = lazy(() => import('./pages/NotFound'))

// Espace client / chef de projet
const Dashboard = lazy(() => import('./pages/app/Dashboard'))
const Projects = lazy(() => import('./pages/app/Projects'))
const ProjectNew = lazy(() => import('./pages/app/ProjectNew'))
const ProjectDetail = lazy(() => import('./pages/app/ProjectDetail'))
const MyTasks = lazy(() => import('./pages/app/MyTasks'))
const Agents = lazy(() => import('./pages/app/Agents'))
const Teams = lazy(() => import('./pages/app/Teams'))
const NotificationCenter = lazy(() => import('./pages/app/NotificationCenter'))
const History = lazy(() => import('./pages/app/History'))
const Profile = lazy(() => import('./pages/app/Profile'))

// Espace admin
const AdminOverview = lazy(() => import('./pages/admin/Overview'))
const AdminUsers = lazy(() => import('./pages/admin/Users'))
const AdminProjects = lazy(() => import('./pages/admin/Projects'))
const AdminAgents = lazy(() => import('./pages/admin/Agents'))
const AdminAudit = lazy(() => import('./pages/admin/Audit'))
const AdminAnnouncements = lazy(() => import('./pages/admin/Announcements'))
const AdminSettings = lazy(() => import('./pages/admin/Settings'))

function Boot() {
  return (
    <div className="grid min-h-screen place-items-center bg-slate-50">
      <div className="flex flex-col items-center gap-4">
        <Logo size={40} />
        <div className="h-1 w-40 overflow-hidden rounded-full bg-slate-200">
          <div className="h-full w-1/2 animate-pulse rounded-full bg-brand-600" />
        </div>
      </div>
    </div>
  )
}

/** Garde d'accès : redirige vers /login si non authentifié. */
function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Boot />
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />
  return children
}

/** Garde admin : réservé au rôle ADMIN / superuser. */
function RequireAdmin({ children }) {
  const { user, loading, isAdmin } = useAuth()
  const location = useLocation()
  if (loading) return <Boot />
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />
  if (!isAdmin) return <Navigate to="/app" replace />
  return children
}

/** Garde espace client : l'administrateur n'a que l'espace admin. */
function RequireClient({ children }) {
  const { user, loading, isAdmin } = useAuth()
  const location = useLocation()
  if (loading) return <Boot />
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />
  if (isAdmin) return <Navigate to="/admin" replace />
  return children
}

/** Garde pilotage : création de projets, agents, équipes — chefs de projet uniquement. */
function RequirePilot({ children }) {
  const { user, loading, canPilot, isAdmin } = useAuth()
  if (loading) return <Boot />
  if (!user) return <Navigate to="/login" replace />
  if (isAdmin) return <Navigate to="/admin" replace />
  if (!canPilot) return <Navigate to="/app" replace />
  return children
}

export default function App() {
  return (
    <>
      <Suspense fallback={<Boot />}>
        <Routes>
          {/* ------------------------- Public ------------------------- */}
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          {/* ---------------------- Espace client ---------------------- */}
          <Route path="/app" element={<RequireClient><AppLayout mode="client" /></RequireClient>}>
            <Route index element={<Dashboard />} />
            <Route path="projects" element={<Projects />} />
            <Route path="projects/new" element={<RequirePilot><ProjectNew /></RequirePilot>} />
            <Route path="projects/:id" element={<ProjectDetail />} />
            <Route path="projects/:id/:tab" element={<ProjectDetail />} />
            <Route path="tasks" element={<MyTasks />} />
            <Route path="agents" element={<RequirePilot><Agents /></RequirePilot>} />
            <Route path="teams" element={<RequirePilot><Teams /></RequirePilot>} />
            <Route path="notifications" element={<NotificationCenter />} />
            <Route path="history" element={<RequirePilot><History /></RequirePilot>} />
            <Route path="profile" element={<Profile />} />
          </Route>

          {/* ---------------------- Espace admin ----------------------- */}
          <Route path="/admin" element={<RequireAdmin><AppLayout mode="admin" /></RequireAdmin>}>
            <Route index element={<AdminOverview />} />
            <Route path="users" element={<AdminUsers />} />
            <Route path="projects" element={<AdminProjects />} />
            <Route path="agents" element={<AdminAgents />} />
            <Route path="audit" element={<AdminAudit />} />
            <Route path="announcements" element={<AdminAnnouncements />} />
            <Route path="settings" element={<AdminSettings />} />
          </Route>

          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
      <ToastStack />
    </>
  )
}
