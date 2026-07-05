import { confColor } from '../lib/utils'

const TH = 'px-3 py-2 text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide text-center'
const TD = 'px-3 py-2.5 text-sm text-center text-gray-700 dark:text-gray-200'

export default function GroupTable({ letter, rows = [] }) {
  return (
    <div className="card overflow-hidden">
      {/* Group header */}
      <div
        className="px-4 py-2.5 text-white font-bold text-xs uppercase tracking-widest"
        style={{ background: 'linear-gradient(90deg, #1a3a6e, #1a73e8)' }}
      >
        ⚽ Group {letter}
      </div>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-gray-50 dark:bg-navy-900/50">
            <th className={`${TH} text-left pl-3 w-6`}>#</th>
            <th className={`${TH} text-left`}>Team</th>
            <th className={TH}>Pts</th>
            <th className={TH}>W</th>
            <th className={TH}>D</th>
            <th className={TH}>L</th>
            <th className={TH}>GF</th>
            <th className={TH}>GA</th>
            <th className={TH}>GD</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const qualifyBg =
              row.rank === 1
                ? 'bg-green-50 dark:bg-green-900/15'
                : row.rank === 2
                ? 'bg-green-50/50 dark:bg-green-900/8'
                : ''
            const gd      = row.gd
            const gdColor = gd > 0 ? 'text-green-600 dark:text-green-400'
                          : gd < 0 ? 'text-red-500 dark:text-red-400'
                          : 'text-gray-400'

            return (
              <tr
                key={row.team}
                className={`border-t border-gray-100 dark:border-navy-700 ${qualifyBg}
                            hover:bg-gray-50 dark:hover:bg-navy-700/40 transition-colors`}
              >
                <td className={`${TD} text-gray-400 text-xs font-medium`}>{row.rank}</td>
                <td className={`${TD} text-left font-semibold text-gray-900 dark:text-gray-100`}>
                  {row.team}
                </td>
                <td className={`${TD} font-bold text-gray-900 dark:text-gray-50`}>{row.pts}</td>
                <td className={TD}>{row.w}</td>
                <td className={TD}>{row.d}</td>
                <td className={TD}>{row.l}</td>
                <td className={TD}>{row.gf}</td>
                <td className={TD}>{row.ga}</td>
                <td className={`${TD} font-semibold ${gdColor}`}>
                  {gd > 0 ? `+${gd}` : gd}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
