import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, MapPin, Clock, Calendar } from 'lucide-react'
import Header from '../components/Header'
import { useLive } from '../hooks/useApi'
import { confColor, pct } from '../lib/utils'

const REFRESH_SECS = 30

// ── Refresh countdown bar ──────────────────────────────────────────────────
function RefreshBar({ onRefetch, isFetching, fetchedAt }) {
  const [secs, setSecs] = useState(REFRESH_SECS)

  useEffect(() => {
    setSecs(REFRESH_SECS)
  }, [fetchedAt])

  useEffect(() => {
    const t = setInterval(() => {
      setSecs(s => {
        if (s <= 1) { onRefetch(); return REFRESH_SECS }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(t)
  }, [onRefetch])

  const updatedTime = fetchedAt
    ? new Date(fetchedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—'

  return (
    <div className="flex items-center gap-3 mb-6 text-sm text-gray-500 dark:text-gray-400">
      <button
        onClick={onRefetch}
        disabled={isFetching}
        className="flex items-center gap-1.5 text-accent hover:text-accent-hover font-medium transition-colors"
      >
        <RefreshCw size={13} className={isFetching ? 'animate-spin' : ''} />
        Refresh now
      </button>
      <span className="text-gray-300 dark:text-navy-600">·</span>
      <span>Auto-refresh in <strong className="text-gray-700 dark:text-gray-200">{secs}s</strong></span>
      <span className="text-gray-300 dark:text-navy-600">·</span>
      <span>Updated {updatedTime}</span>
    </div>
  )
}

// ── Progress bar inside live card ─────────────────────────────────────────
function ProbMini({ p_home, p_draw, p_away, home, away }) {
  if (!p_home && !p_draw && !p_away) return null
  return (
    <div className="mt-3 pt-3 border-t border-gray-100 dark:border-navy-700">
      <p className="text-xs text-gray-400 dark:text-gray-500 mb-1.5 font-medium">Pre-match prediction</p>
      <div className="flex gap-1 h-1.5 rounded-full overflow-hidden">
        <div style={{ width: `${(p_home ?? 1/3) * 100}%`, background: '#34a853' }} />
        <div style={{ width: `${(p_draw ?? 1/3) * 100}%`, background: '#fbbc04' }} />
        <div style={{ width: `${(p_away ?? 1/3) * 100}%`, background: '#ea4335' }} />
      </div>
      <div className="flex justify-between text-xs text-gray-400 dark:text-gray-500 mt-1">
        <span>{home?.split(' ').slice(-1)[0]} {pct(p_home ?? 1/3, 0)}</span>
        <span>Draw {pct(p_draw ?? 1/3, 0)}</span>
        <span>{pct(p_away ?? 1/3, 0)} {away?.split(' ').slice(-1)[0]}</span>
      </div>
    </div>
  )
}

// ── Live win probability bar ───────────────────────────────────────────────
function LiveProbBar({ p_home, p_draw, p_away, home, away }) {
  if (p_home == null) return null
  const ph = (p_home * 100).toFixed(0)
  const pd = (p_draw  * 100).toFixed(0)
  const pa = (p_away  * 100).toFixed(0)
  const leader = p_home > p_away ? home : (p_away > p_home ? away : null)
  return (
    <div className="mt-3 pt-3 border-t border-gray-100 dark:border-navy-700">
      <p className="text-xs text-gray-400 dark:text-gray-500 mb-1.5 font-medium flex items-center gap-1">
        <span className="inline-block w-2 h-2 rounded-full bg-red-500 animate-pulse" />
        Live win probability
      </p>
      <div className="flex gap-0.5 h-2 rounded-full overflow-hidden">
        <div style={{ width: `${ph}%`, background: '#34a853', transition: 'width 0.8s ease' }} />
        <div style={{ width: `${pd}%`, background: '#fbbc04', transition: 'width 0.8s ease' }} />
        <div style={{ width: `${pa}%`, background: '#ea4335', transition: 'width 0.8s ease' }} />
      </div>
      <div className="flex justify-between text-xs mt-1.5">
        <span className={p_home > p_away ? 'font-bold text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'}>
          {home?.split(' ').slice(-1)[0]} {ph}%
        </span>
        <span className="text-gray-400 dark:text-gray-500">Draw {pd}%</span>
        <span className={p_away > p_home ? 'font-bold text-red-500 dark:text-red-400' : 'text-gray-400 dark:text-gray-500'}>
          {pa}% {away?.split(' ').slice(-1)[0]}
        </span>
      </div>
    </div>
  )
}

// ── LIVE match card ────────────────────────────────────────────────────────
function LiveMatchCard({ match }) {
  const {
    home_team, home_score, home_logo, home_abbr,
    away_team, away_score, away_logo, away_abbr,
    status_detail, clock, venue, group,
    p_home, p_draw, p_away,
    live_p_home, live_p_draw, live_p_away,
  } = match

  const isHT = status_detail?.toLowerCase().includes('half') || status_detail === 'HT'

  return (
    <div className="card overflow-hidden">
      {/* Live header */}
      <div
        className="px-4 py-2 flex items-center justify-between"
        style={{ background: 'linear-gradient(90deg, #0d1b2a, #1a3a6e)' }}
      >
        <div className="flex items-center gap-2">
          <span
            className="text-white text-[10px] font-black px-2 py-0.5 rounded"
            style={{ background: '#ea4335', animation: 'pulse 1.5s ease-in-out infinite', letterSpacing: '1px' }}
          >
            LIVE
          </span>
          {group && <span className="text-white/60 text-xs">{group}</span>}
        </div>
        <span className="text-white font-bold text-sm">
          {isHT ? 'Half Time' : (clock ? clock + "'" : status_detail)}
        </span>
      </div>

      {/* Scoreboard */}
      <div className="px-5 py-5">
        <div className="flex items-center justify-between gap-4">
          {/* Home */}
          <div className="flex-1 flex flex-col items-center gap-2 text-center">
            {home_logo
              ? <img src={home_logo} alt={home_abbr} className="h-12 w-12 object-contain" />
              : <div className="h-12 w-12 rounded-full bg-gray-100 dark:bg-navy-700 flex items-center justify-center text-lg font-bold text-gray-500">{home_abbr?.slice(0,3)}</div>
            }
            <p className="font-bold text-gray-900 dark:text-gray-50 text-sm leading-tight">{home_team}</p>
          </div>

          {/* Score */}
          <div className="flex items-center gap-3 shrink-0">
            <span className="text-4xl font-extrabold text-gray-900 dark:text-white tabular-nums">
              {home_score ?? 0}
            </span>
            <span className="text-gray-300 dark:text-navy-600 text-2xl font-light">—</span>
            <span className="text-4xl font-extrabold text-gray-900 dark:text-white tabular-nums">
              {away_score ?? 0}
            </span>
          </div>

          {/* Away */}
          <div className="flex-1 flex flex-col items-center gap-2 text-center">
            {away_logo
              ? <img src={away_logo} alt={away_abbr} className="h-12 w-12 object-contain" />
              : <div className="h-12 w-12 rounded-full bg-gray-100 dark:bg-navy-700 flex items-center justify-center text-lg font-bold text-gray-500">{away_abbr?.slice(0,3)}</div>
            }
            <p className="font-bold text-gray-900 dark:text-gray-50 text-sm leading-tight">{away_team}</p>
          </div>
        </div>

        {venue && (
          <div className="flex items-center justify-center gap-1 mt-3 text-xs text-gray-400 dark:text-gray-500">
            <MapPin size={11} />
            {venue}
          </div>
        )}

        {/* Live probability (Poisson-based, updates with score) */}
        {live_p_home != null
          ? <LiveProbBar p_home={live_p_home} p_draw={live_p_draw} p_away={live_p_away}
                         home={home_team} away={away_team} />
          : <ProbMini p_home={p_home} p_draw={p_draw} p_away={p_away}
                      home={home_team} away={away_team} />
        }
      </div>
    </div>
  )
}

// ── Upcoming match card ────────────────────────────────────────────────────
function UpcomingCard({ match }) {
  const {
    home_team, home_logo, home_abbr,
    away_team, away_logo, away_abbr,
    date, venue, group,
    p_home, p_draw, p_away,
  } = match

  const kickoff = date ? new Date(date) : null
  const now     = new Date()
  const diffMs  = kickoff ? kickoff - now : 0
  const diffH   = Math.floor(diffMs / 3_600_000)
  const diffM   = Math.floor((diffMs % 3_600_000) / 60_000)
  const timeStr = kickoff
    ? kickoff.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : '—'

  const countdown = diffMs > 0
    ? diffH > 0 ? `${diffH}h ${diffM}m` : `${diffM}m`
    : 'Starting soon'

  const fav   = (p_home ?? 1/3) >= (p_away ?? 1/3) ? home_team : away_team
  const favP  = Math.max(p_home ?? 1/3, p_away ?? 1/3)
  const color = confColor(favP)

  return (
    <div className="card p-4 hover:-translate-y-0.5 hover:shadow-md transition-all duration-150">
      {/* Header row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 font-medium">
          <Clock size={11} />
          {timeStr}
          {group && <span className="text-gray-300 dark:text-navy-600 mx-1">·</span>}
          {group && <span>{group}</span>}
        </div>
        <span className="badge bg-blue-50 dark:bg-blue-900/20 text-accent text-[10px]">
          ⏱ {countdown}
        </span>
      </div>

      {/* Teams */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          {home_logo
            ? <img src={home_logo} alt="" className="h-8 w-8 object-contain shrink-0" />
            : <div className="h-8 w-8 rounded-full bg-gray-100 dark:bg-navy-700 flex items-center justify-center text-xs font-bold text-gray-500 shrink-0">{home_abbr?.slice(0,3)}</div>
          }
          <span className="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate">{home_team}</span>
        </div>

        <span className="text-xs font-bold text-gray-400 dark:text-gray-500 px-3 shrink-0">vs</span>

        <div className="flex items-center gap-2 flex-1 min-w-0 justify-end">
          <span className="font-semibold text-sm text-gray-900 dark:text-gray-100 truncate text-right">{away_team}</span>
          {away_logo
            ? <img src={away_logo} alt="" className="h-8 w-8 object-contain shrink-0" />
            : <div className="h-8 w-8 rounded-full bg-gray-100 dark:bg-navy-700 flex items-center justify-center text-xs font-bold text-gray-500 shrink-0">{away_abbr?.slice(0,3)}</div>
          }
        </div>
      </div>

      {/* Prediction */}
      {(p_home || p_draw || p_away) && (
        <div className="mt-3 pt-3 border-t border-gray-100 dark:border-navy-700">
          <div className="flex gap-1 h-1.5 rounded-full overflow-hidden">
            <div style={{ width: `${(p_home ?? 1/3) * 100}%`, background: '#34a853' }} />
            <div style={{ width: `${(p_draw ?? 1/3) * 100}%`, background: '#fbbc04' }} />
            <div style={{ width: `${(p_away ?? 1/3) * 100}%`, background: '#ea4335' }} />
          </div>
          <div className="flex justify-between text-xs text-gray-400 dark:text-gray-500 mt-1">
            <span>{pct(p_home ?? 1/3, 0)}</span>
            <span style={{ color }} className="font-semibold">Fav: {fav.split(' ').slice(-1)[0]}</span>
            <span>{pct(p_away ?? 1/3, 0)}</span>
          </div>
        </div>
      )}

      {venue && (
        <div className="flex items-center gap-1 mt-2 text-xs text-gray-400 dark:text-gray-500">
          <MapPin size={10} />
          {venue}
        </div>
      )}
    </div>
  )
}

// ── Recent result card ─────────────────────────────────────────────────────
function RecentCard({ match }) {
  const {
    home_team, home_score, home_logo, home_abbr,
    away_team, away_score, away_logo, away_abbr,
    group, venue,
  } = match

  const winner = home_score > away_score ? 'home'
               : away_score > home_score ? 'away'
               : 'draw'

  return (
    <div className="card px-4 py-3 flex items-center gap-3">
      {/* Home */}
      <div className="flex items-center gap-2 flex-1 min-w-0">
        {home_logo
          ? <img src={home_logo} alt="" className="h-7 w-7 object-contain shrink-0" />
          : <div className="h-7 w-7 rounded-full bg-gray-100 dark:bg-navy-700 flex items-center justify-center text-xs font-bold text-gray-500 shrink-0">{home_abbr?.slice(0,3)}</div>
        }
        <span className={`text-sm font-${winner === 'home' ? 'bold' : 'medium'} text-gray-${winner === 'home' ? '900 dark:text-gray-50' : '500 dark:text-gray-400'} truncate`}>
          {home_team}
        </span>
      </div>

      {/* Score */}
      <div className="text-center shrink-0">
        <div className="text-base font-extrabold text-gray-900 dark:text-white tabular-nums">
          {home_score ?? 0} – {away_score ?? 0}
        </div>
        <div className="text-[10px] text-gray-400 dark:text-gray-500 font-bold uppercase tracking-wide">FT</div>
      </div>

      {/* Away */}
      <div className="flex items-center gap-2 flex-1 min-w-0 justify-end">
        <span className={`text-sm font-${winner === 'away' ? 'bold' : 'medium'} text-gray-${winner === 'away' ? '900 dark:text-gray-50' : '500 dark:text-gray-400'} truncate text-right`}>
          {away_team}
        </span>
        {away_logo
          ? <img src={away_logo} alt="" className="h-7 w-7 object-contain shrink-0" />
          : <div className="h-7 w-7 rounded-full bg-gray-100 dark:bg-navy-700 flex items-center justify-center text-xs font-bold text-gray-500 shrink-0">{away_abbr?.slice(0,3)}</div>
        }
      </div>
    </div>
  )
}

// ── Empty state ────────────────────────────────────────────────────────────
function Empty({ icon, title, sub }) {
  return (
    <div className="card p-8 text-center col-span-full">
      <div className="text-4xl mb-3">{icon}</div>
      <p className="font-semibold text-gray-700 dark:text-gray-300">{title}</p>
      {sub && <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">{sub}</p>}
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────
export default function Live() {
  const { data, isFetching, refetch, dataUpdatedAt } = useLive()

  const live     = data?.live     ?? []
  const upcoming = data?.upcoming ?? []
  const recent   = data?.recent   ?? []

  const handleRefetch = useCallback(() => { refetch() }, [refetch])

  return (
    <div>
      <Header
        title="Live Match Tracker"
        subtitle="Real-time scores · Auto-refreshes every 30 seconds"
      />

      <RefreshBar
        onRefetch={handleRefetch}
        isFetching={isFetching}
        fetchedAt={data?.fetched_at}
      />

      {/* ── Live matches ── */}
      <section className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <h2 className="section-title mb-0">
            Live Now
          </h2>
          {live.length > 0 && (
            <span
              className="text-white text-[10px] font-black px-2 py-0.5 rounded"
              style={{ background: '#ea4335', letterSpacing: '1px' }}
            >
              {live.length} LIVE
            </span>
          )}
        </div>

        {live.length === 0 ? (
          <Empty
            icon="⚽"
            title="No matches live right now"
            sub="Live scores will appear here during matches"
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {live.map(m => <LiveMatchCard key={m.id} match={m} />)}
          </div>
        )}
      </section>

      {/* ── Upcoming ── */}
      <section className="mb-8">
        <h2 className="section-title mb-1">Upcoming Today</h2>
        <p className="section-sub">With our ML predictions where available</p>

        {upcoming.length === 0 ? (
          <Empty icon="📅" title="No more matches scheduled today" />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {upcoming.map(m => <UpcomingCard key={m.id} match={m} />)}
          </div>
        )}
      </section>

      {/* ── Recent results ── */}
      <section>
        <h2 className="section-title mb-1">Recent Results</h2>
        <p className="section-sub">Matches completed today</p>

        {recent.length === 0 ? (
          <Empty icon="🏁" title="No completed matches yet today" />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {recent.map(m => <RecentCard key={m.id} match={m} />)}
          </div>
        )}
      </section>
    </div>
  )
}
