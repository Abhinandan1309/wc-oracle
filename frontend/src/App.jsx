import { createContext, useContext, useState, useCallback } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Live from './pages/Live'
import Standings from './pages/Standings'
import TeamExplorer from './pages/TeamExplorer'
import BracketPage from './pages/BracketPage'
import PredictionTracker from './pages/PredictionTracker'
import AnalyticsPage from './pages/AnalyticsPage'

const DarkCtx = createContext(null)
export const useDark = () => useContext(DarkCtx)

export default function App() {
  const [dark, setDark] = useState(
    () => document.documentElement.classList.contains('dark')
  )

  const toggle = useCallback(() => {
    const next = !dark
    setDark(next)
    document.documentElement.classList.toggle('dark', next)
    localStorage.setItem('wco-theme', next ? 'dark' : 'light')
  }, [dark])

  return (
    <DarkCtx.Provider value={{ dark, toggle }}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/live" replace />} />
            <Route path="live"      element={<Live />} />
            <Route path="standings" element={<Standings />} />
            <Route path="teams"     element={<TeamExplorer />} />
            <Route path="bracket"   element={<BracketPage />} />
            <Route path="tracker"   element={<PredictionTracker />} />
            <Route path="analytics" element={<AnalyticsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DarkCtx.Provider>
  )
}
