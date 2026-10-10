import clsx from 'clsx'

export const cx = clsx

/* ------------------------------ Nombres ------------------------------ */
const nf = new Intl.NumberFormat('fr-FR')
const nf1 = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

export function num(v, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—'
  return digits ? nf1.format(Number(v)) : nf.format(Number(v))
}

export function hours(v) {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  if (n >= 1000) return `${nf1.format(n / 1000)} k h`
  return `${nf1.format(n)} h`
}

export function currency(v, cur = 'EUR') {
  if (v === null || v === undefined) return '—'
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency', currency: cur, maximumFractionDigits: 0,
  }).format(Number(v))
}

export function compact(v) {
  const n = Number(v)
  if (n >= 1_000_000) return `${nf1.format(n / 1_000_000)} M`
  if (n >= 1000) return `${nf1.format(n / 1000)} k`
  return num(n)
}

export function pct(v, digits = 0) {
  if (v === null || v === undefined) return '—'
  return `${Number(v).toFixed(digits)} %`.replace('.', ',')
}

/* ------------------------------ Dates ------------------------------ */
export function formatDate(v, opts = { day: '2-digit', month: 'short', year: 'numeric' }) {
  if (!v) return '—'
  const d = v instanceof Date ? v : new Date(v)
  if (Number.isNaN(d.getTime())) return '—'
  return new Intl.DateTimeFormat('fr-FR', opts).format(d)
}

export function formatDateTime(v) {
  return formatDate(v, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function timeAgo(v) {
  if (!v) return '—'
  const d = v instanceof Date ? v : new Date(v)
  const s = (Date.now() - d.getTime()) / 1000
  if (s < 60) return "à l'instant"
  if (s < 3600) return `il y a ${Math.floor(s / 60)} min`
  if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`
  const days = Math.floor(s / 86400)
  if (days < 7) return `il y a ${days} j`
  if (days < 31) return `il y a ${Math.floor(days / 7)} sem.`
  return formatDate(d)
}

export function daysUntil(dateStr) {
  if (!dateStr) return null
  const target = new Date(dateStr)
  const today = new Date()
  target.setHours(0, 0, 0, 0); today.setHours(0, 0, 0, 0)
  return Math.round((target - today) / 86400000)
}

export function relativeDeadline(dateStr) {
  const d = daysUntil(dateStr)
  if (d === null) return null
  if (d < 0) return { text: `retard de ${Math.abs(d)} j`, tone: 'danger' }
  if (d === 0) return { text: "aujourd'hui", tone: 'warning' }
  if (d <= 3) return { text: `dans ${d} j`, tone: 'warning' }
  return { text: `dans ${d} j`, tone: 'muted' }
}

/* ------------------------------ Texte ------------------------------ */
export function initials(name = '') {
  const parts = String(name).trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '??'
  return parts.slice(0, 2).map((p) => p[0]).join('').toUpperCase()
}

export function truncate(text, n = 90) {
  const t = String(text || '')
  return t.length > n ? `${t.slice(0, n)}…` : t
}

export function slugify(text) {
  return String(text).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')
}

/* ------------------------------ Couleurs ------------------------------ */
export function hashColor(seed = '') {
  const palette = ['#2563EB', '#0EA5E9', '#1D4ED8', '#0284C7', '#3B82F6', '#0369A1', '#1E40AF', '#38BDF8']
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  return palette[h % palette.length]
}

export function riskTone(score) {
  const n = Number(score) || 0
  if (n >= 70) return { label: 'Critique', cls: 'badge-danger', bar: 'bg-rose-500', hex: '#E11D48' }
  if (n >= 45) return { label: 'Élevé', cls: 'badge-warning', bar: 'bg-amber-500', hex: '#F59E0B' }
  if (n >= 22) return { label: 'Modéré', cls: 'badge-sky', bar: 'bg-sky-500', hex: '#0EA5E9' }
  return { label: 'Faible', cls: 'badge-success', bar: 'bg-emerald-500', hex: '#10B981' }
}

export function healthTone(health) {
  return {
    GREEN: { label: 'Sain', cls: 'badge-success', dot: 'bg-emerald-500', hex: '#10B981' },
    AMBER: { label: 'À surveiller', cls: 'badge-warning', dot: 'bg-amber-500', hex: '#F59E0B' },
    RED: { label: 'Critique', cls: 'badge-danger', dot: 'bg-rose-500', hex: '#E11D48' },
  }[health] || { label: health, cls: 'badge-neutral', dot: 'bg-slate-400', hex: '#94A3B8' }
}

export const PROJECT_STATUS = {
  DRAFT: { label: 'Brouillon', cls: 'badge-neutral' },
  SCOPING: { label: 'Cadrage', cls: 'badge-purple' },
  PLANNED: { label: 'Planifié', cls: 'badge-sky' },
  ACTIVE: { label: 'En cours', cls: 'badge-brand' },
  AT_RISK: { label: 'À risque', cls: 'badge-danger' },
  ON_HOLD: { label: 'En pause', cls: 'badge-warning' },
  COMPLETED: { label: 'Terminé', cls: 'badge-success' },
  CANCELLED: { label: 'Annulé', cls: 'badge-neutral' },
}

export const TASK_STATUS = {
  TODO: { label: 'À faire', cls: 'badge-neutral', hex: '#94A3B8' },
  IN_PROGRESS: { label: 'En cours', cls: 'badge-brand', hex: '#2563EB' },
  REVIEW: { label: 'En revue', cls: 'badge-purple', hex: '#8B5CF6' },
  BLOCKED: { label: 'Bloquée', cls: 'badge-danger', hex: '#E11D48' },
  DONE: { label: 'Terminée', cls: 'badge-success', hex: '#10B981' },
}

export const TASK_PRIORITY = {
  LOWEST: { label: 'Très basse', cls: 'badge-neutral', hex: '#94A3B8' },
  LOW: { label: 'Basse', cls: 'badge-neutral', hex: '#64748B' },
  MEDIUM: { label: 'Moyenne', cls: 'badge-sky', hex: '#0EA5E9' },
  HIGH: { label: 'Haute', cls: 'badge-warning', hex: '#F59E0B' },
  HIGHEST: { label: 'Critique', cls: 'badge-danger', hex: '#E11D48' },
}

export const TASK_TYPE = {
  FEATURE: { label: 'Fonctionnalité', cls: 'badge-brand' },
  BUG: { label: 'Bug', cls: 'badge-danger' },
  TECH: { label: 'Dette technique', cls: 'badge-purple' },
  SPIKE: { label: 'Spike / Étude', cls: 'badge-sky' },
  DOC: { label: 'Documentation', cls: 'badge-neutral' },
  TEST: { label: 'Test', cls: 'badge-success' },
}

export const ROLE_LABEL = {
  ADMIN: { label: 'Administrateur', cls: 'badge-danger' },
  PM: { label: 'Chef de projet', cls: 'badge-brand' },
  MEMBER: { label: 'Membre', cls: 'badge-sky' },
  VIEWER: { label: 'Observateur', cls: 'badge-neutral' },
}

export const USER_STATUS = {
  ACTIVE: { label: 'Actif', cls: 'badge-success' },
  PENDING: { label: 'En attente', cls: 'badge-warning' },
  SUSPENDED: { label: 'Suspendu', cls: 'badge-danger' },
}

export const RISK_CATEGORY = {
  DELAY: 'Risque de retard',
  QUALITY: 'Risque qualité',
  LOAD: 'Dérive de charge',
  BLOCKER: 'Blocage',
  SCOPE: 'Dérive de périmètre',
  BUDGET: 'Dérive budgétaire',
}

export const RUN_STATUS = {
  QUEUED: { label: 'En file', cls: 'badge-neutral', dot: 'bg-slate-400' },
  RUNNING: { label: 'En cours', cls: 'badge-brand', dot: 'bg-brand-500' },
  AWAITING_VALIDATION: { label: 'À valider', cls: 'badge-warning', dot: 'bg-amber-500' },
  SUCCEEDED: { label: 'Succès', cls: 'badge-success', dot: 'bg-emerald-500' },
  FAILED: { label: 'Échec', cls: 'badge-danger', dot: 'bg-rose-500' },
  CANCELLED: { label: 'Annulé', cls: 'badge-neutral', dot: 'bg-slate-400' },
  SKIPPED: { label: 'Réservé', cls: 'badge-purple', dot: 'bg-violet-500' },
}

export const PROPOSAL_STATUS = {
  DRAFT: { label: 'Brouillon', cls: 'badge-neutral' },
  PENDING: { label: 'À valider', cls: 'badge-warning' },
  APPROVED: { label: 'Approuvé', cls: 'badge-success' },
  REJECTED: { label: 'Rejeté', cls: 'badge-danger' },
  APPLIED: { label: 'Appliqué', cls: 'badge-brand' },
}

export const NOTIF_LEVEL = {
  INFO: { cls: 'badge-sky', dot: 'bg-sky-500', ring: 'ring-sky-100', bg: 'bg-sky-50' },
  SUCCESS: { cls: 'badge-success', dot: 'bg-emerald-500', ring: 'ring-emerald-100', bg: 'bg-emerald-50' },
  WARNING: { cls: 'badge-warning', dot: 'bg-amber-500', ring: 'ring-amber-100', bg: 'bg-amber-50' },
  ERROR: { cls: 'badge-danger', dot: 'bg-rose-500', ring: 'ring-rose-100', bg: 'bg-rose-50' },
  AGENT: { cls: 'badge-purple', dot: 'bg-violet-500', ring: 'ring-violet-100', bg: 'bg-violet-50' },
}

export const NOTIF_CATEGORY = {
  SYSTEM: 'Système', AGENT: 'Agent', RISK: 'Risque', TASK: 'Tâche',
  TEAM: 'Équipe', VALIDATION: 'Validation', ACCOUNT: 'Compte', INTEGRATION: 'Intégration',
}

/* ------------------------------ Divers ------------------------------ */
export function downloadJSON(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function toCSV(rows, filename = 'export.csv') {
  if (!rows?.length) return
  const headers = Object.keys(rows[0])
  const escape = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const csv = [headers.join(';'), ...rows.map((r) => headers.map((h) => escape(r[h])).join(';'))].join('\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
