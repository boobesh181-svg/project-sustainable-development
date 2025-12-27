import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'

export default function Topbar({ user, currentPage, onLogout }) {
  const [dbHealth, setDbHealth] = useState(false)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await apiClient.checkHealth()
        setDbHealth(health.db === true)
      } catch (error) {
        setDbHealth(false)
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30000) // Check every 30 seconds
    return () => clearInterval(interval)
  }, [])

  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="px-6 py-4 flex justify-between items-center">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">
            {currentPage === 'dashboard'
              ? 'Dashboard'
              : currentPage === 'mrv'
                ? 'MRV Reports'
                : currentPage === 'anomalies'
                  ? 'Anomalies'
                  : currentPage === 'audit'
                    ? 'Audit Trail'
                    : 'Dashboard'}
          </h2>
          <p className="text-sm text-gray-500">Real-time Materials, Resources & Verification</p>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${dbHealth ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-600">
              Database: {dbHealth ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          <div className="text-sm text-gray-600">
            {user?.email ? (
              <span>
                Signed in as <span className="font-medium text-gray-800">{user.email}</span>
              </span>
            ) : null}
          </div>

          <button
            type="button"
            onClick={onLogout}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded hover:bg-gray-200"
          >
            Logout
          </button>
        </div>
      </div>
    </header>
  )
}
