export const WC_LOGO =
  'https://upload.wikimedia.org/wikipedia/en/thumb/3/30/2026_FIFA_World_Cup.svg/200px-2026_FIFA_World_Cup.svg.png'

export const ROUND_LABELS = {
  R32:    'Rd of 32',
  R16:    'Rd of 16',
  QF:     'Quarter-Final',
  SF:     'Semi-Final',
  Final:  'Final',
  Winner: 'Champion',
}

export const ROUND_KEYS = ['R32', 'R16', 'QF', 'SF', 'Final', 'Winner']

export const ROUND_SHOW = { R32: 16, R16: 8, QF: 4, SF: 4, Final: 2, Winner: 1 }

/** Tailwind colour class based on probability */
export function confColor(p) {
  if (typeof p !== 'number' || isNaN(p)) return '#ea4335'
  if (p >= 0.65) return '#34a853'
  if (p >= 0.50) return '#fbbc04'
  return '#ea4335'
}

export function confBg(p) {
  if (typeof p !== 'number' || isNaN(p)) return 'bg-red-50 dark:bg-red-900/20 text-red-600'
  if (p >= 0.65) return 'bg-green-50 dark:bg-green-900/20 text-green-600'
  if (p >= 0.50) return 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-600'
  return 'bg-red-50 dark:bg-red-900/20 text-red-600'
}

export function pct(val, decimals = 1) {
  return `${(val * 100).toFixed(decimals)}%`
}

export function topTeamsForRound(teams, roundKey, n) {
  return [...teams]
    .sort((a, b) => b[roundKey] - a[roundKey])
    .slice(0, n)
}
