import Header from '../components/Header'
import Ticker from '../components/Ticker'
import GroupTable from '../components/GroupTable'
import MatchCard from '../components/MatchCard'
import { useSchedule, useStandings } from '../hooks/useApi'

function Skeleton({ rows = 4 }) {
  return (
    <div className="card p-4 animate-pulse">
      <div className="h-4 bg-gray-200 dark:bg-navy-700 rounded mb-3 w-1/3" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-3 bg-gray-100 dark:bg-navy-700/60 rounded mb-2" />
      ))}
    </div>
  )
}

const GROUP_LETTERS = ['A','B','C','D','E','F','G','H','I','J','K','L']

export default function Standings() {
  const { data: schedule, isLoading: schedLoading } = useSchedule()
  const { data: standings, isLoading: stdLoading }  = useStandings()

  const played   = schedule?.played   ?? []
  const upcoming = schedule?.upcoming ?? []

  return (
    <div>
      <Header
        title="Live Group Standings"
        subtitle="FIFA World Cup 2026 · All 12 groups"
      />

      <Ticker played={played} upcoming={upcoming} />

      {/* Groups grid */}
      <div className="mb-2">
        <h2 className="section-title">Group Standings</h2>
        <p className="section-sub">
          Top 2 per group advance · 8 best 3rd-place teams also qualify (32 teams total)
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mb-8">
        {stdLoading
          ? GROUP_LETTERS.map(g => <Skeleton key={g} />)
          : GROUP_LETTERS.map(g => (
              <GroupTable
                key={g}
                letter={g}
                rows={standings?.[g] ?? []}
              />
            ))}
      </div>

      {/* Upcoming matches */}
      <div className="border-t border-gray-200 dark:border-navy-700 pt-6 mb-2">
        <h2 className="section-title">Upcoming Matches</h2>
        <p className="section-sub">
          ML ensemble predictions · XGBoost + Poisson + Elo
        </p>
      </div>

      {schedLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} rows={3} />)}
        </div>
      ) : upcoming.length === 0 ? (
        <div className="card p-8 text-center text-gray-500 dark:text-gray-400">
          All group stage matches have been played!
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {upcoming.slice(0, 9).map((m, i) => (
            <MatchCard key={i} match={m} />
          ))}
        </div>
      )}
    </div>
  )
}
