import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import Loading from '../components/Loading'

export default function Anomalies() {
  const [anomalies, setAnomalies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [projectId, setProjectId] = useState(null)

  useEffect(() => {
    const loadAnomalies = async () => {
      try {
        setLoading(true)
        const projects = await apiClient.fetchProjects(1)
        const first = Array.isArray(projects) ? projects[0] : null
        if (!first?.id) {
          setProjectId(null)
          setAnomalies([])
          setError(null)
          return
        }

        setProjectId(first.id)
        const data = await apiClient.fetchAnomalies(first.id)
        setAnomalies(Array.isArray(data) ? data : [])
        setError(null)
      } catch (err) {
        setError(err?.message || 'Failed to load anomalies')
        setAnomalies([])
      } finally {
        setLoading(false)
      }
    }

    loadAnomalies()
  }, [])

  const getSeverityColor = (severity) => {
    const colors = {
      HIGH: 'bg-red-100 text-red-800 border-red-300',
      MEDIUM: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      LOW: 'bg-blue-100 text-blue-800 border-blue-300',
    }
    return colors[severity] || 'bg-gray-100 text-gray-800'
  }

  const getSeverityIcon = (severity) => {
    const icons = {
      HIGH: '🔴',
      MEDIUM: '🟡',
      LOW: '🔵',
    }
    return icons[severity] || '⚪'
  }

  if (loading) return <Loading />
  if (error) return <div className="text-red-600">Error: {error}</div>

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Anomaly Detection</h1>
        <p className="text-gray-600 mt-2">Automated rules engine detects suspicious patterns</p>
        {projectId && <p className="text-xs text-gray-500 mt-1">Project: {projectId}</p>}
      </div>

      {anomalies.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <p className="text-gray-600">✅ No anomalies detected</p>
        </div>
      ) : (
        <div className="space-y-4">
          {anomalies.map((anomaly) => (
            <div
              key={anomaly.id}
              className={`border-l-4 bg-white p-6 rounded-lg shadow hover:shadow-md transition-shadow ${getSeverityColor(anomaly.severity)}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  <span className="text-2xl">{getSeverityIcon(anomaly.severity)}</span>
                  <div>
                    <h3 className="font-semibold text-gray-900">{anomaly.rule_code || 'Unknown Rule'}</h3>
                    <p className="text-sm text-gray-600 mt-1">{anomaly.description || 'No description'}</p>
                    <div className="mt-2 text-xs text-gray-500">
                      <p>
                        Token: {anomaly.token_uid ? String(anomaly.token_uid).slice(0, 12) + '…' : '—'}
                      </p>
                      <p>Detected: {anomaly.detected_at ? new Date(anomaly.detected_at).toLocaleString() : '—'}</p>
                    </div>
                  </div>
                </div>
                <button className="text-sm font-medium text-blue-600 hover:text-blue-800 whitespace-nowrap ml-4">
                  Review
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
