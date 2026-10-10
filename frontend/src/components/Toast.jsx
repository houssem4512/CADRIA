import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Bell, CheckCircle2, Info, Sparkles, TriangleAlert, X, XCircle } from 'lucide-react'
import { useNotifications } from '../context/NotificationContext'
import { cx, NOTIF_LEVEL } from '../lib/format'

const ICONS = {
  INFO: Info, SUCCESS: CheckCircle2, WARNING: TriangleAlert,
  ERROR: XCircle, AGENT: Sparkles,
}

const TONES = {
  INFO: 'border-sky-200 bg-white text-sky-700',
  SUCCESS: 'border-emerald-200 bg-white text-emerald-700',
  WARNING: 'border-amber-200 bg-white text-amber-700',
  ERROR: 'border-rose-200 bg-white text-rose-700',
  AGENT: 'border-violet-200 bg-white text-violet-700',
}

function Toast({ toast, onDismiss }) {
  useEffect(() => {
    const t = setTimeout(() => onDismiss(toast._key), 7000)
    return () => clearTimeout(t)
  }, [toast._key, onDismiss])

  const Icon = ICONS[toast.level] || Bell
  const tone = TONES[toast.level] || TONES.INFO
  const body = (
    <>
      <p className="text-[13px] font-semibold text-slate-900">{toast.title}</p>
      {toast.message && <p className="mt-0.5 line-clamp-2 text-[12px] text-slate-500">{toast.message}</p>}
    </>
  )

  return (
    <div className={cx(
      'pointer-events-auto flex w-[340px] max-w-[calc(100vw-2rem)] animate-slide-in gap-3 rounded-xl border px-4 py-3 shadow-panel',
      tone,
    )}>
      <span className="mt-0.5 shrink-0"><Icon size={17} /></span>
      <div className="min-w-0 flex-1">
        {toast.link ? <Link to={toast.link} onClick={() => onDismiss(toast._key)} className="block">{body}</Link> : body}
      </div>
      <button onClick={() => onDismiss(toast._key)}
        className="-mr-1 -mt-1 h-6 w-6 shrink-0 rounded text-slate-400 transition hover:bg-slate-100 hover:text-slate-600">
        <X size={14} />
      </button>
    </div>
  )
}

/** Pile de notifications flottantes (bas-droite). */
export function ToastStack() {
  const { toasts, dismissToast } = useNotifications()
  if (!toasts.length) return null
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-[70] flex flex-col gap-2">
      {toasts.map((t) => <Toast key={t._key} toast={t} onDismiss={dismissToast} />)}
    </div>
  )
}

export default ToastStack
