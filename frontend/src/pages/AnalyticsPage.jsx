import { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from 'recharts'
import Header from '../components/Header'
import { useChampionHistory, useAccuracy } from '../hooks/useApi'
import { useDark } from '../App'

const PALETTE = [
  '#1a73e8', '#ea4335', '#34a853', '#fbbc04', '#9c27b0',
  '#ff5722', '#00bcd4', '#795548', '#607d8b', '#e91e63',
]

// ── Champion Probability Chart ─────────────────────────────────────────────
function ChampionChart({ history }) {
  const { dark } = useDark()
  const axisColor = dark ? '#9aa0a6' : '#6b7280'
  const gridColor = dark ? '#1a2744' : '#f3f4f6'

  if (!history?.length) {
    return (
      <div className="card p-10 text-center text-gray-400 dark:text-gray-500">
        No simulation history yet — run a simulation to start tracking.
      </div>
    )
  }

  // Find top teams by final snapshot winner probability
  const lastSnap = history[history.length - 1]
  const topTeams = Object.entries(lastSnap.probs)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10)
    .map(([t]) => t)

  // Build chart data: one entry per snapshot
  const chartData = history.map((snap, i) => {
    const point = {
      label: new Date(snap.ts).toLocaleDateString('en-GB', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
      }),
      n: snap.n,
    }
    topTeams.forEach(t => { point[t] = +(snap.probs[t] * 100).toFixed(1) })
    return point
  })

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    return (
      <div className="card px-3 py-2 text-xs shadow-lg max-w-[200px]">
        <p className="font-bold text-gray-700 dark:text-gray-200 mb-1">{label}</p>
        {payload.sort((a, b) => b.value - a.value).map(p => (
          <div key={p.dataKey} className="flex justify-between gap-4">
            <span style={{ color: p.color }}>{p.dataKey}</span>
            <span className="font-semibold">{p.value}%</span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="card p-5">
      <h3 className="font-bold text-gray-800 dark:text-gray-100 mb-1">
        Champion Probability — Top 10 Teams
      </h3>
      <p className="text-xs text-gray-400 dark:text-gray-500 mb-4">
        Tracks how win probability evolves across simulation runs
      </p>
      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
          <CartesianGrid vertical={false} stroke={gridColor} />
          <XAxis
            dataKey="label"
            tick={{ fill: axisColor, fontSize: 10 }}
            axisLine={false} tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: axisColor, fontSize: 10 }}
            axisLine={false} tickLine={false}
            tickFormatter={v => `${v}%`}
            domain={[0, 'auto']}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 11, paddingTop: 12 }}
            iconType="circle"
          />
          {topTeams.map((team, i) => (
            <Line
              key={team}
              type="monotone"
              dataKey={team}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      <p className="text-xs text-gray-400 dark:text-gray-500 mt-3 text-right">
        {history.length} snapshot{history.length !== 1 ? 's' : ''} recorded
      </p>
    </div>
  )
}

// ── Current win probability table ──────────────────────────────────────────
function CurrentWinTable({ history }) {
  if (!history?.length) return null
  const last = history[history.length - 1]
  const rows = Object.entries(last.probs)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 16)

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100 dark:border-navy-700">
        <h3 className="font-bold text-gray-900 dark:text-gray-50">Current Win Probabilities</h3>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
          From latest simulation ({last.n?.toLocaleString()} runs)
        </p>
      </div>
      <div className="divide-y divide-gray-100 dark:divide-navy-700">
        {rows.map(([team, prob], i) => (
          <div key={team} className="px-5 py-2.5 flex items-center gap-4">
            <span className="w-5 text-xs text-gray-400 dark:text-gray-500 tabular-nums">{i + 1}</span>
            <span className="flex-1 text-sm font-medium text-gray-800 dark:text-gray-200">{team}</span>
            <div className="w-32 h-1.5 bg-gray-100 dark:bg-navy-700 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{ width: `${Math.min(prob * 100 / rows[0][1] * 100, 100)}%`, background: '#1a73e8' }}
              />
            </div>
            <span className="w-12 text-right text-sm font-bold tabular-nums"
                  style={{ color: prob > 0.1 ? '#34a853' : prob > 0.05 ? '#fbbc04' : '#9aa0a6' }}>
              {(prob * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Accuracy / Brier score ─────────────────────────────────────────────────
function AccuracyPanel({ data }) {
  if (!data) return null
  const { summary, matches } = data
  if (!summary?.matches_scored) {
    return (
      <div className="card p-8 text-center text-gray-400 dark:text-gray-500">
        No predictions scored yet — accuracy will appear once matches are played.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Matches Scored', value: summary.matches_scored, color: '#1a73e8' },
          { label: 'Avg Brier Score', value: summary.avg_brier?.toFixed(3) ?? '—', color: summary.avg_brier < 0.22 ? '#34a853' : '#ea4335' },
          { label: 'Correct Favorite', value: `${(summary.accuracy * 100).toFixed(0)}%`, color: '#34a853' },
          { label: 'Correct Count', value: summary.correct_favs, color: '#fbbc04' },
        ].map(({ label, value, color }) => (
          <div key={label} className="stat-card">
            <div className="stat-value" style={{ color }}>{value}</div>
            <div className="stat-label">{label}</div>
          </div>
        ))}
      </div>

      {/* Brier score guide */}
      <div className="card px-5 py-3 text-xs text-gray-500 dark:text-gray-400 flex flex-wrap gap-4">
        <span>Brier Score (lower = better):</span>
        <span className="text-green-600 dark:text-green-400 font-medium">≤0.20 Excellent</span>
        <span className="text-yellow-600 dark:text-yellow-400 font-medium">0.20–0.25 Good</span>
        <span className="text-red-500 font-medium">&gt;0.25 Needs improvement</span>
        <span className="ml-auto text-gray-400">Random guess = 0.222</span>
      </div>

      {/* Per-match table */}
      <div className="card overflow-hidden">
        <div className="px-5 py-3 border-b border-gray-100 dark:border-navy-700">
          <h3 className="font-bold text-gray-900 dark:text-gray-50">Per-Match Accuracy</h3>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">Sorted by worst predictions first</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 dark:bg-navy-900/50">
                {['Match', 'Score', 'Pred (H/D/A)', 'Brier', 'Correct?'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matches.map((m, i) => (
                <tr key={i} className="border-t border-gray-100 dark:border-navy-700 hover:bg-gray-50 dark:hover:bg-navy-700/30">
                  <td className="px-4 py-2.5 text-xs text-gray-700 dark:text-gray-200">
                    {m.home} <span className="text-gray-400">vs</span> {m.away}
                  </td>
                  <td className="px-4 py-2.5 font-bold tabular-nums">{m.score}</td>
                  <td className="px-4 py-2.5 text-xs tabular-nums text-gray-500 dark:text-gray-400">
                    {(m.p_home * 100).toFixed(0)}% / {(m.p_draw * 100).toFixed(0)}% / {(m.p_away * 100).toFixed(0)}%
                  </td>
                  <td className="px-4 py-2.5 font-bold tabular-nums"
                      style={{ color: m.brier < 0.20 ? '#34a853' : m.brier < 0.25 ? '#fbbc04' : '#ea4335' }}>
                    {m.brier}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`badge ${m.correct
                      ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                      : 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400'}`}>
                      {m.correct ? 'Yes' : 'No'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────
const TABS = ['Champion History', 'Model Accuracy']

export default function AnalyticsPage() {
  const [tab, setTab] = useState(0)
  const { data: histData } = useChampionHistory()
  const { data: accData }  = useAccuracy()

  const history = histData?.history ?? []

  return (
    <div>
      <Header
        title="Analytics"
        subtitle="Champion probability trends · Model accuracy · Brier scores"
      />

      {/* Tab strip */}
      <div className="flex gap-1 mb-6 border-b border-gray-100 dark:border-navy-700">
        {TABS.map((t, i) => (
          <button
            key={t}
            onClick={() => setTab(i)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === i
                ? 'border-accent text-accent'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 0 && (
        <div className="space-y-6">
          <ChampionChart history={history} />
          <CurrentWinTable history={history} />
        </div>
      )}

      {tab === 1 && <AccuracyPanel data={accData} />}
    </div>
  )
}
