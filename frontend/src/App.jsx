import { useState, useEffect } from 'react'
import Sidebar from './layout/Sidebar'
import Topbar from './layout/Topbar'
import Dashboard from './pages/Dashboard'
import MRV from './pages/MRV'
import Anomalies from './pages/Anomalies'
import Audit from './pages/Audit'
import Loading from './components/Loading'

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard')
  const [loading, setLoading] = useState(false)

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard />
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

  if (loading) {
    return <Loading />
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
      <div className="flex-1 flex flex-col">
        <Topbar />
        <main className="flex-1 overflow-auto p-6">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}

export default App
