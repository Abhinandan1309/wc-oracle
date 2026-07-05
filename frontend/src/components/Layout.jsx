import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import Sidebar from './Sidebar'

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-64 shrink-0">
        <Sidebar />
      </aside>

      {/* Mobile sidebar overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 flex flex-col lg:hidden
                    transition-transform duration-200
                    ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <Sidebar onClose={() => setMobileOpen(false)} />
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto bg-gray-50 dark:bg-navy-900">
        {/* Mobile top bar */}
        <div className="lg:hidden flex items-center gap-3 p-4 border-b border-gray-200 dark:border-navy-700 bg-white dark:bg-navy-800">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-navy-700"
          >
            <Menu size={20} className="text-gray-600 dark:text-gray-300" />
          </button>
          <span className="font-bold text-gray-900 dark:text-white">WC Oracle</span>
        </div>

        <div className="p-4 lg:p-8 max-w-7xl mx-auto animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
