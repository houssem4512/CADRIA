import { useEffect, useState } from 'react'

/**
 * Avatar de Cadria — personnage SVG 100 % autonome (aucune ressource externe)
 * qui salue de la main. Les animations (bras, flottement, clignement) sont
 * définies dans styles/index.css et désactivées en `prefers-reduced-motion`.
 */
export function WavingAvatar({ size = 76, className = '' }) {
  return (
    <svg viewBox="0 0 120 120" width={size} height={size} className={className}
      role="img" aria-label="Cadria, le copilote de projets, vous salue de la main">
      <defs>
        <linearGradient id="cadria-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#DBEAFE" />
          <stop offset="1" stopColor="#E0F2FE" />
        </linearGradient>
        <linearGradient id="cadria-shirt" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2563EB" />
          <stop offset="1" stopColor="#1E40AF" />
        </linearGradient>
      </defs>

      {/* Pastille de fond */}
      <circle cx="60" cy="60" r="58" fill="url(#cadria-bg)" />
      <circle cx="60" cy="60" r="58" fill="none" stroke="#BFDBFE" strokeWidth="1.5" />

      <g className="avatar-float">
        {/* Torse */}
        <path d="M34 116 v-20 a26 26 0 0 1 52 0 v20 z" fill="url(#cadria-shirt)" />
        {/* Col */}
        <path d="M52 86 l8 8 l8 -8" fill="none" stroke="#BFDBFE" strokeWidth="3"
          strokeLinecap="round" strokeLinejoin="round" />

        {/* Bras au repos */}
        <path d="M40 94 q-9 8 -7 19" fill="none" stroke="#1D4ED8" strokeWidth="8" strokeLinecap="round" />
        <circle cx="33" cy="114" r="5" fill="#F6C99F" />

        {/* Tête : calotte sombre (cheveux) + visage */}
        <circle cx="60" cy="49" r="21" fill="#1E293B" />
        <circle cx="60" cy="53.5" r="18.5" fill="#F6C99F" />
        {/* Mèche */}
        <path d="M60 28 q4 -5 9 -3" fill="none" stroke="#1E293B" strokeWidth="4" strokeLinecap="round" />

        {/* Yeux (clignement) */}
        <ellipse className="avatar-eye" cx="53" cy="54" rx="2" ry="2.7" fill="#1E293B" />
        <ellipse className="avatar-eye" cx="67" cy="54" rx="2" ry="2.7" fill="#1E293B" />
        {/* Sourire */}
        <path d="M53.5 62 q6.5 5.5 13 0" fill="none" stroke="#334155" strokeWidth="2.2" strokeLinecap="round" />
        {/* Joues */}
        <circle cx="46.5" cy="59" r="2.6" fill="#F87171" opacity="0.35" />
        <circle cx="73.5" cy="59" r="2.6" fill="#F87171" opacity="0.35" />

        {/* Bras qui salue — rotation autour de l'épaule */}
        <g className="avatar-arm">
          <path d="M80 92 q10 -13 12 -30" fill="none" stroke="#1D4ED8" strokeWidth="8" strokeLinecap="round" />
          <circle cx="93" cy="58" r="6.4" fill="#F6C99F" />
          <path d="M89 53 v-3.4 M93 51.6 v-4 M97 53 v-3.4" stroke="#F6C99F" strokeWidth="2.6" strokeLinecap="round" />
        </g>
      </g>
    </svg>
  )
}

/** Messages d'introduction — ton professionnel, voix du copilote. */
const MESSAGES = [
  'Bonjour 👋 Moi, c’est Cadria — le copilote multi-agents qui transforme vos idées en plans de projet solides.',
  'Décrivez votre projet en une phrase : je le découpe en lots et tâches, j’estime l’effort et j’anticipe les risques.',
  'Vous gardez la main : aucun sprint, aucun ticket n’est créé dans Jira ou Trello sans votre validation.',
]

/**
 * Bulle de présentation : l'avatar salue pendant que Cadria se présente,
 * message après message, avec un indicateur de saisie entre chaque prise
 * de parole.
 */
export function CadriaGreeter() {
  const [idx, setIdx] = useState(0)
  const [typing, setTyping] = useState(true)

  useEffect(() => {
    const t = setTimeout(() => {
      if (typing) setTyping(false)
      else { setIdx((i) => (i + 1) % MESSAGES.length); setTyping(true) }
    }, typing ? 1200 : 4600)
    return () => clearTimeout(t)
  }, [typing, idx])

  return (
    <div className="flex items-end gap-2.5 sm:gap-3">
      <WavingAvatar size={72} className="shrink-0 drop-shadow-lg" />
      <div className="relative max-w-[248px] rounded-2xl border border-slate-200 bg-white p-3.5 shadow-panel sm:max-w-[320px] sm:p-4">
        {/* Queue de la bulle, orientée vers l'avatar */}
        <span className="absolute -left-[7px] bottom-6 h-3.5 w-3.5 rotate-45 border-b border-l border-slate-200 bg-white" />

        <div className="flex items-center gap-2">
          <p className="text-[12.5px] font-bold tracking-tight text-slate-900">Cadria</p>
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[9.5px] font-bold uppercase tracking-wider text-emerald-600">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> en ligne
          </span>
        </div>

        {typing ? (
          <p className="mt-2 flex items-center gap-1" aria-label="Cadria est en train d’écrire">
            <span className="typing-dot h-1.5 w-1.5 rounded-full bg-slate-400" />
            <span className="typing-dot h-1.5 w-1.5 rounded-full bg-slate-400" />
            <span className="typing-dot h-1.5 w-1.5 rounded-full bg-slate-400" />
          </p>
        ) : (
          <p key={idx} className="bubble-in mt-1.5 text-[12.5px] leading-relaxed text-slate-600">
            {MESSAGES[idx]}
          </p>
        )}
      </div>
    </div>
  )
}
