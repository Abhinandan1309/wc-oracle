import { useState, useCallback } from 'react'
import { Shuffle, X, ChevronRight, Info } from 'lucide-react'
import { useBracket, usePaths, useWhatIf } from '../hooks/useApi'
import Header from '../components/Header'

const ROUND_LABELS = { R32: 'Round of 32', R16: 'Round of 16', QF: 'Quarter-Final', SF: 'Semi-Final', Final: 'Final' }

// ── helpers ────────────────────────────────────────────────────────────────────
function fmtDate(d) {
  if (!d) return ''
  const dt = new Date(d)
  return dt.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

function winColor(p) {
  if (p >= 0.65) return '#34a853'
  if (p >= 0.5)  return '#fbbc04'
  return '#ea4335'
}

// ── Team slot ──────────────────────────────────────────────────────────────────
function TeamSlot({ name, score, prob, isWinner, isLoser, isTBD, isSelected, onTeamClick }) {
  const color = prob != null ? winColor(prob) : '#9aa0a6'
  return (
    <div
      className={`flex items-center justify-between px-2.5 py-1.5 ${onTeamClick && name ? 'cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-900/10' : ''}`}
      onClick={e => { if (onTeamClick && name && !isTBD) { e.stopPropagation(); onTeamClick() } }}
      style={{
        borderLeft: isSelected ? '3px solid #f59e0b'
                  : isWinner  ? '3px solid #1a73e8' : '3px solid transparent',
        opacity: isLoser ? 0.45 : 1,
        background: isSelected ? 'rgba(245,158,11,0.08)' : undefined,
      }}
    >
      <span
        className="text-xs font-semibold truncate max-w-[90px]"
        style={{
          color: isTBD ? '#9aa0a6'
               : isSelected ? '#d97706'
               : isWinner ? '#0d1b2a' : 'inherit',
          fontWeight: isWinner || isSelected ? 700 : 500,
          textDecoration: isLoser ? 'line-through' : 'none',
        }}
      >
        {name ?? '?'}
      </span>
      <span className="text-xs font-bold ml-1 tabular-nums shrink-0"
            style={{ color: score != null ? '#0d1b2a' : color }}>
        {score != null ? score : (prob != null && !isTBD ? `${(prob * 100).toFixed(0)}%` : '')}
      </span>
    </div>
  )
}

// ── Match card ─────────────────────────────────────────────────────────────────
function MatchCard({ match, dim, whatIfMode, isOverride, onMatchClick, onTeamClick, selectedTeam }) {
  if (!match) {
    return (
      <div className="rounded-lg border border-dashed border-gray-200 dark:border-navy-700"
           style={{ height: 72 }} />
    )
  }

  const { home, away, played, home_score, away_score, winner, p_home, p_away, date, venue } = match
  const homeWon = played && winner === home
  const awayWon = played && winner === away
  const homeTBD = !home
  const awayTBD = !away
  const clickable = whatIfMode && !played && home && away

  return (
    <div
      onClick={() => clickable && onMatchClick?.(match)}
      className={`rounded-lg overflow-hidden border select-none ${clickable ? 'cursor-pointer' : ''}`}
      style={{
        borderColor: isOverride ? '#f59e0b'
                   : played ? (homeWon || awayWon ? '#1a73e8' : '#e2e8f0') : '#e2e8f0',
        background: isOverride ? '#fffbeb'
                   : dim ? 'transparent' : 'white',
        boxShadow: clickable ? '0 0 0 2px rgba(245,158,11,0.4)'
                 : dim ? 'none' : '0 1px 6px rgba(0,0,0,0.08)',
        opacity: dim ? 0.5 : 1,
      }}
    >
      <TeamSlot
        name={home ?? '?'}
        score={played ? home_score : null}
        prob={!played ? p_home : null}
        isWinner={homeWon}
        isLoser={played && !homeWon}
        isTBD={homeTBD}
        isSelected={selectedTeam === home}
        onTeamClick={() => home && onTeamClick?.(home)}
      />
      <div className="h-px bg-gray-100 dark:bg-navy-700 mx-0" />
      <TeamSlot
        name={away ?? '?'}
        score={played ? away_score : null}
        prob={!played ? p_away : null}
        isWinner={awayWon}
        isLoser={played && !awayWon}
        isTBD={awayTBD}
        isSelected={selectedTeam === away}
        onTeamClick={() => away && onTeamClick?.(away)}
      />
      {(date || venue) && (
        <div className="px-2.5 pb-1.5 text-[9px] text-gray-400 dark:text-gray-500 leading-tight truncate">
          {fmtDate(date)}{venue ? ` · ${venue}` : ''}
        </div>
      )}
    </div>
  )
}

// ── SVG bracket connector ──────────────────────────────────────────────────────
// Draws the "]" bracket shapes connecting N matches (left col) to N/2 matches (right col)
function Connector({ count, height, color }) {
  const pairCount = count / 2
  const centerOf = (i, n) => height * (2 * i + 1) / (2 * n)

  return (
    <svg width={16} height={height} style={{ flexShrink: 0 }}>
      {Array.from({ length: pairCount }).map((_, pi) => {
        const topY    = centerOf(pi * 2,     count)
        const bottomY = centerOf(pi * 2 + 1, count)
        const midY    = (topY + bottomY) / 2
        return (
          <g key={pi}>
            <path
              d={`M0 ${topY} H8 V${bottomY} H0`}
              stroke={color}
              strokeWidth={1.5}
              fill="none"
              strokeLinecap="round"
            />
            <path
              d={`M8 ${midY} H16`}
              stroke={color}
              strokeWidth={1.5}
              fill="none"
              strokeLinecap="round"
            />
          </g>
        )
      })}
    </svg>
  )
}

// ── Half bracket (one side: R32 → R16 → QF → SF) ──────────────────────────────
const CARD_H   = 75   // px per match card
const GAP      = 6    // px gap between cards (tailwind gap-1.5)
const COL_H    = 8 * (CARD_H + GAP) - GAP  // total column height for 8 R32 matches

function countInHalf(half) { return 8 }  // always 8 R32 per half

function HalfBracket({ structure, matches, reversed, whatIfMode, overrides, onTeamClick, onMatchClick, selectedTeam }) {
  const { sf, qf } = structure

  const r32Nums = qf.flatMap(q => q.r16.flatMap(r => r.r32))
  const r16Nums = qf.flatMap(q => q.r16.map(r => r.match))
  const qfNums  = qf.map(q => q.match)
  const sfNum   = sf

  const r32Cards = r32Nums.map(n => ({ num: n, match: matches[n] }))
  const r16Cards = r16Nums.map(n => ({ num: n, match: matches[n] }))
  const qfCards  = qfNums.map(n => ({ num: n, match: matches[n] }))
  const sfCards  = [{ num: sfNum, match: matches[sfNum] }]

  const connColor = '#d1d5db'

  const columns = [
    { key: 'r32', items: r32Cards },
    { key: 'r16', items: r16Cards },
    { key: 'qf',  items: qfCards  },
    { key: 'sf',  items: sfCards  },
  ]

  const rendered = columns.map((col) => (
    <div key={col.key} className="flex flex-col" style={{ height: COL_H, justifyContent: 'space-around', width: 142 }}>
      {col.items.map(({ num, match }, mi) => (
        <MatchCard
          key={mi}
          match={match}
          whatIfMode={whatIfMode}
          isOverride={overrides && String(num) in overrides}
          onMatchClick={onMatchClick}
          onTeamClick={onTeamClick}
          selectedTeam={selectedTeam}
        />
      ))}
    </div>
  ))

  const connectors = [8, 4, 2].map((n, i) => (
    <Connector key={i} count={n} height={COL_H} color={connColor} />
  ))

  const interleaved = []
  rendered.forEach((col, i) => {
    interleaved.push(col)
    if (i < connectors.length) interleaved.push(connectors[i])
  })

  return (
    <div className="flex items-center" style={{ flexDirection: reversed ? 'row-reverse' : 'row' }}>
      {interleaved}
    </div>
  )
}

// ── Final card (center) ────────────────────────────────────────────────────────
function FinalCard({ match }) {
  return (
    <div className="flex flex-col items-center justify-center" style={{ height: COL_H, width: 160 }}>
      <div className="text-xs font-bold uppercase tracking-widest mb-2"
           style={{ color: '#1a73e8' }}>Final</div>
      <div style={{ width: 148 }}>
        <MatchCard match={match} />
      </div>
      {match?.venue && (
        <div className="text-[9px] text-gray-400 mt-1">{fmtDate(match.date)} · {match.venue}</div>
      )}
    </div>
  )
}

// ── Round labels header ────────────────────────────────────────────────────────
function RoundLabels({ reversed }) {
  const labels = ['R32', 'R16', 'QF', 'SF']
  const widths = [142, 16, 142, 16, 142, 16, 142]

  const cols = labels.map((l, i) => (
    <div key={l} style={{ width: 142 }}
         className="text-center text-[10px] font-bold uppercase tracking-widest text-gray-400 dark:text-gray-500 pb-2">
      {ROUND_LABELS[l]}
    </div>
  ))

  // Interleave spacers for connectors
  const interleaved = []
  cols.forEach((col, i) => {
    interleaved.push(col)
    if (i < cols.length - 1) interleaved.push(<div key={`sp${i}`} style={{ width: 16 }} />)
  })

  return (
    <div className="flex items-end" style={{ flexDirection: reversed ? 'row-reverse' : 'row' }}>
      {interleaved}
    </div>
  )
}

// ── Path to Final panel ────────────────────────────────────────────────────────
function PathPanel({ team, paths, onClose }) {
  const path = paths?.[team] ?? []
  const roundColor = { R32: '#1a73e8', R16: '#9c27b0', QF: '#ff5722', SF: '#fbbc04', Final: '#34a853' }

  return (
    <div className="card p-5 mb-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-bold text-gray-900 dark:text-gray-50">{team} — Path to Final</h3>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">Projected bracket journey</p>
        </div>
        <button onClick={onClose}
          className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-navy-700 transition-colors">
          <X size={16} />
        </button>
      </div>
      {path.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-gray-500">Path unavailable.</p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {path.map((step, i) => (
            <div key={i} className="flex items-center gap-2">
              <div className={`rounded-lg px-3 py-2 text-xs font-medium ${
                step.eliminated
                  ? 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 opacity-60'
                  : step.won
                    ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                    : 'bg-gray-50 dark:bg-navy-700 text-gray-700 dark:text-gray-200'
              }`}>
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider"
                        style={{ color: roundColor[step.round] ?? '#9aa0a6' }}>
                    {step.round}
                  </span>
                  {step.played && (
                    <span className={`text-[10px] font-bold ${step.won ? 'text-green-600 dark:text-green-400' : 'text-red-500'}`}>
                      {step.won ? 'Won' : 'Lost'}
                    </span>
                  )}
                </div>
                <div className={step.eliminated ? 'line-through' : ''}>
                  vs {step.opponent ?? '?'}
                  {step.score && <span className="ml-1 opacity-70">({step.score})</span>}
                </div>
                {!step.played && (
                  <div className="text-[10px] opacity-60 mt-0.5">{(step.p_win * 100).toFixed(0)}% to win</div>
                )}
              </div>
              {i < path.length - 1 && !step.eliminated && (
                <ChevronRight size={14} className="text-gray-300 dark:text-navy-600 shrink-0" />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────
export default function BracketPage() {
  const [overrides, setOverrides]       = useState({})
  const [whatIfMode, setWhatIfMode]     = useState(false)
  const [selectedTeam, setSelectedTeam] = useState(null)
  const [pickingMatch, setPickingMatch] = useState(null)

  const { data: realData, isLoading, isError } = useBracket()
  const { data: pathsData } = usePaths()
  const whatIf = useWhatIf()

  const hasOverrides  = Object.keys(overrides).length > 0
  const displayData   = (hasOverrides && whatIf.data) ? whatIf.data : realData
  const matches       = displayData?.matches ?? {}

  const handleMatchClick = (match) => {
    if (!whatIfMode || match.played) return
    setPickingMatch(match)
  }

  const applyOverride = (matchNum, winner) => {
    const next = { ...overrides, [String(matchNum)]: winner }
    setOverrides(next)
    setPickingMatch(null)
    whatIf.mutate(next)
  }

  const removeOverride = (matchNum) => {
    const next = { ...overrides }
    delete next[String(matchNum)]
    setOverrides(next)
    if (Object.keys(next).length > 0) whatIf.mutate(next)
  }

  const resetAll = () => { setOverrides({}); setWhatIfMode(false) }

  return (
    <div>
      <Header
        title="Knockout Bracket"
        subtitle="Live bracket · Win probabilities from 100k simulations"
      />

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <button
          onClick={() => { setWhatIfMode(m => !m); if (whatIfMode) resetAll() }}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
            whatIfMode
              ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border border-amber-300 dark:border-amber-700'
              : 'bg-gray-100 dark:bg-navy-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-navy-600'
          }`}
        >
          <Shuffle size={14} />
          {whatIfMode ? 'Exit What-If Mode' : 'What-If Simulator'}
        </button>
        {whatIfMode && (
          <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">
            Click any unplayed match to override the winner
          </span>
        )}
        {hasOverrides && (
          <button onClick={resetAll}
            className="text-xs text-gray-400 hover:text-red-500 transition-colors flex items-center gap-1">
            <X size={12} /> Reset
          </button>
        )}
        {whatIf.isPending && (
          <span className="text-xs text-gray-400 animate-pulse">Updating…</span>
        )}
        {!whatIfMode && (
          <span className="text-xs text-gray-400 dark:text-gray-500 ml-auto flex items-center gap-1">
            <Info size={11} /> Click a team to see their path to the final
          </span>
        )}
      </div>

      {/* Active overrides chips */}
      {hasOverrides && (
        <div className="card px-4 py-3 mb-4 flex flex-wrap gap-2 items-center">
          <span className="text-xs font-bold text-amber-600 dark:text-amber-400 mr-1">Overrides:</span>
          {Object.entries(overrides).map(([num, winner]) => (
            <span key={num} className="flex items-center gap-1 badge bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400">
              M{num}: {winner}
              <button onClick={() => removeOverride(Number(num))} className="ml-0.5 hover:text-red-500">
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Path to Final panel */}
      {selectedTeam && !whatIfMode && (
        <PathPanel team={selectedTeam} paths={pathsData?.paths} onClose={() => setSelectedTeam(null)} />
      )}

      {/* Override picker modal */}
      {pickingMatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
             onClick={() => setPickingMatch(null)}>
          <div className="card p-6 max-w-sm w-full mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="font-bold text-gray-900 dark:text-gray-50 mb-1">Override Winner</h3>
            <p className="text-xs text-gray-400 dark:text-gray-500 mb-4">
              Match {pickingMatch.num} · {pickingMatch.round}
            </p>
            <div className="space-y-2">
              {[pickingMatch.home, pickingMatch.away].filter(Boolean).map(team => (
                <button key={team} onClick={() => applyOverride(pickingMatch.num, team)}
                  className="w-full px-4 py-3 rounded-lg text-left font-semibold text-sm
                             bg-gray-50 dark:bg-navy-700 hover:bg-blue-50 dark:hover:bg-blue-900/20
                             hover:text-accent transition-colors border border-transparent hover:border-accent/30">
                  {team}
                </button>
              ))}
            </div>
            <button onClick={() => setPickingMatch(null)}
              className="mt-4 w-full text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading && <div className="card p-12 text-center text-gray-400 animate-pulse">Loading bracket…</div>}
      {isError   && <div className="card p-8 text-center text-red-500">Failed to load bracket data.</div>}

      {displayData && (
        <div className="overflow-x-auto pb-6">
          <div style={{ display: 'inline-flex', alignItems: 'flex-start', gap: 0 }}>
            <div>
              <RoundLabels reversed={false} />
              <HalfBracket
                structure={displayData.structure.sf1}
                matches={matches}
                reversed={false}
                whatIfMode={whatIfMode}
                overrides={overrides}
                onTeamClick={t => { if (!whatIfMode) setSelectedTeam(s => s === t ? null : t) }}
                onMatchClick={handleMatchClick}
                selectedTeam={selectedTeam}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <div style={{ height: 12 }} />
              <div style={{ display: 'flex', alignItems: 'center', height: COL_H }}>
                <Connector count={2} height={COL_H} color="#d1d5db" />
                <FinalCard match={matches[displayData.structure.final]} />
                <svg width={16} height={COL_H} style={{ transform: 'scaleX(-1)' }}>
                  {[0, 1].map(pi => {
                    const topY = COL_H * (2 * pi * 2 + 1) / 8
                    const botY = COL_H * (2 * pi * 2 + 3) / 8
                    const midY = (topY + botY) / 2
                    return (
                      <g key={pi}>
                        <path d={`M0 ${topY} H8 V${botY} H0`} stroke="#d1d5db" strokeWidth={1.5} fill="none" strokeLinecap="round" />
                        <path d={`M8 ${midY} H16`} stroke="#d1d5db" strokeWidth={1.5} fill="none" strokeLinecap="round" />
                      </g>
                    )
                  })}
                </svg>
              </div>
            </div>

            <div>
              <RoundLabels reversed={true} />
              <HalfBracket
                structure={displayData.structure.sf2}
                matches={matches}
                reversed={true}
                whatIfMode={whatIfMode}
                overrides={overrides}
                onTeamClick={t => { if (!whatIfMode) setSelectedTeam(s => s === t ? null : t) }}
                onMatchClick={handleMatchClick}
                selectedTeam={selectedTeam}
              />
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      {displayData && (
        <div className="flex flex-wrap gap-5 mt-2 text-xs text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-sm" style={{ background: '#34a853' }} />
            &gt;65% win probability
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-sm" style={{ background: '#fbbc04' }} />
            50–65%
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-sm" style={{ background: '#ea4335' }} />
            &lt;50%
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2 border-l-[3px] border-[#1a73e8] h-4" />
            Match winner
          </span>
        </div>
      )}
    </div>
  )
}
