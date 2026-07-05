import { WC_LOGO } from '../lib/utils'

export default function Header({ title, subtitle }) {
  return (
    <div
      className="rounded-2xl p-6 mb-6 flex items-center gap-5 shadow-lg shadow-blue-900/20"
      style={{
        background: 'linear-gradient(135deg, #0d1b2a 0%, #1a3a6e 50%, #1a73e8 100%)',
      }}
    >
      <img
        src={WC_LOGO}
        alt="WC 2026"
        className="h-14 rounded-xl shadow-md shadow-black/30 shrink-0"
        onError={e => { e.target.style.display = 'none' }}
      />
      <div className="min-w-0">
        <p className="text-blue-200 text-xs font-bold uppercase tracking-widest">WC Oracle</p>
        <h1 className="text-white font-extrabold text-2xl leading-tight mt-0.5 truncate">
          {title}
        </h1>
        <p className="text-blue-200/80 text-sm mt-1">{subtitle}</p>
      </div>
      <div className="ml-auto shrink-0 text-blue-200/60 text-xs text-right hidden sm:block">
        🔄 Updates after each match
      </div>
    </div>
  )
}
