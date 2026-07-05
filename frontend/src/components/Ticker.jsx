export default function Ticker({ played = [], upcoming = [] }) {
  const items = [
    ...played.slice(-8).map(m =>
      `✅ ${m.home_team} ${m.home_score}–${m.away_score} ${m.away_team}`
    ),
    ...upcoming.slice(0, 5).map(m =>
      `⏰ ${m.home_team} vs ${m.away_team}`
    ),
  ]

  if (!items.length) return null

  const text = items.join('   ·   ')

  return (
    <div
      className="rounded-xl mb-5 flex items-center gap-3 overflow-hidden"
      style={{ background: '#060d18', padding: '10px 16px' }}
    >
      <span
        className="shrink-0 text-white text-xs font-black px-2.5 py-1 rounded
                   animate-pulse-slow"
        style={{ background: '#ea4335', letterSpacing: '1.5px' }}
      >
        LIVE
      </span>
      <div className="overflow-hidden flex-1">
        <span
          className="text-gray-300 text-sm font-medium animate-ticker"
          style={{ display: 'inline-block', whiteSpace: 'nowrap' }}
        >
          {text}
        </span>
      </div>
    </div>
  )
}
