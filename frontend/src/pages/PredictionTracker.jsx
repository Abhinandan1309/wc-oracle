import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, CartesianGrid,
} from 'recharts'
import Header from '../components/Header'
import { useSchedule } from '../hooks/useApi'
import { useDark } from '../App'

const PieTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-sm shadow-lg">
      <p className="font-semibold text-gray-800 dark:text-gray-100">{payload[0].name}</p>
      <p style={{ color: payload[0].payload.color }}>{payload[0].value} matches</p>
    </div>
  )
}

const BarTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-sm shadow-lg">
      <p className="font-semibold text-gray-800 dark:text-gray-100">{label} goals</p>
      <p className="text-gray-600 dark:text-gray-300">{payload[0].value} matches</p>
    </div>
  )
}

export default function PredictionTracker() {
  const { dark } = useDark()
  const { data: schedule } = useSchedule()
  const played = schedule?.played ?? []

  const axisColor = dark ? '#9aa0a6' : '#6b7280'
  const gridColor = dark ? '#1a2744' : '#f3f4f6'

  if (played.length === 0) {
    return (
      <div>
        <Header title="Prediction Tracker" subtitle="Live results and accuracy for 2026 WC matches" />
        <div className="card p-16 text-center">
          <div className="text-5xl mb-4">⏳</div>
          <p className="text-lg font-bold text-gray-800 dark:text-gray-100">No matches played yet</p>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Check back once the tournament kicks off!</p>
        </div>
      </div>
    )
  }

  const homeWins = played.filter(m => m.home_score > m.away_score).length
  const awayWins = played.filter(m => m.away_score > m.home_score).length
  const draws    = played.length - homeWins - awayWins

  const avgHome  = played.reduce((s, m) => s + m.home_score, 0) / played.length
  const avgAway  = played.reduce((s, m) => s + m.away_score, 0) / played.length
  const avgTotal = avgHome + avgAway

  // Goals distribution (bucketed)
  const goalBuckets = {}
  played.forEach(m => {
    const t = m.home_score + m.away_score
    goalBuckets[t] = (goalBuckets[t] ?? 0) + 1
  })
  const goalDist = Object.entries(goalBuckets)
    .sort(([a], [b]) => +a - +b)
    .map(([g, c]) => ({ goals: +g, count: c }))

  const pieData = [
    { name: 'Home Win', value: homeWins, color: '#34a853' },
    { name: 'Draw',     value: draws,    color: '#fbbc04' },
    { name: 'Away Win', value: awayWins, color: '#ea4335' },
  ]

  const avgData = [
    { label: 'Home', value: avgHome, color: '#1a73e8' },
    { label: 'Away', value: avgAway, color: '#ea4335' },
  ]

  return (
    <div>
      <Header title="Prediction Tracker" subtitle="Live results and accuracy for 2026 WC matches" />

      {/* Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Matches Played', value: played.length,  color: '#1a73e8' },
          { label: 'Home Wins',      value: homeWins,       color: '#34a853' },
          { label: 'Draws',          value: draws,          color: '#fbbc04' },
          { label: 'Away Wins',      value: awayWins,       color: '#ea4335' },
        ].map(({ label, value, color }) => (
          <div key={label} className="stat-card">
            <div className="stat-value" style={{ color }}>{value}</div>
            <div className="stat-label">{label}</div>
          </div>
        ))}
      </div>

      {/* Results table */}
      <div className="card overflow-hidden mb-6">
        <div className="px-5 py-3 border-b border-gray-100 dark:border-navy-700">
          <h2 className="font-bold text-gray-900 dark:text-gray-50">Completed Matches</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 dark:bg-navy-900/50">
                {['Group', 'Home', 'Score', 'Away', 'Winner'].map(h => (
                  <th key={h}
                    className="px-4 py-2.5 text-left text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {played.map((m, i) => {
                const winner = m.home_score > m.away_score ? m.home_team
                             : m.away_score > m.home_score ? m.away_team : 'Draw'
                return (
                  <tr key={i}
                    className="border-t border-gray-100 dark:border-navy-700
                               hover:bg-gray-50 dark:hover:bg-navy-700/40 transition-colors">
                    <td className="px-4 py-2.5 text-gray-500 dark:text-gray-400 text-xs font-medium">
                      {m.group}
                    </td>
                    <td className="px-4 py-2.5 font-medium text-gray-800 dark:text-gray-200">{m.home_team}</td>
                    <td className="px-4 py-2.5 font-bold text-gray-900 dark:text-gray-50 tabular-nums">
                      {m.home_score}–{m.away_score}
                    </td>
                    <td className="px-4 py-2.5 font-medium text-gray-800 dark:text-gray-200">{m.away_team}</td>
                    <td className="px-4 py-2.5">
                      <span className={`badge ${winner === 'Draw'
                        ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
                        : 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'}`}>
                        {winner}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Charts */}
      <h2 className="section-title">Match Analysis</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Goals distribution */}
        <div className="card p-5">
          <h3 className="text-sm font-bold text-gray-700 dark:text-gray-200 mb-4">Goals per Match</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={goalDist} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={gridColor} />
              <XAxis dataKey="goals" tick={{ fill: axisColor, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: axisColor, fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<BarTooltip />} cursor={{ fill: 'rgba(26,115,232,0.06)' }} />
              <Bar dataKey="count" fill="#1a73e8" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Result distribution pie */}
        <div className="card p-5">
          <h3 className="text-sm font-bold text-gray-700 dark:text-gray-200 mb-4">Result Distribution</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={pieData} cx="50%" cy="50%"
                innerRadius={55} outerRadius={85}
                dataKey="value" nameKey="name"
                paddingAngle={3}
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {pieData.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Pie>
              <Tooltip content={<PieTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Avg goals */}
        <div className="card p-5">
          <h3 className="text-sm font-bold text-gray-700 dark:text-gray-200 mb-4">
            Avg Goals/Team
            <span className="text-gray-400 dark:text-gray-500 font-normal ml-1 text-xs">
              (match avg: {avgTotal.toFixed(2)})
            </span>
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={avgData} margin={{ top: 20, right: 20, left: -20, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={gridColor} />
              <XAxis dataKey="label" tick={{ fill: axisColor, fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: axisColor, fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: 'rgba(26,115,232,0.06)' }} formatter={v => v.toFixed(2)} />
              <Bar dataKey="value" radius={[6,6,0,0]}
                label={{ position: 'top', formatter: v => v.toFixed(2), fill: axisColor, fontSize: 12 }}>
                {avgData.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
