import { useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, CartesianGrid,
} from 'recharts'
import Header from '../components/Header'
import { useSimulation, useRunSimulation } from '../hooks/useApi'
import {
  ROUND_KEYS, ROUND_LABELS, ROUND_SHOW, confColor, topTeamsForRound, pct,
} from '../lib/utils'
import { useDark } from '../App'
import { RefreshCw } from 'lucide-react'

function BracketTeamCard({ name, prob }) {
  const color = confColor(prob)
  return (
    <div
      className="card px-3 py-2.5 text-center hover:-translate-y-0.5
                 hover:shadow-md transition-all duration-150"
      style={{ borderBottom: `3px solid ${color}` }}
    >
      <p className="text-xs font-bold text-gray-800 dark:text-gray-100 truncate">{name}</p>
      <p className="text-sm font-extrabold mt-0.5" style={{ color }}>{pct(prob)}</p>
    </div>
  )
}

const CustomTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-sm shadow-lg">
      <p className="font-semibold text-gray-800 dark:text-gray-100 truncate max-w-[160px]">
        {payload[0].payload.name}
      </p>
      <p style={{ color: payload[0].fill }}>{pct(payload[0].value / 100)}</p>
    </div>
  )
}

export default function BracketSimulator() {
  const { dark } = useDark()
  const { data: sim, isLoading } = useSimulation()
  const runSim = useRunSimulation()
  const [simMsg, setSimMsg] = useState('')

  const teams = sim?.teams ?? []
  const meta  = sim?.meta  ?? {}
  const axisColor = dark ? '#9aa0a6' : '#6b7280'
  const gridColor = dark ? '#1a2744' : '#f3f4f6'

  function handleRerun() {
    setSimMsg('Running 10 000 simulations in background…')
    runSim.mutate(undefined, {
      onSuccess: () => setSimMsg('Done! Refresh in ~15 seconds for updated results.'),
      onError:   () => setSimMsg('Error starting simulation.'),
    })
  }

  // All-team win% chart (sorted)
  const allWins = [...teams]
    .sort((a, b) => b.Winner - a.Winner)
    .map(t => ({ name: t.name, value: t.Winner * 100, color: confColor(t.Winner) }))

  return (
    <div>
      <Header title="Bracket Simulator" subtitle="Most likely teams at each stage · 100 000 simulations" />

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <button onClick={handleRerun} disabled={runSim.isPending} className="btn-primary flex items-center gap-2">
          <RefreshCw size={14} className={runSim.isPending ? 'animate-spin' : ''} />
          Re-run Simulation
        </button>
        {meta.n_simulations && (
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {meta.n_simulations?.toLocaleString()} simulations · {meta.played_matches} matches played
          </span>
        )}
        {simMsg && <span className="text-sm text-accent font-medium">{simMsg}</span>}
      </div>

      {/* Stage-by-stage bracket */}
      {isLoading ? (
        <div className="card p-8 text-center text-gray-400 animate-pulse">Loading simulation…</div>
      ) : (
        <div className="space-y-6 mb-8">
          {ROUND_KEYS.map(rnd => {
            const top = topTeamsForRound(teams, rnd, ROUND_SHOW[rnd])
            const cols = Math.min(ROUND_SHOW[rnd], 8)
            return (
              <div key={rnd}>
                <div className="flex items-center gap-3 mb-3">
                  <span
                    className="text-white text-xs font-bold px-4 py-1.5 rounded-full whitespace-nowrap"
                    style={{ background: '#1a73e8' }}
                  >
                    {ROUND_LABELS[rnd]}
                  </span>
                  <div className="flex-1 border-t border-gray-200 dark:border-navy-700" />
                </div>
                <div
                  className="grid gap-2"
                  style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
                >
                  {top.map(t => (
                    <BracketTeamCard key={t.name} name={t.name} prob={t[rnd]} />
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Win probability — all 48 teams */}
      <div className="border-t border-gray-200 dark:border-navy-700 pt-6">
        <h2 className="section-title">Win Probability — All 48 Teams</h2>
        <p className="section-sub">Sorted by chance to win the tournament</p>

        <div className="card p-5">
          <ResponsiveContainer width="100%" height={520}>
            <BarChart
              layout="vertical"
              data={allWins}
              margin={{ top: 0, right: 60, left: 110, bottom: 0 }}
            >
              <CartesianGrid horizontal={false} stroke={gridColor} />
              <XAxis
                type="number"
                tick={{ fill: axisColor, fontSize: 11 }}
                axisLine={false} tickLine={false}
                tickFormatter={v => `${v.toFixed(0)}%`}
              />
              <YAxis
                type="category" dataKey="name" width={105}
                tick={{ fill: dark ? '#e2e8f0' : '#374151', fontSize: 11 }}
                axisLine={false} tickLine={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(26,115,232,0.06)' }} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]}
                label={{ position: 'right', formatter: v => `${v.toFixed(1)}%`,
                         fill: axisColor, fontSize: 10 }}
              >
                {allWins.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
