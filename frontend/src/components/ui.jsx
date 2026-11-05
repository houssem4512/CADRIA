import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, Check, CheckCircle2, ChevronDown, ChevronLeft, ChevronRight,
  Info, Loader2, Search, X, XCircle,
} from 'lucide-react'
import { cx, initials } from '../lib/format'

/* ============================== Card ============================== */
export function Card({ children, className, hover, onClick, ...rest }) {
  return (
    <div onClick={onClick} className={cx('card', hover && 'card-hover', onClick && 'cursor-pointer', className)} {...rest}>
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, action, icon: Icon, className }) {
  return (
    <div className={cx('card-header', className)}>
      <div className="flex items-start gap-3 min-w-0">
        {Icon && (
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
            <Icon size={17} />
          </span>
        )}
        <div className="min-w-0">
          <h3 className="card-title truncate">{title}</h3>
          {subtitle && <p className="card-subtitle">{subtitle}</p>}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

/* ============================== Badge ============================== */
export function Badge({ children, className = 'badge-neutral', dot, ...rest }) {
  return (
    <span className={cx('badge', className)} {...rest}>
      {dot && <span className={cx('h-1.5 w-1.5 rounded-full', dot)} />}
      {children}
    </span>
  )
}

/* ============================== Button ============================== */
export function Button({
  children, variant = 'primary', size = 'md', icon: Icon, iconRight, loading, className, ...rest
}) {
  return (
    <button
      className={cx('btn', `btn-${size}`, `btn-${variant}`, className)}
      disabled={loading || rest.disabled}
      {...rest}
    >
      {loading ? <Loader2 size={15} className="animate-spin" /> : Icon && <Icon size={15} />}
      {children}
      {iconRight && !loading && <ChevronRight size={15} />}
    </button>
  )
}

export function IconButton({ icon: Icon, label, className, ...rest }) {
  return (
    <button title={label} aria-label={label}
      className={cx('btn btn-ghost btn-icon rounded-lg', className)} {...rest}>
      <Icon size={17} />
    </button>
  )
}

/* ============================== Avatar ============================== */
export function Avatar({ name = '', src, color, size = 36, className, ring }) {
  const [failed, setFailed] = useState(false)
  const c = color || '#2563EB'
  const style = {
    width: size, height: size, fontSize: Math.max(10, size * 0.36),
    background: src && !failed ? 'transparent' : `linear-gradient(135deg, ${c}, ${c}CC)`,
  }
  return (
    <span
      style={style}
      className={cx(
        'inline-grid shrink-0 place-items-center rounded-full font-semibold text-white uppercase',
        ring && 'ring-2 ring-white',
        className,
      )}
      title={name}
    >
      {src && !failed
        ? <img src={src} alt={name} onError={() => setFailed(true)}
               className="h-full w-full rounded-full object-cover" />
        : initials(name)}
    </span>
  )
}

export function AvatarStack({ people = [], size = 28, max = 4, showNames = false }) {
  const shown = people.slice(0, max)
  const rest = people.length - shown.length
  return (
    <div className="flex items-center">
      <div className="flex -space-x-2">
        {shown.map((p, i) => (
          <Avatar key={p.id ?? i} name={p.full_name || p.name || p.email}
                  color={p.avatar_color || p.color} size={size} ring />
        ))}
      </div>
      {rest > 0 && (
        <span style={{ width: size, height: size, fontSize: size * 0.34 }}
          className="ml-[-8px] inline-grid place-items-center rounded-full bg-slate-200 font-semibold text-slate-600 ring-2 ring-white">
          +{rest}
        </span>
      )}
      {showNames && (
        <span className="ml-3 text-xs text-slate-500">
          {people.slice(0, 2).map((p) => p.full_name || p.name).join(', ')}
          {people.length > 2 && ` +${people.length - 2}`}
        </span>
      )}
    </div>
  )
}

/* ============================== Progress ============================== */
export function Progress({ value = 0, tone = 'bg-brand-600', size = 6, showLabel, className }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <div className={cx('w-full', className)}>
      <div className="w-full overflow-hidden rounded-full bg-slate-200" style={{ height: size }}>
        <div className={cx('h-full rounded-full transition-all duration-500', tone)}
             style={{ width: `${v}%` }} />
      </div>
      {showLabel && <span className="mt-1 block text-xs text-slate-500">{Math.round(v)} %</span>}
    </div>
  )
}

export function Ring({ value = 0, size = 56, stroke = 6, color = '#2563EB', children }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0))
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E2E8F0" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={c} strokeDashoffset={c - (v / 100) * c} strokeLinecap="round"
          className="transition-all duration-700" />
      </svg>
      <span className="absolute text-[11px] font-semibold text-slate-700">{children ?? `${Math.round(v)}%`}</span>
    </div>
  )
}

/* ============================== Skeleton ============================== */
export function Skeleton({ className, count = 1 }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={cx('skeleton', className)} />
      ))}
    </>
  )
}

export function SkeletonCard() {
  return (
    <div className="card p-5 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  )
}

/* ============================== Empty state ============================== */
export function EmptyState({ icon: Icon, title, description, action, className }) {
  return (
    <div className={cx('flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50/60 px-6 py-12 text-center', className)}>
      {Icon && (
        <span className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-600">
          <Icon size={22} />
        </span>
      )}
      <p className="text-sm font-semibold text-slate-800">{title}</p>
      {description && <p className="mt-1 max-w-md text-[13px] text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

/* ============================== Alert ============================== */
const ALERT_TONES = {
  info: { cls: 'border-sky-200 bg-sky-50 text-sky-900', Icon: Info },
  success: { cls: 'border-emerald-200 bg-emerald-50 text-emerald-900', Icon: CheckCircle2 },
  warning: { cls: 'border-amber-200 bg-amber-50 text-amber-900', Icon: AlertTriangle },
  error: { cls: 'border-rose-200 bg-rose-50 text-rose-900', Icon: XCircle },
}

export function Alert({ tone = 'info', title, children, className, action }) {
  const { cls, Icon } = ALERT_TONES[tone] || ALERT_TONES.info
  return (
    <div className={cx('flex gap-3 rounded-xl border px-4 py-3 text-sm', cls, className)}>
      <Icon size={17} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cx('text-[13px]', title && 'mt-0.5 opacity-90')}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

/* ============================== Modal ============================== */
export function Modal({ open, onClose, title, subtitle, children, footer, size = 'md', icon: Icon }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = '' }
  }, [open, onClose])

  if (!open) return null
  const widths = { sm: 'max-w-md', md: 'max-w-xl', lg: 'max-w-3xl', xl: 'max-w-5xl' }
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/40 p-4 backdrop-blur-sm sm:items-center">
      <div className="absolute inset-0" onClick={onClose} aria-hidden />
      <div className={cx('relative z-10 w-full animate-scale-in rounded-2xl bg-white shadow-panel', widths[size])}>
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-4">
          <div className="flex items-start gap-3">
            {Icon && <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600"><Icon size={17} /></span>}
            <div>
              <h3 className="text-base font-semibold text-slate-900">{title}</h3>
              {subtitle && <p className="mt-0.5 text-[13px] text-slate-500">{subtitle}</p>}
            </div>
          </div>
          <button onClick={onClose} className="btn btn-ghost btn-icon -mr-2 -mt-1" aria-label="Fermer">
            <X size={18} />
          </button>
        </div>
        <div className="max-h-[70vh] overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-100 bg-slate-50/60 px-6 py-3.5">{footer}</div>}
      </div>
    </div>
  )
}

export function ConfirmDialog({ open, onClose, onConfirm, title, message, confirmLabel = 'Confirmer', tone = 'danger', loading }) {
  return (
    <Modal open={open} onClose={onClose} title={title} size="sm" icon={AlertTriangle}>
      <p className="text-sm text-slate-600">{message}</p>
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>Annuler</Button>
        <Button variant={tone} loading={loading} onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </Modal>
  )
}

/* ============================== Tabs ============================== */
export function Tabs({ tabs, value, onChange, className }) {
  return (
    <div className={cx('flex gap-1 overflow-x-auto border-b border-slate-200 no-scrollbar', className)}>
      {tabs.map((t) => {
        const active = t.key === value
        return (
          <button key={t.key} onClick={() => onChange(t.key)}
            className={cx(
              'relative whitespace-nowrap px-3.5 py-2.5 text-[13px] font-medium transition',
              active ? 'text-brand-700' : 'text-slate-500 hover:text-slate-800',
            )}>
            <span className="flex items-center gap-2">
              {t.icon && <t.icon size={15} />}
              {t.label}
              {t.count !== undefined && (
                <span className={cx('rounded-full px-1.5 py-0.5 text-[10.5px] font-semibold',
                  active ? 'bg-brand-100 text-brand-700' : 'bg-slate-100 text-slate-500')}>
                  {t.count}
                </span>
              )}
            </span>
            {active && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand-600" />}
          </button>
        )
      })}
    </div>
  )
}

/* ============================== Inputs ============================== */
export function Input({ label, error, hint, icon: Icon, className, ...rest }) {
  return (
    <div className={className}>
      {label && <label className="label">{label}</label>}
      <div className="relative">
        {Icon && <Icon size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />}
        <input className={cx('field', Icon && 'pl-9', error && 'field-error')} {...rest} />
      </div>
      {error ? <p className="error-text">{error}</p> : hint && <p className="hint">{hint}</p>}
    </div>
  )
}

export function Textarea({ label, error, hint, className, ...rest }) {
  return (
    <div className={className}>
      {label && <label className="label">{label}</label>}
      <textarea className={cx('field min-h-[92px] resize-y', error && 'field-error')} {...rest} />
      {error ? <p className="error-text">{error}</p> : hint && <p className="hint">{hint}</p>}
    </div>
  )
}

export function Select({ label, error, hint, options = [], className, ...rest }) {
  return (
    <div className={className}>
      {label && <label className="label">{label}</label>}
      <div className="relative">
        <select className={cx('field appearance-none pr-9', error && 'field-error')} {...rest}>
          {options.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <ChevronDown size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
      </div>
      {error ? <p className="error-text">{error}</p> : hint && <p className="hint">{hint}</p>}
    </div>
  )
}

export function SearchInput({ value, onChange, placeholder = 'Rechercher…', className }) {
  return (
    <div className={cx('relative', className)}>
      <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="field h-9 pl-9 pr-9"
      />
      {value && (
        <button onClick={() => onChange('')} className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
          <X size={13} />
        </button>
      )}
    </div>
  )
}

export function Toggle({ checked, onChange, label, description }) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-4 py-2.5">
      <span className="min-w-0">
        <span className="block text-[13px] font-medium text-slate-800">{label}</span>
        {description && <span className="mt-0.5 block text-xs text-slate-500">{description}</span>}
      </span>
      <span className="relative inline-flex shrink-0 cursor-pointer items-center">
        <input type="checkbox" className="peer sr-only" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span className="h-5 w-9 rounded-full bg-slate-300 transition peer-checked:bg-brand-600" />
        <span className="absolute left-0.5 h-4 w-4 rounded-full bg-white shadow transition peer-checked:translate-x-4" />
      </span>
    </label>
  )
}

/* ============================== Table helpers ============================== */
export function Pagination({ count, page, pageSize, onPage, className }) {
  const pages = Math.max(1, Math.ceil(count / pageSize))
  if (pages <= 1) return null
  const shown = []
  const push = (p) => !shown.includes(p) && shown.push(p)
  push(1); push(pages)
  for (let i = page - 1; i <= page + 1; i++) if (i > 0 && i <= pages) push(i)
  shown.sort((a, b) => a - b)
  const final = []
  shown.forEach((p, i) => {
    if (i && p - shown[i - 1] > 1) final.push('…')
    final.push(p)
  })
  return (
    <div className={cx('flex items-center justify-between gap-3 border-t border-slate-100 px-4 py-3', className)}>
      <span className="text-xs text-slate-500">
        {count} résultat{count > 1 ? 's' : ''} · page {page} / {pages}
      </span>
      <div className="flex items-center gap-1">
        <button disabled={page <= 1} onClick={() => onPage(page - 1)} className="btn btn-secondary btn-sm px-2">
          <ChevronLeft size={14} />
        </button>
        {final.map((p, i) => p === '…'
          ? <span key={`e${i}`} className="px-1 text-xs text-slate-400">…</span>
          : <button key={p} onClick={() => onPage(p)}
              className={cx('btn btn-sm min-w-[32px] px-2', p === page ? 'btn-primary' : 'btn-secondary')}>{p}</button>)}
        <button disabled={page >= pages} onClick={() => onPage(page + 1)} className="btn btn-secondary btn-sm px-2">
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  )
}

export function TableSkeleton({ rows = 5, cols = 5 }) {
  return (
    <div className="divide-y divide-slate-100">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3.5">
          <Skeleton className="h-8 w-8 rounded-full" />
          {Array.from({ length: cols - 1 }).map((__, j) => (
            <Skeleton key={j} className="h-3.5 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

/* ============================== Misc ============================== */
export function SectionTitle({ title, description, action }) {
  return (
    <div className="mb-4 flex items-end justify-between gap-4">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        {description && <p className="mt-0.5 text-[13px] text-slate-500">{description}</p>}
      </div>
      {action}
    </div>
  )
}

export function KeyValue({ label, value, className }) {
  return (
    <div className={cx('flex items-center justify-between gap-3 py-1.5 text-[13px]', className)}>
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-800 text-right">{value ?? '—'}</span>
    </div>
  )
}

export function Breadcrumbs({ items = [] }) {
  return (
    <nav className="flex items-center gap-1.5 text-[13px] text-slate-500">
      {items.map((it, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <ChevronRight size={13} className="text-slate-300" />}
          {it.to ? <Link to={it.to} className="hover:text-brand-600 hover:underline">{it.label}</Link>
                 : <span className="font-medium text-slate-700">{it.label}</span>}
        </span>
      ))}
    </nav>
  )
}

export function Dot({ className = 'bg-brand-500', pulse }) {
  return (
    <span className="relative inline-flex h-2 w-2">
      {pulse && <span className={cx('absolute inline-flex h-full w-full rounded-full opacity-60 animate-pulse-ring', className)} />}
      <span className={cx('relative inline-flex h-2 w-2 rounded-full', className)} />
    </span>
  )
}

export function CopyButton({ value, label = 'Copier' }) {
  const [done, setDone] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(value)
    setDone(true)
    setTimeout(() => setDone(false), 1600)
  }
  return (
    <button onClick={copy} className="btn btn-secondary btn-sm">
      {done ? <Check size={13} className="text-emerald-600" /> : null}
      {done ? 'Copié' : label}
    </button>
  )
}
