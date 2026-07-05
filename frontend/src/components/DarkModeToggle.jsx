import { Sun, Moon } from 'lucide-react'
import { useDark } from '../App'

export default function DarkModeToggle() {
  const { dark, toggle } = useDark()

  return (
    <button
      onClick={toggle}
      className="flex items-center gap-2 w-full px-3 py-2 rounded-xl
                 bg-white/10 hover:bg-white/15 text-white/80 hover:text-white
                 text-sm font-medium transition-all duration-150"
    >
      {dark ? <Sun size={15} /> : <Moon size={15} />}
      {dark ? 'Light mode' : 'Dark mode'}
    </button>
  )
}
