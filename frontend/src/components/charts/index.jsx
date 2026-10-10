import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'

const BLUE = ['#1D4ED8', '#2563EB', '#3B82F6', '#0EA5E9', '#38BDF8', '#7DD3FC', '#1E40AF', '#0369A1', '#93C5FD', '#BAE6FD']

const AXIS = { stroke: '#94A3B8', fontSize: 11, fontFamily: 'inherit' }
const GRID = { stroke: '#E2E8F0', strokeDasharray: '4 4', vertical: false }

function TipBox({ active, payload, label, unit = '' }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-slate-200 bg-white/95 px-3 py-2 text-[12px] shadow-panel backdrop-blur">
      {label !== undefined && <p className="mb-1 font-semibold text-slate-700">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} className="flex items-center gap-2 text-slate-600">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color || p.fill || p.stroke }} />
          <span className="capitalize">{p.name}</span>
          <span className="ml-auto font-semibold text-slate-900">
            {typeof p.value === 'number' ? p.value.toLocaleString('fr-FR') : p.value}{unit}
          </span>
        </p>
      ))}
    </div>
  )
}

export function ChartFrame({ height = 240, children, className }) {
  return (
    <div style={{ height }} className={className}>
      <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
    </div>
  )
}

/* ------------------------------- Courbes ------------------------------- */
export function TrendChart({ data = [], xKey, series = [], height = 240, unit = '', area = true }) {
  return (
    <ChartFrame height={height}>
      <AreaChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
        <defs>
          {series.map((s, i) => (
            <linearGradient key={i} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color || BLUE[i]} stopOpacity={0.28} />
              <stop offset="100%" stopColor={s.color || BLUE[i]} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid {...GRID} />
        <XAxis dataKey={xKey} {...AXIS} tickLine={false} axisLine={false} />
        <YAxis {...AXIS} tickLine={false} axisLine={false} width={48} />
        <Tooltip content={<TipBox unit={unit} />} />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} iconType="circle" iconSize={7} />}
        {series.map((s, i) => (
          <Area key={s.key} type="monotone" dataKey={s.key} name={s.label || s.key}
            stroke={s.color || BLUE[i]} strokeWidth={2}
            fill={area ? `url(#grad-${s.key})` : 'transparent'}
            dot={false} activeDot={{ r: 4, strokeWidth: 2 }} />
        ))}
      </AreaChart>
    </ChartFrame>
  )
}

/* ------------------------------ Histogrammes --------------------------- */
export function BarChartView({ data = [], xKey, series = [], height = 240, stacked, layout = 'horizontal', unit = '' }) {
  const vertical = layout === 'vertical'
  return (
    <ChartFrame height={height}>
      <BarChart data={data} layout={layout} margin={{ top: 6, right: 12, bottom: 0, left: vertical ? 20 : -18 }}>
        <CartesianGrid {...GRID} vertical={vertical} horizontal={!vertical} />
        {vertical
          ? (<><XAxis type="number" {...AXIS} tickLine={false} axisLine={false} />
             <YAxis type="category" dataKey={xKey} {...AXIS} tickLine={false} axisLine={false} width={110} /></>)
          : (<><XAxis dataKey={xKey} {...AXIS} tickLine={false} axisLine={false} />
             <YAxis {...AXIS} tickLine={false} axisLine={false} width={48} /></>)}
        <Tooltip content={<TipBox unit={unit} />} cursor={{ fill: '#F1F5F9' }} />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} iconType="circle" iconSize={7} />}
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={s.key} name={s.label || s.key} stackId={stacked ? 'a' : undefined}
            fill={s.color || BLUE[i]} radius={vertical ? [0, 4, 4, 0] : [4, 4, 0, 0]} maxBarSize={vertical ? 22 : 34} />
        ))}
      </BarChart>
    </ChartFrame>
  )
}

/* --------------------------------- Donut ------------------------------- */
export function DonutChart({ data = [], height = 220, innerRadius = 58, outerRadius = 82, centerLabel, centerValue }) {
  const total = data.reduce((s, d) => s + (Number(d.value) || 0), 0)
  return (
    <div className="relative" style={{ height }}>
      <ChartFrame height={height}>
        <PieChart>
          <Tooltip content={<TipBox />} />
          <Pie data={data} dataKey="value" nameKey="label" innerRadius={innerRadius} outerRadius={outerRadius}
            paddingAngle={2} strokeWidth={2} stroke="#fff" isAnimationActive={false}>
            {data.map((d, i) => <Cell key={i} fill={d.color || BLUE[i % BLUE.length]} />)}
          </Pie>
        </PieChart>
      </ChartFrame>
      {(centerValue !== undefined || centerLabel) && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center">
          <div className="text-center">
            {centerValue !== undefined && (
              <p className="text-xl font-bold leading-none text-slate-900">
                {typeof centerValue === 'number' ? centerValue.toLocaleString('fr-FR') : centerValue}
              </p>
            )}
            {centerLabel && <p className="mt-1 text-[11px] text-slate-500">{centerLabel}</p>}
          </div>
        </div>
      )}
      {total > 0 && (
        <div className="mt-1 flex flex-wrap justify-center gap-x-3 gap-y-1">
          {data.map((d, i) => (
            <span key={i} className="flex items-center gap-1.5 text-[11px] text-slate-600">
              <span className="h-2 w-2 rounded-full" style={{ background: d.color || BLUE[i % BLUE.length] }} />
              {d.label} <b className="text-slate-800">{d.value}</b>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

/* --------------------------------- Radar ------------------------------- */
export function RadarChartView({ data = [], dataKey = 'value', height = 260, color = '#2563EB' }) {
  return (
    <ChartFrame height={height}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke="#E2E8F0" />
        <PolarAngleAxis dataKey="label" {...AXIS} tick={{ fontSize: 11, fill: '#475569' }} />
        <Tooltip content={<TipBox />} />
        <Radar dataKey={dataKey} stroke={color} fill={color} fillOpacity={0.22} strokeWidth={2} />
      </RadarChart>
    </ChartFrame>
  )
}

/* -------------------------------- Lignes ------------------------------- */
export function LineChartView({ data = [], xKey, series = [], height = 240, unit = '' }) {
  return (
    <ChartFrame height={height}>
      <LineChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
        <CartesianGrid {...GRID} />
        <XAxis dataKey={xKey} {...AXIS} tickLine={false} axisLine={false} />
        <YAxis {...AXIS} tickLine={false} axisLine={false} width={48} />
        <Tooltip content={<TipBox unit={unit} />} />
        {series.length > 1 && <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} iconType="circle" iconSize={7} />}
        {series.map((s, i) => (
          <Line key={s.key} type="monotone" dataKey={s.key} name={s.label || s.key}
            stroke={s.color || BLUE[i]} strokeWidth={2} dot={{ r: 2.5, strokeWidth: 0, fill: s.color || BLUE[i] }}
            activeDot={{ r: 4.5 }} />
        ))}
      </LineChart>
    </ChartFrame>
  )
}

/* ------------------------------ Barre simple --------------------------- */
export function MiniBar({ value = 0, max = 100, color = '#2563EB', className = '' }) {
  const v = Math.max(0, Math.min(100, (Number(value) / (max || 1)) * 100))
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full bg-slate-200 ${className}`}>
      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${v}%`, background: color }} />
    </div>
  )
}

export { BLUE }
