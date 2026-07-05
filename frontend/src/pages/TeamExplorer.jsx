import { useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid,
} from 'recharts'
import Header from '../components/Header'
import { useSimulation, useTeams } from '../hooks/useApi'
import { ROUND_KEYS, ROUND_LABELS, confColor, pct } from '../lib/utils'
import { useDark } from '../App'

function ProbRow({ label, value }) {
  const color = confColor(value)
  return (
    <div className="card px-4 py-3 flex items-center gap-3">
      <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 w-28 shrink-0">
        {label}
      </span>
      <div className="prob-bar-outer flex-1">
        <div
          className="h-1.5 rounded-full transition-all duration-700"
          style={{ width: `${value * 100}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-sm font-bold w-12 text-right" style={{ color }}>
        {pct(value)}
      </span>
    </div>
  )
}

function StatCard({ label, value }) {
  return (
    <div className="card p-4 text-center">
      <div className="text-2xl font-extrabold text-accent">{value}</div>
      <div className="text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide mt-1">{label}</div>
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-sm shadow-lg">
      <p className="font-semibold text-gray-800 dark:text-gray-100">{label}</p>
      <p style={{ color: payload[0].fill }}>{pct(payload[0].value / 100)}</p>
    </div>
  )
}

export default function TeamExplorer() {
  const { dark } = useDark()
  const { data: sim  } = useSimulation()
  const { data: teamsData } = useTeams()

  const allTeams = teamsData?.teams?.slice().sort() ?? []
  const groups   = teamsData?.groups ?? {}

  const [selected, setSelected] = useState('')

  const teamObj = sim?.teams?.find(t => t.name === selected)
  const group   = teamObj?.group ?? '?'
  const rivals  = (groups[group] ?? []).filter(t => t !== selected)

  const chartData = ROUND_KEYS.map(k => ({
    label: ROUND_LABELS[k],
    value: (teamObj?.[k] ?? 0) * 100,
    color: confColor(teamObj?.[k] ?? 0),
  }))

  const axisColor = dark ? '#9aa0a6' : '#6b7280'
  const gridColor = dark ? '#1a2744' : '#f3f4f6'

  return (
    <div>
      <Header title="Team Explorer" subtitle="Tournament probabilities and stats for every team" />

      <div className="mb-6 max-w-xs">
        <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
          Select a team
        </label>
        <select
          value={selected}
          onChange={e => setSelected(e.target.value)}
          className="w-full card px-4 py-2.5 text-sm font-medium text-gray-900 dark:text-gray-100
                     bg-white dark:bg-navy-800 border border-gray-200 dark:border-navy-600
                     rounded-xl focus:outline-none focus:ring-2 focus:ring-accent/40 cursor-pointer"
        >
          <option value="">Choose a team…</option>
          {allTeams.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {!selected && (
        <div className="card p-12 text-center text-gray-400 dark:text-gray-500">
          Select a team above to explore their tournament probabilities.
        </div>
      )}

      {selected && teamObj && (
        <>
          {/* Team banner */}
          <div
            className="rounded-2xl px-6 py-5 mb-6 text-white shadow-lg shadow-blue-900/20"
            style={{ background: 'linear-gradient(135deg, #0d1b2a, #1a3a6e, #1a73e8)' }}
          >
            <p className="text-2xl font-extrabold">{selected}</p>
            <p className="text-blue-200/80 text-sm mt-1">
              Group {group} · <strong>{pct(teamObj.Winner)}</strong> chance to win the World Cup
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-6">
            {/* Left: prob bars + rivals */}
            <div className="lg:col-span-2 space-y-2">
              <h3 className="section-title text-base">Advancement Probabilities</h3>
              {ROUND_KEYS.map(k => (
                <ProbRow key={k} label={ROUND_LABELS[k]} value={teamObj[k]} />
              ))}

              <div className="pt-4">
                <h3 className="section-title text-base mb-3">Group {group} Rivals</h3>
                <div className="space-y-2">
                  {rivals.map(rival => {
                    const rObj  = sim?.teams?.find(t => t.name === rival)
                    const rWin  = rObj?.Winner ?? 0
                    const color = confColor(rWin + 0.3)
                    return (
                      <div key={rival}
                        className="card flex items-center justify-between px-4 py-2.5">
                        <span className="text-sm font-medium text-gray-800 dark:text-gray-200">{rival}</span>
                        <span className="text-sm font-bold" style={{ color }}>{pct(rWin)}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>

            {/* Right: bar chart */}
            <div className="lg:col-span-3 card p-5">
              <h3 className="font-bold text-gray-800 dark:text-gray-100 mb-4">
                {selected} — Path to Glory
              </h3>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={chartData} margin={{ top: 20, right: 10, left: -10, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke={gridColor} />
                  <XAxis dataKey="label" tick={{ fill: axisColor, fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: axisColor, fontSize: 11 }} axisLine={false} tickLine={false}
                         tickFormatter={v => `${v.toFixed(0)}%`} />
                  <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(26,115,232,0.06)' }} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]} label={{
                    position: 'top', formatter: v => `${v.toFixed(1)}%`,
                    fill: axisColor, fontSize: 11,
                  }}>
                    {chartData.map((d, i) => <Cell key={i} fill={d.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
