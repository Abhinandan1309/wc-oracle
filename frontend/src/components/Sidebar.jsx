import { NavLink } from 'react-router-dom'
import { Radio, BarChart2, Search, Trophy, Target, TrendingUp, X } from 'lucide-react'
import { useDark } from '../App'
import { useSimulation } from '../hooks/useApi'
import { WC_LOGO } from '../lib/utils'
import DarkModeToggle from './DarkModeToggle'

const NAV = [
  { to: '/live',      icon: Radio,     label: 'Live Tracker' },
  { to: '/standings', icon: BarChart2, label: 'Group Standings' },
  { to: '/teams',     icon: Search,    label: 'Team Explorer' },
  { to: '/bracket',   icon: Trophy,    label: 'Knockout Bracket' },
  { to: '/tracker',   icon: Target,      label: 'Prediction Tracker' },
  { to: '/analytics', icon: TrendingUp,  label: 'Analytics' },
]

export default function Sidebar({ onClose }) {
  const { data: sim } = useSimulation()
  const meta = sim?.meta ?? {}

  return (
    <div
      className="flex flex-col h-full"
      style={{
        background: 'linear-gradient(170deg, #060d18 0%, #0d1b2a 40%, #1a3a6e 80%, #1565c0 100%)',
      }}
    >
      {/* Close button (mobile) */}
      {onClose && (
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-white/60 hover:text-white hover:bg-white/10 lg:hidden"
        >
          <X size={18} />
        </button>
      )}

      {/* Logo */}
      <div className="px-6 pt-7 pb-5 text-center">
        <img
          src={WC_LOGO}
          alt="FIFA WC 2026"
          className="h-20 mx-auto rounded-xl shadow-lg shadow-black/40"
          onError={e => { e.target.style.display = 'none' }}
        />
        <p className="text-white font-extrabold text-xl mt-3 tracking-tight">WC Oracle</p>
        <p className="text-white/50 text-xs mt-0.5">FIFA World Cup 2026</p>
      </div>

      <div className="mx-5 border-t border-white/10" />

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon size={17} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="mx-5 border-t border-white/10" />

      {/* Meta + dark toggle */}
      <div className="px-5 py-5 space-y-3">
        {meta.n_simulations && (
          <div className="text-white/60 text-xs space-y-1.5">
            <div>🎲 <span className="text-white/85 font-semibold">{meta.n_simulations?.toLocaleString()}</span> simulations</div>
            <div>⚽ <span className="text-white/85 font-semibold">{meta.played_matches}</span> matches played</div>
          </div>
        )}
        <DarkModeToggle />
        <p className="text-white/30 text-xs text-center pt-1">
          XGBoost · Poisson · Elo
        </p>
      </div>
    </div>
  )
}
