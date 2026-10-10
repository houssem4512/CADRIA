import { cx } from '../lib/format'

export function Logo({ size = 32, withText = true, className, variant = 'brand' }) {
  const gradId = `lg-${Math.random().toString(36).slice(2, 8)}`
  const dark = variant === 'white'
  return (
    <span className={cx('inline-flex items-center gap-2.5', className)}>
      <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop stopColor="#1D4ED8" />
            <stop offset="1" stopColor="#0EA5E9" />
          </linearGradient>
        </defs>
        <rect width="40" height="40" rx="11" fill={`url(#${gradId})`} />
        {/* nœuds d'orchestration */}
        <circle cx="20" cy="11.5" r="3.1" fill="white" />
        <circle cx="11" cy="27" r="3.1" fill="white" fillOpacity=".92" />
        <circle cx="29" cy="27" r="3.1" fill="white" fillOpacity=".92" />
        <path d="M20 14.6v5.2M20 19.8l-6.4 4.6M20 19.8l6.4 4.6" stroke="white" strokeOpacity=".75" strokeWidth="1.7" strokeLinecap="round" />
      </svg>
      {withText && (
        <span className={cx('text-[17px] font-bold tracking-tight', dark ? 'text-white' : 'text-slate-900')}>
          Cadria
          <span className={cx('ml-1.5 rounded px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-wider',
            dark ? 'bg-white/20 text-white' : 'bg-brand-50 text-brand-700')}>IA</span>
        </span>
      )}
    </span>
  )
}

export function LogoMark({ size = 32 }) {
  return <Logo size={size} withText={false} />
}
