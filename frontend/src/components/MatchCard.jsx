import { confColor, pct } from '../lib/utils'

function ProbBar({ value, color }) {
  return (
    <div className="prob-bar-outer mt-1">
      <div
        className="h-1.5 rounded-full transition-all duration-700"
        style={{ width: `${value * 100}%`, backgroundColor: color }}
      />
    </div>
  )
}

export default function MatchCard({ match }) {
  const { home_team, away_team, group, p_home = 1/3, p_draw = 1/3, p_away = 1/3 } = match
  const fav   = p_home >= p_away ? home_team : away_team
  const favP  = Math.max(p_home, p_away)
  const color = confColor(favP)

  return (
    <div
      className="card p-4 hover:-translate-y-0.5 hover:shadow-md transition-all duration-150"
      style={{ borderLeft: `4px solid ${color}` }}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-bold text-gray-400 dark:text-gray-500 uppercase tracking-wide">
          Group {group}
        </span>
        <span className="text-xs font-bold" style={{ color }}>
          {fav} {pct(favP, 0)}
        </span>
      </div>

      <p className="font-bold text-gray-900 dark:text-gray-50 mb-3 text-[15px]">
        {home_team} <span className="text-accent font-normal text-sm">vs</span> {away_team}
      </p>

      <div className="grid grid-cols-3 gap-2 text-center text-xs text-gray-500 dark:text-gray-400">
        {[
          { label: home_team.split(' ')[0], prob: p_home, color: '#34a853' },
          { label: 'Draw',                  prob: p_draw,  color: '#fbbc04' },
          { label: away_team.split(' ')[0], prob: p_away,  color: '#ea4335' },
        ].map(({ label, prob, color: c }) => (
          <div key={label}>
            <div className="font-bold text-gray-800 dark:text-gray-200 text-sm">{pct(prob, 0)}</div>
            <ProbBar value={prob} color={c} />
            <div className="mt-1 truncate">{label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
