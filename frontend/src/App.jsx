import { useState, useEffect } from 'react'
import Sidebar from './layout/Sidebar'
import Topbar from './layout/Topbar'
import Dashboard from './pages/Dashboard'
import CompanyOverview from './pages/CompanyOverview'
import Projects from './pages/Projects'
import MRV from './pages/MRV'
import Anomalies from './pages/Anomalies'
import Audit from './pages/Audit'
import Loading from './components/Loading'
import Login from './pages/Login'
import SupplierPortal from './pages/SupplierPortal'
import { apiClient } from './api/client'

function App() {
  const [currentPage, setCurrentPage] = useState('company')
  const [loading, setLoading] = useState(true)
  const [user, setUser] = useState(null)

  const renderPage = () => {
    switch (currentPage) {
      case 'supplier':
        return <SupplierPortal />
      case 'company':
        return <CompanyOverview />
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
        return <CompanyOverview />
    }
  }

  useEffect(() => {
    const boot = async () => {
      try {
        const me = await apiClient.fetchMe()
        setUser(me)
        setCurrentPage(me?.role === 'supplier' ? 'supplier' : 'company')
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
      setCurrentPage('company')
    }
  }

  if (loading) return <Loading />

  if (!user) {
    return <Login onLoggedIn={(me) => {
      setUser(me)
      setCurrentPage(me?.role === 'supplier' ? 'supplier' : 'company')
    }} />
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar user={user} currentPage={currentPage} onPageChange={setCurrentPage} />
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
