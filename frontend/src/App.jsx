import { useState, useEffect } from 'react'
import Sidebar from './layout/Sidebar'
import Topbar from './layout/Topbar'
import Dashboard from './pages/Dashboard'
import Projects from './pages/Projects'
import MRV from './pages/MRV'
import Anomalies from './pages/Anomalies'
import Audit from './pages/Audit'
import Loading from './components/Loading'
import Login from './pages/Login'
import { apiClient } from './api/client'

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard')
  const [loading, setLoading] = useState(true)
  const [user, setUser] = useState(null)

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard />
      case 'projects':
        return <Projects />
      case 'mrv':
        return <MRV />
      case 'anomalies':
        return <Anomalies />
      case 'audit':
        return <Audit />
      default:
        return <Dashboard />
    }
  }

  useEffect(() => {
    const boot = async () => {
      try {
        const me = await apiClient.fetchMe()
        setUser(me)
      } catch {
        setUser(null)
      } finally {
        setLoading(false)
      }
    }
    boot()
  }, [])

  const onLogout = async () => {
    try {
      await apiClient.logout()
    } finally {
      setUser(null)
      setCurrentPage('dashboard')
    }
  }

  if (loading) return <Loading />

  if (!user) {
    return <Login onLoggedIn={setUser} />
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
      <div className="flex-1 flex flex-col">
        <Topbar user={user} currentPage={currentPage} onLogout={onLogout} />
        <main className="flex-1 overflow-auto p-6">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}

export default App
